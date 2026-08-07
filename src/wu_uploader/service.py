"""Application assembly and process lifecycle management."""

import logging
import signal
import threading
from types import FrameType
from typing import Protocol

from pydantic import SecretStr

from wu_uploader.measurements import MeasurementState
from wu_uploader.models import ApplicationConfig
from wu_uploader.mqtt import MqttIngestion, create_mqtt_ingestion
from wu_uploader.outputs.weather_underground import WeatherUndergroundUploader
from wu_uploader.scheduler import ObservationScheduler

LOGGER: logging.Logger = logging.getLogger(__name__)


class MqttLifecycle(Protocol):
    """Start and stop MQTT ingestion."""

    def start(self) -> None:
        """Start MQTT ingestion.

        :return: None.
        """
        ...

    def stop(self) -> None:
        """Stop MQTT ingestion.

        :return: None.
        """
        ...


class SchedulerLifecycle(Protocol):
    """Run and stop observation scheduling."""

    def run(self) -> None:
        """Run until a stop is requested.

        :return: None.
        """
        ...

    def stop(self) -> None:
        """Stop scheduling new observations.

        :return: None.
        """
        ...


class WeatherUploaderService:
    """Coordinate MQTT ingestion, scheduling, and graceful shutdown.

    :param mqtt: MQTT ingestion lifecycle.
    :param scheduler: Observation scheduler lifecycle.
    """

    def __init__(self, mqtt: MqttLifecycle, scheduler: SchedulerLifecycle) -> None:
        """Initialize service lifecycle state.

        :param mqtt: MQTT ingestion lifecycle.
        :param scheduler: Observation scheduler lifecycle.
        """
        self._mqtt: MqttLifecycle = mqtt
        self._scheduler: SchedulerLifecycle = scheduler
        self._stopping: bool = False
        self._lifecycle_lock: threading.RLock = threading.RLock()

    def run(self) -> None:
        """Start components and run until scheduling is stopped.

        MQTT startup failures are isolated so scheduling and shutdown remain
        operational. Paho handles broker reconnection after successful local
        network-loop startup.

        :return: None.
        """
        try:
            try:
                self._mqtt.start()
            except Exception:
                LOGGER.error("event=mqtt_start_failed reason=local_transport_error")
            LOGGER.info("event=service_started")
            self._scheduler.run()
        finally:
            self.stop()
            LOGGER.info("event=service_stopped")

    def stop(self) -> None:
        """Stop new uploads and disconnect MQTT exactly once.

        :return: None.
        """
        with self._lifecycle_lock:
            if self._stopping:
                return
            self._stopping = True

        self._scheduler.stop()
        try:
            self._mqtt.stop()
        except Exception:
            LOGGER.error("event=mqtt_stop_failed reason=local_transport_error")

    def handle_signal(self, signum: int, _frame: FrameType | None) -> None:
        """Request graceful shutdown for a process signal.

        :param signum: Received operating-system signal number.
        :param _frame: Interrupted Python frame, when available.
        :return: None.
        """
        signal_name: str
        try:
            signal_name = signal.Signals(signum).name
        except ValueError:
            signal_name = str(signum)
        LOGGER.info("event=shutdown_requested signal=%s", signal_name)
        self.stop()


def run_application(configuration: ApplicationConfig) -> None:
    """Assemble and run the configured application until shutdown.

    :param configuration: Fully validated runtime configuration.
    :return: None.
    """
    state: MeasurementState = MeasurementState(configuration.sources)
    mqtt: MqttIngestion = create_mqtt_ingestion(
        configuration.mqtt,
        configuration.credentials,
        configuration.sources,
        state,
    )
    uploader: WeatherUndergroundUploader | None = _create_weather_underground_uploader(configuration)
    scheduler: ObservationScheduler = ObservationScheduler(configuration.upload.interval, state, uploader)
    service: WeatherUploaderService = WeatherUploaderService(mqtt, scheduler)

    signal.signal(signal.SIGINT, service.handle_signal)
    signal.signal(signal.SIGTERM, service.handle_signal)
    service.run()


def _create_weather_underground_uploader(
    configuration: ApplicationConfig,
) -> WeatherUndergroundUploader | None:
    """Create the configured Weather Underground output adapter.

    :param configuration: Fully validated runtime configuration.
    :return: Enabled uploader, or ``None`` when the output is disabled.
    :raises RuntimeError: If validated enabled output credentials are unavailable.
    """
    if not configuration.outputs.weather_underground.enabled:
        return None

    station_id: SecretStr | None = configuration.credentials.wu_station_id
    station_key: SecretStr | None = configuration.credentials.wu_station_key
    if station_id is None or station_key is None:
        raise RuntimeError("Weather Underground credentials are unavailable after configuration validation")
    return WeatherUndergroundUploader(station_id, station_key, configuration.upload.timeout)

import logging
import signal

import pytest

from wu_uploader.service import WeatherUploaderService


class FakeMqttLifecycle:
    """Record MQTT lifecycle calls with optional failures."""

    def __init__(self, *, start_error: bool = False, stop_error: bool = False) -> None:
        """Initialize configured MQTT lifecycle behavior.

        :param start_error: Whether startup raises an exception.
        :param stop_error: Whether shutdown raises an exception.
        """
        self.start_error: bool = start_error
        self.stop_error: bool = stop_error
        self.start_calls: int = 0
        self.stop_calls: int = 0

    def start(self) -> None:
        """Record startup and optionally fail.

        :return: None.
        :raises RuntimeError: When startup failure is configured.
        """
        self.start_calls += 1
        if self.start_error:
            raise RuntimeError("sensitive MQTT startup detail")

    def stop(self) -> None:
        """Record shutdown and optionally fail.

        :return: None.
        :raises RuntimeError: When shutdown failure is configured.
        """
        self.stop_calls += 1
        if self.stop_error:
            raise RuntimeError("sensitive MQTT shutdown detail")


class FakeSchedulerLifecycle:
    """Record scheduler lifecycle calls and optionally request a signal shutdown."""

    def __init__(self, *, shutdown_signal: signal.Signals | None = None) -> None:
        """Initialize scheduler lifecycle behavior.

        :param shutdown_signal: Optional signal delivered while the scheduler runs.
        """
        self.shutdown_signal: signal.Signals | None = shutdown_signal
        self.service: WeatherUploaderService | None = None
        self.run_calls: int = 0
        self.stop_calls: int = 0

    def run(self) -> None:
        """Record execution and optionally deliver the configured signal.

        :return: None.
        """
        self.run_calls += 1
        if self.shutdown_signal is not None and self.service is not None:
            self.service.handle_signal(self.shutdown_signal, None)

    def stop(self) -> None:
        """Record a stop request.

        :return: None.
        """
        self.stop_calls += 1


class TestWeatherUploaderService:
    """Test component coordination and graceful process lifecycle."""

    def test_runs_and_stops_components_in_lifecycle_order(self) -> None:
        """Verify that normal scheduler completion disconnects MQTT cleanly."""
        mqtt: FakeMqttLifecycle = FakeMqttLifecycle()
        scheduler: FakeSchedulerLifecycle = FakeSchedulerLifecycle()
        service: WeatherUploaderService = WeatherUploaderService(mqtt, scheduler)

        service.run()

        assert mqtt.start_calls == 1
        assert scheduler.run_calls == 1
        assert scheduler.stop_calls == 1
        assert mqtt.stop_calls == 1

    def test_mqtt_start_failure_does_not_terminate_scheduler(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Verify that a local MQTT failure does not prevent unrelated scheduling."""
        mqtt: FakeMqttLifecycle = FakeMqttLifecycle(start_error=True)
        scheduler: FakeSchedulerLifecycle = FakeSchedulerLifecycle()
        service: WeatherUploaderService = WeatherUploaderService(mqtt, scheduler)

        with caplog.at_level(logging.INFO):
            service.run()

        assert scheduler.run_calls == 1
        assert mqtt.stop_calls == 1
        assert "event=mqtt_start_failed reason=local_transport_error" in caplog.messages
        assert "sensitive" not in caplog.text

    @pytest.mark.parametrize("shutdown_signal", [signal.SIGINT, signal.SIGTERM])
    def test_signal_stops_scheduler_and_disconnects_mqtt_once(
        self,
        shutdown_signal: signal.Signals,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Verify that process signals request idempotent shutdown without traceback."""
        mqtt: FakeMqttLifecycle = FakeMqttLifecycle()
        scheduler: FakeSchedulerLifecycle = FakeSchedulerLifecycle(shutdown_signal=shutdown_signal)
        service: WeatherUploaderService = WeatherUploaderService(mqtt, scheduler)
        scheduler.service = service

        with caplog.at_level(logging.INFO):
            service.run()

        assert scheduler.stop_calls == 1
        assert mqtt.stop_calls == 1
        assert f"event=shutdown_requested signal={shutdown_signal.name}" in caplog.messages
        assert "event=service_stopped" in caplog.messages

    def test_mqtt_stop_failure_is_sanitized_and_does_not_escape(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Verify that shutdown transport failures remain sanitized and contained."""
        mqtt: FakeMqttLifecycle = FakeMqttLifecycle(stop_error=True)
        scheduler: FakeSchedulerLifecycle = FakeSchedulerLifecycle()
        service: WeatherUploaderService = WeatherUploaderService(mqtt, scheduler)

        with caplog.at_level(logging.INFO):
            service.run()

        assert "event=mqtt_stop_failed reason=local_transport_error" in caplog.messages
        assert "sensitive" not in caplog.text

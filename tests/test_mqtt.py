import logging
import ssl
from typing import cast

import paho.mqtt.client as mqtt
import pytest
from paho.mqtt.enums import CallbackAPIVersion, MQTTErrorCode, MQTTProtocolVersion
from pydantic import SecretStr

from wu_uploader.measurements import MeasurementSnapshot, MeasurementState
from wu_uploader.models import Credentials, MqttConfig, PayloadFormat, SourceConfig, Target, Unit
from wu_uploader.mqtt import (
    MAX_RECONNECT_DELAY_SECONDS,
    MIN_RECONNECT_DELAY_SECONDS,
    MQTT_QOS,
    ConnectHandler,
    DisconnectHandler,
    MessageHandler,
    MqttConnectionError,
    MqttIngestion,
    PahoMqttTransport,
)


def _mqtt_config(*, tls: bool = False) -> MqttConfig:
    """Build MQTT broker configuration for ingestion tests.

    :param tls: Whether verified TLS should be enabled.
    :return: Validated MQTT configuration.
    """
    values: dict[str, object] = {
        "host": "mqtt.example.local",
        "port": 8883 if tls else 1883,
        "client_id": "test-uploader",
        "keepalive": "30s",
        "tls": tls,
    }
    return MqttConfig.model_validate(values)


def _source(
    target: Target,
    *,
    topic: str,
    payload: PayloadFormat = PayloadFormat.SCALAR,
    value: str | None = None,
    accept_retained: bool = False,
) -> SourceConfig:
    """Build one source configuration for MQTT routing tests.

    :param target: Normalized measurement target.
    :param topic: Exact MQTT source topic.
    :param payload: MQTT payload encoding.
    :param value: Optional top-level JSON key.
    :param accept_retained: Whether retained messages are accepted.
    :return: Validated source configuration.
    """
    unit_by_target: dict[Target, Unit] = {
        Target.TEMPERATURE: Unit.CELSIUS,
        Target.HUMIDITY: Unit.PERCENT,
        Target.PRESSURE: Unit.HPA,
    }
    values: dict[str, object] = {
        "topic": topic,
        "payload": payload.value,
        "unit": unit_by_target[target].value,
        "max_age": "60s",
        "accept_retained": accept_retained,
        "target": target.value,
    }
    if value is not None:
        values["value"] = value
    return SourceConfig.model_validate(values)


class FakeTransport:
    """In-memory MQTT transport that exposes callbacks to tests."""

    def __init__(self) -> None:
        """Initialize an idle transport with no installed handlers."""
        self.on_connect: ConnectHandler | None = None
        self.on_disconnect: DisconnectHandler | None = None
        self.on_message: MessageHandler | None = None
        self.started: bool = False
        self.stopped: bool = False
        self.subscriptions: list[tuple[str, int]] = []
        self.rejected_topics: set[str] = set()

    def set_handlers(
        self,
        *,
        on_connect: ConnectHandler,
        on_disconnect: DisconnectHandler,
        on_message: MessageHandler,
    ) -> None:
        """Store ingestion event handlers.

        :param on_connect: Connection event handler.
        :param on_disconnect: Disconnection event handler.
        :param on_message: Message event handler.
        :return: None.
        """
        self.on_connect = on_connect
        self.on_disconnect = on_disconnect
        self.on_message = on_message

    def start(self) -> None:
        """Record network-loop startup.

        :return: None.
        """
        self.started = True

    def stop(self) -> None:
        """Record network-loop shutdown.

        :return: None.
        """
        self.stopped = True

    def subscribe(self, topic: str, qos: int) -> bool:
        """Record a subscription and return its configured outcome.

        :param topic: Exact topic requested by ingestion.
        :param qos: Requested quality of service.
        :return: Whether the topic is locally accepted.
        """
        self.subscriptions.append((topic, qos))
        return topic not in self.rejected_topics

    def trigger_connect(self, *, connected: bool = True, reason: str = "Success") -> None:
        """Deliver a simulated connection result.

        :param connected: Whether the broker accepted the connection.
        :param reason: Human-readable connection reason.
        :return: None.
        """
        assert self.on_connect is not None
        self.on_connect(connected, reason)

    def trigger_disconnect(self, *, unexpected: bool, reason: str) -> None:
        """Deliver a simulated disconnection.

        :param unexpected: Whether automatic reconnection is expected.
        :param reason: Human-readable disconnection reason.
        :return: None.
        """
        assert self.on_disconnect is not None
        self.on_disconnect(unexpected, reason)

    def trigger_message(self, topic: str, payload: bytes, *, retained: bool = False) -> None:
        """Deliver a simulated MQTT message.

        :param topic: MQTT message topic.
        :param payload: Raw MQTT payload.
        :param retained: MQTT retained flag.
        :return: None.
        """
        assert self.on_message is not None
        self.on_message(topic, payload, retained)


class RecordingProcessor:
    """Measurement processor that records source calls and optional failures."""

    def __init__(self, failing_sources: set[str] | None = None) -> None:
        """Initialize the processor with optional simulated failures.

        :param failing_sources: Source identifiers that should raise during processing.
        """
        self.calls: list[tuple[str, bytes]] = []
        self.failing_sources: set[str] = failing_sources or set()

    def process(self, source_name: str, payload: bytes) -> object | None:
        """Record or reject a source payload.

        :param source_name: Configured source identifier.
        :param payload: Raw MQTT payload.
        :return: An opaque success marker.
        :raises RuntimeError: If the source is configured to fail.
        """
        self.calls.append((source_name, payload))
        if source_name in self.failing_sources:
            raise RuntimeError("simulated processing failure")
        return object()


class FakePahoClient:
    """Small Paho client double for transport configuration tests."""

    def __init__(self) -> None:
        """Initialize recorded Paho state and successful default results."""
        self.on_connect: object | None = None
        self.on_connect_fail: object | None = None
        self.on_disconnect: object | None = None
        self.on_message: object | None = None
        self.reconnect_delay: tuple[int, int] | None = None
        self.tls_context: ssl.SSLContext | None = None
        self.credentials: tuple[str, str | None] | None = None
        self.connection: tuple[str, int, int] | None = None
        self.loop_started: bool = False
        self.loop_result: MQTTErrorCode = MQTTErrorCode.MQTT_ERR_SUCCESS
        self.disconnected: bool = False
        self.loop_stopped: bool = False
        self.subscribe_result: MQTTErrorCode = MQTTErrorCode.MQTT_ERR_SUCCESS
        self.subscriptions: list[tuple[str, int]] = []

    def reconnect_delay_set(self, min_delay: int = 1, max_delay: int = 120) -> None:
        """Record configured reconnect limits.

        :param min_delay: Initial reconnect delay in seconds.
        :param max_delay: Maximum reconnect delay in seconds.
        :return: None.
        """
        self.reconnect_delay = (min_delay, max_delay)

    def tls_set_context(self, context: ssl.SSLContext) -> None:
        """Record the TLS context.

        :param context: Verified TLS context.
        :return: None.
        """
        self.tls_context = context

    def username_pw_set(self, username: str, password: str | None = None) -> None:
        """Record broker credentials without logging them.

        :param username: MQTT username.
        :param password: Optional MQTT password.
        :return: None.
        """
        self.credentials = (username, password)

    def connect_async(self, host: str, port: int = 1883, keepalive: int = 60) -> None:
        """Record asynchronous connection parameters.

        :param host: MQTT broker host.
        :param port: MQTT broker port.
        :param keepalive: MQTT keepalive interval in seconds.
        :return: None.
        """
        self.connection = (host, port, keepalive)

    def loop_start(self) -> MQTTErrorCode:
        """Record network-loop startup.

        :return: Configured local Paho result code.
        """
        self.loop_started = True
        return self.loop_result

    def disconnect(self) -> MQTTErrorCode:
        """Record disconnection.

        :return: Successful local Paho result code.
        """
        self.disconnected = True
        return MQTTErrorCode.MQTT_ERR_SUCCESS

    def loop_stop(self) -> MQTTErrorCode:
        """Record network-loop shutdown.

        :return: Successful local Paho result code.
        """
        self.loop_stopped = True
        return MQTTErrorCode.MQTT_ERR_SUCCESS

    def subscribe(self, topic: str, qos: int = 0) -> tuple[MQTTErrorCode, int]:
        """Record one subscription request.

        :param topic: Exact MQTT topic.
        :param qos: Requested quality of service.
        :return: Configured result code and generated message identifier.
        """
        self.subscriptions.append((topic, qos))
        return self.subscribe_result, len(self.subscriptions)


class FakePahoClientFactory:
    """Record Paho constructor arguments and return a client double."""

    def __init__(self, client: FakePahoClient) -> None:
        """Initialize the factory with its client double.

        :param client: Paho-compatible client double to return.
        """
        self.client: FakePahoClient = client
        self.arguments: tuple[CallbackAPIVersion, str, bool, MQTTProtocolVersion] | None = None

    def __call__(
        self,
        *,
        callback_api_version: CallbackAPIVersion,
        client_id: str,
        clean_session: bool,
        protocol: MQTTProtocolVersion,
    ) -> mqtt.Client:
        """Capture constructor arguments and return the configured client.

        :param callback_api_version: Requested Paho callback API.
        :param client_id: Configured MQTT client identifier.
        :param clean_session: Requested MQTT session behavior.
        :param protocol: Requested MQTT protocol version.
        :return: Paho-compatible client double.
        """
        self.arguments = (callback_api_version, client_id, clean_session, protocol)
        return cast(mqtt.Client, self.client)


class TestMqttIngestion:
    """Test source routing, retained filtering, and resubscription."""

    def test_starts_and_stops_transport(self) -> None:
        """Verify that lifecycle calls are delegated to the transport."""
        transport: FakeTransport = FakeTransport()
        ingestion: MqttIngestion = MqttIngestion(_mqtt_config(), {}, RecordingProcessor(), transport)

        ingestion.start()
        ingestion.stop()

        assert transport.started is True
        assert transport.stopped is True

    def test_subscribes_once_per_distinct_topic_after_each_connection(self) -> None:
        """Verify QoS 1 deduplication and resubscription after reconnection."""
        sources: dict[str, SourceConfig] = {
            "temperature": _source(Target.TEMPERATURE, topic="sensors/outdoor"),
            "humidity": _source(Target.HUMIDITY, topic="sensors/outdoor"),
            "pressure": _source(Target.PRESSURE, topic="sensors/pressure"),
        }
        transport: FakeTransport = FakeTransport()
        MqttIngestion(_mqtt_config(), sources, RecordingProcessor(), transport)

        transport.trigger_connect()
        transport.trigger_connect()

        expected_once: list[tuple[str, int]] = [
            ("sensors/outdoor", MQTT_QOS),
            ("sensors/pressure", MQTT_QOS),
        ]
        assert transport.subscriptions == expected_once * 2

    def test_rejected_connection_does_not_subscribe(self, caplog: pytest.LogCaptureFixture) -> None:
        """Verify that rejected connections wait for Paho reconnection without subscribing."""
        transport: FakeTransport = FakeTransport()
        sources: dict[str, SourceConfig] = {"pressure": _source(Target.PRESSURE, topic="sensors/pressure")}
        MqttIngestion(_mqtt_config(), sources, RecordingProcessor(), transport)

        with caplog.at_level(logging.WARNING):
            transport.trigger_connect(connected=False, reason="Not authorized")

        assert transport.subscriptions == []
        assert "event=mqtt_connection_failed host=mqtt.example.local reason=Not authorized" in caplog.messages

    def test_processes_all_sources_sharing_a_topic(self) -> None:
        """Verify that one message independently updates every matching source."""
        sources: dict[str, SourceConfig] = {
            "temperature": _source(
                Target.TEMPERATURE,
                topic="sensors/outdoor",
                payload=PayloadFormat.JSON,
                value="temperature",
            ),
            "humidity": _source(
                Target.HUMIDITY,
                topic="sensors/outdoor",
                payload=PayloadFormat.JSON,
                value="humidity",
            ),
        }
        state: MeasurementState = MeasurementState(sources, clock=lambda: 10.0)
        transport: FakeTransport = FakeTransport()
        MqttIngestion(_mqtt_config(), sources, state, transport)

        transport.trigger_message("sensors/outdoor", b'{"temperature": 18.5, "humidity": 62}')

        snapshot: MeasurementSnapshot = state.snapshot()
        assert snapshot.get(Target.TEMPERATURE) is not None
        assert snapshot.get(Target.HUMIDITY) is not None

    def test_applies_retained_policy_per_matching_source(self) -> None:
        """Verify that retained messages update only sources that accept them."""
        sources: dict[str, SourceConfig] = {
            "temperature": _source(Target.TEMPERATURE, topic="sensors/outdoor"),
            "humidity": _source(Target.HUMIDITY, topic="sensors/outdoor", accept_retained=True),
        }
        processor: RecordingProcessor = RecordingProcessor()
        transport: FakeTransport = FakeTransport()
        MqttIngestion(_mqtt_config(), sources, processor, transport)

        transport.trigger_message("sensors/outdoor", b"50", retained=True)

        assert processor.calls == [("humidity", b"50")]

    def test_source_failure_does_not_block_other_matching_sources(self, caplog: pytest.LogCaptureFixture) -> None:
        """Verify that an unexpected source failure cannot terminate message routing."""
        sources: dict[str, SourceConfig] = {
            "temperature": _source(Target.TEMPERATURE, topic="sensors/outdoor"),
            "humidity": _source(Target.HUMIDITY, topic="sensors/outdoor"),
        }
        processor: RecordingProcessor = RecordingProcessor({"temperature"})
        transport: FakeTransport = FakeTransport()
        MqttIngestion(_mqtt_config(), sources, processor, transport)

        with caplog.at_level(logging.ERROR):
            transport.trigger_message("sensors/outdoor", b"50")

        assert processor.calls == [("temperature", b"50"), ("humidity", b"50")]
        assert "event=mqtt_processing_failed source=temperature reason=internal_error" in caplog.messages

    @pytest.mark.parametrize(
        ("unexpected", "level", "reconnecting"),
        [
            (True, logging.WARNING, "true"),
            (False, logging.INFO, "false"),
        ],
    )
    def test_logs_disconnect_state(
        self,
        unexpected: bool,
        level: int,
        reconnecting: str,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Verify that disconnect logs distinguish reconnection from shutdown."""
        transport: FakeTransport = FakeTransport()
        MqttIngestion(_mqtt_config(), {}, RecordingProcessor(), transport)

        with caplog.at_level(level):
            transport.trigger_disconnect(unexpected=unexpected, reason="connection lost")

        assert f"reconnecting={reconnecting}" in caplog.messages[0]


class TestPahoMqttTransport:
    """Test Paho configuration without opening a broker connection."""

    def test_configures_bounded_reconnection_tls_and_credentials(self) -> None:
        """Verify reconnect limits and secure authenticated broker configuration."""
        client: FakePahoClient = FakePahoClient()
        credentials: Credentials = Credentials(
            mqtt_username=SecretStr("mqtt-user"),
            mqtt_password=SecretStr("mqtt-password"),
        )
        factory: FakePahoClientFactory = FakePahoClientFactory(client)

        PahoMqttTransport(_mqtt_config(tls=True), credentials, factory)

        assert factory.arguments == (
            CallbackAPIVersion.VERSION2,
            "test-uploader",
            True,
            MQTTProtocolVersion.MQTTv311,
        )
        assert client.reconnect_delay == (MIN_RECONNECT_DELAY_SECONDS, MAX_RECONNECT_DELAY_SECONDS)
        assert client.tls_context is not None
        assert client.tls_context.verify_mode is ssl.CERT_REQUIRED
        assert client.tls_context.check_hostname is True
        assert client.credentials == ("mqtt-user", "mqtt-password")

    def test_starts_subscribes_and_stops_client(self) -> None:
        """Verify Paho lifecycle parameters and local subscription results."""
        client: FakePahoClient = FakePahoClient()
        factory: FakePahoClientFactory = FakePahoClientFactory(client)
        transport: PahoMqttTransport = PahoMqttTransport(
            _mqtt_config(),
            Credentials(),
            factory,
        )

        transport.start()
        accepted: bool = transport.subscribe("sensors/pressure", MQTT_QOS)
        transport.stop()

        assert client.connection == ("mqtt.example.local", 1883, 30)
        assert client.loop_started is True
        assert accepted is True
        assert client.subscriptions == [("sensors/pressure", MQTT_QOS)]
        assert client.disconnected is True
        assert client.loop_stopped is True

    def test_rejects_failed_network_loop_start(self) -> None:
        """Verify that a local Paho loop failure is surfaced clearly."""
        client: FakePahoClient = FakePahoClient()
        client.loop_result = MQTTErrorCode.MQTT_ERR_INVAL
        factory: FakePahoClientFactory = FakePahoClientFactory(client)
        transport: PahoMqttTransport = PahoMqttTransport(
            _mqtt_config(),
            Credentials(),
            factory,
        )

        with pytest.raises(MqttConnectionError, match="cannot start MQTT network loop"):
            transport.start()

"""MQTT transport and measurement ingestion."""

import logging
import ssl
from collections import defaultdict
from collections.abc import Callable, Mapping
from typing import Final, Protocol, cast

import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion, MQTTErrorCode, MQTTProtocolVersion
from paho.mqtt.properties import Properties
from paho.mqtt.reasoncodes import ReasonCode
from pydantic import SecretStr

from wu_uploader.models import Credentials, MqttConfig, SourceConfig

LOGGER: logging.Logger = logging.getLogger(__name__)
MQTT_QOS: Final[int] = 1
MIN_RECONNECT_DELAY_SECONDS: Final[int] = 1
MAX_RECONNECT_DELAY_SECONDS: Final[int] = 60

type ConnectHandler = Callable[[bool, str], None]
type DisconnectHandler = Callable[[bool, str], None]
type MessageHandler = Callable[[str, bytes, bool], None]


class MqttConnectionError(RuntimeError):
    """Raised when the local MQTT network loop cannot be started."""


class MeasurementProcessor(Protocol):
    """Process MQTT payloads for named measurement sources."""

    def process(self, source_name: str, payload: bytes) -> object | None:
        """Process one payload for a configured source.

        :param source_name: Configured source identifier.
        :param payload: Raw MQTT payload.
        :return: The processed measurement, or ``None`` when rejected.
        """
        ...


class MqttTransport(Protocol):
    """Minimal MQTT transport boundary used by measurement ingestion."""

    def set_handlers(
        self,
        *,
        on_connect: ConnectHandler,
        on_disconnect: DisconnectHandler,
        on_message: MessageHandler,
    ) -> None:
        """Install transport event handlers.

        :param on_connect: Handler for successful and rejected connections.
        :param on_disconnect: Handler for expected and unexpected disconnects.
        :param on_message: Handler for incoming MQTT messages.
        :return: None.
        """
        ...

    def start(self) -> None:
        """Start connecting and processing network events.

        :return: None.
        :raises MqttConnectionError: If the local network loop cannot start.
        """
        ...

    def stop(self) -> None:
        """Disconnect and stop processing network events.

        :return: None.
        """
        ...

    def subscribe(self, topic: str, qos: int) -> bool:
        """Request one MQTT subscription.

        :param topic: Exact topic to subscribe to.
        :param qos: Requested MQTT quality of service.
        :return: Whether the request was accepted locally.
        """
        ...


class _TlsClient(Protocol):
    """Paho TLS configuration surface with complete local typing."""

    def tls_set_context(self, context: ssl.SSLContext) -> None:
        """Install a verified TLS context.

        :param context: TLS context using normal certificate verification.
        :return: None.
        """
        ...


class _PahoClientFactory(Protocol):
    """Construct a configured Paho client."""

    def __call__(
        self,
        *,
        callback_api_version: CallbackAPIVersion,
        client_id: str,
        clean_session: bool,
        protocol: MQTTProtocolVersion,
    ) -> mqtt.Client:
        """Create a Paho client using the required MQTT contract.

        :param callback_api_version: Paho callback API version.
        :param client_id: Configured MQTT client identifier.
        :param clean_session: Whether MQTT session state is cleared per connection.
        :param protocol: MQTT protocol version.
        :return: Configured Paho client instance.
        """
        ...


_DEFAULT_CLIENT_FACTORY: Final[_PahoClientFactory] = cast(_PahoClientFactory, mqtt.Client)


class PahoMqttTransport:
    """Paho MQTT 3.1.1 transport with automatic bounded reconnection.

    :param config: MQTT broker configuration.
    :param credentials: Optional MQTT credentials.
    :param client_factory: Paho client factory replaceable by tests.
    """

    def __init__(
        self,
        config: MqttConfig,
        credentials: Credentials,
        client_factory: _PahoClientFactory = _DEFAULT_CLIENT_FACTORY,
    ) -> None:
        """Initialize and configure the Paho transport.

        :param config: MQTT broker configuration.
        :param credentials: Optional MQTT credentials.
        :param client_factory: Paho client factory replaceable by tests.
        """
        self._config: MqttConfig = config
        self._client: mqtt.Client = client_factory(
            callback_api_version=CallbackAPIVersion.VERSION2,
            client_id=config.client_id,
            clean_session=True,
            protocol=MQTTProtocolVersion.MQTTv311,
        )
        self._on_connect_handler: ConnectHandler | None = None
        self._on_disconnect_handler: DisconnectHandler | None = None
        self._on_message_handler: MessageHandler | None = None

        self._client.on_connect = self._on_connect
        self._client.on_connect_fail = self._on_connect_fail
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message
        self._client.reconnect_delay_set(
            min_delay=MIN_RECONNECT_DELAY_SECONDS,
            max_delay=MAX_RECONNECT_DELAY_SECONDS,
        )
        self._configure_security(credentials)

    def set_handlers(
        self,
        *,
        on_connect: ConnectHandler,
        on_disconnect: DisconnectHandler,
        on_message: MessageHandler,
    ) -> None:
        """Install transport event handlers.

        :param on_connect: Handler for successful and rejected connections.
        :param on_disconnect: Handler for expected and unexpected disconnects.
        :param on_message: Handler for incoming MQTT messages.
        :return: None.
        """
        self._on_connect_handler = on_connect
        self._on_disconnect_handler = on_disconnect
        self._on_message_handler = on_message

    def start(self) -> None:
        """Start the Paho background network loop and asynchronous connection.

        :return: None.
        :raises MqttConnectionError: If Paho rejects local loop startup.
        """
        self._client.connect_async(
            self._config.host,
            port=self._config.port,
            keepalive=self._config.keepalive,
        )

        loop_result: MQTTErrorCode = self._client.loop_start()
        if loop_result is not MQTTErrorCode.MQTT_ERR_SUCCESS:
            raise MqttConnectionError(f"cannot start MQTT network loop: {mqtt.error_string(loop_result)}")

    def stop(self) -> None:
        """Disconnect from the broker and stop the Paho network loop.

        :return: None.
        """
        self._client.disconnect()
        self._client.loop_stop()

    def subscribe(self, topic: str, qos: int) -> bool:
        """Subscribe to one exact topic.

        :param topic: Exact MQTT topic.
        :param qos: Requested MQTT quality of service.
        :return: Whether Paho accepted the subscription request locally.
        """
        result: MQTTErrorCode
        _message_id: int | None
        result, _message_id = self._client.subscribe(topic, qos=qos)
        return result is MQTTErrorCode.MQTT_ERR_SUCCESS

    def _configure_security(self, credentials: Credentials) -> None:
        """Configure verified TLS and optional broker authentication.

        :param credentials: Optional MQTT username and password.
        :return: None.
        """
        if self._config.tls:
            tls_client: _TlsClient = cast(_TlsClient, self._client)
            tls_client.tls_set_context(ssl.create_default_context())

        username: str | None = _secret_value(credentials.mqtt_username)
        password: str | None = _secret_value(credentials.mqtt_password)
        if username is not None and password is not None:
            self._client.username_pw_set(username, password)

    def _on_connect(
        self,
        _client: mqtt.Client,
        _userdata: object,
        _flags: mqtt.ConnectFlags,
        reason_code: ReasonCode,
        _properties: Properties | None,
    ) -> None:
        """Translate a Paho connection callback into the transport boundary.

        :param _client: Paho client that received the connection result.
        :param _userdata: Unused Paho callback user data.
        :param _flags: Paho connection flags.
        :param reason_code: Broker connection result.
        :param _properties: MQTT callback properties.
        :return: None.
        """
        if self._on_connect_handler is not None:
            self._on_connect_handler(not reason_code.is_failure, str(reason_code))

    def _on_connect_fail(self, _client: mqtt.Client, _userdata: object) -> None:
        """Report a transport-level connection failure.

        :param _client: Paho client whose connection failed.
        :param _userdata: Unused Paho callback user data.
        :return: None.
        """
        if self._on_connect_handler is not None:
            self._on_connect_handler(False, "transport_error")

    def _on_disconnect(
        self,
        _client: mqtt.Client,
        _userdata: object,
        _flags: mqtt.DisconnectFlags,
        reason_code: ReasonCode,
        _properties: Properties | None,
    ) -> None:
        """Translate a Paho disconnection callback into the transport boundary.

        :param _client: Paho client that disconnected.
        :param _userdata: Unused Paho callback user data.
        :param _flags: Paho disconnection flags.
        :param reason_code: Broker or transport disconnection reason.
        :param _properties: MQTT callback properties.
        :return: None.
        """
        if self._on_disconnect_handler is not None:
            self._on_disconnect_handler(reason_code.is_failure, str(reason_code))

    def _on_message(self, _client: mqtt.Client, _userdata: object, message: mqtt.MQTTMessage) -> None:
        """Translate a Paho message into the transport boundary.

        :param _client: Paho client that received the message.
        :param _userdata: Unused Paho callback user data.
        :param message: Received MQTT message.
        :return: None.
        """
        if self._on_message_handler is not None:
            self._on_message_handler(message.topic, bytes(message.payload), message.retain)


class MqttIngestion:
    """Route MQTT messages to configured measurement sources.

    :param config: MQTT broker configuration used for operational logging.
    :param sources: Configured measurement sources keyed by identifier.
    :param processor: Measurement processing destination.
    :param transport: MQTT transport implementation.
    """

    def __init__(
        self,
        config: MqttConfig,
        sources: Mapping[str, SourceConfig],
        processor: MeasurementProcessor,
        transport: MqttTransport,
    ) -> None:
        """Initialize source routing and install transport handlers.

        :param config: MQTT broker configuration used for operational logging.
        :param sources: Configured measurement sources keyed by identifier.
        :param processor: Measurement processing destination.
        :param transport: MQTT transport implementation.
        """
        self._config: MqttConfig = config
        self._sources: dict[str, SourceConfig] = dict(sources)
        self._processor: MeasurementProcessor = processor
        self._transport: MqttTransport = transport
        self._topic_sources: dict[str, tuple[str, ...]] = _group_sources_by_topic(self._sources)
        self._transport.set_handlers(
            on_connect=self._handle_connect,
            on_disconnect=self._handle_disconnect,
            on_message=self._handle_message,
        )

    def start(self) -> None:
        """Start MQTT ingestion.

        :return: None.
        :raises MqttConnectionError: If the local network loop cannot start.
        """
        self._transport.start()

    def stop(self) -> None:
        """Stop MQTT ingestion.

        :return: None.
        """
        self._transport.stop()

    def _handle_connect(self, connected: bool, reason: str) -> None:
        """Handle a connection result and subscribe after every successful connection.

        :param connected: Whether the broker accepted the connection.
        :param reason: Human-readable connection result.
        :return: None.
        """
        if not connected:
            LOGGER.warning("event=mqtt_connection_failed host=%s reason=%s", self._config.host, reason)
            return

        LOGGER.info("event=mqtt_connected host=%s", self._config.host)
        for topic in sorted(self._topic_sources):
            if self._transport.subscribe(topic, MQTT_QOS):
                LOGGER.info("event=mqtt_subscribed topic=%s qos=%d", topic, MQTT_QOS)
            else:
                LOGGER.warning("event=mqtt_subscribe_failed topic=%s qos=%d", topic, MQTT_QOS)

    def _handle_disconnect(self, unexpected: bool, reason: str) -> None:
        """Log whether a disconnect will trigger automatic reconnection.

        :param unexpected: Whether the connection was lost unexpectedly.
        :param reason: Human-readable disconnection reason.
        :return: None.
        """
        if unexpected:
            LOGGER.warning("event=mqtt_disconnected host=%s reason=%s reconnecting=true", self._config.host, reason)
        else:
            LOGGER.info("event=mqtt_disconnected host=%s reason=%s reconnecting=false", self._config.host, reason)

    def _handle_message(self, topic: str, payload: bytes, retained: bool) -> None:
        """Route one MQTT message to every eligible matching source.

        :param topic: Exact MQTT message topic.
        :param payload: Raw MQTT payload bytes.
        :param retained: Whether the broker marked the message as retained.
        :return: None.
        """
        source_names: tuple[str, ...] = self._topic_sources.get(topic, ())
        if not source_names:
            LOGGER.warning("event=mqtt_message_unmatched topic=%s", topic)
            return

        for source_name in source_names:
            source: SourceConfig = self._sources[source_name]
            if retained and not source.accept_retained:
                LOGGER.info("event=mqtt_retained_ignored source=%s topic=%s", source_name, topic)
                continue
            try:
                self._processor.process(source_name, payload)
            except Exception:
                LOGGER.exception("event=mqtt_processing_failed source=%s reason=internal_error", source_name)


def create_mqtt_ingestion(
    config: MqttConfig,
    credentials: Credentials,
    sources: Mapping[str, SourceConfig],
    processor: MeasurementProcessor,
) -> MqttIngestion:
    """Create production MQTT ingestion backed by Paho.

    :param config: MQTT broker configuration.
    :param credentials: Optional MQTT credentials.
    :param sources: Configured measurement sources keyed by identifier.
    :param processor: Measurement processing destination.
    :return: Configured MQTT ingestion component.
    """
    transport: PahoMqttTransport = PahoMqttTransport(config, credentials)
    return MqttIngestion(config, sources, processor, transport)


def _group_sources_by_topic(sources: Mapping[str, SourceConfig]) -> dict[str, tuple[str, ...]]:
    """Group configured source identifiers by exact MQTT topic.

    :param sources: Measurement sources keyed by identifier.
    :return: Source identifier tuples keyed by distinct topic.
    """
    grouped: defaultdict[str, list[str]] = defaultdict(list)
    for source_name, source in sources.items():
        grouped[source.topic].append(source_name)
    return {topic: tuple(source_names) for topic, source_names in grouped.items()}


def _secret_value(secret: SecretStr | None) -> str | None:
    """Read an optional secret for direct transport configuration.

    :param secret: Protected credential value or ``None``.
    :return: Plain credential value for Paho or ``None``.
    """
    return secret.get_secret_value() if secret is not None else None

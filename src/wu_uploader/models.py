"""Typed application configuration models."""

import re
from enum import StrEnum
from typing import Annotated, ClassVar, Final, Self

from pydantic import BaseModel, ConfigDict, Field, SecretStr, StrictBool, StrictInt, StrictStr, model_validator
from pydantic.functional_validators import BeforeValidator

_DURATION_PATTERN: Final[re.Pattern[str]] = re.compile(r"^(?P<value>[0-9]+)(?P<unit>[smh])$")
_DURATION_MULTIPLIERS: Final[dict[str, int]] = {"s": 1, "m": 60, "h": 3600}


def _parse_duration(value: object) -> int:
    if not isinstance(value, str):
        raise ValueError("duration must be a positive integer followed by s, m, or h")

    match: re.Match[str] | None = _DURATION_PATTERN.fullmatch(value)
    if match is None:
        raise ValueError("duration must be a positive integer followed by s, m, or h")

    duration: int = int(match.group("value")) * _DURATION_MULTIPLIERS[match.group("unit")]
    if duration <= 0:
        raise ValueError("duration must be greater than zero")
    return duration


type DurationSeconds = Annotated[int, BeforeValidator(_parse_duration), Field(gt=0)]
type NonEmptyString = Annotated[StrictStr, Field(min_length=1)]
type MqttPort = Annotated[StrictInt, Field(ge=1, le=65535)]


class PayloadFormat(StrEnum):
    """Supported MQTT payload encodings."""

    SCALAR = "scalar"
    JSON = "json"


class Target(StrEnum):
    """Supported normalized measurement targets."""

    TEMPERATURE = "temperature"
    HUMIDITY = "humidity"
    PRESSURE = "pressure"


class Unit(StrEnum):
    """Supported source measurement units."""

    CELSIUS = "celsius"
    FAHRENHEIT = "fahrenheit"
    PERCENT = "percent"
    HPA = "hpa"
    PA = "pa"
    INHG = "inhg"


_TARGET_UNITS: Final[dict[Target, frozenset[Unit]]] = {
    Target.TEMPERATURE: frozenset({Unit.CELSIUS, Unit.FAHRENHEIT}),
    Target.HUMIDITY: frozenset({Unit.PERCENT}),
    Target.PRESSURE: frozenset({Unit.HPA, Unit.PA, Unit.INHG}),
}


class _ConfigurationModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True)


class MqttConfig(_ConfigurationModel):
    """MQTT connection configuration."""

    host: NonEmptyString
    port: MqttPort
    client_id: NonEmptyString = "weather-underground-uploader"
    keepalive: DurationSeconds = 60
    tls: StrictBool = False


class UploadConfig(_ConfigurationModel):
    """Observation upload scheduling configuration."""

    interval: DurationSeconds
    timeout: DurationSeconds = 10


class SourceConfig(_ConfigurationModel):
    """Configuration for one MQTT measurement source."""

    topic: NonEmptyString
    payload: PayloadFormat
    value: NonEmptyString | None = None
    unit: Unit
    max_age: DurationSeconds
    accept_retained: StrictBool = False
    target: Target

    @model_validator(mode="after")
    def _validate_source(self) -> Self:
        if self.payload is PayloadFormat.JSON and self.value is None:
            raise ValueError("value is required when payload is json")
        if self.payload is PayloadFormat.SCALAR and self.value is not None:
            raise ValueError("value is forbidden when payload is scalar")
        if "+" in self.topic or "#" in self.topic:
            raise ValueError("MQTT wildcard topics are not supported")
        if self.unit not in _TARGET_UNITS[self.target]:
            raise ValueError(f"unit {self.unit.value} is not supported for target {self.target.value}")
        return self


class WeatherUndergroundOutputConfig(_ConfigurationModel):
    """Weather Underground output configuration."""

    enabled: StrictBool = True


class OutputsConfig(_ConfigurationModel):
    """Configured output adapters."""

    weather_underground: WeatherUndergroundOutputConfig = Field(default_factory=WeatherUndergroundOutputConfig)


class FileConfiguration(_ConfigurationModel):
    """Validated, credential-free configuration loaded from YAML."""

    mqtt: MqttConfig
    upload: UploadConfig
    sources: Annotated[dict[NonEmptyString, SourceConfig], Field(min_length=1)]
    outputs: OutputsConfig = Field(default_factory=OutputsConfig)

    @model_validator(mode="after")
    def _validate_unique_targets(self) -> Self:
        target_sources: dict[Target, str] = {}
        for source_name, source in self.sources.items():
            if existing_source := target_sources.get(source.target):
                raise ValueError(f"sources {existing_source!r} and {source_name!r} both target {source.target.value!r}")
            target_sources[source.target] = source_name
        return self


class Credentials(_ConfigurationModel):
    """Runtime credentials loaded from environment variables."""

    mqtt_username: SecretStr | None = None
    mqtt_password: SecretStr | None = None
    wu_station_id: SecretStr | None = None
    wu_station_key: SecretStr | None = None


class ApplicationConfig(FileConfiguration):
    """Complete validated runtime configuration."""

    credentials: Credentials

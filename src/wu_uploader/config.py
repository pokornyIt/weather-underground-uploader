"""YAML and environment configuration loading."""

import os
from collections.abc import Hashable, Mapping
from pathlib import Path
from typing import Final, Protocol, cast

import yaml
from pydantic import SecretStr, ValidationError

from wu_uploader.models import ApplicationConfig, Credentials, FileConfiguration

MQTT_USERNAME: Final[str] = "MQTT_USERNAME"
MQTT_PASSWORD: Final[str] = "MQTT_PASSWORD"
WU_STATION_ID: Final[str] = "WU_STATION_ID"
WU_STATION_KEY: Final[str] = "WU_STATION_KEY"


class ConfigurationError(ValueError):
    """Raised when startup configuration cannot be loaded or validated."""


class _UniqueKeyLoader(yaml.SafeLoader):
    pass


class _ObjectConstructor(Protocol):
    def construct_object(self, node: yaml.Node, deep: bool = False) -> object: ...


def _construct_unique_mapping(
    loader: yaml.SafeLoader,
    node: yaml.MappingNode,
    deep: bool = False,
) -> dict[object, object]:
    mapping: dict[object, object] = {}
    constructor: _ObjectConstructor = cast(_ObjectConstructor, loader)
    for key_node, value_node in node.value:
        key: object = constructor.construct_object(key_node, deep=deep)
        if not isinstance(key, Hashable):
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                "found an unhashable mapping key",
                key_node.start_mark,
            )
        if key in mapping:
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                "found a duplicate mapping key",
                key_node.start_mark,
            )
        mapping[key] = constructor.construct_object(value_node, deep=deep)
    return mapping


_UniqueKeyLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_unique_mapping)


def load_configuration(path: Path, environ: Mapping[str, str] | None = None) -> ApplicationConfig:
    """Load and validate file and environment configuration.

    :param path: Path to the YAML configuration file.
    :param environ: Environment mapping; defaults to the process environment.
    :return: Complete typed runtime configuration.
    :raises ConfigurationError: If the file, schema, or credentials are invalid.
    """
    raw_configuration: object = _load_yaml(path)
    try:
        file_configuration: FileConfiguration = FileConfiguration.model_validate(raw_configuration)
    except ValidationError as exc:
        raise ConfigurationError(_format_validation_error(path, exc)) from None

    credentials: Credentials = _load_credentials(environ if environ is not None else os.environ, file_configuration)
    return ApplicationConfig(
        mqtt=file_configuration.mqtt,
        upload=file_configuration.upload,
        sources=file_configuration.sources,
        outputs=file_configuration.outputs,
        credentials=credentials,
    )


def _load_yaml(path: Path) -> object:
    try:
        contents: str = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise ConfigurationError(f"configuration file does not exist: {path}") from None
    except UnicodeDecodeError:
        raise ConfigurationError(f"configuration file is not valid UTF-8: {path}") from None
    except OSError as exc:
        raise ConfigurationError(f"cannot read configuration file {path}: {exc.strerror or 'I/O error'}") from None

    try:
        return cast(object, yaml.load(contents, Loader=_UniqueKeyLoader))
    except yaml.MarkedYAMLError as exc:
        location: str = ""
        if exc.problem_mark is not None:
            location = f" at line {exc.problem_mark.line + 1}, column {exc.problem_mark.column + 1}"
        raise ConfigurationError(f"configuration file contains invalid YAML{location}: {path}") from None
    except yaml.YAMLError:
        raise ConfigurationError(f"configuration file contains invalid YAML: {path}") from None


def _load_credentials(environ: Mapping[str, str], configuration: FileConfiguration) -> Credentials:
    mqtt_username: str | None = environ.get(MQTT_USERNAME) or None
    mqtt_password: str | None = environ.get(MQTT_PASSWORD) or None
    if (mqtt_username is None) != (mqtt_password is None):
        raise ConfigurationError(f"{MQTT_USERNAME} and {MQTT_PASSWORD} must be set together")

    wu_station_id: str | None = environ.get(WU_STATION_ID) or None
    wu_station_key: str | None = environ.get(WU_STATION_KEY) or None
    if configuration.outputs.weather_underground.enabled:
        missing: list[str] = [
            name for name, value in ((WU_STATION_ID, wu_station_id), (WU_STATION_KEY, wu_station_key)) if value is None
        ]
        if missing:
            raise ConfigurationError(f"missing required environment variables: {', '.join(missing)}")

    return Credentials(
        mqtt_username=_to_secret(mqtt_username),
        mqtt_password=_to_secret(mqtt_password),
        wu_station_id=_to_secret(wu_station_id),
        wu_station_key=_to_secret(wu_station_key),
    )


def _to_secret(value: str | None) -> SecretStr | None:
    return SecretStr(value) if value is not None else None


def _format_validation_error(path: Path, error: ValidationError) -> str:
    details: list[str] = []
    for item in error.errors(include_input=False, include_url=False):
        location: str = ".".join(str(part) for part in item["loc"])
        prefix: str = f"{location}: " if location else ""
        details.append(f"{prefix}{item['msg']}")
    return f"invalid configuration in {path}: {'; '.join(details)}"

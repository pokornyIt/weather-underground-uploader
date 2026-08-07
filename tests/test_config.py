from pathlib import Path
from typing import Final

import pytest

from wu_uploader.config import ConfigurationError, load_configuration
from wu_uploader.models import ApplicationConfig, PayloadFormat, SourceConfig, Target, Unit

VALID_ENVIRONMENT: Final[dict[str, str]] = {
    "WU_STATION_ID": "station-id",
    "WU_STATION_KEY": "station-key",
}

VALID_CONFIG: Final[str] = """\
mqtt:
  host: mqtt.example.local
  port: 1883
  keepalive: 2m
upload:
  interval: 1h
sources:
  outdoor_temperature:
    topic: sensors/outdoor
    payload: json
    value: temperature
    unit: celsius
    max_age: 30s
    target: temperature
outputs:
  weather_underground:
    enabled: true
"""


def _write_config(tmp_path: Path, contents: str) -> Path:
    path: Path = tmp_path / "config.yaml"
    path.write_text(contents, encoding="utf-8")
    return path


class TestLoadConfiguration:
    """Test loading and validation of startup configuration."""

    def test_loads_typed_configuration_and_defaults(self, tmp_path: Path) -> None:
        """Verify that valid configuration produces typed values and defaults."""
        configuration: ApplicationConfig = load_configuration(_write_config(tmp_path, VALID_CONFIG), VALID_ENVIRONMENT)

        source: SourceConfig = configuration.sources["outdoor_temperature"]
        assert configuration.mqtt.client_id == "weather-underground-uploader"
        assert configuration.mqtt.keepalive == 120
        assert configuration.mqtt.tls is False
        assert configuration.upload.interval == 3600
        assert configuration.upload.timeout == 10
        assert source.payload is PayloadFormat.JSON
        assert source.unit is Unit.CELSIUS
        assert source.max_age == 30
        assert source.accept_retained is False
        assert source.target is Target.TEMPERATURE
        assert str(configuration.credentials.wu_station_key) == "**********"

    def test_allows_disabled_output_without_wu_credentials(self, tmp_path: Path) -> None:
        """Verify that disabled output does not require Weather Underground credentials."""
        config: str = VALID_CONFIG.replace("enabled: true", "enabled: false")

        configuration: ApplicationConfig = load_configuration(_write_config(tmp_path, config), {})

        assert configuration.outputs.weather_underground.enabled is False
        assert configuration.credentials.wu_station_id is None
        assert configuration.credentials.wu_station_key is None

    def test_defaults_to_enabled_output_when_outputs_are_omitted(self, tmp_path: Path) -> None:
        """Verify that Weather Underground output is enabled by default."""
        config: str = VALID_CONFIG.split("outputs:\n", maxsplit=1)[0]

        configuration: ApplicationConfig = load_configuration(_write_config(tmp_path, config), VALID_ENVIRONMENT)

        assert configuration.outputs.weather_underground.enabled is True

    def test_loads_optional_mqtt_credentials_as_secrets(self, tmp_path: Path) -> None:
        """Verify that optional MQTT credentials are stored as secrets."""
        environment: dict[str, str] = {
            **VALID_ENVIRONMENT,
            "MQTT_USERNAME": "mqtt-user",
            "MQTT_PASSWORD": "mqtt-password",
        }

        configuration: ApplicationConfig = load_configuration(_write_config(tmp_path, VALID_CONFIG), environment)

        assert configuration.credentials.mqtt_username is not None
        assert configuration.credentials.mqtt_username.get_secret_value() == "mqtt-user"
        assert str(configuration.credentials.mqtt_password) == "**********"

    @pytest.mark.parametrize(
        ("environment", "expected"),
        [
            ({"MQTT_USERNAME": "mqtt-user", **VALID_ENVIRONMENT}, "MQTT_USERNAME and MQTT_PASSWORD"),
            ({}, "WU_STATION_ID, WU_STATION_KEY"),
            ({"WU_STATION_ID": "station-id"}, "WU_STATION_KEY"),
        ],
    )
    def test_rejects_invalid_environment(
        self,
        tmp_path: Path,
        environment: dict[str, str],
        expected: str,
    ) -> None:
        """Verify that incomplete required credential pairs are rejected."""
        with pytest.raises(ConfigurationError, match=expected):
            load_configuration(_write_config(tmp_path, VALID_CONFIG), environment)

    @pytest.mark.parametrize(
        ("config", "expected"),
        [
            (VALID_CONFIG + "unexpected: true\n", "unexpected"),
            (VALID_CONFIG.replace("  port: 1883", '  port: "1883"'), "mqtt.port"),
            (VALID_CONFIG.replace("  port: 1883", "  port: 65536"), "mqtt.port"),
            (VALID_CONFIG.replace("  keepalive: 2m", '  keepalive: "120"'), "mqtt.keepalive"),
            (VALID_CONFIG.replace("    enabled: true", '    enabled: "true"'), "outputs.weather_underground.enabled"),
            (VALID_CONFIG.replace("    target: temperature", "    target: humidity"), "not supported for target"),
            (VALID_CONFIG.replace("    topic: sensors/outdoor", "    topic: sensors/+/outdoor"), "wildcard"),
            (VALID_CONFIG.replace("    value: temperature\n", ""), "value is required"),
            (VALID_CONFIG.replace("    payload: json", "    payload: scalar"), "value is forbidden"),
        ],
    )
    def test_rejects_invalid_file_configuration(self, tmp_path: Path, config: str, expected: str) -> None:
        """Verify that invalid schema values and combinations are rejected."""
        with pytest.raises(ConfigurationError, match=expected):
            load_configuration(_write_config(tmp_path, config), VALID_ENVIRONMENT)

    def test_rejects_duplicate_targets(self, tmp_path: Path) -> None:
        """Verify that only one source may be configured for each target."""
        duplicate_source: str = """\
  backup_temperature:
    topic: sensors/backup
    payload: scalar
    unit: fahrenheit
    max_age: 30s
    target: temperature
"""
        config: str = VALID_CONFIG.replace("outputs:\n", f"{duplicate_source}outputs:\n")

        with pytest.raises(ConfigurationError, match="both target 'temperature'"):
            load_configuration(_write_config(tmp_path, config), VALID_ENVIRONMENT)

    def test_rejects_missing_file(self, tmp_path: Path) -> None:
        """Verify that a missing configuration file produces an actionable error."""
        path: Path = tmp_path / "missing.yaml"

        with pytest.raises(ConfigurationError, match="does not exist"):
            load_configuration(path, VALID_ENVIRONMENT)

    def test_reports_invalid_yaml_without_exposing_contents(self, tmp_path: Path) -> None:
        """Verify that YAML parser errors do not expose configuration contents."""
        config: str = "mqtt: [secret-value\n"

        with pytest.raises(ConfigurationError) as error:
            load_configuration(_write_config(tmp_path, config), VALID_ENVIRONMENT)

        assert "invalid YAML" in str(error.value)
        assert "secret-value" not in str(error.value)

    def test_rejects_duplicate_yaml_keys(self, tmp_path: Path) -> None:
        """Verify that duplicate YAML mapping keys are rejected."""
        config: str = VALID_CONFIG.replace("  port: 1883", "  port: 1883\n  port: 8883")

        with pytest.raises(ConfigurationError, match="invalid YAML"):
            load_configuration(_write_config(tmp_path, config), VALID_ENVIRONMENT)

    def test_rejects_yaml_credentials_without_exposing_values(self, tmp_path: Path) -> None:
        """Verify that YAML credentials are rejected without exposing their values."""
        config: str = VALID_CONFIG.replace("  port: 1883", "  port: 1883\n  password: secret-value")

        with pytest.raises(ConfigurationError) as error:
            load_configuration(_write_config(tmp_path, config), VALID_ENVIRONMENT)

        assert "mqtt.password" in str(error.value)
        assert "secret-value" not in str(error.value)

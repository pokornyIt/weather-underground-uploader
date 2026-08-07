from pathlib import Path
from typing import Final

import pytest

from wu_uploader.cli import main

VALID_CONFIG: Final[str] = """\
mqtt:
  host: mqtt.example.local
  port: 1883
upload:
  interval: 60s
sources:
  pressure:
    topic: sensors/pressure
    payload: scalar
    unit: hpa
    max_age: 300s
    target: pressure
outputs:
  weather_underground:
    enabled: false
"""


class TestMain:
    """Test the command-line startup boundary."""

    def test_loads_requested_configuration(self, tmp_path: Path) -> None:
        """Verify that the CLI loads the file supplied through --config."""
        config_path: Path = tmp_path / "config.yaml"
        config_path.write_text(VALID_CONFIG, encoding="utf-8")

        assert main(["--config", str(config_path)]) == 0

    def test_exits_with_actionable_error_for_invalid_configuration(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Verify that invalid configuration exits with an actionable CLI error."""
        config_path: Path = tmp_path / "config.yaml"
        config_path.write_text("mqtt: []\n", encoding="utf-8")

        with pytest.raises(SystemExit) as error:
            main(["--config", str(config_path)])

        captured: tuple[str, str] = capsys.readouterr()
        assert error.value.code == 2
        assert str(config_path) in captured[1]
        assert "invalid configuration" in captured[1]

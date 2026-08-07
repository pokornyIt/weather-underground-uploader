"""Command-line entry point."""

import argparse
import logging
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import cast

from wu_uploader.config import ConfigurationError, load_configuration
from wu_uploader.models import ApplicationConfig

LOGGER: logging.Logger = logging.getLogger(__name__)


def main(argv: Sequence[str] | None = None) -> int:
    """Validate startup configuration and start the service.

    :param argv: Optional command-line arguments excluding the program name.
    :return: Process exit code.
    :raises SystemExit: If command-line arguments or startup configuration are invalid.
    """
    parser: argparse.ArgumentParser = _build_parser()
    arguments: argparse.Namespace = parser.parse_args(argv)
    config_path: Path = cast(Path, arguments.config)

    _configure_logging()
    try:
        configuration: ApplicationConfig = load_configuration(config_path)
    except ConfigurationError as exc:
        parser.exit(2, f"{parser.prog}: error: {exc}\n")

    LOGGER.info(
        "event=configuration_loaded path=%s sources=%d",
        config_path,
        len(configuration.sources),
    )
    return 0


def _build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser.

    :return: Configured application argument parser.
    """
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="Upload MQTT weather observations to Weather Underground PWS."
    )
    parser.add_argument("--config", type=Path, required=True, help="path to the YAML configuration file")
    return parser


def _configure_logging() -> None:
    """Configure structured application logging on standard output.

    :return: None.
    """
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s", stream=sys.stdout)

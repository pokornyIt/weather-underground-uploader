"""MQTT payload parsing and measurement normalization."""

import json
import math
from typing import Final, Never, cast

from wu_uploader.models import PayloadFormat, SourceConfig, Target, Unit

INHG_TO_HPA: Final[float] = 33.8638866667
_INTERNAL_UNITS: Final[dict[Target, Unit]] = {
    Target.TEMPERATURE: Unit.CELSIUS,
    Target.HUMIDITY: Unit.PERCENT,
    Target.PRESSURE: Unit.HPA,
}
_VALID_RANGES: Final[dict[Target, tuple[float, float]]] = {
    Target.TEMPERATURE: (-100.0, 100.0),
    Target.HUMIDITY: (0.0, 100.0),
    Target.PRESSURE: (300.0, 1200.0),
}


class MeasurementError(ValueError):
    """Raised when an MQTT payload cannot produce a valid measurement."""

    reason: str

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def process_payload(payload: bytes, source: SourceConfig) -> float:
    """Parse, normalize, and validate one source payload.

    :param payload: Raw MQTT payload bytes.
    :param source: Configuration of the matching measurement source.
    :return: Valid value in the target's internal unit.
    :raises MeasurementError: If parsing, conversion, or validation fails.
    """
    parsed_value: float = parse_payload(payload, source)
    return normalize_value(parsed_value, source)


def parse_payload(payload: bytes, source: SourceConfig) -> float:
    """Extract a finite numeric value from an MQTT payload.

    :param payload: Raw MQTT payload bytes.
    :param source: Configuration that selects scalar or JSON extraction.
    :return: Extracted finite numeric value in the source unit.
    :raises MeasurementError: If the payload does not satisfy the source contract.
    """
    if source.payload is PayloadFormat.SCALAR:
        return parse_scalar_payload(payload)
    return parse_json_payload(payload, source.value)


def parse_scalar_payload(payload: bytes) -> float:
    """Parse a scalar UTF-8 payload as a finite decimal number.

    :param payload: Raw MQTT payload bytes.
    :return: Parsed finite value.
    :raises MeasurementError: If the payload is empty, malformed, or non-finite.
    """
    text: str = _decode_payload(payload).strip()
    if not text:
        raise MeasurementError("empty_payload")

    try:
        value: float = float(text)
    except ValueError:
        raise MeasurementError("not_numeric") from None
    _ensure_finite(value)
    return value


def parse_json_payload(payload: bytes, value_key: str | None) -> float:
    """Extract one top-level numeric key from a JSON object payload.

    :param payload: Raw MQTT payload bytes.
    :param value_key: Top-level object key configured for the source.
    :return: Extracted finite value.
    :raises MeasurementError: If JSON decoding or extraction fails.
    """
    text: str = _decode_payload(payload)
    try:
        document: object = cast(object, json.loads(text, parse_constant=_reject_json_constant))
    except json.JSONDecodeError:
        raise MeasurementError("invalid_json") from None

    if not isinstance(document, dict):
        raise MeasurementError("json_not_object")
    if value_key is None:
        raise MeasurementError("missing_value_key")

    json_object: dict[object, object] = cast(dict[object, object], document)
    if value_key not in json_object:
        raise MeasurementError("missing_json_key")
    return _json_number(json_object[value_key])


def normalize_value(value: float, source: SourceConfig) -> float:
    """Convert a source value to its internal unit and validate its range.

    :param value: Finite value expressed in the configured source unit.
    :param source: Source configuration defining unit and target.
    :return: Valid normalized value.
    :raises MeasurementError: If the value is non-finite, unsupported, or out of range.
    """
    _ensure_finite(value)
    normalized: float = _convert_to_internal_unit(value, source)
    _ensure_finite(normalized)

    minimum: float
    maximum: float
    minimum, maximum = _VALID_RANGES[source.target]
    if not minimum <= normalized <= maximum:
        raise MeasurementError("out_of_range")
    return normalized


def internal_unit(target: Target) -> Unit:
    """Return the canonical internal unit for a measurement target.

    :param target: Normalized measurement target.
    :return: Canonical unit used in the cache.
    """
    return _INTERNAL_UNITS[target]


def _decode_payload(payload: bytes) -> str:
    try:
        return payload.decode("utf-8")
    except UnicodeDecodeError:
        raise MeasurementError("invalid_utf8") from None


def _reject_json_constant(_constant: str) -> Never:
    raise MeasurementError("non_finite")


def _json_number(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise MeasurementError("json_value_not_number")
    try:
        number: float = float(value)
    except OverflowError:
        raise MeasurementError("non_finite") from None
    _ensure_finite(number)
    return number


def _ensure_finite(value: float) -> None:
    if not math.isfinite(value):
        raise MeasurementError("non_finite")


def _convert_to_internal_unit(value: float, source: SourceConfig) -> float:
    if source.target is Target.TEMPERATURE:
        if source.unit is Unit.CELSIUS:
            return value
        if source.unit is Unit.FAHRENHEIT:
            return (value - 32.0) * 5.0 / 9.0
    elif source.target is Target.HUMIDITY and source.unit is Unit.PERCENT:
        return value
    elif source.target is Target.PRESSURE:
        if source.unit is Unit.HPA:
            return value
        if source.unit is Unit.PA:
            return value / 100.0
        if source.unit is Unit.INHG:
            return value * INHG_TO_HPA
    raise MeasurementError("unsupported_unit")

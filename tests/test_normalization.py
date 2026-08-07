from typing import Final

import pytest

from wu_uploader.models import PayloadFormat, SourceConfig, Target, Unit
from wu_uploader.normalization import MeasurementError, internal_unit, normalize_value, parse_payload, process_payload


def _source(
    target: Target,
    unit: Unit,
    payload: PayloadFormat = PayloadFormat.SCALAR,
    value_key: str | None = None,
) -> SourceConfig:
    values: dict[str, object] = {
        "topic": "sensors/value",
        "payload": payload.value,
        "unit": unit.value,
        "max_age": "60s",
        "target": target.value,
    }
    if value_key is not None:
        values["value"] = value_key
    return SourceConfig.model_validate(values)


JSON_SOURCE: Final[SourceConfig] = _source(
    Target.TEMPERATURE,
    Unit.CELSIUS,
    payload=PayloadFormat.JSON,
    value_key="temperature",
)
SCALAR_SOURCE: Final[SourceConfig] = _source(Target.PRESSURE, Unit.HPA)


class TestParsePayload:
    """Test scalar and top-level JSON payload extraction."""

    @pytest.mark.parametrize(
        ("payload", "expected"),
        [
            (b"1007.4", 1007.4),
            (b"  -12.5 \n", -12.5),
            (b"1e3", 1000.0),
        ],
    )
    def test_parses_valid_scalar_payloads(self, payload: bytes, expected: float) -> None:
        """Verify that finite decimal scalar payloads are parsed."""
        assert parse_payload(payload, SCALAR_SOURCE) == expected

    @pytest.mark.parametrize(
        ("payload", "reason"),
        [
            (b"", "empty_payload"),
            (b"  \n", "empty_payload"),
            (b"not-a-number", "not_numeric"),
            (b"NaN", "non_finite"),
            (b"Infinity", "non_finite"),
            (b"\xff", "invalid_utf8"),
            (b"\x00", "not_numeric"),
            (b"null", "not_numeric"),
        ],
    )
    def test_rejects_invalid_scalar_payloads(self, payload: bytes, reason: str) -> None:
        """Verify that malformed and non-finite scalar payloads are rejected."""
        with pytest.raises(MeasurementError, match=reason):
            parse_payload(payload, SCALAR_SOURCE)

    @pytest.mark.parametrize(
        ("payload", "expected"),
        [
            (b'{"temperature": 18.7}', 18.7),
            (b'{"temperature": 19}', 19.0),
            (b'  {"temperature": -4.5, "ignored": 10}  ', -4.5),
        ],
    )
    def test_extracts_valid_top_level_json_numbers(self, payload: bytes, expected: float) -> None:
        """Verify that one configured top-level JSON number is extracted."""
        assert parse_payload(payload, JSON_SOURCE) == expected

    @pytest.mark.parametrize(
        ("payload", "reason"),
        [
            (b"not-json", "invalid_json"),
            (b"[]", "json_not_object"),
            (b"{}", "missing_json_key"),
            (b'{"temperature": null}', "json_value_not_number"),
            (b'{"temperature": true}', "json_value_not_number"),
            (b'{"temperature": "18.7"}', "json_value_not_number"),
            (b'{"temperature": {"value": 18.7}}', "json_value_not_number"),
            (b'{"temperature": NaN}', "non_finite"),
            (b"\xff", "invalid_utf8"),
        ],
    )
    def test_rejects_invalid_json_payloads(self, payload: bytes, reason: str) -> None:
        """Verify that JSON contract violations are rejected independently."""
        with pytest.raises(MeasurementError, match=reason):
            parse_payload(payload, JSON_SOURCE)


class TestNormalizeValue:
    """Test unit conversion and normalized range validation."""

    @pytest.mark.parametrize(
        ("target", "unit", "value", "expected", "expected_unit"),
        [
            (Target.TEMPERATURE, Unit.CELSIUS, 20.0, 20.0, Unit.CELSIUS),
            (Target.TEMPERATURE, Unit.FAHRENHEIT, 68.0, 20.0, Unit.CELSIUS),
            (Target.HUMIDITY, Unit.PERCENT, 55.0, 55.0, Unit.PERCENT),
            (Target.PRESSURE, Unit.HPA, 1000.0, 1000.0, Unit.HPA),
            (Target.PRESSURE, Unit.PA, 100000.0, 1000.0, Unit.HPA),
            (Target.PRESSURE, Unit.INHG, 29.92, 1013.207489067664, Unit.HPA),
        ],
    )
    def test_converts_supported_units(
        self,
        target: Target,
        unit: Unit,
        value: float,
        expected: float,
        expected_unit: Unit,
    ) -> None:
        """Verify conversion from every supported source unit."""
        source: SourceConfig = _source(target, unit)

        assert normalize_value(value, source) == pytest.approx(expected)
        assert internal_unit(target) is expected_unit

    @pytest.mark.parametrize(
        ("target", "unit", "value"),
        [
            (Target.TEMPERATURE, Unit.CELSIUS, -100.0),
            (Target.TEMPERATURE, Unit.CELSIUS, 100.0),
            (Target.HUMIDITY, Unit.PERCENT, 0.0),
            (Target.HUMIDITY, Unit.PERCENT, 100.0),
            (Target.PRESSURE, Unit.HPA, 300.0),
            (Target.PRESSURE, Unit.HPA, 1200.0),
        ],
    )
    def test_accepts_inclusive_range_boundaries(self, target: Target, unit: Unit, value: float) -> None:
        """Verify that documented minimum and maximum values are accepted."""
        source: SourceConfig = _source(target, unit)

        assert normalize_value(value, source) == value

    @pytest.mark.parametrize(
        ("target", "unit", "value"),
        [
            (Target.TEMPERATURE, Unit.CELSIUS, -100.01),
            (Target.TEMPERATURE, Unit.CELSIUS, 100.01),
            (Target.HUMIDITY, Unit.PERCENT, -0.01),
            (Target.HUMIDITY, Unit.PERCENT, 100.01),
            (Target.PRESSURE, Unit.HPA, 299.99),
            (Target.PRESSURE, Unit.HPA, 1200.01),
        ],
    )
    def test_rejects_values_outside_normalized_ranges(self, target: Target, unit: Unit, value: float) -> None:
        """Verify that normalized values outside documented ranges are rejected."""
        source: SourceConfig = _source(target, unit)

        with pytest.raises(MeasurementError, match="out_of_range"):
            normalize_value(value, source)

    def test_processes_payload_in_documented_order(self) -> None:
        """Verify that payload extraction precedes conversion and validation."""
        source: SourceConfig = _source(Target.TEMPERATURE, Unit.FAHRENHEIT)

        assert process_payload(b"68", source) == pytest.approx(20.0)

import logging
from concurrent.futures import Future, ThreadPoolExecutor

import pytest

from wu_uploader.measurements import Measurement, MeasurementSnapshot, MeasurementState
from wu_uploader.models import PayloadFormat, SourceConfig, Target, Unit


class FakeClock:
    """Controllable monotonic clock for measurement state tests."""

    def __init__(self, initial: float = 0.0) -> None:
        """Initialize the clock at a monotonic timestamp.

        :param initial: Initial monotonic timestamp in seconds.
        """
        self._value: float = initial

    def __call__(self) -> float:
        """Return the current monotonic timestamp.

        :return: Current monotonic timestamp in seconds.
        """
        return self._value

    def advance(self, seconds: float) -> None:
        """Advance the clock by a positive duration.

        :param seconds: Number of monotonic seconds to advance.
        :return: None.
        """
        self._value += seconds


def _source(target: Target, unit: Unit, max_age: int = 60) -> SourceConfig:
    """Build a scalar source configuration for state tests.

    :param target: Normalized measurement target.
    :param unit: Source measurement unit.
    :param max_age: Freshness duration in seconds.
    :return: Validated source configuration.
    """
    values: dict[str, object] = {
        "topic": f"sensors/{target.value}",
        "payload": PayloadFormat.SCALAR.value,
        "unit": unit.value,
        "max_age": f"{max_age}s",
        "target": target.value,
    }
    return SourceConfig.model_validate(values)


class TestMeasurementState:
    """Test normalized in-memory measurement state and freshness snapshots."""

    def test_starts_with_empty_snapshot(self) -> None:
        """Verify that state contains no fabricated initial measurements."""
        clock: FakeClock = FakeClock(10.0)
        state: MeasurementState = MeasurementState({}, clock)

        snapshot: MeasurementSnapshot = state.snapshot()

        assert snapshot.captured_at == 10.0
        assert len(snapshot) == 0

    def test_stores_normalized_measurement_with_monotonic_timestamp(self) -> None:
        """Verify that valid payloads are normalized and timestamped before storage."""
        clock: FakeClock = FakeClock(42.5)
        sources: dict[str, SourceConfig] = {
            "outdoor_temperature": _source(Target.TEMPERATURE, Unit.FAHRENHEIT),
        }
        state: MeasurementState = MeasurementState(sources, clock)

        measurement: Measurement | None = state.process("outdoor_temperature", b"68")

        assert measurement is not None
        assert measurement.target is Target.TEMPERATURE
        assert measurement.value == pytest.approx(20.0)
        assert measurement.unit is Unit.CELSIUS
        assert measurement.received_at == 42.5
        assert measurement.source == "outdoor_temperature"
        assert state.snapshot().get(Target.TEMPERATURE) == measurement

    @pytest.mark.parametrize(
        ("payload", "reason"),
        [
            (b"invalid", "not_numeric"),
            (b"2000", "out_of_range"),
        ],
    )
    def test_invalid_payload_does_not_replace_cached_value(
        self,
        payload: bytes,
        reason: str,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Verify that rejected payloads preserve state and log the source and reason."""
        clock: FakeClock = FakeClock()
        sources: dict[str, SourceConfig] = {"pressure": _source(Target.PRESSURE, Unit.HPA)}
        state: MeasurementState = MeasurementState(sources, clock)
        original: Measurement | None = state.process("pressure", b"1000")

        with caplog.at_level(logging.WARNING):
            rejected: Measurement | None = state.process("pressure", payload)

        assert rejected is None
        assert state.snapshot().get(Target.PRESSURE) == original
        assert f"event=invalid_measurement source=pressure reason={reason}" in caplog.messages

    def test_measurement_is_fresh_through_max_age_boundary(self) -> None:
        """Verify that staleness begins only after max_age is exceeded."""
        clock: FakeClock = FakeClock()
        sources: dict[str, SourceConfig] = {"humidity": _source(Target.HUMIDITY, Unit.PERCENT, max_age=10)}
        state: MeasurementState = MeasurementState(sources, clock)
        state.process("humidity", b"50")

        clock.advance(10.0)
        boundary_snapshot: MeasurementSnapshot = state.snapshot()
        clock.advance(0.001)
        stale_snapshot: MeasurementSnapshot = state.snapshot()

        assert boundary_snapshot.get(Target.HUMIDITY) is not None
        assert stale_snapshot.get(Target.HUMIDITY) is None

    def test_snapshot_omits_only_stale_measurements(self, caplog: pytest.LogCaptureFixture) -> None:
        """Verify that a snapshot remains partial when one cached value is stale."""
        clock: FakeClock = FakeClock()
        sources: dict[str, SourceConfig] = {
            "outdoor_temperature": _source(Target.TEMPERATURE, Unit.CELSIUS, max_age=5),
            "pressure": _source(Target.PRESSURE, Unit.HPA, max_age=20),
        }
        state: MeasurementState = MeasurementState(sources, clock)
        state.process("outdoor_temperature", b"18.5")
        state.process("pressure", b"1000")
        clock.advance(10.0)

        with caplog.at_level(logging.WARNING):
            snapshot: MeasurementSnapshot = state.snapshot()

        assert snapshot.get(Target.TEMPERATURE) is None
        assert snapshot.get(Target.PRESSURE) is not None
        assert "event=measurement_stale source=outdoor_temperature age_seconds=10 max_age_seconds=5" in caplog.messages

    def test_rejects_unknown_source(self) -> None:
        """Verify that programming errors use an actionable unknown-source exception."""
        state: MeasurementState = MeasurementState({})

        with pytest.raises(KeyError, match="unknown measurement source: missing"):
            state.process("missing", b"1")

    def test_updates_and_snapshots_are_thread_safe(self) -> None:
        """Verify that concurrent cache updates and snapshots remain usable."""
        sources: dict[str, SourceConfig] = {"pressure": _source(Target.PRESSURE, Unit.HPA)}
        state: MeasurementState = MeasurementState(sources)

        with ThreadPoolExecutor(max_workers=4) as executor:
            process_futures: list[Future[Measurement | None]] = [
                executor.submit(state.process, "pressure", str(900 + index).encode()) for index in range(100)
            ]
            snapshot_futures: list[Future[MeasurementSnapshot]] = [
                executor.submit(state.snapshot) for _index in range(100)
            ]

        assert all(future.result() is not None for future in process_futures)
        assert all(len(snapshot.measurements) <= 1 for snapshot in (future.result() for future in snapshot_futures))
        assert state.snapshot().get(Target.PRESSURE) is not None

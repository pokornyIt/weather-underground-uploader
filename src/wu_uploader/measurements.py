"""Thread-safe in-memory normalized measurement state."""

import logging
import threading
import time
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass

from wu_uploader.models import SourceConfig, Target, Unit
from wu_uploader.normalization import MeasurementError, internal_unit, process_payload

LOGGER: logging.Logger = logging.getLogger(__name__)
type MonotonicClock = Callable[[], float]


@dataclass(frozen=True, slots=True)
class Measurement:
    """One valid normalized measurement cached for a target."""

    target: Target
    value: float
    unit: Unit
    received_at: float
    source: str


@dataclass(frozen=True, slots=True)
class MeasurementSnapshot:
    """Immutable point-in-time collection of fresh measurements."""

    captured_at: float
    measurements: tuple[Measurement, ...]

    def __iter__(self) -> Iterator[Measurement]:
        """Iterate over measurements in deterministic target order.

        :return: Iterator over snapshot measurements.
        """
        return iter(self.measurements)

    def __len__(self) -> int:
        """Return the number of fresh measurements in the snapshot.

        :return: Number of snapshot measurements.
        """
        return len(self.measurements)

    def get(self, target: Target) -> Measurement | None:
        """Return the measurement for a target when present.

        :param target: Target to find in the snapshot.
        :return: Matching measurement or ``None``.
        """
        return next((measurement for measurement in self.measurements if measurement.target is target), None)


class MeasurementState:
    """Normalize source payloads and maintain a thread-safe in-memory cache.

    :param sources: Configured measurement sources keyed by source identifier.
    :param clock: Monotonic clock used for receipt and freshness timestamps.
    """

    def __init__(self, sources: Mapping[str, SourceConfig], clock: MonotonicClock = time.monotonic) -> None:
        """Initialize an empty measurement cache.

        :param sources: Configured measurement sources keyed by identifier.
        :param clock: Monotonic clock used for receipt and freshness timestamps.
        """
        self._sources: dict[str, SourceConfig] = dict(sources)
        self._clock: MonotonicClock = clock
        self._measurements: dict[Target, Measurement] = {}
        self._lock: threading.Lock = threading.Lock()

    def process(self, source_name: str, payload: bytes) -> Measurement | None:
        """Process one payload and update the cache only when it is valid.

        :param source_name: Identifier of the configured source.
        :param payload: Raw MQTT payload bytes.
        :return: Stored normalized measurement, or ``None`` for invalid input.
        :raises KeyError: If the source identifier is not configured.
        """
        try:
            source: SourceConfig = self._sources[source_name]
        except KeyError:
            raise KeyError(f"unknown measurement source: {source_name}") from None

        try:
            value: float = process_payload(payload, source)
        except MeasurementError as exc:
            LOGGER.warning("event=invalid_measurement source=%s reason=%s", source_name, exc.reason)
            return None

        measurement: Measurement = Measurement(
            target=source.target,
            value=value,
            unit=internal_unit(source.target),
            received_at=self._clock(),
            source=source_name,
        )
        with self._lock:
            self._measurements[source.target] = measurement

        LOGGER.info(
            "event=measurement_updated source=%s target=%s value=%g unit=%s",
            source_name,
            measurement.target.value,
            measurement.value,
            measurement.unit.value,
        )
        return measurement

    def snapshot(self) -> MeasurementSnapshot:
        """Return a consistent snapshot containing only fresh measurements.

        :return: Immutable snapshot captured using the configured monotonic clock.
        """
        with self._lock:
            captured_at: float = self._clock()
            cached: tuple[Measurement, ...] = tuple(self._measurements.values())

        fresh: list[Measurement] = []
        for measurement in cached:
            max_age: int = self._sources[measurement.source].max_age
            age: float = captured_at - measurement.received_at
            if age > max_age:
                LOGGER.warning(
                    "event=measurement_stale source=%s age_seconds=%g max_age_seconds=%d",
                    measurement.source,
                    age,
                    max_age,
                )
                continue
            fresh.append(measurement)

        ordered: tuple[Measurement, ...] = tuple(sorted(fresh, key=lambda item: item.target.value))
        return MeasurementSnapshot(captured_at=captured_at, measurements=ordered)

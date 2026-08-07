import logging

import pytest

from wu_uploader.measurements import Measurement, MeasurementSnapshot
from wu_uploader.models import Target, Unit
from wu_uploader.scheduler import ObservationScheduler


def _snapshot(*measurements: Measurement) -> MeasurementSnapshot:
    """Build a measurement snapshot for scheduler tests.

    :param measurements: Measurements included in the snapshot.
    :return: Test measurement snapshot.
    """
    return MeasurementSnapshot(captured_at=10.0, measurements=measurements)


def _measurement() -> Measurement:
    """Build one fresh normalized test measurement.

    :return: Temperature measurement for upload tests.
    """
    return Measurement(
        target=Target.TEMPERATURE,
        value=20.0,
        unit=Unit.CELSIUS,
        received_at=10.0,
        source="temperature",
    )


class FakeStopSignal:
    """Return configured wait outcomes without wall-clock waiting."""

    def __init__(self, outcomes: list[bool]) -> None:
        """Initialize wait outcomes.

        :param outcomes: Values returned by successive waits.
        """
        self.outcomes: list[bool] = list(outcomes)
        self.waited: list[float | None] = []
        self.set_calls: int = 0

    def wait(self, timeout: float | None = None) -> bool:
        """Record the interval and return the next configured outcome.

        :param timeout: Requested wait duration in seconds.
        :return: Next configured stop state, defaulting to stopped.
        """
        self.waited.append(timeout)
        return self.outcomes.pop(0) if self.outcomes else True

    def set(self) -> None:
        """Record a stop request.

        :return: None.
        """
        self.set_calls += 1


class FakeSnapshotProvider:
    """Return configured snapshots or isolated failures."""

    def __init__(self, outcomes: list[MeasurementSnapshot | Exception]) -> None:
        """Initialize snapshot outcomes.

        :param outcomes: Snapshots or exceptions returned in order.
        """
        self.outcomes: list[MeasurementSnapshot | Exception] = list(outcomes)
        self.calls: int = 0

    def snapshot(self) -> MeasurementSnapshot:
        """Return or raise the next configured outcome.

        :return: Next configured measurement snapshot.
        :raises Exception: Configured snapshot failure.
        """
        self.calls += 1
        outcome: MeasurementSnapshot | Exception = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class FakeUploader:
    """Record snapshots and return or raise configured outcomes."""

    def __init__(self, outcomes: list[bool | Exception] | None = None) -> None:
        """Initialize upload outcomes.

        :param outcomes: Optional upload results or exceptions returned in order.
        """
        self.outcomes: list[bool | Exception] = list(outcomes or [True])
        self.snapshots: list[MeasurementSnapshot] = []

    def upload(self, snapshot: MeasurementSnapshot) -> bool:
        """Record a snapshot and return or raise the next outcome.

        :param snapshot: Non-empty measurement snapshot.
        :return: Configured upload result.
        :raises Exception: Configured upload failure.
        """
        self.snapshots.append(snapshot)
        outcome: bool | Exception = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class TestObservationScheduler:
    """Test interval timing, observation selection, and failure isolation."""

    def test_waits_complete_interval_before_first_upload(self) -> None:
        """Verify that startup never causes an immediate observation upload."""
        snapshot: MeasurementSnapshot = _snapshot(_measurement())
        snapshots: FakeSnapshotProvider = FakeSnapshotProvider([snapshot])
        uploader: FakeUploader = FakeUploader()
        stop_signal: FakeStopSignal = FakeStopSignal([False, True])
        scheduler: ObservationScheduler = ObservationScheduler(60.0, snapshots, uploader, stop_signal)

        scheduler.run()

        assert stop_signal.waited == [60.0, 60.0]
        assert snapshots.calls == 1
        assert uploader.snapshots == [snapshot]

    def test_skips_empty_snapshot_before_output_adapter(self, caplog: pytest.LogCaptureFixture) -> None:
        """Verify that no output adapter is called without a fresh measurement."""
        snapshots: FakeSnapshotProvider = FakeSnapshotProvider([_snapshot()])
        uploader: FakeUploader = FakeUploader()
        scheduler: ObservationScheduler = ObservationScheduler(
            30.0,
            snapshots,
            uploader,
            FakeStopSignal([False, True]),
        )

        with caplog.at_level(logging.INFO):
            scheduler.run()

        assert uploader.snapshots == []
        assert "event=wu_upload_skipped reason=no_measurements" in caplog.messages

    def test_skips_non_empty_snapshot_when_output_is_disabled(self, caplog: pytest.LogCaptureFixture) -> None:
        """Verify that disabled output remains a valid no-request service mode."""
        snapshots: FakeSnapshotProvider = FakeSnapshotProvider([_snapshot(_measurement())])
        scheduler: ObservationScheduler = ObservationScheduler(
            30.0,
            snapshots,
            None,
            FakeStopSignal([False, True]),
        )

        with caplog.at_level(logging.INFO):
            scheduler.run()

        assert "event=wu_upload_skipped reason=output_disabled" in caplog.messages

    @pytest.mark.parametrize("failure_stage", ["snapshot", "upload"])
    def test_component_failure_does_not_stop_later_intervals(
        self,
        failure_stage: str,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Verify that one snapshot or upload failure does not terminate scheduling."""
        valid_snapshot: MeasurementSnapshot = _snapshot(_measurement())
        snapshot_outcomes: list[MeasurementSnapshot | Exception] = [valid_snapshot, valid_snapshot]
        upload_outcomes: list[bool | Exception] = [True, True]
        if failure_stage == "snapshot":
            snapshot_outcomes = [RuntimeError("sensitive snapshot detail"), valid_snapshot]
        else:
            upload_outcomes = [RuntimeError("sensitive upload detail"), True]
        snapshots: FakeSnapshotProvider = FakeSnapshotProvider(snapshot_outcomes)
        uploader: FakeUploader = FakeUploader(upload_outcomes)
        scheduler: ObservationScheduler = ObservationScheduler(
            15.0,
            snapshots,
            uploader,
            FakeStopSignal([False, False, True]),
        )

        with caplog.at_level(logging.INFO):
            scheduler.run()

        assert snapshots.calls == 2
        assert len(uploader.snapshots) >= 1
        assert "sensitive" not in caplog.text

    def test_stop_sets_interruptible_signal(self) -> None:
        """Verify that shutdown wakes an interval wait without sleeping."""
        stop_signal: FakeStopSignal = FakeStopSignal([])
        scheduler: ObservationScheduler = ObservationScheduler(
            10.0,
            FakeSnapshotProvider([]),
            FakeUploader(),
            stop_signal,
        )

        scheduler.stop()

        assert stop_signal.set_calls == 1

    def test_rejects_non_positive_interval(self) -> None:
        """Verify that invalid scheduling intervals fail during assembly."""
        with pytest.raises(ValueError, match="greater than zero"):
            ObservationScheduler(0.0, FakeSnapshotProvider([]), FakeUploader())

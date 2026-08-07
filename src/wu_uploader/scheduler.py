"""Scheduled construction and upload of fresh weather observations."""

import logging
import threading
from typing import Protocol

from wu_uploader.measurements import MeasurementSnapshot

LOGGER: logging.Logger = logging.getLogger(__name__)


class SnapshotProvider(Protocol):
    """Provide consistent snapshots of current measurements."""

    def snapshot(self) -> MeasurementSnapshot:
        """Return one consistent snapshot of fresh measurements.

        :return: Fresh measurement snapshot.
        """
        ...


class ObservationUploader(Protocol):
    """Upload fresh measurement observations."""

    def upload(self, snapshot: MeasurementSnapshot) -> bool:
        """Upload one non-empty observation.

        :param snapshot: Consistent snapshot of fresh measurements.
        :return: Whether the observation was accepted.
        """
        ...


class StopSignal(Protocol):
    """Interruptible waiting boundary used by the scheduler."""

    def wait(self, timeout: float | None = None) -> bool:
        """Wait until stopped or the timeout expires.

        :param timeout: Maximum wait duration in seconds.
        :return: Whether the stop signal was set.
        """
        ...

    def set(self) -> None:
        """Set the stop signal and wake waiting code.

        :return: None.
        """
        ...


class ObservationScheduler:
    """Upload fresh cache snapshots at a fixed interval.

    :param interval: Upload interval in seconds.
    :param snapshots: Measurement snapshot provider.
    :param uploader: Enabled output adapter, or ``None`` when output is disabled.
    :param stop_signal: Interruptible stop signal replaceable by tests.
    """

    def __init__(
        self,
        interval: float,
        snapshots: SnapshotProvider,
        uploader: ObservationUploader | None,
        stop_signal: StopSignal | None = None,
    ) -> None:
        """Initialize the observation scheduler.

        :param interval: Upload interval in seconds.
        :param snapshots: Measurement snapshot provider.
        :param uploader: Enabled output adapter, or ``None`` when output is disabled.
        :param stop_signal: Interruptible stop signal replaceable by tests.
        :raises ValueError: If the interval is not positive.
        """
        if interval <= 0:
            raise ValueError("upload interval must be greater than zero")
        self._interval: float = interval
        self._snapshots: SnapshotProvider = snapshots
        self._uploader: ObservationUploader | None = uploader
        self._stop_signal: StopSignal = stop_signal or threading.Event()

    def run(self) -> None:
        """Run scheduled uploads until a stop is requested.

        The first observation is attempted only after one complete interval.

        :return: None.
        """
        LOGGER.info("event=scheduler_started interval_seconds=%g", self._interval)
        while not self._stop_signal.wait(self._interval):
            self._run_interval()
        LOGGER.info("event=scheduler_stopped")

    def stop(self) -> None:
        """Stop scheduling new observations and wake the scheduler.

        :return: None.
        """
        self._stop_signal.set()

    def _run_interval(self) -> None:
        """Process one scheduled observation without propagating component failures.

        :return: None.
        """
        try:
            snapshot: MeasurementSnapshot = self._snapshots.snapshot()
        except Exception:
            LOGGER.error("event=observation_failed reason=snapshot_error")
            return

        if len(snapshot) == 0:
            LOGGER.info("event=wu_upload_skipped reason=no_measurements")
            return
        if self._uploader is None:
            LOGGER.info("event=wu_upload_skipped reason=output_disabled")
            return

        try:
            self._uploader.upload(snapshot)
        except Exception:
            LOGGER.error("event=wu_upload_failed reason=unexpected_error")

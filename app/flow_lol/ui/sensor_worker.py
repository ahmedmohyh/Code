"""PyQt6 worker that runs the async BLE sensor manager in a background thread.

The worker emits:
  connection_changed(sensor_name, status)
  prediction(sensor_name, prediction_dict)
  samples(sensor_name, List[ECGSample])
  error(sensor_name, exception)
  match_started(game_mode, detected)
  match_ended()
  webcam_changed(recording: bool, output_path: Optional[Path])
"""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QThread, pyqtSignal

from flow_lol.config.settings import AppSettings
from flow_lol.game.detector import GameDetector
from flow_lol.inference.pipeline import InferencePipeline, Prediction
from flow_lol.persistence.ecg_writer import RawECGWriter
from flow_lol.persistence.repository import SessionRepository
from flow_lol.sensors.manager import SensorManager
from flow_lol.webcam.recorder import WebcamRecorder

logger = logging.getLogger(__name__)


class SensorWorker(QThread):
    connection_changed = pyqtSignal(str, str)
    prediction = pyqtSignal(str, object)
    samples = pyqtSignal(str, object)  # sensor_name, List[ECGSample]
    error = pyqtSignal(str, object)
    match_started = pyqtSignal(str, bool)
    match_ended = pyqtSignal()
    webcam_changed = pyqtSignal(bool, object)  # recording: bool, output_path: Optional[Path]

    def __init__(
        self,
        settings: AppSettings,
        parent: Optional["QObject"] = None,
    ) -> None:
        super().__init__(parent)
        self.settings = settings
        self.manager: Optional[SensorManager] = None
        self.inference: Optional[InferencePipeline] = None
        self.detector: Optional[GameDetector] = None
        self.repository: Optional[SessionRepository] = None
        self.webcam: Optional[WebcamRecorder] = None
        self.ecg_writer: Optional[RawECGWriter] = None
        self.session_id: Optional[int] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._stop_event = asyncio.Event()

    def run(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._main())
        finally:
            self._loop.close()
            self._loop = None

    async def _main(self) -> None:
        self.inference = InferencePipeline(
            settings=self.settings,
            on_prediction=self._on_prediction,
        )
        self.inference.load_models()
        if not self.inference.is_ready():
            logger.warning("Models are not ready; predictions will be skipped")

        self.repository = SessionRepository(self.settings.db_path)
        self.session_id = self.repository.create_session(self.settings)

        # Webcam is started only after the sensor manager connects successfully.
        self.webcam: Optional[WebcamRecorder] = None

        self.ecg_writer = RawECGWriter(
            output_dir=self.settings.ecg_save_path,
            enabled=True,
        )

        self.detector = GameDetector(
            settings=self.settings,
            on_match_start=self._on_match_start,
            on_match_end=self._on_match_end,
        )
        await self.detector.start()

        self.manager = SensorManager(
            settings=self.settings,
            on_connection_change=self._on_connection_change,
            on_error=self._on_error,
            on_samples=self._on_samples,
        )
        try:
            await self.manager.start()
        except Exception as exc:
            # SensorManager catches per-sensor failures, but guard against
            # anything unexpected so the worker thread does not die.
            logger.exception("Sensor manager failed to start")
            self._on_error("manager", exc)

        if not self.manager.buffers:
            self._on_error(
                "manager",
                RuntimeError(
                    "No ECG sensor connected. "
                    "Check Bluetooth pairing and that the H10 is blinking blue, "
                    "then remove the H10 from Windows Bluetooth and press Start session again."
                ),
            )
            logger.warning("No sensor buffers available; skipping webcam recording")
        elif self.settings.webcam_enabled:
            logger.info("Sensor connected; starting webcam recording")
            self.webcam = WebcamRecorder(
                output_dir=self.settings.webcam_save_path,
                enabled=True,
            )
            path = self.webcam.start(self.session_id)
            self.webcam_changed.emit(True, path)
        else:
            logger.info("Sensor connected but webcam disabled in settings")
            self.webcam_changed.emit(False, None)

        try:
            while not self._stop_event.is_set():
                for name, buffer in self.manager.buffers.items():
                    for start, samples in buffer.new_windows(
                        window_seconds=self.settings.window_seconds,
                        overlap_percent=self.settings.overlap_percent,
                    ):
                        if self.inference.is_ready():
                            self.inference.process_window(name, start, samples)
                await asyncio.sleep(0.1)
        finally:
            await self.manager.stop()
            if self.detector is not None:
                await self.detector.stop()
            if self.webcam is not None:
                self.webcam.stop()
            if self.ecg_writer is not None and self.session_id is not None:
                self.ecg_writer.close(self.session_id)
            if self.repository is not None and self.session_id is not None:
                sensor_summary = "+".join(sorted(self.manager.buffers.keys()))
                self.repository.end_session(self.session_id, sensor_summary=sensor_summary)

    def _on_prediction(self, prediction: Prediction) -> None:
        if self.repository is not None and self.session_id is not None:
            self.repository.add_prediction(self.session_id, prediction)
        self.prediction.emit(prediction.sensor_name, prediction.to_dict())

    def _on_connection_change(self, name: str, status: str) -> None:
        if self.repository is not None and self.session_id is not None:
            self.repository.add_sensor_event(
                self.session_id, name, "connection", message=status
            )
        self.connection_changed.emit(name, status)

    def _on_error(self, name: str, exc: Exception) -> None:
        if self.repository is not None and self.session_id is not None:
            self.repository.add_sensor_event(
                self.session_id, name, "error", message=str(exc)
            )
        self.error.emit(name, exc)

    def _on_samples(self, name: str, samples: list) -> None:
        if self.ecg_writer is not None:
            self.ecg_writer.add_samples(name, samples)
        self.samples.emit(name, samples)

    def _on_match_start(self, game_mode: str, detected: bool) -> None:
        if self.repository is not None and self.session_id is not None:
            self.repository.start_match(self.session_id, game_mode, detected=detected)
        self.match_started.emit(game_mode, detected)

    def _on_match_end(self) -> None:
        if self.repository is not None:
            self.repository.end_match()
        self.match_ended.emit()

    def start_match(self, game_mode: str) -> None:
        """Request a manual match start from the UI thread."""
        if self._loop is None or self._loop.is_closed():
            return
        asyncio.run_coroutine_threadsafe(self._start_match(game_mode), self._loop)

    async def _start_match(self, game_mode: str) -> None:
        if self.detector is not None:
            await self.detector.start_match(game_mode, detected=False)

    def end_match(self) -> None:
        """Request a manual match end from the UI thread."""
        if self._loop is None or self._loop.is_closed():
            return
        asyncio.run_coroutine_threadsafe(self._end_match(), self._loop)

    async def _end_match(self) -> None:
        if self.detector is not None:
            await self.detector.end_match()

    def toggle_webcam(self) -> None:
        """Request a webcam start/stop toggle from the UI thread."""
        if self._loop is None or self._loop.is_closed():
            return
        asyncio.run_coroutine_threadsafe(self._toggle_webcam(), self._loop)

    async def _toggle_webcam(self) -> None:
        """Start or stop the webcam recorder on the worker thread."""
        if self.session_id is None:
            return
        if self.webcam is not None and self.webcam.is_recording():
            path = self.webcam.stop()
            self.webcam = None
            self.webcam_changed.emit(False, path)
            logger.info("Webcam disabled by user; stopped %s", path)
        else:
            self.webcam = WebcamRecorder(
                output_dir=self.settings.webcam_save_path,
                enabled=True,
            )
            path = self.webcam.start(self.session_id)
            self.webcam_changed.emit(True, path)
            logger.info("Webcam enabled by user; started %s", path)

    def stop(self) -> None:
        self._stop_event.set()
        self.wait(5000)

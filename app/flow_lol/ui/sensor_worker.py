"""PyQt6 worker that runs the async BLE sensor manager in a background thread.

This single worker owns the H10 connection. It starts in "preview" mode
(connection + live ECG, no persistence) and switches into "session" mode when
the user presses Start session, then back to preview when the session ends.
The H10 is connected once and stays connected, avoiding the Windows double-BLE
connect problem.

The worker emits:
  connection_changed(sensor_name, status)
  prediction(sensor_name, prediction_dict)
  samples(sensor_name, List[ECGSample])
  error(sensor_name, exception)
  match_started(game_mode, detected)
  match_ended()
  game_event(event_dict)
  webcam_changed(recording: bool, output_path: Optional[Path])
  webcam_snapshot(path)
  session_state_changed(active: bool)
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QThread, pyqtSignal

from flow_lol.analysis.match_summary import summarize_match
from flow_lol.config.settings import AppSettings
from flow_lol.game.detector import GameDetector
from flow_lol.game.replay_scanner import scan_replays_for_session
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
    game_event = pyqtSignal(object)  # normalized event dict
    webcam_changed = pyqtSignal(bool, object)  # recording: bool, output_path: Optional[Path]
    webcam_snapshot = pyqtSignal(object)  # Path
    session_state_changed = pyqtSignal(bool)  # True when a DB session is active

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
        self._active_match_id: Optional[int] = None
        self._active_match_started_at: Optional[float] = None
        self._match_predictions: list = []
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._stop_event: Optional[asyncio.Event] = None
        self._preview_only = True

    def run(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._stop_event = asyncio.Event()
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

        # Game detector runs continuously so auto-detect works during preview and session.
        self.detector = GameDetector(
            settings=self.settings,
            on_match_start=self._on_match_start,
            on_match_end=self._on_match_end,
            on_game_event=self._on_game_event,
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
            logger.exception("Sensor manager failed to start")
            self._on_error("manager", exc)

        if not self.manager.buffers:
            self._on_error(
                "manager",
                RuntimeError(
                    "No ECG sensor connected. "
                    "Check Bluetooth pairing and that the H10 is blinking blue, "
                    "then remove the H10 from Windows Bluetooth and try again."
                ),
            )
            logger.warning("No sensor buffers available; stopping worker")
            return

        # Start in preview mode: samples flow to UI but nothing is persisted yet.
        logger.info("Sensor connected; preview mode active")
        self.session_state_changed.emit(False)

        try:
            while not self._stop_event.is_set():
                # If we have switched to session mode while running, handle it lazily here.
                await self._ensure_session_started()

                for name, buffer in self.manager.buffers.items():
                    for start, samples in buffer.new_windows(
                        window_seconds=self.settings.window_seconds,
                        overlap_percent=self.settings.overlap_percent,
                    ):
                        if self.inference.is_ready():
                            self.inference.process_window(name, start, samples)
                await asyncio.sleep(0.1)
        finally:
            await self._end_session()
            await self.manager.stop()
            if self.detector is not None:
                await self.detector.stop()

    # ------------------------------------------------------------------
    # Preview / session transitions
    # ------------------------------------------------------------------

    def start_session(self) -> None:
        """Switch from preview mode to a recording session."""
        if self._loop is None or self._loop.is_closed():
            return
        asyncio.run_coroutine_threadsafe(self._do_start_session(), self._loop)

    async def _do_start_session(self) -> None:
        if not self._preview_only or self.session_id is not None:
            return
        if not self.manager or not self.manager.buffers:
            self._on_error(
                "session",
                RuntimeError("Cannot start session: H10 is not connected."),
            )
            return

        self._preview_only = False
        self.repository = SessionRepository(self.settings.db_path)
        self.session_id = self.repository.create_session(self.settings)

        self.ecg_writer = RawECGWriter(
            output_dir=self.settings.ecg_save_path,
            enabled=True,
        )

        if self.settings.webcam_enabled:
            self.webcam = WebcamRecorder(
                output_dir=self.settings.webcam_save_path,
                enabled=True,
                on_snapshot=self._on_webcam_snapshot,
            )
            # Start webcam in a background thread so the async worker loop is not
            # blocked by OpenCV initialization.
            import threading

            def _start_webcam() -> None:
                path = self.webcam.start(self.session_id)
                if path is None:
                    self.webcam = None
                    self.webcam_changed.emit(False, None)
                    self._on_error(
                        "webcam",
                        RuntimeError(
                            "No webcam detected. Check that a camera is connected, "
                            "not in use by another app, and allowed in Windows privacy settings."
                        ),
                    )
                    logger.error("Auto webcam start failed: no camera available")
                else:
                    self.webcam_changed.emit(True, path)
                    logger.info("Webcam recording started: %s", path)

            threading.Thread(target=_start_webcam, name="webcam-start", daemon=True).start()
        else:
            self.webcam_changed.emit(False, None)

        self.session_state_changed.emit(True)
        logger.info("Recording session started: id=%s", self.session_id)

    def stop_session(self) -> None:
        """End the recording session but keep the H10 connection alive."""
        if self._loop is None or self._loop.is_closed():
            return
        asyncio.run_coroutine_threadsafe(self._do_stop_session(), self._loop)

    async def _do_stop_session(self) -> None:
        await self._end_session()
        self._preview_only = True
        self.session_state_changed.emit(False)

    async def _ensure_session_started(self) -> None:
        """No-op if already in session; otherwise session must be triggered externally."""

    async def _end_session(self) -> None:
        if self.session_id is None:
            return
        try:
            if self._active_match_id is not None:
                try:
                    await self.detector.end_match()
                except Exception:
                    pass
            if self.webcam is not None:
                self.webcam.stop()
                self.webcam = None
            if self.ecg_writer is not None:
                self.ecg_writer.close(self.session_id)
                self.ecg_writer = None
            if self.repository is not None and self.manager is not None:
                sensor_summary = "+".join(sorted(self.manager.buffers.keys()))
                self.repository.end_session(self.session_id, sensor_summary=sensor_summary)
            logger.info("Recording session ended: id=%s", self.session_id)
        except Exception as exc:
            logger.exception("Error ending session: %s", exc)
        finally:
            self.session_id = None
            self._active_match_id = None
            self._active_match_started_at = None
            self._match_predictions.clear()
            self.session_state_changed.emit(False)

    # ------------------------------------------------------------------
    # Signal handlers
    # ------------------------------------------------------------------

    def _on_prediction(self, prediction: Prediction) -> None:
        if self.repository is not None and self.session_id is not None:
            self.repository.add_prediction(self.session_id, prediction)
        if self._active_match_id is not None:
            self._match_predictions.append(prediction)
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
            self._active_match_id = self.repository.start_match(
                self.session_id, game_mode, detected=detected
            )
            self._active_match_started_at = time.time()
        self._match_predictions.clear()
        self.match_started.emit(game_mode, detected)

    def _on_match_end(self) -> None:
        if self.repository is not None and self._active_match_id is not None:
            self.repository.end_match(self._active_match_id)
            events = (
                self.repository.get_game_events(
                    self.session_id or 0, match_id=self._active_match_id
                )
                if self.session_id is not None
                else []
            )
            rec = summarize_match(self._match_predictions, events)
            self.repository.update_match_notes(self._active_match_id, rec.to_text())
            self._scan_replays(self._active_match_id)
        self._active_match_id = None
        self._active_match_started_at = None
        self._match_predictions.clear()
        self.match_ended.emit()

    def _on_game_event(self, event: dict) -> None:
        if self.repository is None or self.session_id is None or self._active_match_id is None:
            return
        raw = event.get("raw", {})
        event_time = float(event["timestamp"])
        absolute_ts = (self._active_match_started_at or time.time()) + event_time
        self.repository.add_game_event(
            session_id=self.session_id,
            match_id=self._active_match_id,
            timestamp=absolute_ts,
            event_type=event["event_type"],
            actor=event.get("actor"),
            target=event.get("target"),
            description=event.get("description"),
            source_json=json.dumps(raw, default=str, ensure_ascii=False),
        )
        self.game_event.emit(event)

    def _scan_replays(self, match_id: int) -> None:
        if self.repository is None or self.session_id is None:
            return
        replays = scan_replays_for_session(
            replay_dir=self.settings.replay_save_path,
            session_id=self.session_id,
            match_id=match_id,
            repository=self.repository,
        )
        if replays:
            logger.info("Linked %s replay(s) to match %s", len(replays), match_id)

    # ------------------------------------------------------------------
    # Thread-safe actions requested by the UI
    # ------------------------------------------------------------------

    def start_match(self, game_mode: str) -> None:
        if self._loop is None or self._loop.is_closed():
            logger.warning("Cannot start match: worker loop not available")
            return
        future = asyncio.run_coroutine_threadsafe(self._start_match(game_mode), self._loop)
        future.add_done_callback(self._log_match_future)

    def _log_match_future(self, future) -> None:
        try:
            future.result()
        except Exception:
            logger.exception("Match future failed")

    async def _start_match(self, game_mode: str) -> None:
        if self.detector is None:
            logger.warning("Cannot start match: detector is None")
            return
        logger.info("Worker starting match: %s", game_mode)
        await self.detector.start_match(game_mode, detected=False)

    def end_match(self) -> None:
        if self._loop is None or self._loop.is_closed():
            logger.warning("Cannot end match: worker loop not available")
            return
        future = asyncio.run_coroutine_threadsafe(self._end_match(), self._loop)
        future.add_done_callback(self._log_match_future)

    async def _end_match(self) -> None:
        if self.detector is None:
            logger.warning("Cannot end match: detector is None")
            return
        logger.info("Worker ending match")
        await self.detector.end_match()

    def toggle_webcam(self) -> None:
        if self._loop is None or self._loop.is_closed():
            return
        asyncio.run_coroutine_threadsafe(self._toggle_webcam(), self._loop)

    async def _toggle_webcam(self) -> None:
        if self._preview_only or self.session_id is None:
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
                on_snapshot=self._on_webcam_snapshot,
            )
            path = self.webcam.start(self.session_id)
            if path is None:
                self.webcam = None
                self.webcam_changed.emit(False, None)
                self._on_error(
                    "webcam",
                    RuntimeError(
                        "No webcam detected. Check that a camera is connected, "
                        "not in use by another app, and allowed in Windows privacy settings."
                    ),
                )
                logger.error("Webcam toggle failed: no camera available")
            else:
                self.webcam_changed.emit(True, path)
                logger.info("Webcam enabled by user; started %s", path)

    def _on_webcam_snapshot(self, path: Path) -> None:
        self.webcam_snapshot.emit(path)

    def stop(self) -> None:
        if self._stop_event is not None:
            self._stop_event.set()
        self.wait(8000)

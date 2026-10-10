"""High-level repository for sessions, predictions, and sensor events."""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, List, Optional

from flow_lol.config.settings import AppSettings
from flow_lol.inference.pipeline import Prediction
from flow_lol.persistence.database import (
    Match,
    Prediction as PredictionRow,
    SensorEvent,
    Session,
    init_db,
    session_maker,
)
from flow_lol.utils.paths import database_path

logger = logging.getLogger(__name__)


def _json(obj: Any) -> str:
    return json.dumps(obj, default=str, ensure_ascii=False)


class SessionRepository:
    """Create and query sessions, matches, predictions, and sensor-quality events."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        self.db_path = db_path or str(database_path())
        init_db(self.db_path)
        self._Session = session_maker(self.db_path)
        self.active_match_id: Optional[int] = None

    def create_session(self, settings: AppSettings, game_mode: Optional[str] = None) -> int:
        settings_dict = {
            "use_h10": settings.use_h10,
            "use_verity": settings.use_verity,
            "preferred_sensor": settings.preferred_sensor,
            "use_biraffe2_svm": settings.use_biraffe2_svm,
            "use_biraffe2_knn": settings.use_biraffe2_knn,
            "use_biraffe2_rf": settings.use_biraffe2_rf,
            "use_irshad_rf": settings.use_irshad_rf,
            "use_biraffe2_mlp": settings.use_biraffe2_mlp,
            "window_seconds": settings.window_seconds,
            "overlap_percent": settings.overlap_percent,
            "sampling_rate": settings.sampling_rate,
            "webcam_enabled": settings.webcam_enabled,
            "auto_detect_game": settings.auto_detect_game,
        }
        now = time.time()
        row = Session(
            created_at=now,
            started_at=now,
            game_mode=game_mode,
            window_seconds=settings.window_seconds,
            overlap_percent=settings.overlap_percent,
            sampling_rate=settings.sampling_rate,
            settings_json=_json(settings_dict),
        )
        with self._Session() as sess:
            sess.add(row)
            sess.commit()
            session_id = row.id
        logger.info("Created session %s", session_id)
        return session_id

    def end_session(self, session_id: int, sensor_summary: Optional[str] = None) -> None:
        with self._Session() as sess:
            row = sess.query(Session).filter_by(id=session_id).first()
            if row is None:
                logger.warning("Session %s not found; cannot end", session_id)
                return
            row.ended_at = time.time()
            if sensor_summary is not None:
                row.sensor_summary = sensor_summary
            sess.commit()
        logger.info("Ended session %s", session_id)

    def start_match(self, session_id: int, game_mode: str, detected: bool = False) -> int:
        row = Match(
            session_id=session_id,
            started_at=time.time(),
            game_mode=game_mode,
            detected=1 if detected else 0,
        )
        with self._Session() as sess:
            sess.add(row)
            sess.commit()
            self.active_match_id = row.id
        logger.info("Started match %s (game_mode=%s, detected=%s)", self.active_match_id, game_mode, detected)
        return self.active_match_id

    def end_match(self, match_id: Optional[int] = None) -> None:
        match_id = match_id or self.active_match_id
        if match_id is None:
            return
        with self._Session() as sess:
            row = sess.query(Match).filter_by(id=match_id).first()
            if row is None:
                logger.warning("Match %s not found; cannot end", match_id)
                return
            row.ended_at = time.time()
            sess.commit()
        if self.active_match_id == match_id:
            self.active_match_id = None
        logger.info("Ended match %s", match_id)

    def add_prediction(self, session_id: int, prediction: Prediction) -> None:
        row = PredictionRow(
            session_id=session_id,
            match_id=self.active_match_id,
            timestamp=prediction.end_timestamp,
            sensor_name=prediction.sensor_name,
            n_samples=prediction.n_samples,
            ensemble_label=prediction.ensemble_label,
            n_votes=prediction.n_votes,
            n_for_majority=prediction.n_for_majority,
            votes_json=_json(prediction.votes),
            probabilities_json=_json(prediction.probabilities),
            features_json=_json(prediction.features),
        )
        with self._Session() as sess:
            sess.add(row)
            sess.commit()

    def add_sensor_event(
        self,
        session_id: int,
        sensor_name: str,
        event_type: str,
        message: Optional[str] = None,
        timestamp: Optional[float] = None,
    ) -> None:
        row = SensorEvent(
            session_id=session_id,
            timestamp=timestamp or time.time(),
            sensor_name=sensor_name,
            event_type=event_type,
            message=message,
        )
        with self._Session() as sess:
            sess.add(row)
            sess.commit()

    def get_sessions(self, limit: int = 100) -> List[Dict[str, Any]]:
        with self._Session() as sess:
            rows = (
                sess.query(Session)
                .order_by(Session.started_at.desc())
                .limit(limit)
                .all()
            )
            return [
                {
                    "id": r.id,
                    "created_at": r.created_at,
                    "started_at": r.started_at,
                    "ended_at": r.ended_at,
                    "game_mode": r.game_mode,
                    "sensor_summary": r.sensor_summary,
                    "window_seconds": r.window_seconds,
                    "overlap_percent": r.overlap_percent,
                    "sampling_rate": r.sampling_rate,
                }
                for r in rows
            ]

    def get_matches(self, session_id: int) -> List[Dict[str, Any]]:
        with self._Session() as sess:
            rows = (
                sess.query(Match)
                .filter_by(session_id=session_id)
                .order_by(Match.started_at.asc())
                .all()
            )
            return [
                {
                    "id": r.id,
                    "started_at": r.started_at,
                    "ended_at": r.ended_at,
                    "game_mode": r.game_mode,
                    "detected": bool(r.detected),
                    "notes": r.notes,
                }
                for r in rows
            ]

    def get_predictions(self, session_id: int) -> List[Dict[str, Any]]:
        with self._Session() as sess:
            rows = (
                sess.query(PredictionRow)
                .filter_by(session_id=session_id)
                .order_by(PredictionRow.timestamp.asc())
                .all()
            )
            return [
                {
                    "id": r.id,
                    "match_id": r.match_id,
                    "timestamp": r.timestamp,
                    "sensor_name": r.sensor_name,
                    "n_samples": r.n_samples,
                    "ensemble_label": r.ensemble_label,
                    "n_votes": r.n_votes,
                    "n_for_majority": r.n_for_majority,
                    "votes": json.loads(r.votes_json),
                    "probabilities": json.loads(r.probabilities_json) if r.probabilities_json else None,
                    "features": json.loads(r.features_json) if r.features_json else None,
                }
                for r in rows
            ]

    def get_sensor_events(self, session_id: int) -> List[Dict[str, Any]]:
        with self._Session() as sess:
            rows = (
                sess.query(SensorEvent)
                .filter_by(session_id=session_id)
                .order_by(SensorEvent.timestamp.asc())
                .all()
            )
            return [
                {
                    "id": r.id,
                    "timestamp": r.timestamp,
                    "sensor_name": r.sensor_name,
                    "event_type": r.event_type,
                    "message": r.message,
                }
                for r in rows
            ]

    def delete_session(self, session_id: int) -> None:
        with self._Session() as sess:
            sess.query(PredictionRow).filter_by(session_id=session_id).delete(
                synchronize_session=False
            )
            sess.query(Match).filter_by(session_id=session_id).delete(
                synchronize_session=False
            )
            sess.query(SensorEvent).filter_by(session_id=session_id).delete(
                synchronize_session=False
            )
            sess.query(Session).filter_by(id=session_id).delete(
                synchronize_session=False
            )
            sess.commit()
        logger.info("Deleted session %s and all linked rows", session_id)
        if self.active_match_id is not None:
            # Safety: if the deleted session had the active match, clear it.
            self.active_match_id = None

    def close_stale_sessions(self) -> int:
        """Mark every open session as ended (used on startup after a crash).

        Returns the number of sessions that were closed.
        """
        with self._Session() as sess:
            rows = sess.query(Session).filter_by(ended_at=None).all()
            now = time.time()
            for row in rows:
                row.ended_at = now
            sess.commit()
        if rows:
            logger.info("Closed %s stale session(s) left running after a crash", len(rows))
        return len(rows)

    def delete_all_sessions(self) -> int:
        """Delete every session and all linked rows. Returns the number of sessions removed."""
        with self._Session() as sess:
            n_predictions = sess.query(PredictionRow).delete(synchronize_session=False)
            n_matches = sess.query(Match).delete(synchronize_session=False)
            n_events = sess.query(SensorEvent).delete(synchronize_session=False)
            n_sessions = sess.query(Session).delete(synchronize_session=False)
            sess.commit()
        logger.info(
            "Deleted all sessions (%s), matches (%s), predictions (%s), events (%s)",
            n_sessions,
            n_matches,
            n_predictions,
            n_events,
        )
        self.active_match_id = None
        return n_sessions

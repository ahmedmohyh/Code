"""Detect and parse League of Legends `.rofl` replay files."""

from __future__ import annotations

import json
import logging
import struct
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from flow_lol.persistence.repository import SessionRepository

logger = logging.getLogger(__name__)

# Default LoL replay location on Windows.
DEFAULT_REPLAY_DIR = Path.home() / "Documents" / "League of Legends" / "Replays"


def _default_replay_dir() -> Path:
    return DEFAULT_REPLAY_DIR


def parse_rofl_header(path: Path) -> Optional[Dict[str, object]]:
    """Read the metadata header from a `.rofl` file.

    The first 4 bytes are the length of a JSON metadata string, followed by
    the JSON itself. The JSON contains fields such as ``gameId``,
    ``gameLength``, ``recordingOffset``, and ``recordingLength``.
    """
    try:
        with path.open("rb") as f:
            raw_len = f.read(4)
            if len(raw_len) != 4:
                return None
            (meta_len,) = struct.unpack("<I", raw_len)
            if meta_len > 2_000_000:
                # Sanity cap; a metadata block should never be this large.
                return None
            meta_bytes = f.read(meta_len)
            if len(meta_bytes) != meta_len:
                return None
            meta = json.loads(meta_bytes.decode("utf-8", errors="replace"))
    except Exception as exc:
        logger.debug("Could not parse replay header for %s: %s", path, exc)
        return None

    if not isinstance(meta, dict):
        return None

    # recordingOffset is milliseconds since epoch when the recording started.
    offset_ms = meta.get("recordingOffset")
    length_ms = meta.get("recordingLength")
    recorded_at = None
    duration_seconds = None
    if isinstance(offset_ms, (int, float)):
        recorded_at = offset_ms / 1000.0
    if isinstance(length_ms, (int, float)):
        duration_seconds = length_ms / 1000.0

    return {
        "game_id": str(meta.get("gameId")) if meta.get("gameId") is not None else None,
        "recorded_at": recorded_at,
        "duration_seconds": duration_seconds,
        "game_length": meta.get("gameLength"),
        "raw_metadata": meta,
    }


def scan_replays(
    replay_dir: Optional[Path | str] = None,
) -> List[Dict[str, object]]:
    """Return metadata for every `.rofl` file in the replay folder."""
    if replay_dir is None:
        directory = _default_replay_dir()
    else:
        directory = Path(replay_dir)

    results: List[Dict[str, object]] = []
    if not directory.exists():
        return results

    for path in sorted(directory.glob("*.rofl"), key=lambda p: p.stat().st_mtime, reverse=True):
        header = parse_rofl_header(path)
        if header is None:
            continue
        header["file_path"] = str(path)
        header["file_name"] = path.name
        results.append(header)
    return results


def scan_replays_for_session(
    replay_dir: Path | str,
    session_id: int,
    match_id: int,
    repository: SessionRepository,
    lookback_seconds: float = 600.0,
) -> List[Dict[str, object]]:
    """Find replays recorded around the start of ``match_id`` and link them.

    Returns the list of newly linked replays.
    """
    matches = repository.get_matches(session_id)
    match = next((m for m in matches if m["id"] == match_id), None)
    if match is None:
        return []

    match_start = match["started_at"]
    existing = {r["file_path"] for r in repository.get_replays(session_id, match_id=match_id)}

    linked: List[Dict[str, object]] = []
    for replay in scan_replays(replay_dir):
        if replay["file_path"] in existing:
            continue
        recorded_at = replay.get("recorded_at")
        if recorded_at is None:
            continue
        # Accept replays that started shortly before/after the match was detected.
        if abs(recorded_at - match_start) <= lookback_seconds:
            repository.add_replay(
                file_path=replay["file_path"],
                game_id=replay.get("game_id"),
                recorded_at=recorded_at,
                duration_seconds=replay.get("duration_seconds"),
                session_id=session_id,
                match_id=match_id,
            )
            linked.append(replay)
    return linked

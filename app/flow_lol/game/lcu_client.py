"""League Client Update (LCU) API client for local match detection.

This connects to the League of Legends client that runs on the user's PC while
the client is open. It does **not** need a Riot Games API key and does **not**
make external network requests.

The client exposes an HTTPS server on localhost. The port and password are read
from the ``lockfile`` that the client creates in its install directory.
"""

from __future__ import annotations

import base64
import logging
import os
import ssl
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import aiohttp

logger = logging.getLogger(__name__)

# Common Windows locations for the League Client lockfile.
_LOCKFILE_CANDIDATES: List[Callable[[], Path | None]] = [
    lambda: _local_appdata_path("League of Legends", "lockfile"),
    lambda: _local_appdata_path("Riot Games", "League of Legends", "lockfile"),
    lambda: _local_appdata_path("Riot Games", "Riot Client", "Config", "lockfile"),
    lambda: Path("C:/Riot Games/League of Legends/lockfile"),
]

# Queue ID -> human-readable mode used by the rest of the app.
QUEUE_ID_TO_MODE: Dict[int, str] = {
    420: "Ranked Solo/Duo",
    440: "Ranked Flex",
    450: "ARAM",
    400: "Normal",
    430: "Normal",
    700: "Clash",
    840: "Bot",
    850: "Bot",
    900: "URF",
    950: "URF",
    1300: "Nexus Blitz",
    2000: "Tutorial",
}


@dataclass
class LcuCredentials:
    """Port and password extracted from a League Client lockfile."""

    port: int
    password: str
    protocol: str

    @property
    def base_url(self) -> str:
        return f"{self.protocol}://127.0.0.1:{self.port}"

    @property
    def auth_header(self) -> str:
        token = base64.b64encode(f"riot:{self.password}".encode()).decode()
        return f"Basic {token}"


def _local_appdata_path(*parts: str) -> Path | None:
    appdata = os.environ.get("LOCALAPPDATA")
    if not appdata:
        return None
    return Path(appdata).joinpath(*parts)


def _find_lockfile() -> Path | None:
    """Return the first existing lockfile path, or None if not found."""
    for candidate in _LOCKFILE_CANDIDATES:
        try:
            path = candidate()
            if path is not None and path.exists():
                return path
        except Exception:
            continue
    return None


def _find_lockfile_from_process() -> Path | None:
    """Try to locate the lockfile from the running LeagueClient.exe process."""
    try:
        import psutil
    except ImportError:
        return None

    try:
        for proc in psutil.process_iter(["name", "exe"]):
            name = proc.info.get("name") or ""
            if "LeagueClient" in name:
                exe = proc.info.get("exe")
                if exe:
                    path = Path(exe).parent / "lockfile"
                    if path.exists():
                        return path
    except Exception as exc:
        logger.debug("Could not locate lockfile from process: %s", exc)
    return None


def _parse_lockfile(path: Path) -> Optional[LcuCredentials]:
    """Parse ``LeagueClient:<pid>:<port>:<password>:<protocol>``."""
    try:
        raw = path.read_text(encoding="utf-8").strip()
        parts = raw.split(":")
        if len(parts) != 5:
            logger.warning("Unexpected lockfile format: %s", raw)
            return None
        _, _, port_str, password, protocol = parts
        return LcuCredentials(port=int(port_str), password=password, protocol=protocol)
    except Exception as exc:
        logger.warning("Failed to parse lockfile %s: %s", path, exc)
        return None


class LcuClient:
    """Async LCU API client that polls the local League Client.

    Also polls the in-game Live Client Data API on port 2999 to capture
    kills, deaths, objectives and other events while a match is running.
    """

    def __init__(
        self,
        on_match_start: Callable[[str, bool], None],
        on_match_end: Callable[[], None],
        on_game_event: Optional[Callable[[dict], None]] = None,
        poll_interval: float = 2.0,
        event_poll_interval: float = 1.0,
    ) -> None:
        self.on_match_start = on_match_start
        self.on_match_end = on_match_end
        self.on_game_event = on_game_event
        self.poll_interval = poll_interval
        self.event_poll_interval = event_poll_interval

        self._creds: Optional[LcuCredentials] = None
        self.__session: Optional[aiohttp.ClientSession] = None
        self._last_phase: str = "None"
        self._in_match = False
        self._current_mode: str = "Unknown"

    def last_phase(self) -> str:
        """Return the most recently polled gameflow phase."""
        return self._last_phase
        self._ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        self._ssl_context.check_hostname = False
        self._ssl_context.verify_mode = ssl.CERT_NONE

        self._event_session: Optional[aiohttp.ClientSession] = None
        self._seen_event_ids: set[str] = set()

    async def is_available(self) -> bool:
        """Return True if a lockfile can be found and the client responds."""
        if not await self._ensure_credentials():
            return False
        try:
            session = self._get_session()
            async with session.get(
                f"{self._creds.base_url}/lol-gameflow/v1/gameflow-phase",
                timeout=aiohttp.ClientTimeout(total=3.0),
            ) as resp:
                return resp.status == 200
        except Exception as exc:
            logger.debug("LCU availability check failed: %s", exc)
            return False

    async def _ensure_credentials(self) -> bool:
        """Find and parse the lockfile if we have not already done so."""
        if self._creds is not None:
            return True
        path = _find_lockfile() or _find_lockfile_from_process()
        if path is None:
            return False
        self._creds = _parse_lockfile(path)
        if self._creds is None:
            return False
        logger.info("LCU lockfile found: %s (port %s)", path, self._creds.port)
        return True

    def _get_session(self) -> aiohttp.ClientSession:
        """Return the LCU aiohttp session, creating it lazily."""
        if self.__session is None or self.__session.closed:
            headers = {
                "Authorization": self._creds.auth_header,
                "Accept": "application/json",
            }
            self.__session = aiohttp.ClientSession(
                headers=headers,
                connector=aiohttp.TCPConnector(ssl=self._ssl_context),
            )
        return self.__session

    async def poll_once(self) -> bool:
        """Poll the LCU gameflow phase and emit start/end events.

        Returns True if the client is still reachable.
        """
        if not await self._ensure_credentials():
            return False

        phase = await self._get_phase()
        if phase is None:
            # Client may have closed; drop credentials and let the detector retry.
            self._creds = None
            if self.__session is not None and not self.__session.closed:
                await self.__session.close()
                self.__session = None
            return False

        self._last_phase = phase
        logger.debug("LCU gameflow phase: %s", phase)

        if phase == "InProgress" and not self._in_match:
            mode = await self._resolve_game_mode()
            self._in_match = True
            self._current_mode = mode
            logger.info("LCU match started: %s", mode)
            self.on_match_start(mode, detected=True)

        elif phase in ("EndOfGame", "None", "Lobby", "Matchmaking", "ChampSelect") and self._in_match:
            # EndOfGame means the match is over; None/Lobby means the client left the post-game screen.
            self._in_match = False
            logger.info("LCU match ended (phase: %s)", phase)
            self.on_match_end()

        return True

    async def poll_events_once(self) -> None:
        """Poll the in-game Live Client Data API and emit new events.

        Only called while the LCU phase reports the match is ``InProgress``.
        The Live Client Data API runs on port 2999 with a self-signed cert.
        """
        if self.on_game_event is None:
            return
        try:
            session = self._get_event_session()
            async with session.get(
                "https://127.0.0.1:2999/liveclientdata/eventdata",
                timeout=aiohttp.ClientTimeout(total=2.0),
            ) as resp:
                if resp.status != 200:
                    return
                data = await resp.json()
        except Exception as exc:
            logger.debug("Live Client eventdata request failed: %s", exc)
            return

        events = data.get("Events", []) if isinstance(data, dict) else []
        for event in events:
            event_id = self._event_id(event)
            if event_id in self._seen_event_ids:
                continue
            self._seen_event_ids.add(event_id)
            parsed = self._parse_live_event(event)
            if parsed is not None:
                logger.debug("Live Client event: %s", parsed)
                self.on_game_event(parsed)

    def _get_event_session(self) -> aiohttp.ClientSession:
        """Return an unauthenticated session for the Live Client Data API."""
        if self._event_session is None or self._event_session.closed:
            self._event_session = aiohttp.ClientSession(
                connector=aiohttp.TCPConnector(ssl=self._ssl_context),
            )
        return self._event_session

    @staticmethod
    def _event_id(event: dict) -> str:
        """Build a stable ID for an event so we can deduplicate."""
        return "{}-{}-{}-{}".format(
            event.get("EventID", ""),
            event.get("EventTime", ""),
            event.get("EventName", ""),
            event.get("KillerName", event.get("ActorName", "")),
        )

    @staticmethod
    def _parse_live_event(event: dict) -> Optional[dict]:
        """Convert a Live Client Data event into a normalized game event.

        Returns None for unsupported event types.
        """
        name = event.get("EventName", "")
        timestamp = event.get("EventTime")
        if timestamp is None:
            return None

        mapping = {
            "ChampionKill": ("kill", "KillerName", "VictimName"),
            "TurretKilled": ("objective", "KillerName", ""),
            "InhibKilled": ("objective", "KillerName", ""),
            "DragonKilled": ("objective", "KillerName", "DragonType"),
            "BaronKilled": ("objective", "KillerName", ""),
            "HeraldKilled": ("objective", "KillerName", ""),
        }
        if name not in mapping:
            return None

        event_type, actor_key, target_key = mapping[name]
        return {
            "raw": event,
            "event_type": event_type,
            "timestamp": float(timestamp),
            "actor": event.get(actor_key),
            "target": event.get(target_key) if target_key else None,
            "description": name,
        }

    async def _get_phase(self) -> Optional[str]:
        """Return the current gameflow phase string, or None on failure."""
        try:
            session = self._get_session()
            async with session.get(
                f"{self._creds.base_url}/lol-gameflow/v1/gameflow-phase",
                timeout=aiohttp.ClientTimeout(total=3.0),
            ) as resp:
                if resp.status != 200:
                    return None
                # Response is a JSON string like "\"InProgress\"".
                data = await resp.json()
                if isinstance(data, str):
                    return data
                return data.get("phase") if isinstance(data, dict) else None
        except Exception as exc:
            logger.debug("LCU phase request failed: %s", exc)
            return None

    async def _resolve_game_mode(self) -> str:
        """Ask the LCU session endpoint for the queue ID and map it to a mode."""
        try:
            session = self._get_session()
            async with session.get(
                f"{self._creds.base_url}/lol-gameflow/v1/session",
                timeout=aiohttp.ClientTimeout(total=3.0),
            ) as resp:
                if resp.status != 200:
                    return "Unknown"
                session_data = await resp.json()
                queue_id = self._extract_queue_id(session_data)
                if queue_id is not None:
                    return QUEUE_ID_TO_MODE.get(queue_id, f"Queue {queue_id}")
        except Exception as exc:
            logger.warning("Could not resolve LCU game mode: %s", exc)
        return "Unknown"

    @staticmethod
    def _extract_queue_id(session_data: Any) -> Optional[int]:
        """Safely extract queue.id from a gameflow session response."""
        if not isinstance(session_data, dict):
            return None
        queue = session_data.get("queue") or session_data.get("gameData", {}).get("queue")
        if isinstance(queue, dict):
            return queue.get("id")
        return None

    async def close(self) -> None:
        """Close the underlying aiohttp session."""
        if self.__session is not None and not self.__session.closed:
            await self.__session.close()
            self.__session = None
        if self._event_session is not None and not self._event_session.closed:
            await self._event_session.close()
            self._event_session = None
        self._creds = None

    def reset_event_tracking(self) -> None:
        """Clear seen event IDs, e.g. at the start of a new match."""
        self._seen_event_ids.clear()


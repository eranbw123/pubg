"""Token-authenticated loopback WebSocket server.

Binds to ``127.0.0.1`` only. The bind address is asserted rather than
configured freely: a bridge that accepted connections from the network would
expose live position data to anything on the LAN.

The server runs its asyncio loop on a daemon thread so the controller's control
loop stays synchronous and testable. Shared state is guarded by a lock and
copied out; callers never see a half-written snapshot.
"""

from __future__ import annotations

import asyncio
import json
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import websockets
from websockets.asyncio.server import ServerConnection, serve

from ..clock import Clock, SystemClock
from .envelope import (
    MSG_AUTH_FAILED,
    MSG_AUTH_OK,
    PROTOCOL_VERSION,
    AuthRequest,
    AuthResponse,
    BridgeFrame,
)
from .session import SessionTracker

LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})


@dataclass
class ServerConfig:
    host: str = "127.0.0.1"
    port: int = 17311
    token: str = ""
    heartbeat_interval_s: float = 1.0
    stale_after_s: float = 5.0
    #: Frames retained for the run bundle; oldest are dropped beyond this.
    max_buffered_frames: int = 20000

    def __post_init__(self) -> None:
        if self.host not in LOOPBACK_HOSTS:
            raise ValueError(
                f"bridge host must be loopback, got {self.host!r}. "
                "Binding to a routable interface would expose live game data."
            )


@dataclass
class BridgeServer:
    """Receives bridge frames. Never sends anything that could reach the game."""

    config: ServerConfig
    clock: Clock = field(default_factory=SystemClock)
    #: Called on the server thread for every accepted frame.
    on_frame: Callable[[BridgeFrame, float], None] | None = None

    tracker: SessionTracker = field(init=False)
    _frames: list[dict[str, Any]] = field(default_factory=list, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)
    _loop: asyncio.AbstractEventLoop | None = field(default=None, init=False)
    _thread: threading.Thread | None = field(default=None, init=False)
    _stop_event: asyncio.Event | None = field(default=None, init=False)
    _ready: threading.Event = field(default_factory=threading.Event, init=False)
    _rejected_connections: int = field(default=0, init=False)
    _last_error: str = field(default="", init=False)

    def __post_init__(self) -> None:
        self.tracker = SessionTracker(stale_after_s=self.config.stale_after_s)

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #
    def start(self, timeout_s: float = 5.0) -> None:
        if self._thread is not None:
            return
        self._ready.clear()
        self._thread = threading.Thread(target=self._run_loop, name="bridge-server", daemon=True)
        self._thread.start()
        if not self._ready.wait(timeout_s):
            raise RuntimeError(f"bridge server did not start within {timeout_s}s")

    def stop(self, timeout_s: float = 5.0) -> None:
        loop, stop_event = self._loop, self._stop_event
        if loop is not None and stop_event is not None:
            loop.call_soon_threadsafe(stop_event.set)
        if self._thread is not None:
            self._thread.join(timeout_s)
        self._thread = None
        self._loop = None
        self.tracker.on_disconnect("server stopped")

    def _run_loop(self) -> None:
        asyncio.run(self._serve())

    async def _serve(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._stop_event = asyncio.Event()
        async with serve(self._handle, self.config.host, self.config.port):
            self._ready.set()
            await self._stop_event.wait()

    # ------------------------------------------------------------------ #
    # Connection handling
    # ------------------------------------------------------------------ #
    async def _handle(self, connection: ServerConnection) -> None:
        try:
            raw_auth = await asyncio.wait_for(connection.recv(), timeout=10.0)
        except (TimeoutError, websockets.exceptions.ConnectionClosed):
            self._rejected_connections += 1
            self._last_error = "auth frame not received"
            return

        accepted, detail, session_id = self._authenticate(raw_auth)
        await connection.send(
            AuthResponse(
                type=MSG_AUTH_OK if accepted else MSG_AUTH_FAILED,
                accepted=accepted,
                detail=detail,
                heartbeat_interval_s=self.config.heartbeat_interval_s,
            ).model_dump_json()
        )
        if not accepted:
            self._rejected_connections += 1
            self._last_error = detail
            await connection.close(code=4401, reason=detail[:120])
            return

        self.tracker.on_connect(session_id, self.clock.monotonic())
        try:
            async for message in connection:
                self._ingest(message)
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self.tracker.on_disconnect("bridge disconnected")

    def _authenticate(self, raw: str | bytes) -> tuple[bool, str, str]:
        try:
            payload = json.loads(raw)
            request = AuthRequest.model_validate(payload)
        except Exception as exc:
            return False, f"malformed auth frame: {exc}"[:200], ""

        if request.protocol_version != PROTOCOL_VERSION:
            return (
                False,
                f"protocol version mismatch: bridge {request.protocol_version}, "
                f"controller {PROTOCOL_VERSION}",
                "",
            )
        if not self.config.token or request.token != self.config.token:
            return False, "invalid session token", ""
        return True, "authenticated", request.session_id or "unnamed-session"

    def _ingest(self, message: str | bytes) -> None:
        now = self.clock.monotonic()
        try:
            payload = json.loads(message)
        except json.JSONDecodeError as exc:
            self.tracker.parse_warnings += 1
            self._record({"type": "invalid_json", "error": str(exc), "at": now})
            return

        try:
            frame = BridgeFrame.model_validate(payload)
        except Exception as exc:
            self.tracker.parse_warnings += 1
            self._record({"type": "invalid_frame", "error": str(exc)[:300], "raw": payload})
            return

        if frame.type == "feature_status":
            for entry in frame.raw.get("features", []):
                if isinstance(entry, dict) and "feature" in entry:
                    self.tracker.feature_registration[str(entry["feature"])] = bool(
                        entry.get("registered")
                    )

        accepted, reason = self.tracker.accept(frame.sequence, now)
        record = frame.model_dump(mode="json")
        record["controller_receive_ts"] = now
        record["accepted"] = accepted
        record["accept_reason"] = reason
        self._record(record)

        if accepted and self.on_frame is not None:
            self.on_frame(frame, now)

    def _record(self, entry: dict[str, Any]) -> None:
        with self._lock:
            self._frames.append(entry)
            if len(self._frames) > self.config.max_buffered_frames:
                del self._frames[: len(self._frames) - self.config.max_buffered_frames]

    # ------------------------------------------------------------------ #
    @property
    def frames(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._frames)

    @property
    def rejected_connections(self) -> int:
        return self._rejected_connections

    @property
    def last_error(self) -> str:
        return self._last_error

    def drain_frames(self) -> list[dict[str, Any]]:
        with self._lock:
            drained, self._frames = self._frames, []
        return drained


__all__ = ["LOOPBACK_HOSTS", "BridgeServer", "ServerConfig"]

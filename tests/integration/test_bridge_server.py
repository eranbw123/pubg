"""Loopback bridge server, exercised with a fake bridge client.

The fake client speaks the real wire protocol over a real socket, so auth,
framing and sequence handling are tested end to end without Overwolf or the
game. No test here can send input: Stage 1 registers no actuator at all.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

import pytest
import websockets

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fixtures import overwolf_payloads as payloads  # noqa: E402
from pubg_training_bot.protocol.envelope import PROTOCOL_VERSION  # noqa: E402
from pubg_training_bot.protocol.server import BridgeServer, ServerConfig  # noqa: E402
from pubg_training_bot.sensors.overwolf import OverwolfSensorSource  # noqa: E402

TOKEN = "test-token-abc123"


def free_port() -> int:
    import socket

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class FakeBridgeClient:
    """Minimal stand-in for the Overwolf app."""

    def __init__(self, port: int, token: str = TOKEN, protocol_version: int = PROTOCOL_VERSION):
        self.port = port
        self.token = token
        self.protocol_version = protocol_version
        self.sequence = 0

    async def __aenter__(self) -> FakeBridgeClient:
        self.connection = await websockets.connect(f"ws://127.0.0.1:{self.port}")
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.connection.close()

    async def authenticate(self) -> dict[str, Any]:
        await self.connection.send(
            json.dumps(
                {
                    "type": "auth",
                    "protocol_version": self.protocol_version,
                    "token": self.token,
                    "bridge_version": "test",
                    "session_id": "fake-session",
                }
            )
        )
        return json.loads(await asyncio.wait_for(self.connection.recv(), timeout=5))

    async def send_raw(self, payload: str) -> None:
        await self.connection.send(payload)

    async def send_frame(
        self, raw: dict[str, Any], frame_type: str = "info_update", sequence: int | None = None
    ) -> None:
        if sequence is None:
            self.sequence += 1
            sequence = self.sequence
        await self.connection.send(
            json.dumps(
                {
                    "type": frame_type,
                    "sequence": sequence,
                    "bridge_ts_ms": sequence * 100.0,
                    "source_ts_ms": None,
                    "raw": raw,
                    "normalized": None,
                    "feature": raw.get("feature"),
                }
            )
        )


async def settle(predicate, timeout: float = 5.0) -> bool:
    """Wait for the server thread to catch up, without a blind sleep."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        if predicate():
            return True
        await asyncio.sleep(0.02)
    return False


@pytest.fixture
def server():
    config = ServerConfig(port=free_port(), token=TOKEN)
    instance = BridgeServer(config=config)
    instance.start()
    yield instance
    instance.stop()


# --------------------------------------------------------------------------- #
def test_non_loopback_bind_is_refused() -> None:
    """Binding to a routable interface would expose live position data."""
    with pytest.raises(ValueError, match="loopback"):
        ServerConfig(host="0.0.0.0", port=17311, token=TOKEN)  # noqa: S104
    ServerConfig(host="127.0.0.1", port=17311, token=TOKEN)


@pytest.mark.asyncio
async def test_valid_token_is_accepted(server: BridgeServer) -> None:
    async with FakeBridgeClient(server.config.port) as client:
        response = await client.authenticate()
    assert response["accepted"] is True
    assert response["type"] == "auth_ok"


@pytest.mark.asyncio
async def test_wrong_token_is_rejected(server: BridgeServer) -> None:
    async with FakeBridgeClient(server.config.port, token="not-the-token") as client:
        response = await client.authenticate()
    assert response["accepted"] is False
    assert "token" in response["detail"]
    assert await settle(lambda: server.rejected_connections == 1)


@pytest.mark.asyncio
async def test_protocol_version_mismatch_is_rejected(server: BridgeServer) -> None:
    async with FakeBridgeClient(server.config.port, protocol_version=999) as client:
        response = await client.authenticate()
    assert response["accepted"] is False
    assert "protocol version mismatch" in response["detail"]


@pytest.mark.asyncio
async def test_frames_are_recorded_with_raw_payload_intact(server: BridgeServer) -> None:
    async with FakeBridgeClient(server.config.port) as client:
        await client.authenticate()
        await client.send_frame(payloads.LOCATION_UPDATE)
        assert await settle(lambda: server.tracker.messages_received == 1)

    frames = [f for f in server.frames if f.get("type") == "info_update"]
    assert len(frames) == 1
    assert frames[0]["raw"]["info"]["location"]["location"] == '{"x":2300,"y":5740,"z":1520}', (
        "the raw payload must survive byte-for-byte for offline re-parsing"
    )
    assert frames[0]["accepted"] is True


@pytest.mark.asyncio
async def test_malformed_json_is_counted_not_crashing(server: BridgeServer) -> None:
    async with FakeBridgeClient(server.config.port) as client:
        await client.authenticate()
        await client.send_raw("{not json at all")
        await client.send_frame(payloads.MAP_UPDATE)
        assert await settle(lambda: server.tracker.messages_received == 1)

    assert server.tracker.parse_warnings >= 1
    assert any(f.get("type") == "invalid_json" for f in server.frames)


@pytest.mark.asyncio
async def test_frame_failing_schema_is_preserved_as_invalid(server: BridgeServer) -> None:
    async with FakeBridgeClient(server.config.port) as client:
        await client.authenticate()
        await client.send_raw(json.dumps({"type": "info_update", "sequence": -5}))
        assert await settle(lambda: server.tracker.parse_warnings >= 1)

    invalid = [f for f in server.frames if f.get("type") == "invalid_frame"]
    assert invalid, "an unparseable frame must be recorded, not dropped silently"
    assert "raw" in invalid[0]


@pytest.mark.asyncio
async def test_duplicate_and_regressed_sequences_are_handled(server: BridgeServer) -> None:
    async with FakeBridgeClient(server.config.port) as client:
        await client.authenticate()
        await client.send_frame(payloads.MAP_UPDATE, sequence=5)
        await client.send_frame(payloads.MAP_UPDATE, sequence=5)
        await client.send_frame(payloads.MAP_UPDATE, sequence=2)
        await client.send_frame(payloads.MAP_UPDATE, sequence=6)
        assert await settle(lambda: server.tracker.messages_received == 2)

    assert server.tracker.duplicates_dropped == 1
    assert server.tracker.regressions_rejected == 1


@pytest.mark.asyncio
async def test_feature_registration_outcomes_are_recorded(server: BridgeServer) -> None:
    async with FakeBridgeClient(server.config.port) as client:
        await client.authenticate()
        await client.send_frame(
            {
                "features": [
                    {"feature": "location", "registered": True},
                    {"feature": "me", "registered": False},
                ]
            },
            frame_type="feature_status",
        )
        assert await settle(lambda: bool(server.tracker.feature_registration))

    assert server.tracker.feature_registration == {"location": True, "me": False}


# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_sensor_source_builds_snapshots_from_live_frames() -> None:
    config = ServerConfig(port=free_port(), token=TOKEN)
    source = OverwolfSensorSource(config=config)
    source.start()
    try:
        assert source.latest() is None, "no snapshot before any data arrives"

        async with FakeBridgeClient(config.port) as client:
            await client.authenticate()
            await client.send_frame(payloads.MAP_UPDATE)
            await client.send_frame(payloads.PHASE_UPDATE)
            await client.send_frame(payloads.ME_UPDATE)
            await client.send_frame(payloads.LOCATION_UPDATE)
            assert await settle(
                lambda: source.latest() is not None and source.latest().raw_position is not None
            )

        snapshot = source.latest()
        assert snapshot is not None
        assert snapshot.map_id == "Erangel_Main"
        assert str(snapshot.phase) == "landed"
        assert str(snapshot.view) == "fpp"
        assert snapshot.raw_position is not None
        assert snapshot.raw_position.as_tuple() == (2300.0, 5740.0, 1520.0)
        assert snapshot.location_age_s is not None and snapshot.location_age_s < 5.0
        assert snapshot.heading is None, "heading arrives in Stage 4; it must abstain now"
        assert snapshot.foreground is False, "foreground is unknown until Stage 2 supplies it"

        observations = source.observations()
        assert observations["position_updates"] == 1
        assert observations["observed_maps"] == ["Erangel_Main"]
    finally:
        source.stop()


@pytest.mark.asyncio
async def test_location_age_grows_when_updates_stop() -> None:
    """The headline sensor rule: a stale position stays visible but ages."""
    config = ServerConfig(port=free_port(), token=TOKEN)
    source = OverwolfSensorSource(config=config)
    source.start()
    try:
        async with FakeBridgeClient(config.port) as client:
            await client.authenticate()
            await client.send_frame(payloads.LOCATION_UPDATE)
            assert await settle(
                lambda: source.latest() is not None and source.latest().raw_position is not None
            )
            first = source.latest().location_age_s

            await asyncio.sleep(0.4)
            # A non-location update must not refresh the location age.
            await client.send_frame(payloads.MAP_UPDATE)
            assert await settle(lambda: source.latest().map_id == "Erangel_Main")

        later = source.latest().location_age_s
        assert first is not None and later is not None
        assert later > first, "an unrelated feature update must not reset location age"
    finally:
        source.stop()

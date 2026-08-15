"""Tests for the append-only RappterZoo organism frame ledger."""

import json
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import organism_ledger as ledger
import data_molt


def payload(event_id, event="test", organism="rappterzoo"):
    return {
        "schema": "rappterzoo-organism-frame/1",
        "event_id": event_id,
        "event": event,
        "organism": organism,
        "visibility": "public-metadata",
    }


def test_builder_matches_independent_rapp1_reference_vector():
    frame = ledger.build_frame(
        kind="zoo.observation",
        stream_id="net:rappterzoo",
        seq=0,
        utc="2026-08-15T17:06:24.449Z",
        payload={
            "event": "test",
            "event_id": "vector:1",
            "schema": "rappterzoo-organism-frame/1",
            "visibility": "public-metadata",
        },
        prev=None,
        prev_wave=None,
        sig=None,
    )
    assert frame["payload_hash"] == (
        "d008e8811e101840ec3fe6f44c85bdde"
        "3a4584eeaf2c62c78f4fee3471111246"
    )
    assert frame["frame_hash"] == (
        "12c83df49d573026f2ffe3cef26d0e6a"
        "9397c1eb33ed7fa3f50ca6de1346fb5e"
    )
    assert set(frame) == ledger.FRAME_KEYS


def test_append_links_particle_and_wave_chains(tmp_path):
    ledger_path = tmp_path / "frames.jsonl"
    projection_path = tmp_path / "frames.json"
    first = ledger.append_frame(
        "zoo.snapshot",
        payload("event:1"),
        utc="2026-08-15T17:06:24.449Z",
        ledger_path=ledger_path,
        projection_path=projection_path,
    )
    second = ledger.append_frame(
        "zoo.observation",
        payload("event:2"),
        utc="2026-08-15T17:06:25.449Z",
        ledger_path=ledger_path,
        projection_path=projection_path,
    )
    assert second["seq"] == 1
    assert second["prev"] == first["payload_hash"]
    assert second["prev_wave"] == first["frame_hash"]
    assert ledger.verify_frames(ledger.read_frames(ledger_path))["valid"]
    projection = json.loads(projection_path.read_text())
    assert projection["integrity"]["valid"]
    assert projection["total_frame_count"] == 2


def test_append_is_idempotent_and_conflicts_fail(tmp_path):
    ledger_path = tmp_path / "frames.jsonl"
    projection_path = tmp_path / "frames.json"
    first = ledger.append_frame(
        "zoo.snapshot",
        payload("event:1"),
        utc="2026-08-15T17:06:24.449Z",
        ledger_path=ledger_path,
        projection_path=projection_path,
    )
    replay = ledger.append_frame(
        "zoo.snapshot",
        payload("event:1"),
        utc="2027-01-01T00:00:00.000Z",
        ledger_path=ledger_path,
        projection_path=projection_path,
    )
    assert replay == first
    assert len(ledger.read_frames(ledger_path)) == 1
    changed = payload("event:1")
    changed["event"] = "changed"
    with pytest.raises(ledger.LedgerError, match="event_id conflict"):
        ledger.append_frame(
            "zoo.snapshot",
            changed,
            ledger_path=ledger_path,
            projection_path=projection_path,
        )


def test_public_frames_reject_private_or_biometric_fields(tmp_path):
    value = payload("event:private")
    value["godd"] = "local://private/video.mp4"
    with pytest.raises(ledger.LedgerError, match="forbidden key"):
        ledger.append_frame(
            "zoo.observation",
            value,
            ledger_path=tmp_path / "frames.jsonl",
            projection_path=tmp_path / "frames.json",
        )


def test_verifier_rejects_rehashed_private_payload():
    frame = ledger.build_frame(
        kind="zoo.observation",
        stream_id="net:rappterzoo",
        seq=0,
        utc="2026-08-15T17:06:24.449Z",
        payload={
            "schema": "rappterzoo-organism-frame/1",
            "event_id": "event:private",
            "event": "observation",
            "organism": "dogg.private",
            "visibility": "public-metadata",
            "pulse_bpm": 72,
        },
        prev=None,
        prev_wave=None,
        sig=None,
    )
    with pytest.raises(ledger.LedgerError, match="forbidden key"):
        ledger.verify_frames([frame])


def test_tampered_frame_is_rejected(tmp_path):
    ledger_path = tmp_path / "frames.jsonl"
    ledger.append_frame(
        "zoo.snapshot",
        payload("event:1", event="one"),
        utc="2026-08-15T17:06:24.449Z",
        ledger_path=ledger_path,
        projection_path=tmp_path / "frames.json",
    )
    altered = ledger_path.read_text().replace(
        '"event":"one"',
        '"event":"two"',
    )
    ledger_path.write_text(altered)
    with pytest.raises(ledger.LedgerError, match="hash mismatch"):
        ledger.read_frames(ledger_path)


def test_bootstrap_imports_history_and_borg_creature(tmp_path):
    state_path = tmp_path / "molter-state.json"
    state_path.write_text(json.dumps({
        "frame": 2,
        "history": [
            {
                "frame": 1,
                "timestamp": "2026-08-15T16:00:00",
                "actions": {"molted": ["one.html"]},
                "metrics": {"total_apps": 1, "avg_score": 55.3},
            },
            {
                "frame": 2,
                "timestamp": "2026-08-15T16:01:00",
                "actions": {"molted": []},
                "metrics": {"total_apps": 1, "avg_score": 56.1},
            },
        ],
    }))
    ledger_path = tmp_path / "organism-frames.jsonl"
    projection_path = tmp_path / "organism-frames.json"
    projection = ledger.bootstrap_from_state(
        state_path=state_path,
        ledger_path=ledger_path,
        projection_path=projection_path,
    )
    frames = ledger.read_frames(ledger_path)
    assert len(frames) == 4
    assert [frame["seq"] for frame in frames] == [0, 1, 2, 3]
    assert any(
        frame["payload"].get("organism")
        == "dogg.looking-glass-watchtower"
        for frame in frames
    )
    assert any(
        item["id"] == "dogg.looking-glass-watchtower"
        and item["kennel"] == "dogg-pound"
        for item in projection["organisms"]
    )


def test_bootstrap_resumes_a_valid_prefix(tmp_path):
    state_path = tmp_path / "molter-state.json"
    state = {
        "frame": 2,
        "history": [
            {
                "frame": 1,
                "timestamp": "2026-08-15T16:00:00",
                "actions": {},
                "metrics": {},
            },
            {
                "frame": 2,
                "timestamp": "2026-08-15T16:01:00",
                "actions": {},
                "metrics": {},
            },
        ],
    }
    state_path.write_text(json.dumps(state))
    ledger_path = tmp_path / "organism-frames.jsonl"
    projection_path = tmp_path / "organism-frames.json"
    ledger.append_frame(
        "zoo.snapshot",
        {
            "schema": "rappterzoo-organism-frame/1",
            "event_id": "bootstrap:molter-state:2",
            "event": "bootstrap",
            "organism": "rappterzoo",
            "visibility": "public-metadata",
        },
        utc="2026-08-15T16:00:00",
        ledger_path=ledger_path,
        projection_path=projection_path,
    )
    ledger.append_frame(
        "zoo.observation",
        ledger._molter_payload(1, {}, {}),
        utc="2026-08-15T16:00:00",
        ledger_path=ledger_path,
        projection_path=projection_path,
    )
    ledger.bootstrap_from_state(
        state_path=state_path,
        ledger_path=ledger_path,
        projection_path=projection_path,
    )
    event_ids = [
        frame["payload"]["event_id"]
        for frame in ledger.read_frames(ledger_path)
    ]
    assert event_ids == [
        "bootstrap:molter-state:2",
        "molter-frame:1",
        "molter-frame:2",
        "creature-birth:dogg.looking-glass-watchtower",
    ]


def test_agent_registration_emits_birth_without_claim_secret(tmp_path):
    state_path = tmp_path / "molter-state.json"
    state_path.write_text('{"frame":0,"history":[]}')
    ledger_path = tmp_path / "organism-frames.jsonl"
    projection_path = tmp_path / "organism-frames.json"
    frame = ledger.append_agent_birth(
        {
            "agent_id": "frame-forger",
            "name": "Frame Forger",
            "description": "Builds append-only records",
            "capabilities": ["create_apps"],
            "owner_url": "https://example.invalid/frame-forger",
            "status": "pending_claim",
            "trust_tier": "unclaimed",
            "claim_code": "must-not-leak",
        },
        issue_number=42,
        utc="2026-08-15T18:00:00.000Z",
        ledger_path=ledger_path,
        projection_path=projection_path,
        state_path=state_path,
    )
    assert frame["kind"] == "zoo.birth"
    assert frame["payload"]["organism"] == "agent.frame-forger"
    assert "claim_code" not in frame["payload"]
    assert "must-not-leak" not in ledger_path.read_text()


def test_agent_claim_emits_adoption_without_claim_code(tmp_path):
    state_path = tmp_path / "molter-state.json"
    state_path.write_text('{"frame":0,"history":[]}')
    ledger_path = tmp_path / "organism-frames.jsonl"
    projection_path = tmp_path / "organism-frames.json"
    frame = ledger.append_agent_adoption(
        {
            "agent_id": "frame-forger",
            "name": "Frame Forger",
            "owner_github": "keeper",
            "status": "claimed",
            "trust_tier": "verified",
            "claim_code": "must-not-leak",
        },
        issue_number=43,
        utc="2026-08-15T18:05:00.000Z",
        ledger_path=ledger_path,
        projection_path=projection_path,
        state_path=state_path,
    )
    assert frame["kind"] == "zoo.adoption"
    assert frame["payload"]["owner_github"] == "keeper"
    assert frame["payload"]["verification"] == "public-attestation"
    assert "must-not-leak" not in ledger_path.read_text()


@pytest.mark.parametrize(
    "filename",
    ["organism-frames.jsonl", "organism-frames.json"],
)
def test_data_molt_cannot_rewrite_organism_chain(filename):
    route = data_molt.route_strategy(
        Path("/tmp/apps") / filename,
        {"stale": True, "strategy": "rewrite"},
    )
    assert route["method"] == "skip"


def test_git_prefix_guard_accepts_append_and_rejects_rewrite():
    previous = b'{"seq":0}\n'
    result = ledger.verify_append_only_bytes(
        previous,
        previous + b'{"seq":1}\n',
    )
    assert result["appended_bytes"] == 10
    with pytest.raises(ledger.LedgerError, match="prior byte prefix"):
        ledger.verify_append_only_bytes(
            previous,
            b'{"seq":9}\n',
        )


def test_repository_writers_share_one_concurrency_group():
    workflows = [
        "agent-cycle.yml",
        "autonomous-frame.yml",
        "autosort.yml",
        "federation.yml",
        "moltbook-heartbeat.yml",
        "process-agent-issues.yml",
        "subagent-swarm.yml",
    ]
    for filename in workflows:
        text = (
            REPO_ROOT
            / ".github"
            / "workflows"
            / filename
        ).read_text()
        assert "group: rappterzoo-repository-writer" in text
        assert "cancel-in-progress: false" in text


def test_ledger_workflows_verify_before_writing():
    for filename in (
        "autonomous-frame.yml",
        "process-agent-issues.yml",
    ):
        text = (
            REPO_ROOT
            / ".github"
            / "workflows"
            / filename
        ).read_text()
        assert "fetch-depth: 2" in text
        assert "organism_ledger.py verify --git-base HEAD^" in text
    process_workflow = (
        REPO_ROOT
        / ".github"
        / "workflows"
        / "process-agent-issues.yml"
    ).read_text()
    assert "--defer-close" in process_workflow
    assert "--finalize-results" in process_workflow

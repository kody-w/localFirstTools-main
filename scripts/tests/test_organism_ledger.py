"""Tests for the append-only RappterZoo organism frame ledger."""

import hashlib
import json
import os
import socket
import subprocess
import sys
import time
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


def reference_canonical(value):
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def reference_hash(domain, value):
    return hashlib.sha256(
        domain.encode("ascii") + b"\n" + reference_canonical(value)
    ).hexdigest()


def rehash_frame(frame):
    frame["payload_hash"] = reference_hash(
        "rapp/1:particle",
        frame["payload"],
    )
    wave = {
        key: value
        for key, value in frame.items()
        if key not in {"frame_hash", "sig"}
    }
    frame["frame_hash"] = reference_hash("rapp/1:wave", wave)
    return frame


def frame_pair():
    first = ledger.build_frame(
        "zoo.snapshot",
        ledger.STREAM_ID,
        0,
        "2026-08-15T17:06:24.449Z",
        payload("event:1"),
        None,
        None,
    )
    second = ledger.build_frame(
        "zoo.observation",
        ledger.STREAM_ID,
        1,
        "2026-08-15T17:06:25.449Z",
        payload("event:2"),
        first["payload_hash"],
        first["frame_hash"],
    )
    return [first, second]


def test_builder_matches_independent_rapp1_reference_vector():
    frame = ledger.build_frame(
        kind="zoo.observation",
        stream_id="net:rappterzoo",
        seq=0,
        utc="2026-08-15T17:06:24.449Z",
        payload={
            "event": "test",
            "event_id": "vector:1",
            "organism": "rappterzoo",
            "schema": "rappterzoo-organism-frame/1",
            "visibility": "public-metadata",
        },
        prev=None,
        prev_wave=None,
        sig=None,
    )
    assert frame["payload_hash"] == (
        "bb870ad821672da33a48f7da8d0786e6"
        "2ef93425e5259ad0fae94070cdd05b84"
    )
    assert frame["frame_hash"] == (
        "9ddec8d8bc53e041ee8fbaaa0ee6739b"
        "2e9723d7fa152d4051cac1000d2c91d8"
    )
    assert set(frame) == ledger.FRAME_KEYS
    assert frame["sig"] is None


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
    before = ledger_path.read_bytes()
    projection_path.write_text("{}\n")
    repaired = ledger.append_frame(
        "zoo.snapshot",
        payload("event:1"),
        utc="2030-01-01T00:00:00.000Z",
        ledger_path=ledger_path,
        projection_path=projection_path,
    )
    assert repaired == first
    assert ledger_path.read_bytes() == before
    assert ledger.verify_projection([first], projection_path)["valid"]
    changed = payload("event:1")
    changed["event"] = "changed"
    with pytest.raises(ledger.LedgerError, match="event_id conflict"):
        ledger.append_frame(
            "zoo.snapshot",
            changed,
            ledger_path=ledger_path,
            projection_path=projection_path,
        )


@pytest.mark.parametrize(
    "forbidden_key",
    [
        "godd",
        "faceLandmarks",
        "pulse-bpm",
        "claim_code",
        "privateKey",
        "auth_token",
        "user_password",
        "private_notes",
        "raw_media_url",
        "biometric_template_v2",
    ],
)
def test_public_frames_reject_private_or_biometric_fields(
    tmp_path,
    forbidden_key,
):
    value = payload("event:private")
    value["nested"] = {forbidden_key: "must-not-be-public"}
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
        },
        prev=None,
        prev_wave=None,
        sig=None,
    )
    frame["payload"]["pulse_bpm"] = 72
    rehash_frame(frame)
    with pytest.raises(ledger.LedgerError, match="forbidden key"):
        ledger.verify_frames([frame])


def test_payload_hash_tamper_is_rejected(tmp_path):
    ledger_path = tmp_path / "frames.jsonl"
    ledger.append_frame(
        "zoo.snapshot",
        payload("event:1", event="one"),
        utc="2026-08-15T17:06:24.449Z",
        ledger_path=ledger_path,
        projection_path=tmp_path / "frames.json",
    )
    frame = json.loads(ledger_path.read_text())
    frame["payload_hash"] = "0" * 64
    ledger_path.write_bytes(ledger.canonical_bytes(frame) + b"\n")
    with pytest.raises(ledger.LedgerError, match="payload hash mismatch"):
        ledger.read_frames(ledger_path)


def test_wave_link_tamper_is_rejected_after_rehash():
    frames = frame_pair()
    frames[1]["prev_wave"] = "0" * 64
    rehash_frame(frames[1])
    with pytest.raises(ledger.LedgerError, match="wave chain is broken"):
        ledger.verify_frames(frames)


def test_sig_mutation_cannot_claim_acceptance():
    frame = frame_pair()[0]
    frame["sig"] = "not-a-verified-signature"
    with pytest.raises(ledger.LedgerError, match="sig:null"):
        ledger.verify_frames([frame])


def attention_payload():
    return {
        "schema": "rappterzoo-organism-frame/1",
        "event_id": "attention-evaluation:" + "1" * 64,
        "event": "attention-evaluation",
        "organism": "rappterzoo.attention",
        "visibility": "public-metadata",
        "group_id": "attention:test:s0000of0001:g000000:fixture",
        "shard_id": "attention-shard:0000of0001",
        "scope_key": "test-scope",
        "scope_digest": "6" * 64,
        "base_record_hash": "7" * 64,
        "base_frame_hash": "8" * 64,
        "endpoint_identity_digest": "9" * 64,
        "evaluation_axis": "quality",
        "provenance_digest": "a" * 64,
        "request_digest": "1" * 64,
        "input_digest": "2" * 64,
        "prompt_digest": "3" * 64,
        "policy_digest": "4" * 64,
        "group_object_digest": "5" * 64,
        "group_object_path": "attention/groups/" + "5" * 64 + ".json",
        "total_group_count": 2,
        "candidate_count": 2,
        "candidate_budget": 2,
        "candidate_record_ids": ["comment:1", "comment:2"],
        "attention_budget": 2,
        "selected_count": 2,
        "selected_record_ids": ["comment:1", "comment:2"],
    }


def test_attention_frame_semantics_reject_budget_tamper_after_rehash():
    frame = ledger.build_frame(
        "zoo.attention",
        ledger.STREAM_ID,
        0,
        "2026-08-15T17:06:24.449Z",
        attention_payload(),
        None,
        None,
    )
    frame["payload"]["attention_budget"] = 1
    rehash_frame(frame)
    with pytest.raises(ledger.LedgerError, match="exceeds its budget"):
        ledger.verify_frames([frame])


def test_attention_events_require_their_protocol_kind():
    with pytest.raises(ledger.LedgerError, match="require kind zoo.attention"):
        ledger.build_frame(
            "zoo.observation",
            ledger.STREAM_ID,
            0,
            "2026-08-15T17:06:24.449Z",
            attention_payload(),
            None,
            None,
        )


def test_attention_frame_rejects_selected_non_candidate_after_rehash():
    frame = ledger.build_frame(
        "zoo.attention",
        ledger.STREAM_ID,
        0,
        "2026-08-15T17:06:24.449Z",
        attention_payload(),
        None,
        None,
    )
    frame["payload"]["selected_record_ids"][0] = "comment:outside"
    rehash_frame(frame)
    with pytest.raises(ledger.LedgerError, match="non-candidate"):
        ledger.verify_frames([frame])


def test_duplicate_event_ids_are_rejected_after_full_rehash():
    frames = frame_pair()
    frames[1]["payload"]["event_id"] = frames[0]["payload"]["event_id"]
    rehash_frame(frames[1])
    with pytest.raises(ledger.LedgerError, match="duplicate event_id"):
        ledger.verify_frames(frames)


def test_rollback_timestamp_is_rejected_after_full_rehash():
    frames = frame_pair()
    frames[1]["utc"] = "2026-08-15T17:06:23.449Z"
    rehash_frame(frames[1])
    with pytest.raises(ledger.LedgerError, match="timestamps must be monotonic"):
        ledger.verify_frames(frames)


def test_autonomous_event_numbers_cannot_roll_back():
    frames = frame_pair()
    frames[0]["payload"] = ledger._molter_payload(2, {}, {})
    rehash_frame(frames[0])
    frames[1]["payload"] = ledger._molter_payload(1, {}, {})
    frames[1]["prev"] = frames[0]["payload_hash"]
    frames[1]["prev_wave"] = frames[0]["frame_hash"]
    rehash_frame(frames[1])
    with pytest.raises(ledger.LedgerError, match="strictly increasing"):
        ledger.verify_frames(frames)


def test_restricted_canonical_profile_rejects_binary64_values():
    with pytest.raises(ledger.LedgerError, match="binary64"):
        ledger.canonical_bytes({"score": 55.3})
    generated = ledger._molter_payload(
        1,
        {"ratio": 0.5},
        {"avg_score": 55.3},
    )
    assert generated["actions"]["ratio"] == "0.5"
    assert generated["metrics"]["avg_score"] == "55.3"


@pytest.mark.parametrize(
    "mutation, error",
    [
        (lambda line: b" " + line, "non-canonical"),
        (lambda line: line.replace(b'{"frame_hash"', b'{ "frame_hash"', 1), "non-canonical"),
        (lambda line: line.rstrip(b"\n"), "complete frame boundary"),
    ],
)
def test_malformed_canonical_ledger_bytes_are_rejected(
    tmp_path,
    mutation,
    error,
):
    ledger_path = tmp_path / "frames.jsonl"
    ledger.append_frame(
        "zoo.snapshot",
        payload("canonical:1"),
        utc="2026-08-15T17:06:24.449Z",
        ledger_path=ledger_path,
        projection_path=tmp_path / "frames.json",
    )
    ledger_path.write_bytes(mutation(ledger_path.read_bytes()))
    with pytest.raises(ledger.LedgerError, match=error):
        ledger.read_frames(ledger_path)


def test_active_lock_blocks_and_live_old_lock_never_expires(
    tmp_path,
    monkeypatch,
):
    ledger_path = tmp_path / "frames.jsonl"
    projection_path = tmp_path / "frames.json"
    with ledger._ledger_lock(ledger_path):
        with pytest.raises(ledger.LedgerError, match="already locked"):
            ledger.append_frame(
                "zoo.snapshot",
                payload("locked:1"),
                ledger_path=ledger_path,
                projection_path=projection_path,
            )
    lock_path = ledger_path.with_name(ledger_path.name + ".lock")
    lock_path.write_text(json.dumps({
        "created_utc": "2020-01-01T00:00:00.000Z",
        "hostname": socket.gethostname(),
        "pid": os.getpid(),
        "token": "abandoned",
        "version": 1,
    }))
    stale_time = time.time() - ledger.LOCK_STALE_SECONDS - 10
    os.utime(str(lock_path), (stale_time, stale_time))
    with pytest.raises(ledger.LedgerError, match="already locked"):
        ledger.append_frame(
            "zoo.snapshot",
            payload("locked:1"),
            utc="2026-08-15T17:06:24.449Z",
            ledger_path=ledger_path,
            projection_path=projection_path,
        )
    assert lock_path.exists()
    monkeypatch.setattr(ledger, "_pid_is_alive", lambda _pid: False)
    frame = ledger.append_frame(
        "zoo.snapshot",
        payload("locked:1"),
        utc="2026-08-15T17:06:24.449Z",
        ledger_path=ledger_path,
        projection_path=projection_path,
    )
    assert frame["seq"] == 0
    assert not lock_path.exists()


def test_pending_append_recovers_a_crash_without_rewriting_prefix(tmp_path):
    ledger_path = tmp_path / "frames.jsonl"
    projection_path = tmp_path / "frames.json"
    first, second = frame_pair()
    previous = ledger.canonical_bytes(first) + b"\n"
    appended = ledger.canonical_bytes(second) + b"\n"
    ledger_path.write_bytes(previous)
    ledger._write_pending_append(ledger_path, previous, appended)
    ledger_path.write_bytes(previous + appended[: len(appended) // 2])
    recovered = ledger.append_frame(
        "zoo.observation",
        payload("event:2"),
        utc="2030-01-01T00:00:00.000Z",
        ledger_path=ledger_path,
        projection_path=projection_path,
    )
    assert recovered == second
    assert ledger_path.read_bytes() == previous + appended
    assert not ledger._pending_path(ledger_path).exists()
    assert ledger.verify_projection([first, second], projection_path)["valid"]


def test_failed_bootstrap_preflight_never_writes_a_partial_ledger(tmp_path):
    state_path = tmp_path / "molter-state.json"
    state_path.write_text(json.dumps({
        "frame": 2,
        "history": [
            {
                "frame": 1,
                "timestamp": "2026-08-15T16:01:00Z",
                "actions": {},
                "metrics": {},
            },
            {
                "frame": 2,
                "timestamp": "2026-08-15T16:00:00Z",
                "actions": {},
                "metrics": {},
            },
        ],
    }))
    ledger_path = tmp_path / "organism-frames.jsonl"
    projection_path = tmp_path / "organism-frames.json"
    with pytest.raises(ledger.LedgerError, match="timestamps must be monotonic"):
        ledger.bootstrap_from_state(
            state_path=state_path,
            ledger_path=ledger_path,
            projection_path=projection_path,
        )
    assert not ledger_path.exists()
    assert not projection_path.exists()


def test_projection_tail_has_pagination_anchors_and_stable_layout(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(ledger, "PROJECTION_LIMIT", 2)
    ledger_path = tmp_path / "frames.jsonl"
    projection_path = tmp_path / "frames.json"
    for index in range(4):
        ledger.append_frame(
            "zoo.observation",
            payload("projection:{}".format(index)),
            utc="2026-08-15T17:06:{:02d}.449Z".format(24 + index),
            ledger_path=ledger_path,
            projection_path=projection_path,
        )
    frames = ledger.read_frames(ledger_path)
    projection = json.loads(projection_path.read_text())
    assert [frame["seq"] for frame in projection["frames"]] == [2, 3]
    assert projection["pagination"] == {
        "mode": "bounded-tail",
        "order": "seq-ascending",
        "limit": 2,
        "start_seq": 2,
        "end_seq": 3,
        "has_older": True,
        "older_before_seq": 2,
        "has_newer": False,
    }
    assert projection["segment"]["first_prev"] == frames[1]["payload_hash"]
    assert projection["segment"]["first_prev_wave"] == frames[1]["frame_hash"]
    assert projection["segment"]["head_frame_hash"] == frames[3]["frame_hash"]
    assert projection["rapp1"]["acceptance"] == "structural-unverified"
    assert projection["rapp1"]["canonicalization"]["binary64"] == "forbidden"
    seed = projection["organisms"][0]["layout_seed"]
    assert len(seed) == 64
    first_bytes = projection_path.read_bytes()
    ledger.write_projection(frames, projection_path)
    assert projection_path.read_bytes() == first_bytes


def test_git_guard_rejects_a_structurally_valid_prefix_rewrite(tmp_path):
    root = tmp_path / "repo"
    apps = root / "apps"
    apps.mkdir(parents=True)
    ledger_path = apps / "organism-frames.jsonl"
    projection_path = apps / "organism-frames.json"
    first = frame_pair()[0]
    ledger_path.write_bytes(ledger.canonical_bytes(first) + b"\n")
    subprocess.run(["git", "init", "-q"], cwd=str(root), check=True)
    subprocess.run(
        ["git", "config", "user.email", "ledger@example.invalid"],
        cwd=str(root),
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Ledger Test"],
        cwd=str(root),
        check=True,
    )
    subprocess.run(
        ["git", "add", "apps/organism-frames.jsonl"],
        cwd=str(root),
        check=True,
    )
    subprocess.run(
        ["git", "-c", "commit.gpgsign=false", "commit", "-qm", "ledger base"],
        cwd=str(root),
        check=True,
    )
    ledger.append_frame(
        "zoo.observation",
        payload("event:2"),
        utc="2026-08-15T17:06:25.449Z",
        ledger_path=ledger_path,
        projection_path=projection_path,
    )
    assert ledger.verify_git_append_only(
        "HEAD",
        root=root,
        ledger_path=ledger_path,
    )["checked"]
    replacement = ledger.build_frame(
        "zoo.snapshot",
        ledger.STREAM_ID,
        0,
        "2026-08-15T17:06:24.449Z",
        payload("replacement:1"),
        None,
        None,
    )
    ledger_path.write_bytes(ledger.canonical_bytes(replacement) + b"\n")
    with pytest.raises(ledger.LedgerError, match="prior byte prefix"):
        ledger.verify_git_append_only(
            "HEAD",
            root=root,
            ledger_path=ledger_path,
        )


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


def test_committed_ledger_passes_independent_structural_contract():
    ledger_path = REPO_ROOT / "apps" / "organism-frames.jsonl"
    projection_path = REPO_ROOT / "apps" / "organism-frames.json"
    raw = ledger_path.read_bytes()
    assert raw.endswith(b"\n")
    lines = raw.split(b"\n")[:-1]
    previous = None
    event_ids = set()
    frames = []
    for index, line in enumerate(lines):
        frame = json.loads(line.decode("utf-8"))
        assert set(frame) == {
            "spec",
            "kind",
            "stream_id",
            "seq",
            "utc",
            "payload",
            "payload_hash",
            "frame_hash",
            "prev",
            "prev_wave",
            "sig",
        }
        assert line == reference_canonical(frame)
        assert frame["spec"] == "rapp/1"
        assert frame["stream_id"] == "net:rappterzoo"
        assert frame["seq"] == index
        assert frame["sig"] is None
        assert frame["payload"]["schema"] == "rappterzoo-organism-frame/1"
        assert frame["payload"]["visibility"] == "public-metadata"
        event_id = frame["payload"]["event_id"]
        assert event_id not in event_ids
        event_ids.add(event_id)
        assert frame["payload_hash"] == reference_hash(
            "rapp/1:particle",
            frame["payload"],
        )
        wave = {
            key: value
            for key, value in frame.items()
            if key not in {"frame_hash", "sig"}
        }
        assert frame["frame_hash"] == reference_hash("rapp/1:wave", wave)
        if previous is None:
            assert frame["prev"] is None
            assert frame["prev_wave"] is None
        else:
            assert frame["utc"] >= previous["utc"]
            assert frame["prev"] == previous["payload_hash"]
            assert frame["prev_wave"] == previous["frame_hash"]
        previous = frame
        frames.append(frame)
    assert json.loads(projection_path.read_text()) == ledger.projection_value(frames)
    assert projection_path.read_bytes() == ledger._pretty_json_bytes(
        json.loads(projection_path.read_text())
    )


def write_frame_file(path, frames):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"".join(
        ledger.canonical_bytes(frame) + b"\n"
        for frame in frames
    ))


def test_subscriber_replica_checkpoint_and_witness_are_truthful(tmp_path):
    source = tmp_path / "publisher.jsonl"
    replica = tmp_path / "subscriber" / "replica.jsonl"
    checkpoint = tmp_path / "subscriber" / "checkpoint.json"
    witnesses = tmp_path / "subscriber" / "witnesses"
    write_frame_file(source, frame_pair())
    result = ledger.replicate_subscriber_chain(
        source,
        replica,
        checkpoint,
        "subscriber-alpha",
        publisher_git_commit="a" * 40,
    )
    assert result["appended_frames"] == 2
    assert replica.read_bytes() == source.read_bytes()
    claims = result["checkpoint"]["claims"]
    assert claims["single_subscriber"] == "one-independent-local-replica"
    assert claims["publisher_authority"] == "centralized"
    assert claims["consensus"] == "none"
    assert claims["mining"] == "none"
    assert claims["token"] == "none"
    witness = ledger.emit_subscriber_witness(
        replica,
        checkpoint,
        witnesses,
        "2026-08-15T18:00:00.000Z",
    )
    assert witness["witness"]["head"]["frame_hash"] == frame_pair()[-1][
        "frame_hash"
    ]
    assert witness["witness"]["attestation"] == (
        "independent-structural-witness-unverified"
    )
    assert witness["path"].name == (
        witness["witness"]["witness_digest"] + ".json"
    )


def test_subscriber_accepts_only_appended_delta_and_chains_witness(tmp_path):
    source = tmp_path / "publisher.jsonl"
    replica = tmp_path / "subscriber" / "replica.jsonl"
    checkpoint = tmp_path / "subscriber" / "checkpoint.json"
    witnesses = tmp_path / "subscriber" / "witnesses"
    first, second = frame_pair()
    write_frame_file(source, [first])
    initial = ledger.replicate_subscriber_chain(
        source,
        replica,
        checkpoint,
        "subscriber-alpha",
    )
    first_witness = ledger.emit_subscriber_witness(
        replica,
        checkpoint,
        witnesses,
        "2026-08-15T18:00:00.000Z",
    )
    write_frame_file(source, [first, second])
    updated = ledger.replicate_subscriber_chain(
        source,
        replica,
        checkpoint,
        "subscriber-alpha",
    )
    assert updated["appended_frames"] == 1
    assert updated["checkpoint"]["previous_checkpoint_digest"] == initial[
        "checkpoint"
    ]["checkpoint_digest"]
    second_witness = ledger.emit_subscriber_witness(
        replica,
        checkpoint,
        witnesses,
        "2026-08-15T18:01:00.000Z",
        previous_witness_digest=first_witness["witness"][
            "witness_digest"
        ],
    )
    assert second_witness["witness"]["accepted_delta_count"] == 1
    assert second_witness["witness"]["previous_witness_digest"] == (
        first_witness["witness"]["witness_digest"]
    )


def test_subscriber_detects_publisher_fork_without_reset(tmp_path):
    source = tmp_path / "publisher.jsonl"
    replica = tmp_path / "subscriber" / "replica.jsonl"
    checkpoint = tmp_path / "subscriber" / "checkpoint.json"
    evidence_dir = tmp_path / "subscriber" / "fork-evidence"
    write_frame_file(source, frame_pair())
    ledger.replicate_subscriber_chain(
        source,
        replica,
        checkpoint,
        "subscriber-alpha",
    )
    replica_before = replica.read_bytes()
    checkpoint_before = checkpoint.read_bytes()
    replacement = ledger.build_frame(
        "zoo.snapshot",
        ledger.STREAM_ID,
        0,
        "2026-08-15T17:06:24.449Z",
        payload("replacement:fork"),
        None,
        None,
    )
    write_frame_file(source, [replacement])
    with pytest.raises(ledger.ForkError) as captured:
        ledger.replicate_subscriber_chain(
            source,
            replica,
            checkpoint,
            "subscriber-alpha",
            evidence_dir=evidence_dir,
        )
    assert captured.value.evidence["classification"] == (
        "explicit-prefix-fork-or-drift"
    )
    assert replica.read_bytes() == replica_before
    assert checkpoint.read_bytes() == checkpoint_before
    assert list(evidence_dir.glob("*.json"))


def test_multiple_subscribers_decentralize_custody_not_authority(tmp_path):
    source = tmp_path / "publisher.jsonl"
    write_frame_file(source, frame_pair())
    receipts = []
    replicas = []
    for subscriber in ("alpha", "beta"):
        directory = tmp_path / subscriber
        replica = directory / "replica.jsonl"
        checkpoint = directory / "checkpoint.json"
        ledger.replicate_subscriber_chain(
            source,
            replica,
            checkpoint,
            "subscriber-" + subscriber,
        )
        receipts.append(ledger.emit_subscriber_witness(
            replica,
            checkpoint,
            directory / "witnesses",
            "2026-08-15T18:00:00.000Z",
        )["witness"])
        replicas.append(replica.read_bytes())
    assert replicas[0] == replicas[1] == source.read_bytes()
    assert receipts[0]["subscriber_id_digest"] != receipts[1][
        "subscriber_id_digest"
    ]
    assert all(
        receipt["claims"]["multiple_subscribers"]
        == "independent-custody-and-verification-if-separately-controlled"
        and receipt["claims"]["publisher_authority"] == "centralized"
        and receipt["claims"]["witness_quorum"] == "not-established"
        for receipt in receipts
    )


@pytest.mark.parametrize(
    "filename",
    ["organism-frames.jsonl", "organism-frames.json"],
)
def test_data_molt_cannot_rewrite_organism_chain(filename):
    route = data_molt.route_strategy(
        Path("apps") / filename,
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


def test_repository_writers_use_non_dropping_remote_lock():
    workflows = [
        "agent-cycle.yml",
        "autonomous-frame.yml",
        "autosort.yml",
        "federation.yml",
        "moltbook-heartbeat.yml",
        "process-agent-issues.yml",
        "subagent-swarm.yml",
        "syndication.yml",
    ]
    for filename in workflows:
        text = (
            REPO_ROOT
            / ".github"
            / "workflows"
            / filename
        ).read_text()
        assert "repository_lock.py acquire" in text
        assert "repository_lock.py release" in text
        assert "actions: read" in text
        assert "group: rappterzoo-repository-writer" not in text

    gate = (
        REPO_ROOT
        / ".github"
        / "workflows"
        / "moonshot-gate.yml"
    ).read_text()
    assert "group: moonshot-gate-" in gate
    assert "cancel-in-progress: true" in gate


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

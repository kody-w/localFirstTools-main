"""Tests for the recursive scene compiled from one real organism hash."""

import copy
import importlib.util
import json
import shutil
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import looking_glass_hash as glass
import organism_ledger


def test_target_is_real_watchtower_birth_frame():
    scene = glass.build_scene(ROOT)
    assert scene["generated_from"] == {
        "event_id": glass.TARGET_EVENT_ID,
        "frame_hash": glass.TARGET_FRAME_HASH,
        "payload_hash": (
            "db9ee87c4df83e53a38c06af392a7ea"
            "2462b400f9b13be4e4b11d21d484a283a"
        ),
        "seq": 51,
        "stream_id": "net:rappterzoo",
        "utc": "2026-08-15T17:06:24.449Z",
    }
    assert scene["target_frame"]["payload"]["organism"] == (
        "dogg.looking-glass-watchtower"
    )


def test_scene_has_exact_seven_dimension_cycle():
    scene = glass.build_scene(ROOT)
    assert [item["id"] for item in scene["dimensions"]] == (
        glass.DIMENSION_IDS
    )
    assert scene["recursion"]["cycle"] == glass.DIMENSION_IDS
    assert len(scene["recursion"]["hash_bytes"]) == 32
    assert scene["integrity"]["dimension_count"] == 7


def test_absent_attention_and_mutation_are_not_overclaimed():
    scene = glass.build_scene(ROOT)
    dimensions = {
        item["id"]: item
        for item in scene["dimensions"]
    }
    assert dimensions["attention"]["status"] == (
        "contract-visible-not-observed"
    )
    assert dimensions["attention"]["facts"]["direct_object_count"] == 0
    assert dimensions["mutation"]["status"] == (
        "immutable-no-direct-mutation"
    )
    assert dimensions["mutation"]["facts"]["direct_frame_count"] == 0


def test_scene_is_bound_to_real_syndication_delta():
    scene = glass.build_scene(ROOT)
    dimension = next(
        item
        for item in scene["dimensions"]
        if item["id"] == "syndication"
    )
    assert dimension["facts"]["containing_delta"] == (
        "593525f4b7c858ef4f1d2882e52ad5ba"
        "92510dee569f7b4ffce768556114a45b"
    )
    assert dimension["facts"]["containing_delta_sequence"] == 0
    assert dimension["facts"]["containing_delta_profile"] == "legacy"


def test_scene_build_is_byte_deterministic(tmp_path):
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    glass.write_scene(ROOT, first)
    glass.write_scene(ROOT, second)
    assert first.read_bytes() == second.read_bytes()


def test_existing_scene_fails_closed_when_mutable_sources_drift(tmp_path):
    root = tmp_path / "repo"
    (root / "apps" / "looking-glass").mkdir(parents=True)
    for relative in (
        "apps/organism-frames.jsonl",
        "apps/organism-frames.json",
        "apps/manifest.json",
        "apps/attention/policy.json",
        "apps/attention/prompt-contract.json",
        "apps/attention/frame-control.json",
        "apps/syndication/index.json",
        "index.html",
    ):
        source = ROOT / relative
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    shutil.copytree(
        ROOT / "apps" / "syndication" / "deltas",
        root / "apps" / "syndication" / "deltas",
    )
    glass.write_scene(root)
    policy_path = root / "apps" / "attention" / "policy.json"
    policy = json.loads(policy_path.read_text())
    policy["candidate_budget"] += 1
    policy_path.write_text(json.dumps(policy, indent=2) + "\n")
    with pytest.raises(
        glass.LookingGlassError,
        match="source drift detected",
    ):
        glass.write_scene(root)


def test_scene_verifier_rejects_mutated_frame_or_digest():
    scene = glass.build_scene(ROOT)
    mutated = copy.deepcopy(scene)
    mutated["target_frame"]["payload"]["display_name"] = "Forged"
    with pytest.raises(glass.LookingGlassError, match="stale or mutated"):
        glass.verify_scene(mutated, ROOT)
    mutated = copy.deepcopy(scene)
    mutated["integrity"]["scene_digest"] = "0" * 64
    with pytest.raises(glass.LookingGlassError, match="scene digest mismatch"):
        glass.verify_scene(mutated, ROOT)


def test_scene_has_zero_nonpublic_records_and_no_forbidden_keys():
    scene = glass.build_scene(ROOT)
    assert scene["privacy_proof"]["zero_nonpublic_records"] is True
    assert scene["privacy_proof"]["forbidden_key_hits"] == []
    assert organism_ledger._find_forbidden_key(scene) is None


def test_portal_release_is_idempotent_in_isolated_tree(tmp_path):
    root = tmp_path / "repo"
    (root / "apps" / "looking-glass").mkdir(parents=True)
    (root / "apps" / "syndication").mkdir(parents=True)
    (root / "apps" / "attention").mkdir(parents=True)
    for relative in (
        "apps/organism-frames.jsonl",
        "apps/organism-frames.json",
        "apps/manifest.json",
        "apps/attention/policy.json",
        "apps/attention/prompt-contract.json",
        "apps/attention/frame-control.json",
        "apps/syndication/index.json",
        "index.html",
    ):
        source = ROOT / relative
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    shutil.copytree(
        ROOT / "apps" / "syndication" / "deltas",
        root / "apps" / "syndication" / "deltas",
    )
    manifest = json.loads((root / "apps" / "manifest.json").read_text())
    category = manifest["categories"]["3d_immersive"]
    if not any(
        item.get("file") == glass.APP_FILE
        for item in category["apps"]
    ):
        category["apps"].insert(0, copy.deepcopy(glass.APP_METADATA))
        category["count"] = len(category["apps"])
    (root / "apps" / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n"
    )
    glass.write_scene(root)
    first = glass.append_portal_frame(
        root,
        utc="2026-08-15T20:51:02.781Z",
    )
    second = glass.append_portal_frame(
        root,
        utc="2027-01-01T00:00:00.000Z",
    )
    assert first == second
    frames = organism_ledger.read_frames(
        root / "apps" / "organism-frames.jsonl"
    )
    matches = [
        frame
        for frame in frames
        if frame["payload"]["event_id"]
        == "experience-birth:looking-glass-inside-one-hash"
    ]
    assert len(matches) == 1


def test_app_security_theme_and_data_contract():
    path = ROOT / glass.APP_PATH
    assert path.is_file()
    html = path.read_text(encoding="utf-8")
    assert "Looking Glass: Inside One Hash" in html
    assert "../looking-glass/hash-scene.json" in html
    assert glass.TARGET_FRAME_HASH in html
    assert "rappterzoo:category\" content=\"3d_immersive" in html
    assert "Content-Security-Policy" in html
    assert "new Function" not in html
    assert "document.write" not in html
    assert "eval(" not in html
    assert "--cp-accent" in html
    first_script = html.index("<script>")
    detector = html.index(
        'const param = new URLSearchParams(window.location.search)'
    )
    assert first_script < detector

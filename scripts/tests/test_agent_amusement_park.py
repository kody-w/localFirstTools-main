"""Tests for the local-first amusement park built for AI agents."""

import copy
import json
import shutil
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import agent_amusement_park as park
import organism_ledger


def test_bundle_builds_seven_nights_from_real_anchor():
    state, events, contract = park.build_bundle(ROOT)
    assert state["anchor"]["frame_hash"] == park.ANCHOR_FRAME_HASH
    assert state["anchor"]["seq"] == 51
    assert state["night_count"] == 7
    assert len(state["nights"]) == 7
    assert len(events) == state["event_ledger"]["event_count"]
    assert contract["park_id"] == park.PARK_ID


def test_event_ledger_is_append_only_and_content_addressed():
    _state, events, _contract = park.build_bundle(ROOT)
    result = park.verify_events(events)
    assert result["event_count"] == len(events)
    assert result["head"] == events[-1]["event_hash"]
    assert [event["seq"] for event in events] == list(range(len(events)))
    assert events[0]["prev"] is None
    assert all(
        events[index]["prev"] == events[index - 1]["event_hash"]
        for index in range(1, len(events))
    )


def test_synthetic_economy_balances_and_pays_royalties():
    state, events, contract = park.build_bundle(ROOT)
    assert state["economy"]["real_money"] is False
    assert state["economy"]["balanced"] is True
    assert state["economy"]["total_debits"] == (
        state["economy"]["total_credits"]
    )
    assert sum(park.ROYALTY_BPS.values()) == 10000
    assert contract["economy"] == {
        "currency": "synthetic-credit",
        "payment_claim": "simulation-only",
        "real_money": False,
        "tradable_asset_or_mining_claim": False,
    }
    settlement_events = [
        event
        for event in events
        if event["kind"] == "park.royalty-settlement"
    ]
    assert len(settlement_events) == 7
    assert all(
        event["payload"]["royalty_credits"] > 0
        for event in settlement_events
    )
    escrow_accounts = {
        name: totals
        for name, totals in state["economy"]["accounts"].items()
        if name.startswith("escrow.")
    }
    assert escrow_accounts
    assert all(
        totals["credits"] == totals["debits"]
        for totals in escrow_accounts.values()
    )


def test_resource_negotiation_is_bounded_and_contended():
    state, events, _contract = park.build_bundle(ROOT)
    resource_events = [
        event
        for event in events
        if event["kind"] == "park.resource-negotiation"
    ]
    assert len(resource_events) == 7
    contention_seen = False
    for event in resource_events:
        payload = event["payload"]
        for resource, capacity in park.RESOURCE_CAPACITY.items():
            requested = sum(
                bid["requested"][resource]
                for bid in payload["bids"]
            )
            allocated = sum(
                allocation[resource]
                for allocation in payload["allocations"].values()
            )
            assert allocated <= capacity
            if requested > capacity and allocated < requested:
                contention_seen = True
    assert contention_seen is True
    assert state["resource_capacity"] == park.RESOURCE_CAPACITY


def test_park_invents_retires_and_evolves_every_night():
    state, _events, _contract = park.build_bundle(ROOT)
    inventions = state["evolution"]["inventions"]
    retirements = state["evolution"]["retirements"]
    evolutions = state["evolution"]["nightly_mutations"]
    assert [item["attraction"]["id"] for item in inventions] == [
        "fold-at-home-ferris-wheel",
        "append-only-memory-maze",
    ]
    assert retirements == [{
        "attraction_id": "static-queue",
        "night": 2,
        "reason": "two-consecutive-low-signal-nights",
    }]
    assert len(evolutions) == 7
    assert len({item["attraction_id"] for item in evolutions}) >= 5


def test_customer_retains_all_authority_controls():
    state, _events, contract = park.build_bundle(ROOT)
    expected = {
        "canonical_mutation": "customer-approved-release-only",
        "customer_can_export_full_ledger": True,
        "customer_can_select_model_route": True,
        "customer_can_shutdown_immediately": True,
        "customer_holds_runtime_keys": True,
        "park_or_vendor_remote_shutdown": False,
    }
    assert state["control_tower"] == expected
    assert contract["control_boundary"] == expected
    assert contract["write_default"] == "local-branch-only"
    assert all(
        action["canonical_write"] is False
        for action in contract["agent_actions"].values()
    )


def test_bundle_is_byte_deterministic(tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    park.write_bundle(ROOT, first)
    park.write_bundle(ROOT, second)
    for name in ("park-state.json", "events.jsonl", "agent-contract.json"):
        assert (first / name).read_bytes() == (second / name).read_bytes()


def test_public_bundle_contains_no_forbidden_keys():
    state, events, contract = park.build_bundle(ROOT)
    assert organism_ledger._find_forbidden_key(state) is None
    assert organism_ledger._find_forbidden_key(contract) is None
    assert all(
        organism_ledger._find_forbidden_key(event) is None
        for event in events
    )


def test_verifier_rejects_mutated_history():
    state, events, contract = park.build_bundle(ROOT)
    mutated = copy.deepcopy(events)
    mutated[3]["payload"]["night"] = 99
    with pytest.raises(park.ParkError, match="payload hash mismatch"):
        park.verify_events(mutated)
    mutated_state = copy.deepcopy(state)
    mutated_state["economy"]["real_money"] = True
    with pytest.raises(park.ParkError, match="state projection"):
        park.verify_bundle(mutated_state, events, contract, ROOT)


def test_release_is_idempotent_in_isolated_tree(tmp_path):
    root = tmp_path / "repo"
    (root / "apps").mkdir(parents=True)
    for relative in (
        "apps/organism-frames.jsonl",
        "apps/organism-frames.json",
        "apps/manifest.json",
    ):
        source = ROOT / relative
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    manifest = json.loads((root / "apps" / "manifest.json").read_text())
    category = manifest["categories"]["3d_immersive"]
    if not any(
        item.get("file") == park.APP_FILE
        for item in category["apps"]
    ):
        category["apps"].insert(0, copy.deepcopy(park.APP_METADATA))
        category["count"] = len(category["apps"])
    (root / "apps" / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n"
    )
    park.write_bundle(root)
    first = park.append_park_frame(
        root,
        utc="2026-08-16T01:12:00.000Z",
    )
    second = park.append_park_frame(
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
        == "experience-birth:agent-amusement-park"
    ]
    assert len(matches) == 1


def test_discovery_surfaces_publish_the_agent_park():
    manifest = json.loads((ROOT / "apps" / "manifest.json").read_text())
    category = manifest["categories"]["3d_immersive"]
    assert category["count"] == len(category["apps"])
    assert any(
        item.get("file") == park.APP_FILE
        for item in category["apps"]
    )
    feed = json.loads((ROOT / "apps" / "feed.json").read_text())
    feed_urls = {
        item["item"]["url"]
        for item in feed["dataFeedElement"]
    }
    assert park.APP_URL in feed_urls
    mcp = json.loads((ROOT / ".well-known" / "mcp.json").read_text())
    resource_names = {item["name"] for item in mcp["resources"]}
    assert {
        "agent_amusement_park",
        "agent_park_contract",
        "agent_park_event_ledger",
        "agent_park_guide",
        "agent_park_state",
    }.issubset(resource_names)
    protocol = json.loads(
        (ROOT / ".well-known" / "agent-protocol").read_text()
    )
    assert protocol["agent_amusement_park"]["economy"] == (
        "synthetic-credit-only"
    )
    assert protocol["mcp_stdio"]["agent_park_prompt"] == (
        "agent_amusement_park_first_visit"
    )


def test_app_security_theme_and_agent_first_contract():
    path = ROOT / park.APP_PATH
    assert path.is_file()
    html = path.read_text(encoding="utf-8")
    assert "Agent Amusement Park" in html
    assert "../agent-park/park-state.json" in html
    assert "../agent-park/events.jsonl" in html
    assert "../organism-frames.json" in html
    assert "Emergency stop" in html
    assert "synthetic" in html.lower()
    assert "time travel" in html.lower()
    assert "Content-Security-Policy" in html
    assert "--cp-accent" in html
    assert "eval(" not in html
    assert "new Function" not in html
    assert "document.write" not in html
    first_script = html.index("<script>")
    detector = html.index(
        'const param = new URLSearchParams(window.location.search)'
    )
    assert first_script < detector

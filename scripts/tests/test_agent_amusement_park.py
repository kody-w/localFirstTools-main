"""Tests for the local-first amusement park built for AI agents."""

import copy
import hashlib
import json
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import agent_amusement_park as park
import organism_ledger


EXPECTED_COMBINED_EVENT_SHA256 = (
    "bfefe99e73fd89bc4f435dd3dfd9c4a5b784788017e406a79fe92194273351bf"
)
EXPECTED_SEASON_TWO_HEAD = (
    "a7cf7ce7e18c97c4099bd01edb47211b9cf2c53ddd968d76f9d626d412a29ed9"
)
EXPECTED_STATE_DIGEST = (
    "b3782eaaec8b4a647107c6a9e3b0b146e7beb9a0135f92673c8f9644ba32ce6e"
)


def _rehash_event_chain(events, start=park.SEASON_ONE_EVENT_COUNT):
    previous = events[start - 1]["event_hash"] if start else None
    for index in range(start, len(events)):
        event = events[index]
        event["seq"] = index
        event["prev"] = previous
        if event["schema"] == park.EVENT_SCHEMA_V1:
            payload_domain = park.PAYLOAD_HASH_DOMAIN_V1
            event_domain = park.EVENT_HASH_DOMAIN_V1
        else:
            payload_domain = park.PAYLOAD_HASH_DOMAIN
            event_domain = park.EVENT_HASH_DOMAIN
            event["season"] = park.SEASON_TWO
            event["season_seq"] = index - park.SEASON_ONE_EVENT_COUNT
        event["payload_hash"] = park._canonical_digest(
            payload_domain,
            event["payload"],
        )
        projected = {
            key: copy.deepcopy(value)
            for key, value in event.items()
            if key != "event_hash"
        }
        event["event_hash"] = park._canonical_digest(
            event_domain,
            projected,
        )
        previous = event["event_hash"]


def _rebind_bundle(state, events, contract):
    event_bytes = park._event_bytes(events)
    state["event_ledger"]["event_count"] = len(events)
    state["event_ledger"]["head"] = events[-1]["event_hash"]
    state["event_ledger"]["sha256"] = hashlib.sha256(
        event_bytes
    ).hexdigest()
    state["integrity"]["state_digest"] = park._canonical_digest(
        park.STATE_HASH_DOMAIN,
        park._state_without_digest(state),
    )
    contract["integrity"]["contract_digest"] = park._canonical_digest(
        park.CONTRACT_HASH_DOMAIN,
        park._contract_without_digest(contract),
    )
    bundle_digest = park._bundle_digest(
        len(events),
        events[-1]["event_hash"],
        state["event_ledger"]["sha256"],
        state["integrity"]["state_digest"],
        contract["integrity"]["contract_digest"],
    )
    state["integrity"]["bundle_digest"] = bundle_digest
    contract["integrity"]["bundle_digest"] = bundle_digest


def test_bundle_builds_seven_nights_from_real_anchor():
    state, events, contract = park.build_bundle(ROOT)
    assert state["anchor"]["frame_hash"] == park.ANCHOR_FRAME_HASH
    assert state["anchor"]["seq"] == 51
    assert state["night_count"] == 7
    assert len(state["nights"]) == 7
    assert state["latest_season"] == park.SEASON_TWO
    assert state["agent_contract"] == "agent-contract-v2.json"
    assert len(events) == park.SEASON_ONE_EVENT_COUNT * 2
    assert len(events) == state["event_ledger"]["event_count"]
    assert events[park.SEASON_ONE_EVENT_COUNT - 1]["event_hash"] == (
        park.SEASON_ONE_HEAD
    )
    assert events[park.SEASON_ONE_EVENT_COUNT]["prev"] == (
        park.SEASON_ONE_HEAD
    )
    assert contract["park_id"] == park.PARK_ID
    assert contract["schema"] == park.CONTRACT_SCHEMA


def test_published_season_one_prefix_and_v1_contract_are_byte_exact():
    event_bytes = park.EVENTS_PATH.read_bytes()
    event_lines = event_bytes.splitlines(keepends=True)
    assert hashlib.sha256(event_bytes).hexdigest() == (
        EXPECTED_COMBINED_EVENT_SHA256
    )
    assert len(event_lines) == 94
    prefix = b"".join(event_lines[:park.SEASON_ONE_EVENT_COUNT])
    assert hashlib.sha256(prefix).hexdigest() == (
        park.SEASON_ONE_PREFIX_SHA256
    )
    prefix_events = [
        json.loads(line.decode("utf-8"))
        for line in event_lines[:park.SEASON_ONE_EVENT_COUNT]
    ]
    assert len(prefix_events) == 47
    assert prefix_events[-1]["event_hash"] == park.SEASON_ONE_HEAD
    assert json.loads(event_lines[-1])["event_hash"] == (
        EXPECTED_SEASON_TWO_HEAD
    )
    assert all("season" not in event for event in prefix_events)
    legacy_contract = park.LEGACY_CONTRACT_PATH.read_bytes()
    assert hashlib.sha256(legacy_contract).hexdigest() == (
        park.LEGACY_CONTRACT_SHA256
    )
    assert len(legacy_contract) == 1814


def test_event_ledger_is_append_only_and_content_addressed():
    _state, events, _contract = park.build_bundle(ROOT)
    result = park.verify_events(events)
    assert result["event_count"] == len(events)
    assert result["head"] == events[-1]["event_hash"]
    assert result["season_one_event_count"] == 47
    assert result["season_two_event_count"] == 47
    assert [event["seq"] for event in events] == list(range(len(events)))
    assert events[0]["prev"] is None
    assert all(
        events[index]["prev"] == events[index - 1]["event_hash"]
        for index in range(1, len(events))
    )
    assert park._event_bytes(
        events[:park.SEASON_ONE_EVENT_COUNT]
    ) == park._season_one_prefix_bytes(park.EVENTS_PATH)
    season_two = events[park.SEASON_ONE_EVENT_COUNT:]
    assert all(event["season"] == park.SEASON_TWO for event in season_two)
    assert [event["season_seq"] for event in season_two] == list(
        range(len(season_two))
    )
    parsed = [
        datetime.strptime(
            event["utc"],
            "%Y-%m-%dT%H:%M:%S.%fZ",
        ).replace(tzinfo=timezone.utc)
        for event in events
    ]
    assert all(
        parsed[index] > parsed[index - 1]
        for index in range(1, len(parsed))
    )

    original_hashes = [event["event_hash"] for event in events]
    appended = copy.deepcopy(events)
    park._append_event(
        appended,
        "park.future-checkpoint",
        {
            "night": 8,
            "purpose": "appendability-proof",
            "season": park.SEASON_TWO,
        },
        "2026-08-30T00:00:00.000Z",
    )
    appended_result = park.verify_events(appended)
    assert [event["event_hash"] for event in appended[:-1]] == (
        original_hashes
    )
    assert appended[-1]["seq"] == len(events)
    assert appended[-1]["season_seq"] == len(season_two)
    assert appended[-1]["prev"] == original_hashes[-1]
    assert appended_result["event_count"] == len(events) + 1


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
        if (
            park._event_season(event) == park.SEASON_TWO
            and event["kind"] == "park.royalty-settlement"
        )
    ]
    assert len(settlement_events) == 7
    assert all(
        event["payload"]["royalty_credits"] > 0
        for event in settlement_events
    )
    assert park._split_royalty(1) == {
        "creator": 1,
        "customer_reserve": 0,
        "open_protocol": 0,
        "park_operations": 0,
        "resource_pool": 0,
    }
    for event in settlement_events:
        payload = event["payload"]
        assert payload["basis_points"] == park.ROYALTY_BPS
        assert payload["rounding_policy"] == "largest-remainder/1"
        admissions = {
            posting["ride_id"]: posting["amount"]
            for posting in payload["postings"]
            if posting["kind"] == "synthetic-admission"
        }
        royalty_postings = [
            posting
            for posting in payload["postings"]
            if posting["kind"] == "synthetic-royalty"
        ]
        assert all(posting["amount"] > 0 for posting in payload["postings"])
        assert sum(admissions.values()) == payload["gross_credits"]
        for ride_id, gross in admissions.items():
            split = {
                share: 0
                for share in park.ROYALTY_BPS
            }
            for posting in royalty_postings:
                if posting["ride_id"] != ride_id:
                    continue
                assert posting["basis_points"] == (
                    park.ROYALTY_BPS[posting["share"]]
                )
                split[posting["share"]] = posting["amount"]
            assert split == park._split_royalty(gross)
            assert sum(split.values()) == gross
            for share, basis_points in park.ROYALTY_BPS.items():
                error = abs(
                    split[share] * 10000
                    - gross * basis_points
                )
                assert error < 10000
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
        if (
            park._event_season(event) == park.SEASON_TWO
            and event["kind"] == "park.resource-negotiation"
        )
    ]
    assert len(resource_events) == 7
    contention_seen = False
    for event in resource_events:
        payload = event["payload"]
        assert payload["algorithm"] == (
            "guaranteed-floor-weighted-fair-queue/1"
        )
        assert payload["guaranteed_request_bps"] == (
            park.RESOURCE_GUARANTEE_BPS
        )
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
                assert allocated == capacity
                for bid in payload["bids"]:
                    request = bid["requested"][resource]
                    allocation = payload["allocations"][
                        bid["attraction_id"]
                    ][resource]
                    guaranteed = max(
                        1,
                        (
                            request
                            * park.RESOURCE_GUARANTEE_BPS
                        )
                        // 10000,
                    )
                    assert guaranteed <= allocation <= request
    assert contention_seen is True
    assert state["resource_capacity"] == park.RESOURCE_CAPACITY


def test_agent_cohort_demand_is_conserved_and_auditable():
    state, events, _contract = park.build_bundle(ROOT)
    expected_cohorts = {
        cohort["id"]: cohort
        for cohort in park._visitor_cohorts()
    }
    preferred_categories = {
        preference
        for cohort in expected_cohorts.values()
        for preference in cohort["preferences"]
    }
    demand_relevant_categories = {
        attraction["category"]
        for attraction in state["attractions"]
        if attraction["category"] != "static"
    }
    assert demand_relevant_categories <= preferred_categories
    admission_events = [
        event
        for event in events
        if (
            park._event_season(event) == park.SEASON_TWO
            and event["kind"] == "park.admission-settlement"
        )
    ]
    assert len(admission_events) == park.NIGHT_COUNT
    for event in admission_events:
        payload = event["payload"]
        aggregate = {
            attraction_id: 0
            for attraction_id in payload["admissions"]
        }
        assert {
            cohort["cohort_id"]
            for cohort in payload["cohort_demand"]
        } == set(expected_cohorts)
        for cohort in payload["cohort_demand"]:
            expected = expected_cohorts[cohort["cohort_id"]]
            assert cohort["population"] == expected["population"]
            assert cohort["preferences"] == expected["preferences"]
            assert sum(
                choice["admissions"]
                for choice in cohort["allocations"]
            ) == cohort["population"]
            assert [choice["rank"] for choice in cohort["allocations"]] == [
                1,
                2,
            ]
            for choice in cohort["allocations"]:
                aggregate[choice["attraction_id"]] += (
                    choice["admissions"]
                )
        assert aggregate == payload["admissions"]
        assert payload["population"] == 100
        assert sum(aggregate.values()) == payload["population"]


def test_park_invents_retires_and_evolves_every_night():
    state, events, _contract = park.build_bundle(ROOT)
    inventions = state["evolution"]["inventions"]
    retirements = state["evolution"]["retirements"]
    evolutions = state["evolution"]["nightly_mutations"]
    assert [item["attraction"]["id"] for item in inventions] == [
        "fold-at-home-ferris-wheel",
        "append-only-memory-maze",
    ]
    assert retirements
    assert retirements[0]["attraction_id"] == "static-queue"
    assert retirements[0]["night"] == 2
    assert all(
        retirement["reason"]
        == "two-consecutive-low-popularity-or-satisfaction-nights"
        for retirement in retirements
    )
    assert all(item["season"] == park.SEASON_TWO for item in retirements)
    assert all(item["season"] == park.SEASON_TWO for item in inventions)
    assert all(item["season"] == park.SEASON_TWO for item in evolutions)
    assert all(
        snapshot["season"] == park.SEASON_TWO
        for snapshot in state["nights"]
    )
    retirement_by_ride = {
        retirement["attraction_id"]: retirement["night"]
        for retirement in retirements
    }
    admission_by_night = {
        event["payload"]["night"]: event["payload"]["admissions"]
        for event in events
        if (
            park._event_season(event) == park.SEASON_TWO
            and event["kind"] == "park.admission-settlement"
        )
    }
    streaks = {}
    for snapshot in state["nights"]:
        night = snapshot["night"]
        attractions = {
            attraction["id"]: attraction
            for attraction in snapshot["attractions"]
        }
        for attraction_id, admissions in admission_by_night[night].items():
            metrics = attractions[attraction_id]["last_metrics"]
            low_signal = (
                metrics["popularity_bps"] < park.MIN_POPULARITY_BPS
                or metrics["satisfaction"] < 45
            )
            streaks[attraction_id] = (
                streaks.get(attraction_id, 0) + 1
                if low_signal
                else 0
            )
            if streaks[attraction_id] >= park.RETIREMENT_STREAK_NIGHTS:
                assert retirement_by_ride[attraction_id] == night
    assert len(evolutions) == 7
    assert len({item["attraction_id"] for item in evolutions}) >= 5
    assert all(
        item["after"]["version"] == item["before"]["version"] + 1
        and item["after"]["quality"] >= item["before"]["quality"]
        and item["after"]["novelty"] >= item["before"]["novelty"]
        for item in evolutions
    )
    for invention in inventions:
        provenance = copy.deepcopy(invention["provenance"])
        design_digest = provenance.pop("design_digest")
        assert provenance["night"] == invention["night"]
        assert provenance["anchor_frame_hash"] == park.ANCHOR_FRAME_HASH
        assert design_digest == park._canonical_digest(
            park.INVENTION_HASH_DOMAIN,
            {
                "attraction": invention["attraction"],
                "provenance": provenance,
            },
        )


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


def test_v2_contract_specifies_mcp_export_hashing_and_limits():
    _state, _events, contract = park.build_bundle(ROOT)
    assert contract["schema"] == "rappterzoo-agent-park-contract/2"
    assert contract["legacy_contract"] == {
        "immutable": True,
        "path": "agent-contract.json",
        "schema": "rappterzoo-agent-park-contract/1",
        "sha256": park.LEGACY_CONTRACT_SHA256,
    }
    assert contract["mcp_mapping"]["tools"] == {
        "bid_for_resources": "agent_park_local_action",
        "export_branch": "agent_park_export_branch",
        "invent_attraction": "agent_park_local_action",
        "time_travel": "agent_park_time_travel",
        "visit": "agent_park_local_action",
    }
    branch_export = contract["branch_export"]
    assert branch_export["export_schema"] == (
        "rappterzoo-agent-park-local-branch/2"
    )
    assert branch_export["required_fields"] == [
        "export_schema",
        "park_id",
        "canonical_write",
        "canonical_event_head",
        "canonical_organism_head",
        "action_limit",
        "actions",
        "authority",
        "branch_digest",
    ]
    assert branch_export["action_schema"] == (
        "rappterzoo-agent-park-local-action/2"
    )
    assert branch_export["action_required_fields"] == [
        "schema",
        "seq",
        "kind",
        "prev",
        "source",
        "source_hash",
        "payload",
        "payload_hash",
        "canonical_write",
        "action_hash",
    ]
    assert branch_export["canonical_write"] is False
    assert branch_export["action_additional_properties"] is False
    assert branch_export["export_additional_properties"] is False
    assert contract["action_limit"] == {
        "canonical_writes_per_session": 0,
        "first_visit_recommended_local_actions": 1,
        "max_local_actions_per_mcp_session": 100,
        "max_resource_units_per_field": 10000,
        "max_synthetic_bid": 1000000,
    }
    hashing = contract["canonicalization_and_hashing"]
    assert hashing["canonical_json"]["floats"] == "forbidden"
    assert hashing["canonical_json"]["encoding"] == "utf-8"
    assert set(hashing["preimages"]) == {
        "branch_digest",
        "bundle_digest",
        "contract_digest",
        "event_hash",
        "event_ledger_sha256",
        "full_export_content_digest",
        "invention_design_digest",
        "local_action_hash",
        "local_action_payload_hash",
        "local_action_source_hash",
        "payload_hash",
        "state_digest",
    }
    assert all(
        value.endswith("\n")
        for value in hashing["hash_domains"].values()
    )
    assert hashing["preimages"]["local_action_hash"]["bytes"] == [
        "mcp_local_branch_json({schema,seq,kind,prev,source,"
        "source_hash,payload,payload_hash,canonical_write})"
    ]
    assert hashing["preimages"]["branch_digest"]["bytes"] == [
        "mcp_local_branch_json({export_schema,park_id,"
        "canonical_write,canonical_event_head,"
        "canonical_organism_head,action_limit,actions,authority})"
    ]
    assert hashing["preimages"]["local_action_source_hash"] == {
        "park": "copy the selected canonical park event's event_hash",
        "organism": (
            "copy the selected canonical organism frame's frame_hash"
        ),
        "rehash": False,
    }
    full_export = contract["full_export"]
    assert full_export["export_schema"] == (
        "rappterzoo-agent-park-full-export/2"
    )
    assert full_export["required_fields"] == [
        "export_schema",
        "park_id",
        "canonical_write",
        "park_events",
        "organism_frames",
        "state",
        "contract",
        "bundle",
        "authority",
        "content_digest",
    ]
    assert full_export["content_digest_field"] == "content_digest"
    assert full_export["replay_requirements"]["park"][
        "preserve_season_one_prefix"
    ] == {
        "event_count": park.SEASON_ONE_EVENT_COUNT,
        "head": park.SEASON_ONE_HEAD,
        "sha256": park.SEASON_ONE_PREFIX_SHA256,
    }
    assert all(
        full_export["replay_requirements"][name]
        for name in ("park", "organism", "state", "contract", "bundle")
    )
    assert hashing["preimages"]["full_export_content_digest"]["bytes"] == [
        "utf8(hash_domains.full_export_v2)",
        "canonical_json({export_schema,park_id,canonical_write,"
        "park_events,organism_frames,state,contract,bundle,authority})",
    ]
    assert contract["verifier"] == {
        "command": "python3 scripts/agent_amusement_park.py verify",
        "fail_closed": True,
        "version": park.VERIFIER_VERSION,
    }


def test_state_event_and_contract_digests_share_one_bundle_binding():
    state, events, contract = park.build_bundle(ROOT)
    event_bytes = park._event_bytes(events)
    event_sha256 = hashlib.sha256(event_bytes).hexdigest()
    assert state["event_ledger"]["sha256"] == event_sha256
    assert state["integrity"]["state_digest"] == park._canonical_digest(
        park.STATE_HASH_DOMAIN,
        park._state_without_digest(state),
    )
    assert state["integrity"]["state_digest"] == EXPECTED_STATE_DIGEST
    assert contract["integrity"]["contract_digest"] == (
        park._canonical_digest(
            park.CONTRACT_HASH_DOMAIN,
            park._contract_without_digest(contract),
        )
    )
    expected_binding = park._bundle_digest(
        len(events),
        events[-1]["event_hash"],
        event_sha256,
        state["integrity"]["state_digest"],
        contract["integrity"]["contract_digest"],
    )
    assert len(expected_binding) == 64
    assert state["integrity"]["bundle_digest"] == expected_binding
    assert contract["integrity"]["bundle_digest"] == expected_binding


def test_bundle_is_byte_deterministic(tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    legacy_before = park.LEGACY_CONTRACT_PATH.read_bytes()
    park.write_bundle(ROOT, first)
    park.write_bundle(ROOT, second)
    for name in (
        "park-state.json",
        "events.jsonl",
        "agent-contract-v2.json",
    ):
        assert (first / name).read_bytes() == (second / name).read_bytes()
    assert park.LEGACY_CONTRACT_PATH.read_bytes() == legacy_before


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
    resealed_prefix = copy.deepcopy(events)
    resealed_prefix[3]["payload"]["night"] = 99
    _rehash_event_chain(resealed_prefix, start=0)
    with pytest.raises(park.ParkError, match="Season 1 event head"):
        park.verify_events(resealed_prefix)
    mutated_state = copy.deepcopy(state)
    mutated_state["economy"]["real_money"] = True
    with pytest.raises(park.ParkError, match="state digest"):
        park.verify_bundle(mutated_state, events, contract, ROOT)


def test_focused_mutations_fail_even_when_attackers_rehash():
    state, events, contract = park.build_bundle(ROOT)

    invalid_utc = copy.deepcopy(events)
    invalid_utc[park.SEASON_ONE_EVENT_COUNT]["utc"] = (
        "2026-08-22T23:50:00Z"
    )
    _rehash_event_chain(invalid_utc)
    with pytest.raises(park.ParkError, match="UTC"):
        park.verify_events(invalid_utc)

    overallocated = copy.deepcopy(events)
    resource_event = next(
        event
        for event in overallocated
        if (
            park._event_season(event) == park.SEASON_TWO
            and event["kind"] == "park.resource-negotiation"
        )
    )
    bid = resource_event["payload"]["bids"][0]
    attraction_id = bid["attraction_id"]
    resource_event["payload"]["allocations"][attraction_id][
        "attention_slots"
    ] = bid["requested"]["attention_slots"] + 1
    _rehash_event_chain(overallocated)
    rebound_state = copy.deepcopy(state)
    rebound_contract = copy.deepcopy(contract)
    _rebind_bundle(rebound_state, overallocated, rebound_contract)
    with pytest.raises(park.ParkError, match="resource allocation"):
        park.verify_bundle(
            rebound_state,
            overallocated,
            rebound_contract,
            ROOT,
        )

    bad_royalty = copy.deepcopy(events)
    settlement = next(
        event
        for event in bad_royalty
        if (
            park._event_season(event) == park.SEASON_TWO
            and event["kind"] == "park.royalty-settlement"
        )
    )
    royalty_posting = next(
        posting
        for posting in settlement["payload"]["postings"]
        if posting["kind"] == "synthetic-royalty"
    )
    royalty_posting["basis_points"] += 1
    _rehash_event_chain(bad_royalty)
    rebound_state = copy.deepcopy(state)
    rebound_contract = copy.deepcopy(contract)
    _rebind_bundle(rebound_state, bad_royalty, rebound_contract)
    with pytest.raises(park.ParkError, match="royalty basis points"):
        park.verify_bundle(
            rebound_state,
            bad_royalty,
            rebound_contract,
            ROOT,
        )

    bad_provenance = copy.deepcopy(state)
    bad_provenance["evolution"]["inventions"][0]["provenance"][
        "design_digest"
    ] = "0" * 64
    rebound_contract = copy.deepcopy(contract)
    _rebind_bundle(bad_provenance, events, rebound_contract)
    with pytest.raises(park.ParkError, match="invention provenance"):
        park.verify_bundle(
            bad_provenance,
            events,
            rebound_contract,
            ROOT,
        )

    severed_binding = copy.deepcopy(state)
    severed_binding["control_tower"][
        "customer_holds_runtime_keys"
    ] = False
    severed_binding["integrity"]["state_digest"] = park._canonical_digest(
        park.STATE_HASH_DOMAIN,
        park._state_without_digest(severed_binding),
    )
    with pytest.raises(park.ParkError, match="bundle digest binding"):
        park.verify_bundle(severed_binding, events, contract, ROOT)


def test_release_is_idempotent_in_isolated_tree(tmp_path):
    root = tmp_path / "repo"
    (root / "apps").mkdir(parents=True)
    for relative in (
        "apps/organism-frames.jsonl",
        "apps/organism-frames.json",
        "apps/manifest.json",
        "apps/agent-park/events.jsonl",
        "apps/agent-park/agent-contract.json",
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
    existing_frames = organism_ledger.read_frames(
        root / "apps" / "organism-frames.jsonl"
    )
    first_utc = (
        datetime.strptime(
            existing_frames[-1]["utc"],
            "%Y-%m-%dT%H:%M:%S.%fZ",
        ).replace(tzinfo=timezone.utc)
        + timedelta(minutes=1)
    )
    second_utc = first_utc + timedelta(days=1)
    first = park.append_park_frame(
        root,
        utc=first_utc.isoformat(timespec="milliseconds").replace(
            "+00:00",
            "Z",
        ),
    )
    second = park.append_park_frame(
        root,
        utc=second_utc.isoformat(timespec="milliseconds").replace(
            "+00:00",
            "Z",
        ),
    )
    assert first == second
    frames = organism_ledger.read_frames(
        root / "apps" / "organism-frames.jsonl"
    )
    matches = [
        frame
        for frame in frames
        if frame["payload"]["event_id"]
        == "experience-release:agent-amusement-park:{}".format(
            first["payload"]["bundle_digest"]
        )
    ]
    assert len(matches) == 1
    assert matches[0]["payload"]["bundle_digest"] == (
        first["payload"]["bundle_digest"]
    )


def test_checked_in_bundle_is_current_and_verifiable():
    state = park._load_json(park.STATE_PATH)
    events = park._load_events(park.EVENTS_PATH)
    contract = park._load_json(park.CONTRACT_PATH)
    result = park.verify_bundle(state, events, contract, ROOT)
    expected_state, expected_events, expected_contract = park.build_bundle(
        ROOT
    )
    assert result["valid"] is True
    assert state == expected_state
    assert events == expected_events
    assert contract == expected_contract


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

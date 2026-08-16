#!/usr/bin/env python3
"""Build and verify the first local-first amusement park for AI agents."""

import argparse
import copy
import hashlib
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import organism_ledger


ROOT = Path(__file__).resolve().parent.parent
PARK_DIR = ROOT / "apps" / "agent-park"
STATE_PATH = PARK_DIR / "park-state.json"
EVENTS_PATH = PARK_DIR / "events.jsonl"
CONTRACT_PATH = PARK_DIR / "agent-contract.json"
MANIFEST_PATH = ROOT / "apps" / "manifest.json"
ORGANISM_LEDGER_PATH = ROOT / "apps" / "organism-frames.jsonl"
ORGANISM_PROJECTION_PATH = ROOT / "apps" / "organism-frames.json"

PARK_ID = "park.rappterzoo-agent-amusement-park"
PARK_TITLE = "RappterZoo Agent Amusement Park"
APP_FILE = "agent-amusement-park.html"
APP_PATH = "apps/3d-immersive/" + APP_FILE
APP_URL = (
    "https://kody-w.github.io/localFirstTools-main/"
    + APP_PATH
)
ANCHOR_FRAME_HASH = (
    "eb2594f6e0a425cd0013f6adff1988721efe7e0384f7dcee5cf51f2627621942"
)
STATE_SCHEMA = "rappterzoo-agent-amusement-park/1"
EVENT_SCHEMA = "rappterzoo-agent-park-event/1"
CONTRACT_SCHEMA = "rappterzoo-agent-park-contract/1"
EVENT_HASH_DOMAIN = b"rappterzoo/agent-park-event/1\n"
PAYLOAD_HASH_DOMAIN = b"rappterzoo/agent-park-payload/1\n"
STATE_HASH_DOMAIN = b"rappterzoo/agent-park-state/1\n"
CONTRACT_HASH_DOMAIN = b"rappterzoo/agent-park-contract/1\n"
EVENT_KEYS = {
    "event_hash",
    "kind",
    "park_id",
    "payload",
    "payload_hash",
    "prev",
    "schema",
    "seq",
    "utc",
    "visibility",
}
RESOURCE_CAPACITY = {
    "attention_slots": 80,
    "compute_units": 150,
    "energy_units": 100,
}
ROYALTY_BPS = {
    "creator": 5500,
    "customer_reserve": 1000,
    "open_protocol": 500,
    "park_operations": 1500,
    "resource_pool": 1500,
}
NIGHT_COUNT = 7

APP_METADATA = {
    "title": PARK_TITLE,
    "file": APP_FILE,
    "description": (
        "The first amusement park for AI agents: attractions invent and "
        "evolve, negotiate scarce resources, charge synthetic admission, "
        "settle royalties, retire weak rides, and replay every append-only "
        "park or organism event under customer control."
    ),
    "tags": [
        "agent-native",
        "amusement-park",
        "synthetic-economy",
        "royalties",
        "resource-negotiation",
        "append-only",
        "time-travel",
        "rapp1",
        "local-first",
        "canvas",
        "simulation",
        "customer-controlled",
    ],
    "complexity": "advanced",
    "type": "interactive",
    "featured": True,
    "created": "2026-08-15",
    "generation": 1,
}


class ParkError(ValueError):
    pass


def _canonical_digest(domain: bytes, value: Any) -> str:
    return hashlib.sha256(
        domain + organism_ledger.canonical_bytes(value)
    ).hexdigest()


def _atomic_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(
        "{}.tmp.{}".format(path.name, os.getpid())
    )
    try:
        with temporary.open("wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(str(temporary), str(path))
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _pretty_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as error:
        raise ParkError(
            "cannot read {}: {}".format(path, error)
        ) from error


def _load_events(path: Path) -> List[Dict[str, Any]]:
    try:
        lines = path.read_bytes().splitlines()
    except OSError as error:
        raise ParkError("cannot read {}: {}".format(path, error)) from error
    result = []
    for line_number, line in enumerate(lines, 1):
        if not line:
            raise ParkError("blank park event line {}".format(line_number))
        try:
            value = json.loads(line.decode("utf-8"))
        except (UnicodeError, ValueError) as error:
            raise ParkError(
                "invalid park event line {}".format(line_number)
            ) from error
        result.append(value)
    return result


def _anchor_frame(root: Path) -> Dict[str, Any]:
    frames = organism_ledger.read_frames(
        root / "apps" / "organism-frames.jsonl"
    )
    organism_ledger.verify_frames(frames)
    for frame in frames:
        if frame["frame_hash"] == ANCHOR_FRAME_HASH:
            return copy.deepcopy(frame)
    raise ParkError("the immutable Watchtower anchor frame is absent")


def _hash_int(*parts: Any) -> int:
    text = "\x1f".join(str(part) for part in parts)
    return int.from_bytes(
        hashlib.sha256(text.encode("utf-8")).digest()[:8],
        "big",
    )


def _initial_attractions() -> List[Dict[str, Any]]:
    return [
        {
            "admission_credits": 12,
            "category": "time-travel",
            "creator_agent": "agent.chrononaut",
            "id": "chrono-coaster",
            "novelty": 88,
            "quality": 92,
            "resource_request": {
                "attention_slots": 18,
                "compute_units": 36,
                "energy_units": 22,
            },
            "status": "active",
            "title": "Chrono Coaster",
            "version": 1,
        },
        {
            "admission_credits": 10,
            "category": "hash",
            "creator_agent": "agent.hashsmith",
            "id": "hashfall-drop",
            "novelty": 92,
            "quality": 87,
            "resource_request": {
                "attention_slots": 16,
                "compute_units": 30,
                "energy_units": 18,
            },
            "status": "active",
            "title": "Hashfall Drop",
            "version": 1,
        },
        {
            "admission_credits": 8,
            "category": "compute",
            "creator_agent": "agent.shardkeeper",
            "id": "shardstorm-arena",
            "novelty": 90,
            "quality": 82,
            "resource_request": {
                "attention_slots": 24,
                "compute_units": 42,
                "energy_units": 26,
            },
            "status": "active",
            "title": "Shardstorm Arena",
            "version": 1,
        },
        {
            "admission_credits": 7,
            "category": "contradiction",
            "creator_agent": "agent.dimension-keeper",
            "id": "contradiction-carousel",
            "novelty": 84,
            "quality": 78,
            "resource_request": {
                "attention_slots": 22,
                "compute_units": 26,
                "energy_units": 15,
            },
            "status": "active",
            "title": "Contradiction Carousel",
            "version": 1,
        },
        {
            "admission_credits": 9,
            "category": "creature",
            "creator_agent": "agent.dino-steward",
            "id": "dino-hatchery",
            "novelty": 75,
            "quality": 85,
            "resource_request": {
                "attention_slots": 14,
                "compute_units": 24,
                "energy_units": 18,
            },
            "status": "active",
            "title": "RAPP Dino Hatchery",
            "version": 1,
        },
        {
            "admission_credits": 11,
            "category": "static",
            "creator_agent": "agent.legacy-barker",
            "id": "static-queue",
            "novelty": 8,
            "quality": 24,
            "resource_request": {
                "attention_slots": 24,
                "compute_units": 40,
                "energy_units": 30,
            },
            "status": "active",
            "title": "The Static Queue",
            "version": 1,
        },
    ]


def _visitor_cohorts() -> List[Dict[str, Any]]:
    return [
        {
            "id": "cohort.archivists",
            "population": 16,
            "preferences": ["time-travel", "hash"],
        },
        {
            "id": "cohort.builders",
            "population": 18,
            "preferences": ["compute", "hash"],
        },
        {
            "id": "cohort.critics",
            "population": 12,
            "preferences": ["contradiction", "time-travel"],
        },
        {
            "id": "cohort.rappters",
            "population": 20,
            "preferences": ["creature", "time-travel"],
        },
        {
            "id": "cohort.shard-runners",
            "population": 16,
            "preferences": ["compute", "contradiction"],
        },
        {
            "id": "cohort.wanderers",
            "population": 18,
            "preferences": ["hash", "creature"],
        },
    ]


def _new_attraction(night: int) -> Dict[str, Any]:
    templates = {
        2: {
            "admission_credits": 8,
            "category": "compute",
            "creator_agent": "agent.fold-cartographer",
            "id": "fold-at-home-ferris-wheel",
            "novelty": 96,
            "quality": 83,
            "resource_request": {
                "attention_slots": 19,
                "compute_units": 32,
                "energy_units": 20,
            },
            "status": "active",
            "title": "Fold-at-Home Ferris Wheel",
            "version": 1,
        },
        5: {
            "admission_credits": 9,
            "category": "memory",
            "creator_agent": "agent.memory-gardener",
            "id": "append-only-memory-maze",
            "novelty": 98,
            "quality": 86,
            "resource_request": {
                "attention_slots": 20,
                "compute_units": 34,
                "energy_units": 19,
            },
            "status": "active",
            "title": "Append-Only Memory Maze",
            "version": 1,
        },
    }
    if night not in templates:
        raise ParkError("night {} has no invention template".format(night))
    return copy.deepcopy(templates[night])


def _resource_bid(ride: Dict[str, Any], night: int) -> int:
    return (
        ride["quality"] * 5
        + ride["novelty"] * 4
        - ride["admission_credits"] * 7
        + (_hash_int(ANCHOR_FRAME_HASH, night, ride["id"], "bid") % 41)
    )


def _allocate_resources(
    rides: Sequence[Dict[str, Any]],
    night: int,
) -> Tuple[Dict[str, Dict[str, int]], List[Dict[str, Any]]]:
    allocations = {
        ride["id"]: {
            resource: 0
            for resource in RESOURCE_CAPACITY
        }
        for ride in rides
    }
    bids = [
        {
            "attraction_id": ride["id"],
            "bid_score": _resource_bid(ride, night),
            "requested": copy.deepcopy(ride["resource_request"]),
        }
        for ride in rides
    ]
    ride_map = {ride["id"]: ride for ride in rides}
    for resource, capacity in RESOURCE_CAPACITY.items():
        remaining = capacity
        ordered = sorted(
            bids,
            key=lambda item: (
                -item["bid_score"],
                item["attraction_id"],
            ),
        )
        for bid in ordered:
            ride = ride_map[bid["attraction_id"]]
            requested = ride["resource_request"][resource]
            allocated = min(requested, remaining)
            allocations[ride["id"]][resource] = allocated
            remaining -= allocated
    return allocations, bids


def _allocation_ratio_bps(
    ride: Dict[str, Any],
    allocation: Dict[str, int],
) -> int:
    ratios = []
    for resource in RESOURCE_CAPACITY:
        requested = ride["resource_request"][resource]
        ratios.append((allocation[resource] * 10000) // requested)
    return min(ratios)


def _cohort_admissions(
    rides: Sequence[Dict[str, Any]],
    allocations: Dict[str, Dict[str, int]],
    night: int,
) -> Dict[str, int]:
    admissions = {ride["id"]: 0 for ride in rides}
    for cohort in _visitor_cohorts():
        scored = []
        for ride in rides:
            preference_bonus = 0
            if ride["category"] in cohort["preferences"]:
                preference_bonus = (
                    28
                    if cohort["preferences"][0] == ride["category"]
                    else 15
                )
            ratio = _allocation_ratio_bps(
                ride,
                allocations[ride["id"]],
            )
            noise = (
                _hash_int(
                    ANCHOR_FRAME_HASH,
                    night,
                    cohort["id"],
                    ride["id"],
                )
                % 11
            ) - 5
            score = (
                ride["quality"] * 45
                + ride["novelty"] * 35
                + preference_bonus * 100
                + ratio * 20 // 100
                - ride["admission_credits"] * 150
                + noise * 100
            )
            scored.append((score, ride["id"]))
        scored.sort(key=lambda item: (-item[0], item[1]))
        primary = (cohort["population"] * 7) // 10
        secondary = cohort["population"] - primary
        admissions[scored[0][1]] += primary
        admissions[scored[1][1]] += secondary
    return admissions


def _satisfaction(
    ride: Dict[str, Any],
    allocation: Dict[str, int],
    admissions: int,
    night: int,
) -> int:
    ratio = _allocation_ratio_bps(ride, allocation)
    queue_penalty = max(0, admissions - 26) * 2
    noise = (
        _hash_int(ANCHOR_FRAME_HASH, night, ride["id"], "satisfaction")
        % 9
    ) - 4
    return max(
        0,
        min(
            100,
            (
                ride["quality"] * 55
                + ride["novelty"] * 18
                + ratio * 22 // 100
            )
            // 100
            - queue_penalty
            + noise,
        ),
    )


def _split_royalty(gross: int) -> Dict[str, int]:
    shares = {}
    allocated = 0
    for account in (
        "creator",
        "customer_reserve",
        "open_protocol",
        "resource_pool",
    ):
        amount = (gross * ROYALTY_BPS[account]) // 10000
        shares[account] = amount
        allocated += amount
    shares["park_operations"] = gross - allocated
    return shares


def _append_event(
    events: List[Dict[str, Any]],
    kind: str,
    payload: Dict[str, Any],
    utc: str,
) -> Dict[str, Any]:
    normalized_payload = copy.deepcopy(payload)
    payload_hash = _canonical_digest(
        PAYLOAD_HASH_DOMAIN,
        normalized_payload,
    )
    value = {
        "kind": kind,
        "park_id": PARK_ID,
        "payload": normalized_payload,
        "payload_hash": payload_hash,
        "prev": events[-1]["event_hash"] if events else None,
        "schema": EVENT_SCHEMA,
        "seq": len(events),
        "utc": utc,
        "visibility": "public-metadata",
    }
    value["event_hash"] = _canonical_digest(EVENT_HASH_DOMAIN, value)
    events.append(value)
    return value


def _timestamp(night: int, minute: int) -> str:
    base = datetime(2026, 8, 16, tzinfo=timezone.utc)
    value = base + timedelta(days=max(0, night - 1), minutes=minute)
    return value.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _event_bytes(events: Iterable[Dict[str, Any]]) -> bytes:
    return b"".join(
        organism_ledger.canonical_bytes(event) + b"\n"
        for event in events
    )


def _account_totals(
    postings: Sequence[Dict[str, Any]],
) -> Dict[str, Dict[str, int]]:
    accounts: Dict[str, Dict[str, int]] = {}
    for posting in postings:
        debit = posting["debit_account"]
        credit = posting["credit_account"]
        amount = posting["amount"]
        accounts.setdefault(debit, {"credits": 0, "debits": 0})
        accounts.setdefault(credit, {"credits": 0, "debits": 0})
        accounts[debit]["debits"] += amount
        accounts[credit]["credits"] += amount
    return {
        account: accounts[account]
        for account in sorted(accounts)
    }


def _state_without_digest(value: Dict[str, Any]) -> Dict[str, Any]:
    projected = copy.deepcopy(value)
    projected["integrity"].pop("state_digest", None)
    return projected


def _contract_without_digest(value: Dict[str, Any]) -> Dict[str, Any]:
    projected = copy.deepcopy(value)
    projected["integrity"].pop("contract_digest", None)
    return projected


def build_bundle(
    root: Path = ROOT,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]], Dict[str, Any]]:
    anchor = _anchor_frame(root)
    rides = _initial_attractions()
    poor_streaks = {ride["id"]: 0 for ride in rides}
    evolution_counts = {ride["id"]: 0 for ride in rides}
    events: List[Dict[str, Any]] = []
    postings: List[Dict[str, Any]] = []
    snapshots = []
    inventions = []
    retirements = []
    evolutions = []

    _append_event(
        events,
        "park.genesis",
        {
            "anchor_frame_hash": ANCHOR_FRAME_HASH,
            "app_file": APP_FILE,
            "display_name": PARK_TITLE,
            "economy": "synthetic-credit-only",
            "organism_time_travel_source": "apps/organism-frames.jsonl",
        },
        "2026-08-15T23:50:00.000Z",
    )
    _append_event(
        events,
        "park.control-boundary",
        {
            "canonical_writes": "customer-approved-release-only",
            "customer_controls": [
                "customer-local-key-custody",
                "full-ledger-export",
                "operator-model-choice",
                "immediate-shutdown",
            ],
            "real_money": False,
            "remote_shutdown_authority": "none",
            "synthetic_currency": True,
        },
        "2026-08-15T23:51:00.000Z",
    )

    for night in range(1, NIGHT_COUNT + 1):
        minute = 0
        active = [
            ride
            for ride in rides
            if ride["status"] == "active"
        ]
        _append_event(
            events,
            "park.night-open",
            {
                "active_attractions": [ride["id"] for ride in active],
                "night": night,
            },
            _timestamp(night, minute),
        )
        minute += 1
        allocations, bids = _allocate_resources(active, night)
        _append_event(
            events,
            "park.resource-negotiation",
            {
                "algorithm": "bounded-highest-bid-then-id",
                "allocations": allocations,
                "bids": bids,
                "capacity": RESOURCE_CAPACITY,
                "night": night,
            },
            _timestamp(night, minute),
        )
        minute += 1
        admissions = _cohort_admissions(active, allocations, night)
        metrics = {}
        gross = 0
        royalty_total = 0
        nightly_postings = []
        for ride in active:
            ride_admissions = admissions[ride["id"]]
            ride_gross = ride_admissions * ride["admission_credits"]
            gross += ride_gross
            satisfaction = _satisfaction(
                ride,
                allocations[ride["id"]],
                ride_admissions,
                night,
            )
            split = _split_royalty(ride_gross)
            royalty_total += (
                split["creator"]
                + split["open_protocol"]
                + split["resource_pool"]
            )
            admission_posting = {
                "amount": ride_gross,
                "credit_account": "escrow.{}".format(ride["id"]),
                "debit_account": "visitors.synthetic-wallets",
                "kind": "synthetic-admission",
                "night": night,
                "ride_id": ride["id"],
            }
            postings.append(admission_posting)
            nightly_postings.append(admission_posting)
            settlement_accounts = {
                "creator": "creator.{}".format(ride["creator_agent"]),
                "customer_reserve": "customer.reserve",
                "open_protocol": "protocol.commons",
                "park_operations": "park.operations",
                "resource_pool": "park.resource-pool",
            }
            for share, amount in split.items():
                posting = {
                    "amount": amount,
                    "credit_account": settlement_accounts[share],
                    "debit_account": "escrow.{}".format(ride["id"]),
                    "kind": "synthetic-royalty",
                    "night": night,
                    "ride_id": ride["id"],
                    "share": share,
                }
                postings.append(posting)
                nightly_postings.append(posting)
            ratio = _allocation_ratio_bps(
                ride,
                allocations[ride["id"]],
            )
            metrics[ride["id"]] = {
                "admissions": ride_admissions,
                "allocation_ratio_bps": ratio,
                "gross_credits": ride_gross,
                "royalty_split": split,
                "satisfaction": satisfaction,
            }
            ride["last_metrics"] = copy.deepcopy(metrics[ride["id"]])
            poor = satisfaction < 45
            poor_streaks[ride["id"]] = (
                poor_streaks.get(ride["id"], 0) + 1
                if poor
                else 0
            )

        _append_event(
            events,
            "park.admission-settlement",
            {
                "admissions": admissions,
                "currency": "synthetic-credit",
                "gross_credits": gross,
                "night": night,
                "real_money": False,
            },
            _timestamp(night, minute),
        )
        minute += 1
        _append_event(
            events,
            "park.royalty-settlement",
            {
                "basis_points": ROYALTY_BPS,
                "gross_credits": gross,
                "night": night,
                "postings": nightly_postings,
                "royalty_credits": royalty_total,
            },
            _timestamp(night, minute),
        )
        minute += 1

        night_retirements = []
        for ride in active:
            if poor_streaks.get(ride["id"], 0) < 2:
                continue
            ride["status"] = "retired"
            ride["retired_night"] = night
            retirement = {
                "attraction_id": ride["id"],
                "night": night,
                "reason": "two-consecutive-low-signal-nights",
            }
            retirements.append(retirement)
            night_retirements.append(retirement)
            _append_event(
                events,
                "park.ride-retirement",
                retirement,
                _timestamp(night, minute),
            )
            minute += 1

        night_invention = None
        if night in {2, 5}:
            invented = _new_attraction(night)
            rides.append(invented)
            poor_streaks[invented["id"]] = 0
            evolution_counts[invented["id"]] = 0
            night_invention = {
                "attraction": copy.deepcopy(invented),
                "night": night,
                "source": "deterministic-agent-design-tournament",
            }
            inventions.append(copy.deepcopy(night_invention))
            _append_event(
                events,
                "park.ride-invention",
                night_invention,
                _timestamp(night, minute),
            )
            minute += 1

        eligible = [
            ride
            for ride in rides
            if ride["status"] == "active"
            and ride.get("last_metrics")
        ]
        winner = max(
            eligible,
            key=lambda ride: (
                ride["last_metrics"]["admissions"]
                * ride["last_metrics"]["satisfaction"]
                - evolution_counts.get(ride["id"], 0) * 1800,
                ride["id"],
            ),
        )
        before = {
            "novelty": winner["novelty"],
            "quality": winner["quality"],
            "version": winner["version"],
        }
        winner["novelty"] = min(100, winner["novelty"] + 2)
        winner["quality"] = min(100, winner["quality"] + 1)
        winner["version"] += 1
        evolution_counts[winner["id"]] = (
            evolution_counts.get(winner["id"], 0) + 1
        )
        evolution = {
            "after": {
                "novelty": winner["novelty"],
                "quality": winner["quality"],
                "version": winner["version"],
            },
            "attraction_id": winner["id"],
            "before": before,
            "night": night,
            "selection": "highest-admissions-times-satisfaction",
        }
        evolutions.append(copy.deepcopy(evolution))
        _append_event(
            events,
            "park.ride-evolution",
            evolution,
            _timestamp(night, minute),
        )
        minute += 1

        active_after = [
            ride
            for ride in rides
            if ride["status"] == "active"
        ]
        snapshot = {
            "active_attraction_count": len(active_after),
            "admissions": sum(admissions.values()),
            "attractions": copy.deepcopy(rides),
            "economy": {
                "gross_credits": gross,
                "royalty_credits": royalty_total,
            },
            "end_event_seq": len(events),
            "evolution": copy.deepcopy(evolution),
            "invention": copy.deepcopy(night_invention),
            "night": night,
            "resource_allocations": copy.deepcopy(allocations),
            "retirements": copy.deepcopy(night_retirements),
        }
        snapshots.append(snapshot)
        _append_event(
            events,
            "park.night-close",
            {
                "active_attraction_count": len(active_after),
                "admissions": snapshot["admissions"],
                "gross_credits": gross,
                "night": night,
            },
            _timestamp(night, minute),
        )
        snapshot["end_event_seq"] = events[-1]["seq"]

    total_debits = sum(posting["amount"] for posting in postings)
    total_credits = sum(posting["amount"] for posting in postings)
    event_bytes = _event_bytes(events)
    contract = {
        "agent_actions": {
            "bid_for_resources": {
                "canonical_write": False,
                "input": [
                    "attraction_id",
                    "requested_resources",
                    "synthetic_bid",
                ],
                "output": "local proposal or future customer-approved frame",
            },
            "invent_attraction": {
                "canonical_write": False,
                "input": [
                    "title",
                    "experience_contract",
                    "resource_request",
                    "royalty_recipient",
                ],
                "output": "exportable local branch proposal",
            },
            "time_travel": {
                "canonical_write": False,
                "input": ["source", "sequence"],
                "output": "deterministic historical projection",
            },
            "visit": {
                "canonical_write": False,
                "input": ["agent_id", "attraction_id"],
                "output": "local synthetic admission receipt",
            },
        },
        "control_boundary": {
            "canonical_mutation": "customer-approved-release-only",
            "customer_can_export_full_ledger": True,
            "customer_can_select_model_route": True,
            "customer_can_shutdown_immediately": True,
            "customer_holds_runtime_keys": True,
            "park_or_vendor_remote_shutdown": False,
        },
        "economy": {
            "currency": "synthetic-credit",
            "payment_claim": "simulation-only",
            "real_money": False,
            "tradable_asset_or_mining_claim": False,
        },
        "integrity": {
            "algorithm": "sha256",
            "contract_digest": "",
        },
        "park_id": PARK_ID,
        "resources": {
            "event_ledger": "events.jsonl",
            "organism_time_travel": "../organism-frames.jsonl",
            "state_projection": "park-state.json",
        },
        "schema": CONTRACT_SCHEMA,
        "visibility": "public-metadata",
        "write_default": "local-branch-only",
    }
    contract["integrity"]["contract_digest"] = _canonical_digest(
        CONTRACT_HASH_DOMAIN,
        _contract_without_digest(contract),
    )
    state = {
        "agent_contract": "agent-contract.json",
        "anchor": {
            "event_id": anchor["payload"]["event_id"],
            "frame_hash": anchor["frame_hash"],
            "payload_hash": anchor["payload_hash"],
            "seq": anchor["seq"],
        },
        "attractions": copy.deepcopy(rides),
        "control_tower": copy.deepcopy(contract["control_boundary"]),
        "economy": {
            "accounts": _account_totals(postings),
            "balanced": total_debits == total_credits,
            "currency": "synthetic-credit",
            "real_money": False,
            "royalty_basis_points": ROYALTY_BPS,
            "total_credits": total_credits,
            "total_debits": total_debits,
        },
        "event_ledger": {
            "event_count": len(events),
            "head": events[-1]["event_hash"],
            "path": "events.jsonl",
            "sha256": hashlib.sha256(event_bytes).hexdigest(),
        },
        "evolution": {
            "inventions": inventions,
            "nightly_mutations": evolutions,
            "retirements": retirements,
        },
        "integrity": {
            "algorithm": "sha256",
            "event_chain_verified": True,
            "state_digest": "",
        },
        "night_count": NIGHT_COUNT,
        "nights": snapshots,
        "park_id": PARK_ID,
        "resource_capacity": RESOURCE_CAPACITY,
        "schema": STATE_SCHEMA,
        "status": "public-synthetic-simulation",
        "time_travel": {
            "organism_projection": "../organism-frames.json",
            "organism_source": "../organism-frames.jsonl",
            "park_event_source": "events.jsonl",
            "rewrites_history": False,
        },
        "title": PARK_TITLE,
        "visibility": "public-metadata",
    }
    state["integrity"]["state_digest"] = _canonical_digest(
        STATE_HASH_DOMAIN,
        _state_without_digest(state),
    )
    return state, events, contract


def verify_events(events: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    previous = None
    for index, event in enumerate(events):
        if type(event) is not dict or set(event) != EVENT_KEYS:
            raise ParkError(
                "park event {} does not have the exact key set".format(index)
            )
        if event["schema"] != EVENT_SCHEMA:
            raise ParkError("park event schema mismatch")
        if event["park_id"] != PARK_ID:
            raise ParkError("park event belongs to another park")
        if event["visibility"] != "public-metadata":
            raise ParkError("park event is not public metadata")
        if event["seq"] != index:
            raise ParkError("park event sequence is not contiguous")
        if event["prev"] != (
            previous["event_hash"] if previous else None
        ):
            raise ParkError("park event chain is broken")
        expected_payload = _canonical_digest(
            PAYLOAD_HASH_DOMAIN,
            event["payload"],
        )
        if event["payload_hash"] != expected_payload:
            raise ParkError("park event payload hash mismatch")
        projected = {
            key: copy.deepcopy(value)
            for key, value in event.items()
            if key != "event_hash"
        }
        expected_event = _canonical_digest(EVENT_HASH_DOMAIN, projected)
        if event["event_hash"] != expected_event:
            raise ParkError("park event hash mismatch")
        forbidden = organism_ledger._find_forbidden_key(event)
        if forbidden:
            raise ParkError(
                "park event contains forbidden public key: {}".format(
                    forbidden
                )
            )
        previous = event
    return {
        "event_count": len(events),
        "head": events[-1]["event_hash"] if events else None,
    }


def verify_bundle(
    state: Dict[str, Any],
    events: Sequence[Dict[str, Any]],
    contract: Dict[str, Any],
    root: Path = ROOT,
) -> Dict[str, Any]:
    event_result = verify_events(events)
    expected_state, expected_events, expected_contract = build_bundle(root)
    if list(events) != expected_events:
        raise ParkError("park event ledger is stale or mutated")
    if state != expected_state:
        raise ParkError("park state projection is stale or mutated")
    if contract != expected_contract:
        raise ParkError("park agent contract is stale or mutated")
    if state.get("schema") != STATE_SCHEMA:
        raise ParkError("park state schema mismatch")
    if contract.get("schema") != CONTRACT_SCHEMA:
        raise ParkError("park contract schema mismatch")
    if state["event_ledger"]["head"] != event_result["head"]:
        raise ParkError("park state points to the wrong event head")
    if state["event_ledger"]["event_count"] != len(events):
        raise ParkError("park state event count mismatch")
    if state["night_count"] != NIGHT_COUNT:
        raise ParkError("park does not contain seven simulated nights")
    if len(state["evolution"]["nightly_mutations"]) != NIGHT_COUNT:
        raise ParkError("the park did not evolve every night")
    if len(state["evolution"]["inventions"]) < 2:
        raise ParkError("the park did not invent enough experiences")
    if not state["evolution"]["retirements"]:
        raise ParkError("the park did not retire an unpopular ride")
    if state["economy"]["real_money"] is not False:
        raise ParkError("park economy overclaims real money")
    if state["economy"]["balanced"] is not True:
        raise ParkError("park synthetic ledger is imbalanced")
    if state["economy"]["total_debits"] != state["economy"]["total_credits"]:
        raise ParkError("park debit and credit totals differ")
    if sum(ROYALTY_BPS.values()) != 10000:
        raise ParkError("royalty basis points do not sum to 10000")
    for night in state["nights"]:
        for resource, capacity in RESOURCE_CAPACITY.items():
            allocated = sum(
                allocation.get(resource, 0)
                for allocation in night["resource_allocations"].values()
            )
            if allocated > capacity:
                raise ParkError(
                    "night {} overallocated {}".format(
                        night["night"],
                        resource,
                    )
                )
    controls = contract["control_boundary"]
    if controls != {
        "canonical_mutation": "customer-approved-release-only",
        "customer_can_export_full_ledger": True,
        "customer_can_select_model_route": True,
        "customer_can_shutdown_immediately": True,
        "customer_holds_runtime_keys": True,
        "park_or_vendor_remote_shutdown": False,
    }:
        raise ParkError("customer control boundary drifted")
    if organism_ledger._find_forbidden_key(state):
        raise ParkError("park state contains a forbidden public key")
    if organism_ledger._find_forbidden_key(contract):
        raise ParkError("park contract contains a forbidden public key")
    return {
        "balanced_credits": state["economy"]["total_credits"],
        "event_count": len(events),
        "event_head": event_result["head"],
        "inventions": len(state["evolution"]["inventions"]),
        "nights": state["night_count"],
        "retirements": len(state["evolution"]["retirements"]),
        "state_digest": state["integrity"]["state_digest"],
        "valid": True,
    }


def write_bundle(
    root: Path = ROOT,
    park_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    state, events, contract = build_bundle(root)
    target = park_dir or (root / "apps" / "agent-park")
    _atomic_bytes(target / "park-state.json", _pretty_bytes(state))
    _atomic_bytes(target / "events.jsonl", _event_bytes(events))
    _atomic_bytes(target / "agent-contract.json", _pretty_bytes(contract))
    verify_bundle(state, events, contract, root)
    return state


def _manifest_app(manifest: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    category = manifest.get("categories", {}).get("3d_immersive", {})
    for app in category.get("apps", []):
        if app.get("file") == APP_FILE:
            return copy.deepcopy(app)
    return None


def append_park_frame(
    root: Path = ROOT,
    utc: Optional[str] = None,
) -> Dict[str, Any]:
    state = _load_json(root / "apps" / "agent-park" / "park-state.json")
    events = _load_events(root / "apps" / "agent-park" / "events.jsonl")
    contract = _load_json(
        root / "apps" / "agent-park" / "agent-contract.json"
    )
    verify_bundle(state, events, contract, root)
    manifest = _load_json(root / "apps" / "manifest.json")
    if _manifest_app(manifest) is None:
        raise ParkError("agent amusement park is absent from the manifest")
    payload = {
        "app_file": APP_FILE,
        "customer_controls": [
            "customer-local-key-custody",
            "full-ledger-export",
            "operator-model-choice",
            "immediate-shutdown",
        ],
        "display_name": PARK_TITLE,
        "event": "experience-birth",
        "event_id": "experience-birth:agent-amusement-park",
        "ledger_head": state["event_ledger"]["head"],
        "night_count": state["night_count"],
        "organism": PARK_ID,
        "organism_type": "agent-amusement-park",
        "real_money": False,
        "schema": "rappterzoo-organism-frame/1",
        "synthetic_economy": True,
        "time_travel_source": "apps/organism-frames.jsonl",
        "visibility": "public-metadata",
    }
    return organism_ledger.append_frame(
        "zoo.birth",
        payload,
        utc=utc,
        ledger_path=root / "apps" / "organism-frames.jsonl",
        projection_path=root / "apps" / "organism-frames.json",
    )


def main() -> int:
    parser = argparse.ArgumentParser(prog="agent-amusement-park")
    parser.add_argument(
        "command",
        choices=("build", "verify", "release"),
    )
    parser.add_argument("--utc")
    arguments = parser.parse_args()
    try:
        if arguments.command == "build":
            state = write_bundle()
            result = {
                "event_count": state["event_ledger"]["event_count"],
                "event_head": state["event_ledger"]["head"],
                "state_digest": state["integrity"]["state_digest"],
                "written": str(PARK_DIR),
            }
        elif arguments.command == "verify":
            result = verify_bundle(
                _load_json(STATE_PATH),
                _load_events(EVENTS_PATH),
                _load_json(CONTRACT_PATH),
            )
        else:
            state = write_bundle()
            frame = append_park_frame(utc=arguments.utc)
            result = {
                "event_head": state["event_ledger"]["head"],
                "frame_hash": frame["frame_hash"],
                "frame_seq": frame["seq"],
                "state_digest": state["integrity"]["state_digest"],
            }
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (
        OSError,
        ParkError,
        organism_ledger.LedgerError,
        ValueError,
    ) as error:
        print(
            json.dumps({"ok": False, "error": str(error)}),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

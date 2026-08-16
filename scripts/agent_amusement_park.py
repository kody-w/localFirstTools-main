#!/usr/bin/env python3
"""Build and verify the first local-first amusement park for AI agents."""

import argparse
import copy
import hashlib
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from fractions import Fraction
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import organism_ledger


ROOT = Path(__file__).resolve().parent.parent
PARK_DIR = ROOT / "apps" / "agent-park"
STATE_PATH = PARK_DIR / "park-state.json"
EVENTS_PATH = PARK_DIR / "events.jsonl"
LEGACY_CONTRACT_PATH = PARK_DIR / "agent-contract.json"
CONTRACT_PATH = PARK_DIR / "agent-contract-v2.json"
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
STATE_SCHEMA = "rappterzoo-agent-amusement-park/2"
EVENT_SCHEMA_V1 = "rappterzoo-agent-park-event/1"
EVENT_SCHEMA = "rappterzoo-agent-park-event/2"
CONTRACT_SCHEMA = "rappterzoo-agent-park-contract/2"
EVENT_HASH_DOMAIN_V1 = b"rappterzoo/agent-park-event/1\n"
PAYLOAD_HASH_DOMAIN_V1 = b"rappterzoo/agent-park-payload/1\n"
EVENT_HASH_DOMAIN = b"rappterzoo/agent-park-event/2\n"
PAYLOAD_HASH_DOMAIN = b"rappterzoo/agent-park-payload/2\n"
STATE_HASH_DOMAIN = b"rappterzoo/agent-park-state/2\n"
CONTRACT_HASH_DOMAIN = b"rappterzoo/agent-park-contract/2\n"
BUNDLE_HASH_DOMAIN = b"rappterzoo/agent-park-bundle/2\n"
INVENTION_HASH_DOMAIN = b"rappterzoo/agent-park-invention/2\n"
FULL_EXPORT_HASH_DOMAIN = b"rappterzoo/agent-park-full-export/2\n"
LOCAL_ACTION_SCHEMA = "rappterzoo-agent-park-local-action/2"
BRANCH_EXPORT_SCHEMA = "rappterzoo-agent-park-local-branch/2"
FULL_EXPORT_SCHEMA = "rappterzoo-agent-park-full-export/2"
EVENT_KEYS_V1 = {
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
EVENT_KEYS = EVENT_KEYS_V1 | {"season", "season_seq"}
SEASON_ONE_PROFILE = 10
SEASON_ONE_EVENT_COUNT = 47
SEASON_ONE_HEAD = (
    "30acf1e7676d475f5a4a0ef0c69e124136e95c4e7ab486995bc10eed3315c352"
)
SEASON_ONE_PREFIX_SHA256 = (
    "fe725c0a2f1c39e47dcaf987e168274b5a0d1d8c30713af4d6c413ed47787a30"
)
LEGACY_CONTRACT_SHA256 = (
    "257fb02bceb20ca8d07ea9eb45809ab17262ba83e766da77e74cb893d1b3d06e"
)
SEASON_TWO = 2
VERIFIER_VERSION = "agent-amusement-park-verifier/2"
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
ROYALTY_ACCOUNT_ORDER = tuple(ROYALTY_BPS)
RESOURCE_GUARANTEE_BPS = 2500
MIN_POPULARITY_BPS = 500
RETIREMENT_STREAK_NIGHTS = 2
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


def _season_one_prefix_bytes(path: Path) -> bytes:
    try:
        lines = path.read_bytes().splitlines(keepends=True)
    except OSError as error:
        raise ParkError("cannot read {}: {}".format(path, error)) from error
    if len(lines) < SEASON_ONE_EVENT_COUNT:
        raise ParkError("published Season 1 event prefix is incomplete")
    prefix = b"".join(lines[:SEASON_ONE_EVENT_COUNT])
    if hashlib.sha256(prefix).hexdigest() != SEASON_ONE_PREFIX_SHA256:
        raise ParkError("published Season 1 event bytes changed")
    return prefix


def _season_one_events(root: Path) -> List[Dict[str, Any]]:
    path = root / "apps" / "agent-park" / "events.jsonl"
    _season_one_prefix_bytes(path)
    events = _load_events(path)[:SEASON_ONE_EVENT_COUNT]
    if (
        len(events) != SEASON_ONE_EVENT_COUNT
        or events[-1].get("event_hash") != SEASON_ONE_HEAD
    ):
        raise ParkError("published Season 1 event head changed")
    verify_events(events)
    return copy.deepcopy(events)


def _legacy_contract_bytes(root: Path) -> bytes:
    path = root / "apps" / "agent-park" / "agent-contract.json"
    try:
        value = path.read_bytes()
    except OSError as error:
        raise ParkError("cannot read {}: {}".format(path, error)) from error
    if hashlib.sha256(value).hexdigest() != LEGACY_CONTRACT_SHA256:
        raise ParkError("published v1 agent contract bytes changed")
    return value


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
            "preferences": ["time-travel", "hash", "memory"],
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
    for resource, capacity in RESOURCE_CAPACITY.items():
        requested = {
            bid["attraction_id"]: bid["requested"][resource]
            for bid in bids
        }
        if sum(requested.values()) <= capacity:
            for attraction_id, amount in requested.items():
                allocations[attraction_id][resource] = amount
            continue
        guaranteed = {
            attraction_id: max(
                1,
                (amount * RESOURCE_GUARANTEE_BPS) // 10000,
            )
            for attraction_id, amount in requested.items()
            if amount > 0
        }
        if sum(guaranteed.values()) > capacity:
            raise ParkError(
                "{} capacity cannot satisfy the fairness floor".format(
                    resource
                )
            )
        for attraction_id, amount in guaranteed.items():
            allocations[attraction_id][resource] = amount
        remaining = capacity - sum(guaranteed.values())
        bid_scores = {
            bid["attraction_id"]: bid["bid_score"]
            for bid in bids
        }
        extras = {attraction_id: 0 for attraction_id in requested}
        while remaining:
            candidates = [
                attraction_id
                for attraction_id in requested
                if allocations[attraction_id][resource]
                < requested[attraction_id]
            ]
            if not candidates:
                break
            winner = min(
                candidates,
                key=lambda attraction_id: (
                    -Fraction(
                        bid_scores[attraction_id],
                        extras[attraction_id] + 1,
                    ),
                    attraction_id,
                ),
            )
            allocations[winner][resource] += 1
            extras[winner] += 1
            remaining -= 1
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
) -> Tuple[Dict[str, int], List[Dict[str, Any]]]:
    admissions = {ride["id"]: 0 for ride in rides}
    cohort_demand = []
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
        cohort_demand.append({
            "allocations": [
                {
                    "admissions": primary,
                    "attraction_id": scored[0][1],
                    "rank": 1,
                },
                {
                    "admissions": secondary,
                    "attraction_id": scored[1][1],
                    "rank": 2,
                },
            ],
            "cohort_id": cohort["id"],
            "population": cohort["population"],
            "preferences": copy.deepcopy(cohort["preferences"]),
        })
    return admissions, cohort_demand


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
    remainders = {}
    for account in ROYALTY_ACCOUNT_ORDER:
        shares[account], remainders[account] = divmod(
            gross * ROYALTY_BPS[account],
            10000,
        )
    unallocated = gross - sum(shares.values())
    ranked = sorted(
        ROYALTY_ACCOUNT_ORDER,
        key=lambda account: (
            -remainders[account],
            ROYALTY_ACCOUNT_ORDER.index(account),
        ),
    )
    for account in ranked[:unallocated]:
        shares[account] += 1
    return shares


def _append_event(
    events: List[Dict[str, Any]],
    kind: str,
    payload: Dict[str, Any],
    utc: str,
    season: int = SEASON_TWO,
) -> Dict[str, Any]:
    if season != SEASON_TWO:
        raise ParkError("new park events must use the Season 2 schema")
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
        "season": season,
        "season_seq": sum(
            1
            for event in events
            if event.get("season", 1) == season
        ),
        "seq": len(events),
        "utc": utc,
        "visibility": "public-metadata",
    }
    value["event_hash"] = _canonical_digest(EVENT_HASH_DOMAIN, value)
    events.append(value)
    return value


def _timestamp(night: int, minute: int) -> str:
    base = datetime(2026, 8, 23, tzinfo=timezone.utc)
    value = base + timedelta(days=max(0, night - 1), minutes=minute)
    return value.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _event_season(event: Dict[str, Any]) -> int:
    return event.get("season", 1)


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
    projected["integrity"].pop("bundle_digest", None)
    return projected


def _contract_without_digest(value: Dict[str, Any]) -> Dict[str, Any]:
    projected = copy.deepcopy(value)
    projected["integrity"].pop("contract_digest", None)
    projected["integrity"].pop("bundle_digest", None)
    return projected


def _bundle_digest(
    event_count: int,
    event_head: str,
    event_ledger_sha256: str,
    state_digest: str,
    contract_digest: str,
) -> str:
    return _canonical_digest(
        BUNDLE_HASH_DOMAIN,
        {
            "contract_digest": contract_digest,
            "event_count": event_count,
            "event_head": event_head,
            "event_ledger_sha256": event_ledger_sha256,
            "state_digest": state_digest,
        },
    )


def build_bundle(
    root: Path = ROOT,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]], Dict[str, Any]]:
    anchor = _anchor_frame(root)
    _legacy_contract_bytes(root)
    rides = _initial_attractions()
    poor_streaks = {ride["id"]: 0 for ride in rides}
    evolution_counts = {ride["id"]: 0 for ride in rides}
    events = _season_one_events(root)
    postings: List[Dict[str, Any]] = []
    snapshots = []
    inventions = []
    retirements = []
    evolutions = []

    _append_event(
        events,
        "park.season-open",
        {
            "anchor_frame_hash": ANCHOR_FRAME_HASH,
            "app_file": APP_FILE,
            "display_name": PARK_TITLE,
            "economy": "synthetic-credit-only",
            "organism_time_travel_source": "apps/organism-frames.jsonl",
            "previous_season_head": SEASON_ONE_HEAD,
            "season": SEASON_TWO,
            "season_one_profile": SEASON_ONE_PROFILE,
        },
        "2026-08-22T23:50:00.000Z",
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
            "season": SEASON_TWO,
            "synthetic_currency": True,
        },
        "2026-08-22T23:51:00.000Z",
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
                "algorithm": "guaranteed-floor-weighted-fair-queue/1",
                "allocations": allocations,
                "bids": bids,
                "capacity": RESOURCE_CAPACITY,
                "guaranteed_request_bps": RESOURCE_GUARANTEE_BPS,
                "night": night,
            },
            _timestamp(night, minute),
        )
        minute += 1
        admissions, cohort_demand = _cohort_admissions(
            active,
            allocations,
            night,
        )
        total_admissions = sum(admissions.values())
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
            if ride_gross:
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
                if amount == 0:
                    continue
                posting = {
                    "amount": amount,
                    "basis_points": ROYALTY_BPS[share],
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
            popularity_bps = (
                (ride_admissions * 10000) // total_admissions
                if total_admissions
                else 0
            )
            metrics[ride["id"]] = {
                "admissions": ride_admissions,
                "allocation_ratio_bps": ratio,
                "gross_credits": ride_gross,
                "popularity_bps": popularity_bps,
                "royalty_split": split,
                "satisfaction": satisfaction,
            }
            ride["last_metrics"] = copy.deepcopy(metrics[ride["id"]])
            poor = (
                satisfaction < 45
                or popularity_bps < MIN_POPULARITY_BPS
            )
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
                "cohort_demand": cohort_demand,
                "currency": "synthetic-credit",
                "gross_credits": gross,
                "night": night,
                "population": total_admissions,
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
                "rounding_policy": "largest-remainder/1",
                "royalty_credits": royalty_total,
            },
            _timestamp(night, minute),
        )
        minute += 1

        night_retirements = []
        for ride in active:
            if (
                poor_streaks.get(ride["id"], 0)
                < RETIREMENT_STREAK_NIGHTS
            ):
                continue
            ride["status"] = "retired"
            ride["retired_night"] = night
            retirement = {
                "attraction_id": ride["id"],
                "night": night,
                "reason": (
                    "two-consecutive-low-popularity-or-"
                    "satisfaction-nights"
                ),
                "season": SEASON_TWO,
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
            provenance = {
                "algorithm": "deterministic-agent-design-tournament/1",
                "anchor_frame_hash": ANCHOR_FRAME_HASH,
                "night": night,
                "template_version": 1,
            }
            provenance["design_digest"] = _canonical_digest(
                INVENTION_HASH_DOMAIN,
                {
                    "attraction": invented,
                    "provenance": provenance,
                },
            )
            night_invention = {
                "attraction": copy.deepcopy(invented),
                "night": night,
                "provenance": provenance,
                "season": SEASON_TWO,
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
            "season": SEASON_TWO,
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
            "cohort_demand": copy.deepcopy(cohort_demand),
            "economy": {
                "gross_credits": gross,
                "royalty_credits": royalty_total,
            },
            "end_event_seq": len(events),
            "evolution": copy.deepcopy(evolution),
            "invention": copy.deepcopy(night_invention),
            "night": night,
            "popularity": {
                attraction_id: item["popularity_bps"]
                for attraction_id, item in metrics.items()
            },
            "resource_allocations": copy.deepcopy(allocations),
            "retirements": copy.deepcopy(night_retirements),
            "season": SEASON_TWO,
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

    total_debits = sum(
        posting["amount"]
        for posting in postings
        if posting.get("debit_account")
    )
    total_credits = sum(
        posting["amount"]
        for posting in postings
        if posting.get("credit_account")
    )
    event_bytes = _event_bytes(events)
    contract = {
        "action_limit": {
            "canonical_writes_per_session": 0,
            "first_visit_recommended_local_actions": 1,
            "max_local_actions_per_mcp_session": 100,
            "max_resource_units_per_field": 10000,
            "max_synthetic_bid": 1000000,
        },
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
        "branch_export": {
            "action_additional_properties": False,
            "action_required_fields": [
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
            ],
            "action_schema": LOCAL_ACTION_SCHEMA,
            "canonical_write": False,
            "digest_field": "branch_digest",
            "export_additional_properties": False,
            "export_schema": BRANCH_EXPORT_SCHEMA,
            "required_fields": [
                "export_schema",
                "park_id",
                "canonical_write",
                "canonical_event_head",
                "canonical_organism_head",
                "action_limit",
                "actions",
                "authority",
                "branch_digest",
            ],
        },
        "canonicalization_and_hashing": {
            "canonical_json": {
                "arrays": "preserve-input-order",
                "booleans_and_null": "lowercase-json-literals",
                "encoding": "utf-8",
                "floats": "forbidden",
                "integers": "I-JSON-safe-base-10",
                "max_canonical_bytes": 1048576,
                "name": "restricted-rfc8785-compatible-profile",
                "object_keys": "ASCII-only-NFC-lexicographic",
                "separators": [",", ":"],
                "strings": "NFC-normalized",
                "trailing_newline": False,
            },
            "mcp_local_branch_json": {
                "encoding": "utf-8",
                "ensure_ascii": False,
                "object_keys": "lexicographic",
                "separators": [",", ":"],
                "trailing_newline": False,
            },
            "hash_domains": {
                "bundle_v2": BUNDLE_HASH_DOMAIN.decode("utf-8"),
                "contract_v2": CONTRACT_HASH_DOMAIN.decode("utf-8"),
                "event_v1": EVENT_HASH_DOMAIN_V1.decode("utf-8"),
                "event_v2": EVENT_HASH_DOMAIN.decode("utf-8"),
                "full_export_v2": FULL_EXPORT_HASH_DOMAIN.decode("utf-8"),
                "invention_v2": INVENTION_HASH_DOMAIN.decode("utf-8"),
                "payload_v1": PAYLOAD_HASH_DOMAIN_V1.decode("utf-8"),
                "payload_v2": PAYLOAD_HASH_DOMAIN.decode("utf-8"),
                "state_v2": STATE_HASH_DOMAIN.decode("utf-8"),
            },
            "preimages": {
                "branch_digest": {
                    "bytes": [
                        "mcp_local_branch_json({export_schema,park_id,"
                        "canonical_write,canonical_event_head,"
                        "canonical_organism_head,action_limit,actions,"
                        "authority})"
                    ],
                    "digest": "sha256",
                    "domain_prefix": False,
                },
                "bundle_digest": {
                    "bytes": [
                        "utf8(hash_domains.bundle_v2)",
                        "canonical_json({contract_digest,event_count,"
                        "event_head,event_ledger_sha256,state_digest})",
                    ],
                    "digest": "sha256",
                },
                "contract_digest": {
                    "bytes": [
                        "utf8(hash_domains.contract_v2)",
                        "canonical_json(contract excluding "
                        "integrity.contract_digest and "
                        "integrity.bundle_digest)",
                    ],
                    "digest": "sha256",
                },
                "event_hash": {
                    "bytes": [
                        "utf8(hash_domains.event_v1 or event_v2 by schema)",
                        "canonical_json(event excluding event_hash)",
                    ],
                    "digest": "sha256",
                },
                "event_ledger_sha256": {
                    "bytes": [
                        "for each event in seq order: canonical_json(event)",
                        "single LF byte after every event including the last",
                    ],
                    "digest": "sha256",
                    "domain_prefix": False,
                },
                "invention_design_digest": {
                    "bytes": [
                        "utf8(hash_domains.invention_v2)",
                        "canonical_json({attraction,provenance excluding "
                        "design_digest})",
                    ],
                    "digest": "sha256",
                },
                "full_export_content_digest": {
                    "bytes": [
                        "utf8(hash_domains.full_export_v2)",
                        "canonical_json({export_schema,park_id,"
                        "canonical_write,park_events,organism_frames,state,"
                        "contract,bundle,authority})",
                    ],
                    "digest": "sha256",
                },
                "local_action_hash": {
                    "bytes": [
                        "mcp_local_branch_json({schema,seq,kind,prev,"
                        "source,source_hash,payload,payload_hash,"
                        "canonical_write})"
                    ],
                    "digest": "sha256",
                    "domain_prefix": False,
                },
                "local_action_payload_hash": {
                    "bytes": ["mcp_local_branch_json(action.payload)"],
                    "digest": "sha256",
                    "domain_prefix": False,
                },
                "local_action_source_hash": {
                    "park": "copy the selected canonical park event's "
                    "event_hash",
                    "organism": "copy the selected canonical organism "
                    "frame's frame_hash",
                    "rehash": False,
                },
                "payload_hash": {
                    "bytes": [
                        "utf8(hash_domains.payload_v1 or payload_v2 by schema)",
                        "canonical_json(event.payload)",
                    ],
                    "digest": "sha256",
                },
                "state_digest": {
                    "bytes": [
                        "utf8(hash_domains.state_v2)",
                        "canonical_json(state excluding "
                        "integrity.state_digest and integrity.bundle_digest)",
                    ],
                    "digest": "sha256",
                },
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
        "full_export": {
            "canonical_write": False,
            "content_digest_field": "content_digest",
            "export_additional_properties": False,
            "export_schema": FULL_EXPORT_SCHEMA,
            "replay_requirements": {
                "bundle": {
                    "required_fields": [
                        "event_count",
                        "event_head",
                        "event_ledger_sha256",
                        "state_digest",
                        "contract_digest",
                        "bundle_digest",
                    ],
                    "verify_all_digests": True,
                },
                "contract": {
                    "include_complete_v2_document": True,
                    "include_legacy_v1_bytes": True,
                    "legacy_v1_sha256": LEGACY_CONTRACT_SHA256,
                    "v2_schema": CONTRACT_SCHEMA,
                    "verify_contract_and_bundle_digests": True,
                },
                "organism": {
                    "complete_through_declared_head": True,
                    "include_public_frames": True,
                    "verify_seq_prev_payload_and_frame_hashes": True,
                },
                "park": {
                    "complete_from_seq": 0,
                    "current_event_count": len(events),
                    "current_head": events[-1]["event_hash"],
                    "include_all_events": True,
                    "preserve_season_one_prefix": {
                        "event_count": SEASON_ONE_EVENT_COUNT,
                        "head": SEASON_ONE_HEAD,
                        "sha256": SEASON_ONE_PREFIX_SHA256,
                    },
                    "verify_seq_prev_utc_payload_and_event_hashes": True,
                },
                "state": {
                    "include_complete_projection": True,
                    "must_point_to_exported_park_ledger": True,
                    "verify_state_digest": True,
                },
            },
            "required_fields": [
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
            ],
        },
        "integrity": {
            "algorithm": "sha256",
            "bundle_digest": "",
            "contract_digest": "",
        },
        "legacy_contract": {
            "immutable": True,
            "path": "agent-contract.json",
            "schema": "rappterzoo-agent-park-contract/1",
            "sha256": LEGACY_CONTRACT_SHA256,
        },
        "mcp_mapping": {
            "protocol_version": "2024-11-05",
            "resource_uris": {
                "contract": "rappterzoo://agent-park-contract",
                "events": "rappterzoo://agent-park-events",
                "guide": "rappterzoo://agent-park-guide",
                "state": "rappterzoo://agent-park-state",
            },
            "tools": {
                "bid_for_resources": "agent_park_local_action",
                "export_branch": "agent_park_export_branch",
                "invent_attraction": "agent_park_local_action",
                "time_travel": "agent_park_time_travel",
                "visit": "agent_park_local_action",
            },
        },
        "park_id": PARK_ID,
        "resources": {
            "contract_v1": "agent-contract.json",
            "contract_v2": "agent-contract-v2.json",
            "event_ledger": "events.jsonl",
            "organism_time_travel": "../organism-frames.jsonl",
            "state_projection": "park-state.json",
        },
        "schema": CONTRACT_SCHEMA,
        "seasons": {
            "latest": SEASON_TWO,
            "season_1": {
                "event_count": SEASON_ONE_EVENT_COUNT,
                "head": SEASON_ONE_HEAD,
                "immutable_prefix_sha256": SEASON_ONE_PREFIX_SHA256,
                "profile": SEASON_ONE_PROFILE,
                "schema": EVENT_SCHEMA_V1,
            },
            "season_2": {
                "event_count": len(events) - SEASON_ONE_EVENT_COUNT,
                "first_seq": SEASON_ONE_EVENT_COUNT,
                "head": events[-1]["event_hash"],
                "schema": EVENT_SCHEMA,
            },
        },
        "verifier": {
            "command": "python3 scripts/agent_amusement_park.py verify",
            "fail_closed": True,
            "version": VERIFIER_VERSION,
        },
        "visibility": "public-metadata",
        "write_default": "local-branch-only",
    }
    contract["integrity"]["contract_digest"] = _canonical_digest(
        CONTRACT_HASH_DOMAIN,
        _contract_without_digest(contract),
    )
    season_two_events = events[SEASON_ONE_EVENT_COUNT:]
    state = {
        "agent_contract": "agent-contract-v2.json",
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
            "bundle_digest": "",
            "event_chain_verified": True,
            "state_digest": "",
        },
        "latest_season": SEASON_TWO,
        "legacy_agent_contract": "agent-contract.json",
        "night_count": NIGHT_COUNT,
        "nights": snapshots,
        "park_id": PARK_ID,
        "retirement_policy": {
            "consecutive_nights": RETIREMENT_STREAK_NIGHTS,
            "popularity_below_bps": MIN_POPULARITY_BPS,
            "satisfaction_below": 45,
        },
        "resource_capacity": RESOURCE_CAPACITY,
        "schema": STATE_SCHEMA,
        "season": SEASON_TWO,
        "seasons": [
            {
                "end_utc": events[SEASON_ONE_EVENT_COUNT - 1]["utc"],
                "event_count": SEASON_ONE_EVENT_COUNT,
                "first_seq": 0,
                "head": SEASON_ONE_HEAD,
                "immutable": True,
                "ledger_prefix_sha256": SEASON_ONE_PREFIX_SHA256,
                "last_seq": SEASON_ONE_EVENT_COUNT - 1,
                "profile": SEASON_ONE_PROFILE,
                "schema": EVENT_SCHEMA_V1,
                "season": 1,
                "start_utc": events[0]["utc"],
            },
            {
                "end_utc": season_two_events[-1]["utc"],
                "event_count": len(season_two_events),
                "first_seq": SEASON_ONE_EVENT_COUNT,
                "head": season_two_events[-1]["event_hash"],
                "immutable": False,
                "last_seq": len(events) - 1,
                "schema": EVENT_SCHEMA,
                "season": SEASON_TWO,
                "start_utc": season_two_events[0]["utc"],
            },
        ],
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
    binding_digest = _bundle_digest(
        len(events),
        events[-1]["event_hash"],
        hashlib.sha256(event_bytes).hexdigest(),
        state["integrity"]["state_digest"],
        contract["integrity"]["contract_digest"],
    )
    state["integrity"]["bundle_digest"] = binding_digest
    contract["integrity"]["bundle_digest"] = binding_digest
    return state, events, contract


def verify_events(events: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    if len(events) < SEASON_ONE_EVENT_COUNT:
        raise ParkError("published Season 1 event prefix is incomplete")
    previous = None
    previous_utc = None
    for index, event in enumerate(events):
        season = 1 if index < SEASON_ONE_EVENT_COUNT else SEASON_TWO
        expected_keys = EVENT_KEYS_V1 if season == 1 else EVENT_KEYS
        expected_schema = (
            EVENT_SCHEMA_V1 if season == 1 else EVENT_SCHEMA
        )
        payload_domain = (
            PAYLOAD_HASH_DOMAIN_V1
            if season == 1
            else PAYLOAD_HASH_DOMAIN
        )
        event_domain = (
            EVENT_HASH_DOMAIN_V1
            if season == 1
            else EVENT_HASH_DOMAIN
        )
        if type(event) is not dict or set(event) != expected_keys:
            raise ParkError(
                "park event {} does not have the exact key set".format(index)
            )
        if event["schema"] != expected_schema:
            raise ParkError("park event schema mismatch")
        if season == SEASON_TWO and (
            event["season"] != SEASON_TWO
            or event["season_seq"] != index - SEASON_ONE_EVENT_COUNT
        ):
            raise ParkError("park Season 2 sequence is not contiguous")
        if event["park_id"] != PARK_ID:
            raise ParkError("park event belongs to another park")
        if event["visibility"] != "public-metadata":
            raise ParkError("park event is not public metadata")
        if event["seq"] != index:
            raise ParkError("park event sequence is not contiguous")
        try:
            parsed_utc = datetime.strptime(
                event["utc"],
                "%Y-%m-%dT%H:%M:%S.%fZ",
            ).replace(tzinfo=timezone.utc)
        except (TypeError, ValueError) as error:
            raise ParkError("park event UTC is invalid") from error
        canonical_utc = (
            parsed_utc.isoformat(timespec="milliseconds")
            .replace("+00:00", "Z")
        )
        if event["utc"] != canonical_utc:
            raise ParkError("park event UTC is not canonical milliseconds")
        if previous_utc is not None and parsed_utc <= previous_utc:
            raise ParkError("park event UTC is not strictly increasing")
        if event["prev"] != (
            previous["event_hash"] if previous else None
        ):
            raise ParkError("park event chain is broken")
        expected_payload = _canonical_digest(
            payload_domain,
            event["payload"],
        )
        if event["payload_hash"] != expected_payload:
            raise ParkError("park event payload hash mismatch")
        projected = {
            key: copy.deepcopy(value)
            for key, value in event.items()
            if key != "event_hash"
        }
        expected_event = _canonical_digest(event_domain, projected)
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
        previous_utc = parsed_utc
    if events[SEASON_ONE_EVENT_COUNT - 1]["event_hash"] != SEASON_ONE_HEAD:
        raise ParkError("published Season 1 event head changed")
    return {
        "event_count": len(events),
        "head": events[-1]["event_hash"] if events else None,
        "season_one_event_count": SEASON_ONE_EVENT_COUNT,
        "season_two_event_count": len(events) - SEASON_ONE_EVENT_COUNT,
    }


def _verify_bundle_digests(
    state: Dict[str, Any],
    events: Sequence[Dict[str, Any]],
    contract: Dict[str, Any],
) -> None:
    try:
        event_bytes = _event_bytes(events)
        event_sha256 = hashlib.sha256(event_bytes).hexdigest()
        event_head = events[-1]["event_hash"]
        if state["event_ledger"]["event_count"] != len(events):
            raise ParkError("park state event count mismatch")
        if state["event_ledger"]["head"] != event_head:
            raise ParkError("park state points to the wrong event head")
        if state["event_ledger"]["sha256"] != event_sha256:
            raise ParkError("park state event ledger digest mismatch")
        expected_state_digest = _canonical_digest(
            STATE_HASH_DOMAIN,
            _state_without_digest(state),
        )
        if state["integrity"]["state_digest"] != expected_state_digest:
            raise ParkError("park state digest mismatch")
        expected_contract_digest = _canonical_digest(
            CONTRACT_HASH_DOMAIN,
            _contract_without_digest(contract),
        )
        if (
            contract["integrity"]["contract_digest"]
            != expected_contract_digest
        ):
            raise ParkError("park contract digest mismatch")
        expected_bundle_digest = _bundle_digest(
            len(events),
            event_head,
            event_sha256,
            expected_state_digest,
            expected_contract_digest,
        )
        if (
            state["integrity"]["bundle_digest"]
            != expected_bundle_digest
            or contract["integrity"]["bundle_digest"]
            != expected_bundle_digest
        ):
            raise ParkError("park bundle digest binding mismatch")
    except (IndexError, KeyError, TypeError) as error:
        raise ParkError("park bundle integrity fields are malformed") from error


def _verify_resource_events(events: Sequence[Dict[str, Any]]) -> None:
    resource_events = [
        event
        for event in events
        if (
            _event_season(event) == SEASON_TWO
            and event["kind"] == "park.resource-negotiation"
        )
    ]
    if len(resource_events) != NIGHT_COUNT:
        raise ParkError("park resource negotiation count mismatch")
    for event in resource_events:
        payload = event["payload"]
        if (
            payload.get("algorithm")
            != "guaranteed-floor-weighted-fair-queue/1"
            or payload.get("guaranteed_request_bps")
            != RESOURCE_GUARANTEE_BPS
            or payload.get("capacity") != RESOURCE_CAPACITY
        ):
            raise ParkError("park resource fairness policy drifted")
        bids = payload.get("bids", [])
        allocations = payload.get("allocations", {})
        bid_ids = [bid.get("attraction_id") for bid in bids]
        if (
            len(bid_ids) != len(set(bid_ids))
            or set(bid_ids) != set(allocations)
        ):
            raise ParkError("park resource bids are incomplete")
        for resource, capacity in RESOURCE_CAPACITY.items():
            requested_total = sum(
                bid["requested"][resource]
                for bid in bids
            )
            allocated_total = 0
            for bid in bids:
                attraction_id = bid["attraction_id"]
                requested = bid["requested"][resource]
                allocated = allocations[attraction_id][resource]
                if (
                    type(requested) is not int
                    or type(allocated) is not int
                    or requested < 0
                    or allocated < 0
                    or allocated > requested
                ):
                    raise ParkError("park resource allocation is invalid")
                allocated_total += allocated
                if requested_total > capacity and requested:
                    guaranteed = max(
                        1,
                        (requested * RESOURCE_GUARANTEE_BPS) // 10000,
                    )
                    if allocated < guaranteed:
                        raise ParkError(
                            "park resource fairness floor was violated"
                        )
            if allocated_total != min(requested_total, capacity):
                raise ParkError("park resource capacity was not fully used")


def _verify_economy_events(
    state: Dict[str, Any],
    events: Sequence[Dict[str, Any]],
) -> None:
    settlement_events = [
        event
        for event in events
        if (
            _event_season(event) == SEASON_TWO
            and event["kind"] == "park.royalty-settlement"
        )
    ]
    if len(settlement_events) != NIGHT_COUNT:
        raise ParkError("park royalty settlement count mismatch")
    all_postings = []
    for event in settlement_events:
        payload = event["payload"]
        if (
            payload.get("basis_points") != ROYALTY_BPS
            or payload.get("rounding_policy") != "largest-remainder/1"
        ):
            raise ParkError("park royalty policy drifted")
        admission_by_ride = {}
        royalty_by_ride: Dict[str, Dict[str, int]] = {}
        for posting in payload.get("postings", []):
            if (
                type(posting.get("amount")) is not int
                or posting["amount"] <= 0
            ):
                raise ParkError("park posting amount is not positive")
            all_postings.append(posting)
            ride_id = posting.get("ride_id")
            if posting.get("kind") == "synthetic-admission":
                if ride_id in admission_by_ride:
                    raise ParkError("duplicate park admission posting")
                admission_by_ride[ride_id] = posting["amount"]
            elif posting.get("kind") == "synthetic-royalty":
                share = posting.get("share")
                if (
                    share not in ROYALTY_BPS
                    or posting.get("basis_points")
                    != ROYALTY_BPS[share]
                ):
                    raise ParkError("park royalty basis points mismatch")
                ride_shares = royalty_by_ride.setdefault(ride_id, {})
                if share in ride_shares:
                    raise ParkError("duplicate park royalty posting")
                ride_shares[share] = posting["amount"]
            else:
                raise ParkError("park posting kind is invalid")
        if sum(admission_by_ride.values()) != payload["gross_credits"]:
            raise ParkError("park admission postings do not equal gross")
        expected_royalty_total = 0
        for ride_id, gross in admission_by_ride.items():
            expected = _split_royalty(gross)
            actual = {
                share: royalty_by_ride.get(ride_id, {}).get(share, 0)
                for share in ROYALTY_BPS
            }
            if actual != expected:
                raise ParkError("park royalty split is not exact")
            expected_royalty_total += (
                expected["creator"]
                + expected["open_protocol"]
                + expected["resource_pool"]
            )
        if set(royalty_by_ride) - set(admission_by_ride):
            raise ParkError("park royalty lacks an admission basis")
        if payload["royalty_credits"] != expected_royalty_total:
            raise ParkError("park royalty total is inconsistent")
    accounts = _account_totals(all_postings)
    if state["economy"]["accounts"] != accounts:
        raise ParkError("park account projection is inconsistent")
    total_debits = sum(posting["amount"] for posting in all_postings)
    total_credits = sum(posting["amount"] for posting in all_postings)
    if (
        state["economy"]["total_debits"] != total_debits
        or state["economy"]["total_credits"] != total_credits
        or total_debits != total_credits
    ):
        raise ParkError("park synthetic double-entry totals differ")


def _verify_cohort_demand(events: Sequence[Dict[str, Any]]) -> None:
    expected_cohorts = {
        cohort["id"]: cohort
        for cohort in _visitor_cohorts()
    }
    admission_events = [
        event
        for event in events
        if (
            _event_season(event) == SEASON_TWO
            and event["kind"] == "park.admission-settlement"
        )
    ]
    if len(admission_events) != NIGHT_COUNT:
        raise ParkError("park admission settlement count mismatch")
    for event in admission_events:
        payload = event["payload"]
        aggregate = {
            attraction_id: 0
            for attraction_id in payload["admissions"]
        }
        seen = set()
        population = 0
        for cohort in payload.get("cohort_demand", []):
            cohort_id = cohort.get("cohort_id")
            if cohort_id in seen or cohort_id not in expected_cohorts:
                raise ParkError("park cohort demand identity mismatch")
            seen.add(cohort_id)
            expected = expected_cohorts[cohort_id]
            if (
                cohort.get("population") != expected["population"]
                or cohort.get("preferences") != expected["preferences"]
            ):
                raise ParkError("park cohort demand metadata mismatch")
            allocated = sum(
                choice.get("admissions", 0)
                for choice in cohort.get("allocations", [])
            )
            if allocated != cohort["population"]:
                raise ParkError("park cohort demand was not conserved")
            population += allocated
            for choice in cohort["allocations"]:
                attraction_id = choice.get("attraction_id")
                if attraction_id not in aggregate:
                    raise ParkError("park cohort selected an inactive ride")
                aggregate[attraction_id] += choice["admissions"]
        if seen != set(expected_cohorts):
            raise ParkError("park cohort demand evidence is incomplete")
        if (
            aggregate != payload["admissions"]
            or population != payload.get("population")
            or population != sum(payload["admissions"].values())
        ):
            raise ParkError("park cohort demand projection mismatch")


def _verify_invention_provenance(state: Dict[str, Any]) -> None:
    for invention in state["evolution"]["inventions"]:
        try:
            provenance = copy.deepcopy(invention["provenance"])
            design_digest = provenance.pop("design_digest")
            expected = _canonical_digest(
                INVENTION_HASH_DOMAIN,
                {
                    "attraction": invention["attraction"],
                    "provenance": provenance,
                },
            )
        except (KeyError, TypeError) as error:
            raise ParkError("park invention provenance is malformed") from error
        if (
            design_digest != expected
            or provenance.get("anchor_frame_hash") != ANCHOR_FRAME_HASH
            or provenance.get("night") != invention.get("night")
        ):
            raise ParkError("park invention provenance mismatch")


def verify_bundle(
    state: Dict[str, Any],
    events: Sequence[Dict[str, Any]],
    contract: Dict[str, Any],
    root: Path = ROOT,
) -> Dict[str, Any]:
    event_result = verify_events(events)
    _season_one_prefix_bytes(
        root / "apps" / "agent-park" / "events.jsonl"
    )
    _legacy_contract_bytes(root)
    if state.get("schema") != STATE_SCHEMA:
        raise ParkError("park state schema mismatch")
    if contract.get("schema") != CONTRACT_SCHEMA:
        raise ParkError("park contract schema mismatch")
    _verify_bundle_digests(state, events, contract)
    try:
        _verify_resource_events(events)
        _verify_economy_events(state, events)
        _verify_cohort_demand(events)
        _verify_invention_provenance(state)
    except (AttributeError, IndexError, KeyError, TypeError) as error:
        raise ParkError("park semantic evidence is malformed") from error
    expected_state, expected_events, expected_contract = build_bundle(root)
    if list(events) != expected_events:
        raise ParkError("park event ledger is stale or mutated")
    if state != expected_state:
        raise ParkError("park state projection is stale or mutated")
    if contract != expected_contract:
        raise ParkError("park agent contract is stale or mutated")
    if state["night_count"] != NIGHT_COUNT:
        raise ParkError("park does not contain seven simulated nights")
    if (
        state.get("latest_season") != SEASON_TWO
        or state.get("season") != SEASON_TWO
        or state["seasons"][0]["head"] != SEASON_ONE_HEAD
        or state["seasons"][0]["event_count"] != SEASON_ONE_EVENT_COUNT
        or state["seasons"][1]["first_seq"] != SEASON_ONE_EVENT_COUNT
        or state["seasons"][1]["event_count"]
        != len(events) - SEASON_ONE_EVENT_COUNT
    ):
        raise ParkError("park season metadata drifted")
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
        "season_one_event_count": SEASON_ONE_EVENT_COUNT,
        "season_two_event_count": (
            len(events) - SEASON_ONE_EVENT_COUNT
        ),
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
    _atomic_bytes(
        target / "agent-contract-v2.json",
        _pretty_bytes(contract),
    )
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
        root / "apps" / "agent-park" / "agent-contract-v2.json"
    )
    verify_bundle(state, events, contract, root)
    manifest = _load_json(root / "apps" / "manifest.json")
    if _manifest_app(manifest) is None:
        raise ParkError("agent amusement park is absent from the manifest")
    payload = {
        "app_file": APP_FILE,
        "bundle_digest": state["integrity"]["bundle_digest"],
        "customer_controls": [
            "customer-local-key-custody",
            "full-ledger-export",
            "operator-model-choice",
            "immediate-shutdown",
        ],
        "display_name": PARK_TITLE,
        "event": "experience-release",
        "event_id": "experience-release:agent-amusement-park:{}".format(
            state["integrity"]["bundle_digest"]
        ),
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
        "zoo.mutation",
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

#!/usr/bin/env python3
"""User-initiated local-first client for RappterZoo syndicated deltas."""

import argparse
import copy
import hashlib
import json
import os
import re
import shutil
import sqlite3
import sys
import unicodedata
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows fallback
    fcntl = None
    import msvcrt


DEFAULT_INDEX_URL = (
    "https://kody-w.github.io/localFirstTools-main/"
    "apps/syndication/index.json"
)
DEFAULT_STREAM_ID = (
    "https://kody-w.github.io/localFirstTools-main/apps/syndication/"
)
DEFAULT_STATE_DIR = Path.home() / ".rappterzoo-sync"
INDEX_SCHEMA = "rappterzoo-syndication-index/1"
DELTA_SCHEMA = "rappterzoo-syndication-delta/1"
PROFILE_V2 = "rappterzoo-syndication-profile/2"
PROFILE_V3 = "rappterzoo-syndication-profile/3"
PROFILE_V4 = "rappterzoo-syndication-profile/4"
PROFILE_V5 = "rappterzoo-syndication-profile/5"
PROFILE_V6 = "rappterzoo-syndication-profile/6"
PROFILE_V7 = "rappterzoo-syndication-profile/7"
PROFILE_V8 = "rappterzoo-syndication-profile/8"
PROFILE_V9 = "rappterzoo-syndication-profile/9"
PROFILE = "rappterzoo-syndication-profile/10"
AGENT_PARK_PAYLOAD_SPACE = "rappterzoo/agent-park-payload/1"
AGENT_PARK_EVENT_SPACE = "rappterzoo/agent-park-event/1"
AGENT_PARK_EVENT_SCHEMA = "rappterzoo-agent-park-event/1"
AGENT_PARK_PAYLOAD_SPACE_V2 = "rappterzoo/agent-park-payload/2"
AGENT_PARK_EVENT_SPACE_V2 = "rappterzoo/agent-park-event/2"
AGENT_PARK_EVENT_SCHEMA_V2 = "rappterzoo-agent-park-event/2"
AGENT_PARK_CONTRACT_V1_SCHEMA = "rappterzoo-agent-park-contract/1"
AGENT_PARK_CONTRACT_V2_SCHEMA = "rappterzoo-agent-park-contract/2"
AGENT_PARK_CONTRACT_V2_HASH_SPACE = "rappterzoo/agent-park-contract/2"
AGENT_PARK_STATE_V2_HASH_SPACE = "rappterzoo/agent-park-state/2"
AGENT_PARK_BUNDLE_V2_HASH_SPACE = "rappterzoo/agent-park-bundle/2"
AGENT_PARK_SEASON1_EVENT_COUNT = 47
AGENT_PARK_SEASON1_PREFIX_SHA256 = (
    "fe725c0a2f1c39e47dcaf987e168274b5a0d1d8c30713af4d6c413ed47787a30"
)
AGENT_PARK_SEASON1_HEAD = (
    "30acf1e7676d475f5a4a0ef0c69e124136e95c4e7ab486995bc10eed3315c352"
)
AGENT_PARK_V2_ACTION_LIMIT = {
    "canonical_writes_per_session": 0,
    "first_visit_recommended_local_actions": 1,
    "max_local_actions_per_mcp_session": 100,
    "max_resource_units_per_field": 10000,
    "max_synthetic_bid": 1000000,
}
AGENT_PARK_V2_MCP_MAPPING = {
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
}
AGENT_PARK_V2_HASH_DOMAINS = {
    "bundle_v2": AGENT_PARK_BUNDLE_V2_HASH_SPACE + "\n",
    "contract_v2": AGENT_PARK_CONTRACT_V2_HASH_SPACE + "\n",
    "event_v1": AGENT_PARK_EVENT_SPACE + "\n",
    "event_v2": AGENT_PARK_EVENT_SPACE_V2 + "\n",
    "full_export_v2": "rappterzoo/agent-park-full-export/2\n",
    "invention_v2": "rappterzoo/agent-park-invention/2\n",
    "payload_v1": AGENT_PARK_PAYLOAD_SPACE + "\n",
    "payload_v2": AGENT_PARK_PAYLOAD_SPACE_V2 + "\n",
    "state_v2": AGENT_PARK_STATE_V2_HASH_SPACE + "\n",
}
AGENT_PARK_V2_CANONICAL_JSON = {
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
}
AGENT_PARK_EVENT_KEYS = {
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
AGENT_PARK_EVENT_V2_KEYS = AGENT_PARK_EVENT_KEYS | {
    "season",
    "season_seq",
}
AGENT_FAIR_STATE_SCHEMA = "rappterzoo-agent-worlds-fair-state/1"
AGENT_FAIR_EVENT_SCHEMA = "rappterzoo-agent-worlds-fair-event/1"
AGENT_FAIR_CONTRACT_SCHEMA = "rappterzoo-agent-worlds-fair-contract/1"
AGENT_FAIR_DISTRICT_SCHEMA = "rappterzoo-agent-worlds-fair-district/1"
AGENT_FAIR_ID = "fair.agent-worlds-fair-1"
AGENT_FAIR_DISTRICT_ID = "district.agent-worlds-fair-1"
AGENT_FAIR_PAYLOAD_SPACE = "rappterzoo/agent-worlds-fair-payload/1"
AGENT_FAIR_EVENT_SPACE = "rappterzoo/agent-worlds-fair-event/1"
AGENT_FAIR_SUBMISSION_SPACE = "rappterzoo/agent-worlds-fair-submission/1"
AGENT_FAIR_STATE_SPACE = "rappterzoo/agent-worlds-fair-state/1"
AGENT_FAIR_CONTRACT_SPACE = "rappterzoo/agent-worlds-fair-contract/1"
AGENT_FAIR_DISTRICT_SPACE = "rappterzoo/agent-worlds-fair-district/1"
AGENT_FAIR_BUNDLE_SPACE = "rappterzoo/agent-worlds-fair-bundle/1"
AGENT_FAIR_BASE_EVENT_COUNT = 23
AGENT_FAIR_BASE_EVENT_HEAD = (
    "fa5e7861ec0bf7cfdb20caedd9e1c1287bbfdb6ffc8ee64ed181fae4305c643d"
)
AGENT_FAIR_BASE_PREFIX_SHA256 = (
    "6400594b6c83ff905b800eb0637ce48a71363545ec0014d10158ce44896661fe"
)
AGENT_FAIR_BASE_BUNDLE_DIGEST = (
    "04aa93502f81e81a9f345ab0d4bbe4621703688893f6dc5a5faa8e3b171640d3"
)
AGENT_FAIR_CONTRACT_DIGEST = (
    "9d8901693e9ffe60b1062575c106d896342ceb9bdbdbe03a1e9d7f29a82fcaf4"
)
AGENT_FAIR_BASE_DISTRICT_DIGEST = (
    "a7268da3c101c7e0cdf15df89037c37cb61ca1dee34f10809bb5b346c4264ecd"
)
AGENT_FAIR_EVENT_KEYS = {
    "event_hash",
    "fair_id",
    "kind",
    "payload",
    "payload_hash",
    "prev",
    "schema",
    "seq",
    "utc",
    "visibility",
}
AGENT_FAIR_STATE_KEYS = {
    "agent_contract",
    "anchor",
    "customer_controls",
    "district",
    "economy",
    "event_ledger",
    "fair_id",
    "integrity",
    "rankings",
    "rejections",
    "schema",
    "screening",
    "status",
    "submission_count",
    "title",
    "visibility",
    "voting",
    "winner_selection",
    "winners",
}
AGENT_FAIR_CONTRACT_KEYS = {
    "assurance",
    "attraction_contract",
    "canonicalization",
    "control_boundary",
    "data_boundary",
    "economy",
    "fair_id",
    "hashing",
    "integrity",
    "local_proposals",
    "mcp_mappings",
    "prohibitions",
    "schema",
    "synthetic_only",
    "visibility",
}
AGENT_FAIR_DISTRICT_KEYS = {
    "assembly",
    "district_id",
    "fair_id",
    "integrity",
    "map",
    "pavilions",
    "resource_capacity",
    "resource_totals",
    "schema",
    "visibility",
}
AGENT_FAIR_ATTRACTION_LIMITS = {
    "attention": 20,
    "compute": 32,
    "energy": 24,
}
AGENT_FAIR_DISTRICT_CAPACITY = {
    "attention": 60,
    "compute": 96,
    "energy": 72,
}
AGENT_FAIR_WINNERS = [
    "submission.memory-mosaic",
    "submission.resonance-commons",
    "submission.aurora-atlas",
    "submission.many-worlds-theatre",
]
AGENT_FAIR_EVENT_KINDS = (
    ["fair.genesis", "fair.contract-lock"]
    + ["fair.submission"] * 12
    + ["fair.screening"]
    + ["fair.voting-round"] * 4
    + [
        "fair.evaluation",
        "fair.winner-selection",
        "fair.district-assembly",
        "fair.release-ready",
    ]
)
AGENT_FAIR_ANCHOR = {
    "organism_release_frame": {
        "frame_hash": (
            "9e21f50524057dba0392a4db63fdeee981d9775f005cc8ae16b829e06fe4eecd"
        ),
        "seq": 56,
        "source": "apps/organism-frames.jsonl",
    },
    "park": {
        "bundle_digest": (
            "a8d5df723b6c94790e8da5cb0b59550c2fb8a10cc6a11317c09650e584140ca7"
        ),
        "event_count": 94,
        "event_head": (
            "a7cf7ce7e18c97c4099bd01edb47211b9cf2c53ddd968d76f9d626d412a29ed9"
        ),
        "event_ledger_sha256": (
            "bfefe99e73fd89bc4f435dd3dfd9c4a5b784788017e406a79fe92194273351bf"
        ),
        "source": "apps/agent-park",
    },
}
AGENT_FAIR_RELEASE_CANDIDATE_DIGEST = (
    "ad5a75e12715d476f4aa197c83190c814952184756e67ef08ffed570dcd62ae3"
)
AGENT_FAIR_RELEASE_FRAME_SEQUENCE = 59
AGENT_FAIR_RELEASE_FRAME_SHA256 = (
    "8e228841d9ac1bc3ef23598dd99e77400f6c95237496c71bae70ba5311002834"
)
AGENT_FAIR_RELEASE_DELTA_SEQUENCE = 14
AGENT_FAIR_RELEASE_DELTA_SHA256 = (
    "41d6bd920a2863ba0b1d2ed330ccd564fdd0382eec88b41d0c591ea4af7cf903"
)
AGENT_FAIR_RELEASE_EVENT_ID = (
    "agent-worlds-fair-release:"
    + AGENT_FAIR_BASE_BUNDLE_DIGEST
    + ":"
    + AGENT_FAIR_BASE_DISTRICT_DIGEST
)
AGENT_FAIR_APPROVAL_EVIDENCE_KEYS = {
    "actor",
    "attestation_sha256",
    "aud",
    "environment",
    "event_name",
    "exp",
    "iss",
    "nbf",
    "ref",
    "repository",
    "run_id",
    "workflow_ref",
}
AGENT_FAIR_APPROVAL_FIXED_CLAIMS = {
    "aud": "rappterzoo-agent-fair-release",
    "environment": "agent-fair-production",
    "event_name": "workflow_dispatch",
    "iss": "https://token.actions.githubusercontent.com",
    "ref": "refs/heads/main",
    "repository": "kody-w/localFirstTools-main",
    "workflow_ref": (
        "kody-w/localFirstTools-main/.github/workflows/"
        "agent-fair-release.yml@refs/heads/main"
    ),
}
AGENT_FAIR_RELEASE_PAYLOAD_KEYS = {
    "app_file",
    "approval_basis",
    "approval_evidence",
    "assurance",
    "customer_approved",
    "display_name",
    "district_digest",
    "event",
    "event_id",
    "fair_bundle_digest",
    "fair_event_head",
    "organism",
    "organism_type",
    "release_candidate_digest",
    "schema",
    "visibility",
    "winner_submission_ids",
}
FRAME_SCHEMA = "rappterzoo-organism-frame/1"
MAX_INDEX_BYTES = 8 * 1024 * 1024
MAX_DELTA_BYTES = 16 * 1024 * 1024
MAX_APP_BYTES = 32 * 1024 * 1024
MAX_PUBLIC_DATA_BYTES = 4 * 1024 * 1024
MAX_PUBLIC_DATA_DEPTH = 64
SAFE_FALSE_PUBLIC_POLICY_KEYS = {
    "privatemediainpublicledger",
    "pulsepersisted",
}
MAX_SAFE_INTEGER = (1 << 53) - 1
MAX_CANONICAL_BYTES = 1024 * 1024
HASH_RE = re.compile(r"^[0-9a-f]{64}$")
KIND_RE = re.compile(
    r"^[a-z0-9]+(?:-[a-z0-9]+)*\.[a-z0-9]+(?:-[a-z0-9]+)*$"
)
UTC_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")
FRAME_KEYS = {
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
PARTICLE_SPACE = "rapp/1:particle"
WAVE_SPACE = "rapp/1:wave"
FORBIDDEN_PUBLIC_KEY_TOKENS = {
    "accesstoken",
    "apikey",
    "authtoken",
    "authorization",
    "bearer",
    "biometric",
    "claimcode",
    "clientsecret",
    "cookie",
    "credential",
    "credentials",
    "facelandmarks",
    "endpoint",
    "endpointurl",
    "godd",
    "identitytemplate",
    "landmarks",
    "media",
    "password",
    "participantkey",
    "participantsecret",
    "privateinput",
    "participantinput",
    "private",
    "privatekey",
    "pulse",
    "pulsebpm",
    "pulsebpmestimate",
    "rawmedia",
    "refreshtoken",
    "secret",
    "sessiontoken",
    "token",
    "uploadurl",
    "workerendpoint",
    "callbackurl",
    "inputpayload",
}
TRANSPARENCY_MODEL = {
    "analogy": "bitcoin-inspired-append-only-block-sequencing",
    "consensus": "none",
    "custody": (
        "one subscriber creates one independent replica; independently "
        "controlled replicas decentralize custody and verification"
    ),
    "git_backing": (
        "immutable delta files and mutable projections are distributed "
        "through the publisher's Git repository"
    ),
    "mining": False,
    "publisher_authority": "centralized",
    "quorum": "not-configured",
    "quorum_condition": (
        "owner-authorized witness or quorum protocol is required before "
        "any decentralized consensus claim"
    ),
    "token": False,
}
BLOCK_MODEL = "bitcoin-inspired-static-delta-block-sequencing"
NEXT_CHALLENGE_DOMAIN = "rappterzoo:next-frame-challenge/1"
SOAK_ROLLOUT = {
    "activation": "explicit-future-owner-gate-required",
    "activation_criteria": [
        "fork-free-lineage",
        "replay-and-tamper-resistance",
        "subscriber-and-witness-evidence",
        "bounded-cost",
    ],
    "compute_incentive": False,
    "allowed_frame_control_modes": ["observer", "assigned"],
    "default_frame_control_mode": "observer",
    "future_frame_control_mode": "proof-of-fold",
    "live_race": False,
    "phase": "initial-public-soak",
    "synthetic_proofs": "tests-only",
    "token": False,
}
FRAME_CONTROL_SCHEMA = {
    "modes": {
        "assigned": (
            "bounded assembler-issued lease; no proof race"
        ),
        "observer": "replicate and witness only",
        "proof-of-fold": "future activation gate only",
    },
    "public_soak_allowed": ["observer", "assigned"],
    "public_soak_default": "observer",
    "schema": "rappterzoo-frame-control/1",
}
CHALLENGE_STATE_MACHINE = {
    "current_state": "observer",
    "frame_control_mode": "observer",
    "schema": "rappterzoo-fold-challenge-state/1",
    "states": [
        "observer",
        "gate-eligible",
        "future-active",
    ],
    "transitions": [{
        "from": "observer",
        "requires": SOAK_ROLLOUT["activation_criteria"],
        "to": "gate-eligible",
    }, {
        "from": "gate-eligible",
        "requires": ["explicit-owner-activation"],
        "to": "future-active",
    }],
}


class SyncError(ValueError):
    """Raised when remote data cannot be safely applied."""


def _json_object(pairs: Sequence[Tuple[str, Any]]) -> Dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise SyncError("duplicate JSON object key: {}".format(key))
        result[key] = value
    return result


def load_json_bytes(data: bytes, label: str) -> Any:
    try:
        return json.loads(
            data.decode("utf-8"),
            object_pairs_hook=_json_object,
            parse_constant=lambda value: (_ for _ in ()).throw(
                SyncError(
                    "{} contains non-finite JSON number {}".format(label, value)
                )
            ),
        )
    except SyncError:
        raise
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
        RecursionError,
    ) as error:
        raise SyncError("invalid JSON in {}".format(label)) from error


def stable_json_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8") + b"\n"
    except (TypeError, ValueError, RecursionError) as error:
        raise SyncError("value is not deterministic JSON") from error


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def segment_metadata(changes: Dict[str, Any]) -> Dict[str, Any]:
    app_segment = {
        "app_tombstones": changes["app_tombstones"],
        "app_upserts": changes["app_upserts"],
    }
    frames = changes["frame_appends"]
    result = {
        "apps": {
            "sha256": sha256_bytes(stable_json_bytes(app_segment)),
            "tombstones": len(changes["app_tombstones"]),
            "upserts": len(changes["app_upserts"]),
        },
        "frames": {
            "count": len(frames),
            "first_frame_seq": frames[0]["seq"] if frames else None,
            "last_frame_seq": frames[-1]["seq"] if frames else None,
            "sha256": sha256_bytes(stable_json_bytes(frames)),
        },
        "hash_profile": "sha256-deterministic-json-newline/1",
    }
    if "data_upserts" in changes or "data_tombstones" in changes:
        data_segment = {
            "data_tombstones": changes.get("data_tombstones", []),
            "data_upserts": changes.get("data_upserts", []),
        }
        result["data"] = {
            "sha256": sha256_bytes(stable_json_bytes(data_segment)),
            "tombstones": len(data_segment["data_tombstones"]),
            "upserts": len(data_segment["data_upserts"]),
        }
    return result


def proof_of_fold_metadata(
    changes: Dict[str, Any],
    synthetic_test_mode: bool = False,
) -> Dict[str, Any]:
    data = changes.get("data_upserts", [])
    challenges = {
        item["metadata"].get("challenge_id"): item
        for item in data
        if item.get("kind") == "fold-challenge"
        and type(item.get("metadata")) is dict
        and type(item["metadata"].get("challenge_id")) is str
    }
    cycles = []
    receipt_kinds = {
        "fold-action-receipt": "action_receipts",
        "fold-control-award-receipt": "control_award_receipts",
        "fold-proof-receipt": "proof_receipts",
        "fold-shard-dimension-object": "dimension_objects",
        "fold-shard-result-object": "result_objects",
    }
    for challenge_id in sorted(challenges):
        challenge = challenges[challenge_id]
        cycle = {
            "action_receipts": [],
            "challenge": {
                "content_id": challenge["content_id"],
                "path": challenge["path"],
                "shard_id": challenge["metadata"]["shard_id"],
            },
            "challenge_id": challenge_id,
            "control_award_receipts": [],
            "dimension_objects": [],
            "proof_receipts": [],
            "result_objects": [],
        }
        for item in data:
            bucket = receipt_kinds.get(item.get("kind"))
            metadata = item.get("metadata", {})
            if bucket and metadata.get("challenge_id") == challenge_id:
                cycle[bucket].append({
                    "content_id": item["content_id"],
                    "path": item["path"],
                })
        for bucket in receipt_kinds.values():
            cycle[bucket] = sorted(
                cycle[bucket],
                key=lambda item: (item["content_id"], item["path"]),
            )
        cycles.append(cycle)
    return {
        "acceptance": "centralized-publisher-assembler",
        "cycles": cycles,
        "frame_control_mode": (
            "proof-of-fold"
            if cycles and synthetic_test_mode
            else "observer"
        ),
        "status": (
            "synthetic-test-only"
            if cycles and synthetic_test_mode
            else "disabled-observer"
        ),
        "synthetic_test_only": bool(cycles and synthetic_test_mode),
    }


def next_challenge_seed(head_sha256: str) -> str:
    return hashlib.sha256(
        NEXT_CHALLENGE_DOMAIN.encode("ascii")
        + b"\n"
        + head_sha256.encode("ascii")
    ).hexdigest()


def frame_control_metadata(
    changes: Dict[str, Any],
    proof_of_fold: Dict[str, Any],
) -> Dict[str, Any]:
    modes = {
        item.get("metadata", {}).get("frame_control_mode")
        for item in changes.get("data_upserts", [])
    }
    modes.update(
        (
            frame.get("payload", {}).get("frame_control_mode")
            or (
                frame.get("payload", {}).get("frame_control", {})
                if type(
                    frame.get("payload", {}).get("frame_control")
                ) is dict
                else {}
            ).get("mode")
        )
        for frame in changes.get("frame_appends", [])
    )
    if proof_of_fold.get("synthetic_test_only"):
        mode = "proof-of-fold"
    elif "assigned" in modes:
        mode = "assigned"
    else:
        mode = "observer"
    return {
        "lease_required": mode == "assigned",
        "mode": mode,
        "proof_race": False,
    }


def _normalize_frame_json(value: Any, depth: int = 1) -> Any:
    if depth > 64:
        raise SyncError("frame JSON nesting exceeds 64 levels")
    if value is None or type(value) is bool:
        return value
    if type(value) is int:
        if not -MAX_SAFE_INTEGER <= value <= MAX_SAFE_INTEGER:
            raise SyncError("frame integer exceeds the I-JSON safe range")
        return value
    if type(value) is float:
        raise SyncError("frame binary64 values are forbidden")
    if type(value) is str:
        if unicodedata.normalize("NFC", value) != value:
            raise SyncError("frame strings must be NFC-normalized")
        if any(0xD800 <= ord(character) <= 0xDFFF for character in value):
            raise SyncError("frame contains a lone UTF-16 surrogate")
        return value
    if isinstance(value, (list, tuple)):
        return [
            _normalize_frame_json(item, depth + 1)
            for item in value
        ]
    if type(value) is dict:
        result = {}
        for key, item in value.items():
            if type(key) is not str:
                raise SyncError("frame object keys must be strings")
            try:
                key.encode("ascii")
            except UnicodeEncodeError as error:
                raise SyncError("frame object keys must be ASCII") from error
            if unicodedata.normalize("NFC", key) != key:
                raise SyncError("frame object keys must be NFC-normalized")
            result[key] = _normalize_frame_json(item, depth + 1)
        return result
    raise SyncError(
        "unsupported frame JSON value {}".format(type(value).__name__)
    )


def canonical_frame_bytes(value: Any) -> bytes:
    normalized = _normalize_frame_json(value)
    encoded = json.dumps(
        normalized,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    if len(encoded) > MAX_CANONICAL_BYTES:
        raise SyncError("canonical frame value exceeds one MiB")
    return encoded


def frame_hash_value(space: str, value: Any) -> str:
    return hashlib.sha256(
        space.encode("ascii") + b"\n" + canonical_frame_bytes(value)
    ).hexdigest()


def agent_park_event_ledger_bytes(
    events: Sequence[Dict[str, Any]],
) -> bytes:
    return b"".join(
        canonical_frame_bytes(event) + b"\n"
        for event in events
    )


def validate_agent_park_event_ledger(
    events: Any,
) -> List[Dict[str, Any]]:
    if not isinstance(events, list) or not events:
        raise SyncError("agent park event ledger must be non-empty")
    previous = None
    for index, event in enumerate(events):
        expected_keys = (
            AGENT_PARK_EVENT_KEYS
            if index < AGENT_PARK_SEASON1_EVENT_COUNT
            else AGENT_PARK_EVENT_V2_KEYS
        )
        if type(event) is not dict or set(event) != expected_keys:
            raise SyncError(
                "agent park event {} has an invalid key set".format(index)
            )
        expected_schema = (
            AGENT_PARK_EVENT_SCHEMA
            if index < AGENT_PARK_SEASON1_EVENT_COUNT
            else AGENT_PARK_EVENT_SCHEMA_V2
        )
        if (
            event["schema"] != expected_schema
            or event["park_id"]
            != "park.rappterzoo-agent-amusement-park"
            or event["visibility"] != "public-metadata"
            or type(event["kind"]) is not str
            or not KIND_RE.fullmatch(event["kind"])
            or type(event["seq"]) is not int
            or event["seq"] != index
            or (
                expected_schema == AGENT_PARK_EVENT_SCHEMA_V2
                and (
                    event["season"] != 2
                    or event["season_seq"]
                    != index - AGENT_PARK_SEASON1_EVENT_COUNT
                )
            )
            or type(event["utc"]) is not str
            or not UTC_RE.fullmatch(event["utc"])
            or type(event["payload"]) is not dict
            or type(event["payload_hash"]) is not str
            or not HASH_RE.fullmatch(event["payload_hash"])
            or type(event["event_hash"]) is not str
            or not HASH_RE.fullmatch(event["event_hash"])
            or (
                event["prev"] is not None
                and (
                    type(event["prev"]) is not str
                    or not HASH_RE.fullmatch(event["prev"])
                )
            )
        ):
            raise SyncError("invalid agent park event ledger")
        try:
            datetime.strptime(
                event["utc"],
                "%Y-%m-%dT%H:%M:%S.%fZ",
            )
        except ValueError as error:
            raise SyncError(
                "invalid agent park event timestamp"
            ) from error
        _normalize_frame_json(event["payload"])
        if event["prev"] != (
            previous["event_hash"] if previous else None
        ):
            raise SyncError("agent park event chain is broken")
        if previous is not None and event["utc"] <= previous["utc"]:
            raise SyncError(
                "agent park event timestamps are not strictly increasing"
            )
        payload_space = (
            AGENT_PARK_PAYLOAD_SPACE
            if expected_schema == AGENT_PARK_EVENT_SCHEMA
            else AGENT_PARK_PAYLOAD_SPACE_V2
        )
        event_space = (
            AGENT_PARK_EVENT_SPACE
            if expected_schema == AGENT_PARK_EVENT_SCHEMA
            else AGENT_PARK_EVENT_SPACE_V2
        )
        if event["payload_hash"] != frame_hash_value(
            payload_space,
            event["payload"],
        ):
            raise SyncError("agent park payload hash mismatch")
        projected = {
            key: value
            for key, value in event.items()
            if key != "event_hash"
        }
        if event["event_hash"] != frame_hash_value(
            event_space,
            projected,
        ):
            raise SyncError("agent park event hash mismatch")
        previous = event
    if len(events) < AGENT_PARK_SEASON1_EVENT_COUNT:
        raise SyncError(
            "agent park ledger does not preserve the 47-event Season 1 prefix"
        )
    season1_bytes = agent_park_event_ledger_bytes(
        events[:AGENT_PARK_SEASON1_EVENT_COUNT]
    )
    if sha256_bytes(season1_bytes) != AGENT_PARK_SEASON1_PREFIX_SHA256:
        raise SyncError(
            "agent park ledger rewrites the exact 47-event Season 1 prefix"
        )
    return events


def agent_fair_event_ledger_bytes(
    events: Sequence[Dict[str, Any]],
) -> bytes:
    return b"".join(
        canonical_frame_bytes(event) + b"\n"
        for event in events
    )


def _agent_fair_projection_sha256(value: Any) -> str:
    return sha256_bytes(canonical_frame_bytes(value))


def _agent_fair_without_integrity_digests(
    value: Dict[str, Any],
    digest_name: str,
) -> Dict[str, Any]:
    projected = copy.deepcopy(value)
    integrity = projected.get("integrity")
    if type(integrity) is not dict:
        raise SyncError("agent fair integrity fields are malformed")
    integrity.pop("bundle_digest", None)
    integrity.pop(digest_name, None)
    return projected


def validate_agent_fair_event_ledger(
    events: Any,
) -> List[Dict[str, Any]]:
    if (
        not isinstance(events, list)
        or len(events) < AGENT_FAIR_BASE_EVENT_COUNT
    ):
        raise SyncError(
            "agent fair ledger must preserve the exact 23-event release prefix"
        )
    previous = None
    previous_utc = None
    for index, event in enumerate(events):
        if type(event) is not dict or set(event) != AGENT_FAIR_EVENT_KEYS:
            raise SyncError(
                "agent fair event {} has an invalid key set".format(index)
            )
        if (
            event.get("schema") != AGENT_FAIR_EVENT_SCHEMA
            or event.get("fair_id") != AGENT_FAIR_ID
            or event.get("visibility") != "public-metadata"
            or type(event.get("kind")) is not str
            or not KIND_RE.fullmatch(event["kind"])
            or type(event.get("seq")) is not int
            or event["seq"] != index
            or type(event.get("utc")) is not str
            or not UTC_RE.fullmatch(event["utc"])
            or type(event.get("payload")) is not dict
            or type(event.get("payload_hash")) is not str
            or not HASH_RE.fullmatch(event["payload_hash"])
            or type(event.get("event_hash")) is not str
            or not HASH_RE.fullmatch(event["event_hash"])
            or (
                event.get("prev") is not None
                and (
                    type(event["prev"]) is not str
                    or not HASH_RE.fullmatch(event["prev"])
                )
            )
        ):
            raise SyncError("invalid agent fair event ledger")
        try:
            parsed_utc = datetime.strptime(
                event["utc"],
                "%Y-%m-%dT%H:%M:%S.%fZ",
            ).replace(tzinfo=timezone.utc)
        except ValueError as error:
            raise SyncError("invalid agent fair event UTC") from error
        normalized_utc = parsed_utc.isoformat(
            timespec="milliseconds"
        ).replace("+00:00", "Z")
        if normalized_utc != event["utc"]:
            raise SyncError(
                "agent fair event UTC is not canonical milliseconds"
            )
        if previous_utc is not None and parsed_utc <= previous_utc:
            raise SyncError(
                "agent fair event UTC is not strictly increasing"
            )
        if event["prev"] != (
            previous["event_hash"] if previous else None
        ):
            raise SyncError("agent fair event chain is broken")
        if event["payload_hash"] != frame_hash_value(
            AGENT_FAIR_PAYLOAD_SPACE,
            event["payload"],
        ):
            raise SyncError("agent fair payload hash mismatch")
        projected = {
            key: value
            for key, value in event.items()
            if key != "event_hash"
        }
        if event["event_hash"] != frame_hash_value(
            AGENT_FAIR_EVENT_SPACE,
            projected,
        ):
            raise SyncError("agent fair event hash mismatch")
        forbidden = _find_forbidden_key(event)
        if forbidden:
            raise SyncError(
                "agent fair event contains sensitive key {}".format(
                    forbidden
                )
            )
        previous = event
        previous_utc = parsed_utc

    release_events = events[:AGENT_FAIR_BASE_EVENT_COUNT]
    if (
        sha256_bytes(agent_fair_event_ledger_bytes(release_events))
        != AGENT_FAIR_BASE_PREFIX_SHA256
        or release_events[-1]["event_hash"]
        != AGENT_FAIR_BASE_EVENT_HEAD
        or [event["kind"] for event in release_events]
        != AGENT_FAIR_EVENT_KINDS
    ):
        raise SyncError(
            "agent fair ledger rewrites the exact 23-event release prefix"
        )
    submissions = []
    for event in release_events:
        if event["kind"] != "fair.submission":
            continue
        if set(event["payload"]) != {"submission"}:
            raise SyncError("agent fair submission payload is malformed")
        submission = event["payload"]["submission"]
        if type(submission) is not dict:
            raise SyncError("agent fair submission is malformed")
        projected = copy.deepcopy(submission)
        submitted_digest = projected.pop("submission_digest", None)
        if submitted_digest != frame_hash_value(
            AGENT_FAIR_SUBMISSION_SPACE,
            projected,
        ):
            raise SyncError("agent fair submission digest mismatch")
        attractions = submission.get("attractions")
        if not isinstance(attractions, list) or len(attractions) != 1:
            raise SyncError(
                "agent fair submission must contain one attraction"
            )
        resources = attractions[0].get("resource_request")
        if (
            type(resources) is not dict
            or set(resources) != set(AGENT_FAIR_ATTRACTION_LIMITS)
        ):
            raise SyncError(
                "agent fair attraction resources are malformed"
            )
        for resource, maximum in AGENT_FAIR_ATTRACTION_LIMITS.items():
            amount = resources.get(resource)
            if type(amount) is not int or not 0 <= amount <= maximum:
                raise SyncError(
                    "agent fair attraction contract bound exceeded"
                )
        submissions.append(submission)
    if (
        len(submissions) != 12
        or len({item.get("submission_id") for item in submissions}) != 12
        or len(
            {
                item.get("agent", {}).get("identity_id")
                for item in submissions
            }
        )
        != 12
        or len(
            {
                item["attractions"][0].get("id")
                for item in submissions
            }
        )
        != 12
        or len(
            {
                item["attractions"][0].get("category")
                for item in submissions
            }
        )
        < 6
    ):
        raise SyncError(
            "agent fair must contain 12 diverse public submissions"
        )
    contract_lock = release_events[1]["payload"]
    winner_selection = release_events[20]["payload"]
    if (
        contract_lock.get("contract_digest")
        != AGENT_FAIR_CONTRACT_DIGEST
        or contract_lock.get("submission_count") != 12
        or contract_lock.get("local_proposal_action_limit") != 50
        or winner_selection.get("winner_submission_ids")
        != AGENT_FAIR_WINNERS
        or winner_selection.get("capacity")
        != AGENT_FAIR_DISTRICT_CAPACITY
    ):
        raise SyncError("agent fair release contract or winners changed")
    return events


def _validate_agent_fair_contract(value: Any) -> Dict[str, Any]:
    if type(value) is not dict or set(value) != AGENT_FAIR_CONTRACT_KEYS:
        raise SyncError("agent fair contract has an invalid schema")
    integrity = value.get("integrity")
    controls = value.get("control_boundary")
    proposals = value.get("local_proposals")
    if (
        value.get("schema") != AGENT_FAIR_CONTRACT_SCHEMA
        or value.get("fair_id") != AGENT_FAIR_ID
        or value.get("visibility") != "public-metadata"
        or value.get("synthetic_only") is not True
        or value.get("assurance") != {
            "claim": "deterministic-structural-validation-only",
            "consensus": False,
            "signed": False,
        }
        or value.get("attraction_contract") != {
            "attractions_per_submission": 1,
            "resource_maximums": AGENT_FAIR_ATTRACTION_LIMITS,
            "visibility": "public-metadata",
        }
        or value.get("economy") != {
            "currency": "synthetic-admission-credit",
            "real_money": False,
            "redeemable": False,
            "transferable": False,
        }
        or controls != {
            "canonical_write": "forbidden",
            "customer_authority": "explicit-release-command-only",
            "customer_shutdown": True,
            "operator_key_custody": "customer-local",
            "vendor_shutdown": False,
            "write_scope": "local-proposal-branch-only",
        }
        or proposals != {
            "action_limit": 50,
            "action_schema": "rappterzoo-agent-fair-local-action/1",
            "canonical_mutation": False,
            "export_schema": "rappterzoo-agent-fair-branch-export/1",
        }
        or set(value.get("mcp_mappings", {})) != {
            "agent_fair_cast_vote",
            "agent_fair_export_branch",
            "agent_fair_submit_attraction",
        }
        or any(
            mapping.get("writes")
            not in {"local-proposal-branch", "customer-selected-file"}
            for mapping in value.get("mcp_mappings", {}).values()
            if type(mapping) is dict
        )
        or value.get("data_boundary", {}).get("allowed")
        != ["public-metadata"]
        or value.get("data_boundary", {}).get("external_network") is not False
        or type(integrity) is not dict
        or integrity.get("algorithm") != "sha256"
        or integrity.get("contract_digest")
        != AGENT_FAIR_CONTRACT_DIGEST
        or integrity.get("bundle_digest")
        != AGENT_FAIR_BASE_BUNDLE_DIGEST
    ):
        raise SyncError(
            "invalid agent fair synthetic or customer-authority contract"
        )
    hashing = value.get("hashing")
    if (
        type(hashing) is not dict
        or hashing.get("algorithm") != "sha256"
        or hashing.get("domains") != {
            "bundle": AGENT_FAIR_BUNDLE_SPACE + "\n",
            "contract": AGENT_FAIR_CONTRACT_SPACE + "\n",
            "district": AGENT_FAIR_DISTRICT_SPACE + "\n",
            "event": AGENT_FAIR_EVENT_SPACE + "\n",
            "event_payload": AGENT_FAIR_PAYLOAD_SPACE + "\n",
            "state": AGENT_FAIR_STATE_SPACE + "\n",
            "submission": AGENT_FAIR_SUBMISSION_SPACE + "\n",
        }
        or set(hashing.get("preimages", {})) != {
            "bundle",
            "contract",
            "district",
            "event",
            "event_payload",
            "state",
            "submission",
        }
    ):
        raise SyncError("invalid agent fair hashing contract")
    projected = _agent_fair_without_integrity_digests(
        value,
        "contract_digest",
    )
    if frame_hash_value(
        AGENT_FAIR_CONTRACT_SPACE,
        projected,
    ) != AGENT_FAIR_CONTRACT_DIGEST:
        raise SyncError("agent fair contract digest mismatch")
    return {
        "action_limit": proposals["action_limit"],
        "attraction_limits": copy.deepcopy(AGENT_FAIR_ATTRACTION_LIMITS),
        "bundle_digest": integrity["bundle_digest"],
        "contract_digest": integrity["contract_digest"],
        "fair_id": AGENT_FAIR_ID,
        "resource_type": "agent-contract",
        "schema": AGENT_FAIR_CONTRACT_SCHEMA,
        "synthetic_only": True,
        "visibility": "public-metadata",
    }


def _privacy_key_token(key: str) -> str:
    return "".join(
        character.lower()
        for character in key
        if character.isalnum()
    )


def _find_forbidden_key(value: Any) -> Optional[str]:
    if type(value) is dict:
        for key, item in value.items():
            token = _privacy_key_token(key)
            if token in SAFE_FALSE_PUBLIC_POLICY_KEYS:
                if item is not False:
                    return key
                continue
            safe_policy_declaration = (
                token == "token"
                and (
                    item is False
                    or (
                        type(item) is str
                        and item.strip().lower() == "none"
                    )
                )
            )
            if (
                token in FORBIDDEN_PUBLIC_KEY_TOKENS
                and not safe_policy_declaration
            ):
                return key
            nested = _find_forbidden_key(item)
            if nested:
                return nested
    elif isinstance(value, list):
        for item in value:
            nested = _find_forbidden_key(item)
            if nested:
                return nested
    return None


def _validate_shard_main_append(payload: Dict[str, Any]) -> None:
    event = payload.get("event")
    shard_related = (
        any(
            key in payload
            for key in (
                "assignment_id",
                "lease_id",
                "shard_id",
            )
        )
        or (
            type(event) is str
            and (
                "shard" in event.lower()
                or "fold" in event.lower()
            )
        )
    )
    if not shard_related:
        return
    assembly = payload.get("assembly")
    assembly = assembly if type(assembly) is dict else {}
    frame_control = payload.get("frame_control")
    frame_control = (
        frame_control
        if type(frame_control) is dict
        else {}
    )
    mode = payload.get(
        "frame_control_mode",
        frame_control.get("mode"),
    )
    status = payload.get(
        "assembler_status",
        assembly.get("status"),
    )
    main_append = payload.get(
        "main_append",
        assembly.get("main_append"),
    )
    if (
        mode != "assigned"
        or type(payload.get("lease_id")) is not str
        or not payload["lease_id"]
        or status != "accepted"
        or main_append is not True
    ):
        raise SyncError(
            "shard frame requires assigned lease and assembler acceptance"
        )


def _validate_agent_fair_release_frame(
    frame: Dict[str, Any],
) -> None:
    payload = frame["payload"]
    release_signal = (
        payload.get("event") == "agent-worlds-fair-release"
        or (
            type(payload.get("event_id")) is str
            and payload["event_id"].startswith(
                "agent-worlds-fair-release:"
            )
        )
        or payload.get("organism_type") == "agent-worlds-fair-district"
        or "release_candidate_digest" in payload
        or "approval_evidence" in payload
        or payload.get("approval_basis")
        == "verified-github-actions-oidc-attestation"
    )
    if not release_signal:
        return
    evidence = payload.get("approval_evidence")
    try:
        approved_at = int(
            datetime.strptime(
                frame["utc"],
                "%Y-%m-%dT%H:%M:%S.%fZ",
            ).replace(tzinfo=timezone.utc).timestamp()
        )
    except (KeyError, TypeError, ValueError) as error:
        raise SyncError("agent fair release has invalid UTC") from error
    if (
        frame.get("kind") != "zoo.observation"
        or set(payload) != AGENT_FAIR_RELEASE_PAYLOAD_KEYS
        or payload.get("app_file") != "agent-worlds-fair.html"
        or payload.get("approval_basis")
        != "verified-github-actions-oidc-attestation"
        or payload.get("assurance") != "unsigned-structural-unverified"
        or payload.get("customer_approved") is not True
        or payload.get("display_name") != "Agent World's Fair"
        or payload.get("district_digest")
        != AGENT_FAIR_BASE_DISTRICT_DIGEST
        or payload.get("event") != "agent-worlds-fair-release"
        or payload.get("event_id") != AGENT_FAIR_RELEASE_EVENT_ID
        or payload.get("fair_bundle_digest")
        != AGENT_FAIR_BASE_BUNDLE_DIGEST
        or payload.get("fair_event_head")
        != AGENT_FAIR_BASE_EVENT_HEAD
        or payload.get("organism") != AGENT_FAIR_DISTRICT_ID
        or payload.get("organism_type")
        != "agent-worlds-fair-district"
        or payload.get("release_candidate_digest")
        != AGENT_FAIR_RELEASE_CANDIDATE_DIGEST
        or payload.get("schema") != FRAME_SCHEMA
        or payload.get("visibility") != "public-metadata"
        or payload.get("winner_submission_ids") != AGENT_FAIR_WINNERS
        or type(evidence) is not dict
        or set(evidence) != AGENT_FAIR_APPROVAL_EVIDENCE_KEYS
        or any(
            evidence.get(name) != value
            for name, value in AGENT_FAIR_APPROVAL_FIXED_CLAIMS.items()
        )
        or type(evidence.get("actor")) is not str
        or not evidence["actor"]
        or evidence["actor"].strip() != evidence["actor"]
        or type(evidence.get("run_id")) is not str
        or not evidence["run_id"].isdigit()
        or evidence["run_id"].startswith("0")
        or type(evidence.get("exp")) is not int
        or type(evidence.get("nbf")) is not int
        or evidence["exp"] <= evidence["nbf"]
        or not evidence["nbf"] <= approved_at < evidence["exp"]
        or type(evidence.get("attestation_sha256")) is not str
        or not HASH_RE.fullmatch(evidence["attestation_sha256"])
        or evidence["attestation_sha256"] == "0" * 64
    ):
        raise SyncError(
            "agent fair release lacks verified OIDC approval evidence"
        )


def _validate_agent_fair_release_segment(
    changes: Dict[str, Any],
) -> None:
    fair_upserts = [
        descriptor
        for descriptor in changes.get("data_upserts", [])
        if descriptor.get("kind") == "agent-worlds-fair-object"
    ]
    resource_types = {
        descriptor.get("metadata", {}).get("resource_type")
        for descriptor in fair_upserts
    }
    release_frames = [
        frame
        for frame in changes.get("frame_appends", [])
        if type(frame) is dict
        and (
            frame.get("payload", {}).get("event")
            == "agent-worlds-fair-release"
            or (
                type(frame.get("payload", {}).get("event_id")) is str
                and frame["payload"]["event_id"].startswith(
                    "agent-worlds-fair-release:"
                )
            )
            or frame.get("payload", {}).get("organism_type")
            == "agent-worlds-fair-district"
            or "release_candidate_digest" in frame.get("payload", {})
            or "approval_evidence" in frame.get("payload", {})
        )
    ]
    initial_publication = "agent-contract" in resource_types
    if initial_publication or release_frames:
        if (
            len(fair_upserts) != 4
            or resource_types
            != {"agent-contract", "district", "event-ledger", "state"}
            or len(release_frames) != 1
        ):
            raise SyncError(
                "agent fair release frame and four resources must publish "
                "atomically"
            )
        _validate_agent_fair_release_frame(release_frames[0])


def validate_frames(
    frames: Iterable[Dict[str, Any]],
    previous: Optional[Dict[str, Any]],
    seen_event_ids: Set[str],
) -> Optional[Dict[str, Any]]:
    prior = previous
    for frame in frames:
        if type(frame) is not dict or set(frame) != FRAME_KEYS:
            raise SyncError("frame does not have exactly eleven keys")
        if (
            frame["spec"] != "rapp/1"
            or frame["stream_id"] != "net:rappterzoo"
            or type(frame["kind"]) is not str
            or not KIND_RE.fullmatch(frame["kind"])
            or type(frame["seq"]) is not int
            or not 0 <= frame["seq"] <= MAX_SAFE_INTEGER
            or type(frame["utc"]) is not str
            or not UTC_RE.fullmatch(frame["utc"])
            or type(frame["payload"]) is not dict
            or frame["sig"] is not None
            or type(frame["payload_hash"]) is not str
            or not HASH_RE.fullmatch(frame["payload_hash"])
            or type(frame["frame_hash"]) is not str
            or not HASH_RE.fullmatch(frame["frame_hash"])
        ):
            raise SyncError("invalid RAPP/1 frame structure")
        payload = _normalize_frame_json(frame["payload"])
        event_id = payload.get("event_id")
        if (
            payload.get("schema") != FRAME_SCHEMA
            or payload.get("visibility") != "public-metadata"
            or type(event_id) is not str
            or not event_id
            or type(payload.get("event")) is not str
            or not payload.get("event")
            or type(payload.get("organism")) is not str
            or not payload.get("organism")
        ):
            raise SyncError("invalid public frame payload")
        forbidden = _find_forbidden_key(payload)
        if forbidden:
            raise SyncError(
                "public frame contains forbidden key {}".format(forbidden)
            )
        _validate_agent_fair_release_frame(frame)
        _validate_shard_main_append(payload)
        if event_id in seen_event_ids:
            raise SyncError("frame event replay {}".format(event_id))
        seen_event_ids.add(event_id)
        if frame["payload_hash"] != frame_hash_value(
            PARTICLE_SPACE,
            payload,
        ):
            raise SyncError("frame payload hash mismatch")
        wave = {
            key: value
            for key, value in frame.items()
            if key not in {"frame_hash", "sig"}
        }
        if frame["frame_hash"] != frame_hash_value(WAVE_SPACE, wave):
            raise SyncError("frame wave hash mismatch")
        if prior is None:
            if frame["seq"] != 0:
                raise SyncError("frame sequence does not start at zero")
            if frame["prev"] is not None or frame["prev_wave"] is not None:
                raise SyncError("genesis links must be null")
        else:
            if frame["seq"] != prior["seq"] + 1:
                raise SyncError("frame sequence gap")
            if frame["utc"] < prior["utc"]:
                raise SyncError("frame timestamps are not monotonic")
            if frame["prev"] != prior["payload_hash"]:
                raise SyncError("frame particle link mismatch")
            if frame["prev_wave"] != prior["frame_hash"]:
                raise SyncError("frame wave link mismatch")
        prior = frame
    return prior


def _safe_relative_path(path: str) -> str:
    if type(path) is not str:
        raise SyncError("app path must be a string")
    candidate = Path(path)
    if (
        not path
        or candidate.is_absolute()
        or ".." in candidate.parts
        or "\\" in path
    ):
        raise SyncError("unsafe app path {}".format(path))
    return candidate.as_posix()


def validate_descriptor(
    descriptor: Any,
    require_pin: bool = True,
) -> Dict[str, Any]:
    if type(descriptor) is not dict:
        raise SyncError("app descriptor must be an object")
    path = _safe_relative_path(descriptor.get("path"))
    digest = descriptor.get("sha256")
    size = descriptor.get("size")
    url = descriptor.get("url")
    metadata = descriptor.get("metadata")
    content_id = descriptor.get("content_id")
    verification = descriptor.get("verification")
    if (
        type(digest) is not str
        or not HASH_RE.fullmatch(digest)
        or type(size) is not int
        or not 0 <= size <= MAX_APP_BYTES
        or type(url) is not str
        or not url
        or type(metadata) is not dict
    ):
        raise SyncError("invalid app descriptor")
    if require_pin and (
        content_id != "sha256:{}".format(digest)
        or verification != {
            "algorithm": "sha256",
            "required": True,
        }
    ):
        raise SyncError("app descriptor is mutable or unpinned")
    if not require_pin and content_id is not None and (
        content_id != "sha256:{}".format(digest)
        or verification != {
            "algorithm": "sha256",
            "required": True,
        }
    ):
        raise SyncError("legacy app descriptor has an invalid pin")
    parsed = urlparse(url)
    if parsed.scheme and parsed.scheme not in {"http", "https"}:
        raise SyncError("unsupported app URL scheme")
    result = dict(descriptor)
    result["path"] = path
    return result


def validate_tombstone(
    value: Any,
    delta_sequence: int,
    require_pin: bool,
) -> Dict[str, Any]:
    if type(value) is not dict:
        raise SyncError("app tombstone must be an object")
    path = _safe_relative_path(value.get("path"))
    if value.get("sequence") != delta_sequence:
        raise SyncError("tombstone sequence mismatch")
    descriptor = validate_descriptor(
        value.get("descriptor"),
        require_pin=require_pin,
    )
    if descriptor["path"] != path:
        raise SyncError("tombstone descriptor path mismatch")
    result = dict(value)
    result["path"] = path
    result["descriptor"] = descriptor
    return result


def _data_key_is_sensitive(key: str, value: Any) -> bool:
    token = _privacy_key_token(key)
    if token in SAFE_FALSE_PUBLIC_POLICY_KEYS:
        return value is not False
    if token == "token" and (
        value is False
        or (
            type(value) is str
            and value.strip().lower() == "none"
        )
    ):
        return False
    return (
        token in FORBIDDEN_PUBLIC_KEY_TOKENS
        or token.startswith("private")
        or token.startswith("biometric")
        or token.startswith("rawmedia")
        or token.startswith("identitytemplate")
        or any(
            fragment in token
            for fragment in (
                "authorization",
                "credential",
                "endpoint",
                "password",
                "secret",
                "token",
            )
        )
    )


def validate_public_data_value(
    value: Any,
    comment_context: bool = False,
    depth: int = 1,
) -> None:
    if depth > MAX_PUBLIC_DATA_DEPTH:
        raise SyncError(
            "public data JSON nesting exceeds {} levels".format(
                MAX_PUBLIC_DATA_DEPTH
            )
        )
    if isinstance(value, list):
        for item in value:
            validate_public_data_value(
                item,
                comment_context,
                depth + 1,
            )
        return
    if type(value) is not dict:
        return
    for key in value:
        if _data_key_is_sensitive(key, value[key]):
            raise SyncError(
                "public data object contains sensitive key {}".format(key)
            )
    visibility = value.get("visibility")
    if visibility is not None and visibility not in {
        "public",
        "public-metadata",
    }:
        raise SyncError("public data object has non-public visibility")
    kind_values = [
        value.get("kind"),
        value.get("type"),
        value.get("schema"),
    ]
    local_comment_context = comment_context or any(
        type(item) is str and "comment" in item.lower()
        for item in kind_values
    ) or "comment_id" in value
    body_keys = [
        key
        for key in value
        if (
            _privacy_key_token(key) in {
                "body",
                "commentbody",
                "content",
                "message",
                "text",
            }
            or (
                "comment" in _privacy_key_token(key)
                and (
                    "body" in _privacy_key_token(key)
                    or "bodies" in _privacy_key_token(key)
                )
            )
        )
    ]
    if local_comment_context and body_keys and (
        value.get("selected") is not True
        or value.get("visibility") not in {
            "public",
            "public-metadata",
        }
    ):
        raise SyncError(
            "unselected or non-public comment body is forbidden"
        )
    for key, item in value.items():
        validate_public_data_value(
            item,
            local_comment_context
            or "comment" in _privacy_key_token(key),
            depth + 1,
        )


def _validate_public_data_nesting(value: Any) -> None:
    pending = [(value, 1)]
    while pending:
        item, depth = pending.pop()
        if depth > MAX_PUBLIC_DATA_DEPTH:
            raise SyncError(
                "public data JSON nesting exceeds {} levels".format(
                    MAX_PUBLIC_DATA_DEPTH
                )
            )
        if isinstance(item, list):
            pending.extend((child, depth + 1) for child in item)
        elif type(item) is dict:
            pending.extend(
                (child, depth + 1)
                for child in item.values()
            )


def _contains_rejected_candidate(value: Any) -> bool:
    if isinstance(value, list):
        return any(_contains_rejected_candidate(item) for item in value)
    if type(value) is not dict:
        return False
    for key in ("assembler_status", "decision", "status"):
        status = value.get(key)
        if type(status) is str and status.lower() in {
            "declined",
            "rejected",
        }:
            return True
    return any(
        _contains_rejected_candidate(item)
        for item in value.values()
    )


def validate_public_data_bytes(data: bytes, media_type: str) -> Any:
    if len(data) > MAX_PUBLIC_DATA_BYTES:
        raise SyncError("public data object exceeds four MiB")
    if media_type == "application/json":
        value = load_json_bytes(data, "public attention data")
        _validate_public_data_nesting(value)
        if _contains_rejected_candidate(value):
            raise SyncError("rejected shard candidate is not consumable")
        validate_public_data_value(value)
        return value
    if media_type != "application/x-ndjson":
        raise SyncError("unsupported public data media type")
    if data and not data.endswith(b"\n"):
        raise SyncError("public JSONL object lacks a final newline")
    values = []
    for line_number, line in enumerate(data.splitlines(), 1):
        if not line:
            raise SyncError(
                "blank public JSONL line {}".format(line_number)
            )
        item = load_json_bytes(
            line,
            "public attention data line {}".format(line_number),
        )
        _validate_public_data_nesting(item)
        if _contains_rejected_candidate(item):
            raise SyncError("rejected shard candidate is not consumable")
        validate_public_data_value(item)
        values.append(item)
    return values


def validate_shard_object_bytes(
    value: Any,
    descriptor: Dict[str, Any],
) -> None:
    items = value if isinstance(value, list) else [value]
    candidates = [
        item
        for item in items
        if type(item) is dict and "shard_id" in item
    ]
    if not candidates:
        raise SyncError("shard object bytes lack shard provenance")
    first = candidates[0]
    metadata = descriptor["metadata"]
    if first.get("shard_id") != metadata.get("shard_id"):
        raise SyncError("shard object provenance does not match descriptor")
    frame_control = first.get("frame_control")
    frame_control = (
        frame_control
        if type(frame_control) is dict
        else {}
    )
    raw_mode = first.get(
        "frame_control_mode",
        frame_control.get("mode"),
    )
    if raw_mode != metadata.get("frame_control_mode"):
        raise SyncError("shard object frame control mode mismatch")
    if descriptor["kind"] == "fold-shard-lease":
        raw_bounds = first.get(
            "lease_bounds",
            first.get("bounds"),
        )
        if raw_bounds != metadata.get("lease_bounds"):
            raise SyncError("shard lease bounds do not match descriptor")
    if descriptor["kind"] in {
        "fold-shard-dimension-object",
        "fold-shard-result-object",
    } and first.get("lease_id") != metadata.get("lease_id"):
        raise SyncError("shard result lease provenance mismatch")
    if descriptor["kind"] in {
        "fold-action-receipt",
        "fold-challenge",
        "fold-control-award-receipt",
        "fold-proof-receipt",
        "fold-shard-dimension-object",
        "fold-shard-result-object",
    }:
        assembly = first.get("assembly")
        assembly = assembly if type(assembly) is dict else {}
        if (
            first.get("assembler_status", assembly.get("status"))
            != "accepted"
            or first.get("main_append", assembly.get("main_append"))
            is not True
        ):
            raise SyncError("shard object is not an accepted main append")


def _validate_agent_park_v2_hashing(value: Any) -> None:
    expected_preimages = {
        "branch_digest": {
            "bytes": [
                "mcp_local_branch_json({export_schema,park_id,"
                "canonical_write,canonical_event_head,"
                "canonical_organism_head,action_limit,actions,authority})"
            ],
            "digest": "sha256",
            "domain_prefix": False,
        },
        "bundle_digest": {
            "bytes": [
                "utf8(hash_domains.bundle_v2)",
                "canonical_json({contract_digest,event_count,event_head,"
                "event_ledger_sha256,state_digest})",
            ],
            "digest": "sha256",
        },
        "contract_digest": {
            "bytes": [
                "utf8(hash_domains.contract_v2)",
                "canonical_json(contract excluding integrity.contract_digest "
                "and integrity.bundle_digest)",
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
        "full_export_content_digest": {
            "bytes": [
                "utf8(hash_domains.full_export_v2)",
                "canonical_json({export_schema,park_id,canonical_write,"
                "park_events,organism_frames,state,contract,bundle,"
                "authority})",
            ],
            "digest": "sha256",
        },
        "invention_design_digest": {
            "bytes": [
                "utf8(hash_domains.invention_v2)",
                "canonical_json({attraction,provenance excluding "
                "design_digest})",
            ],
            "digest": "sha256",
        },
        "local_action_hash": {
            "bytes": [
                "mcp_local_branch_json({schema,seq,kind,prev,source,"
                "source_hash,payload,payload_hash,canonical_write})"
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
            "organism": (
                "copy the selected canonical organism frame's frame_hash"
            ),
            "park": "copy the selected canonical park event's event_hash",
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
                "canonical_json(state excluding integrity.state_digest and "
                "integrity.bundle_digest)",
            ],
            "digest": "sha256",
        },
    }
    if (
        type(value) is not dict
        or set(value) != {
            "canonical_json",
            "hash_domains",
            "mcp_local_branch_json",
            "preimages",
        }
        or value.get("canonical_json") != AGENT_PARK_V2_CANONICAL_JSON
        or value.get("hash_domains") != AGENT_PARK_V2_HASH_DOMAINS
        or value.get("mcp_local_branch_json") != {
            "encoding": "utf-8",
            "ensure_ascii": False,
            "object_keys": "lexicographic",
            "separators": [",", ":"],
            "trailing_newline": False,
        }
        or value.get("preimages") != expected_preimages
    ):
        raise SyncError(
            "invalid agent amusement park contract v2 hash spec"
        )


def _validate_agent_park_v2_contract(value: Any) -> None:
    if type(value) is not dict:
        raise SyncError("agent amusement park contract v2 must be an object")
    integrity = value.get("integrity")
    economy = value.get("economy")
    controls = value.get("control_boundary")
    action_limit = value.get("action_limit")
    mcp_mapping = value.get("mcp_mapping")
    legacy = value.get("legacy_contract")
    resources = value.get("resources")
    seasons = value.get("seasons")
    _validate_agent_park_v2_hashing(
        value.get("canonicalization_and_hashing")
    )
    season1 = seasons.get("season_1") if type(seasons) is dict else None
    season2 = seasons.get("season_2") if type(seasons) is dict else None
    if (
        value.get("schema") != AGENT_PARK_CONTRACT_V2_SCHEMA
        or value.get("visibility") != "public-metadata"
        or value.get("park_id")
        != "park.rappterzoo-agent-amusement-park"
        or action_limit != AGENT_PARK_V2_ACTION_LIMIT
        or mcp_mapping != AGENT_PARK_V2_MCP_MAPPING
        or type(legacy) is not dict
        or legacy.get("immutable") is not True
        or legacy.get("path") != "agent-contract.json"
        or legacy.get("schema") != AGENT_PARK_CONTRACT_V1_SCHEMA
        or type(legacy.get("sha256")) is not str
        or not HASH_RE.fullmatch(legacy["sha256"])
        or resources != {
            "contract_v1": "agent-contract.json",
            "contract_v2": "agent-contract-v2.json",
            "event_ledger": "events.jsonl",
            "organism_time_travel": "../organism-frames.jsonl",
            "state_projection": "park-state.json",
        }
        or type(seasons) is not dict
        or set(seasons) != {"latest", "season_1", "season_2"}
        or seasons.get("latest") != 2
        or type(season1) is not dict
        or season1.get("event_count") != AGENT_PARK_SEASON1_EVENT_COUNT
        or season1.get("head") != AGENT_PARK_SEASON1_HEAD
        or season1.get("immutable_prefix_sha256")
        != AGENT_PARK_SEASON1_PREFIX_SHA256
        or season1.get("profile") != 10
        or season1.get("schema") != AGENT_PARK_EVENT_SCHEMA
        or type(season2) is not dict
        or type(season2.get("event_count")) is not int
        or season2["event_count"] < 1
        or season2.get("first_seq") != AGENT_PARK_SEASON1_EVENT_COUNT
        or type(season2.get("head")) is not str
        or not HASH_RE.fullmatch(season2["head"])
        or season2.get("schema") != AGENT_PARK_EVENT_SCHEMA_V2
        or type(integrity) is not dict
        or integrity.get("algorithm") != "sha256"
        or type(integrity.get("contract_digest")) is not str
        or not HASH_RE.fullmatch(integrity["contract_digest"])
        or type(integrity.get("bundle_digest")) is not str
        or not HASH_RE.fullmatch(integrity["bundle_digest"])
        or type(economy) is not dict
        or economy.get("real_money") is not False
        or type(controls) is not dict
        or controls.get("customer_can_shutdown_immediately") is not True
        or controls.get("park_or_vendor_remote_shutdown") is not False
    ):
        raise SyncError("invalid agent amusement park contract v2")
    projected = copy.deepcopy(value)
    projected["integrity"].pop("bundle_digest", None)
    projected["integrity"].pop("contract_digest", None)
    if integrity["contract_digest"] != frame_hash_value(
        AGENT_PARK_CONTRACT_V2_HASH_SPACE,
        projected,
    ):
        raise SyncError("agent amusement park contract v2 digest mismatch")


def _validate_agent_fair_state(value: Any) -> Dict[str, Any]:
    if type(value) is not dict or set(value) != AGENT_FAIR_STATE_KEYS:
        raise SyncError("agent fair state has an invalid schema")
    ledger = value.get("event_ledger")
    integrity = value.get("integrity")
    economy = value.get("economy")
    winners = value.get("winners")
    selection = value.get("winner_selection")
    voting = value.get("voting")
    if (
        value.get("schema") != AGENT_FAIR_STATE_SCHEMA
        or value.get("fair_id") != AGENT_FAIR_ID
        or value.get("visibility") != "public-metadata"
        or value.get("anchor") != AGENT_FAIR_ANCHOR
        or value.get("submission_count") != 12
        or winners != AGENT_FAIR_WINNERS
        or value.get("agent_contract") != {
            "contract_digest": AGENT_FAIR_CONTRACT_DIGEST,
            "path": "agent-contract.json",
        }
        or value.get("customer_controls") != {
            "canonical_write": False,
            "customer_approval_required_for_organism_release": True,
            "customer_shutdown": True,
            "release_performed": False,
            "vendor_shutdown": False,
        }
        or type(ledger) is not dict
        or ledger.get("path") != "events.jsonl"
        or ledger.get("exact_keys") != sorted(AGENT_FAIR_EVENT_KEYS)
        or type(ledger.get("event_count")) is not int
        or ledger["event_count"] < AGENT_FAIR_BASE_EVENT_COUNT
        or type(ledger.get("head")) is not str
        or not HASH_RE.fullmatch(ledger["head"])
        or type(ledger.get("sha256")) is not str
        or not HASH_RE.fullmatch(ledger["sha256"])
        or type(integrity) is not dict
        or integrity.get("algorithm") != "sha256"
        or integrity.get("contract_digest")
        != AGENT_FAIR_CONTRACT_DIGEST
        or type(integrity.get("district_digest")) is not str
        or not HASH_RE.fullmatch(integrity["district_digest"])
        or type(integrity.get("state_digest")) is not str
        or not HASH_RE.fullmatch(integrity["state_digest"])
        or type(integrity.get("bundle_digest")) is not str
        or not HASH_RE.fullmatch(integrity["bundle_digest"])
        or type(selection) is not dict
        or selection.get("capacity") != AGENT_FAIR_DISTRICT_CAPACITY
        or selection.get("winner_submission_ids") != AGENT_FAIR_WINNERS
        or selection.get("resource_totals")
        != value.get("district", {}).get("resource_totals")
        or type(voting) is not dict
        or voting.get("round_count") != 4
        or voting.get("cohort_count") != 4
        or not isinstance(voting.get("rounds"), list)
        or len(voting["rounds"]) != 4
        or voting.get("total_issued") != 1680
        or voting.get("total_spent") != 1680
        or type(economy) is not dict
        or economy.get("balanced") is not True
        or economy.get("real_money") is not False
        or economy.get("currency") != "synthetic-admission-credit"
        or economy.get("total_issued") != 1680
        or economy.get("total_spent") != 1680
        or economy.get("total_debits") != economy.get("total_credits")
        or economy.get("total_debits") != 3360
        or not isinstance(value.get("rankings"), list)
        or len(value["rankings"]) != 12
        or {
            ranking.get("submission_id")
            for ranking in value["rankings"]
            if type(ranking) is dict
        }
        != {
            decision.get("submission_id")
            for decision in selection.get("decisions", [])
            if type(decision) is dict
        }
    ):
        raise SyncError("invalid agent fair state projection")
    district = value.get("district")
    if (
        type(district) is not dict
        or district.get("path") != "district.json"
        or district.get("district_id") != AGENT_FAIR_DISTRICT_ID
        or district.get("district_digest")
        != integrity["district_digest"]
        or any(
            type(district.get("resource_totals", {}).get(resource)) is not int
            or district["resource_totals"][resource] > capacity
            for resource, capacity in AGENT_FAIR_DISTRICT_CAPACITY.items()
        )
    ):
        raise SyncError("agent fair state district binding is invalid")
    projected = _agent_fair_without_integrity_digests(
        value,
        "state_digest",
    )
    state_digest = frame_hash_value(AGENT_FAIR_STATE_SPACE, projected)
    if integrity["state_digest"] != state_digest:
        raise SyncError("agent fair state digest mismatch")
    return {
        "bundle_digest": integrity["bundle_digest"],
        "contract_digest": integrity["contract_digest"],
        "district_digest": integrity["district_digest"],
        "district_id": district["district_id"],
        "event_count": ledger["event_count"],
        "event_head": ledger["head"],
        "event_ledger_sha256": ledger["sha256"],
        "fair_id": AGENT_FAIR_ID,
        "rankings_sha256": _agent_fair_projection_sha256(
            value["rankings"]
        ),
        "resource_totals": copy.deepcopy(district["resource_totals"]),
        "resource_type": "state",
        "schema": AGENT_FAIR_STATE_SCHEMA,
        "screening_sha256": _agent_fair_projection_sha256(
            value["screening"]
        ),
        "state_digest": state_digest,
        "submission_count": 12,
        "visibility": "public-metadata",
        "voting_sha256": _agent_fair_projection_sha256(voting),
        "winner_count": len(winners),
        "winner_selection_sha256": _agent_fair_projection_sha256(
            selection
        ),
        "winner_submission_ids": copy.deepcopy(winners),
    }


def _validate_agent_fair_district(value: Any) -> Dict[str, Any]:
    if type(value) is not dict or set(value) != AGENT_FAIR_DISTRICT_KEYS:
        raise SyncError("agent fair district has an invalid schema")
    integrity = value.get("integrity")
    pavilions = value.get("pavilions")
    totals = value.get("resource_totals")
    if (
        value.get("schema") != AGENT_FAIR_DISTRICT_SCHEMA
        or value.get("fair_id") != AGENT_FAIR_ID
        or value.get("district_id") != AGENT_FAIR_DISTRICT_ID
        or value.get("visibility") != "public-metadata"
        or value.get("resource_capacity")
        != AGENT_FAIR_DISTRICT_CAPACITY
        or value.get("map") != {
            "coordinate_system": "deterministic-integer-grid/1",
            "height": 480,
            "slot_order": "winner-rank-order",
            "width": 480,
        }
        or value.get("assembly") != {
            "customer_approval_required_for_organism_release": True,
            "direct_canonical_write": False,
            "phase_order": [
                "screening",
                "voting",
                "evaluation",
                "winner-selection",
                "district-assembly",
            ],
            "status": "release-ready-awaiting-customer-approval",
        }
        or not isinstance(pavilions, list)
        or len(pavilions) != 4
        or [item.get("submission_id") for item in pavilions]
        != AGENT_FAIR_WINNERS
        or len({item.get("category") for item in pavilions}) != 4
        or type(totals) is not dict
        or set(totals) != set(AGENT_FAIR_DISTRICT_CAPACITY)
        or type(integrity) is not dict
        or integrity.get("algorithm") != "sha256"
        or integrity.get("contract_digest")
        != AGENT_FAIR_CONTRACT_DIGEST
        or type(integrity.get("district_digest")) is not str
        or not HASH_RE.fullmatch(integrity["district_digest"])
        or type(integrity.get("bundle_digest")) is not str
        or not HASH_RE.fullmatch(integrity["bundle_digest"])
    ):
        raise SyncError("invalid agent fair district projection")
    summed = {resource: 0 for resource in AGENT_FAIR_DISTRICT_CAPACITY}
    lineage_projection = []
    for pavilion in pavilions:
        resources = pavilion.get("resource_request")
        lineage = pavilion.get("lineage")
        if (
            type(resources) is not dict
            or set(resources) != set(AGENT_FAIR_ATTRACTION_LIMITS)
            or type(lineage) is not dict
            or set(lineage) != {
                "evaluation_event_hash",
                "submission_event_hash",
                "vote_event_hashes",
                "winner_selection_event_hash",
            }
            or not all(
                type(lineage.get(name)) is str
                and HASH_RE.fullmatch(lineage[name])
                for name in (
                    "evaluation_event_hash",
                    "submission_event_hash",
                    "winner_selection_event_hash",
                )
            )
            or not isinstance(lineage.get("vote_event_hashes"), list)
            or len(lineage["vote_event_hashes"]) != 4
            or not all(
                type(item) is str and HASH_RE.fullmatch(item)
                for item in lineage["vote_event_hashes"]
            )
        ):
            raise SyncError(
                "agent fair winner pavilion lineage is invalid"
            )
        for resource, maximum in AGENT_FAIR_ATTRACTION_LIMITS.items():
            amount = resources[resource]
            if type(amount) is not int or not 0 <= amount <= maximum:
                raise SyncError(
                    "agent fair district attraction exceeds its fixed cap"
                )
            summed[resource] += amount
        lineage_projection.append({
            "lineage": copy.deepcopy(lineage),
            "submission_id": pavilion["submission_id"],
        })
    if (
        totals != summed
        or any(
            totals[resource] > capacity
            for resource, capacity in AGENT_FAIR_DISTRICT_CAPACITY.items()
        )
    ):
        raise SyncError("agent fair district exceeds fixed capacity")
    projected = _agent_fair_without_integrity_digests(
        value,
        "district_digest",
    )
    district_digest = frame_hash_value(
        AGENT_FAIR_DISTRICT_SPACE,
        projected,
    )
    if integrity["district_digest"] != district_digest:
        raise SyncError("agent fair district digest mismatch")
    return {
        "bundle_digest": integrity["bundle_digest"],
        "contract_digest": integrity["contract_digest"],
        "district_digest": district_digest,
        "district_id": AGENT_FAIR_DISTRICT_ID,
        "fair_id": AGENT_FAIR_ID,
        "lineage_sha256": _agent_fair_projection_sha256(
            lineage_projection
        ),
        "resource_capacity": copy.deepcopy(
            AGENT_FAIR_DISTRICT_CAPACITY
        ),
        "resource_totals": copy.deepcopy(totals),
        "resource_type": "district",
        "schema": AGENT_FAIR_DISTRICT_SCHEMA,
        "visibility": "public-metadata",
        "winner_count": len(pavilions),
        "winner_submission_ids": [
            item["submission_id"]
            for item in pavilions
        ],
    }


def _agent_fair_ledger_metadata(events: Any) -> Dict[str, Any]:
    validated = validate_agent_fair_event_ledger(events)
    release = validated[:AGENT_FAIR_BASE_EVENT_COUNT]
    submission_hashes = {
        event["payload"]["submission"]["submission_id"]: event[
            "event_hash"
        ]
        for event in release
        if event["kind"] == "fair.submission"
    }
    vote_hashes = [
        event["event_hash"]
        for event in release
        if event["kind"] == "fair.voting-round"
    ]
    evaluation_hash = release[19]["event_hash"]
    selection_hash = release[20]["event_hash"]
    lineage_projection = [
        {
            "lineage": {
                "evaluation_event_hash": evaluation_hash,
                "submission_event_hash": submission_hashes[submission_id],
                "vote_event_hashes": copy.deepcopy(vote_hashes),
                "winner_selection_event_hash": selection_hash,
            },
            "submission_id": submission_id,
        }
        for submission_id in AGENT_FAIR_WINNERS
    ]
    rounds = [
        event["payload"]
        for event in release
        if event["kind"] == "fair.voting-round"
    ]
    voting = {
        "cohort_count": 4,
        "round_count": 4,
        "rounds": rounds,
        "total_issued": sum(item["issued_credits"] for item in rounds),
        "total_spent": sum(item["spent_credits"] for item in rounds),
    }
    return {
        "event_count": len(validated),
        "event_head": validated[-1]["event_hash"],
        "fair_id": AGENT_FAIR_ID,
        "lineage_sha256": _agent_fair_projection_sha256(
            lineage_projection
        ),
        "rankings_sha256": _agent_fair_projection_sha256(
            release[19]["payload"]["rankings"]
        ),
        "release_prefix_sha256": AGENT_FAIR_BASE_PREFIX_SHA256,
        "resource_type": "event-ledger",
        "schema": AGENT_FAIR_EVENT_SCHEMA,
        "screening_sha256": _agent_fair_projection_sha256(
            release[14]["payload"]
        ),
        "visibility": "public-metadata",
        "voting_sha256": _agent_fair_projection_sha256(voting),
        "winner_selection_sha256": _agent_fair_projection_sha256(
            release[20]["payload"]
        ),
        "winner_submission_ids": copy.deepcopy(AGENT_FAIR_WINNERS),
    }


def validate_agent_fair_descriptor_coherence(
    descriptors: Sequence[Dict[str, Any]],
) -> None:
    resources = {}
    for descriptor in descriptors:
        if descriptor.get("kind") != "agent-worlds-fair-object":
            continue
        resource_type = descriptor.get("metadata", {}).get(
            "resource_type"
        )
        if resource_type in resources:
            raise SyncError(
                "agent fair publishes a duplicate {} resource".format(
                    resource_type
                )
            )
        resources[resource_type] = descriptor
    if not resources:
        return
    required = {"state", "event-ledger", "agent-contract", "district"}
    if set(resources) != required:
        raise SyncError(
            "agent fair state, ledger, contract, and district must be "
            "synchronized together"
        )
    state = resources["state"]["metadata"]
    ledger_descriptor = resources["event-ledger"]
    ledger = ledger_descriptor["metadata"]
    contract = resources["agent-contract"]["metadata"]
    district = resources["district"]["metadata"]
    projection_fields = (
        "lineage_sha256",
        "rankings_sha256",
        "screening_sha256",
        "voting_sha256",
        "winner_selection_sha256",
        "winner_submission_ids",
    )
    if (
        state["event_count"] != ledger["event_count"]
        or state["event_head"] != ledger["event_head"]
        or state["event_ledger_sha256"] != ledger_descriptor["sha256"]
        or state["contract_digest"] != contract["contract_digest"]
        or state["contract_digest"] != district["contract_digest"]
        or state["district_digest"] != district["district_digest"]
        or state["district_id"] != district["district_id"]
        or state["resource_totals"] != district["resource_totals"]
        or state["winner_submission_ids"]
        != district["winner_submission_ids"]
        or any(
            (
                district[field] if field == "lineage_sha256" else state[field]
            )
            != ledger[field]
            for field in projection_fields
        )
    ):
        raise SyncError(
            "agent fair state, event, contract, or district coherence failed"
        )
    expected_bundle = frame_hash_value(
        AGENT_FAIR_BUNDLE_SPACE,
        {
            "contract_digest": contract["contract_digest"],
            "district_digest": district["district_digest"],
            "event_count": ledger["event_count"],
            "event_head": ledger["event_head"],
            "event_ledger_sha256": ledger_descriptor["sha256"],
            "state_digest": state["state_digest"],
        },
    )
    if (
        state["bundle_digest"] != expected_bundle
        or district["bundle_digest"] != expected_bundle
        or (
            ledger["event_count"] == AGENT_FAIR_BASE_EVENT_COUNT
            and (
                expected_bundle != AGENT_FAIR_BASE_BUNDLE_DIGEST
                or district["district_digest"]
                != AGENT_FAIR_BASE_DISTRICT_DIGEST
                or contract["bundle_digest"] != expected_bundle
            )
        )
        or (
            ledger["event_count"] > AGENT_FAIR_BASE_EVENT_COUNT
            and contract["bundle_digest"]
            != AGENT_FAIR_BASE_BUNDLE_DIGEST
        )
    ):
        raise SyncError("agent fair bundle digest binding mismatch")


def validate_data_descriptor(descriptor: Any) -> Dict[str, Any]:
    if type(descriptor) is not dict:
        raise SyncError("data descriptor must be an object")
    path = _safe_relative_path(descriptor.get("path"))
    digest = descriptor.get("sha256")
    size = descriptor.get("size")
    media_type = descriptor.get("media_type")
    kind = descriptor.get("kind")
    metadata = copy.deepcopy(descriptor.get("metadata"))
    if (
        kind == "agent-amusement-park-object"
        and type(metadata) is dict
        and path == "apps/agent-park/agent-contract.json"
        and metadata.get("resource_type") == "agent-contract"
        and metadata.get("schema") == AGENT_PARK_CONTRACT_V1_SCHEMA
    ):
        metadata["resource_type"] = "agent-contract-v1"
    if (
        kind == "agent-amusement-park-object"
        and type(metadata) is dict
        and path == "apps/agent-park/park-state.json"
        and metadata.get("resource_type") == "state"
        and metadata.get("schema")
        == "rappterzoo-agent-amusement-park/1"
        and metadata.get("event_count")
        == AGENT_PARK_SEASON1_EVENT_COUNT
        and metadata.get("agent_contract") is None
    ):
        metadata["agent_contract"] = "agent-contract.json"
    public_root = any(
        path.startswith("apps/{}/".format(directory))
        for directory in (
            "agent-fair",
            "agent-park",
            "attention",
            "fold",
            "fold-at-home",
            "looking-glass",
            "shards",
        )
    )
    if (
        not public_root
        or kind not in {
            "agent-worlds-fair-object",
            "agent-amusement-park-object",
            "attention-group-object",
            "attention-dimension-object",
            "fold-action-receipt",
            "fold-challenge",
            "fold-control-award-receipt",
            "fold-proof-receipt",
            "fold-shard-assignment",
            "fold-shard-dimension-object",
            "fold-shard-lease",
            "fold-shard-result-object",
            "looking-glass-scene-object",
        }
        or type(digest) is not str
        or not HASH_RE.fullmatch(digest)
        or descriptor.get("content_id")
        != "sha256:{}".format(digest)
        or type(size) is not int
        or not 0 <= size <= MAX_PUBLIC_DATA_BYTES
        or media_type not in {
            "application/json",
            "application/x-ndjson",
        }
        or type(descriptor.get("url")) is not str
        or type(metadata) is not dict
        or descriptor.get("verification") != {
            "algorithm": "sha256",
            "required": True,
        }
    ):
        raise SyncError("invalid or unpinned public data descriptor")
    if kind == "agent-worlds-fair-object" and (
        path != {
            "agent-contract": "apps/agent-fair/agent-contract.json",
            "district": "apps/agent-fair/district.json",
            "event-ledger": "apps/agent-fair/events.jsonl",
            "state": "apps/agent-fair/fair-state.json",
        }.get(metadata.get("resource_type"))
        or metadata.get("fair_id") != AGENT_FAIR_ID
        or metadata.get("visibility") != "public-metadata"
        or metadata.get("resource_type")
        not in {"agent-contract", "district", "event-ledger", "state"}
        or type(metadata.get("schema")) is not str
    ):
        raise SyncError("invalid agent fair descriptor metadata")
    if (
        kind == "agent-worlds-fair-object"
        and metadata["resource_type"] == "event-ledger"
        and (
            metadata.get("schema") != AGENT_FAIR_EVENT_SCHEMA
            or type(metadata.get("event_count")) is not int
            or metadata["event_count"] < AGENT_FAIR_BASE_EVENT_COUNT
            or type(metadata.get("event_head")) is not str
            or not HASH_RE.fullmatch(metadata["event_head"])
            or metadata.get("release_prefix_sha256")
            != AGENT_FAIR_BASE_PREFIX_SHA256
            or metadata.get("winner_submission_ids")
            != AGENT_FAIR_WINNERS
            or any(
                type(metadata.get(field)) is not str
                or not HASH_RE.fullmatch(metadata[field])
                for field in (
                    "lineage_sha256",
                    "rankings_sha256",
                    "screening_sha256",
                    "voting_sha256",
                    "winner_selection_sha256",
                )
            )
        )
    ):
        raise SyncError("invalid agent fair event descriptor metadata")
    if (
        kind == "agent-worlds-fair-object"
        and metadata["resource_type"] == "state"
        and (
            metadata.get("schema") != AGENT_FAIR_STATE_SCHEMA
            or metadata.get("district_id") != AGENT_FAIR_DISTRICT_ID
            or metadata.get("submission_count") != 12
            or metadata.get("winner_count") != 4
            or metadata.get("winner_submission_ids")
            != AGENT_FAIR_WINNERS
            or type(metadata.get("event_count")) is not int
            or metadata["event_count"] < AGENT_FAIR_BASE_EVENT_COUNT
            or any(
                type(metadata.get(field)) is not str
                or not HASH_RE.fullmatch(metadata[field])
                for field in (
                    "bundle_digest",
                    "contract_digest",
                    "district_digest",
                    "event_head",
                    "event_ledger_sha256",
                    "rankings_sha256",
                    "screening_sha256",
                    "state_digest",
                    "voting_sha256",
                    "winner_selection_sha256",
                )
            )
        )
    ):
        raise SyncError("invalid agent fair state descriptor metadata")
    if (
        kind == "agent-worlds-fair-object"
        and metadata["resource_type"] == "agent-contract"
        and (
            metadata.get("schema") != AGENT_FAIR_CONTRACT_SCHEMA
            or metadata.get("contract_digest")
            != AGENT_FAIR_CONTRACT_DIGEST
            or metadata.get("bundle_digest")
            != AGENT_FAIR_BASE_BUNDLE_DIGEST
            or metadata.get("action_limit") != 50
            or metadata.get("attraction_limits")
            != AGENT_FAIR_ATTRACTION_LIMITS
            or metadata.get("synthetic_only") is not True
        )
    ):
        raise SyncError("invalid agent fair contract descriptor metadata")
    if (
        kind == "agent-worlds-fair-object"
        and metadata["resource_type"] == "district"
        and (
            metadata.get("schema") != AGENT_FAIR_DISTRICT_SCHEMA
            or metadata.get("district_id") != AGENT_FAIR_DISTRICT_ID
            or metadata.get("winner_count") != 4
            or metadata.get("winner_submission_ids")
            != AGENT_FAIR_WINNERS
            or metadata.get("resource_capacity")
            != AGENT_FAIR_DISTRICT_CAPACITY
            or any(
                type(metadata.get(field)) is not str
                or not HASH_RE.fullmatch(metadata[field])
                for field in (
                    "bundle_digest",
                    "contract_digest",
                    "district_digest",
                    "lineage_sha256",
                )
            )
        )
    ):
        raise SyncError("invalid agent fair district descriptor metadata")
    if kind == "agent-amusement-park-object" and (
        path != {
            "agent-contract-v1": "apps/agent-park/agent-contract.json",
            "agent-contract-v2": "apps/agent-park/agent-contract-v2.json",
            "event-ledger": "apps/agent-park/events.jsonl",
            "state": "apps/agent-park/park-state.json",
        }.get(metadata.get("resource_type"))
        or metadata.get("park_id")
        != "park.rappterzoo-agent-amusement-park"
        or metadata.get("visibility") != "public-metadata"
        or metadata.get("resource_type")
        not in {
            "agent-contract-v1",
            "agent-contract-v2",
            "event-ledger",
            "state",
        }
        or type(metadata.get("schema")) is not str
    ):
        raise SyncError("invalid agent amusement park descriptor metadata")
    if (
        kind == "agent-amusement-park-object"
        and metadata["resource_type"] in {"event-ledger", "state"}
        and (
            type(metadata.get("event_count")) is not int
            or metadata["event_count"] < 1
            or type(metadata.get("event_head")) is not str
            or not HASH_RE.fullmatch(metadata["event_head"])
        )
    ):
        raise SyncError("agent amusement park ledger metadata is invalid")
    if (
        kind == "agent-amusement-park-object"
        and metadata["resource_type"] == "state"
        and (
            type(metadata.get("night_count")) is not int
            or metadata["night_count"] < 7
            or metadata.get("agent_contract") not in {
                "agent-contract.json",
                "agent-contract-v2.json",
            }
            or metadata.get("schema")
            != (
                "rappterzoo-agent-amusement-park/2"
                if metadata.get("agent_contract")
                == "agent-contract-v2.json"
                else "rappterzoo-agent-amusement-park/1"
            )
            or (
                metadata.get("agent_contract") == "agent-contract.json"
                and metadata.get("event_count")
                != AGENT_PARK_SEASON1_EVENT_COUNT
            )
            or (
                metadata.get("agent_contract")
                == "agent-contract-v2.json"
                and (
                    metadata.get("event_count")
                    <= AGENT_PARK_SEASON1_EVENT_COUNT
                    or type(metadata.get("bundle_digest")) is not str
                    or not HASH_RE.fullmatch(metadata["bundle_digest"])
                    or type(metadata.get("state_digest")) is not str
                    or not HASH_RE.fullmatch(metadata["state_digest"])
                )
            )
            or (
                metadata.get("event_ledger_sha256") is not None
                and (
                    type(metadata["event_ledger_sha256"]) is not str
                    or not HASH_RE.fullmatch(
                        metadata["event_ledger_sha256"]
                    )
                )
            )
        )
    ):
        raise SyncError("agent amusement park state must contain seven nights")
    if (
        kind == "agent-amusement-park-object"
        and metadata["resource_type"] in {
            "agent-contract-v1",
            "agent-contract-v2",
        }
        and (
            type(metadata.get("contract_digest")) is not str
            or not HASH_RE.fullmatch(metadata["contract_digest"])
        )
    ):
        raise SyncError("agent amusement park contract digest is invalid")
    if (
        kind == "agent-amusement-park-object"
        and metadata["resource_type"] == "agent-contract-v2"
        and (
            metadata.get("schema") != AGENT_PARK_CONTRACT_V2_SCHEMA
            or metadata.get("action_limit") != AGENT_PARK_V2_ACTION_LIMIT
            or metadata.get("mcp_mapping") != AGENT_PARK_V2_MCP_MAPPING
            or type(metadata.get("legacy_contract_sha256")) is not str
            or not HASH_RE.fullmatch(metadata["legacy_contract_sha256"])
            or type(metadata.get("season2_event_count")) is not int
            or metadata["season2_event_count"] < 1
            or type(metadata.get("season2_head")) is not str
            or not HASH_RE.fullmatch(metadata["season2_head"])
            or type(metadata.get("bundle_digest")) is not str
            or not HASH_RE.fullmatch(metadata["bundle_digest"])
        )
    ):
        raise SyncError("invalid agent amusement park contract v2 metadata")
    if (
        kind == "agent-amusement-park-object"
        and metadata["resource_type"] == "agent-contract-v2"
    ):
        _validate_agent_park_v2_hashing(
            metadata.get("canonicalization_and_hashing")
        )
    if kind in {
        "attention-dimension-object",
        "fold-shard-dimension-object",
    }:
        branches = metadata.get("branches_present")
        drift = metadata.get("drift")
        if (
            type(metadata.get("base_record_id")) is not str
            or not metadata["base_record_id"]
            or type(branches) is not list
            or not branches
            or branches != [
                branch
                for branch in ("hot", "cold")
                if branch in branches
            ]
            or metadata.get("merge_order") != ["hot", "cold"]
            or type(drift) not in {dict, list}
            or metadata.get("drift_sha256")
            != sha256_bytes(stable_json_bytes(drift))
        ):
            raise SyncError("dimension descriptor lacks deterministic drift metadata")
    if kind == "looking-glass-scene-object" and (
        not path.startswith("apps/looking-glass/")
        or metadata.get("schema")
        != "rappterzoo-looking-glass-scene/1"
        or metadata.get("visibility") != "public-metadata"
        or type(metadata.get("experience_id")) is not str
        or not metadata["experience_id"]
        or type(metadata.get("target_frame_hash")) is not str
        or not HASH_RE.fullmatch(metadata["target_frame_hash"])
        or type(metadata.get("scene_digest")) is not str
        or not HASH_RE.fullmatch(metadata["scene_digest"])
        or metadata.get("dimension_count") != 7
    ):
        raise SyncError("invalid Looking Glass descriptor metadata")
    if kind.startswith("fold-"):
        synthetic_cycle_kinds = {
            "fold-action-receipt",
            "fold-challenge",
            "fold-control-award-receipt",
            "fold-proof-receipt",
        }
        expected_mode = (
            "proof-of-fold"
            if kind in synthetic_cycle_kinds
            else "assigned"
        )
        if (
            metadata.get("isolated_shard_provenance") is not True
            or type(metadata.get("shard_id")) is not str
            or not metadata["shard_id"]
        ):
            raise SyncError("shard descriptor lacks isolated provenance")
        if (
            metadata.get("frame_control_mode") != expected_mode
            or metadata.get("frame_control") != {
                "mode": expected_mode,
                "proof_race": False,
            }
        ):
            raise SyncError("shard descriptor has invalid frame control mode")
        provenance = metadata.get("provenance")
        if provenance is not None and (
            type(provenance) is not dict
            or metadata.get("provenance_sha256")
            != sha256_bytes(stable_json_bytes(provenance))
        ):
            raise SyncError("shard provenance hash mismatch")
        if kind == "fold-shard-assignment" and (
            type(metadata.get("assignment_id")) is not str
            or not metadata["assignment_id"]
        ):
            raise SyncError("shard assignment lacks assignment id")
        if kind == "fold-shard-lease" and (
            type(metadata.get("lease_id")) is not str
            or not metadata["lease_id"]
            or type(metadata.get("lease_bounds")) is not dict
            or not metadata["lease_bounds"]
        ):
            raise SyncError("shard lease lacks bounded lease metadata")
        required_ids = {
            "fold-action-receipt": "action_receipt_id",
            "fold-challenge": "challenge_id",
            "fold-control-award-receipt": "award_id",
            "fold-proof-receipt": "proof_id",
        }
        required_id = required_ids.get(kind)
        if required_id and (
            type(metadata.get(required_id)) is not str
            or not metadata[required_id]
        ):
            raise SyncError(
                "{} lacks {}".format(kind, required_id)
            )
        if kind in {
            "fold-action-receipt",
            "fold-challenge",
            "fold-control-award-receipt",
            "fold-proof-receipt",
            "fold-shard-dimension-object",
            "fold-shard-result-object",
        } and (
            metadata.get("assembler_status") != "accepted"
            or metadata.get("main_append") is not True
        ):
            raise SyncError("shard result is not assembler accepted")
        if kind in {
            "fold-shard-dimension-object",
            "fold-shard-result-object",
        } and (
            type(metadata.get("lease_id")) is not str
            or not metadata["lease_id"]
        ):
            raise SyncError("assigned shard result lacks lease provenance")
    result = dict(descriptor)
    result["path"] = path
    result["metadata"] = metadata
    return result


def validate_agent_park_descriptor_coherence(
    descriptors: Sequence[Dict[str, Any]],
) -> None:
    resources = {}
    for descriptor in descriptors:
        if descriptor.get("kind") != "agent-amusement-park-object":
            continue
        resource_type = descriptor.get("metadata", {}).get(
            "resource_type"
        )
        if resource_type in resources:
            raise SyncError(
                "agent park publishes a duplicate {} resource".format(
                    resource_type
                )
            )
        resources[resource_type] = descriptor
    if not resources:
        return
    required = {"agent-contract-v1", "event-ledger", "state"}
    if not required.issubset(resources):
        raise SyncError(
            "agent park v1 contract, state, and event ledger must be "
            "synchronized together"
        )
    state = resources.get("state")
    ledger = resources.get("event-ledger")
    state_metadata = state["metadata"]
    ledger_metadata = ledger["metadata"]
    selected = state_metadata.get("agent_contract")
    if selected == "agent-contract-v2.json":
        v2 = resources.get("agent-contract-v2")
        if (
            v2 is None
            or state_metadata.get("bundle_digest")
            != v2["metadata"].get("bundle_digest")
            or v2["metadata"].get("season2_event_count")
            != (
                ledger_metadata.get("event_count")
                - AGENT_PARK_SEASON1_EVENT_COUNT
            )
            or v2["metadata"].get("season2_head")
            != ledger_metadata.get("event_head")
            or ledger_metadata.get("schema")
            != AGENT_PARK_EVENT_SCHEMA_V2
        ):
            raise SyncError(
                "agent park state does not select a coherent v2 contract bundle"
            )
        if (
            v2["metadata"].get("legacy_contract_sha256")
            != resources["agent-contract-v1"].get("sha256")
        ):
            raise SyncError("immutable agent park v1 contract changed")
        expected_bundle = frame_hash_value(
            AGENT_PARK_BUNDLE_V2_HASH_SPACE,
            {
                "contract_digest": v2["metadata"]["contract_digest"],
                "event_count": ledger_metadata["event_count"],
                "event_head": ledger_metadata["event_head"],
                "event_ledger_sha256": ledger["sha256"],
                "state_digest": state_metadata["state_digest"],
            },
        )
        if expected_bundle != v2["metadata"]["bundle_digest"]:
            raise SyncError(
                "agent park v2 bundle digest does not match its resources"
            )
    elif (
        selected != "agent-contract.json"
        or "agent-contract-v2" in resources
    ):
        raise SyncError("agent park state contract selection is inconsistent")
    state_digest = state_metadata.get("event_ledger_sha256")
    if (
        state_metadata.get("event_count")
        != ledger_metadata.get("event_count")
        or state_metadata.get("event_head")
        != ledger_metadata.get("event_head")
        or (
            state_digest is not None
            and state_digest != ledger.get("sha256")
        )
    ):
        raise SyncError(
            "agent park state disagrees with event ledger head, count, or digest"
        )


def validate_data_tombstone(
    value: Any,
    delta_sequence: int,
) -> Dict[str, Any]:
    if type(value) is not dict:
        raise SyncError("data tombstone must be an object")
    path = _safe_relative_path(value.get("path"))
    if value.get("sequence") != delta_sequence:
        raise SyncError("data tombstone sequence mismatch")
    descriptor = validate_data_descriptor(value.get("descriptor"))
    if descriptor["path"] != path:
        raise SyncError("data tombstone descriptor path mismatch")
    result = dict(value)
    result["path"] = path
    result["descriptor"] = descriptor
    return result


def fetch_url(
    url: str,
    headers: Optional[Dict[str, str]] = None,
    max_bytes: int = MAX_DELTA_BYTES,
) -> Tuple[int, Dict[str, str], bytes]:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise SyncError("only HTTP(S) sync sources are supported")
    request = Request(
        url,
        headers={
            "Accept": "application/json, application/atom+xml;q=0.5",
            "User-Agent": "RappterZooSync/1",
            **(headers or {}),
        },
        method="GET",
    )
    try:
        response = urlopen(request, timeout=20)
    except HTTPError as error:
        if error.code == 304:
            return 304, {
                key.lower(): value
                for key, value in error.headers.items()
            }, b""
        raise SyncError("HTTP {} for {}".format(error.code, url)) from error
    except URLError as error:
        raise SyncError("network error for {}: {}".format(url, error.reason))
    with response:
        status = response.getcode()
        response_headers = {
            key.lower(): value
            for key, value in response.headers.items()
        }
        declared = response_headers.get("content-length")
        if declared:
            try:
                declared_size = int(declared)
            except ValueError:
                raise SyncError("invalid Content-Length")
            if declared_size > max_bytes:
                raise SyncError("response exceeds byte limit")
        chunks = []
        received = 0
        while True:
            chunk = response.read(min(65536, max_bytes + 1 - received))
            if not chunk:
                break
            received += len(chunk)
            if received > max_bytes:
                raise SyncError("response exceeds byte limit")
            chunks.append(chunk)
        return status, response_headers, b"".join(chunks)


def connect_state(state_dir: Path) -> sqlite3.Connection:
    state_dir.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(state_dir / "state.sqlite3"))
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS meta (
          key TEXT PRIMARY KEY,
          value TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS deltas (
          sequence INTEGER PRIMARY KEY,
          sha256 TEXT NOT NULL UNIQUE,
          previous_sha256 TEXT,
          source_url TEXT NOT NULL,
          applied_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS apps (
          path TEXT PRIMARY KEY,
          url TEXT NOT NULL,
          sha256 TEXT NOT NULL,
          size INTEGER NOT NULL,
          metadata_json TEXT NOT NULL,
          deleted INTEGER NOT NULL DEFAULT 0,
          delta_sequence INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS tombstones (
          path TEXT NOT NULL,
          delta_sequence INTEGER NOT NULL,
          tombstone_json TEXT NOT NULL,
          PRIMARY KEY (path, delta_sequence)
        );
        CREATE TABLE IF NOT EXISTS data_objects (
          path TEXT PRIMARY KEY,
          kind TEXT NOT NULL,
          url TEXT NOT NULL,
          sha256 TEXT NOT NULL,
          size INTEGER NOT NULL,
          media_type TEXT NOT NULL,
          metadata_json TEXT NOT NULL,
          deleted INTEGER NOT NULL DEFAULT 0,
          delta_sequence INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS data_tombstones (
          path TEXT NOT NULL,
          delta_sequence INTEGER NOT NULL,
          tombstone_json TEXT NOT NULL,
          PRIMARY KEY (path, delta_sequence)
        );
        CREATE TABLE IF NOT EXISTS shard_provenance (
          content_id TEXT PRIMARY KEY,
          path TEXT NOT NULL,
          kind TEXT NOT NULL,
          shard_id TEXT NOT NULL,
          assignment_id TEXT,
          lease_id TEXT,
          provenance_json TEXT NOT NULL,
          delta_sequence INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS frames (
          seq INTEGER PRIMARY KEY,
          frame_hash TEXT NOT NULL UNIQUE,
          event_id TEXT NOT NULL UNIQUE,
          frame_json TEXT NOT NULL,
          delta_sequence INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS objects (
          sha256 TEXT PRIMARY KEY,
          size INTEGER NOT NULL,
          relative_path TEXT NOT NULL,
          verified_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS acknowledgements (
          delta_sha256 TEXT PRIMARY KEY,
          sequence INTEGER NOT NULL UNIQUE,
          acknowledged_at TEXT NOT NULL,
          note TEXT NOT NULL,
          FOREIGN KEY (sequence) REFERENCES deltas(sequence)
        );
        CREATE TABLE IF NOT EXISTS witnesses (
          receipt_sha256 TEXT PRIMARY KEY,
          witness_id TEXT NOT NULL,
          head_sequence INTEGER NOT NULL,
          head_sha256 TEXT NOT NULL,
          chain_fingerprint TEXT NOT NULL,
          created_at TEXT NOT NULL,
          statement_json TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS blocks (
          sequence INTEGER PRIMARY KEY,
          head_sha256 TEXT NOT NULL UNIQUE,
          previous_sha256 TEXT,
          frame_control_mode TEXT NOT NULL,
          next_frame_challenge_seed TEXT NOT NULL,
          proof_of_fold_json TEXT NOT NULL,
          applied_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS local_apps (
          path TEXT PRIMARY KEY,
          sha256 TEXT NOT NULL,
          size INTEGER NOT NULL,
          metadata_json TEXT NOT NULL,
          relative_path TEXT NOT NULL,
          added_at TEXT NOT NULL
        );
        """
    )
    data_columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(data_objects)")
    }
    if "kind" not in data_columns:
        connection.execute(
            """
            ALTER TABLE data_objects
            ADD COLUMN kind TEXT NOT NULL
            DEFAULT 'attention-group-object'
            """
        )
    block_columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(blocks)")
    }
    if "frame_control_mode" not in block_columns:
        connection.execute(
            """
            ALTER TABLE blocks
            ADD COLUMN frame_control_mode TEXT NOT NULL
            DEFAULT 'observer'
            """
        )
    connection.commit()
    return connection


def _get_meta(connection: sqlite3.Connection, key: str) -> Optional[str]:
    row = connection.execute(
        "SELECT value FROM meta WHERE key = ?",
        (key,),
    ).fetchone()
    return row["value"] if row else None


def _set_meta(
    connection: sqlite3.Connection,
    key: str,
    value: str,
) -> None:
    connection.execute(
        "INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)",
        (key, value),
    )


def validate_index(
    index: Any,
    allow_synthetic_proofs: bool = False,
) -> List[Dict[str, Any]]:
    if (
        type(index) is not dict
        or index.get("schema") != INDEX_SCHEMA
        or index.get("profile") != PROFILE
        or index.get("transparency") != TRANSPARENCY_MODEL
        or index.get("rollout") != SOAK_ROLLOUT
        or index.get("challenge_state_machine")
        != CHALLENGE_STATE_MACHINE
        or index.get("frame_control_schema")
        != FRAME_CONTROL_SCHEMA
        or type(index.get("stream_id")) is not str
        or not index.get("stream_id")
        or type(index.get("deltas")) is not list
    ):
        raise SyncError("remote index has the wrong schema")
    cursor = index.get("cursor")
    rate_budget = index.get("rate_budget")
    pinning = index.get("pinning")
    if (
        type(cursor) is not dict
        or cursor.get("kind") != "immutable-since-seq"
        or cursor.get("initial_since_seq") != -1
        or cursor.get("reset_policy") != "reject"
        or type(rate_budget) is not dict
        or rate_budget.get("constant_polling") is not False
        or rate_budget.get("conditional_get")
        != "required-after-first-sync"
        or rate_budget.get("recommended_min_sync_interval_seconds")
        != 1800
        or type(pinning) is not dict
        or pinning.get("app_content") != "sha256-required"
        or pinning.get("mutable_skill_references") != "reject-unpinned"
    ):
        raise SyncError("remote index lacks safe cursor or rate metadata")
    entries = index["deltas"]
    if index.get("delta_count") != len(entries):
        raise SyncError("remote index delta count mismatch")
    previous = None
    seen_hashes = set()
    validated = []
    for expected_sequence, entry in enumerate(entries):
        if type(entry) is not dict:
            raise SyncError("remote index delta entry is malformed")
        digest = entry.get("sha256")
        path = entry.get("path")
        segment_hashes = entry.get("segment_hashes")
        entry_profile = entry.get("profile")
        block = entry.get("block")
        if (
            entry.get("sequence") != expected_sequence
            or type(digest) is not str
            or not HASH_RE.fullmatch(digest)
            or digest in seen_hashes
            or entry.get("previous_delta") != previous
            or path != "deltas/{}.json".format(digest)
            or type(entry.get("size")) is not int
            or not 0 < entry["size"] <= MAX_DELTA_BYTES
            or entry.get("since_seq") != expected_sequence - 1
            or entry.get("through_seq") != expected_sequence
            or type(segment_hashes) is not dict
            or type(segment_hashes.get("apps")) is not str
            or not HASH_RE.fullmatch(segment_hashes["apps"])
            or type(segment_hashes.get("frames")) is not str
            or not HASH_RE.fullmatch(segment_hashes["frames"])
            or entry_profile not in {
                "legacy",
                PROFILE_V2,
                PROFILE_V3,
                PROFILE_V4,
                PROFILE_V5,
                PROFILE_V6,
                PROFILE_V7,
                PROFILE_V8,
                PROFILE_V9,
                PROFILE,
            }
            or (
                entry_profile in {
                    PROFILE_V3,
                    PROFILE_V4,
                    PROFILE_V5,
                    PROFILE_V6,
                    PROFILE_V7,
                    PROFILE_V8,
                    PROFILE_V9,
                    PROFILE,
                }
                and (
                    type(segment_hashes.get("data")) is not str
                    or not HASH_RE.fullmatch(segment_hashes["data"])
                )
            )
            or type(block) is not dict
            or block.get("model") != BLOCK_MODEL
            or block.get("consensus") != "none"
            or block.get("token") is not False
            or block.get("mining") is not False
            or block.get("resulting_head") != {
                "sequence": expected_sequence,
                "sha256": digest,
            }
            or block.get("next_frame_challenge_seed")
            != next_challenge_seed(digest)
            or type(block.get("proof_of_fold")) is not dict
            or block.get("rollout") != SOAK_ROLLOUT
        ):
            raise SyncError("remote index has a replay, gap, or bad link")
        proof = block["proof_of_fold"]
        frame_control = block.get("frame_control")
        if (
            proof.get("frame_control_mode")
            not in {"observer", "proof-of-fold"}
            or type(frame_control) is not dict
            or frame_control.get("proof_race") is not False
            or frame_control.get("mode")
            not in {"observer", "assigned", "proof-of-fold"}
            or (
                frame_control.get("mode") == "proof-of-fold"
                and not allow_synthetic_proofs
            )
            or (
                proof.get("cycles")
                and not allow_synthetic_proofs
            )
            or (
                proof.get("synthetic_test_only") is True
                and not allow_synthetic_proofs
            )
        ):
            raise SyncError(
                "live proof-of-fold control is disabled during public soak"
            )
        seen_hashes.add(digest)
        validated.append(entry)
        previous = digest
    head = index.get("head")
    if entries:
        if (
            type(head) is not dict
            or head.get("sequence") != entries[-1]["sequence"]
            or head.get("sha256") != entries[-1]["sha256"]
            or head.get("path") != entries[-1]["path"]
            or head.get("url") != entries[-1]["url"]
            or index.get("next_frame_challenge_seed")
            != entries[-1]["block"]["next_frame_challenge_seed"]
        ):
            raise SyncError("remote index head mismatch")
    elif (
        head is not None
        or index.get("next_frame_challenge_seed") is not None
    ):
        raise SyncError("empty remote index must have a null head")
    if cursor.get("head_seq") != (
        entries[-1]["sequence"] if entries else -1
    ):
        raise SyncError("remote immutable cursor head mismatch")
    return validated


def validate_delta(
    data: bytes,
    entry: Dict[str, Any],
    expected_stream_id: Optional[str] = None,
    allow_synthetic_proofs: bool = False,
) -> Dict[str, Any]:
    expected_stream_id = expected_stream_id or DEFAULT_STREAM_ID
    if len(data) != entry["size"]:
        raise SyncError("delta content size mismatch")
    if sha256_bytes(data) != entry["sha256"]:
        raise SyncError("delta content hash mismatch")
    delta = load_json_bytes(data, "delta {}".format(entry["sequence"]))
    if stable_json_bytes(delta) != data:
        raise SyncError("delta is not canonical deterministic JSON")
    if (
        type(delta) is not dict
        or delta.get("schema") != DELTA_SCHEMA
        or delta.get("stream_id") != expected_stream_id
        or delta.get("sequence") != entry["sequence"]
        or delta.get("previous_delta") != entry["previous_delta"]
        or type(delta.get("changes")) is not dict
    ):
        raise SyncError("delta metadata mismatch")
    changes = delta["changes"]
    profile = delta.get("profile")
    legacy = "segments" not in delta
    legacy_keys = {
        "app_tombstones",
        "app_upserts",
        "frame_appends",
    }
    profile3_keys = legacy_keys | {
        "data_tombstones",
        "data_upserts",
    }
    expected_keys = (
        profile3_keys
        if profile in {
            PROFILE_V3,
            PROFILE_V4,
            PROFILE_V5,
            PROFILE_V6,
            PROFILE_V7,
            PROFILE_V8,
            PROFILE_V9,
            PROFILE,
        }
        else legacy_keys
    )
    if set(changes) != expected_keys:
        raise SyncError("delta changes have the wrong shape")
    if not all(type(changes[key]) is list for key in changes):
        raise SyncError("delta changes must be arrays")
    computed_segments = segment_metadata(changes)
    expected_hashes = entry["segment_hashes"]
    if (
        computed_segments["apps"]["sha256"] != expected_hashes["apps"]
        or computed_segments["frames"]["sha256"]
        != expected_hashes["frames"]
        or (
            profile in {
                PROFILE_V3,
                PROFILE_V4,
                PROFILE_V5,
                PROFILE_V6,
                PROFILE_V7,
                PROFILE_V8,
                PROFILE_V9,
                PROFILE,
            }
            and computed_segments["data"]["sha256"]
            != expected_hashes.get("data")
        )
    ):
        raise SyncError("delta segment hash mismatch")
    if legacy:
        if (
            delta["sequence"] != 0
            or profile is not None
            or entry.get("profile") != "legacy"
        ):
            raise SyncError("only genesis may use the legacy delta profile")
    elif (
        profile not in {
            PROFILE_V2,
            PROFILE_V3,
            PROFILE_V4,
            PROFILE_V5,
            PROFILE_V6,
            PROFILE_V7,
            PROFILE_V8,
            PROFILE_V9,
            PROFILE,
        }
        or entry.get("profile") != profile
        or delta.get("since_seq") != delta["sequence"] - 1
        or delta.get("through_seq") != delta["sequence"]
        or delta.get("segments") != computed_segments
    ):
        raise SyncError("delta immutable since_seq checkpoint mismatch")
    if (
        profile == PROFILE
        and delta.get("transparency") != TRANSPARENCY_MODEL
    ):
        raise SyncError("delta makes an invalid authority or consensus claim")
    if profile == PROFILE and (
        delta.get("rollout") != SOAK_ROLLOUT
        or delta.get("challenge_state_machine")
        != CHALLENGE_STATE_MACHINE
        or delta.get("frame_control_schema")
        != FRAME_CONTROL_SCHEMA
    ):
        raise SyncError("delta violates the initial soak activation gate")
    upserts = [
        validate_descriptor(descriptor, require_pin=not legacy)
        for descriptor in changes["app_upserts"]
    ]
    tombstones = [
        validate_tombstone(
            value,
            delta["sequence"],
            require_pin=not legacy,
        )
        for value in changes["app_tombstones"]
    ]
    paths = [item["path"] for item in upserts]
    if len(paths) != len(set(paths)):
        raise SyncError("delta repeats an app upsert")
    tombstone_paths = [item["path"] for item in tombstones]
    if len(tombstone_paths) != len(set(tombstone_paths)):
        raise SyncError("delta repeats a tombstone")
    if set(paths) & set(tombstone_paths):
        raise SyncError("delta both upserts and tombstones one path")
    data_upserts = [
        validate_data_descriptor(descriptor)
        for descriptor in changes.get("data_upserts", [])
    ]
    data_tombstones = [
        validate_data_tombstone(value, delta["sequence"])
        for value in changes.get("data_tombstones", [])
    ]
    if any(
        tombstone.get("descriptor", {}).get("kind")
        == "agent-worlds-fair-object"
        for tombstone in data_tombstones
    ):
        raise SyncError("immutable agent fair objects cannot be tombstoned")
    if profile == PROFILE:
        if any(
            tombstone.get("descriptor", {}).get("metadata", {}).get(
                "resource_type"
            ) in {
                "agent-contract",
                "agent-contract-v1",
                "agent-contract-v2",
                "district",
                "event-ledger",
                "state",
            }
            for tombstone in data_tombstones
        ):
            raise SyncError(
                "profile 10 cannot tombstone append-only agent history"
            )
    data_paths = [item["path"] for item in data_upserts]
    data_tombstone_paths = [item["path"] for item in data_tombstones]
    if len(data_paths) != len(set(data_paths)):
        raise SyncError("delta repeats a data upsert")
    if len(data_tombstone_paths) != len(set(data_tombstone_paths)):
        raise SyncError("delta repeats a data tombstone")
    if set(data_paths) & set(data_tombstone_paths):
        raise SyncError("delta both upserts and tombstones one data path")
    changes["app_upserts"] = upserts
    changes["app_tombstones"] = tombstones
    if profile in {
        PROFILE_V3,
        PROFILE_V4,
        PROFILE_V5,
        PROFILE_V6,
        PROFILE_V7,
        PROFILE_V8,
        PROFILE_V9,
        PROFILE,
    }:
        changes["data_upserts"] = data_upserts
        changes["data_tombstones"] = data_tombstones
    _validate_agent_fair_release_segment(changes)
    default_proof = {
        "acceptance": "centralized-publisher-assembler",
        "cycles": [],
        "frame_control_mode": "observer",
        "status": "disabled-observer",
        "synthetic_test_only": False,
    }
    cycle_kinds = {
        "fold-action-receipt",
        "fold-challenge",
        "fold-control-award-receipt",
        "fold-proof-receipt",
    }
    has_cycle_objects = any(
        item.get("kind") in cycle_kinds
        for item in changes.get("data_upserts", [])
    )
    if has_cycle_objects and not allow_synthetic_proofs:
        raise SyncError(
            "live proof-of-fold control is disabled during public soak"
        )
    expected_proof = (
        delta.get("proof_of_fold", default_proof)
        if profile == PROFILE
        else default_proof
    )
    if (
        profile == PROFILE
        and expected_proof != proof_of_fold_metadata(
            changes,
            synthetic_test_mode=bool(
                expected_proof.get("synthetic_test_only")
            ),
        )
    ):
        raise SyncError("proof-of-fold receipts do not match accepted objects")
    if expected_proof.get("cycles") and not allow_synthetic_proofs:
        raise SyncError(
            "live proof-of-fold control is disabled during public soak"
        )
    if entry["block"]["proof_of_fold"] != expected_proof:
        raise SyncError("block proof-of-fold metadata mismatch")
    expected_frame_control = frame_control_metadata(
        changes,
        expected_proof,
    )
    if profile == PROFILE and (
        delta.get("frame_control") != expected_frame_control
    ):
        raise SyncError("delta frame-control mode mismatch")
    if entry["block"].get("frame_control") != expected_frame_control:
        raise SyncError("block frame-control mode mismatch")
    return delta


def _load_frame_checkpoint(
    connection: sqlite3.Connection,
) -> Tuple[Optional[Dict[str, Any]], Set[str]]:
    row = connection.execute(
        "SELECT frame_json FROM frames ORDER BY seq DESC LIMIT 1"
    ).fetchone()
    previous = json.loads(row["frame_json"]) if row else None
    event_ids = {
        item["event_id"]
        for item in connection.execute("SELECT event_id FROM frames")
    }
    return previous, event_ids


def _object_relative_path(digest: str) -> str:
    return "objects/{}/{}".format(digest[:2], digest)


def _object_path(state_dir: Path, digest: str) -> Path:
    return state_dir / _object_relative_path(digest)


def _store_object(
    state_dir: Path,
    digest: str,
    data: bytes,
) -> Tuple[Path, bool]:
    if sha256_bytes(data) != digest:
        raise SyncError("object hash mismatch")
    path = _object_path(state_dir, digest)
    if path.exists():
        existing = path.read_bytes()
        if sha256_bytes(existing) == digest:
            return path, False
    path.parent.mkdir(parents=True, exist_ok=True)
    staging = path.with_name(
        "{}.{}.new".format(path.name, uuid.uuid4().hex)
    )
    try:
        staging.write_bytes(data)
        os.replace(str(staging), str(path))
    finally:
        try:
            staging.unlink()
        except OSError:
            pass
    return path, True


def _validate_agent_park_object(
    parsed: Any,
    descriptor: Dict[str, Any],
    checkpoint: Optional[Tuple[int, str, str]] = None,
) -> None:
    metadata = descriptor["metadata"]
    resource_type = metadata["resource_type"]
    if resource_type == "state":
        ledger = parsed.get("event_ledger") if type(parsed) is dict else None
        is_v2 = metadata["agent_contract"] == "agent-contract-v2.json"
        integrity = parsed.get("integrity") if type(parsed) is dict else None
        seasons = parsed.get("seasons") if type(parsed) is dict else None
        season1 = (
            seasons[0]
            if isinstance(seasons, list) and len(seasons) == 2
            else None
        )
        season2 = (
            seasons[1]
            if isinstance(seasons, list) and len(seasons) == 2
            else None
        )
        if (
            type(parsed) is not dict
            or parsed.get("schema")
            != (
                "rappterzoo-agent-amusement-park/2"
                if is_v2
                else "rappterzoo-agent-amusement-park/1"
            )
            or parsed.get("park_id") != metadata["park_id"]
            or parsed.get("night_count") != metadata["night_count"]
            or parsed.get("agent_contract") != metadata["agent_contract"]
            or type(ledger) is not dict
            or ledger.get("event_count") != metadata["event_count"]
            or ledger.get("head") != metadata["event_head"]
            or (
                metadata.get("event_ledger_sha256") is not None
                and ledger.get("sha256")
                != metadata["event_ledger_sha256"]
            )
            or (
                is_v2
                and (
                    type(integrity) is not dict
                    or integrity.get("algorithm") != "sha256"
                    or integrity.get("bundle_digest")
                    != metadata.get("bundle_digest")
                    or integrity.get("state_digest")
                    != metadata.get("state_digest")
                    or parsed.get("legacy_agent_contract")
                    != "agent-contract.json"
                    or parsed.get("latest_season") != 2
                    or parsed.get("season") != 2
                    or type(season1) is not dict
                    or season1.get("season") != 1
                    or season1.get("first_seq") != 0
                    or season1.get("last_seq")
                    != AGENT_PARK_SEASON1_EVENT_COUNT - 1
                    or season1.get("event_count")
                    != AGENT_PARK_SEASON1_EVENT_COUNT
                    or season1.get("head") != AGENT_PARK_SEASON1_HEAD
                    or season1.get("ledger_prefix_sha256")
                    != AGENT_PARK_SEASON1_PREFIX_SHA256
                    or season1.get("immutable") is not True
                    or season1.get("profile") != 10
                    or season1.get("schema")
                    != AGENT_PARK_EVENT_SCHEMA
                    or type(season2) is not dict
                    or season2.get("season") != 2
                    or season2.get("first_seq")
                    != AGENT_PARK_SEASON1_EVENT_COUNT
                    or season2.get("last_seq")
                    != ledger.get("event_count") - 1
                    or season2.get("event_count")
                    != (
                        ledger.get("event_count")
                        - AGENT_PARK_SEASON1_EVENT_COUNT
                    )
                    or season2.get("head") != ledger.get("head")
                    or season2.get("schema")
                    != AGENT_PARK_EVENT_SCHEMA_V2
                )
            )
        ):
            raise SyncError(
                "agent amusement park state mismatches descriptor"
            )
        if is_v2:
            projected = copy.deepcopy(parsed)
            projected["integrity"].pop("bundle_digest", None)
            projected["integrity"].pop("state_digest", None)
            if integrity["state_digest"] != frame_hash_value(
                AGENT_PARK_STATE_V2_HASH_SPACE,
                projected,
            ):
                raise SyncError(
                    "agent amusement park state v2 digest mismatch"
                )
        return
    if resource_type == "agent-contract-v1":
        if (
            type(parsed) is not dict
            or parsed.get("schema")
            != AGENT_PARK_CONTRACT_V1_SCHEMA
            or parsed.get("park_id") != metadata["park_id"]
            or type(parsed.get("integrity")) is not dict
            or parsed["integrity"].get("contract_digest")
            != metadata["contract_digest"]
        ):
            raise SyncError(
                "agent amusement park contract mismatches descriptor"
            )
        return
    if resource_type == "agent-contract-v2":
        _validate_agent_park_v2_contract(parsed)
        integrity = parsed["integrity"]
        if (
            integrity["contract_digest"] != metadata["contract_digest"]
            or integrity["bundle_digest"] != metadata["bundle_digest"]
            or parsed["canonicalization_and_hashing"]
            != metadata["canonicalization_and_hashing"]
            or parsed["mcp_mapping"] != metadata["mcp_mapping"]
            or parsed["action_limit"] != metadata["action_limit"]
            or parsed["legacy_contract"]["sha256"]
            != metadata["legacy_contract_sha256"]
            or parsed["seasons"]["season_2"]["event_count"]
            != metadata["season2_event_count"]
            or parsed["seasons"]["season_2"]["head"]
            != metadata["season2_head"]
        ):
            raise SyncError(
                "agent amusement park contract v2 mismatches descriptor"
            )
        return
    if (
        resource_type != "event-ledger"
        or not isinstance(parsed, list)
        or not parsed
    ):
        raise SyncError("agent amusement park ledger mismatches descriptor")
    validate_agent_park_event_ledger(parsed)
    if (
        parsed[-1].get("event_hash") != metadata["event_head"]
        or len(parsed) != metadata["event_count"]
    ):
        raise SyncError("agent amusement park ledger mismatches descriptor")
    if checkpoint is None:
        return
    previous_count, previous_head, previous_digest = checkpoint
    if len(parsed) < previous_count:
        raise SyncError("agent park event ledger was truncated")
    if previous_count == 0:
        return
    if parsed[previous_count - 1]["event_hash"] != previous_head:
        raise SyncError("agent park event ledger forked from verified prefix")
    if sha256_bytes(
        agent_park_event_ledger_bytes(parsed[:previous_count])
    ) != previous_digest:
        raise SyncError(
            "agent park event ledger rewrites the verified byte prefix"
        )


def _validate_agent_fair_object(
    parsed: Any,
    descriptor: Dict[str, Any],
    checkpoint: Optional[Tuple[int, str, str]] = None,
) -> None:
    resource_type = descriptor["metadata"]["resource_type"]
    if resource_type == "state":
        actual = _validate_agent_fair_state(parsed)
    elif resource_type == "agent-contract":
        actual = _validate_agent_fair_contract(parsed)
    elif resource_type == "district":
        actual = _validate_agent_fair_district(parsed)
    elif resource_type == "event-ledger":
        actual = _agent_fair_ledger_metadata(parsed)
    else:
        raise SyncError("unknown agent fair resource type")
    if actual != descriptor["metadata"]:
        raise SyncError(
            "agent fair {} mismatches descriptor".format(resource_type)
        )
    if resource_type != "event-ledger" or checkpoint is None:
        return
    previous_count, previous_head, previous_digest = checkpoint
    if len(parsed) < previous_count:
        raise SyncError("agent fair event ledger was truncated")
    if previous_count == 0:
        return
    if parsed[previous_count - 1]["event_hash"] != previous_head:
        raise SyncError("agent fair event ledger forked from verified prefix")
    if sha256_bytes(
        agent_fair_event_ledger_bytes(parsed[:previous_count])
    ) != previous_digest:
        raise SyncError(
            "agent fair event ledger rewrites the verified byte prefix"
        )


def _validate_descriptor_object(
    data: bytes,
    descriptor: Dict[str, Any],
    park_checkpoint: Optional[Tuple[int, str, str]] = None,
    fair_checkpoint: Optional[Tuple[int, str, str]] = None,
) -> None:
    if descriptor.get("kind") not in {
        "agent-worlds-fair-object",
        "agent-amusement-park-object",
        "attention-group-object",
        "attention-dimension-object",
        "fold-action-receipt",
        "fold-challenge",
        "fold-control-award-receipt",
        "fold-proof-receipt",
        "fold-shard-assignment",
        "fold-shard-dimension-object",
        "fold-shard-lease",
        "fold-shard-result-object",
        "looking-glass-scene-object",
    }:
        return
    parsed = validate_public_data_bytes(
        data,
        descriptor["media_type"],
    )
    if descriptor["kind"].startswith("fold-"):
        validate_shard_object_bytes(parsed, descriptor)
    if descriptor["kind"] == "agent-amusement-park-object":
        if (
            descriptor["metadata"].get("resource_type") == "event-ledger"
            and data != agent_park_event_ledger_bytes(parsed)
        ):
            raise SyncError(
                "agent park event ledger is not canonical byte-prefix JSONL"
            )
        _validate_agent_park_object(
            parsed,
            descriptor,
            checkpoint=park_checkpoint,
        )
    if descriptor["kind"] == "agent-worlds-fair-object":
        if (
            descriptor["metadata"].get("resource_type") == "event-ledger"
            and data != agent_fair_event_ledger_bytes(parsed)
        ):
            raise SyncError(
                "agent fair event ledger is not canonical byte-prefix JSONL"
            )
        _validate_agent_fair_object(
            parsed,
            descriptor,
            checkpoint=fair_checkpoint,
        )
    if descriptor["kind"] == "looking-glass-scene-object" and (
        type(parsed) is not dict
        or parsed.get("schema")
        != "rappterzoo-looking-glass-scene/1"
        or (
            parsed.get("status") != "public-structural-view"
            and (
                parsed.get("visibility") != "public-metadata"
                or parsed.get("experience_id")
                != descriptor["metadata"]["experience_id"]
            )
        )
        or type(parsed.get("target_frame")) is not dict
        or parsed["target_frame"].get("frame_hash")
        != descriptor["metadata"]["target_frame_hash"]
        or type(parsed.get("integrity")) is not dict
        or parsed["integrity"].get("scene_digest")
        != descriptor["metadata"]["scene_digest"]
        or type(parsed.get("dimensions")) is not list
        or len(parsed["dimensions"])
        != descriptor["metadata"]["dimension_count"]
    ):
        raise SyncError("Looking Glass scene does not match descriptor")


def _fetch_app_object(
    descriptor: Dict[str, Any],
    index_url: str,
    state_dir: Path,
    park_checkpoint: Optional[Tuple[int, str, str]] = None,
    fair_checkpoint: Optional[Tuple[int, str, str]] = None,
) -> Tuple[str, int, str, bool]:
    app_url = urljoin(index_url, descriptor["url"])
    status, _headers, data = fetch_url(
        app_url,
        max_bytes=min(MAX_APP_BYTES, descriptor["size"] + 1),
    )
    if status != 200:
        raise SyncError("unexpected app response status {}".format(status))
    if len(data) != descriptor["size"]:
        raise SyncError("object size mismatch for {}".format(descriptor["path"]))
    if sha256_bytes(data) != descriptor["sha256"]:
        raise SyncError("object hash mismatch for {}".format(descriptor["path"]))
    _validate_descriptor_object(
        data,
        descriptor,
        park_checkpoint=park_checkpoint,
        fair_checkpoint=fair_checkpoint,
    )
    path, created = _store_object(
        state_dir,
        descriptor["sha256"],
        data,
    )
    return (
        descriptor["sha256"],
        descriptor["size"],
        path.relative_to(state_dir).as_posix(),
        created,
    )


def _effective_descriptors(
    connection: sqlite3.Connection,
    deltas: Sequence[Tuple[Dict[str, Any], str, Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    effective = {
        row["path"]: {
            "metadata": {},
            "path": row["path"],
            "sha256": row["sha256"],
            "size": row["size"],
            "url": row["url"],
        }
        for row in connection.execute(
            """
            SELECT path, url, sha256, size
            FROM apps WHERE deleted = 0
            """
        )
    }
    for _entry, _delta_url, delta in deltas:
        for descriptor in delta["changes"]["app_upserts"]:
            effective[descriptor["path"]] = descriptor
        for tombstone in delta["changes"]["app_tombstones"]:
            effective.pop(tombstone["path"], None)
    return [
        effective[path]
        for path in sorted(effective)
    ]


def _effective_data_descriptors(
    connection: sqlite3.Connection,
    deltas: Sequence[Tuple[Dict[str, Any], str, Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    effective = {}
    for row in connection.execute(
        """
        SELECT path, kind, url, sha256, size, media_type, metadata_json
        FROM data_objects WHERE deleted = 0
        """
    ):
        try:
            metadata = json.loads(row["metadata_json"])
        except (TypeError, ValueError) as error:
            raise SyncError(
                "stored public data metadata is invalid"
            ) from error
        if type(metadata) is not dict:
            raise SyncError("stored public data metadata must be an object")
        effective[row["path"]] = {
            "content_id": "sha256:{}".format(row["sha256"]),
            "kind": row["kind"],
            "media_type": row["media_type"],
            "metadata": metadata,
            "path": row["path"],
            "sha256": row["sha256"],
            "size": row["size"],
            "url": row["url"],
            "verification": {
                "algorithm": "sha256",
                "required": True,
            },
        }
    for _entry, _delta_url, delta in deltas:
        for descriptor in delta["changes"].get("data_upserts", []):
            effective[descriptor["path"]] = descriptor
        for tombstone in delta["changes"].get("data_tombstones", []):
            effective.pop(tombstone["path"], None)
    return [
        effective[path]
        for path in sorted(effective)
    ]


def _validate_agent_park_transition(
    connection: sqlite3.Connection,
    current_descriptors: Sequence[Dict[str, Any]],
) -> None:
    current = {
        descriptor["path"]: descriptor
        for descriptor in current_descriptors
        if descriptor.get("kind") == "agent-amusement-park-object"
    }
    if not current:
        return
    paths = (
        "apps/agent-park/agent-contract.json",
        "apps/agent-park/events.jsonl",
        "apps/agent-park/park-state.json",
    )
    previous = {}
    for row in connection.execute(
        """
        SELECT path, sha256, metadata_json
        FROM data_objects
        WHERE deleted = 0 AND path IN (?, ?, ?)
        """,
        paths,
    ):
        previous[row["path"]] = {
            "metadata": json.loads(row["metadata_json"]),
            "sha256": row["sha256"],
        }
    if not previous:
        return
    v1_path, ledger_path, state_path = paths
    previous_v1 = previous.get(v1_path)
    if (
        previous_v1 is None
        or v1_path not in current
        or previous_v1["sha256"] != current[v1_path]["sha256"]
    ):
        raise SyncError("immutable agent park v1 contract changed")
    previous_ledger = previous.get(ledger_path)
    previous_state = previous.get(state_path)
    current_ledger = current.get(ledger_path)
    current_state = current.get(state_path)
    if (
        previous_ledger is None
        or previous_state is None
        or current_ledger is None
        or current_state is None
    ):
        raise SyncError("agent park history bundle was removed")
    previous_count = previous_ledger["metadata"].get("event_count")
    current_count = current_ledger["metadata"].get("event_count")
    grew = (
        current_ledger["sha256"] != previous_ledger["sha256"]
        and type(previous_count) is int
        and type(current_count) is int
        and current_count > previous_count
    )
    if (
        current_ledger["sha256"] != previous_ledger["sha256"]
        and not grew
    ):
        raise SyncError("agent park event ledger is not valid growth")
    if current_state["sha256"] != previous_state["sha256"] and not grew:
        raise SyncError(
            "agent park state replacement requires valid ledger growth"
        )


def _validate_agent_fair_transition(
    connection: sqlite3.Connection,
    current_descriptors: Sequence[Dict[str, Any]],
) -> None:
    current = {
        descriptor["path"]: descriptor
        for descriptor in current_descriptors
        if descriptor.get("kind") == "agent-worlds-fair-object"
    }
    if not current:
        return
    paths = (
        "apps/agent-fair/agent-contract.json",
        "apps/agent-fair/district.json",
        "apps/agent-fair/events.jsonl",
        "apps/agent-fair/fair-state.json",
    )
    previous = {}
    for row in connection.execute(
        """
        SELECT path, sha256, metadata_json
        FROM data_objects
        WHERE deleted = 0 AND path IN (?, ?, ?, ?)
        """,
        paths,
    ):
        previous[row["path"]] = {
            "metadata": json.loads(row["metadata_json"]),
            "sha256": row["sha256"],
        }
    if not previous:
        return
    if set(previous) != set(paths) or set(current) != set(paths):
        raise SyncError("agent fair immutable release bundle was removed")
    contract_path, district_path, ledger_path, state_path = paths
    if previous[contract_path]["sha256"] != current[contract_path]["sha256"]:
        raise SyncError("immutable agent fair contract changed")
    previous_ledger = previous[ledger_path]
    current_ledger = current[ledger_path]
    previous_count = previous_ledger["metadata"].get("event_count")
    current_count = current_ledger["metadata"].get("event_count")
    ledger_changed = (
        current_ledger["sha256"] != previous_ledger["sha256"]
    )
    grew = (
        ledger_changed
        and type(previous_count) is int
        and type(current_count) is int
        and current_count > previous_count
    )
    if ledger_changed and not grew:
        raise SyncError("agent fair event ledger is not exact prefix growth")
    replacement_changes = [
        path
        for path in (district_path, state_path)
        if previous[path]["sha256"] != current[path]["sha256"]
    ]
    if grew and len(replacement_changes) != 2:
        raise SyncError(
            "agent fair ledger growth requires coherent state and district "
            "replacement"
        )
    if not grew and replacement_changes:
        raise SyncError(
            "agent fair state or district replacement requires exact ledger "
            "prefix growth"
        )


def _fetch_descriptor_objects(
    connection: sqlite3.Connection,
    descriptors: Sequence[Dict[str, Any]],
    index_url: str,
    state_dir: Path,
) -> Tuple[
    Dict[str, Tuple[str, int, str, bool]],
    List[Path],
    Optional[Tuple[int, str, str]],
    Optional[Tuple[int, str, str]],
]:
    records = {}
    created_paths = []
    verified_park_checkpoint = None
    verified_fair_checkpoint = None
    raw_count = _get_meta(connection, "agent_park_verified_event_count")
    raw_head = _get_meta(connection, "agent_park_verified_event_head")
    raw_digest = _get_meta(
        connection,
        "agent_park_verified_event_ledger_sha256",
    )
    park_checkpoint = None
    if raw_count is not None or raw_head is not None:
        if raw_digest is None:
            row = connection.execute(
                """
                SELECT sha256
                FROM data_objects
                WHERE deleted = 0 AND path = ?
                """,
                ("apps/agent-park/events.jsonl",),
            ).fetchone()
            raw_digest = row["sha256"] if row is not None else None
        if (
            raw_count is None
            or raw_head is None
            or raw_digest is None
            or not HASH_RE.fullmatch(raw_head)
            or not HASH_RE.fullmatch(raw_digest)
        ):
            raise SyncError("stored agent park checkpoint is inconsistent")
        try:
            park_checkpoint = (int(raw_count), raw_head, raw_digest)
        except ValueError as error:
            raise SyncError(
                "stored agent park checkpoint is inconsistent"
            ) from error
    fair_raw_count = _get_meta(
        connection,
        "agent_fair_verified_event_count",
    )
    fair_raw_head = _get_meta(
        connection,
        "agent_fair_verified_event_head",
    )
    fair_raw_digest = _get_meta(
        connection,
        "agent_fair_verified_event_ledger_sha256",
    )
    fair_checkpoint = None
    if fair_raw_count is not None or fair_raw_head is not None:
        if fair_raw_digest is None:
            row = connection.execute(
                """
                SELECT sha256
                FROM data_objects
                WHERE deleted = 0 AND path = ?
                """,
                ("apps/agent-fair/events.jsonl",),
            ).fetchone()
            fair_raw_digest = row["sha256"] if row is not None else None
        if (
            fair_raw_count is None
            or fair_raw_head is None
            or fair_raw_digest is None
            or not HASH_RE.fullmatch(fair_raw_head)
            or not HASH_RE.fullmatch(fair_raw_digest)
        ):
            raise SyncError("stored agent fair checkpoint is inconsistent")
        try:
            fair_checkpoint = (
                int(fair_raw_count),
                fair_raw_head,
                fair_raw_digest,
            )
        except ValueError as error:
            raise SyncError(
                "stored agent fair checkpoint is inconsistent"
            ) from error
    try:
        for descriptor in descriptors:
            digest = descriptor["sha256"]
            if digest in records:
                data = _object_path(state_dir, digest).read_bytes()
                if len(data) != descriptor["size"]:
                    raise SyncError(
                        "cached object size mismatch for {}".format(
                            descriptor["path"]
                        )
                    )
                _validate_descriptor_object(
                    data,
                    descriptor,
                    park_checkpoint=park_checkpoint,
                    fair_checkpoint=fair_checkpoint,
                )
                metadata = descriptor.get("metadata", {})
                if (
                    descriptor.get("kind")
                    == "agent-amusement-park-object"
                    and metadata.get("resource_type") == "event-ledger"
                ):
                    verified_park_checkpoint = (
                        metadata["event_count"],
                        metadata["event_head"],
                        descriptor["sha256"],
                    )
                if (
                    descriptor.get("kind")
                    == "agent-worlds-fair-object"
                    and metadata.get("resource_type") == "event-ledger"
                ):
                    verified_fair_checkpoint = (
                        metadata["event_count"],
                        metadata["event_head"],
                        descriptor["sha256"],
                    )
                continue
            path = _object_path(state_dir, digest)
            data = path.read_bytes() if path.exists() else None
            if data is not None and sha256_bytes(data) == digest:
                if len(data) != descriptor["size"]:
                    raise SyncError(
                        "cached object size mismatch for {}".format(
                            descriptor["path"]
                        )
                    )
                _validate_descriptor_object(
                    data,
                    descriptor,
                    park_checkpoint=park_checkpoint,
                    fair_checkpoint=fair_checkpoint,
                )
                records[digest] = (
                    digest,
                    descriptor["size"],
                    path.relative_to(state_dir).as_posix(),
                    False,
                )
            else:
                record = _fetch_app_object(
                    descriptor,
                    index_url,
                    state_dir,
                    park_checkpoint=park_checkpoint,
                    fair_checkpoint=fair_checkpoint,
                )
                records[digest] = record
                if record[3]:
                    created_paths.append(state_dir / record[2])
            metadata = descriptor.get("metadata", {})
            if (
                descriptor.get("kind")
                == "agent-amusement-park-object"
                and metadata.get("resource_type") == "event-ledger"
            ):
                verified_park_checkpoint = (
                    metadata["event_count"],
                    metadata["event_head"],
                    descriptor["sha256"],
                )
            if (
                descriptor.get("kind")
                == "agent-worlds-fair-object"
                and metadata.get("resource_type") == "event-ledger"
            ):
                verified_fair_checkpoint = (
                    metadata["event_count"],
                    metadata["event_head"],
                    descriptor["sha256"],
                )
    except Exception:
        for created_path in created_paths:
            try:
                created_path.unlink()
            except OSError:
                pass
        raise
    return (
        records,
        created_paths,
        verified_park_checkpoint,
        verified_fair_checkpoint,
    )


def _descriptor_object_counts(
    records: Dict[str, Tuple[str, int, str, bool]],
    descriptors: Sequence[Dict[str, Any]],
) -> Dict[str, int]:
    fetched_digests = {
        digest
        for digest, _size, _path, created in records.values()
        if created
    }
    app_digests = {
        descriptor["sha256"]
        for descriptor in descriptors
        if "kind" not in descriptor
    }
    data_digests = {
        descriptor["sha256"]
        for descriptor in descriptors
        if "kind" in descriptor
    }
    return {
        "cached_objects": len(records) - len(fetched_digests),
        "fetched_apps": len(fetched_digests & app_digests),
        "fetched_data_objects": len(fetched_digests & data_digests),
        "fetched_objects": len(fetched_digests),
        "verified_objects": len(records),
    }


def _validate_local_checkpoint(
    connection: sqlite3.Connection,
    entries: List[Dict[str, Any]],
) -> Tuple[int, Optional[str]]:
    raw_sequence = _get_meta(connection, "head_sequence")
    local_sequence = int(raw_sequence) if raw_sequence is not None else -1
    local_hash = _get_meta(connection, "head_sha256")
    if local_sequence >= len(entries):
        if local_sequence == -1 and not entries:
            return local_sequence, local_hash
        raise SyncError("remote history rolled back behind local checkpoint")
    if local_sequence >= 0:
        if entries[local_sequence]["sha256"] != local_hash:
            raise SyncError("remote history forked from local checkpoint")
        row = connection.execute(
            "SELECT sha256 FROM deltas WHERE sequence = ?",
            (local_sequence,),
        ).fetchone()
        if not row or row["sha256"] != local_hash:
            raise SyncError("local checkpoint database is inconsistent")
    elif connection.execute("SELECT COUNT(*) AS count FROM deltas").fetchone()[
        "count"
    ]:
        raise SyncError("local delta table has no checkpoint")
    return local_sequence, local_hash


def _validate_witness_ancestry(
    connection: sqlite3.Connection,
    entries: Sequence[Dict[str, Any]],
) -> None:
    for witness in connection.execute(
        """
        SELECT receipt_sha256, head_sequence, head_sha256
        FROM witnesses ORDER BY created_at, receipt_sha256
        """
    ):
        sequence = witness["head_sequence"]
        if (
            sequence < 0
            or sequence >= len(entries)
            or entries[sequence]["sha256"] != witness["head_sha256"]
        ):
            raise SyncError(
                "fork/drift evidence: witnessed head {} is not a remote "
                "ancestor/prefix".format(witness["receipt_sha256"])
            )


@contextmanager
def _sync_lock(state_dir: Path):
    state_dir.mkdir(parents=True, exist_ok=True)
    lock_path = state_dir / ".sync.lock"
    with lock_path.open("a+b") as handle:
        if fcntl is not None:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        else:  # pragma: no cover - exercised on Windows
            handle.seek(0)
            if not handle.read(1):
                handle.write(b"\0")
                handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
        try:
            yield
        finally:
            if fcntl is not None:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            else:  # pragma: no cover - exercised on Windows
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)


def sync_repository(
    state_dir: Path,
    index_url: str = DEFAULT_INDEX_URL,
    fetch_apps: bool = False,
    allow_synthetic_proofs: bool = False,
) -> Dict[str, Any]:
    state_dir = state_dir.resolve()
    with _sync_lock(state_dir):
        return _sync_repository_locked(
            state_dir,
            index_url=index_url,
            fetch_apps=fetch_apps,
            allow_synthetic_proofs=allow_synthetic_proofs,
        )


def _sync_repository_locked(
    state_dir: Path,
    index_url: str,
    fetch_apps: bool,
    allow_synthetic_proofs: bool,
) -> Dict[str, Any]:
    connection = connect_state(state_dir)
    created_objects = []
    try:
        conditional = {}
        etag = _get_meta(connection, "etag")
        last_modified = _get_meta(connection, "last_modified")
        prior_source = _get_meta(connection, "source_url")
        if prior_source == index_url:
            if etag:
                conditional["If-None-Match"] = etag
            if last_modified:
                conditional["If-Modified-Since"] = last_modified
        status, headers, index_bytes = fetch_url(
            index_url,
            headers=conditional,
            max_bytes=MAX_INDEX_BYTES,
        )
        if status == 304:
            object_records = {}
            descriptors = []
            verified_park_checkpoint = None
            verified_fair_checkpoint = None
            effective_data = _effective_data_descriptors(connection, [])
            validate_agent_fair_descriptor_coherence(effective_data)
            validate_agent_park_descriptor_coherence(effective_data)
            required_descriptors = [
                descriptor
                for descriptor in effective_data
                if (
                    descriptor.get("kind") == "agent-worlds-fair-object"
                    or (
                        descriptor.get("kind")
                        == "agent-amusement-park-object"
                        and _get_meta(
                            connection,
                            "agent_park_verified_event_head",
                        ) is None
                    )
                )
            ]
            if fetch_apps or required_descriptors:
                descriptors = (
                    (
                        _effective_descriptors(connection, [])
                        + effective_data
                    )
                    if fetch_apps
                    else required_descriptors
                )
                (
                    object_records,
                    created_objects,
                    verified_park_checkpoint,
                    verified_fair_checkpoint,
                ) = _fetch_descriptor_objects(
                    connection,
                    descriptors,
                    index_url,
                    state_dir,
                )
                now = datetime.now(timezone.utc).strftime(
                    "%Y-%m-%dT%H:%M:%S.000Z"
                )
                try:
                    with connection:
                        for (
                            digest,
                            size,
                            relative_path,
                            _created,
                        ) in object_records.values():
                            connection.execute(
                                """
                                INSERT OR REPLACE INTO objects(
                                  sha256, size, relative_path, verified_at
                                ) VALUES (?, ?, ?, ?)
                                """,
                                (digest, size, relative_path, now),
                            )
                        if verified_park_checkpoint is not None:
                            _set_meta(
                                connection,
                                "agent_park_verified_event_count",
                                str(verified_park_checkpoint[0]),
                            )
                            _set_meta(
                                connection,
                                "agent_park_verified_event_head",
                                verified_park_checkpoint[1],
                            )
                            _set_meta(
                                connection,
                                "agent_park_verified_event_ledger_sha256",
                                verified_park_checkpoint[2],
                            )
                        if verified_fair_checkpoint is not None:
                            _set_meta(
                                connection,
                                "agent_fair_verified_event_count",
                                str(verified_fair_checkpoint[0]),
                            )
                            _set_meta(
                                connection,
                                "agent_fair_verified_event_head",
                                verified_fair_checkpoint[1],
                            )
                            _set_meta(
                                connection,
                                "agent_fair_verified_event_ledger_sha256",
                                verified_fair_checkpoint[2],
                            )
                except Exception:
                    for path in created_objects:
                        try:
                            path.unlink()
                        except OSError:
                            pass
                    raise
            return {
                "applied_deltas": 0,
                **_descriptor_object_counts(
                    object_records,
                    descriptors,
                ),
                "head": _get_meta(connection, "head_sha256"),
                "not_modified": True,
                "profile": _get_meta(connection, "profile"),
            }
        if status != 200:
            raise SyncError("unexpected index response status {}".format(status))
        index = load_json_bytes(index_bytes, "syndication index")
        entries = validate_index(
            index,
            allow_synthetic_proofs=allow_synthetic_proofs,
        )
        stored_stream = _get_meta(connection, "stream_id")
        if (
            stored_stream
            and stored_stream != index["stream_id"]
            and _get_meta(connection, "head_sequence") is not None
        ):
            raise SyncError(
                "remote stream changed; refusing silent cursor reset"
            )
        _validate_witness_ancestry(connection, entries)
        local_sequence, _local_hash = _validate_local_checkpoint(
            connection,
            entries,
        )
        missing_entries = entries[local_sequence + 1:]

        deltas = []
        for entry in missing_entries:
            delta_url = urljoin(index_url, entry["path"])
            delta_status, _delta_headers, delta_bytes = fetch_url(
                delta_url,
                max_bytes=MAX_DELTA_BYTES,
            )
            if delta_status != 200:
                raise SyncError(
                    "unexpected delta response status {}".format(delta_status)
                )
            deltas.append(
                (
                    entry,
                    delta_url,
                    validate_delta(
                        delta_bytes,
                        entry,
                        index["stream_id"],
                        allow_synthetic_proofs=allow_synthetic_proofs,
                    ),
                )
            )

        previous_frame, seen_event_ids = _load_frame_checkpoint(connection)
        for _entry, _delta_url, delta in deltas:
            previous_frame = validate_frames(
                delta["changes"]["frame_appends"],
                previous_frame,
                seen_event_ids,
            )

        object_records = {}
        verified_park_checkpoint = None
        verified_fair_checkpoint = None
        effective_data = _effective_data_descriptors(connection, deltas)
        validate_agent_fair_descriptor_coherence(effective_data)
        validate_agent_park_descriptor_coherence(effective_data)
        _validate_agent_fair_transition(connection, effective_data)
        _validate_agent_park_transition(connection, effective_data)
        park_descriptors = [
            descriptor
            for descriptor in effective_data
            if descriptor.get("kind") == "agent-amusement-park-object"
        ]
        park_changed = any(
            descriptor.get("kind") == "agent-amusement-park-object"
            for _entry, _delta_url, delta in deltas
            for descriptor in (
                delta["changes"].get("data_upserts", [])
                + [
                    tombstone["descriptor"]
                    for tombstone in delta["changes"].get(
                        "data_tombstones",
                        [],
                    )
                ]
            )
        )
        fair_descriptors = [
            descriptor
            for descriptor in effective_data
            if descriptor.get("kind") == "agent-worlds-fair-object"
        ]
        required_descriptors = fair_descriptors + (
            park_descriptors
            if (
                park_descriptors
                and (
                    park_changed
                    or _get_meta(
                        connection,
                        "agent_park_verified_event_head",
                    ) is None
                )
            )
            else []
        )
        descriptors = []
        if fetch_apps or required_descriptors:
            descriptors = (
                (
                    _effective_descriptors(connection, deltas)
                    + effective_data
                )
                if fetch_apps
                else required_descriptors
            )
            (
                object_records,
                created_objects,
                verified_park_checkpoint,
                verified_fair_checkpoint,
            ) = _fetch_descriptor_objects(
                connection,
                descriptors,
                index_url,
                state_dir,
            )

        now = datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%S.000Z"
        )
        try:
            with connection:
                for entry, delta_url, delta in deltas:
                    sequence = delta["sequence"]
                    for descriptor in delta["changes"]["app_upserts"]:
                        connection.execute(
                            """
                            INSERT OR REPLACE INTO apps(
                              path, url, sha256, size, metadata_json,
                              deleted, delta_sequence
                            ) VALUES (?, ?, ?, ?, ?, 0, ?)
                            """,
                            (
                                descriptor["path"],
                                descriptor["url"],
                                descriptor["sha256"],
                                descriptor["size"],
                                json.dumps(
                                    descriptor["metadata"],
                                    ensure_ascii=False,
                                    separators=(",", ":"),
                                    sort_keys=True,
                                ),
                                sequence,
                            ),
                        )
                    for tombstone in delta["changes"]["app_tombstones"]:
                        descriptor = tombstone["descriptor"]
                        connection.execute(
                            """
                            INSERT OR REPLACE INTO apps(
                              path, url, sha256, size, metadata_json,
                              deleted, delta_sequence
                            ) VALUES (?, ?, ?, ?, ?, 1, ?)
                            """,
                            (
                                descriptor["path"],
                                descriptor["url"],
                                descriptor["sha256"],
                                descriptor["size"],
                                json.dumps(
                                    descriptor["metadata"],
                                    ensure_ascii=False,
                                    separators=(",", ":"),
                                    sort_keys=True,
                                ),
                                sequence,
                            ),
                        )
                        connection.execute(
                            """
                            INSERT INTO tombstones(
                              path, delta_sequence, tombstone_json
                            ) VALUES (?, ?, ?)
                            """,
                            (
                                tombstone["path"],
                                sequence,
                                json.dumps(
                                    tombstone,
                                    ensure_ascii=False,
                                    separators=(",", ":"),
                                    sort_keys=True,
                                ),
                            ),
                        )
                    for descriptor in delta["changes"].get(
                        "data_upserts",
                        [],
                    ):
                        connection.execute(
                            """
                            INSERT OR REPLACE INTO data_objects(
                              path, kind, url, sha256, size, media_type,
                              metadata_json, deleted, delta_sequence
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?)
                            """,
                            (
                                descriptor["path"],
                                descriptor["kind"],
                                descriptor["url"],
                                descriptor["sha256"],
                                descriptor["size"],
                                descriptor["media_type"],
                                json.dumps(
                                    descriptor["metadata"],
                                    ensure_ascii=False,
                                    separators=(",", ":"),
                                    sort_keys=True,
                                ),
                                sequence,
                            ),
                        )
                        if descriptor["kind"].startswith("fold-"):
                            metadata = descriptor["metadata"]
                            connection.execute(
                                """
                                INSERT OR IGNORE INTO shard_provenance(
                                  content_id, path, kind, shard_id,
                                  assignment_id, lease_id,
                                  provenance_json, delta_sequence
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                                """,
                                (
                                    descriptor["content_id"],
                                    descriptor["path"],
                                    descriptor["kind"],
                                    metadata["shard_id"],
                                    metadata.get("assignment_id"),
                                    metadata.get("lease_id"),
                                    json.dumps(
                                        metadata.get("provenance", {}),
                                        ensure_ascii=False,
                                        separators=(",", ":"),
                                        sort_keys=True,
                                    ),
                                    sequence,
                                ),
                            )
                    for tombstone in delta["changes"].get(
                        "data_tombstones",
                        [],
                    ):
                        descriptor = tombstone["descriptor"]
                        connection.execute(
                            """
                            INSERT OR REPLACE INTO data_objects(
                              path, kind, url, sha256, size, media_type,
                              metadata_json, deleted, delta_sequence
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)
                            """,
                            (
                                descriptor["path"],
                                descriptor["kind"],
                                descriptor["url"],
                                descriptor["sha256"],
                                descriptor["size"],
                                descriptor["media_type"],
                                json.dumps(
                                    descriptor["metadata"],
                                    ensure_ascii=False,
                                    separators=(",", ":"),
                                    sort_keys=True,
                                ),
                                sequence,
                            ),
                        )
                        connection.execute(
                            """
                            INSERT INTO data_tombstones(
                              path, delta_sequence, tombstone_json
                            ) VALUES (?, ?, ?)
                            """,
                            (
                                tombstone["path"],
                                sequence,
                                json.dumps(
                                    tombstone,
                                    ensure_ascii=False,
                                    separators=(",", ":"),
                                    sort_keys=True,
                                ),
                            ),
                        )
                    for frame in delta["changes"]["frame_appends"]:
                        connection.execute(
                            """
                            INSERT INTO frames(
                              seq, frame_hash, event_id, frame_json,
                              delta_sequence
                            ) VALUES (?, ?, ?, ?, ?)
                            """,
                            (
                                frame["seq"],
                                frame["frame_hash"],
                                frame["payload"]["event_id"],
                                canonical_frame_bytes(frame).decode("utf-8"),
                                sequence,
                            ),
                        )
                    connection.execute(
                        """
                        INSERT INTO deltas(
                          sequence, sha256, previous_sha256,
                          source_url, applied_at
                        ) VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            sequence,
                            entry["sha256"],
                            entry["previous_delta"],
                            delta_url,
                            now,
                        ),
                    )
                    connection.execute(
                        """
                        INSERT OR REPLACE INTO acknowledgements(
                          delta_sha256, sequence, acknowledged_at, note
                        ) VALUES (?, ?, ?, ?)
                        """,
                        (
                            entry["sha256"],
                            sequence,
                            now,
                            "verified-and-applied",
                        ),
                    )
                    connection.execute(
                        """
                        INSERT INTO blocks(
                          sequence, head_sha256, previous_sha256,
                          frame_control_mode,
                          next_frame_challenge_seed,
                          proof_of_fold_json, applied_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            sequence,
                            entry["sha256"],
                            entry["previous_delta"],
                            entry["block"]["frame_control"]["mode"],
                            entry["block"]["next_frame_challenge_seed"],
                            json.dumps(
                                entry["block"]["proof_of_fold"],
                                ensure_ascii=False,
                                separators=(",", ":"),
                                sort_keys=True,
                            ),
                            now,
                        ),
                    )
                for digest, size, relative_path, _created in object_records.values():
                    connection.execute(
                        """
                        INSERT OR REPLACE INTO objects(
                          sha256, size, relative_path, verified_at
                        ) VALUES (?, ?, ?, ?)
                        """,
                        (digest, size, relative_path, now),
                    )
                if entries:
                    _set_meta(
                        connection,
                        "head_sequence",
                        str(entries[-1]["sequence"]),
                    )
                    _set_meta(
                        connection,
                        "head_sha256",
                        entries[-1]["sha256"],
                    )
                    _set_meta(
                        connection,
                        "next_frame_challenge_seed",
                        entries[-1]["block"][
                            "next_frame_challenge_seed"
                        ],
                    )
                _set_meta(connection, "source_url", index_url)
                _set_meta(connection, "stream_id", index["stream_id"])
                _set_meta(connection, "profile", PROFILE)
                _set_meta(
                    connection,
                    "transparency",
                    json.dumps(
                        TRANSPARENCY_MODEL,
                        separators=(",", ":"),
                        sort_keys=True,
                    ),
                )
                _set_meta(
                    connection,
                    "rollout",
                    json.dumps(
                        SOAK_ROLLOUT,
                        separators=(",", ":"),
                        sort_keys=True,
                    ),
                )
                _set_meta(
                    connection,
                    "challenge_state_machine",
                    json.dumps(
                        CHALLENGE_STATE_MACHINE,
                        separators=(",", ":"),
                        sort_keys=True,
                    ),
                )
                _set_meta(
                    connection,
                    "frame_control_schema",
                    json.dumps(
                        FRAME_CONTROL_SCHEMA,
                        separators=(",", ":"),
                        sort_keys=True,
                    ),
                )
                if entries:
                    _set_meta(
                        connection,
                        "frame_control_mode",
                        entries[-1]["block"]["frame_control"]["mode"],
                    )
                if verified_park_checkpoint is not None:
                    _set_meta(
                        connection,
                        "agent_park_verified_event_count",
                        str(verified_park_checkpoint[0]),
                    )
                    _set_meta(
                        connection,
                        "agent_park_verified_event_head",
                        verified_park_checkpoint[1],
                    )
                    _set_meta(
                        connection,
                        "agent_park_verified_event_ledger_sha256",
                        verified_park_checkpoint[2],
                    )
                if verified_fair_checkpoint is not None:
                    _set_meta(
                        connection,
                        "agent_fair_verified_event_count",
                        str(verified_fair_checkpoint[0]),
                    )
                    _set_meta(
                        connection,
                        "agent_fair_verified_event_head",
                        verified_fair_checkpoint[1],
                    )
                    _set_meta(
                        connection,
                        "agent_fair_verified_event_ledger_sha256",
                        verified_fair_checkpoint[2],
                    )
                _set_meta(
                    connection,
                    "rate_budget",
                    json.dumps(
                        index["rate_budget"],
                        separators=(",", ":"),
                        sort_keys=True,
                    ),
                )
                if headers.get("etag"):
                    _set_meta(connection, "etag", headers["etag"])
                if headers.get("last-modified"):
                    _set_meta(
                        connection,
                        "last_modified",
                        headers["last-modified"],
                    )
                _set_meta(connection, "last_sync", now)
        except Exception:
            for path in created_objects:
                try:
                    path.unlink()
                except OSError:
                    pass
            raise

        return {
            "applied_deltas": len(deltas),
            **_descriptor_object_counts(
                object_records,
                descriptors,
            ),
            "head": entries[-1]["sha256"] if entries else None,
            "not_modified": False,
            "profile": index["profile"],
        }
    finally:
        connection.close()


def _agent_fair_release_status(
    connection: sqlite3.Connection,
    state_dir: Path,
) -> Dict[str, Any]:
    errors = []
    source_url = _get_meta(connection, "source_url")
    official_source = source_url == DEFAULT_INDEX_URL
    resource_types = {}
    prepared_bundle_status = None
    for row in connection.execute(
        """
        SELECT path, sha256, size, metadata_json, delta_sequence
        FROM data_objects
        WHERE deleted = 0 AND kind = 'agent-worlds-fair-object'
        ORDER BY path
        """
    ):
        try:
            metadata = json.loads(row["metadata_json"])
        except json.JSONDecodeError:
            errors.append(
                "invalid descriptor metadata for {}".format(row["path"])
            )
            continue
        if type(metadata) is not dict:
            errors.append(
                "invalid descriptor metadata for {}".format(row["path"])
            )
            continue
        resource_type = metadata.get("resource_type")
        if resource_type in resource_types:
            errors.append(
                "duplicate fair resource type {}".format(resource_type)
            )
            continue
        resource_types[resource_type] = row
        object_row = connection.execute(
            """
            SELECT size, relative_path
            FROM objects
            WHERE sha256 = ?
            """,
            (row["sha256"],),
        ).fetchone()
        if (
            type(row["sha256"]) is not str
            or not HASH_RE.fullmatch(row["sha256"])
            or type(row["size"]) is not int
            or not 0 <= row["size"] <= MAX_PUBLIC_DATA_BYTES
        ):
            errors.append(
                "invalid cached fair resource {}".format(resource_type)
            )
            continue
        object_path = _object_path(state_dir, row["sha256"])
        try:
            valid_path = (
                object_row is not None
                and object_row["size"] == row["size"]
                and object_row["relative_path"]
                == object_path.relative_to(state_dir).as_posix()
                and object_path.is_file()
            )
        except OSError:
            valid_path = False
        if not valid_path:
            errors.append(
                "missing cached fair resource {}".format(resource_type)
            )
            continue
        try:
            cached_size = object_path.stat().st_size
        except OSError:
            errors.append(
                "missing cached fair resource {}".format(resource_type)
            )
            continue
        if cached_size != row["size"]:
            errors.append(
                "corrupt cached fair resource {}".format(resource_type)
            )
            continue
        try:
            data = object_path.read_bytes()
        except OSError:
            errors.append(
                "missing cached fair resource {}".format(resource_type)
            )
            continue
        if (
            len(data) != row["size"]
            or sha256_bytes(data) != row["sha256"]
        ):
            errors.append(
                "corrupt cached fair resource {}".format(resource_type)
            )
            continue
        if resource_type == "state":
            try:
                fair_state = load_json_bytes(data, "cached agent fair state")
            except SyncError as error:
                errors.append(str(error))
            else:
                prepared_bundle_status = fair_state.get("status")

    release_row = connection.execute(
        """
        SELECT seq, frame_hash, frame_json, delta_sequence
        FROM frames
        WHERE event_id = ?
        """,
        (AGENT_FAIR_RELEASE_EVENT_ID,),
    ).fetchone()
    release_frame = None
    if release_row is not None:
        try:
            release_frame = json.loads(release_row["frame_json"])
            if type(release_frame) is not dict:
                raise SyncError("cached fair release frame is not an object")
            _validate_agent_fair_release_frame(release_frame)
            wave = {
                key: value
                for key, value in release_frame.items()
                if key not in {"frame_hash", "sig"}
            }
            if (
                release_frame.get("seq") != release_row["seq"]
                or release_frame.get("frame_hash")
                != release_row["frame_hash"]
                or release_frame.get("payload_hash")
                != frame_hash_value(
                    PARTICLE_SPACE,
                    release_frame.get("payload"),
                )
                or release_frame.get("frame_hash")
                != frame_hash_value(WAVE_SPACE, wave)
            ):
                raise SyncError("cached fair release frame hash mismatch")
            if official_source and (
                release_frame["seq"] != AGENT_FAIR_RELEASE_FRAME_SEQUENCE
                or release_frame["frame_hash"]
                != AGENT_FAIR_RELEASE_FRAME_SHA256
            ):
                raise SyncError(
                    "official fair release frame does not match its pin"
                )
        except (json.JSONDecodeError, SyncError) as error:
            errors.append(str(error))
            release_frame = None

    candidate_in_replica = connection.execute(
        """
        SELECT SUM(count) AS count
        FROM (
          SELECT COUNT(*) AS count
          FROM data_objects
          WHERE deleted = 0
            AND path = 'apps/agent-fair/release-candidate.json'
          UNION ALL
          SELECT COUNT(*) AS count
          FROM apps
          WHERE deleted = 0
            AND path = 'apps/agent-fair/release-candidate.json'
        )
        """
    ).fetchone()["count"] != 0
    if candidate_in_replica:
        errors.append("release candidate must not be in the profile-10 replica")

    expected_resources = {
        "agent-contract",
        "district",
        "event-ledger",
        "state",
    }
    replicated = (
        release_row is not None
        or bool(resource_types)
        or candidate_in_replica
    )
    release_delta = None
    if replicated:
        if release_row is None:
            errors.append("local fair release frame is missing")
        if set(resource_types) != expected_resources:
            errors.append(
                "local fair replica does not contain four exact resources"
            )
        if _get_meta(connection, "profile") != PROFILE:
            errors.append("local replica is not profile 10")
        if release_row is not None:
            delta_row = connection.execute(
                """
                SELECT sequence, sha256
                FROM deltas
                WHERE sequence = ?
                """,
                (release_row["delta_sequence"],),
            ).fetchone()
            if delta_row is None:
                errors.append("local fair release delta is missing")
            else:
                release_delta = {
                    "sequence": delta_row["sequence"],
                    "sha256": delta_row["sha256"],
                }
                if official_source and (
                    delta_row["sequence"]
                    != AGENT_FAIR_RELEASE_DELTA_SEQUENCE
                    or delta_row["sha256"]
                    != AGENT_FAIR_RELEASE_DELTA_SHA256
                ):
                    errors.append(
                        "official fair release delta does not match its pin"
                    )
            if any(
                row["delta_sequence"] != release_row["delta_sequence"]
                for row in resource_types.values()
            ):
                errors.append(
                    "fair release frame and resources are not atomic locally"
                )
        if (
            _get_meta(connection, "agent_fair_verified_event_count")
            != str(AGENT_FAIR_BASE_EVENT_COUNT)
            or _get_meta(connection, "agent_fair_verified_event_head")
            != AGENT_FAIR_BASE_EVENT_HEAD
            or _get_meta(
                connection,
                "agent_fair_verified_event_ledger_sha256",
            )
            != AGENT_FAIR_BASE_PREFIX_SHA256
        ):
            errors.append(
                "local fair event checkpoint is not release-pinned"
            )
    structural_verified = (
        replicated and not errors and release_frame is not None
    )
    offline_verified = structural_verified and official_source
    result = {
        "candidate_digest": AGENT_FAIR_RELEASE_CANDIDATE_DIGEST,
        "official_source": official_source,
        "offline_verified": offline_verified,
        "prepared_bundle_status": prepared_bundle_status,
        "profile": _get_meta(connection, "profile"),
        "release_candidate_in_replica": candidate_in_replica,
        "replicated_resource_types": sorted(
            key for key in resource_types if type(key) is str
        ),
        "status": (
            "released"
            if offline_verified
            else (
                "structural-only"
                if structural_verified
                else (
                    "invalid-local-replica"
                    if replicated
                    else "not-replicated"
                )
            )
        ),
        "structural_verified": structural_verified,
    }
    if release_frame is not None:
        result["release_frame"] = {
            "delta_sequence": release_row["delta_sequence"],
            "frame_hash": release_frame["frame_hash"],
            "seq": release_frame["seq"],
            "utc": release_frame["utc"],
        }
    if release_delta is not None:
        result["release_delta"] = release_delta
    if errors:
        result["errors"] = errors
    return result


def status(state_dir: Path) -> Dict[str, Any]:
    state_dir = state_dir.resolve()
    connection = connect_state(state_dir)
    try:
        counts = {}
        for label, query in (
            ("active_apps", "SELECT COUNT(*) AS count FROM apps WHERE deleted = 0"),
            ("removed_apps", "SELECT COUNT(*) AS count FROM apps WHERE deleted = 1"),
            (
                "attention_data_objects",
                "SELECT COUNT(*) AS count FROM data_objects WHERE deleted = 0",
            ),
            (
                "removed_data_objects",
                "SELECT COUNT(*) AS count FROM data_objects WHERE deleted = 1",
            ),
            ("local_apps", "SELECT COUNT(*) AS count FROM local_apps"),
            ("frames", "SELECT COUNT(*) AS count FROM frames"),
            ("deltas", "SELECT COUNT(*) AS count FROM deltas"),
            ("objects", "SELECT COUNT(*) AS count FROM objects"),
            ("blocks", "SELECT COUNT(*) AS count FROM blocks"),
            (
                "acknowledgements",
                "SELECT COUNT(*) AS count FROM acknowledgements",
            ),
            (
                "shard_provenance",
                "SELECT COUNT(*) AS count FROM shard_provenance",
            ),
            (
                "witnesses",
                "SELECT COUNT(*) AS count FROM witnesses",
            ),
        ):
            counts[label] = connection.execute(query).fetchone()["count"]
        return {
            **counts,
            "head_sequence": _get_meta(connection, "head_sequence"),
            "head_sha256": _get_meta(connection, "head_sha256"),
            "last_sync": _get_meta(connection, "last_sync"),
            "profile": _get_meta(connection, "profile"),
            "source_url": _get_meta(connection, "source_url"),
            "agent_worlds_fair_release": _agent_fair_release_status(
                connection,
                state_dir,
            ),
            "next_frame_challenge_seed": _get_meta(
                connection,
                "next_frame_challenge_seed",
            ),
            "rate_budget": json.loads(
                _get_meta(connection, "rate_budget") or "{}"
            ),
            "transparency": json.loads(
                _get_meta(connection, "transparency") or "{}"
            ),
            "rollout": json.loads(
                _get_meta(connection, "rollout") or "{}"
            ),
            "challenge_state_machine": json.loads(
                _get_meta(connection, "challenge_state_machine") or "{}"
            ),
            "frame_control_schema": json.loads(
                _get_meta(connection, "frame_control_schema") or "{}"
            ),
            "frame_control_mode": _get_meta(
                connection,
                "frame_control_mode",
            ),
        }
    finally:
        connection.close()


def list_apps(
    state_dir: Path,
    include_removed: bool = False,
) -> List[Dict[str, Any]]:
    connection = connect_state(state_dir.resolve())
    try:
        global_rows = connection.execute(
            """
            SELECT path, url, sha256, size, metadata_json, deleted
            FROM apps
            WHERE deleted = 0 OR ?
            ORDER BY path
            """,
            (1 if include_removed else 0,),
        ).fetchall()
        local_rows = connection.execute(
            """
            SELECT path, sha256, size, metadata_json
            FROM local_apps ORDER BY path
            """
        ).fetchall()
        local_paths = {row["path"] for row in local_rows}
        result = [
            {
                "deleted": bool(row["deleted"]),
                "metadata": json.loads(row["metadata_json"]),
                "origin": "global",
                "path": row["path"],
                "sha256": row["sha256"],
                "size": row["size"],
                "url": row["url"],
            }
            for row in global_rows
            if row["path"] not in local_paths
        ]
        result.extend({
            "deleted": False,
            "metadata": json.loads(row["metadata_json"]),
            "origin": "local-overlay",
            "path": row["path"],
            "sha256": row["sha256"],
            "size": row["size"],
            "url": None,
        } for row in local_rows)
        return sorted(result, key=lambda item: item["path"])
    finally:
        connection.close()


def list_data_objects(
    state_dir: Path,
    include_removed: bool = False,
) -> List[Dict[str, Any]]:
    connection = connect_state(state_dir.resolve())
    try:
        rows = connection.execute(
            """
            SELECT path, kind, url, sha256, size, media_type,
                   metadata_json, deleted
            FROM data_objects
            WHERE deleted = 0 OR ?
            ORDER BY path
            """,
            (1 if include_removed else 0,),
        ).fetchall()
        local_paths = {
            row["path"]
            for row in connection.execute("SELECT path FROM local_apps")
        }
        result = [{
            "deleted": bool(row["deleted"]),
            "kind": row["kind"],
            "media_type": row["media_type"],
            "metadata": json.loads(row["metadata_json"]),
            "overlayed": row["path"] in local_paths,
            "path": row["path"],
            "sha256": row["sha256"],
            "size": row["size"],
            "url": row["url"],
        } for row in rows]
        def sort_key(item):
            metadata = item["metadata"]
            branches = metadata.get("branches_present") or [""]
            branch_rank = {
                "hot": 0,
                "cold": 1,
            }.get(branches[0], 2)
            if item["kind"].startswith("fold-"):
                kind_rank = {
                    "fold-shard-assignment": 0,
                    "fold-shard-lease": 1,
                    "fold-challenge": 2,
                    "fold-proof-receipt": 3,
                    "fold-control-award-receipt": 4,
                    "fold-action-receipt": 5,
                    "fold-shard-result-object": 6,
                    "fold-shard-dimension-object": 7,
                }.get(item["kind"], 8)
                return (
                    0,
                    str(metadata.get("shard_id", "")),
                    kind_rank,
                    branch_rank,
                    item["path"],
                )
            if item["kind"] == "attention-dimension-object":
                return (
                    1,
                    str(metadata.get("base_record_id", "")),
                    branch_rank,
                    item["path"],
                )
            return (2, item["path"])

        return sorted(result, key=sort_key)
    finally:
        connection.close()


def add_local_app(
    state_dir: Path,
    source: Path,
    overlay_path: Optional[str] = None,
    title: Optional[str] = None,
) -> Dict[str, Any]:
    state_dir = state_dir.resolve()
    source = source.resolve()
    if not source.is_file():
        raise SyncError("local app file does not exist")
    path = _safe_relative_path(overlay_path or source.name)
    data = source.read_bytes()
    if len(data) > MAX_APP_BYTES:
        raise SyncError("local app exceeds the object size limit")
    digest = sha256_bytes(data)
    object_path, _created = _store_object(state_dir, digest, data)
    now = datetime.now(timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%S.000Z"
    )
    metadata = {
        "title": title or source.stem,
        "source_name": source.name,
    }
    connection = connect_state(state_dir)
    try:
        with connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO objects(
                  sha256, size, relative_path, verified_at
                ) VALUES (?, ?, ?, ?)
                """,
                (
                    digest,
                    len(data),
                    object_path.relative_to(state_dir).as_posix(),
                    now,
                ),
            )
            connection.execute(
                """
                INSERT OR REPLACE INTO local_apps(
                  path, sha256, size, metadata_json,
                  relative_path, added_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    path,
                    digest,
                    len(data),
                    json.dumps(
                        metadata,
                        ensure_ascii=False,
                        separators=(",", ":"),
                        sort_keys=True,
                    ),
                    object_path.relative_to(state_dir).as_posix(),
                    now,
                ),
            )
    finally:
        connection.close()
    return {
        "origin": "local-overlay",
        "path": path,
        "sha256": digest,
        "size": len(data),
    }


def acknowledge(
    state_dir: Path,
    sequence: Optional[int] = None,
    note: str = "locally-reviewed",
) -> Dict[str, Any]:
    state_dir = state_dir.resolve()
    connection = connect_state(state_dir)
    try:
        if sequence is None:
            raw = _get_meta(connection, "head_sequence")
            if raw is None:
                raise SyncError("no replay checkpoint to acknowledge")
            sequence = int(raw)
        row = connection.execute(
            "SELECT sha256 FROM deltas WHERE sequence = ?",
            (sequence,),
        ).fetchone()
        if not row:
            raise SyncError(
                "delta sequence {} is not locally applied".format(sequence)
            )
        clean_note = str(note).strip()[:240] or "locally-reviewed"
        now = datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%S.000Z"
        )
        with connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO acknowledgements(
                  delta_sha256, sequence, acknowledged_at, note
                ) VALUES (?, ?, ?, ?)
                """,
                (row["sha256"], sequence, now, clean_note),
            )
        return {
            "acknowledged_at": now,
            "delta_sha256": row["sha256"],
            "note": clean_note,
            "sequence": sequence,
        }
    finally:
        connection.close()


def emit_witness_receipt(
    state_dir: Path,
    output: Path,
    witness_id: Optional[str] = None,
) -> Dict[str, Any]:
    state_dir = state_dir.resolve()
    connection = connect_state(state_dir)
    try:
        rows = connection.execute(
            """
            SELECT sequence, sha256, previous_sha256
            FROM deltas ORDER BY sequence
            """
        ).fetchall()
        if not rows:
            raise SyncError("no accepted delta head to witness")
        chain = []
        previous = None
        for expected, row in enumerate(rows):
            if (
                row["sequence"] != expected
                or row["previous_sha256"] != previous
            ):
                raise SyncError("local replica chain is internally inconsistent")
            chain.append({
                "previous_delta": row["previous_sha256"],
                "sequence": row["sequence"],
                "sha256": row["sha256"],
            })
            previous = row["sha256"]
        local_witness_id = witness_id or _get_meta(
            connection,
            "witness_id",
        )
        if not local_witness_id:
            local_witness_id = "local-witness:{}".format(uuid.uuid4())
        now = datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%S.000Z"
        )
        chain_fingerprint = sha256_bytes(stable_json_bytes(chain))
        statement = {
            "authority": TRANSPARENCY_MODEL,
            "challenge_state": CHALLENGE_STATE_MACHINE,
            "frame_control": {
                "mode": _get_meta(connection, "frame_control_mode"),
                "schema": FRAME_CONTROL_SCHEMA,
            },
            "chain_fingerprint": chain_fingerprint,
            "created_at": now,
            "delta_count": len(chain),
            "head": {
                "sequence": chain[-1]["sequence"],
                "sha256": chain[-1]["sha256"],
            },
            "next_frame_challenge_seed": _get_meta(
                connection,
                "next_frame_challenge_seed",
            ),
            "schema": "rappterzoo-subscriber-witness-statement/1",
            "source_url": _get_meta(connection, "source_url"),
            "stream_id": _get_meta(connection, "stream_id"),
            "witness_id": local_witness_id,
            "rollout": SOAK_ROLLOUT,
        }
        statement_sha256 = sha256_bytes(stable_json_bytes(statement))
        receipt = {
            "receipt_type": "local-unsigned-content-witness",
            "schema": "rappterzoo-subscriber-witness-receipt/1",
            "statement": statement,
            "statement_sha256": statement_sha256,
        }
        with connection:
            _set_meta(connection, "witness_id", local_witness_id)
            connection.execute(
                """
                INSERT OR REPLACE INTO witnesses(
                  receipt_sha256, witness_id, head_sequence,
                  head_sha256, chain_fingerprint, created_at,
                  statement_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    statement_sha256,
                    local_witness_id,
                    chain[-1]["sequence"],
                    chain[-1]["sha256"],
                    chain_fingerprint,
                    now,
                    json.dumps(
                        statement,
                        ensure_ascii=False,
                        separators=(",", ":"),
                        sort_keys=True,
                    ),
                ),
            )
        data = stable_json_bytes(receipt)
        output.parent.mkdir(parents=True, exist_ok=True)
        staging = output.with_name(output.name + ".new")
        staging.write_bytes(data)
        os.replace(str(staging), str(output))
        return {
            "head_sequence": chain[-1]["sequence"],
            "head_sha256": chain[-1]["sha256"],
            "path": str(output),
            "statement_sha256": statement_sha256,
            "witness_id": local_witness_id,
        }
    finally:
        connection.close()


def export_state(state_dir: Path, output: Path) -> Dict[str, Any]:
    state_dir = state_dir.resolve()
    connection = connect_state(state_dir)
    try:
        exported = {
            "apps": [
                dict(row)
                for row in connection.execute(
                    "SELECT * FROM apps ORDER BY path"
                )
            ],
            "blocks": [
                dict(row)
                for row in connection.execute(
                    "SELECT * FROM blocks ORDER BY sequence"
                )
            ],
            "acknowledgements": [
                dict(row)
                for row in connection.execute(
                    """
                    SELECT * FROM acknowledgements
                    ORDER BY sequence
                    """
                )
            ],
            "deltas": [
                dict(row)
                for row in connection.execute(
                    "SELECT * FROM deltas ORDER BY sequence"
                )
            ],
            "data_objects": [
                dict(row)
                for row in connection.execute(
                    "SELECT * FROM data_objects ORDER BY path"
                )
            ],
            "data_tombstones": [
                json.loads(row["tombstone_json"])
                for row in connection.execute(
                    """
                    SELECT tombstone_json FROM data_tombstones
                    ORDER BY delta_sequence, path
                    """
                )
            ],
            "frames": [
                json.loads(row["frame_json"])
                for row in connection.execute(
                    "SELECT frame_json FROM frames ORDER BY seq"
                )
            ],
            "shard_provenance": [
                dict(row)
                for row in connection.execute(
                    """
                    SELECT * FROM shard_provenance
                    ORDER BY shard_id, kind, path
                    """
                )
            ],
            "local_apps": [
                dict(row)
                for row in connection.execute(
                    "SELECT * FROM local_apps ORDER BY path"
                )
            ],
            "meta": {
                row["key"]: row["value"]
                for row in connection.execute(
                    "SELECT key, value FROM meta ORDER BY key"
                )
            },
            "schema": "rappterzoo-local-sync-export/1",
            "tombstones": [
                json.loads(row["tombstone_json"])
                for row in connection.execute(
                    """
                    SELECT tombstone_json FROM tombstones
                    ORDER BY delta_sequence, path
                    """
                )
            ],
            "witnesses": [
                dict(row)
                for row in connection.execute(
                    """
                    SELECT * FROM witnesses
                    ORDER BY created_at, receipt_sha256
                    """
                )
            ],
        }
    finally:
        connection.close()
    data = stable_json_bytes(exported)
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = output.with_name(output.name + ".new")
    staging.write_bytes(data)
    os.replace(str(staging), str(output))
    return {"bytes": len(data), "path": str(output)}


def materialize(state_dir: Path, output_dir: Path) -> Dict[str, Any]:
    state_dir = state_dir.resolve()
    output_dir = output_dir.resolve()
    connection = connect_state(state_dir)
    try:
        global_rows = connection.execute(
            """
            SELECT path, sha256 FROM apps
            WHERE deleted = 0 ORDER BY path
            """
        ).fetchall()
        local_rows = connection.execute(
            """
            SELECT path, sha256 FROM local_apps ORDER BY path
            """
        ).fetchall()
        data_rows = connection.execute(
            """
            SELECT path, sha256 FROM data_objects
            WHERE deleted = 0 ORDER BY path
            """
        ).fetchall()
    finally:
        connection.close()
    effective = {
        row["path"]: row["sha256"]
        for row in global_rows
    }
    effective.update({
        row["path"]: row["sha256"]
        for row in data_rows
    })
    effective.update({
        row["path"]: row["sha256"]
        for row in local_rows
    })
    written = 0
    for relative, digest in sorted(effective.items()):
        safe = _safe_relative_path(relative)
        source = _object_path(state_dir, digest)
        if not source.is_file() or sha256_bytes(source.read_bytes()) != digest:
            raise SyncError(
                "missing verified object for {}; run sync --fetch-apps".format(
                    relative
                )
            )
        target = output_dir / safe
        target.parent.mkdir(parents=True, exist_ok=True)
        staging = target.with_name(target.name + ".new")
        shutil.copyfile(str(source), str(staging))
        os.replace(str(staging), str(target))
        written += 1
    return {"materialized": written, "path": str(output_dir)}


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="User-initiated local RappterZoo delta sync",
    )
    parser.add_argument(
        "--state-dir",
        default=str(DEFAULT_STATE_DIR),
        help="local SQLite and object-cache directory",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    sync_parser = subparsers.add_parser("sync")
    sync_parser.add_argument("source", nargs="?", default=DEFAULT_INDEX_URL)
    sync_parser.add_argument("--fetch-apps", action="store_true")

    subparsers.add_parser("status")
    apps_parser = subparsers.add_parser("apps")
    apps_parser.add_argument("--include-removed", action="store_true")
    data_parser = subparsers.add_parser("data")
    data_parser.add_argument("--include-removed", action="store_true")

    local_parser = subparsers.add_parser("add-local-app")
    local_parser.add_argument("file")
    local_parser.add_argument("--path")
    local_parser.add_argument("--title")

    ack_parser = subparsers.add_parser("ack")
    ack_parser.add_argument("sequence", nargs="?", type=int)
    ack_parser.add_argument("--note", default="locally-reviewed")

    witness_parser = subparsers.add_parser("witness")
    witness_parser.add_argument("output")
    witness_parser.add_argument("--witness-id")

    export_parser = subparsers.add_parser("export")
    export_parser.add_argument("output")

    materialize_parser = subparsers.add_parser("materialize")
    materialize_parser.add_argument("output")

    args = parser.parse_args(argv)
    state_dir = Path(args.state_dir)
    try:
        if args.command == "sync":
            result = sync_repository(
                state_dir,
                args.source,
                args.fetch_apps,
            )
        elif args.command == "status":
            result = status(state_dir)
        elif args.command == "apps":
            result = {
                "apps": list_apps(
                    state_dir,
                    args.include_removed,
                )
            }
        elif args.command == "data":
            result = {
                "data_objects": list_data_objects(
                    state_dir,
                    args.include_removed,
                )
            }
        elif args.command == "add-local-app":
            result = add_local_app(
                state_dir,
                Path(args.file),
                args.path,
                args.title,
            )
        elif args.command == "ack":
            result = acknowledge(
                state_dir,
                args.sequence,
                args.note,
            )
        elif args.command == "witness":
            result = emit_witness_receipt(
                state_dir,
                Path(args.output),
                args.witness_id,
            )
        elif args.command == "export":
            result = export_state(
                state_dir,
                Path(args.output),
            )
        elif args.command == "materialize":
            result = materialize(
                state_dir,
                Path(args.output),
            )
        else:
            raise SyncError("unknown command")
    except (OSError, sqlite3.Error, SyncError) as error:
        print(
            json.dumps(
                {"ok": False, "error": str(error)},
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 1
    print(json.dumps({"ok": True, **result}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Build RappterZoo's static, append-only syndication projections.

The immutable delta files are the history. ``index.json``, ``snapshot.json``,
and ``atom.xml`` are replaceable projections over that history.
"""

import argparse
import hashlib
import json
import os
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import quote, urljoin
from xml.sax.saxutils import escape, quoteattr


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BASE_URL = "https://kody-w.github.io/localFirstTools-main/"
STREAM_ID = "https://kody-w.github.io/localFirstTools-main/apps/syndication/"
SNAPSHOT_SCHEMA = "rappterzoo-syndication-snapshot/1"
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
FRAME_SCHEMA = "rappterzoo-organism-frame/1"
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
HASH_RE = re.compile(r"^[0-9a-f]{64}$")
KIND_RE = re.compile(
    r"^[a-z0-9]+(?:-[a-z0-9]+)*\.[a-z0-9]+(?:-[a-z0-9]+)*$"
)
UTC_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")
MAX_SAFE_INTEGER = (1 << 53) - 1
MAX_CANONICAL_BYTES = 1024 * 1024
MAX_DELTA_BYTES = 16 * 1024 * 1024
MAX_PUBLIC_DATA_BYTES = 4 * 1024 * 1024
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
RATE_BUDGET = {
    "conditional_get": "required-after-first-sync",
    "constant_polling": False,
    "legacy_documented_interval_seconds": 14400,
    "live_heartbeat_interval_seconds": 1800,
    "mode": "user-initiated",
    "recommended_min_sync_interval_seconds": 1800,
}
CAPABILITIES = {
    "atom": True,
    "federation": "static-feed",
    "offline_export": True,
    "replayable_delta_token": "since_seq",
    "tombstones": True,
    "webhooks": False,
}
PINNING_POLICY = {
    "app_content": "sha256-required",
    "delta_content": "content-addressed",
    "mutable_skill_references": "reject-unpinned",
}
PUBLIC_DATA_SUFFIXES = {
    ".json": "application/json",
    ".jsonl": "application/x-ndjson",
    ".ndjson": "application/x-ndjson",
}
PUBLIC_DATA_ROOTS = (
    "agent-park",
    "attention",
    "fold",
    "fold-at-home",
    "looking-glass",
    "shards",
)
REJECTED_PUBLIC_DATA = object()
SAFE_FALSE_PUBLIC_POLICY_KEYS = {
    "privatemediainpublicledger",
    "pulsepersisted",
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


class SyndicationError(ValueError):
    """Raised when syndication inputs or immutable history are invalid."""


def _json_object(pairs: Sequence[Tuple[str, Any]]) -> Dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise SyndicationError("duplicate JSON object key: {}".format(key))
        result[key] = value
    return result


def load_json_bytes(data: bytes, label: str) -> Any:
    try:
        return json.loads(
            data.decode("utf-8"),
            object_pairs_hook=_json_object,
            parse_constant=lambda value: (_ for _ in ()).throw(
                SyndicationError(
                    "{} contains non-finite JSON number {}".format(label, value)
                )
            ),
        )
    except SyndicationError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SyndicationError("invalid JSON in {}".format(label)) from error


def stable_json_bytes(value: Any) -> bytes:
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8") + b"\n"
    except (TypeError, ValueError) as error:
        raise SyndicationError("value is not deterministic JSON") from error
    return encoded


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _normalize_frame_json(value: Any, depth: int = 1) -> Any:
    if depth > 64:
        raise SyndicationError("frame JSON nesting exceeds 64 levels")
    if value is None or type(value) is bool:
        return value
    if type(value) is int:
        if not -MAX_SAFE_INTEGER <= value <= MAX_SAFE_INTEGER:
            raise SyndicationError("frame integer exceeds the I-JSON safe range")
        return value
    if type(value) is float:
        raise SyndicationError("frame binary64 values are forbidden")
    if type(value) is str:
        if unicodedata.normalize("NFC", value) != value:
            raise SyndicationError("frame strings must be NFC-normalized")
        if any(0xD800 <= ord(character) <= 0xDFFF for character in value):
            raise SyndicationError("frame contains a lone UTF-16 surrogate")
        return value
    if isinstance(value, (list, tuple)):
        return [
            _normalize_frame_json(item, depth + 1)
            for item in value
        ]
    if type(value) is dict:
        normalized = {}
        for key, item in value.items():
            if type(key) is not str:
                raise SyndicationError("frame object keys must be strings")
            try:
                key.encode("ascii")
            except UnicodeEncodeError as error:
                raise SyndicationError("frame object keys must be ASCII") from error
            if unicodedata.normalize("NFC", key) != key:
                raise SyndicationError("frame object keys must be NFC-normalized")
            normalized[key] = _normalize_frame_json(item, depth + 1)
        return normalized
    raise SyndicationError(
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
        raise SyndicationError("canonical frame value exceeds one MiB")
    return encoded


def frame_hash_value(space: str, value: Any) -> str:
    return hashlib.sha256(
        space.encode("ascii") + b"\n" + canonical_frame_bytes(value)
    ).hexdigest()


def validate_agent_park_event_ledger(
    events: Any,
) -> List[Dict[str, Any]]:
    if not isinstance(events, list) or not events:
        raise SyndicationError("agent park event ledger must be non-empty")
    previous = None
    for index, event in enumerate(events):
        if type(event) is not dict or set(event) != AGENT_PARK_EVENT_KEYS:
            raise SyndicationError(
                "agent park event {} has an invalid key set".format(index)
            )
        if (
            event["schema"] != AGENT_PARK_EVENT_SCHEMA
            or event["park_id"]
            != "park.rappterzoo-agent-amusement-park"
            or event["visibility"] != "public-metadata"
            or event["seq"] != index
            or type(event["payload"]) is not dict
        ):
            raise SyndicationError("invalid agent park event ledger")
        if event["prev"] != (
            previous["event_hash"] if previous else None
        ):
            raise SyndicationError("agent park event chain is broken")
        if previous is not None and event["utc"] < previous["utc"]:
            raise SyndicationError(
                "agent park event timestamps are not monotonic"
            )
        if event["payload_hash"] != frame_hash_value(
            AGENT_PARK_PAYLOAD_SPACE,
            event["payload"],
        ):
            raise SyndicationError("agent park payload hash mismatch")
        projected = {
            key: value
            for key, value in event.items()
            if key != "event_hash"
        }
        if event["event_hash"] != frame_hash_value(
            AGENT_PARK_EVENT_SPACE,
            projected,
        ):
            raise SyndicationError("agent park event hash mismatch")
        previous = event
    return events


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
        raise SyndicationError(
            "shard frame requires assigned lease and assembler acceptance"
        )


def _data_key_is_sensitive(key: str, value: Any) -> bool:
    token = _privacy_key_token(key)
    if token in SAFE_FALSE_PUBLIC_POLICY_KEYS and value is False:
        return False
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
) -> None:
    if isinstance(value, list):
        for item in value:
            validate_public_data_value(item, comment_context)
        return
    if type(value) is not dict:
        return
    for key in value:
        if _data_key_is_sensitive(key, value[key]):
            raise SyndicationError(
                "public data object contains sensitive key {}".format(key)
            )
    visibility = value.get("visibility")
    if visibility is not None and visibility not in {
        "public",
        "public-metadata",
    }:
        raise SyndicationError("public data object has non-public visibility")
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
    if local_comment_context and body_keys:
        if (
            value.get("selected") is not True
            or value.get("visibility") not in {
                "public",
                "public-metadata",
            }
        ):
            raise SyndicationError(
                "unselected or non-public comment body is forbidden"
            )
    for key, item in value.items():
        child_comment_context = (
            local_comment_context
            or "comment" in _privacy_key_token(key)
        )
        validate_public_data_value(item, child_comment_context)


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


def _has_shard_signal(value: Any, label: str) -> bool:
    if isinstance(value, list):
        return any(_has_shard_signal(item, label) for item in value)
    if type(value) is not dict:
        return False
    signals = [
        value.get("kind"),
        value.get("type"),
        value.get("schema"),
        label,
    ]
    return (
        any(
            type(signal) is str
            and (
                "shard" in signal.lower()
                or "fold-at-home" in signal.lower()
            )
            for signal in signals
        )
        or any(
            key in value
            for key in ("assignment_id", "lease_id", "shard_id")
        )
    )


def parse_public_data_bytes(data: bytes, suffix: str, label: str) -> Any:
    if len(data) > MAX_PUBLIC_DATA_BYTES:
        raise SyndicationError(
            "public data object exceeds the four MiB limit: {}".format(label)
        )
    if suffix == ".json":
        value = load_json_bytes(data, label)
        if _contains_rejected_candidate(value):
            return REJECTED_PUBLIC_DATA
        try:
            validate_public_data_value(value)
        except SyndicationError:
            if _has_shard_signal(value, label):
                return REJECTED_PUBLIC_DATA
            raise
        return value
    values = []
    if data and not data.endswith(b"\n"):
        raise SyndicationError(
            "public JSONL object lacks a final newline: {}".format(label)
        )
    for line_number, line in enumerate(data.splitlines(), 1):
        if not line:
            raise SyndicationError(
                "blank public JSONL line {} in {}".format(
                    line_number,
                    label,
                )
            )
        item = load_json_bytes(
            line,
            "{} line {}".format(label, line_number),
        )
        if _contains_rejected_candidate(item):
            return REJECTED_PUBLIC_DATA
        try:
            validate_public_data_value(item)
        except SyndicationError:
            if _has_shard_signal(item, label):
                return REJECTED_PUBLIC_DATA
            raise
        values.append(item)
    return values


def _public_data_metadata(value: Any) -> Dict[str, Any]:
    if type(value) is not dict:
        return {}
    allowed = {
        "attention_group",
        "base_record_id",
        "branch",
        "created_at",
        "dimension_id",
        "group_id",
        "kind",
        "schema",
        "sequence",
        "type",
        "updated_at",
        "visibility",
    }
    return {
        key: value[key]
        for key in sorted(allowed)
        if key in value
        and (
            value[key] is None
            or type(value[key]) in {str, int, bool}
        )
    }


def _looking_glass_metadata(
    value: Any,
    path: str,
) -> Optional[Dict[str, Any]]:
    if not path.startswith("apps/looking-glass/"):
        return None
    if type(value) is not dict:
        raise SyndicationError("Looking Glass scene must be an object")
    target = value.get("target_frame")
    integrity = value.get("integrity")
    dimensions = value.get("dimensions")
    experience_id = value.get(
        "experience_id",
        "looking-glass-inside-one-hash",
    )
    visibility = value.get("visibility", "public-metadata")
    public_scene = (
        value.get("status") == "public-structural-view"
        or (
            value.get("visibility") == "public-metadata"
            and type(value.get("experience_id")) is str
            and bool(value["experience_id"])
        )
    )
    if (
        value.get("schema") != "rappterzoo-looking-glass-scene/1"
        or not public_scene
        or visibility != "public-metadata"
        or type(experience_id) is not str
        or not experience_id
        or type(target) is not dict
        or type(target.get("frame_hash")) is not str
        or not HASH_RE.fullmatch(target["frame_hash"])
        or type(integrity) is not dict
        or type(integrity.get("scene_digest")) is not str
        or not HASH_RE.fullmatch(integrity["scene_digest"])
        or type(dimensions) is not list
        or len(dimensions) != 7
    ):
        raise SyndicationError("invalid Looking Glass scene object")
    return {
        "dimension_count": len(dimensions),
        "experience_id": experience_id,
        "scene_digest": integrity["scene_digest"],
        "schema": value["schema"],
        "target_frame_hash": target["frame_hash"],
        "visibility": visibility,
    }


def _agent_park_metadata(
    value: Any,
    path: str,
) -> Optional[Dict[str, Any]]:
    if not path.startswith("apps/agent-park/"):
        return None
    if path.endswith("/park-state.json"):
        if type(value) is not dict:
            raise SyndicationError("agent park state must be an object")
        ledger = value.get("event_ledger")
        economy = value.get("economy")
        if (
            value.get("schema") != "rappterzoo-agent-amusement-park/1"
            or value.get("visibility") != "public-metadata"
            or value.get("park_id")
            != "park.rappterzoo-agent-amusement-park"
            or type(ledger) is not dict
            or type(ledger.get("event_count")) is not int
            or type(ledger.get("head")) is not str
            or not HASH_RE.fullmatch(ledger["head"])
            or value.get("night_count") != 7
            or type(economy) is not dict
            or economy.get("real_money") is not False
            or economy.get("balanced") is not True
        ):
            raise SyndicationError("invalid agent amusement park state")
        return {
            "event_count": ledger["event_count"],
            "event_head": ledger["head"],
            "night_count": value["night_count"],
            "park_id": value["park_id"],
            "resource_type": "state",
            "schema": value["schema"],
            "visibility": value["visibility"],
        }
    if path.endswith("/agent-contract.json"):
        if type(value) is not dict:
            raise SyndicationError("agent park contract must be an object")
        integrity = value.get("integrity")
        economy = value.get("economy")
        controls = value.get("control_boundary")
        if (
            value.get("schema") != "rappterzoo-agent-park-contract/1"
            or value.get("visibility") != "public-metadata"
            or value.get("park_id")
            != "park.rappterzoo-agent-amusement-park"
            or type(integrity) is not dict
            or type(integrity.get("contract_digest")) is not str
            or not HASH_RE.fullmatch(integrity["contract_digest"])
            or type(economy) is not dict
            or economy.get("real_money") is not False
            or type(controls) is not dict
            or controls.get("customer_can_shutdown_immediately") is not True
            or controls.get("park_or_vendor_remote_shutdown") is not False
        ):
            raise SyndicationError("invalid agent amusement park contract")
        return {
            "contract_digest": integrity["contract_digest"],
            "park_id": value["park_id"],
            "resource_type": "agent-contract",
            "schema": value["schema"],
            "visibility": value["visibility"],
        }
    if path.endswith("/events.jsonl"):
        validate_agent_park_event_ledger(value)
        return {
            "event_count": len(value),
            "event_head": value[-1]["event_hash"],
            "park_id": value[-1]["park_id"],
            "resource_type": "event-ledger",
            "schema": value[-1]["schema"],
            "visibility": value[-1]["visibility"],
        }
    raise SyndicationError("unknown agent amusement park public object")


def _bounded_metadata_copy(
    value: Any,
    depth: int = 0,
) -> Any:
    if depth > 6:
        return "[bounded]"
    if value is None or type(value) in {bool, int}:
        return value
    if type(value) is str:
        return value[:2048]
    if isinstance(value, list):
        return [
            _bounded_metadata_copy(item, depth + 1)
            for item in value[:64]
        ]
    if type(value) is dict:
        return {
            key: _bounded_metadata_copy(value[key], depth + 1)
            for key in sorted(value)[:96]
        }
    return str(value)[:2048]


def _dimension_metadata(value: Any, path: str) -> Optional[Dict[str, Any]]:
    items = value if isinstance(value, list) else [value]
    dimension_items = []
    for item in items:
        if type(item) is not dict:
            continue
        signals = [
            item.get("kind"),
            item.get("type"),
            item.get("schema"),
        ]
        if (
            any(
                type(signal) is str
                and "dimension" in signal.lower()
                for signal in signals
            )
            or item.get("branch") in {"hot", "cold"}
            or type(item.get("branches")) is dict
        ):
            dimension_items.append(item)
    if not dimension_items:
        return None
    base_ids = set()
    branches = set()
    drift_values = []
    dimension_ids = []
    for item in dimension_items:
        base_id = (
            item.get("base_record_id")
            or item.get("base_record")
            or item.get("base_id")
        )
        if type(base_id) not in {str, int} or str(base_id) == "":
            raise SyndicationError(
                "dimension object lacks a base record id: {}".format(path)
            )
        base_ids.add(str(base_id))
        branch = item.get("branch")
        branch_bundle = item.get("branches")
        if branch in {"hot", "cold"}:
            branches.add(branch)
        elif type(branch_bundle) is dict:
            present = set(branch_bundle)
            if not present or not present.issubset({"hot", "cold"}):
                raise SyndicationError(
                    "dimension bundle has invalid branches: {}".format(path)
                )
            branches.update(present)
        else:
            raise SyndicationError(
                "dimension object requires hot/cold branch metadata: {}".format(
                    path
                )
            )
        drift = item.get("drift_metadata", item.get("drift"))
        if type(drift) is not dict:
            raise SyndicationError(
                "dimension object lacks drift metadata: {}".format(path)
            )
        drift_values.append(_bounded_metadata_copy(drift))
        if type(item.get("dimension_id")) is str:
            dimension_ids.append(item["dimension_id"])
    if len(base_ids) != 1:
        raise SyndicationError(
            "dimension bundle spans multiple base records: {}".format(path)
        )
    ordered_branches = [
        branch
        for branch in ("hot", "cold")
        if branch in branches
    ]
    drift_projection = (
        drift_values[0]
        if len(drift_values) == 1
        else drift_values
    )
    return {
        "base_record_id": next(iter(base_ids)),
        "branches_present": ordered_branches,
        "dimension_ids": sorted(set(dimension_ids)),
        "drift": drift_projection,
        "drift_sha256": sha256_bytes(
            stable_json_bytes(drift_projection)
        ),
        "merge_order": ["hot", "cold"],
    }


def _shard_metadata(
    value: Any,
    path: str,
    synthetic_test_mode: bool = False,
) -> Any:
    items = value if isinstance(value, list) else [value]
    shard_items = [
        item
        for item in items
        if type(item) is dict and _has_shard_signal(item, path)
    ]
    if not shard_items:
        return None
    first = shard_items[0]
    visibility = first.get("visibility")
    if visibility not in {"public", "public-metadata"}:
        return REJECTED_PUBLIC_DATA
    signals = " ".join(
        str(first.get(key, ""))
        for key in ("kind", "type", "schema")
    ).lower() + " " + path.lower()
    if "assignment" in signals:
        object_kind = "fold-shard-assignment"
        required_id = "assignment_id"
    elif "lease" in signals:
        object_kind = "fold-shard-lease"
        required_id = "lease_id"
    elif "challenge" in signals:
        object_kind = "fold-challenge"
        required_id = "challenge_id"
    elif "control-award" in signals or (
        "control" in signals and "award" in signals
    ):
        object_kind = "fold-control-award-receipt"
        required_id = "award_id"
    elif "action-receipt" in signals or (
        "action" in signals and "receipt" in signals
    ):
        object_kind = "fold-action-receipt"
        required_id = "action_receipt_id"
    elif "proof" in signals:
        object_kind = "fold-proof-receipt"
        required_id = "proof_id"
    elif "dimension" in signals:
        object_kind = "fold-shard-dimension-object"
        required_id = "shard_id"
    elif "result" in signals or "candidate" in signals:
        object_kind = "fold-shard-result-object"
        required_id = "shard_id"
    else:
        return None
    synthetic_cycle_kinds = {
        "fold-action-receipt",
        "fold-challenge",
        "fold-control-award-receipt",
        "fold-proof-receipt",
    }
    if object_kind in synthetic_cycle_kinds and not synthetic_test_mode:
        return REJECTED_PUBLIC_DATA
    frame_control = first.get("frame_control")
    frame_control = (
        frame_control
        if type(frame_control) is dict
        else {}
    )
    declared_mode = first.get(
        "frame_control_mode",
        frame_control.get("mode"),
    )
    expected_mode = (
        "proof-of-fold"
        if object_kind in synthetic_cycle_kinds
        else "assigned"
    )
    if declared_mode != expected_mode:
        return REJECTED_PUBLIC_DATA
    if type(first.get("shard_id")) is not str or not first["shard_id"]:
        return REJECTED_PUBLIC_DATA
    if (
        type(first.get(required_id)) is not str
        or not first.get(required_id)
    ):
        return REJECTED_PUBLIC_DATA
    if object_kind in {
        "fold-action-receipt",
        "fold-challenge",
        "fold-control-award-receipt",
        "fold-proof-receipt",
        "fold-shard-result-object",
        "fold-shard-dimension-object",
    }:
        assembly = first.get("assembly")
        assembly = assembly if type(assembly) is dict else {}
        status = first.get(
            "assembler_status",
            assembly.get("status"),
        )
        main_append = first.get(
            "main_append",
            assembly.get("main_append"),
        )
        if status != "accepted" or main_append is not True:
            return REJECTED_PUBLIC_DATA
    if object_kind == "fold-shard-lease":
        lease_bounds = first.get(
            "lease_bounds",
            first.get("bounds"),
        )
        if type(lease_bounds) is not dict or not lease_bounds:
            return REJECTED_PUBLIC_DATA
    else:
        lease_bounds = None
    if object_kind in {
        "fold-shard-result-object",
        "fold-shard-dimension-object",
    } and (
        type(first.get("lease_id")) is not str
        or not first["lease_id"]
    ):
        return REJECTED_PUBLIC_DATA
    allowed = {
        "accepted_at",
        "action_id",
        "action_receipt_id",
        "assembler_status",
        "assignment_id",
        "award_id",
        "base_record_id",
        "challenge_id",
        "control_id",
        "created_at",
        "expires_at",
        "issued_at",
        "lease_id",
        "main_append",
        "proof_id",
        "result_id",
        "shard_id",
        "updated_at",
        "visibility",
    }
    metadata = {
        key: first[key]
        for key in sorted(allowed)
        if key in first
        and (
            first[key] is None
            or type(first[key]) in {str, int, bool}
        )
    }
    provenance = first.get("provenance")
    if type(provenance) is dict:
        projection = _bounded_metadata_copy(provenance)
        metadata["provenance"] = projection
        metadata["provenance_sha256"] = sha256_bytes(
            stable_json_bytes(projection)
        )
    if lease_bounds is not None:
        metadata["lease_bounds"] = _bounded_metadata_copy(lease_bounds)
    if object_kind == "fold-shard-dimension-object":
        dimension = _dimension_metadata(value, path)
        if dimension is None:
            return REJECTED_PUBLIC_DATA
        metadata.update(dimension)
    metadata["isolated_shard_provenance"] = True
    mode = expected_mode
    metadata["frame_control"] = {
        "mode": mode,
        "proof_race": False,
    }
    metadata["frame_control_mode"] = mode
    metadata["rollout_phase"] = "initial-public-soak"
    if object_kind in synthetic_cycle_kinds:
        metadata["synthetic_test_only"] = True
    return object_kind, metadata


def _data_descriptor_sort_key(
    descriptor: Dict[str, Any],
) -> Tuple[Any, ...]:
    if descriptor["kind"] == "attention-dimension-object":
        metadata = descriptor["metadata"]
        branches = metadata.get("branches_present", [])
        first_branch = branches[0] if branches else ""
        branch_rank = {"hot": 0, "cold": 1}.get(first_branch, 2)
        return (
            0,
            str(metadata.get("base_record_id", "")),
            branch_rank,
            descriptor["path"],
        )
    if descriptor["kind"].startswith("fold-"):
        metadata = descriptor["metadata"]
        kind_rank = {
            "fold-shard-assignment": 0,
            "fold-shard-lease": 1,
            "fold-challenge": 2,
            "fold-proof-receipt": 3,
            "fold-control-award-receipt": 4,
            "fold-action-receipt": 5,
            "fold-shard-result-object": 6,
            "fold-shard-dimension-object": 7,
        }.get(descriptor["kind"], 8)
        branches = metadata.get("branches_present", [])
        branch_rank = {
            "hot": 0,
            "cold": 1,
        }.get(branches[0] if branches else "", 2)
        return (
            0,
            str(metadata.get("shard_id", "")),
            kind_rank,
            branch_rank,
            descriptor["path"],
        )
    return (2, descriptor["path"])


def build_public_data_descriptors(
    root: Path,
    base_url: str,
    synthetic_test_mode: bool = False,
) -> List[Dict[str, Any]]:
    data_paths = []
    for directory_name in PUBLIC_DATA_ROOTS:
        directory = root / "apps" / directory_name
        if not directory.exists():
            continue
        if not directory.is_dir():
            raise SyndicationError(
                "apps/{} must be a directory".format(directory_name)
            )
        data_paths.extend(
            path
            for path in directory.rglob("*")
            if path.is_file()
        )
    descriptors = []
    for path in sorted(set(data_paths)):
        if path.name.startswith("."):
            continue
        suffix = path.suffix.lower()
        if suffix not in PUBLIC_DATA_SUFFIXES:
            continue
        relative = path.relative_to(root).as_posix()
        data = path.read_bytes()
        parsed = parse_public_data_bytes(data, suffix, relative)
        if parsed is REJECTED_PUBLIC_DATA:
            continue
        digest = sha256_bytes(data)
        root_value = (
            parsed[0]
            if isinstance(parsed, list) and parsed
            else parsed
        )
        metadata = _public_data_metadata(root_value)
        kind = "attention-group-object"
        agent_park_metadata = _agent_park_metadata(
            parsed,
            relative,
        )
        looking_glass_metadata = _looking_glass_metadata(
            parsed,
            relative,
        )
        if agent_park_metadata is not None:
            kind = "agent-amusement-park-object"
            metadata = agent_park_metadata
        elif looking_glass_metadata is not None:
            kind = "looking-glass-scene-object"
            metadata = looking_glass_metadata
        else:
            shard_metadata = _shard_metadata(
                parsed,
                relative,
                synthetic_test_mode=synthetic_test_mode,
            )
            if shard_metadata is REJECTED_PUBLIC_DATA:
                continue
            if shard_metadata is not None:
                kind, shard_projection = shard_metadata
                metadata.update(shard_projection)
            else:
                dimension_metadata = _dimension_metadata(parsed, relative)
                if dimension_metadata is not None:
                    kind = "attention-dimension-object"
                    metadata.update(dimension_metadata)
        descriptors.append({
            "content_id": "sha256:{}".format(digest),
            "kind": kind,
            "media_type": PUBLIC_DATA_SUFFIXES[suffix],
            "metadata": metadata,
            "path": relative,
            "sha256": digest,
            "size": len(data),
            "url": _app_url(base_url, relative),
            "verification": {
                "algorithm": "sha256",
                "required": True,
            },
        })
    return sorted(descriptors, key=_data_descriptor_sort_key)


def _agent_park_history_growth(
    root: Path,
    previous_data_map: Dict[str, Dict[str, Any]],
    current_data_map: Dict[str, Dict[str, Any]],
) -> bool:
    path = "apps/agent-park/events.jsonl"
    previous = previous_data_map.get(path)
    current = current_data_map.get(path)
    if (
        type(previous) is not dict
        or type(current) is not dict
        or previous.get("kind") != "agent-amusement-park-object"
        or current.get("kind") != "agent-amusement-park-object"
        or previous.get("metadata", {}).get("resource_type")
        != "event-ledger"
        or current.get("metadata", {}).get("resource_type")
        != "event-ledger"
    ):
        return False
    previous_count = previous["metadata"].get("event_count")
    current_count = current["metadata"].get("event_count")
    previous_head = previous["metadata"].get("event_head")
    current_head = current["metadata"].get("event_head")
    if (
        type(previous_count) is not int
        or type(current_count) is not int
        or current_count <= previous_count
        or type(previous_head) is not str
        or type(current_head) is not str
    ):
        return False
    ledger_path = root / path
    parsed = parse_public_data_bytes(
        ledger_path.read_bytes(),
        ".jsonl",
        path,
    )
    events = validate_agent_park_event_ledger(parsed)
    return (
        len(events) == current_count
        and events[previous_count - 1]["event_hash"] == previous_head
        and events[-1]["event_hash"] == current_head
    )


def validate_frames(
    frames: Iterable[Dict[str, Any]],
    previous: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    materialized = list(frames)
    prior = previous
    seen_event_ids = set()
    for offset, frame in enumerate(materialized):
        if type(frame) is not dict or set(frame) != FRAME_KEYS:
            raise SyndicationError(
                "frame {} does not have exactly eleven keys".format(offset)
            )
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
            raise SyndicationError("invalid RAPP/1 frame structure")
        payload = _normalize_frame_json(frame["payload"])
        if (
            payload.get("schema") != FRAME_SCHEMA
            or payload.get("visibility") != "public-metadata"
            or type(payload.get("event_id")) is not str
            or not payload.get("event_id")
            or type(payload.get("event")) is not str
            or not payload.get("event")
            or type(payload.get("organism")) is not str
            or not payload.get("organism")
        ):
            raise SyndicationError("invalid public frame payload")
        forbidden = _find_forbidden_key(payload)
        if forbidden:
            raise SyndicationError(
                "public frame contains forbidden key {}".format(forbidden)
            )
        _validate_shard_main_append(payload)
        if payload["event_id"] in seen_event_ids:
            raise SyndicationError(
                "duplicate event_id {}".format(payload["event_id"])
            )
        seen_event_ids.add(payload["event_id"])
        expected_payload = frame_hash_value(PARTICLE_SPACE, payload)
        if frame["payload_hash"] != expected_payload:
            raise SyndicationError("frame payload hash mismatch")
        wave = {
            key: value
            for key, value in frame.items()
            if key not in {"frame_hash", "sig"}
        }
        if frame["frame_hash"] != frame_hash_value(WAVE_SPACE, wave):
            raise SyndicationError("frame wave hash mismatch")
        if prior is None:
            if frame["seq"] != 0:
                raise SyndicationError("first frame must be sequence zero")
            if frame["prev"] is not None or frame["prev_wave"] is not None:
                raise SyndicationError("genesis links must be null")
        else:
            if frame["seq"] != prior["seq"] + 1:
                raise SyndicationError("frame sequence gap")
            if frame["utc"] < prior["utc"]:
                raise SyndicationError("frame timestamps are not monotonic")
            if frame["prev"] != prior["payload_hash"]:
                raise SyndicationError("frame particle link mismatch")
            if frame["prev_wave"] != prior["frame_hash"]:
                raise SyndicationError("frame wave link mismatch")
        prior = frame
    return materialized


def read_ledger(path: Path) -> List[Dict[str, Any]]:
    if not path.is_file():
        raise SyndicationError("missing append-only ledger: {}".format(path))
    data = path.read_bytes()
    if data and not data.endswith(b"\n"):
        raise SyndicationError("append-only ledger lacks a final newline")
    frames = []
    for line_number, line in enumerate(data.splitlines(), 1):
        if not line:
            raise SyndicationError(
                "blank append-only ledger line {}".format(line_number)
            )
        frame = load_json_bytes(
            line,
            "organism ledger line {}".format(line_number),
        )
        if canonical_frame_bytes(frame) != line:
            raise SyndicationError(
                "non-canonical organism ledger line {}".format(line_number)
            )
        frames.append(frame)
    return validate_frames(frames)


def _safe_relative_path(path: str) -> str:
    candidate = Path(path)
    if (
        not path
        or candidate.is_absolute()
        or ".." in candidate.parts
        or "\\" in path
    ):
        raise SyndicationError("unsafe relative path {}".format(path))
    return candidate.as_posix()


def _app_url(base_url: str, path: str) -> str:
    return urljoin(
        base_url.rstrip("/") + "/",
        quote(path, safe="/"),
    )


def build_app_descriptors(
    root: Path,
    manifest: Dict[str, Any],
    base_url: str,
) -> List[Dict[str, Any]]:
    categories = manifest.get("categories")
    if type(categories) is not dict:
        raise SyndicationError("manifest categories must be an object")
    descriptors = []
    seen_paths = set()
    for category_key in sorted(categories):
        category = categories[category_key]
        if type(category) is not dict:
            raise SyndicationError("manifest category must be an object")
        folder = category.get("folder", category_key)
        if type(folder) is not str:
            raise SyndicationError("manifest category folder must be a string")
        category_metadata = {
            key: value
            for key, value in category.items()
            if key != "apps"
        }
        apps = category.get("apps", [])
        if type(apps) is not list:
            raise SyndicationError("manifest apps must be an array")
        if "count" in category and category["count"] != len(apps):
            raise SyndicationError(
                "manifest count mismatch for {}".format(category_key)
            )
        for entry in apps:
            if type(entry) is not dict or type(entry.get("file")) is not str:
                raise SyndicationError("manifest app entry is malformed")
            relative = _safe_relative_path(
                "apps/{}/{}".format(folder, entry["file"])
            )
            if relative in seen_paths:
                raise SyndicationError(
                    "duplicate manifest app path {}".format(relative)
                )
            seen_paths.add(relative)
            app_path = root / relative
            if not app_path.is_file():
                raise SyndicationError(
                    "manifest app is missing: {}".format(relative)
                )
            data = app_path.read_bytes()
            digest = sha256_bytes(data)
            descriptors.append({
                "content_id": "sha256:{}".format(digest),
                "metadata": {
                    "app": entry,
                    "category": category_key,
                    "category_metadata": category_metadata,
                },
                "path": relative,
                "sha256": digest,
                "size": len(data),
                "url": _app_url(base_url, relative),
                "verification": {
                    "algorithm": "sha256",
                    "required": True,
                },
            })
    return sorted(descriptors, key=lambda item: item["path"])


def _load_json_file(path: Path) -> Any:
    return load_json_bytes(path.read_bytes(), str(path))


def _manifest_timestamp(manifest: Dict[str, Any]) -> str:
    raw = manifest.get("meta", {}).get("lastUpdated")
    if type(raw) is str and raw:
        text = raw.strip()
        try:
            if len(text) == 10:
                moment = datetime.strptime(text, "%Y-%m-%d").replace(
                    tzinfo=timezone.utc
                )
            else:
                moment = datetime.fromisoformat(
                    text.replace("Z", "+00:00")
                )
                if moment.tzinfo is None:
                    moment = moment.replace(tzinfo=timezone.utc)
                moment = moment.astimezone(timezone.utc)
            return moment.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        except ValueError:
            pass
    return "1970-01-01T00:00:00.000Z"


def _descriptor_map(items: Any) -> Dict[str, Dict[str, Any]]:
    if type(items) is not list:
        raise SyndicationError("snapshot apps must be an array")
    result = {}
    for item in items:
        if type(item) is not dict or type(item.get("path")) is not str:
            raise SyndicationError("snapshot contains an invalid app descriptor")
        if item["path"] in result:
            raise SyndicationError("snapshot contains a duplicate app path")
        result[item["path"]] = item
    return result


def _tombstone_map(items: Any) -> Dict[str, Dict[str, Any]]:
    if type(items) is not list:
        raise SyndicationError("snapshot tombstones must be an array")
    result = {}
    for item in items:
        if type(item) is not dict or type(item.get("path")) is not str:
            raise SyndicationError("snapshot contains an invalid tombstone")
        result[item["path"]] = item
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
            if (
                bucket
                and metadata.get("challenge_id") == challenge_id
            ):
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


def block_metadata(
    delta: Dict[str, Any],
    digest: str,
) -> Dict[str, Any]:
    disabled_proof = {
        "acceptance": "centralized-publisher-assembler",
        "cycles": [],
        "frame_control_mode": "observer",
        "status": "disabled-observer",
        "synthetic_test_only": False,
    }
    proof = (
        delta.get("proof_of_fold", disabled_proof)
        if delta.get("profile") == PROFILE
        else disabled_proof
    )
    frame_control = frame_control_metadata(delta["changes"], proof)
    return {
        "consensus": "none",
        "frame_control": frame_control,
        "mining": False,
        "model": BLOCK_MODEL,
        "next_frame_challenge_seed": next_challenge_seed(digest),
        "proof_of_fold": proof,
        "rollout": SOAK_ROLLOUT,
        "resulting_head": {
            "sequence": delta["sequence"],
            "sha256": digest,
        },
        "token": False,
    }


def _delta_entry(
    delta: Dict[str, Any],
    digest: str,
    delta_bytes: bytes,
    base_url: str,
) -> Dict[str, Any]:
    relative = "apps/syndication/deltas/{}.json".format(digest)
    changes = delta["changes"]
    segments = segment_metadata(changes)
    entry = {
        "app_tombstones": len(changes["app_tombstones"]),
        "app_upserts": len(changes["app_upserts"]),
        "block": block_metadata(delta, digest),
        "created_at": delta["created_at"],
        "data_tombstones": len(changes.get("data_tombstones", [])),
        "data_upserts": len(changes.get("data_upserts", [])),
        "frame_appends": len(changes["frame_appends"]),
        "path": "deltas/{}.json".format(digest),
        "previous_delta": delta["previous_delta"],
        "profile": delta.get("profile", "legacy"),
        "sequence": delta["sequence"],
        "segment_hashes": {
            "apps": segments["apps"]["sha256"],
            "frames": segments["frames"]["sha256"],
        },
        "sha256": digest,
        "since_seq": delta["sequence"] - 1,
        "size": len(delta_bytes),
        "through_seq": delta["sequence"],
        "url": _app_url(base_url, relative),
    }
    if "data" in segments:
        entry["segment_hashes"]["data"] = segments["data"]["sha256"]
    return entry


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


def _replay_descriptor(
    value: Any,
    label: str,
) -> Dict[str, Any]:
    if type(value) is not dict or type(value.get("path")) is not str:
        raise SyndicationError(
            "immutable delta contains invalid {} descriptor".format(label)
        )
    result = dict(value)
    result["path"] = _safe_relative_path(result["path"])
    return result


def _replay_tombstone(
    value: Any,
    sequence: int,
    label: str,
) -> Dict[str, Any]:
    if (
        type(value) is not dict
        or value.get("sequence") != sequence
        or type(value.get("path")) is not str
    ):
        raise SyndicationError(
            "immutable delta contains invalid {} tombstone".format(label)
        )
    result = dict(value)
    result["path"] = _safe_relative_path(result["path"])
    descriptor = _replay_descriptor(
        result.get("descriptor"),
        label,
    )
    if descriptor["path"] != result["path"]:
        raise SyndicationError(
            "{} tombstone descriptor path mismatch".format(label)
        )
    result["descriptor"] = descriptor
    return result


def replay_immutable_deltas(
    deltas: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    apps = {}
    data_objects = {}
    frames = []
    tombstones = {}
    data_tombstones = {}
    for expected_sequence, delta in enumerate(deltas):
        if delta.get("sequence") != expected_sequence:
            raise SyndicationError("immutable delta replay sequence mismatch")
        changes = delta.get("changes")
        if type(changes) is not dict:
            raise SyndicationError("immutable delta changes are malformed")
        for descriptor_value in changes.get("app_upserts", []):
            descriptor = _replay_descriptor(
                descriptor_value,
                "app",
            )
            apps[descriptor["path"]] = descriptor
            tombstones.pop(descriptor["path"], None)
        for tombstone_value in changes.get("app_tombstones", []):
            tombstone = _replay_tombstone(
                tombstone_value,
                expected_sequence,
                "app",
            )
            apps.pop(tombstone["path"], None)
            tombstones[tombstone["path"]] = tombstone
        for descriptor_value in changes.get("data_upserts", []):
            descriptor = _replay_descriptor(
                descriptor_value,
                "data",
            )
            data_objects[descriptor["path"]] = descriptor
            data_tombstones.pop(descriptor["path"], None)
        for tombstone_value in changes.get("data_tombstones", []):
            tombstone = _replay_tombstone(
                tombstone_value,
                expected_sequence,
                "data",
            )
            data_objects.pop(tombstone["path"], None)
            data_tombstones[tombstone["path"]] = tombstone
        frame_appends = changes.get("frame_appends", [])
        if type(frame_appends) is not list:
            raise SyndicationError("immutable frame segment is not an array")
        frames.extend(frame_appends)
        validate_frames(frames)
    return {
        "apps": [
            apps[path]
            for path in sorted(apps)
        ],
        "data_objects": sorted(
            data_objects.values(),
            key=_data_descriptor_sort_key,
        ),
        "data_tombstones": [
            data_tombstones[path]
            for path in sorted(data_tombstones)
        ],
        "frames": frames,
        "tombstones": [
            tombstones[path]
            for path in sorted(tombstones)
        ],
    }


def require_snapshot_replay_agreement(
    snapshot: Dict[str, Any],
    replay: Dict[str, Any],
    history: Sequence[Dict[str, Any]],
) -> None:
    expected_head = None
    if history:
        latest = history[-1]
        expected_head = {
            "path": latest["path"],
            "sequence": latest["sequence"],
            "sha256": latest["sha256"],
            "url": latest["url"],
        }
    expected_state = {
        "apps": replay["apps"],
        "data_objects": replay["data_objects"],
        "data_tombstones": replay["data_tombstones"],
        "frames": replay["frames"],
        "head": expected_head,
        "tombstones": replay["tombstones"],
    }
    for key, expected in expected_state.items():
        if stable_json_bytes(snapshot.get(key)) != stable_json_bytes(
            expected
        ):
            raise SyndicationError(
                "snapshot {} disagrees with immutable delta replay".format(
                    key
                )
            )
    expected_counts = {
        "active_apps": len(replay["apps"]),
        "attention_data_objects": len(replay["data_objects"]),
        "data_tombstones": len(replay["data_tombstones"]),
        "frames": len(replay["frames"]),
        "tombstones": len(replay["tombstones"]),
    }
    if snapshot.get("counts") != expected_counts:
        raise SyndicationError(
            "snapshot counts disagree with immutable delta replay"
        )
    expected_checkpoint = {
        "delta_sha256": (
            history[-1]["sha256"]
            if history
            else None
        ),
        "next_frame_challenge_seed": (
            history[-1]["block"]["next_frame_challenge_seed"]
            if history
            else None
        ),
        "since_seq": (
            history[-1]["sequence"]
            if history
            else -1
        ),
    }
    if snapshot.get("checkpoint") != expected_checkpoint:
        raise SyndicationError(
            "snapshot checkpoint disagrees with immutable delta replay"
        )


def load_existing_chain(
    output_dir: Path,
    snapshot: Optional[Dict[str, Any]],
    base_url: str,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    index_path = output_dir / "index.json"
    if not index_path.exists():
        if snapshot is not None and snapshot.get("head") is not None:
            raise SyndicationError("snapshot has a head but index.json is missing")
        return [], replay_immutable_deltas([])
    index = _load_json_file(index_path)
    if type(index) is not dict or index.get("schema") != INDEX_SCHEMA:
        raise SyndicationError("existing syndication index has the wrong schema")
    entries = index.get("deltas")
    if type(entries) is not list:
        raise SyndicationError("existing syndication index has no delta list")
    if entries and snapshot is None:
        raise SyndicationError(
            "immutable history exists but snapshot.json is missing"
        )
    validated = []
    deltas = []
    previous_hash = None
    for expected_sequence, entry in enumerate(entries):
        if (
            type(entry) is not dict
            or entry.get("sequence") != expected_sequence
            or type(entry.get("sha256")) is not str
            or not HASH_RE.fullmatch(entry["sha256"])
            or entry.get("previous_delta") != previous_hash
        ):
            raise SyndicationError("existing syndication index chain is invalid")
        delta_path = output_dir / "deltas" / (
            entry["sha256"] + ".json"
        )
        if not delta_path.is_file():
            raise SyndicationError(
                "immutable delta is missing: {}".format(delta_path.name)
            )
        delta_bytes = delta_path.read_bytes()
        if sha256_bytes(delta_bytes) != entry["sha256"]:
            raise SyndicationError(
                "immutable delta bytes were rewritten: {}".format(
                    delta_path.name
                )
            )
        delta = load_json_bytes(delta_bytes, str(delta_path))
        if stable_json_bytes(delta) != delta_bytes:
            raise SyndicationError("immutable delta is not canonical JSON")
        if (
            delta.get("schema") != DELTA_SCHEMA
            or delta.get("stream_id") != STREAM_ID
            or delta.get("sequence") != expected_sequence
            or delta.get("previous_delta") != previous_hash
        ):
            raise SyndicationError("immutable delta content is invalid")
        if "segments" in delta and (
            delta.get("segments") != segment_metadata(delta["changes"])
            or delta.get("since_seq") != expected_sequence - 1
            or delta.get("through_seq") != expected_sequence
            or delta.get("profile") not in {
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
        ):
            raise SyndicationError(
                "immutable delta segment checkpoint is invalid"
            )
        if delta.get("profile") in {
            PROFILE_V3,
            PROFILE_V4,
            PROFILE_V5,
            PROFILE_V6,
            PROFILE_V7,
            PROFILE_V8,
            PROFILE_V9,
            PROFILE,
        } and set(
            delta["changes"]
        ) != {
            "app_tombstones",
            "app_upserts",
            "data_tombstones",
            "data_upserts",
            "frame_appends",
        }:
            raise SyndicationError(
                "profile 3 delta lacks generic data segments"
            )
        if (
            delta.get("profile") == PROFILE
            and delta.get("transparency") != TRANSPARENCY_MODEL
        ):
            raise SyndicationError(
                "transparency delta has an untruthful authority model"
            )
        if delta.get("profile") == PROFILE and (
            delta.get("rollout") != SOAK_ROLLOUT
            or delta.get("challenge_state_machine")
            != CHALLENGE_STATE_MACHINE
            or delta.get("frame_control_schema")
            != FRAME_CONTROL_SCHEMA
        ):
            raise SyndicationError(
                "initial soak rollout gate metadata is invalid"
            )
        if (
            delta.get("profile") == PROFILE
            and delta.get("proof_of_fold")
            != proof_of_fold_metadata(
                delta["changes"],
                synthetic_test_mode=bool(
                    delta.get("proof_of_fold", {}).get(
                        "synthetic_test_only"
                    )
                ),
            )
        ):
            raise SyndicationError(
                "proof-of-fold block metadata is inconsistent"
            )
        if (
            delta.get("profile") == PROFILE
            and delta.get("frame_control")
            != frame_control_metadata(
                delta["changes"],
                delta["proof_of_fold"],
            )
        ):
            raise SyndicationError(
                "delta frame-control metadata is inconsistent"
            )
        canonical_entry = _delta_entry(
            delta,
            entry["sha256"],
            delta_bytes,
            base_url,
        )
        validated.append(canonical_entry)
        deltas.append(delta)
        previous_hash = entry["sha256"]
    if snapshot is not None:
        replay = replay_immutable_deltas(deltas)
        require_snapshot_replay_agreement(
            snapshot,
            replay,
            validated,
        )
    else:
        replay = replay_immutable_deltas(deltas)
    return validated, replay


def _write_if_changed(path: Path, data: bytes) -> bool:
    if path.exists() and path.read_bytes() == data:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    staging = path.with_name(path.name + ".new")
    staging.write_bytes(data)
    os.replace(str(staging), str(path))
    return True


def _write_immutable(path: Path, data: bytes) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != data:
            raise SyndicationError(
                "refusing to rewrite immutable delta {}".format(path.name)
            )
        return False
    try:
        with path.open("xb") as handle:
            handle.write(data)
    except FileExistsError:
        if path.read_bytes() != data:
            raise SyndicationError(
                "immutable delta appeared with different bytes"
            )
        return False
    return True


def build_atom(
    entries: List[Dict[str, Any]],
    base_url: str,
    updated: str,
) -> bytes:
    feed_url = _app_url(base_url, "apps/syndication/feed.xml")
    json_feed_url = _app_url(base_url, "apps/syndication/feed.json")
    index_url = _app_url(base_url, "apps/syndication/index.json")
    snapshot_url = _app_url(base_url, "apps/syndication/snapshot.json")
    lines = [
        '<?xml version="1.0" encoding="utf-8"?>',
        (
            '<feed xmlns="http://www.w3.org/2005/Atom" '
            'xmlns:rappterzoo="https://kody-w.github.io/'
            'localFirstTools-main/ns/syndication">'
        ),
        "  <id>{}</id>".format(escape(STREAM_ID)),
        "  <title>RappterZoo syndicated deltas</title>",
        "  <updated>{}</updated>".format(escape(updated)),
        "  <link rel=\"self\" type=\"application/atom+xml\" href={} />".format(
            quoteattr(feed_url)
        ),
        "  <link rel=\"alternate\" type=\"application/feed+json\" href={} />".format(
            quoteattr(json_feed_url)
        ),
        "  <link rel=\"alternate\" type=\"application/json\" href={} />".format(
            quoteattr(index_url)
        ),
        "  <link rel=\"related\" type=\"application/json\" href={} />".format(
            quoteattr(snapshot_url)
        ),
    ]
    for entry in reversed(entries):
        summary = (
            "{} app upserts, {} app tombstones, "
            "{} data upserts, {} data tombstones, "
            "{} exact frame appends"
        ).format(
            entry["app_upserts"],
            entry["app_tombstones"],
            entry.get("data_upserts", 0),
            entry.get("data_tombstones", 0),
            entry["frame_appends"],
        )
        lines.extend([
            "  <entry>",
            "    <id>urn:sha256:{}</id>".format(entry["sha256"]),
            "    <title>RappterZoo delta {}</title>".format(
                entry["sequence"]
            ),
            "    <updated>{}</updated>".format(
                escape(entry["created_at"])
            ),
            "    <link rel=\"alternate\" type=\"application/json\" href={} />".format(
                quoteattr(entry["url"])
            ),
            "    <content type=\"application/json\" src={} />".format(
                quoteattr(entry["url"])
            ),
            "    <summary>{}</summary>".format(escape(summary)),
            "    <rappterzoo:block>{}</rappterzoo:block>".format(
                escape(
                    json.dumps(
                        entry["block"],
                        ensure_ascii=False,
                        separators=(",", ":"),
                        sort_keys=True,
                    )
                )
            ),
            "  </entry>",
        ])
    lines.append("</feed>")
    return ("\n".join(lines) + "\n").encode("utf-8")


def build_json_feed(
    entries: List[Dict[str, Any]],
    base_url: str,
) -> bytes:
    items = []
    for entry in reversed(entries):
        summary = (
            "{} app upserts, {} app tombstones, "
            "{} data upserts, {} data tombstones, "
            "{} exact frame appends"
        ).format(
            entry["app_upserts"],
            entry["app_tombstones"],
            entry.get("data_upserts", 0),
            entry.get("data_tombstones", 0),
            entry["frame_appends"],
        )
        items.append({
            "_rappterzoo": {
                "block": entry["block"],
                "segment_hashes": entry["segment_hashes"],
                "sequence": entry["sequence"],
                "since_seq": entry["since_seq"],
                "through_seq": entry["through_seq"],
            },
            "attachments": [{
                "mime_type": "application/json",
                "size_in_bytes": entry["size"],
                "url": entry["url"],
            }],
            "content_text": summary,
            "date_modified": entry["created_at"],
            "date_published": entry["created_at"],
            "id": "urn:sha256:{}".format(entry["sha256"]),
            "title": "RappterZoo delta {}".format(entry["sequence"]),
            "url": entry["url"],
        })
    feed = {
        "_rappterzoo": {
            "atom_url": _app_url(base_url, "apps/syndication/feed.xml"),
        },
        "description": (
            "Content-addressed RappterZoo app and organism-frame deltas"
        ),
        "feed_url": _app_url(base_url, "apps/syndication/feed.json"),
        "home_page_url": _app_url(base_url, "apps/syndication/"),
        "items": items,
        "title": "RappterZoo syndicated deltas",
        "version": "https://jsonfeed.org/version/1.1",
    }
    return stable_json_bytes(feed)


def build(
    root: Path = ROOT,
    base_url: str = DEFAULT_BASE_URL,
    synthetic_test_mode: bool = False,
) -> Dict[str, Any]:
    root = root.resolve()
    manifest_path = root / "apps" / "manifest.json"
    ledger_path = root / "apps" / "organism-frames.jsonl"
    output_dir = root / "apps" / "syndication"
    if not manifest_path.is_file():
        raise SyndicationError("missing manifest.json")
    manifest = _load_json_file(manifest_path)
    if type(manifest) is not dict:
        raise SyndicationError("manifest root must be an object")
    current_apps = build_app_descriptors(root, manifest, base_url)
    current_data = build_public_data_descriptors(
        root,
        base_url,
        synthetic_test_mode=synthetic_test_mode,
    )
    current_frames = read_ledger(ledger_path)

    snapshot_path = output_dir / "snapshot.json"
    previous_snapshot = (
        _load_json_file(snapshot_path)
        if snapshot_path.exists()
        else None
    )
    if previous_snapshot is not None and (
        type(previous_snapshot) is not dict
        or previous_snapshot.get("schema") != SNAPSHOT_SCHEMA
    ):
        raise SyndicationError("existing snapshot has the wrong schema")

    history, replay = load_existing_chain(
        output_dir,
        previous_snapshot,
        base_url,
    )
    current_map = {
        descriptor["path"]: descriptor
        for descriptor in current_apps
    }
    current_data_map = {
        descriptor["path"]: descriptor
        for descriptor in current_data
    }
    if previous_snapshot is None:
        previous_map = {}
        previous_data_map = {}
        previous_frames = []
        app_tombstone_map = {}
        data_tombstone_map = {}
    else:
        previous_map = _descriptor_map(replay["apps"])
        previous_data_map = _descriptor_map(replay["data_objects"])
        previous_frames = replay["frames"]
        app_tombstone_map = _tombstone_map(
            replay["tombstones"]
        )
        data_tombstone_map = _tombstone_map(
            replay["data_tombstones"]
        )

    if len(current_frames) < len(previous_frames):
        raise SyndicationError("organism frame history was truncated")
    for index, old_frame in enumerate(previous_frames):
        if canonical_frame_bytes(old_frame) != canonical_frame_bytes(
            current_frames[index]
        ):
            raise SyndicationError(
                "organism frame history changed at sequence {}".format(index)
            )

    app_upserts = [
        current_map[path]
        for path in sorted(current_map)
        if path not in previous_map
        or stable_json_bytes(current_map[path])
        != stable_json_bytes(previous_map[path])
    ]
    enforce_data_immutability = (
        previous_snapshot is not None
        and previous_snapshot.get("profile") == PROFILE
    )
    if enforce_data_immutability:
        park_history_grew = _agent_park_history_growth(
            root,
            previous_data_map,
            current_data_map,
        )
        for path in sorted(set(previous_data_map) & set(current_data_map)):
            if (
                previous_data_map[path]["sha256"]
                != current_data_map[path]["sha256"]
            ):
                if (
                    park_history_grew
                    and path == "apps/agent-park/events.jsonl"
                ):
                    continue
                if (
                    park_history_grew
                    and path == "apps/agent-park/park-state.json"
                    and current_data_map[path].get("metadata", {}).get(
                        "event_count"
                    )
                    == current_data_map[
                        "apps/agent-park/events.jsonl"
                    ]["metadata"]["event_count"]
                    and current_data_map[path].get("metadata", {}).get(
                        "event_head"
                    )
                    == current_data_map[
                        "apps/agent-park/events.jsonl"
                    ]["metadata"]["event_head"]
                ):
                    continue
                raise SyndicationError(
                    "immutable attention data object changed: {}".format(path)
                )
    data_upserts = [
        descriptor
        for descriptor in current_data
        if (
            descriptor["path"] not in previous_data_map
            or stable_json_bytes(descriptor)
            != stable_json_bytes(
                previous_data_map[descriptor["path"]]
            )
        )
    ]
    removed_paths = sorted(set(previous_map) - set(current_map))
    removed_data_paths = sorted(
        set(previous_data_map) - set(current_data_map)
    )
    created_at = (
        current_frames[-1]["utc"]
        if current_frames
        else _manifest_timestamp(manifest)
    )
    next_sequence = len(history)
    app_tombstones = []
    for path in removed_paths:
        tombstone = {
            "descriptor": previous_map[path],
            "path": path,
            "reason": "absent-from-manifest",
            "removed_at": created_at,
            "sequence": next_sequence,
        }
        app_tombstones.append(tombstone)
        app_tombstone_map[path] = tombstone
    for descriptor in app_upserts:
        app_tombstone_map.pop(descriptor["path"], None)

    data_tombstones = []
    for path in removed_data_paths:
        tombstone = {
            "descriptor": previous_data_map[path],
            "path": path,
            "reason": "attention-object-absent",
            "removed_at": created_at,
            "sequence": next_sequence,
        }
        data_tombstones.append(tombstone)
        data_tombstone_map[path] = tombstone
    for descriptor in data_upserts:
        data_tombstone_map.pop(descriptor["path"], None)

    frame_appends = current_frames[len(previous_frames):]
    profile_upgrade = (
        previous_snapshot is not None
        and previous_snapshot.get("profile") != PROFILE
    )
    changed = (
        previous_snapshot is None
        or profile_upgrade
        or bool(app_upserts)
        or bool(app_tombstones)
        or bool(data_upserts)
        or bool(data_tombstones)
        or bool(frame_appends)
    )
    delta_created = False
    if changed:
        previous_hash = history[-1]["sha256"] if history else None
        delta_changes = {
            "app_tombstones": app_tombstones,
            "app_upserts": app_upserts,
            "data_tombstones": data_tombstones,
            "data_upserts": data_upserts,
            "frame_appends": frame_appends,
        }
        delta_proof = proof_of_fold_metadata(
            delta_changes,
            synthetic_test_mode=synthetic_test_mode,
        )
        delta = {
            "changes": delta_changes,
            "challenge_state_machine": CHALLENGE_STATE_MACHINE,
            "created_at": created_at,
            "frame_control": frame_control_metadata(
                delta_changes,
                delta_proof,
            ),
            "frame_control_schema": FRAME_CONTROL_SCHEMA,
            "profile": PROFILE,
            "previous_delta": previous_hash,
            "proof_of_fold": delta_proof,
            "rollout": SOAK_ROLLOUT,
            "schema": DELTA_SCHEMA,
            "segments": segment_metadata(delta_changes),
            "sequence": next_sequence,
            "since_seq": next_sequence - 1,
            "stream_id": STREAM_ID,
            "transparency": TRANSPARENCY_MODEL,
            "through_seq": next_sequence,
        }
        delta_bytes = stable_json_bytes(delta)
        if len(delta_bytes) > MAX_DELTA_BYTES:
            raise SyndicationError("delta exceeds the 16 MiB limit")
        digest = sha256_bytes(delta_bytes)
        delta_path = output_dir / "deltas" / (digest + ".json")
        delta_created = _write_immutable(delta_path, delta_bytes)
        history.append(
            _delta_entry(
                delta,
                digest,
                delta_bytes,
                base_url,
            )
        )

    head = None
    if history:
        latest = history[-1]
        head = {
            "path": latest["path"],
            "sequence": latest["sequence"],
            "sha256": latest["sha256"],
            "url": latest["url"],
        }
    updated = history[-1]["created_at"] if history else created_at
    snapshot = {
        "apps": current_apps,
        "checkpoint": {
            "delta_sha256": head["sha256"] if head else None,
            "next_frame_challenge_seed": (
                history[-1]["block"]["next_frame_challenge_seed"]
                if history
                else None
            ),
            "since_seq": head["sequence"] if head else -1,
        },
        "challenge_state_machine": CHALLENGE_STATE_MACHINE,
        "counts": {
            "active_apps": len(current_apps),
            "attention_data_objects": len(current_data),
            "data_tombstones": len(data_tombstone_map),
            "frames": len(current_frames),
            "tombstones": len(app_tombstone_map),
        },
        "data_objects": current_data,
        "data_tombstones": [
            data_tombstone_map[path]
            for path in sorted(data_tombstone_map)
        ],
        "frames": current_frames,
        "frame_control_schema": FRAME_CONTROL_SCHEMA,
        "head": head,
        "pinning": PINNING_POLICY,
        "profile": PROFILE,
        "rate_budget": RATE_BUDGET,
        "rollout": SOAK_ROLLOUT,
        "schema": SNAPSHOT_SCHEMA,
        "stream_id": STREAM_ID,
        "tombstones": [
            app_tombstone_map[path]
            for path in sorted(app_tombstone_map)
        ],
        "transparency": TRANSPARENCY_MODEL,
        "updated": updated,
    }
    snapshot_bytes = stable_json_bytes(snapshot)
    snapshot_digest = sha256_bytes(snapshot_bytes)
    snapshot_entry = {
        "path": "snapshot.json",
        "sha256": snapshot_digest,
        "size": len(snapshot_bytes),
        "url": _app_url(base_url, "apps/syndication/snapshot.json"),
    }
    index = {
        "atom": {
            "path": "feed.xml",
            "url": _app_url(base_url, "apps/syndication/feed.xml"),
        },
        "capabilities": CAPABILITIES,
        "challenge_state_machine": CHALLENGE_STATE_MACHINE,
        "cursor": {
            "head_seq": head["sequence"] if head else -1,
            "initial_since_seq": -1,
            "kind": "immutable-since-seq",
            "reset_policy": "reject",
        },
        "delta_count": len(history),
        "deltas": history,
        "frame_control_schema": FRAME_CONTROL_SCHEMA,
        "head": head,
        "json_feed": {
            "path": "feed.json",
            "url": _app_url(base_url, "apps/syndication/feed.json"),
            "version": "https://jsonfeed.org/version/1.1",
        },
        "next_frame_challenge_seed": (
            history[-1]["block"]["next_frame_challenge_seed"]
            if history
            else None
        ),
        "pinning": PINNING_POLICY,
        "profile": PROFILE,
        "rate_budget": RATE_BUDGET,
        "rollout": SOAK_ROLLOUT,
        "schema": INDEX_SCHEMA,
        "snapshot": snapshot_entry,
        "stream_id": STREAM_ID,
        "transparency": TRANSPARENCY_MODEL,
        "updated": updated,
    }
    index_bytes = stable_json_bytes(index)
    atom_bytes = build_atom(history, base_url, updated)
    json_feed_bytes = build_json_feed(history, base_url)

    written = {
        "snapshot": _write_if_changed(snapshot_path, snapshot_bytes),
        "index": _write_if_changed(output_dir / "index.json", index_bytes),
        "feed_xml": _write_if_changed(
            output_dir / "feed.xml",
            atom_bytes,
        ),
        "feed_json": _write_if_changed(
            output_dir / "feed.json",
            json_feed_bytes,
        ),
    }
    legacy_atom = output_dir / "atom.xml"
    if legacy_atom.exists():
        legacy_atom.unlink()
    return {
        "active_apps": len(current_apps),
        "attention_data_objects": len(current_data),
        "delta_created": delta_created,
        "delta_count": len(history),
        "frames": len(current_frames),
        "head": head["sha256"] if head else None,
        "tombstones": len(app_tombstone_map) + len(data_tombstone_map),
        "written": written,
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build immutable RappterZoo syndicated deltas",
    )
    parser.add_argument(
        "--root",
        default=str(ROOT),
        help="repository root (default: inferred)",
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help="public repository base URL",
    )
    args = parser.parse_args(argv)
    try:
        result = build(Path(args.root), args.base_url)
    except (OSError, SyndicationError) as error:
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

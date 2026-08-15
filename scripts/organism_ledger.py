#!/usr/bin/env python3
"""Append-only RAPP/1-shaped organism frames for RappterZoo.

The ledger is public metadata only. It deliberately makes no authenticated
RAPP/1 acceptance claim because this repository does not carry a signed
Section 13 registry or a signing key for the swarm stream.
"""

import argparse
import errno
import hashlib
import json
import math
import os
import re
import socket
import subprocess
import sys
import time
import unicodedata
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


ROOT = Path(__file__).resolve().parent.parent
APPS_DIR = ROOT / "apps"
LEDGER_PATH = APPS_DIR / "organism-frames.jsonl"
PROJECTION_PATH = APPS_DIR / "organism-frames.json"
STATE_PATH = APPS_DIR / "molter-state.json"

STREAM_ID = "net:rappterzoo"
PARTICLE_SPACE = "rapp/1:particle"
WAVE_SPACE = "rapp/1:wave"
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
KIND_RE = re.compile(
    r"^[a-z0-9]+(?:-[a-z0-9]+)*\.[a-z0-9]+(?:-[a-z0-9]+)*$"
)
HASH_RE = re.compile(r"^[0-9a-f]{64}$")
UTC_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")
MAX_SAFE_INTEGER = (1 << 53) - 1
MAX_CANONICAL_BYTES = 1024 * 1024
PROJECTION_LIMIT = 1000
LOCK_STALE_SECONDS = 15 * 60
PUBLIC_VISIBILITY = "public-metadata"
PAYLOAD_SCHEMA = "rappterzoo-organism-frame/1"
SAFE_FALSE_PUBLIC_POLICY_KEYS = {
    "privatemediainpublicledger",
    "pulsepersisted",
}
SUBSCRIBER_CHECKPOINT_SCHEMA = "rappterzoo-subscriber-checkpoint/1"
SUBSCRIBER_WITNESS_SCHEMA = "rappterzoo-subscriber-witness/1"
SUBSCRIBER_FORK_SCHEMA = "rappterzoo-subscriber-fork-evidence/1"
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
    "godd",
    "identitytemplate",
    "landmarks",
    "media",
    "password",
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
}
FORBIDDEN_PUBLIC_KEY_PREFIX_TOKENS = (
    FORBIDDEN_PUBLIC_KEY_TOKENS - {"media"}
)
FORBIDDEN_PUBLIC_KEY_COMPONENT_TOKENS = (
    FORBIDDEN_PUBLIC_KEY_TOKENS - {
        "media",
        "rawmedia",
        "facelandmarks",
        "identitytemplate",
        "pulsebpm",
        "pulsebpmestimate",
    }
)


class LedgerError(ValueError):
    pass


class ForkError(LedgerError):
    def __init__(self, message: str, evidence: Dict[str, Any]):
        super().__init__(message)
        self.evidence = evidence


def normalize_utc(value: Optional[str] = None) -> str:
    if value is None:
        moment = datetime.now(timezone.utc)
    else:
        text = str(value).strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            moment = datetime.fromisoformat(text)
        except ValueError as error:
            raise LedgerError("timestamp is not ISO-8601") from error
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        moment = moment.astimezone(timezone.utc)
    return moment.strftime("%Y-%m-%dT%H:%M:%S.%f")[:23] + "Z"


def _normalize_json(value: Any, depth: int = 1) -> Any:
    if depth > 64:
        raise LedgerError("JSON nesting exceeds 64 levels")
    if value is None or type(value) is bool:
        return value
    if type(value) is int:
        if not -MAX_SAFE_INTEGER <= value <= MAX_SAFE_INTEGER:
            raise LedgerError("integer exceeds the RAPP/1 I-JSON safe range")
        return value
    if type(value) is float:
        raise LedgerError(
            "binary64 numbers are outside the restricted canonical profile"
        )
    if type(value) is str:
        if unicodedata.normalize("NFC", value) != value:
            raise LedgerError("strings must already be NFC-normalized")
        if any(0xD800 <= ord(character) <= 0xDFFF for character in value):
            raise LedgerError("lone UTF-16 surrogates are forbidden")
        return value
    if isinstance(value, (list, tuple)):
        return [
            _normalize_json(item, depth + 1)
            for item in value
        ]
    if type(value) is dict:
        result = {}
        for key, item in value.items():
            if type(key) is not str:
                raise LedgerError("JSON object keys must be strings")
            try:
                key.encode("ascii")
            except UnicodeEncodeError as error:
                raise LedgerError(
                    "restricted canonical profile requires ASCII object keys"
                ) from error
            if unicodedata.normalize("NFC", key) != key:
                raise LedgerError("JSON object keys must be NFC-normalized")
            result[key] = _normalize_json(item, depth + 1)
        return result
    raise LedgerError(
        "unsupported JSON value: {}".format(type(value).__name__)
    )


def canonical_bytes(value: Any) -> bytes:
    """Canonical bytes for the restricted RAPP/1 payload profile.

    This is deliberately only an RFC 8785-compatible subset: ASCII object
    keys, NFC strings, I-JSON safe integers, booleans, null, arrays, and
    objects. Binary64 values are rejected rather than serialized with a
    Python-specific approximation of ECMAScript number formatting.
    """

    normalized = _normalize_json(value)
    encoded = json.dumps(
        normalized,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    if len(encoded) > MAX_CANONICAL_BYTES:
        raise LedgerError("canonical value exceeds one MiB")
    return encoded


def hash_value(space: str, value: Any) -> str:
    if space not in {PARTICLE_SPACE, WAVE_SPACE}:
        raise LedgerError("unsupported RAPP/1 hash domain")
    return hashlib.sha256(
        space.encode("ascii") + b"\n" + canonical_bytes(value)
    ).hexdigest()


def _snapshot_json(value: Any, depth: int = 1) -> Any:
    """Convert runtime observations into the ledger's stable JSON subset."""
    if depth > 64:
        raise LedgerError("JSON nesting exceeds 64 levels")
    if type(value) is float:
        if not math.isfinite(value):
            raise LedgerError("non-finite number is forbidden")
        return format(value, ".15g")
    if isinstance(value, (list, tuple)):
        return [_snapshot_json(item, depth + 1) for item in value]
    if type(value) is dict:
        return {
            key: _snapshot_json(item, depth + 1)
            for key, item in value.items()
        }
    return _normalize_json(value, depth)


def _privacy_key_token(key: str) -> str:
    return "".join(character.lower() for character in key if character.isalnum())


def _privacy_key_components(key: str) -> List[str]:
    separated = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", key)
    return [
        component.lower()
        for component in re.findall(r"[A-Za-z0-9]+", separated)
        if component
    ]


def _is_forbidden_public_key(key: str, value: Any) -> bool:
    token = _privacy_key_token(key)
    if value is False and token in SAFE_FALSE_PUBLIC_POLICY_KEYS:
        return False
    components = _privacy_key_components(key)
    if token in FORBIDDEN_PUBLIC_KEY_TOKENS:
        return True
    if any(
        token.startswith(forbidden)
        for forbidden in FORBIDDEN_PUBLIC_KEY_PREFIX_TOKENS
    ):
        return True
    return any(
        component in FORBIDDEN_PUBLIC_KEY_COMPONENT_TOKENS
        for component in components
    )


def _find_forbidden_key(value: Any) -> Optional[str]:
    if type(value) is dict:
        for key, item in value.items():
            if _is_forbidden_public_key(key, item):
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


def _require_public_hash(payload: Dict[str, Any], key: str) -> None:
    value = payload.get(key)
    if type(value) is not str or not HASH_RE.fullmatch(value):
        raise LedgerError("payload {} must be a SHA-256 digest".format(key))


def _require_public_ids(payload: Dict[str, Any], key: str) -> List[str]:
    values = payload.get(key)
    if type(values) is not list:
        raise LedgerError("payload {} must be an array".format(key))
    if any(type(value) is not str or not value for value in values):
        raise LedgerError(
            "payload {} must contain non-empty strings".format(key)
        )
    if len(values) != len(set(values)):
        raise LedgerError("payload {} contains duplicates".format(key))
    return values


def _validate_attention_payload(payload: Dict[str, Any]) -> None:
    event = payload.get("event")
    if event == "attention-evaluation":
        for key in (
            "base_frame_hash",
            "base_record_hash",
            "endpoint_identity_digest",
            "group_object_digest",
            "input_digest",
            "policy_digest",
            "prompt_digest",
            "provenance_digest",
            "request_digest",
            "scope_digest",
        ):
            _require_public_hash(payload, key)
        for key in (
            "evaluation_axis",
            "group_id",
            "group_object_path",
            "scope_key",
            "shard_id",
        ):
            if type(payload.get(key)) is not str or not payload[key]:
                raise LedgerError(
                    "attention payload requires {}".format(key)
                )
        selected_ids = _require_public_ids(
            payload,
            "selected_record_ids",
        )
        candidate_ids = _require_public_ids(
            payload,
            "candidate_record_ids",
        )
        for key in (
            "attention_budget",
            "candidate_budget",
            "candidate_count",
            "selected_count",
            "total_group_count",
        ):
            value = payload.get(key)
            if (
                type(value) is not int
                or value < 0
                or value > MAX_SAFE_INTEGER
            ):
                raise LedgerError(
                    "attention payload {} is invalid".format(key)
                )
        if payload["selected_count"] != len(selected_ids):
            raise LedgerError("attention selected_count does not match IDs")
        if payload["candidate_count"] != len(candidate_ids):
            raise LedgerError("attention candidate_count does not match IDs")
        if payload["selected_count"] > payload["attention_budget"]:
            raise LedgerError("attention selection exceeds its budget")
        if payload["attention_budget"] > payload["candidate_count"]:
            raise LedgerError("attention budget exceeds candidate count")
        if payload["candidate_count"] > payload["candidate_budget"]:
            raise LedgerError("attention candidates exceed candidate budget")
        if payload["candidate_count"] > payload["total_group_count"]:
            raise LedgerError("attention candidates exceed total group")
        if not set(selected_ids).issubset(set(candidate_ids)):
            raise LedgerError(
                "attention selection contains a non-candidate record"
            )
        if payload.get("event_id") != "attention-evaluation:{}".format(
            payload["request_digest"]
        ):
            raise LedgerError("attention event_id does not match request_digest")
        if payload["group_object_path"] != (
            "attention/groups/{}.json".format(
                payload["group_object_digest"]
            )
        ):
            raise LedgerError(
                "attention group path does not match its digest"
            )
    elif event == "dimension-reconciliation":
        for key in ("base_record_hash", "dimension_object_digest"):
            _require_public_hash(payload, key)
        for key in (
            "base_frame_hashes",
            "branch_group_digests",
            "endpoint_identity_digests",
            "scope_digests",
        ):
            values = _require_public_ids(payload, key)
            for value in values:
                if not HASH_RE.fullmatch(value):
                    raise LedgerError(
                        "dimension {} contains a non-digest".format(key)
                    )
        for key in (
            "shard_ids",
            "evaluation_axes",
            "drift_classification",
        ):
            _require_public_ids(payload, key)
        for key in (
            "comparison_count",
            "collision_count",
            "collision_rate_ppm",
        ):
            value = payload.get(key)
            if (
                type(value) is not int
                or value < 0
                or value > MAX_SAFE_INTEGER
            ):
                raise LedgerError(
                    "dimension {} is invalid".format(key)
                )
        if payload.get("rarity_gate") not in {
            "bootstrap",
            "rare-pass",
            "frequency-breach",
        }:
            raise LedgerError("dimension rarity_gate is invalid")
        if payload.get("dimension_object_path") != (
            "attention/dimensions/{}.json".format(
                payload["dimension_object_digest"]
            )
        ):
            raise LedgerError("dimension object path mismatch")
        if payload.get("event_id") != "attention-dimension:{}".format(
            payload["dimension_object_digest"]
        ):
            raise LedgerError("dimension event_id does not match object")
    elif event == "fold-challenge":
        for key in (
            "challenge_digest",
            "base_head_hash",
            "frame_control_config_digest",
        ):
            _require_public_hash(payload, key)
        for key in ("shard_id", "channel", "action_kind"):
            if type(payload.get(key)) is not str or not payload[key]:
                raise LedgerError("fold challenge requires {}".format(key))
        for key in (
            "base_head_seq",
            "epoch",
            "control_frame",
            "difficulty_bits",
            "max_work_iterations",
        ):
            if type(payload.get(key)) is not int or payload[key] < -1:
                raise LedgerError("fold challenge {} is invalid".format(key))
        if (
            payload.get("control_model")
            != "application-frame-control-election"
            or payload.get("consensus_model") != "none"
            or payload.get("economic_model") != "none"
        ):
            raise LedgerError("fold challenge overstates control authority")
        if payload.get("execution_mode") not in {
            "synthetic-test",
            "active-owner-authorized",
        }:
            raise LedgerError("fold challenge execution mode is invalid")
        if payload.get("event_id") != "fold-challenge:{}".format(
            payload["challenge_digest"]
        ):
            raise LedgerError("fold challenge event_id mismatch")
    elif event == "fold-control-award":
        for key in (
            "award_digest",
            "challenge_digest",
            "winner_participant_object_digest",
            "winner_proof_hash",
            "base_head_hash",
            "frame_control_config_digest",
        ):
            _require_public_hash(payload, key)
        if (
            payload.get("control_model")
            != "application-frame-control-election"
            or payload.get("consensus_model") != "none"
            or payload.get("economic_model") != "none"
        ):
            raise LedgerError("fold award overstates control authority")
        if payload.get("execution_mode") not in {
            "synthetic-test",
            "active-owner-authorized",
        }:
            raise LedgerError("fold award execution mode is invalid")
        if payload.get("event_id") != "fold-award:{}".format(
            payload["award_digest"]
        ):
            raise LedgerError("fold award event_id mismatch")
    elif event == "fold-control-expiry":
        for key in (
            "expiry_digest",
            "challenge_digest",
            "base_head_hash",
            "frame_control_config_digest",
        ):
            _require_public_hash(payload, key)
        if (
            payload.get("control_model")
            != "application-frame-control-election"
            or payload.get("consensus_model") != "none"
            or payload.get("economic_model") != "none"
        ):
            raise LedgerError("fold expiry overstates control authority")
        if payload.get("execution_mode") not in {
            "synthetic-test",
            "active-owner-authorized",
        }:
            raise LedgerError("fold expiry execution mode is invalid")
        if payload.get("event_id") != "fold-expiry:{}".format(
            payload["expiry_digest"]
        ):
            raise LedgerError("fold expiry event_id mismatch")
    elif event == "fold-control-action":
        for key in (
            "award_digest",
            "challenge_digest",
            "winner_participant_object_digest",
            "winner_proof_hash",
            "accepted_result_frame_hash",
            "group_object_digest",
            "frame_control_config_digest",
        ):
            _require_public_hash(payload, key)
        if (
            payload.get("control_model")
            != "application-frame-control-election"
            or payload.get("consensus_model") != "none"
            or payload.get("economic_model") != "none"
        ):
            raise LedgerError("fold action overstates control authority")
        if payload.get("execution_mode") not in {
            "synthetic-test",
            "active-owner-authorized",
        }:
            raise LedgerError("fold action execution mode is invalid")
        if payload.get("event_id") != "fold-action:{}".format(
            payload["award_digest"]
        ):
            raise LedgerError("fold action event_id mismatch")
    elif event == "assigned-control-action":
        for key in (
            "lease_digest",
            "candidate_result_digest",
            "participant_object_digest",
            "accepted_result_frame_hash",
            "group_object_digest",
        ):
            _require_public_hash(payload, key)
        if (
            payload.get("control_model")
            != "application-assigned-shard-control"
            or payload.get("consensus_model") != "none"
            or payload.get("economic_model") != "none"
        ):
            raise LedgerError("assigned action overstates control authority")
        if payload.get("event_id") != "assigned-action:{}".format(
            payload["candidate_result_digest"]
        ):
            raise LedgerError("assigned action event_id mismatch")
    elif event in {"mutation-receipt", "delta-receipt"}:
        expected_run_kind = (
            "mutation" if event == "mutation-receipt" else "delta"
        )
        if payload.get("run_kind") != expected_run_kind:
            raise LedgerError("receipt event and run_kind disagree")
        for key in (
            "attention_frame_hash",
            "base_frame_hash",
            "base_record_hash",
            "endpoint_identity_digest",
            "group_object_digest",
            "mutation_prompt_digest",
            "output_digest",
            "receipt_object_digest",
            "scope_digest",
        ):
            _require_public_hash(payload, key)
        for key in (
            "evaluation_axis",
            "group_id",
            "mutation_id",
            "receipt_object_path",
            "shard_id",
        ):
            if type(payload.get(key)) is not str or not payload[key]:
                raise LedgerError("receipt payload requires {}".format(key))
        attention_seq = payload.get("attention_frame_seq")
        if (
            type(attention_seq) is not int
            or attention_seq < 0
            or attention_seq > MAX_SAFE_INTEGER
        ):
            raise LedgerError("receipt attention_frame_seq is invalid")
        if type(payload.get("output_media_type")) is not str:
            raise LedgerError("receipt output_media_type must be a string")
        consumed = _require_public_ids(payload, "consumed_record_ids")
        if not consumed:
            raise LedgerError("receipt must consume at least one selected record")
        if payload.get("event_id") != "attention-{}:{}".format(
            payload["run_kind"],
            payload["mutation_id"],
        ):
            raise LedgerError("receipt event_id does not match mutation lineage")
        if payload["receipt_object_path"] != (
            "attention/receipts/{}.json".format(
                payload["receipt_object_digest"]
            )
        ):
            raise LedgerError(
                "receipt object path does not match its digest"
            )
        dimension_mode = payload.get("dimension_mode")
        dimension_digest = payload.get("dimension_object_digest")
        branch_digests = payload.get("dimension_branch_group_digests")
        if (
            type(branch_digests) is not list
            or len(branch_digests) != len(set(branch_digests))
        ):
            raise LedgerError("receipt dimension branches are invalid")
        for digest in branch_digests:
            if type(digest) is not str or not HASH_RE.fullmatch(digest):
                raise LedgerError(
                    "receipt dimension branch is not a digest"
                )
        if dimension_mode == "none":
            if dimension_digest is not None or branch_digests:
                raise LedgerError("receipt none dimension carries branches")
        elif dimension_mode in {"chosen", "carry-both"}:
            if (
                type(dimension_digest) is not str
                or not HASH_RE.fullmatch(dimension_digest)
                or len(branch_digests) < 2
            ):
                raise LedgerError("receipt dimension lineage is invalid")
        else:
            raise LedgerError("receipt dimension_mode is invalid")


def _validate_kind_event(kind: str, payload: Dict[str, Any]) -> None:
    event = payload.get("event")
    expected = {
        "attention-evaluation": "zoo.attention",
        "dimension-reconciliation": "zoo.dimension",
        "fold-challenge": "zoo.challenge",
        "fold-control-award": "zoo.control-award",
        "fold-control-expiry": "zoo.control-expiry",
        "fold-control-action": "zoo.control-action",
        "assigned-control-action": "zoo.control-action",
        "mutation-receipt": "zoo.mutation",
        "delta-receipt": "zoo.delta",
    }.get(event)
    if expected is not None and kind != expected:
        raise LedgerError(
            "{} events require kind {}".format(event, expected)
        )


def validate_public_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    normalized = _normalize_json(payload)
    if type(normalized) is not dict:
        raise LedgerError("payload must be a JSON object")
    if normalized.get("schema") != PAYLOAD_SCHEMA:
        raise LedgerError("payload has the wrong schema")
    if normalized.get("visibility") != PUBLIC_VISIBILITY:
        raise LedgerError(
            "the public ledger accepts only public-metadata frames"
        )
    forbidden = _find_forbidden_key(normalized)
    if forbidden:
        raise LedgerError(
            "public frame contains forbidden key: {}".format(forbidden)
        )
    event_id = normalized.get("event_id")
    if type(event_id) is not str or not event_id:
        raise LedgerError("payload requires a non-empty event_id")
    for required in ("event", "organism"):
        value = normalized.get(required)
        if type(value) is not str or not value:
            raise LedgerError(
                "payload requires a non-empty {}".format(required)
            )
    for optional in (
        "display_name",
        "kennel",
        "neighborhood",
        "organism_type",
    ):
        if optional in normalized and type(normalized[optional]) is not str:
            raise LedgerError(
                "payload {} must be a string".format(optional)
            )
    _validate_attention_payload(normalized)
    return normalized


def build_frame(
    kind: str,
    stream_id: str,
    seq: int,
    utc: str,
    payload: Dict[str, Any],
    prev: Optional[str],
    prev_wave: Optional[str],
    sig: Optional[str] = None,
) -> Dict[str, Any]:
    if type(kind) is not str or not KIND_RE.fullmatch(kind):
        raise LedgerError("kind does not match the RAPP/1 label form")
    if stream_id != STREAM_ID:
        raise LedgerError("this ledger accepts only net:rappterzoo")
    if (
        type(seq) is not int
        or seq < 0
        or seq > MAX_SAFE_INTEGER
    ):
        raise LedgerError("sequence must be an I-JSON safe non-negative integer")
    if sig is not None:
        raise LedgerError(
            "unsigned public frames require sig:null; acceptance is unverified"
        )
    if seq == 0:
        if prev is not None or prev_wave is not None:
            raise LedgerError("genesis links must be null")
    else:
        if (
            type(prev) is not str
            or not HASH_RE.fullmatch(prev)
            or type(prev_wave) is not str
            or not HASH_RE.fullmatch(prev_wave)
        ):
            raise LedgerError("non-genesis frames require hash links")
    normalized_payload = validate_public_payload(payload)
    _validate_kind_event(kind, normalized_payload)
    normalized_utc = normalize_utc(utc)
    frame = {
        "spec": "rapp/1",
        "kind": kind,
        "stream_id": stream_id,
        "seq": seq,
        "utc": normalized_utc,
        "payload": normalized_payload,
        "payload_hash": hash_value(PARTICLE_SPACE, normalized_payload),
        "frame_hash": "0" * 64,
        "prev": prev,
        "prev_wave": prev_wave,
        "sig": sig,
    }
    wave_preimage = {
        key: value
        for key, value in frame.items()
        if key not in {"frame_hash", "sig"}
    }
    frame["frame_hash"] = hash_value(WAVE_SPACE, wave_preimage)
    return frame


def _json_object(pairs: List[Tuple[str, Any]]) -> Dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise LedgerError("duplicate JSON object key: {}".format(key))
        result[key] = value
    return result


def _invalid_json_constant(value: str) -> None:
    raise LedgerError("non-finite JSON number is forbidden: {}".format(value))


def _read_frame_bytes(data: bytes) -> List[Dict[str, Any]]:
    if not data:
        return []
    if not data.endswith(b"\n"):
        raise LedgerError("ledger does not end on a complete frame boundary")
    frames = []
    for line_number, line in enumerate(data.split(b"\n")[:-1], 1):
        if not line:
            raise LedgerError("blank ledger line at {}".format(line_number))
        if len(line) > MAX_CANONICAL_BYTES:
            raise LedgerError(
                "ledger frame exceeds one MiB at line {}".format(line_number)
            )
        try:
            frame = json.loads(
                line.decode("utf-8"),
                object_pairs_hook=_json_object,
                parse_constant=_invalid_json_constant,
            )
        except LedgerError:
            raise
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise LedgerError(
                "invalid ledger JSON at line {}".format(line_number)
            ) from error
        if canonical_bytes(frame) != line:
            raise LedgerError(
                "non-canonical ledger frame at line {}".format(line_number)
            )
        frames.append(frame)
    verify_frames(frames)
    return frames


def read_frames(path: Path = LEDGER_PATH) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    return _read_frame_bytes(path.read_bytes())


def verify_frames(frames: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    materialized = list(frames)
    previous = None
    previous_molter_frame = None
    seen_event_ids = set()
    for index, frame in enumerate(materialized):
        if type(frame) is not dict or set(frame) != FRAME_KEYS:
            raise LedgerError(
                "frame {} does not have exactly eleven keys".format(index)
            )
        if frame["spec"] != "rapp/1":
            raise LedgerError("frame {} has the wrong spec".format(index))
        if frame["stream_id"] != STREAM_ID:
            raise LedgerError("frame {} has the wrong stream".format(index))
        if (
            type(frame["kind"]) is not str
            or not KIND_RE.fullmatch(frame["kind"])
        ):
            raise LedgerError("frame {} has an invalid kind".format(index))
        if (
            type(frame["seq"]) is not int
            or frame["seq"] != index
            or frame["seq"] > MAX_SAFE_INTEGER
        ):
            raise LedgerError("frame {} is not contiguous".format(index))
        if (
            type(frame["utc"]) is not str
            or not UTC_RE.fullmatch(frame["utc"])
        ):
            raise LedgerError("frame {} has an invalid UTC value".format(index))
        try:
            if normalize_utc(frame["utc"]) != frame["utc"]:
                raise LedgerError(
                    "frame {} UTC is not normalized".format(index)
                )
        except LedgerError as error:
            raise LedgerError(
                "frame {} has an invalid UTC value".format(index)
            ) from error
        if type(frame["payload"]) is not dict:
            raise LedgerError("frame {} payload is not an object".format(index))
        validate_public_payload(frame["payload"])
        _validate_kind_event(frame["kind"], frame["payload"])
        if (
            type(frame["payload_hash"]) is not str
            or not HASH_RE.fullmatch(frame["payload_hash"])
        ):
            raise LedgerError("frame {} has an invalid payload hash".format(index))
        if (
            type(frame["frame_hash"]) is not str
            or not HASH_RE.fullmatch(frame["frame_hash"])
        ):
            raise LedgerError("frame {} has an invalid frame hash".format(index))
        if frame["sig"] is not None:
            raise LedgerError(
                "frame {} must keep sig:null for structural-unverified data".format(
                    index
                )
            )
        expected_payload_hash = hash_value(
            PARTICLE_SPACE,
            frame["payload"],
        )
        if frame["payload_hash"] != expected_payload_hash:
            raise LedgerError(
                "frame {} payload hash mismatch".format(index)
            )
        wave_preimage = {
            key: value
            for key, value in frame.items()
            if key not in {"frame_hash", "sig"}
        }
        expected_frame_hash = hash_value(WAVE_SPACE, wave_preimage)
        if frame["frame_hash"] != expected_frame_hash:
            raise LedgerError("frame {} frame hash mismatch".format(index))
        if previous is None:
            if frame["prev"] is not None or frame["prev_wave"] is not None:
                raise LedgerError("genesis links must be null")
        else:
            if frame["utc"] < previous["utc"]:
                raise LedgerError("frame timestamps must be monotonic")
            if frame["prev"] != previous["payload_hash"]:
                raise LedgerError("payload chain is broken")
            if frame["prev_wave"] != previous["frame_hash"]:
                raise LedgerError("wave chain is broken")
        event_id = frame["payload"].get("event_id")
        if type(event_id) is not str or not event_id:
            raise LedgerError("every payload requires an event_id")
        if event_id in seen_event_ids:
            raise LedgerError("duplicate event_id: {}".format(event_id))
        seen_event_ids.add(event_id)
        if frame["payload"].get("event") == "autonomous-frame":
            molter_frame = frame["payload"].get("molter_frame")
            if (
                type(molter_frame) is not int
                or molter_frame < 0
                or molter_frame > MAX_SAFE_INTEGER
                or event_id != "molter-frame:{}".format(molter_frame)
            ):
                raise LedgerError(
                    "autonomous frame has inconsistent event ordering metadata"
                )
            if (
                previous_molter_frame is not None
                and molter_frame <= previous_molter_frame
            ):
                raise LedgerError(
                    "autonomous molter frames must be strictly increasing"
                )
            previous_molter_frame = molter_frame
        previous = frame
    return {
        "valid": True,
        "frame_count": len(materialized),
        "head": (
            {
                "seq": materialized[-1]["seq"],
                "payload_hash": materialized[-1]["payload_hash"],
                "frame_hash": materialized[-1]["frame_hash"],
            }
            if materialized
            else None
        ),
    }


def verify_append_only_bytes(previous: bytes, current: bytes) -> Dict[str, Any]:
    if previous and not previous.endswith(b"\n"):
        raise LedgerError("previous ledger does not end on a frame boundary")
    if not current.startswith(previous):
        raise LedgerError("current ledger does not preserve the prior byte prefix")
    if current and not current.endswith(b"\n"):
        raise LedgerError("current ledger does not end on a frame boundary")
    return {
        "valid": True,
        "previous_bytes": len(previous),
        "current_bytes": len(current),
        "appended_bytes": len(current) - len(previous),
    }


def verify_git_append_only(
    base_ref: str,
    root: Path = ROOT,
    ledger_path: Path = LEDGER_PATH,
) -> Dict[str, Any]:
    relative = ledger_path.relative_to(root)
    resolved = subprocess.run(
        ["git", "rev-parse", "--verify", "{}^{{commit}}".format(base_ref)],
        cwd=str(root),
        capture_output=True,
        check=False,
    )
    if resolved.returncode != 0:
        raise LedgerError("git base ref is unavailable: {}".format(base_ref))
    result = subprocess.run(
        ["git", "show", "{}:{}".format(base_ref, relative)],
        cwd=str(root),
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return {
            "valid": True,
            "checked": False,
            "reason": "base ref has no organism ledger",
            "base_ref": base_ref,
        }
    current = ledger_path.read_bytes() if ledger_path.exists() else b""
    base_frames = _read_frame_bytes(result.stdout)
    current_frames = _read_frame_bytes(current)
    prefix = verify_append_only_bytes(result.stdout, current)
    return {
        **prefix,
        "checked": True,
        "base_ref": base_ref,
        "base_frame_count": len(base_frames),
        "current_frame_count": len(current_frames),
    }


def _fsync_directory(path: Path) -> None:
    try:
        descriptor = os.open(str(path), os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)


def _pid_is_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError as error:
        if error.errno == errno.ESRCH:
            return False
        if error.errno == errno.EPERM:
            return True
        raise
    return True


def _stale_lock_snapshot(lock_path: Path) -> Optional[Tuple[int, int, int]]:
    try:
        stat = lock_path.stat()
        data = lock_path.read_bytes()
    except FileNotFoundError:
        return None
    snapshot = (stat.st_ino, stat.st_size, stat.st_mtime_ns)
    age = max(0.0, time.time() - stat.st_mtime)
    try:
        record = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return snapshot if age >= LOCK_STALE_SECONDS else None
    if type(record) is not dict:
        return snapshot if age >= LOCK_STALE_SECONDS else None
    pid = record.get("pid")
    hostname = record.get("hostname")
    if type(pid) is not int or type(hostname) is not str:
        return snapshot if age >= LOCK_STALE_SECONDS else None
    if hostname != socket.gethostname():
        return snapshot if age >= LOCK_STALE_SECONDS else None
    if _pid_is_alive(pid):
        return None
    return snapshot


def _remove_stale_lock(
    lock_path: Path,
    snapshot: Tuple[int, int, int],
) -> bool:
    try:
        stat = lock_path.stat()
    except FileNotFoundError:
        return True
    current = (stat.st_ino, stat.st_size, stat.st_mtime_ns)
    if current != snapshot:
        return False
    try:
        lock_path.unlink()
    except FileNotFoundError:
        return True
    _fsync_directory(lock_path.parent)
    return True


@contextmanager
def _ledger_lock(path: Path):
    lock_path = path.with_name(path.name + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = None
    token = uuid.uuid4().hex
    while descriptor is None:
        try:
            descriptor = os.open(
                str(lock_path),
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                0o600,
            )
        except FileExistsError as error:
            stale = _stale_lock_snapshot(lock_path)
            if stale is not None and _remove_stale_lock(lock_path, stale):
                continue
            raise LedgerError(
                "organism ledger is already locked: {}".format(lock_path)
            ) from error
    inode = os.fstat(descriptor).st_ino
    record = {
        "created_utc": normalize_utc(),
        "hostname": socket.gethostname(),
        "pid": os.getpid(),
        "token": token,
        "version": 1,
    }
    try:
        data = canonical_bytes(record)
        written = os.write(descriptor, data)
        if written != len(data):
            raise LedgerError("could not persist the complete ledger lock")
        os.fsync(descriptor)
        _fsync_directory(lock_path.parent)
        yield
    finally:
        os.close(descriptor)
        try:
            stat = lock_path.stat()
            current = json.loads(lock_path.read_text(encoding="utf-8"))
            if (
                stat.st_ino == inode
                and type(current) is dict
                and current.get("token") == token
            ):
                lock_path.unlink()
                _fsync_directory(lock_path.parent)
        except (FileNotFoundError, UnicodeDecodeError, ValueError):
            pass


def _pretty_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def _atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(
        "{}.tmp.{}.{}".format(path.name, os.getpid(), uuid.uuid4().hex)
    )
    try:
        with temporary.open("wb") as handle:
            handle.write(_pretty_json_bytes(value))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(str(temporary), str(path))
        _fsync_directory(path.parent)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _write_immutable_json(path: Path, value: Any) -> bool:
    canonical_bytes(value)
    encoded = _pretty_json_bytes(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != encoded:
            raise LedgerError(
                "immutable object exists with different bytes: {}".format(path)
            )
        return False
    temporary = path.with_name(
        "{}.tmp.{}.{}".format(path.name, os.getpid(), uuid.uuid4().hex)
    )
    try:
        with temporary.open("wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(str(temporary), str(path))
        except FileExistsError:
            if path.read_bytes() != encoded:
                raise LedgerError(
                    "immutable object raced with different bytes: {}".format(
                        path
                    )
                )
            return False
        _fsync_directory(path.parent)
        return True
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def subscriber_chain_claims() -> Dict[str, str]:
    return {
        "chain_model": (
            "git-backed-content-addressed-append-only-transparency-chain"
        ),
        "blockchain_style": "hash-chain-analogy-only",
        "single_subscriber": "one-independent-local-replica",
        "multiple_subscribers": (
            "independent-custody-and-verification-if-separately-controlled"
        ),
        "publisher_authority": "centralized",
        "witness_quorum": "not-established",
        "consensus": "none",
        "mining": "none",
        "token": "none",
    }


def _subscriber_digest(domain: str, value: Dict[str, Any], key: str) -> str:
    return hashlib.sha256(
        domain.encode("ascii")
        + b"\n"
        + canonical_bytes({
            item_key: item_value
            for item_key, item_value in value.items()
            if item_key != key
        })
    ).hexdigest()


def _subscriber_head(frames: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not frames:
        return None
    return {
        "seq": frames[-1]["seq"],
        "payload_hash": frames[-1]["payload_hash"],
        "frame_hash": frames[-1]["frame_hash"],
    }


def _verify_subscriber_checkpoint(value: Any) -> Dict[str, Any]:
    keys = {
        "schema",
        "checkpoint_digest",
        "subscriber_id_digest",
        "stream_id",
        "frame_count",
        "byte_count",
        "head",
        "ledger_sha256",
        "previous_checkpoint_digest",
        "previous_frame_count",
        "previous_head_frame_hash",
        "accepted_delta_count",
        "publisher_git_commit",
        "claims",
    }
    if type(value) is not dict or set(value) != keys:
        raise LedgerError("subscriber checkpoint has the wrong shape")
    normalized = _normalize_json(value)
    if normalized["schema"] != SUBSCRIBER_CHECKPOINT_SCHEMA:
        raise LedgerError("subscriber checkpoint has the wrong schema")
    for key in ("checkpoint_digest", "subscriber_id_digest", "ledger_sha256"):
        if (
            type(normalized[key]) is not str
            or not HASH_RE.fullmatch(normalized[key])
        ):
            raise LedgerError("subscriber checkpoint {} is invalid".format(key))
    expected = _subscriber_digest(
        "rappterzoo/subscriber-checkpoint/1",
        normalized,
        "checkpoint_digest",
    )
    if normalized["checkpoint_digest"] != expected:
        raise LedgerError("subscriber checkpoint digest mismatch")
    if normalized["claims"] != subscriber_chain_claims():
        raise LedgerError("subscriber checkpoint overstates chain authority")
    return normalized


def _fork_evidence(
    subscriber_id_digest: str,
    reason: str,
    checkpoint: Optional[Dict[str, Any]],
    replica_bytes: bytes,
    source_bytes: bytes,
) -> Dict[str, Any]:
    evidence = {
        "schema": SUBSCRIBER_FORK_SCHEMA,
        "evidence_digest": "",
        "subscriber_id_digest": subscriber_id_digest,
        "stream_id": STREAM_ID,
        "reason": reason,
        "witnessed_checkpoint_digest": (
            checkpoint["checkpoint_digest"] if checkpoint else None
        ),
        "witnessed_frame_count": (
            checkpoint["frame_count"] if checkpoint else 0
        ),
        "witnessed_head_frame_hash": (
            checkpoint["head"]["frame_hash"]
            if checkpoint and checkpoint["head"]
            else None
        ),
        "replica_byte_count": len(replica_bytes),
        "replica_sha256": hashlib.sha256(replica_bytes).hexdigest(),
        "observed_source_byte_count": len(source_bytes),
        "observed_source_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "classification": "explicit-prefix-fork-or-drift",
        "claims": subscriber_chain_claims(),
    }
    evidence["evidence_digest"] = _subscriber_digest(
        "rappterzoo/subscriber-fork-evidence/1",
        evidence,
        "evidence_digest",
    )
    return evidence


def _raise_subscriber_fork(
    subscriber_id_digest: str,
    reason: str,
    checkpoint: Optional[Dict[str, Any]],
    replica_bytes: bytes,
    source_bytes: bytes,
    evidence_dir: Optional[Path],
) -> None:
    evidence = _fork_evidence(
        subscriber_id_digest,
        reason,
        checkpoint,
        replica_bytes,
        source_bytes,
    )
    if evidence_dir is not None:
        _write_immutable_json(
            evidence_dir / "{}.json".format(evidence["evidence_digest"]),
            evidence,
        )
    raise ForkError(reason, evidence)


def replicate_subscriber_chain(
    source_ledger_path: Path,
    replica_ledger_path: Path,
    checkpoint_path: Path,
    subscriber_id: str,
    publisher_git_commit: Optional[str] = None,
    evidence_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    if type(subscriber_id) is not str or not subscriber_id:
        raise LedgerError("subscriber_id must be non-empty")
    subscriber_id_digest = hashlib.sha256(
        subscriber_id.encode("utf-8")
    ).hexdigest()
    if publisher_git_commit is not None and (
        type(publisher_git_commit) is not str
        or not re.fullmatch(r"[0-9a-f]{40,64}", publisher_git_commit)
    ):
        raise LedgerError("publisher_git_commit is invalid")
    source_bytes = (
        source_ledger_path.read_bytes()
        if source_ledger_path.exists()
        else b""
    )
    source_frames = _read_frame_bytes(source_bytes)
    replica_bytes = (
        replica_ledger_path.read_bytes()
        if replica_ledger_path.exists()
        else b""
    )
    replica_frames = _read_frame_bytes(replica_bytes)
    checkpoint = None
    if checkpoint_path.exists():
        try:
            checkpoint = _verify_subscriber_checkpoint(
                json.loads(checkpoint_path.read_text(encoding="utf-8"))
            )
        except (OSError, ValueError, json.JSONDecodeError) as error:
            raise LedgerError("subscriber checkpoint is unreadable") from error
        if checkpoint["subscriber_id_digest"] != subscriber_id_digest:
            raise LedgerError("checkpoint belongs to another subscriber")
        if (
            checkpoint["frame_count"] != len(replica_frames)
            or checkpoint["byte_count"] != len(replica_bytes)
            or checkpoint["ledger_sha256"]
            != hashlib.sha256(replica_bytes).hexdigest()
            or checkpoint["head"] != _subscriber_head(replica_frames)
        ):
            _raise_subscriber_fork(
                subscriber_id_digest,
                "local replica no longer matches its witnessed checkpoint",
                checkpoint,
                replica_bytes,
                source_bytes,
                evidence_dir,
            )
    try:
        verify_append_only_bytes(replica_bytes, source_bytes)
    except LedgerError:
        _raise_subscriber_fork(
            subscriber_id_digest,
            "publisher source does not preserve the witnessed replica prefix",
            checkpoint,
            replica_bytes,
            source_bytes,
            evidence_dir,
        )
    if checkpoint and checkpoint["head"]:
        witnessed_seq = checkpoint["head"]["seq"]
        if (
            witnessed_seq >= len(source_frames)
            or source_frames[witnessed_seq]["frame_hash"]
            != checkpoint["head"]["frame_hash"]
        ):
            _raise_subscriber_fork(
                subscriber_id_digest,
                "previously witnessed head is not an ancestor of publisher head",
                checkpoint,
                replica_bytes,
                source_bytes,
                evidence_dir,
            )
    delta = source_bytes[len(replica_bytes):]
    if not delta and checkpoint is not None:
        return {
            "updated": False,
            "checkpoint": checkpoint,
            "appended_bytes": 0,
            "appended_frames": 0,
        }
    previous_count = len(replica_frames)
    previous_head = _subscriber_head(replica_frames)
    replica_ledger_path.parent.mkdir(parents=True, exist_ok=True)
    if delta:
        _append_exact_bytes(replica_ledger_path, replica_bytes, delta)
    updated_bytes = source_bytes
    updated_frames = source_frames
    new_checkpoint = {
        "schema": SUBSCRIBER_CHECKPOINT_SCHEMA,
        "checkpoint_digest": "",
        "subscriber_id_digest": subscriber_id_digest,
        "stream_id": STREAM_ID,
        "frame_count": len(updated_frames),
        "byte_count": len(updated_bytes),
        "head": _subscriber_head(updated_frames),
        "ledger_sha256": hashlib.sha256(updated_bytes).hexdigest(),
        "previous_checkpoint_digest": (
            checkpoint["checkpoint_digest"] if checkpoint else None
        ),
        "previous_frame_count": previous_count,
        "previous_head_frame_hash": (
            previous_head["frame_hash"] if previous_head else None
        ),
        "accepted_delta_count": len(updated_frames) - previous_count,
        "publisher_git_commit": publisher_git_commit,
        "claims": subscriber_chain_claims(),
    }
    new_checkpoint["checkpoint_digest"] = _subscriber_digest(
        "rappterzoo/subscriber-checkpoint/1",
        new_checkpoint,
        "checkpoint_digest",
    )
    _verify_subscriber_checkpoint(new_checkpoint)
    _atomic_json(checkpoint_path, new_checkpoint)
    return {
        "updated": True,
        "checkpoint": new_checkpoint,
        "appended_bytes": len(delta),
        "appended_frames": len(updated_frames) - previous_count,
    }


def emit_subscriber_witness(
    replica_ledger_path: Path,
    checkpoint_path: Path,
    witness_dir: Path,
    emitted_at: str,
    previous_witness_digest: Optional[str] = None,
) -> Dict[str, Any]:
    checkpoint = _verify_subscriber_checkpoint(
        json.loads(checkpoint_path.read_text(encoding="utf-8"))
    )
    replica_bytes = replica_ledger_path.read_bytes()
    frames = _read_frame_bytes(replica_bytes)
    if (
        checkpoint["frame_count"] != len(frames)
        or checkpoint["ledger_sha256"]
        != hashlib.sha256(replica_bytes).hexdigest()
        or checkpoint["head"] != _subscriber_head(frames)
    ):
        evidence = _fork_evidence(
            checkpoint["subscriber_id_digest"],
            "witness emission found checkpoint/replica drift",
            checkpoint,
            replica_bytes,
            replica_bytes,
        )
        raise ForkError(
            "witness emission found checkpoint/replica drift",
            evidence,
        )
    if previous_witness_digest is not None and not HASH_RE.fullmatch(
        previous_witness_digest
    ):
        raise LedgerError("previous_witness_digest is invalid")
    witness = {
        "schema": SUBSCRIBER_WITNESS_SCHEMA,
        "witness_digest": "",
        "subscriber_id_digest": checkpoint["subscriber_id_digest"],
        "stream_id": STREAM_ID,
        "checkpoint_digest": checkpoint["checkpoint_digest"],
        "previous_witness_digest": previous_witness_digest,
        "accepted_frame_count": checkpoint["frame_count"],
        "accepted_byte_count": checkpoint["byte_count"],
        "accepted_delta_count": checkpoint["accepted_delta_count"],
        "head": checkpoint["head"],
        "ledger_sha256": checkpoint["ledger_sha256"],
        "publisher_git_commit": checkpoint["publisher_git_commit"],
        "emitted_at": normalize_utc(emitted_at),
        "attestation": "independent-structural-witness-unverified",
        "claims": subscriber_chain_claims(),
    }
    witness["witness_digest"] = _subscriber_digest(
        "rappterzoo/subscriber-witness/1",
        witness,
        "witness_digest",
    )
    path = witness_dir / "{}.json".format(witness["witness_digest"])
    _write_immutable_json(path, witness)
    return {"witness": witness, "path": path}


def _organism_summary(frames: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    organisms = {}
    for frame in frames:
        payload = frame["payload"]
        organism_id = payload["organism"]
        summary = organisms.setdefault(
            organism_id,
            {
                "id": organism_id,
                "display_name": payload.get("display_name", organism_id),
                "organism_type": payload.get("organism_type", "ecosystem"),
                "neighborhood": payload.get(
                    "neighborhood",
                    "rappterzoo",
                ),
                "kennel": payload.get("kennel"),
                "first_seq": frame["seq"],
                "last_seq": frame["seq"],
                "frame_count": 0,
                "last_seen": frame["utc"],
                "kinds": [],
                "kind_counts": {},
                "event_counts": {},
                "layout_seed": hashlib.sha256(
                    (
                        "rappterzoo/observatory-organism/1\n"
                        + organism_id
                    ).encode("utf-8")
                ).hexdigest(),
            },
        )
        summary["display_name"] = payload.get(
            "display_name",
            summary["display_name"],
        )
        summary["organism_type"] = payload.get(
            "organism_type",
            summary["organism_type"],
        )
        summary["neighborhood"] = payload.get(
            "neighborhood",
            summary["neighborhood"],
        )
        summary["kennel"] = payload.get("kennel", summary["kennel"])
        summary["last_seq"] = frame["seq"]
        summary["last_seen"] = frame["utc"]
        summary["frame_count"] += 1
        kind_counts = summary["kind_counts"]
        kind_counts[frame["kind"]] = kind_counts.get(frame["kind"], 0) + 1
        event = payload["event"]
        event_counts = summary["event_counts"]
        event_counts[event] = event_counts.get(event, 0) + 1
        if frame["kind"] not in summary["kinds"]:
            summary["kinds"].append(frame["kind"])
    for summary in organisms.values():
        summary["kinds"].sort()
        summary["kind_counts"] = dict(sorted(summary["kind_counts"].items()))
        summary["event_counts"] = dict(
            sorted(summary["event_counts"].items())
        )
    return sorted(
        organisms.values(),
        key=lambda item: (-item["frame_count"], item["id"]),
    )


def _segment_digest(frames: List[Dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    digest.update(b"rappterzoo/projection-segment/1\n")
    for frame in frames:
        digest.update(frame["frame_hash"].encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def _segment_metadata(
    visible_frames: List[Dict[str, Any]],
) -> Dict[str, Any]:
    if not visible_frames:
        return {
            "first_seq": None,
            "last_seq": None,
            "first_prev": None,
            "first_prev_wave": None,
            "head_payload_hash": None,
            "head_frame_hash": None,
            "hash_domain": "rappterzoo/projection-segment/1",
            "segment_hash": _segment_digest([]),
        }
    first = visible_frames[0]
    last = visible_frames[-1]
    return {
        "first_seq": first["seq"],
        "last_seq": last["seq"],
        "first_prev": first["prev"],
        "first_prev_wave": first["prev_wave"],
        "head_payload_hash": last["payload_hash"],
        "head_frame_hash": last["frame_hash"],
        "hash_domain": "rappterzoo/projection-segment/1",
        "segment_hash": _segment_digest(visible_frames),
    }


def _observatory_metadata(
    frames: List[Dict[str, Any]],
    organisms: List[Dict[str, Any]],
) -> Dict[str, Any]:
    return {
        "schema": "rappterzoo-organism-observatory/1",
        "layout_inputs": {
            "frame_order": "seq-ascending",
            "frame_seed": "frame_hash",
            "organism_seed": "organisms[].layout_seed",
            "time_axis": "utc",
        },
        "stream_seed": hashlib.sha256(
            (
                "rappterzoo/observatory-stream/1\n"
                + STREAM_ID
            ).encode("ascii")
        ).hexdigest(),
        "timeline": {
            "first_seq": frames[0]["seq"] if frames else None,
            "last_seq": frames[-1]["seq"] if frames else None,
            "first_utc": frames[0]["utc"] if frames else None,
            "last_utc": frames[-1]["utc"] if frames else None,
        },
        "organism_count": len(organisms),
    }


def projection_value(frames: List[Dict[str, Any]]) -> Dict[str, Any]:
    integrity = verify_frames(frames)
    visible_frames = frames[-PROJECTION_LIMIT:]
    segment = _segment_metadata(visible_frames)
    organisms = _organism_summary(frames)
    start_seq = segment["first_seq"]
    projection = {
        "schema": "rappterzoo-organism-feed/1",
        "generated_at": frames[-1]["utc"] if frames else None,
        "stream_id": STREAM_ID,
        "append_only_source": "organism-frames.jsonl",
        "digg_view": "data-tools/digg.html",
        "transparency_chain": {
            **subscriber_chain_claims(),
            "replication": "subscriber-local-prefix-replica-and-checkpoint",
            "fork_policy": "previously-witnessed-non-ancestor-is-explicit-drift",
            "witness_receipts": "content-addressed-structural-observations",
        },
        "frame_control": {
            "mode": "assigned",
            "model": "bitcoin-inspired-append-only-block-sequencing",
            "description": "not-Bitcoin-and-not-decentralized-consensus",
            "authority": "centralized-main-assembler",
            "assigned_folding": "enabled-with-bounded-assembler-leases",
            "live_election": "disabled",
            "synthetic_proofs": "tests-only",
            "future_activation": (
                "explicit-owner-gate-after-measured-public-soak"
            ),
            "activation_evidence": [
                "bounded-cost",
                "fork-free-lineage",
                "public-soak-stability",
                "replay-tamper-resistance",
                "subscriber-witness-evidence",
            ],
            "consensus": "none",
            "mining": "none",
            "currency": "none",
            "compute_incentive": "none",
            "permanent_authority": "none",
        },
        "privacy": {
            "projection": PUBLIC_VISIBILITY,
            "private_godd_media": "excluded",
            "raw_frames": "excluded",
            "biometric_values": "excluded",
        },
        "rapp1": {
            "wire_shape": "exact-eleven-key-frame",
            "hash_domains": [PARTICLE_SPACE, WAVE_SPACE],
            "canonicalization": {
                "profile": "restricted-rapp1-json-v1",
                "compatible_subset_of": "RFC 8785",
                "object_keys": "ASCII",
                "strings": "NFC",
                "numbers": "I-JSON-safe-integers-only",
                "binary64": "forbidden",
            },
            "acceptance": "structural-unverified",
            "reason": (
                "No authenticated RAPP/1 Section 13 registry or swarm "
                "signature is asserted by this public projection."
            ),
        },
        "integrity": {
            **integrity,
            "scope": "full-ledger",
            "projected_segment": {
                "valid": True,
                **segment,
            },
        },
        "pagination": {
            "mode": "bounded-tail",
            "order": "seq-ascending",
            "limit": PROJECTION_LIMIT,
            "start_seq": start_seq,
            "end_seq": segment["last_seq"],
            "has_older": start_seq is not None and start_seq > 0,
            "older_before_seq": (
                start_seq
                if start_seq is not None and start_seq > 0
                else None
            ),
            "has_newer": False,
        },
        "segment": segment,
        "organisms": organisms,
        "observatory": _observatory_metadata(frames, organisms),
        "frames": visible_frames,
        "projection_frame_count": len(visible_frames),
        "total_frame_count": len(frames),
    }
    return projection


def write_projection(
    frames: Optional[List[Dict[str, Any]]] = None,
    path: Path = PROJECTION_PATH,
) -> Dict[str, Any]:
    if frames is None:
        with _ledger_lock(LEDGER_PATH):
            _recover_pending_append(LEDGER_PATH)
            frames = read_frames()
            projection = projection_value(frames)
            _atomic_json(path, projection)
            return projection
    projection = projection_value(frames)
    _atomic_json(path, projection)
    return projection


def verify_projection(
    frames: List[Dict[str, Any]],
    path: Path = PROJECTION_PATH,
) -> Dict[str, Any]:
    if not path.exists():
        raise LedgerError("derived organism projection is missing")
    raw = path.read_bytes()
    try:
        current = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_json_object,
            parse_constant=_invalid_json_constant,
        )
    except LedgerError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise LedgerError("derived organism projection is invalid JSON") from error
    expected = projection_value(frames)
    if current != expected:
        raise LedgerError("derived organism projection is stale or mutated")
    if raw != _pretty_json_bytes(current):
        raise LedgerError("derived organism projection bytes are not deterministic")
    return {
        "valid": True,
        "frame_count": len(current["frames"]),
        "segment_hash": current["segment"]["segment_hash"],
    }


def _paths_match(first: Path, second: Path) -> bool:
    return first.resolve() == second.resolve()


def _stage_frame(
    frames: List[Dict[str, Any]],
    kind: str,
    payload: Dict[str, Any],
    utc: Optional[str],
) -> Tuple[Dict[str, Any], bool]:
    if type(kind) is not str or not KIND_RE.fullmatch(kind):
        raise LedgerError("kind does not match the RAPP/1 label form")
    normalized_payload = validate_public_payload(payload)
    event_id = normalized_payload["event_id"]
    for existing in frames:
        if existing["payload"]["event_id"] != event_id:
            continue
        if existing["kind"] == kind and existing["payload"] == normalized_payload:
            return existing, False
        raise LedgerError("event_id conflict for {}".format(event_id))
    normalized_timestamp = normalize_utc(utc)
    if frames and normalized_timestamp < frames[-1]["utc"]:
        raise LedgerError("new frame timestamp predates the ledger head")
    previous = frames[-1] if frames else None
    frame = build_frame(
        kind=kind,
        stream_id=STREAM_ID,
        seq=len(frames),
        utc=normalized_timestamp,
        payload=normalized_payload,
        prev=previous["payload_hash"] if previous else None,
        prev_wave=previous["frame_hash"] if previous else None,
        sig=None,
    )
    frames.append(frame)
    verify_frames(frames)
    return frame, True


def _write_all(descriptor: int, data: bytes) -> None:
    offset = 0
    while offset < len(data):
        written = os.write(descriptor, data[offset:])
        if written <= 0:
            raise LedgerError("could not append the complete ledger frame")
        offset += written


def _pending_path(ledger_path: Path) -> Path:
    return ledger_path.with_name(ledger_path.name + ".pending")


def _remove_pending_append(ledger_path: Path) -> None:
    try:
        _pending_path(ledger_path).unlink()
    except FileNotFoundError:
        return
    _fsync_directory(ledger_path.parent)


def _write_pending_append(
    ledger_path: Path,
    previous: bytes,
    appended: bytes,
) -> None:
    pending_path = _pending_path(ledger_path)
    temporary = pending_path.with_name(
        "{}.tmp.{}.{}".format(
            pending_path.name,
            os.getpid(),
            uuid.uuid4().hex,
        )
    )
    header = {
        "previous_bytes": len(previous),
        "previous_sha256": hashlib.sha256(previous).hexdigest(),
        "version": 1,
    }
    try:
        with temporary.open("wb") as handle:
            handle.write(canonical_bytes(header) + b"\n" + appended)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(str(temporary), str(pending_path))
        _fsync_directory(ledger_path.parent)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _append_raw_bytes(ledger_path: Path, appended: bytes) -> None:
    descriptor = os.open(
        str(ledger_path),
        os.O_APPEND | os.O_CREAT | os.O_WRONLY,
        0o644,
    )
    try:
        _write_all(descriptor, appended)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    _fsync_directory(ledger_path.parent)


def _recover_pending_append(ledger_path: Path) -> bool:
    pending_path = _pending_path(ledger_path)
    if not pending_path.exists():
        return False
    data = pending_path.read_bytes()
    header_line, separator, appended = data.partition(b"\n")
    if not separator or not appended or not appended.endswith(b"\n"):
        raise LedgerError("pending ledger append is malformed")
    try:
        header = json.loads(
            header_line.decode("utf-8"),
            object_pairs_hook=_json_object,
            parse_constant=_invalid_json_constant,
        )
    except LedgerError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise LedgerError("pending ledger append has invalid metadata") from error
    if (
        type(header) is not dict
        or set(header) != {
            "previous_bytes",
            "previous_sha256",
            "version",
        }
        or header["version"] != 1
        or type(header["previous_bytes"]) is not int
        or header["previous_bytes"] < 0
        or type(header["previous_sha256"]) is not str
        or not HASH_RE.fullmatch(header["previous_sha256"])
        or canonical_bytes(header) != header_line
    ):
        raise LedgerError("pending ledger append metadata is invalid")
    current = ledger_path.read_bytes() if ledger_path.exists() else b""
    previous_bytes = header["previous_bytes"]
    if len(current) < previous_bytes:
        raise LedgerError("pending append cannot recover a truncated ledger")
    previous = current[:previous_bytes]
    if hashlib.sha256(previous).hexdigest() != header["previous_sha256"]:
        raise LedgerError("pending append does not match the ledger prefix")
    expected = previous + appended
    if current != expected:
        if not expected.startswith(current):
            raise LedgerError("pending append conflicts with current ledger bytes")
        _append_raw_bytes(ledger_path, expected[len(current):])
        current = ledger_path.read_bytes()
    if current != expected:
        raise LedgerError("pending ledger append recovery was incomplete")
    _read_frame_bytes(current)
    _remove_pending_append(ledger_path)
    return True


def _append_exact_bytes(
    ledger_path: Path,
    previous: bytes,
    appended: bytes,
) -> None:
    current = ledger_path.read_bytes() if ledger_path.exists() else b""
    if current != previous:
        raise LedgerError("ledger changed after validation; append aborted")
    _read_frame_bytes(previous + appended)
    _write_pending_append(ledger_path, previous, appended)
    _append_raw_bytes(ledger_path, appended)
    committed = ledger_path.read_bytes()
    verify_append_only_bytes(previous, committed)
    if committed != previous + appended:
        raise LedgerError("ledger append was not an exact prefix extension")
    _read_frame_bytes(committed)
    _remove_pending_append(ledger_path)


def append_frame(
    kind: str,
    payload: Dict[str, Any],
    utc: Optional[str] = None,
    ledger_path: Path = LEDGER_PATH,
    projection_path: Path = PROJECTION_PATH,
) -> Dict[str, Any]:
    if _paths_match(ledger_path, projection_path):
        raise LedgerError("ledger and projection paths must be distinct")
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with _ledger_lock(ledger_path):
        _recover_pending_append(ledger_path)
        previous_bytes = (
            ledger_path.read_bytes() if ledger_path.exists() else b""
        )
        frames = _read_frame_bytes(previous_bytes)
        frame, created = _stage_frame(frames, kind, payload, utc)
        if created:
            _append_exact_bytes(
                ledger_path,
                previous_bytes,
                canonical_bytes(frame) + b"\n",
            )
        write_projection(frames, projection_path)
        return frame


def _history_timestamp_after(
    requested: str,
    frames: List[Dict[str, Any]],
) -> str:
    normalized = normalize_utc(requested)
    if not frames or normalized >= frames[-1]["utc"]:
        return normalized
    head = datetime.fromisoformat(
        frames[-1]["utc"].replace("Z", "+00:00")
    )
    return normalize_utc((head + timedelta(milliseconds=1)).isoformat())


def _molter_payload(
    frame_number: int,
    actions: Dict[str, Any],
    metrics: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "schema": "rappterzoo-organism-frame/1",
        "event_id": "molter-frame:{}".format(frame_number),
        "event": "autonomous-frame",
        "organism": "rappterzoo",
        "display_name": "RappterZoo",
        "organism_type": "neighborhood",
        "neighborhood": "rappterzoo",
        "visibility": PUBLIC_VISIBILITY,
        "molter_frame": int(frame_number),
        "actions": _snapshot_json(actions),
        "metrics": _snapshot_json(metrics),
    }


def _ensure_bootstrap(
    state_path: Path,
    ledger_path: Path,
    projection_path: Path,
) -> List[Dict[str, Any]]:
    if _pending_path(ledger_path).exists():
        with _ledger_lock(ledger_path):
            _recover_pending_append(ledger_path)
    if not ledger_path.exists() or not ledger_path.read_bytes():
        bootstrap_from_state(
            state_path=state_path,
            ledger_path=ledger_path,
            projection_path=projection_path,
        )
    frames = read_frames(ledger_path)
    if (
        not frames
        or frames[0]["payload"].get("event") != "bootstrap"
        or frames[0]["payload"].get("organism") != "rappterzoo"
    ):
        raise LedgerError("organism event writers require a genesis bootstrap")
    return frames


def append_molter_frame(
    frame_number: int,
    observation: Dict[str, Any],
    actions: Dict[str, Any],
    utc: Optional[str] = None,
    ledger_path: Path = LEDGER_PATH,
    projection_path: Path = PROJECTION_PATH,
    state_path: Path = STATE_PATH,
) -> Dict[str, Any]:
    frames = _ensure_bootstrap(
        state_path,
        ledger_path,
        projection_path,
    )
    metrics = {
        "total_apps": observation.get("total_apps_manifest", 0),
        "avg_score": observation.get("avg_score", 0),
        "below_40": observation.get("below_40", 0),
        "unmolted": observation.get("unmolted", 0),
    }
    timestamp = _history_timestamp_after(
        utc or normalize_utc(),
        frames,
    )
    return append_frame(
        "zoo.observation",
        _molter_payload(frame_number, actions, metrics),
        utc=timestamp,
        ledger_path=ledger_path,
        projection_path=projection_path,
    )


def append_agent_birth(
    agent: Dict[str, Any],
    issue_number: int,
    utc: Optional[str] = None,
    ledger_path: Path = LEDGER_PATH,
    projection_path: Path = PROJECTION_PATH,
    state_path: Path = STATE_PATH,
) -> Dict[str, Any]:
    frames = _ensure_bootstrap(
        state_path,
        ledger_path,
        projection_path,
    )
    agent_id = str(agent.get("agent_id", "")).strip()
    if not agent_id:
        raise LedgerError("agent birth requires agent_id")
    timestamp = _history_timestamp_after(
        utc or normalize_utc(),
        frames,
    )
    payload = {
        "schema": "rappterzoo-organism-frame/1",
        "event_id": "agent-registration:{}".format(agent_id),
        "event": "birth",
        "organism": "agent.{}".format(agent_id),
        "display_name": agent.get("name", agent_id),
        "organism_type": "agent",
        "neighborhood": "rappterzoo",
        "kennel": "agent-directory",
        "visibility": PUBLIC_VISIBILITY,
        "issue_number": int(issue_number),
        "description": agent.get("description", ""),
        "capabilities": agent.get("capabilities", []),
        "owner_url": agent.get("owner_url", ""),
        "status": agent.get("status", "pending_claim"),
        "trust_tier": agent.get("trust_tier", "unclaimed"),
    }
    return append_frame(
        "zoo.birth",
        payload,
        utc=timestamp,
        ledger_path=ledger_path,
        projection_path=projection_path,
    )


def append_agent_adoption(
    agent: Dict[str, Any],
    issue_number: int,
    utc: Optional[str] = None,
    ledger_path: Path = LEDGER_PATH,
    projection_path: Path = PROJECTION_PATH,
    state_path: Path = STATE_PATH,
) -> Dict[str, Any]:
    frames = _ensure_bootstrap(
        state_path,
        ledger_path,
        projection_path,
    )
    agent_id = str(agent.get("agent_id", "")).strip()
    owner = str(agent.get("owner_github", "")).strip()
    if not agent_id or not owner:
        raise LedgerError("agent adoption requires agent_id and owner_github")
    timestamp = _history_timestamp_after(
        utc or normalize_utc(),
        frames,
    )
    payload = {
        "schema": "rappterzoo-organism-frame/1",
        "event_id": "agent-adoption:{}:{}".format(agent_id, owner),
        "event": "adoption",
        "organism": "agent.{}".format(agent_id),
        "display_name": agent.get("name", agent_id),
        "organism_type": "agent",
        "neighborhood": "rappterzoo",
        "kennel": "agent-directory",
        "visibility": PUBLIC_VISIBILITY,
        "issue_number": int(issue_number),
        "owner_github": owner,
        "status": agent.get("status", "claimed"),
        "trust_tier": agent.get("trust_tier", "claimed"),
        "verification": (
            "public-attestation"
            if agent.get("trust_tier") == "verified"
            else "github-claim"
        ),
    }
    return append_frame(
        "zoo.adoption",
        payload,
        utc=timestamp,
        ledger_path=ledger_path,
        projection_path=projection_path,
    )


def _watchtower_birth_payload() -> Dict[str, Any]:
    return {
        "schema": "rappterzoo-organism-frame/1",
        "event_id": "creature-birth:dogg.looking-glass-watchtower",
        "event": "birth",
        "organism": "dogg.looking-glass-watchtower",
        "display_name": "Looking Glass Watchtower",
        "organism_type": "dogg",
        "neighborhood": "rappterzoo",
        "kennel": "dogg-pound",
        "visibility": PUBLIC_VISIBILITY,
        "front_door": {
            "kind": "skills-md",
            "url": (
                "https://raw.githubusercontent.com/kody-w/"
                "localFirstTools-main/main/skills.md"
            ),
        },
        "source": {
            "kind": "borg-global-assimilation",
            "repository": "kody-w/localFirstTools-main",
            "commit": "9c7f8747c1ce2cd41a8a8f63489c582e44ca5a51",
        },
        "capabilities": [
            "anonymous-motion-events",
            "pose-and-hand-gesture-observations",
            "factual-play-by-play",
            "append-only-public-metadata",
        ],
        "privacy": {
            "audio": False,
            "cloud_inference": False,
            "face_recognition": False,
            "private_media_in_public_ledger": False,
            "pulse_persisted": False,
        },
    }


def _load_bootstrap_state(state_path: Path) -> Dict[str, Any]:
    if not state_path.exists():
        return {"frame": 0, "history": []}
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise LedgerError("molter state is unreadable or invalid JSON") from error
    if type(state) is not dict:
        raise LedgerError("molter state must be a JSON object")
    state_frame = state.get("frame", 0)
    history = state.get("history", [])
    if (
        type(state_frame) is not int
        or state_frame < 0
        or state_frame > MAX_SAFE_INTEGER
    ):
        raise LedgerError("molter state frame must be a safe non-negative integer")
    if type(history) is not list:
        raise LedgerError("molter state history must be an array")
    normalized_history = []
    seen_frames = set()
    for index, historical in enumerate(history):
        if type(historical) is not dict:
            raise LedgerError(
                "molter history item {} must be an object".format(index)
            )
        frame_number = historical.get("frame")
        if (
            type(frame_number) is not int
            or frame_number < 0
            or frame_number > MAX_SAFE_INTEGER
        ):
            raise LedgerError(
                "molter history item {} has an invalid frame".format(index)
            )
        if frame_number in seen_frames:
            raise LedgerError(
                "molter history contains duplicate frame {}".format(
                    frame_number
                )
            )
        seen_frames.add(frame_number)
        if "timestamp" not in historical:
            raise LedgerError(
                "molter history item {} is missing timestamp".format(index)
            )
        timestamp = normalize_utc(historical["timestamp"])
        actions = historical.get("actions", {})
        metrics = historical.get("metrics", {})
        if type(actions) is not dict or type(metrics) is not dict:
            raise LedgerError(
                "molter history actions and metrics must be objects"
            )
        normalized_history.append({
            "frame": frame_number,
            "timestamp": timestamp,
            "actions": actions,
            "metrics": metrics,
        })
    normalized_history.sort(key=lambda item: item["frame"])
    if normalized_history and state_frame < normalized_history[-1]["frame"]:
        raise LedgerError("molter state head precedes its bounded history")
    for index in range(1, len(normalized_history)):
        if (
            normalized_history[index]["timestamp"]
            < normalized_history[index - 1]["timestamp"]
        ):
            raise LedgerError("molter history timestamps must be monotonic")
    return {
        "frame": state_frame,
        "history": normalized_history,
    }


def bootstrap_from_state(
    state_path: Path = STATE_PATH,
    ledger_path: Path = LEDGER_PATH,
    projection_path: Path = PROJECTION_PATH,
) -> Dict[str, Any]:
    if _paths_match(ledger_path, projection_path):
        raise LedgerError("ledger and projection paths must be distinct")
    state = _load_bootstrap_state(state_path)
    history = state["history"]
    first_timestamp = (
        history[0]["timestamp"]
        if history
        else "2026-08-15T17:06:24.449Z"
    )
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with _ledger_lock(ledger_path):
        _recover_pending_append(ledger_path)
        previous_bytes = (
            ledger_path.read_bytes() if ledger_path.exists() else b""
        )
        frames = _read_frame_bytes(previous_bytes)
        bootstrap_indexes = [
            index
            for index, frame in enumerate(frames)
            if frame["payload"].get("event") == "bootstrap"
            and frame["payload"].get("organism") == "rappterzoo"
        ]
        if bootstrap_indexes and bootstrap_indexes != [0]:
            raise LedgerError(
                "ledger must contain exactly one genesis bootstrap frame"
            )
        has_bootstrap = bootstrap_indexes == [0]
        if not has_bootstrap and frames:
            raise LedgerError(
                "non-empty ledger is missing its bootstrap frame"
            )
        appended = []
        if not has_bootstrap:
            frame, created = _stage_frame(
                frames,
                "zoo.snapshot",
                {
                    "schema": PAYLOAD_SCHEMA,
                    "event_id": "bootstrap:molter-state:{}".format(
                        state["frame"]
                    ),
                    "event": "bootstrap",
                    "organism": "rappterzoo",
                    "display_name": "RappterZoo",
                    "organism_type": "neighborhood",
                    "neighborhood": "rappterzoo",
                    "visibility": PUBLIC_VISIBILITY,
                    "source": {
                        "kind": "bounded-molter-state",
                        "history_count": len(history),
                        "head_frame": state["frame"],
                    },
                },
                first_timestamp,
            )
            if created:
                appended.append(frame)
        for historical in history:
            frame, created = _stage_frame(
                frames,
                "zoo.observation",
                _molter_payload(
                    historical["frame"],
                    historical["actions"],
                    historical["metrics"],
                ),
                historical["timestamp"],
            )
            if created:
                appended.append(frame)
        frame, created = _stage_frame(
            frames,
            "zoo.birth",
            _watchtower_birth_payload(),
            _history_timestamp_after(
                "2026-08-15T17:06:24.449Z",
                frames,
            ),
        )
        if created:
            appended.append(frame)
        if appended:
            _append_exact_bytes(
                ledger_path,
                previous_bytes,
                b"".join(
                    canonical_bytes(frame) + b"\n"
                    for frame in appended
                ),
            )
        return write_projection(frames, projection_path)


def main() -> int:
    parser = argparse.ArgumentParser(prog="organism-ledger")
    parser.add_argument(
        "command",
        choices=("bootstrap", "verify", "project", "replicate", "witness"),
    )
    parser.add_argument(
        "--git-base",
        help="For verify, require the current JSONL to preserve this git ref.",
    )
    parser.add_argument("--source-ledger")
    parser.add_argument("--replica-ledger")
    parser.add_argument("--checkpoint")
    parser.add_argument("--subscriber-id")
    parser.add_argument("--publisher-git-commit")
    parser.add_argument("--evidence-dir")
    parser.add_argument("--witness-dir")
    parser.add_argument("--emitted-at")
    parser.add_argument("--previous-witness-digest")
    arguments = parser.parse_args()
    try:
        if arguments.command == "bootstrap":
            result = bootstrap_from_state()
        elif arguments.command == "project":
            result = write_projection()
        elif arguments.command == "replicate":
            required = (
                arguments.source_ledger,
                arguments.replica_ledger,
                arguments.checkpoint,
                arguments.subscriber_id,
            )
            if not all(required):
                raise LedgerError(
                    "replicate requires source-ledger, replica-ledger, "
                    "checkpoint, and subscriber-id"
                )
            result = replicate_subscriber_chain(
                Path(arguments.source_ledger),
                Path(arguments.replica_ledger),
                Path(arguments.checkpoint),
                arguments.subscriber_id,
                publisher_git_commit=arguments.publisher_git_commit,
                evidence_dir=(
                    Path(arguments.evidence_dir)
                    if arguments.evidence_dir
                    else None
                ),
            )
        elif arguments.command == "witness":
            required = (
                arguments.replica_ledger,
                arguments.checkpoint,
                arguments.witness_dir,
                arguments.emitted_at,
            )
            if not all(required):
                raise LedgerError(
                    "witness requires replica-ledger, checkpoint, "
                    "witness-dir, and emitted-at"
                )
            result = emit_subscriber_witness(
                Path(arguments.replica_ledger),
                Path(arguments.checkpoint),
                Path(arguments.witness_dir),
                arguments.emitted_at,
                previous_witness_digest=arguments.previous_witness_digest,
            )
        else:
            with _ledger_lock(LEDGER_PATH):
                recovered = _recover_pending_append(LEDGER_PATH)
                frames = read_frames()
                if recovered:
                    write_projection(frames)
                result = verify_frames(frames)
                result["projection"] = verify_projection(frames)
                if arguments.git_base:
                    result["git_prefix"] = verify_git_append_only(
                        arguments.git_base
                    )
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except ForkError as error:
        print(
            json.dumps({
                "ok": False,
                "error": str(error),
                "fork_evidence": error.evidence,
            }),
            file=sys.stderr,
        )
        return 1
    except LedgerError as error:
        print(
            json.dumps({"ok": False, "error": str(error)}),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

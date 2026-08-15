#!/usr/bin/env python3
"""Budgeted, content-addressed attention frames for public interaction groups."""

import argparse
import hashlib
import json
import os
import re
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import organism_ledger as ledger


ROOT = Path(__file__).resolve().parent.parent
ATTENTION_DIR = ROOT / "apps" / "attention"
DEFAULT_PROMPT_PATH = ATTENTION_DIR / "prompt-contract.json"
DEFAULT_POLICY_PATH = ATTENTION_DIR / "policy.json"
DEFAULT_FRAME_CONTROL_PATH = ATTENTION_DIR / "frame-control.json"

REQUEST_SCHEMA = "rappterzoo-attention-request/1"
EVALUATOR_PACKET_SCHEMA = "rappterzoo-attention-evaluator-packet/1"
PROMPT_SCHEMA = "rappterzoo-attention-prompt/1"
POLICY_SCHEMA = "rappterzoo-attention-policy/1"
EVALUATION_SCHEMA = "rappterzoo-attention-evaluation/1"
GROUP_SCHEMA = "rappterzoo-attention-group/1"
RECEIPT_SCHEMA = "rappterzoo-mutation-receipt/1"
RECEIPT_OBJECT_SCHEMA = "rappterzoo-mutation-receipt-object/1"
SHARD_WRITER_SCHEMA = "rappterzoo-attention-shard-writer/1"
DIMENSION_SCHEMA = "rappterzoo-attention-dimension/1"
PARTICIPANT_REGISTRATION_SCHEMA = "rappterzoo-brainstem-registration/1"
PARTICIPANT_SCHEMA = "rappterzoo-brainstem-participant/1"
PARTICIPANT_REVOCATION_SCHEMA = "rappterzoo-brainstem-revocation/1"
LEASE_REQUEST_SCHEMA = "rappterzoo-shard-lease-request/1"
LEASE_SCHEMA = "rappterzoo-shard-capability-lease/1"
CANDIDATE_RESULT_SCHEMA = "rappterzoo-candidate-shard-result/1"
ASSEMBLY_RECEIPT_SCHEMA = "rappterzoo-candidate-assembly-receipt/1"
FOLD_CHALLENGE_SCHEMA = "rappterzoo-proof-of-fold-challenge/1"
FOLD_ATTEMPT_SCHEMA = "rappterzoo-proof-of-fold-attempt/1"
FOLD_AWARD_SCHEMA = "rappterzoo-frame-control-award/1"
FOLD_EXPIRY_SCHEMA = "rappterzoo-frame-control-expiry/1"
FOLD_MIN_DIFFICULTY_BITS = 3
FOLD_MAX_DIFFICULTY_BITS = 12
FRAME_CONTROL_CONFIG_SCHEMA = "rappterzoo-frame-control-config/1"

MAX_INPUT_BYTES = 8 * 1024 * 1024
MAX_EVALUATION_BYTES = 256 * 1024
MAX_RECORDS = 10000
MAX_SHARDS = 1024
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,199}$")
RECORD_KIND_RE = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
MEDIA_TYPE_RE = re.compile(
    r"^[a-z0-9][a-z0-9!#$&^_.+-]{0,63}/"
    r"[a-z0-9][a-z0-9!#$&^_.+-]{0,63}$"
)
SECRET_PATTERNS = (
    re.compile(
        r"(?i)\b(?:api[_ -]?key|authorization|bearer|password|secret|token)"
        r"\b\s*[:=]"
    ),
    re.compile(
        r"\b(?:ghp|github_pat|moltbook|sk)_[A-Za-z0-9_-]{8,}"
    ),
)
RECORD_KEYS = {
    "record_id",
    "kind",
    "created_at",
    "visibility",
    "public_text",
    "priority",
    "source_ref",
}
DESCRIPTOR_KEYS = {
    "record_id",
    "record_digest",
    "kind",
    "created_at",
    "priority",
    "source_ref",
}
POLICY_KEYS = {
    "schema",
    "selection_algorithm",
    "max_group_records",
    "candidate_budget",
    "attention_budget",
    "dimension_gate_min_comparisons",
    "dimension_max_branches",
    "dimension_max_collision_rate_ppm",
    "dimension_gate_min_comparisons",
    "dimension_max_branches",
    "dimension_max_collision_rate_ppm",
    "max_public_text_chars",
    "max_reason_chars",
    "score_min",
    "score_max",
}
PROMPT_KEYS = {
    "schema",
    "contract_id",
    "objective",
    "selection_instruction",
    "evaluation_dimensions",
    "reason_instruction",
    "output_contract",
    "safety_constraints",
}
REQUEST_KEYS = {
    "schema",
    "request_id",
    "request_digest",
    "group_id",
    "shard_id",
    "scope_key",
    "scope_digest",
    "base_record_hash",
    "base_frame_hash",
    "endpoint_identity_digest",
    "evaluation_axis",
    "provenance",
    "scope",
    "record_descriptors",
    "total_group_count",
    "candidate_record_ids",
    "candidate_count",
    "candidate_budget",
    "attention_budget",
    "input_digest",
    "prompt_contract",
    "prompt_digest",
    "policy",
    "policy_digest",
}
EVALUATION_KEYS = {
    "schema",
    "request_digest",
    "input_digest",
    "prompt_digest",
    "shard_id",
    "scope_digest",
    "base_record_hash",
    "base_frame_hash",
    "endpoint_identity_digest",
    "evaluation_axis",
    "group_assessment",
    "selected",
}
ASSESSMENT_KEYS = {
    "attention_state",
    "polarity",
    "mutation_recommendation",
    "reason",
}
SELECTION_KEYS = {
    "record_id",
    "record_digest",
    "score",
    "reason",
}
RECEIPT_KEYS = {
    "schema",
    "run_kind",
    "mutation_id",
    "group_object_digest",
    "attention_frame_seq",
    "attention_frame_hash",
    "consumed_record_ids",
    "output_digest",
    "output_media_type",
    "mutation_prompt_digest",
    "dimension_object_digest",
    "dimension_mode",
    "dimension_branch_group_digests",
}
CANDIDATE_RESULT_KEYS = {
    "schema",
    "candidate_result_digest",
    "trust_status",
    "lease_id",
    "lease_digest",
    "participant_ref",
    "participant_identity_ref",
    "participant_object_digest",
    "participant_identity_digest",
    "endpoint_identity_digest",
    "shard_id",
    "channel",
    "scope_key",
    "scope_digest",
    "base_record_hash",
    "base_frame_hash",
    "base_head_seq",
    "base_head_hash",
    "attention_request_digest",
    "evaluation",
    "output_count",
    "output_bytes",
    "submitted_at",
    "submission_nonce",
    "submission_idempotency_key",
    "privacy_policy_digest",
    "wire_protocol",
    "control_award_digest",
    "winner_proof_hash",
    "frame_control_mode",
}


class AttentionError(ValueError):
    pass


def _digest(domain: str, value: Any) -> str:
    return hashlib.sha256(
        domain.encode("ascii") + b"\n" + ledger.canonical_bytes(value)
    ).hexdigest()


def _load_json(path: Path, max_bytes: int = MAX_INPUT_BYTES) -> Any:
    try:
        raw = path.read_bytes()
    except OSError as error:
        raise AttentionError("cannot read {}".format(path)) from error
    if len(raw) > max_bytes:
        raise AttentionError("{} exceeds its byte limit".format(path))
    try:
        return json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=ledger._json_object,
            parse_constant=ledger._invalid_json_constant,
        )
    except ledger.LedgerError as error:
        raise AttentionError(str(error)) from error
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AttentionError("{} is not valid JSON".format(path)) from error


def _write_immutable_json(path: Path, value: Any) -> bool:
    ledger.canonical_bytes(value)
    encoded = ledger._pretty_json_bytes(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != encoded:
            raise AttentionError(
                "immutable object already exists with different bytes: {}".format(
                    path
                )
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
                raise AttentionError(
                    "immutable object raced with different bytes: {}".format(
                        path
                    )
                )
            return False
        ledger._fsync_directory(path.parent)
        return True
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _require_exact_keys(value: Any, keys: set, label: str) -> Dict[str, Any]:
    if type(value) is not dict or set(value) != keys:
        raise AttentionError(
            "{} must have exactly: {}".format(label, ", ".join(sorted(keys)))
        )
    return value


def _require_id(value: Any, label: str) -> str:
    if type(value) is not str or not ID_RE.fullmatch(value):
        raise AttentionError("{} is not a valid public identifier".format(label))
    return value


def _require_hash(value: Any, label: str) -> str:
    if type(value) is not str or not ledger.HASH_RE.fullmatch(value):
        raise AttentionError("{} must be a SHA-256 digest".format(label))
    return value


def _reject_secret_text(value: str, label: str) -> None:
    for pattern in SECRET_PATTERNS:
        if pattern.search(value):
            raise AttentionError(
                "{} appears to contain a credential or secret".format(label)
            )


def _reject_private_keys(value: Any, label: str) -> None:
    forbidden = ledger._find_forbidden_key(value)
    if forbidden:
        raise AttentionError(
            "{} contains forbidden public key: {}".format(label, forbidden)
        )


def validate_policy(value: Any) -> Dict[str, Any]:
    policy = _require_exact_keys(value, POLICY_KEYS, "attention policy")
    try:
        normalized = ledger._normalize_json(policy)
    except ledger.LedgerError as error:
        raise AttentionError(str(error)) from error
    if normalized["schema"] != POLICY_SCHEMA:
        raise AttentionError("attention policy has the wrong schema")
    if normalized["selection_algorithm"] != "priority-desc-digest-asc-v1":
        raise AttentionError("unsupported attention selection algorithm")
    for key in (
        "max_group_records",
        "candidate_budget",
        "attention_budget",
        "max_public_text_chars",
        "max_reason_chars",
        "score_min",
        "score_max",
    ):
        if type(normalized[key]) is not int:
            raise AttentionError("policy {} must be an integer".format(key))
    if not 1 <= normalized["max_group_records"] <= 1000:
        raise AttentionError("max_group_records must be between 1 and 1000")
    if not 1 <= normalized["candidate_budget"] <= normalized[
        "max_group_records"
    ]:
        raise AttentionError("candidate_budget exceeds the group bound")
    if not 1 <= normalized["attention_budget"] <= normalized[
        "candidate_budget"
    ]:
        raise AttentionError("attention_budget exceeds candidate_budget")
    if not 1 <= normalized["dimension_gate_min_comparisons"] <= 100000:
        raise AttentionError("dimension_gate_min_comparisons is invalid")
    if not 2 <= normalized["dimension_max_branches"] <= 64:
        raise AttentionError("dimension_max_branches is invalid")
    if not 0 <= normalized["dimension_max_collision_rate_ppm"] <= 1000000:
        raise AttentionError(
            "dimension_max_collision_rate_ppm is invalid"
        )
    if not 1 <= normalized["max_public_text_chars"] <= 20000:
        raise AttentionError("max_public_text_chars is invalid")
    if not 1 <= normalized["max_reason_chars"] <= 2000:
        raise AttentionError("max_reason_chars is invalid")
    if (
        normalized["score_min"] < 0
        or normalized["score_max"] > 1000
        or normalized["score_min"] >= normalized["score_max"]
    ):
        raise AttentionError("score range is invalid")
    return normalized


def validate_prompt_contract(value: Any) -> Dict[str, Any]:
    prompt = _require_exact_keys(value, PROMPT_KEYS, "prompt contract")
    try:
        normalized = ledger._normalize_json(prompt)
    except ledger.LedgerError as error:
        raise AttentionError(str(error)) from error
    _reject_private_keys(normalized, "prompt contract")
    if normalized["schema"] != PROMPT_SCHEMA:
        raise AttentionError("prompt contract has the wrong schema")
    _require_id(normalized["contract_id"], "prompt contract_id")
    for key in (
        "objective",
        "selection_instruction",
        "reason_instruction",
    ):
        if type(normalized[key]) is not str or not normalized[key].strip():
            raise AttentionError("prompt {} must be non-empty".format(key))
        if len(normalized[key]) > 4000:
            raise AttentionError("prompt {} is too long".format(key))
    for key in ("evaluation_dimensions", "safety_constraints"):
        values = normalized[key]
        if (
            type(values) is not list
            or not values
            or len(values) > 32
            or any(type(item) is not str or not item for item in values)
        ):
            raise AttentionError("prompt {} is invalid".format(key))
    if type(normalized["output_contract"]) is not dict:
        raise AttentionError("prompt output_contract must be an object")
    return normalized


def _normalize_record(
    value: Any,
    policy: Dict[str, Any],
) -> Dict[str, Any]:
    record = _require_exact_keys(value, RECORD_KEYS, "attention record")
    try:
        normalized = ledger._normalize_json(record)
    except ledger.LedgerError as error:
        raise AttentionError(str(error)) from error
    _reject_private_keys(normalized, "attention record")
    record_id = _require_id(normalized["record_id"], "record_id")
    if (
        type(normalized["kind"]) is not str
        or not RECORD_KIND_RE.fullmatch(normalized["kind"])
    ):
        raise AttentionError("record kind is invalid")
    try:
        normalized["created_at"] = ledger.normalize_utc(
            normalized["created_at"]
        )
    except ledger.LedgerError as error:
        raise AttentionError(str(error)) from error
    if normalized["visibility"] != ledger.PUBLIC_VISIBILITY:
        raise AttentionError("attention records must be public-metadata")
    public_text = normalized["public_text"]
    if (
        type(public_text) is not str
        or not public_text.strip()
        or len(public_text) > policy["max_public_text_chars"]
    ):
        raise AttentionError("public_text is empty or exceeds its bound")
    _reject_secret_text(public_text, "public_text for {}".format(record_id))
    priority = normalized["priority"]
    if (
        type(priority) is not int
        or priority < -ledger.MAX_SAFE_INTEGER
        or priority > ledger.MAX_SAFE_INTEGER
    ):
        raise AttentionError("record priority is invalid")
    if (
        type(normalized["source_ref"]) is not str
        or len(normalized["source_ref"]) > 300
    ):
        raise AttentionError("record source_ref is invalid")
    _reject_secret_text(
        normalized["source_ref"],
        "source_ref for {}".format(record_id),
    )
    return normalized


def _record_digest(record: Dict[str, Any]) -> str:
    return _digest("rappterzoo/attention-record/1", record)


def _record_descriptor(record: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "record_id": record["record_id"],
        "record_digest": _record_digest(record),
        "kind": record["kind"],
        "created_at": record["created_at"],
        "priority": record["priority"],
        "source_ref": record["source_ref"],
    }


def _normalize_records(
    value: Any,
    policy: Dict[str, Any],
) -> List[Dict[str, Any]]:
    if type(value) is dict and set(value) == {"records"}:
        value = value["records"]
    if type(value) is not list or not value or len(value) > MAX_RECORDS:
        raise AttentionError("records must be a non-empty bounded array")
    records = [_normalize_record(item, policy) for item in value]
    ids = [record["record_id"] for record in records]
    if len(ids) != len(set(ids)):
        raise AttentionError("record_id values must be unique")
    return records


def _endpoint_identity_digest(identity: str) -> str:
    if (
        type(identity) is not str
        or not identity.strip()
        or len(identity) > 200
        or "://" in identity
        or "@" in identity
    ):
        raise AttentionError(
            "endpoint identity must be a non-URL public alias"
        )
    _reject_secret_text(identity, "endpoint identity")
    return _digest(
        "rappterzoo/attention-endpoint/1",
        {"identity": identity.strip()},
    )


def _scope_digest(
    scope_key: str,
    source: str,
    window_start: str,
    window_end: str,
    base_record_hash: str,
    base_frame_hash: str,
    evaluation_axis: str,
) -> str:
    return _digest(
        "rappterzoo/attention-scope/1",
        {
            "scope_key": scope_key,
            "source": source,
            "window_start": window_start,
            "window_end": window_end,
            "base_record_hash": base_record_hash,
            "base_frame_hash": base_frame_hash,
            "evaluation_axis": evaluation_axis,
        },
    )


def _assigned_shard(scope_digest: str, shard_count: int) -> int:
    return int(scope_digest[:16], 16) % shard_count


def _shard_id(shard_count: int, shard_index: int) -> str:
    return "attention-shard:{:04d}of{:04d}".format(
        shard_index,
        shard_count,
    )


def _register_shard_writer(
    attention_dir: Path,
    shard_id: str,
    shard_count: int,
    shard_index: int,
    endpoint_identity_digest: str,
) -> Path:
    path = attention_dir / "shards" / (
        "shard-{:04d}-of-{:04d}.json".format(
            shard_index,
            shard_count,
        )
    )
    record = {
        "schema": SHARD_WRITER_SCHEMA,
        "shard_id": shard_id,
        "shard_count": shard_count,
        "shard_index": shard_index,
        "endpoint_identity_digest": endpoint_identity_digest,
    }
    if path.exists():
        existing = _load_json(path)
        if existing != record:
            raise AttentionError(
                "shard {} is already assigned to another writer".format(
                    shard_id
                )
            )
        return path
    _write_immutable_json(path, record)
    return path


def _scope_slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    if not slug:
        raise AttentionError("scope_id must contain letters or digits")
    return slug[:60]


def _group_id(scope: Dict[str, Any], input_digest: str) -> str:
    return "attention:{}:s{:04d}of{:04d}:g{:06d}:{}".format(
        _scope_slug(scope["scope_id"]),
        scope["shard_index"],
        scope["shard_count"],
        scope["group_index"],
        input_digest[:16],
    )


def _request_preimage(request: Dict[str, Any]) -> Dict[str, Any]:
    return {
        key: value
        for key, value in request.items()
        if key not in {"request_id", "request_digest"}
    }


def _request_digest(request: Dict[str, Any]) -> str:
    return _digest(
        "rappterzoo/attention-request/1",
        _request_preimage(request),
    )


def _validate_scope(value: Any) -> Dict[str, Any]:
    keys = {
        "scope_id",
        "source",
        "window_start",
        "window_end",
        "shard_count",
        "shard_index",
        "group_index",
        "group_count",
    }
    scope = _require_exact_keys(value, keys, "attention scope")
    _require_id(scope["scope_id"], "scope_id")
    if type(scope["source"]) is not str or not scope["source"]:
        raise AttentionError("scope source must be non-empty")
    try:
        start = ledger.normalize_utc(scope["window_start"])
        end = ledger.normalize_utc(scope["window_end"])
    except ledger.LedgerError as error:
        raise AttentionError(str(error)) from error
    if start > end:
        raise AttentionError("scope window_start exceeds window_end")
    for key in (
        "shard_count",
        "shard_index",
        "group_index",
        "group_count",
    ):
        if type(scope[key]) is not int or scope[key] < 0:
            raise AttentionError("scope {} is invalid".format(key))
    if (
        not 1 <= scope["shard_count"] <= MAX_SHARDS
        or scope["shard_index"] >= scope["shard_count"]
        or not 1 <= scope["group_count"] <= MAX_RECORDS
        or scope["group_index"] >= scope["group_count"]
    ):
        raise AttentionError("scope shard/group bounds are invalid")
    return {
        **scope,
        "window_start": start,
        "window_end": end,
    }


def verify_request(value: Any) -> Dict[str, Any]:
    request = _require_exact_keys(value, REQUEST_KEYS, "attention request")
    try:
        normalized = ledger._normalize_json(request)
    except ledger.LedgerError as error:
        raise AttentionError(str(error)) from error
    if normalized["schema"] != REQUEST_SCHEMA:
        raise AttentionError("attention request has the wrong schema")
    policy = validate_policy(normalized["policy"])
    prompt = validate_prompt_contract(normalized["prompt_contract"])
    scope = _validate_scope(normalized["scope"])
    provenance = normalized["provenance"]
    if (
        type(provenance) is not dict
        or set(provenance) != {
            "base_record_hash",
            "base_frame_hash",
            "endpoint_identity",
            "evaluation_axis",
        }
        or provenance["base_record_hash"]
        not in {"explicit", "derived-scope-record-set-v1"}
        or provenance["base_frame_hash"]
        not in {"explicit", "derived-current-ledger-head"}
        or provenance["endpoint_identity"]
        not in {"explicit", "local-default-writer"}
        or provenance["evaluation_axis"]
        not in {"explicit", "default-general-axis"}
    ):
        raise AttentionError("request provenance is invalid")
    scope_key = _require_id(normalized["scope_key"], "scope_key")
    evaluation_axis = _require_id(
        normalized["evaluation_axis"],
        "evaluation_axis",
    )
    for key in (
        "scope_digest",
        "base_record_hash",
        "base_frame_hash",
        "endpoint_identity_digest",
    ):
        _require_hash(normalized[key], key)
    expected_scope_digest = _scope_digest(
        scope_key,
        scope["source"],
        scope["window_start"],
        scope["window_end"],
        normalized["base_record_hash"],
        normalized["base_frame_hash"],
        evaluation_axis,
    )
    if normalized["scope_digest"] != expected_scope_digest:
        raise AttentionError("request scope_digest mismatch")
    if scope["scope_id"] != scope_key:
        raise AttentionError("scope key and scope object disagree")
    expected_shard_id = _shard_id(
        scope["shard_count"],
        scope["shard_index"],
    )
    if normalized["shard_id"] != expected_shard_id:
        raise AttentionError("request shard_id mismatch")
    if scope["shard_index"] != _assigned_shard(
        normalized["scope_digest"],
        scope["shard_count"],
    ):
        raise AttentionError("request is assigned to the wrong shard")
    descriptors = normalized["record_descriptors"]
    if (
        type(descriptors) is not list
        or not descriptors
        or any(
            type(item) is not dict or set(item) != DESCRIPTOR_KEYS
            for item in descriptors
        )
    ):
        raise AttentionError("record_descriptors are invalid")
    ids = []
    for descriptor in descriptors:
        ids.append(_require_id(descriptor["record_id"], "descriptor record_id"))
        _require_hash(descriptor["record_digest"], "record_digest")
        if (
            type(descriptor["kind"]) is not str
            or not RECORD_KIND_RE.fullmatch(descriptor["kind"])
            or type(descriptor["created_at"]) is not str
            or ledger.normalize_utc(descriptor["created_at"])
            != descriptor["created_at"]
            or type(descriptor["priority"]) is not int
            or type(descriptor["source_ref"]) is not str
        ):
            raise AttentionError("record descriptor is invalid")
    if len(ids) != len(set(ids)):
        raise AttentionError("request contains duplicate record IDs")
    if normalized["total_group_count"] != len(descriptors):
        raise AttentionError("total_group_count does not match descriptors")
    if normalized["candidate_budget"] != policy["candidate_budget"]:
        raise AttentionError("request candidate_budget disagrees with policy")
    candidate_ids = normalized["candidate_record_ids"]
    if (
        type(candidate_ids) is not list
        or len(candidate_ids) != normalized["candidate_count"]
        or len(candidate_ids) != len(set(candidate_ids))
        or any(record_id not in ids for record_id in candidate_ids)
    ):
        raise AttentionError("candidate_record_ids violate the prefilter")
    if (
        not 1 <= normalized["candidate_count"]
        <= normalized["candidate_budget"]
        or normalized["candidate_count"] > len(descriptors)
    ):
        raise AttentionError("request candidate_count is invalid")
    expected_attention_budget = min(
        policy["attention_budget"],
        normalized["candidate_count"],
    )
    if normalized["attention_budget"] != expected_attention_budget:
        raise AttentionError("request attention_budget is invalid")
    expected_input = _digest(
        "rappterzoo/attention-input/1",
        descriptors,
    )
    if normalized["input_digest"] != expected_input:
        raise AttentionError("request input_digest mismatch")
    if normalized["policy_digest"] != _digest(
        "rappterzoo/attention-policy/1",
        policy,
    ):
        raise AttentionError("request policy_digest mismatch")
    if normalized["prompt_digest"] != _digest(
        "rappterzoo/attention-prompt/1",
        prompt,
    ):
        raise AttentionError("request prompt_digest mismatch")
    ranked = sorted(
        descriptors,
        key=lambda item: (
            -item["priority"],
            item["record_digest"],
            item["record_id"],
        ),
    )
    expected_ids = [
        item["record_id"]
        for item in ranked[: normalized["candidate_count"]]
    ]
    if candidate_ids != expected_ids:
        raise AttentionError("candidate prefilter is not deterministic")
    if normalized["group_id"] != _group_id(scope, expected_input):
        raise AttentionError("group_id does not match its scope and input")
    expected_digest = _request_digest(normalized)
    if normalized["request_digest"] != expected_digest:
        raise AttentionError("request_digest mismatch")
    if normalized["request_id"] != "attention-request:{}".format(
        expected_digest
    ):
        raise AttentionError("request_id mismatch")
    _reject_private_keys(normalized, "attention request")
    return normalized


def verify_evaluator_packet(
    value: Any,
    request_value: Any,
) -> Dict[str, Any]:
    try:
        ledger.canonical_bytes(value)
    except ledger.LedgerError as error:
        raise AttentionError(str(error)) from error
    keys = {
        "schema",
        "request_id",
        "request_digest",
        "group_id",
        "shard_id",
        "scope_key",
        "scope_digest",
        "base_record_hash",
        "base_frame_hash",
        "endpoint_identity_digest",
        "evaluation_axis",
        "provenance",
        "scope",
        "total_group_count",
        "candidate_count",
        "candidate_budget",
        "attention_budget",
        "input_digest",
        "prompt_contract",
        "prompt_digest",
        "policy",
        "policy_digest",
        "candidate_context",
    }
    packet = _require_exact_keys(value, keys, "evaluator packet")
    request = verify_request(request_value)
    try:
        normalized = ledger._normalize_json(packet)
    except ledger.LedgerError as error:
        raise AttentionError(str(error)) from error
    if normalized["schema"] != EVALUATOR_PACKET_SCHEMA:
        raise AttentionError("evaluator packet has the wrong schema")
    for key in (
        "request_id",
        "request_digest",
        "group_id",
        "shard_id",
        "scope_key",
        "scope_digest",
        "base_record_hash",
        "base_frame_hash",
        "endpoint_identity_digest",
        "evaluation_axis",
        "provenance",
        "scope",
        "total_group_count",
        "candidate_count",
        "candidate_budget",
        "attention_budget",
        "input_digest",
        "prompt_contract",
        "prompt_digest",
        "policy",
        "policy_digest",
    ):
        if normalized[key] != request[key]:
            raise AttentionError("evaluator packet {} mismatch".format(key))
    contexts = normalized["candidate_context"]
    if (
        type(contexts) is not list
        or len(contexts) != request["candidate_count"]
    ):
        raise AttentionError("candidate_context count mismatch")
    descriptor_by_id = {
        item["record_id"]: item
        for item in request["record_descriptors"]
    }
    context_ids = []
    for item in contexts:
        if (
            type(item) is not dict
            or set(item) != RECORD_KEYS | {"record_digest"}
        ):
            raise AttentionError("candidate_context record shape is invalid")
        record = {
            key: item[key]
            for key in RECORD_KEYS
        }
        record = _normalize_record(record, request["policy"])
        descriptor = _record_descriptor(record)
        if item["record_digest"] != descriptor["record_digest"]:
            raise AttentionError("candidate_context digest mismatch")
        if descriptor_by_id.get(record["record_id"]) != descriptor:
            raise AttentionError("candidate_context input mismatch")
        context_ids.append(record["record_id"])
    if context_ids != request["candidate_record_ids"]:
        raise AttentionError("candidate_context IDs do not match prefilter")
    _reject_private_keys(normalized, "evaluator packet")
    return normalized


def prepare_requests(
    records_value: Any,
    prompt_value: Any,
    policy_value: Any,
    scope_id: str,
    source: str,
    window_start: str,
    window_end: str,
    base_record_hash: Optional[str] = None,
    base_frame_hash: Optional[str] = None,
    endpoint_identity: Optional[str] = None,
    evaluation_axis: Optional[str] = None,
    shard_count: int = 1,
    shard_index: Optional[int] = None,
    attention_dir: Path = ATTENTION_DIR,
    ledger_path: Path = ledger.LEDGER_PATH,
) -> List[Dict[str, Any]]:
    policy = validate_policy(policy_value)
    prompt = validate_prompt_contract(prompt_value)
    _require_id(scope_id, "scope_id")
    if type(source) is not str or not source:
        raise AttentionError("source must be non-empty")
    if (
        type(shard_count) is not int
        or not 1 <= shard_count <= MAX_SHARDS
    ):
        raise AttentionError("shard_count is invalid")
    try:
        start = ledger.normalize_utc(window_start)
        end = ledger.normalize_utc(window_end)
    except ledger.LedgerError as error:
        raise AttentionError(str(error)) from error
    if start > end:
        raise AttentionError("window_start exceeds window_end")
    records = _normalize_records(records_value, policy)
    scoped = [
        record
        for record in records
        if start <= record["created_at"] <= end
    ]
    if not scoped:
        raise AttentionError("no records matched the requested scope")
    scoped.sort(key=lambda item: (item["record_id"], _record_digest(item)))
    provenance = {
        "base_record_hash": "explicit",
        "base_frame_hash": "explicit",
        "endpoint_identity": "explicit",
        "evaluation_axis": "explicit",
    }
    if base_record_hash is None:
        base_record_hash = _digest(
            "rappterzoo/derived-scope-record-set/1",
            [_record_descriptor(record) for record in scoped],
        )
        provenance["base_record_hash"] = "derived-scope-record-set-v1"
    else:
        _require_hash(base_record_hash, "base_record_hash")
    if base_frame_hash is None:
        frames = ledger.read_frames(ledger_path)
        base_frame_hash = (
            frames[-1]["frame_hash"] if frames else "0" * 64
        )
        provenance["base_frame_hash"] = "derived-current-ledger-head"
    else:
        _require_hash(base_frame_hash, "base_frame_hash")
    if endpoint_identity is None:
        endpoint_identity = "local-attention-portal"
        provenance["endpoint_identity"] = "local-default-writer"
    if evaluation_axis is None:
        evaluation_axis = "general"
        provenance["evaluation_axis"] = "default-general-axis"
    _require_id(evaluation_axis, "evaluation_axis")
    scope_digest = _scope_digest(
        scope_id,
        source,
        start,
        end,
        base_record_hash,
        base_frame_hash,
        evaluation_axis,
    )
    assigned_shard = _assigned_shard(scope_digest, shard_count)
    if shard_index is not None and shard_index != assigned_shard:
        raise AttentionError(
            "scope is deterministically assigned to shard {}".format(
                assigned_shard
            )
        )
    shard_index = assigned_shard
    shard_id = _shard_id(shard_count, shard_index)
    endpoint_digest = _endpoint_identity_digest(endpoint_identity)
    shard_writer_path = _register_shard_writer(
        attention_dir,
        shard_id,
        shard_count,
        shard_index,
        endpoint_digest,
    )
    size = policy["max_group_records"]
    groups = [
        scoped[index:index + size]
        for index in range(0, len(scoped), size)
    ]
    prompt_digest = _digest("rappterzoo/attention-prompt/1", prompt)
    policy_digest = _digest("rappterzoo/attention-policy/1", policy)
    prepared = []
    for group_index, group_records in enumerate(groups):
        descriptors = [
            _record_descriptor(record)
            for record in group_records
        ]
        input_digest = _digest(
            "rappterzoo/attention-input/1",
            descriptors,
        )
        ranked = sorted(
            descriptors,
            key=lambda item: (
                -item["priority"],
                item["record_digest"],
                item["record_id"],
            ),
        )
        candidate_count = min(
            policy["candidate_budget"],
            len(descriptors),
        )
        candidate_ids = [
            item["record_id"]
            for item in ranked[:candidate_count]
        ]
        actual_attention_budget = min(
            policy["attention_budget"],
            candidate_count,
        )
        record_by_id = {
            record["record_id"]: record
            for record in group_records
        }
        descriptor_by_id = {
            descriptor["record_id"]: descriptor
            for descriptor in descriptors
        }
        scope = {
            "scope_id": scope_id,
            "source": source,
            "window_start": start,
            "window_end": end,
            "shard_count": shard_count,
            "shard_index": shard_index,
            "group_index": group_index,
            "group_count": len(groups),
        }
        request = {
            "schema": REQUEST_SCHEMA,
            "request_id": "",
            "request_digest": "",
            "group_id": _group_id(scope, input_digest),
            "shard_id": shard_id,
            "scope_key": scope_id,
            "scope_digest": scope_digest,
            "base_record_hash": base_record_hash,
            "base_frame_hash": base_frame_hash,
            "endpoint_identity_digest": endpoint_digest,
            "evaluation_axis": evaluation_axis,
            "provenance": provenance,
            "scope": scope,
            "record_descriptors": descriptors,
            "total_group_count": len(descriptors),
            "candidate_record_ids": candidate_ids,
            "candidate_count": candidate_count,
            "candidate_budget": policy["candidate_budget"],
            "attention_budget": actual_attention_budget,
            "input_digest": input_digest,
            "prompt_contract": prompt,
            "prompt_digest": prompt_digest,
            "policy": policy,
            "policy_digest": policy_digest,
        }
        request_digest = _request_digest(request)
        request["request_digest"] = request_digest
        request["request_id"] = "attention-request:{}".format(
            request_digest
        )
        verified = verify_request(request)
        path = attention_dir / "requests" / "{}.json".format(
            request_digest
        )
        _write_immutable_json(path, verified)
        evaluator_packet = {
            "schema": EVALUATOR_PACKET_SCHEMA,
            "request_id": verified["request_id"],
            "request_digest": verified["request_digest"],
            "group_id": verified["group_id"],
            "shard_id": verified["shard_id"],
            "scope_key": verified["scope_key"],
            "scope_digest": verified["scope_digest"],
            "base_record_hash": verified["base_record_hash"],
            "base_frame_hash": verified["base_frame_hash"],
            "endpoint_identity_digest": verified[
                "endpoint_identity_digest"
            ],
            "evaluation_axis": verified["evaluation_axis"],
            "provenance": verified["provenance"],
            "scope": verified["scope"],
            "total_group_count": verified["total_group_count"],
            "candidate_count": verified["candidate_count"],
            "candidate_budget": verified["candidate_budget"],
            "attention_budget": verified["attention_budget"],
            "input_digest": verified["input_digest"],
            "prompt_contract": verified["prompt_contract"],
            "prompt_digest": verified["prompt_digest"],
            "policy": verified["policy"],
            "policy_digest": verified["policy_digest"],
            "candidate_context": [
                {
                    **record_by_id[record_id],
                    "record_digest": descriptor_by_id[record_id][
                        "record_digest"
                    ],
                }
                for record_id in candidate_ids
            ],
        }
        evaluator_packet = verify_evaluator_packet(
            evaluator_packet,
            verified,
        )
        prepared.append({
            "request": verified,
            "path": path,
            "evaluator_packet": evaluator_packet,
            "shard_writer_path": shard_writer_path,
        })
    return prepared


def validate_evaluation(
    value: Any,
    request: Dict[str, Any],
) -> Dict[str, Any]:
    try:
        encoded = ledger.canonical_bytes(value)
    except ledger.LedgerError as error:
        raise AttentionError(str(error)) from error
    if len(encoded) > MAX_EVALUATION_BYTES:
        raise AttentionError("attention evaluation exceeds its byte limit")
    evaluation = _require_exact_keys(
        value,
        EVALUATION_KEYS,
        "attention evaluation",
    )
    try:
        normalized = ledger._normalize_json(evaluation)
    except ledger.LedgerError as error:
        raise AttentionError(str(error)) from error
    if normalized["schema"] != EVALUATION_SCHEMA:
        raise AttentionError("attention evaluation has the wrong schema")
    for key in ("request_digest", "input_digest", "prompt_digest"):
        if normalized[key] != request[key]:
            raise AttentionError("evaluation {} mismatch".format(key))
    for key in (
        "shard_id",
        "scope_digest",
        "base_record_hash",
        "base_frame_hash",
        "endpoint_identity_digest",
        "evaluation_axis",
    ):
        if normalized[key] != request[key]:
            raise AttentionError("evaluation {} mismatch".format(key))
    assessment = _require_exact_keys(
        normalized["group_assessment"],
        ASSESSMENT_KEYS,
        "group_assessment",
    )
    if assessment["attention_state"] not in {"hot", "cold", "neutral"}:
        raise AttentionError("group attention_state is invalid")
    if assessment["polarity"] not in {
        "positive",
        "negative",
        "neutral",
    }:
        raise AttentionError("group polarity is invalid")
    if assessment["mutation_recommendation"] not in {
        "promote",
        "hold",
        "revise",
        "suppress",
    }:
        raise AttentionError("group mutation recommendation is invalid")
    if (
        type(assessment["reason"]) is not str
        or not assessment["reason"]
        or len(assessment["reason"])
        > request["policy"]["max_reason_chars"]
    ):
        raise AttentionError("group assessment reason is invalid")
    _reject_secret_text(
        assessment["reason"],
        "group assessment reason",
    )
    selected = normalized["selected"]
    if (
        type(selected) is not list
        or not 1 <= len(selected) <= request["attention_budget"]
    ):
        raise AttentionError("evaluation selection violates the budget")
    selected_by_id = {}
    descriptor_by_id = {
        item["record_id"]: item
        for item in request["record_descriptors"]
    }
    policy = request["policy"]
    for item in selected:
        _require_exact_keys(item, SELECTION_KEYS, "evaluation selection")
        record_id = _require_id(item["record_id"], "selected record_id")
        if record_id in selected_by_id:
            raise AttentionError("evaluation repeats a selected record")
        if record_id not in request["candidate_record_ids"]:
            raise AttentionError("evaluation selected an unbudgeted record")
        if item["record_digest"] != descriptor_by_id[record_id][
            "record_digest"
        ]:
            raise AttentionError("evaluation record_digest mismatch")
        if (
            type(item["score"]) is not int
            or not policy["score_min"]
            <= item["score"]
            <= policy["score_max"]
        ):
            raise AttentionError("evaluation score is outside policy")
        reason = item["reason"]
        if (
            type(reason) is not str
            or not reason.strip()
            or len(reason) > policy["max_reason_chars"]
        ):
            raise AttentionError("evaluation reason is invalid")
        _reject_secret_text(reason, "evaluation reason")
        selected_by_id[record_id] = item
    return {
        **normalized,
        "selected": [
            selected_by_id[record_id]
            for record_id in request["candidate_record_ids"]
            if record_id in selected_by_id
        ],
    }


def _group_preimage(group: Dict[str, Any]) -> Dict[str, Any]:
    return {
        key: value
        for key, value in group.items()
        if key != "group_object_digest"
    }


def _group_digest(group: Dict[str, Any]) -> str:
    return _digest(
        "rappterzoo/attention-group/1",
        _group_preimage(group),
    )


def verify_group_object(value: Any) -> Dict[str, Any]:
    keys = {
        "schema",
        "group_object_digest",
        "group_id",
        "shard_id",
        "scope_key",
        "scope_digest",
        "base_record_hash",
        "base_frame_hash",
        "endpoint_identity_digest",
        "evaluation_axis",
        "provenance",
        "request_id",
        "request_digest",
        "input_digest",
        "prompt_digest",
        "policy_digest",
        "policy",
        "scope",
        "total_group_count",
        "candidate_count",
        "candidate_budget",
        "attention_budget",
        "selected_count",
        "record_descriptors",
        "candidate_records",
        "selected_records",
        "unselected_candidate_records",
        "never_candidate_records",
        "group_intelligence",
    }
    group = _require_exact_keys(value, keys, "attention group object")
    try:
        normalized = ledger._normalize_json(group)
    except ledger.LedgerError as error:
        raise AttentionError(str(error)) from error
    if normalized["schema"] != GROUP_SCHEMA:
        raise AttentionError("attention group has the wrong schema")
    for key in ("group_id", "shard_id", "scope_key", "evaluation_axis"):
        _require_id(normalized[key], key)
    for key in (
        "scope_digest",
        "base_record_hash",
        "base_frame_hash",
        "endpoint_identity_digest",
    ):
        _require_hash(normalized[key], key)
    scope = _validate_scope(normalized["scope"])
    if (
        type(normalized["provenance"]) is not dict
        or set(normalized["provenance"]) != {
            "base_record_hash",
            "base_frame_hash",
            "endpoint_identity",
            "evaluation_axis",
        }
    ):
        raise AttentionError("group provenance is invalid")
    if normalized["scope_key"] != scope["scope_id"]:
        raise AttentionError("group scope key mismatch")
    if normalized["scope_digest"] != _scope_digest(
        normalized["scope_key"],
        scope["source"],
        scope["window_start"],
        scope["window_end"],
        normalized["base_record_hash"],
        normalized["base_frame_hash"],
        normalized["evaluation_axis"],
    ):
        raise AttentionError("group scope_digest mismatch")
    if normalized["shard_id"] != _shard_id(
        scope["shard_count"],
        scope["shard_index"],
    ):
        raise AttentionError("group shard_id mismatch")
    policy = validate_policy(normalized["policy"])
    if normalized["policy_digest"] != _digest(
        "rappterzoo/attention-policy/1",
        policy,
    ):
        raise AttentionError("group policy_digest mismatch")
    _require_hash(normalized["group_object_digest"], "group_object_digest")
    if normalized["group_object_digest"] != _group_digest(normalized):
        raise AttentionError("group object digest mismatch")
    if normalized["selected_count"] != len(normalized["selected_records"]):
        raise AttentionError("group selected_count mismatch")
    if (
        normalized["selected_count"] < 1
        or normalized["selected_count"] > normalized["attention_budget"]
    ):
        raise AttentionError("group exceeds attention budget")
    if (
        type(normalized["record_descriptors"]) is not list
        or type(normalized["candidate_records"]) is not list
        or type(normalized["selected_records"]) is not list
        or type(normalized["unselected_candidate_records"]) is not list
        or type(normalized["never_candidate_records"]) is not list
    ):
        raise AttentionError("group records must be arrays")
    descriptor_by_id = {}
    for descriptor in normalized["record_descriptors"]:
        if type(descriptor) is not dict or set(descriptor) != DESCRIPTOR_KEYS:
            raise AttentionError("group record descriptor is invalid")
        descriptor_by_id[descriptor["record_id"]] = descriptor
    if len(descriptor_by_id) != len(normalized["record_descriptors"]):
        raise AttentionError("group record descriptors contain duplicates")
    canonical_descriptors = sorted(
        normalized["record_descriptors"],
        key=lambda item: (item["record_id"], item["record_digest"]),
    )
    if normalized["record_descriptors"] != canonical_descriptors:
        raise AttentionError(
            "group record_descriptors are not deterministically ordered"
        )
    selected_shape = DESCRIPTOR_KEYS | {
        "score",
        "reason",
    }
    for item in normalized["selected_records"]:
        if type(item) is not dict or set(item) != selected_shape:
            raise AttentionError("selected group record shape is invalid")
        descriptor = {
            key: item[key]
            for key in DESCRIPTOR_KEYS
        }
        if descriptor != descriptor_by_id.get(item["record_id"]):
            raise AttentionError("selected group record digest mismatch")
        if (
            type(item["score"]) is not int
            or not policy["score_min"]
            <= item["score"]
            <= policy["score_max"]
        ):
            raise AttentionError("selected group score is outside policy")
        if (
            type(item["reason"]) is not str
            or not item["reason"]
            or len(item["reason"]) > policy["max_reason_chars"]
        ):
            raise AttentionError("selected group reason is invalid")
        _reject_secret_text(item["reason"], "selected group reason")
    descriptor_ids = {
        item["record_id"]
        for item in normalized["record_descriptors"]
    }
    selected_ids = {
        item["record_id"]
        for item in normalized["selected_records"]
    }
    candidate_ids = {
        item["record_id"]
        for item in normalized["candidate_records"]
    }
    unselected_candidate_ids = {
        item["record_id"]
        for item in normalized["unselected_candidate_records"]
    }
    never_candidate_ids = {
        item["record_id"]
        for item in normalized["never_candidate_records"]
    }
    if (
        len(candidate_ids) != len(normalized["candidate_records"])
        or len(selected_ids) != len(normalized["selected_records"])
        or len(unselected_candidate_ids)
        != len(normalized["unselected_candidate_records"])
        or len(never_candidate_ids)
        != len(normalized["never_candidate_records"])
    ):
        raise AttentionError("group record partitions contain duplicates")
    if (
        selected_ids & unselected_candidate_ids
        or selected_ids | unselected_candidate_ids != candidate_ids
        or candidate_ids & never_candidate_ids
        or candidate_ids | never_candidate_ids != descriptor_ids
        or normalized["total_group_count"] != len(descriptor_ids)
        or normalized["candidate_count"] != len(candidate_ids)
        or normalized["candidate_count"] > normalized["candidate_budget"]
    ):
        raise AttentionError("group record partition is invalid")
    for section in (
        normalized["candidate_records"],
        normalized["unselected_candidate_records"],
        normalized["never_candidate_records"],
    ):
        if any(
            type(item) is not dict or set(item) != DESCRIPTOR_KEYS
            for item in section
        ):
            raise AttentionError(
                "non-selected group records may contain only descriptors"
            )
    ranked_descriptors = sorted(
        canonical_descriptors,
        key=lambda item: (
            -item["priority"],
            item["record_digest"],
            item["record_id"],
        ),
    )
    expected_candidates = ranked_descriptors[
        : normalized["candidate_count"]
    ]
    if normalized["candidate_records"] != expected_candidates:
        raise AttentionError(
            "candidate_records do not equal the deterministic descriptor subset"
        )
    selected_descriptor_list = [
        {
            key: item[key]
            for key in DESCRIPTOR_KEYS
        }
        for item in normalized["selected_records"]
    ]
    expected_selected = [
        descriptor
        for descriptor in expected_candidates
        if descriptor["record_id"] in selected_ids
    ]
    if selected_descriptor_list != expected_selected:
        raise AttentionError(
            "selected_records do not preserve deterministic candidate order"
        )
    expected_unselected = [
        descriptor
        for descriptor in expected_candidates
        if descriptor["record_id"] not in selected_ids
    ]
    if normalized["unselected_candidate_records"] != expected_unselected:
        raise AttentionError(
            "unselected_candidate_records do not equal candidate descriptors"
        )
    expected_never_candidates = [
        descriptor
        for descriptor in canonical_descriptors
        if descriptor["record_id"] not in candidate_ids
    ]
    if normalized["never_candidate_records"] != expected_never_candidates:
        raise AttentionError(
            "never_candidate_records do not equal canonical descriptors"
        )
    intelligence = normalized["group_intelligence"]
    if (
        type(intelligence) is not dict
        or set(intelligence) != {
            "prompt_contract",
            "evaluation_digest",
            "group_assessment",
            "score_total",
            "score_mean_milli",
        }
    ):
        raise AttentionError("group_intelligence is invalid")
    prompt = validate_prompt_contract(intelligence["prompt_contract"])
    assessment = intelligence["group_assessment"]
    if (
        type(assessment) is not dict
        or set(assessment) != ASSESSMENT_KEYS
        or assessment["attention_state"] not in {"hot", "cold", "neutral"}
        or assessment["polarity"]
        not in {"positive", "negative", "neutral"}
        or assessment["mutation_recommendation"]
        not in {"promote", "hold", "revise", "suppress"}
        or type(assessment["reason"]) is not str
        or not assessment["reason"]
        or len(assessment["reason"]) > policy["max_reason_chars"]
    ):
        raise AttentionError("group assessment is invalid")
    _reject_secret_text(assessment["reason"], "group assessment reason")
    if normalized["prompt_digest"] != _digest(
        "rappterzoo/attention-prompt/1",
        prompt,
    ):
        raise AttentionError("group prompt_digest mismatch")
    evaluation = {
        "schema": EVALUATION_SCHEMA,
        "request_digest": normalized["request_digest"],
        "input_digest": normalized["input_digest"],
        "prompt_digest": normalized["prompt_digest"],
        "shard_id": normalized["shard_id"],
        "scope_digest": normalized["scope_digest"],
        "base_record_hash": normalized["base_record_hash"],
        "base_frame_hash": normalized["base_frame_hash"],
        "endpoint_identity_digest": normalized[
            "endpoint_identity_digest"
        ],
        "evaluation_axis": normalized["evaluation_axis"],
        "group_assessment": intelligence["group_assessment"],
        "selected": [
            {
                "record_id": item["record_id"],
                "record_digest": item["record_digest"],
                "score": item["score"],
                "reason": item["reason"],
            }
            for item in normalized["selected_records"]
        ],
    }
    if intelligence["evaluation_digest"] != _digest(
        "rappterzoo/attention-evaluation/1",
        evaluation,
    ):
        raise AttentionError("group evaluation_digest mismatch")
    score_total = sum(
        item["score"]
        for item in normalized["selected_records"]
    )
    if (
        intelligence["score_total"] != score_total
        or intelligence["score_mean_milli"]
        != score_total * 1000 // normalized["selected_count"]
    ):
        raise AttentionError("group intelligence score aggregate mismatch")
    _reject_private_keys(normalized, "attention group")
    return normalized


def _relative_attention_path(section: str, digest: str) -> str:
    return "attention/{}/{}.json".format(section, digest)


def apply_evaluation(
    request_value: Any,
    evaluation_value: Any,
    attention_dir: Path = ATTENTION_DIR,
    ledger_path: Path = ledger.LEDGER_PATH,
    projection_path: Path = ledger.PROJECTION_PATH,
    utc: Optional[str] = None,
) -> Dict[str, Any]:
    request = verify_request(request_value)
    evaluation = validate_evaluation(evaluation_value, request)
    descriptor_by_id = {
        item["record_id"]: item
        for item in request["record_descriptors"]
    }
    evaluation_by_id = {
        item["record_id"]: item
        for item in evaluation["selected"]
    }
    selected_ids = [
        item["record_id"]
        for item in evaluation["selected"]
    ]
    selected_records = []
    for record_id in selected_ids:
        result = evaluation_by_id[record_id]
        selected_records.append({
            **descriptor_by_id[record_id],
            "score": result["score"],
            "reason": result["reason"],
        })
    selected_id_set = set(selected_ids)
    candidate_id_set = set(request["candidate_record_ids"])
    candidate_records = [
        descriptor_by_id[record_id]
        for record_id in request["candidate_record_ids"]
    ]
    unselected_candidate_records = [
        descriptor
        for descriptor in candidate_records
        if descriptor["record_id"] not in selected_id_set
    ]
    never_candidate_records = [
        descriptor
        for descriptor in request["record_descriptors"]
        if descriptor["record_id"] not in candidate_id_set
    ]
    score_total = sum(
        item["score"]
        for item in evaluation["selected"]
    )
    group = {
        "schema": GROUP_SCHEMA,
        "group_object_digest": "",
        "group_id": request["group_id"],
        "shard_id": request["shard_id"],
        "scope_key": request["scope_key"],
        "scope_digest": request["scope_digest"],
        "base_record_hash": request["base_record_hash"],
        "base_frame_hash": request["base_frame_hash"],
        "endpoint_identity_digest": request["endpoint_identity_digest"],
        "evaluation_axis": request["evaluation_axis"],
        "provenance": request["provenance"],
        "request_id": request["request_id"],
        "request_digest": request["request_digest"],
        "input_digest": request["input_digest"],
        "prompt_digest": request["prompt_digest"],
        "policy_digest": request["policy_digest"],
        "policy": request["policy"],
        "scope": request["scope"],
        "total_group_count": request["total_group_count"],
        "candidate_count": request["candidate_count"],
        "candidate_budget": request["candidate_budget"],
        "attention_budget": request["attention_budget"],
        "selected_count": len(selected_ids),
        "record_descriptors": request["record_descriptors"],
        "candidate_records": candidate_records,
        "selected_records": selected_records,
        "unselected_candidate_records": unselected_candidate_records,
        "never_candidate_records": never_candidate_records,
        "group_intelligence": {
            "prompt_contract": request["prompt_contract"],
            "evaluation_digest": _digest(
                "rappterzoo/attention-evaluation/1",
                evaluation,
            ),
            "group_assessment": evaluation["group_assessment"],
            "score_total": score_total,
            "score_mean_milli": (
                score_total * 1000 // len(selected_ids)
            ),
        },
    }
    group["group_object_digest"] = _group_digest(group)
    group = verify_group_object(group)
    event_id = "attention-evaluation:{}".format(
        request["request_digest"]
    )
    for existing in ledger.read_frames(ledger_path):
        if existing["payload"]["event_id"] != event_id:
            continue
        if existing["payload"].get("group_object_digest") != group[
            "group_object_digest"
        ]:
            raise AttentionError(
                "attention request already has a different evaluation frame"
            )
    group_path = attention_dir / "groups" / "{}.json".format(
        group["group_object_digest"]
    )
    _write_immutable_json(group_path, group)
    payload = {
        "schema": ledger.PAYLOAD_SCHEMA,
        "event_id": event_id,
        "event": "attention-evaluation",
        "organism": "rappterzoo.attention",
        "display_name": "RappterZoo Attention Portal",
        "organism_type": "evaluation-frame",
        "neighborhood": "rappterzoo",
        "visibility": ledger.PUBLIC_VISIBILITY,
        "group_id": group["group_id"],
        "shard_id": group["shard_id"],
        "scope_key": group["scope_key"],
        "scope_digest": group["scope_digest"],
        "base_record_hash": group["base_record_hash"],
        "base_frame_hash": group["base_frame_hash"],
        "endpoint_identity_digest": group["endpoint_identity_digest"],
        "evaluation_axis": group["evaluation_axis"],
        "provenance_digest": _digest(
            "rappterzoo/attention-provenance/1",
            group["provenance"],
        ),
        "request_digest": group["request_digest"],
        "input_digest": group["input_digest"],
        "prompt_digest": group["prompt_digest"],
        "policy_digest": group["policy_digest"],
        "group_object_digest": group["group_object_digest"],
        "group_object_path": _relative_attention_path(
            "groups",
            group["group_object_digest"],
        ),
        "total_group_count": group["total_group_count"],
        "candidate_count": group["candidate_count"],
        "candidate_budget": group["candidate_budget"],
        "candidate_record_ids": request["candidate_record_ids"],
        "attention_budget": group["attention_budget"],
        "selected_count": group["selected_count"],
        "selected_record_ids": selected_ids,
    }
    frame = ledger.append_frame(
        "zoo.attention",
        payload,
        utc=utc,
        ledger_path=ledger_path,
        projection_path=projection_path,
    )
    return {
        "request": request,
        "evaluation": evaluation,
        "group": group,
        "group_path": group_path,
        "frame": frame,
    }


def _merge_key(group: Dict[str, Any]) -> Tuple[Any, ...]:
    return (
        group["base_record_hash"],
        group["evaluation_axis"],
        group["scope_digest"],
        group["shard_id"],
        group["group_id"],
        group["group_object_digest"],
    )


def _drift_classification(
    first: Dict[str, Any],
    second: Dict[str, Any],
) -> List[str]:
    drift = []
    first_assessment = first["group_intelligence"]["group_assessment"]
    second_assessment = second["group_intelligence"]["group_assessment"]
    if {
        first_assessment["attention_state"],
        second_assessment["attention_state"],
    } == {"hot", "cold"}:
        drift.append("hot-cold-selection")
    if {
        first_assessment["polarity"],
        second_assessment["polarity"],
    } == {"positive", "negative"}:
        drift.append("polarity")
    recommendation_rank = {
        "promote": 2,
        "hold": 0,
        "revise": -1,
        "suppress": -2,
    }
    first_rank = recommendation_rank[
        first_assessment["mutation_recommendation"]
    ]
    second_rank = recommendation_rank[
        second_assessment["mutation_recommendation"]
    ]
    if first_rank * second_rank < 0:
        drift.append("mutation-recommendation")
    if first["base_frame_hash"] != second["base_frame_hash"]:
        drift.append("base-frame-fork")
    return drift


def _dimension_digest(value: Dict[str, Any]) -> str:
    return _digest(
        "rappterzoo/attention-dimension/1",
        {
            key: item
            for key, item in value.items()
            if key != "dimension_object_digest"
        },
    )


def verify_dimension_object(value: Any) -> Dict[str, Any]:
    keys = {
        "schema",
        "dimension_object_digest",
        "base_record_hash",
        "base_frame_hashes",
        "branches",
        "drift_classification",
        "merge_metrics",
        "resolution",
    }
    dimension = _require_exact_keys(value, keys, "dimension object")
    try:
        normalized = ledger._normalize_json(dimension)
    except ledger.LedgerError as error:
        raise AttentionError(str(error)) from error
    if normalized["schema"] != DIMENSION_SCHEMA:
        raise AttentionError("dimension object has the wrong schema")
    _require_hash(normalized["base_record_hash"], "base_record_hash")
    _require_hash(
        normalized["dimension_object_digest"],
        "dimension_object_digest",
    )
    if normalized["dimension_object_digest"] != _dimension_digest(normalized):
        raise AttentionError("dimension object digest mismatch")
    frame_hashes = normalized["base_frame_hashes"]
    if (
        type(frame_hashes) is not list
        or not frame_hashes
        or frame_hashes != sorted(set(frame_hashes))
    ):
        raise AttentionError("dimension base_frame_hashes are invalid")
    for frame_hash in frame_hashes:
        _require_hash(frame_hash, "dimension base frame hash")
    branches = normalized["branches"]
    if type(branches) is not list or len(branches) < 2:
        raise AttentionError("dimension requires at least two branches")
    branch_digests = []
    for branch in branches:
        required = {
            "group_id",
            "group_object_digest",
            "group_object_path",
            "request_digest",
            "input_digest",
            "prompt_digest",
            "policy_digest",
            "shard_id",
            "scope_key",
            "scope_digest",
            "base_frame_hash",
            "endpoint_identity_digest",
            "evaluation_axis",
            "group_assessment",
            "selected_evidence",
        }
        _require_exact_keys(branch, required, "dimension branch")
        for key in (
            "group_object_digest",
            "request_digest",
            "input_digest",
            "prompt_digest",
            "policy_digest",
            "scope_digest",
            "base_frame_hash",
            "endpoint_identity_digest",
        ):
            _require_hash(branch[key], key)
        branch_digests.append(branch["group_object_digest"])
    if branch_digests != sorted(set(branch_digests)):
        raise AttentionError("dimension branch order is not deterministic")
    drift = normalized["drift_classification"]
    if (
        type(drift) is not list
        or not drift
        or drift != sorted(set(drift))
    ):
        raise AttentionError("dimension drift classification is invalid")
    metrics = normalized["merge_metrics"]
    if (
        type(metrics) is not dict
        or set(metrics) != {
            "comparison_count",
            "collision_count",
            "collision_rate_ppm",
            "rarity_gate",
        }
        or metrics["rarity_gate"]
        not in {"bootstrap", "rare-pass", "frequency-breach"}
    ):
        raise AttentionError("dimension merge metrics are invalid")
    resolution = normalized["resolution"]
    if resolution != {
        "mode": "carry-both",
        "chosen_group_object_digest": None,
    }:
        raise AttentionError("automatic dimensions must carry both branches")
    _reject_private_keys(normalized, "dimension object")
    return normalized


def merge_attention_groups(
    group_values: Iterable[Any],
    attention_dir: Path = ATTENTION_DIR,
    ledger_path: Path = ledger.LEDGER_PATH,
    projection_path: Path = ledger.PROJECTION_PATH,
    utc: Optional[str] = None,
) -> Dict[str, Any]:
    groups = [
        verify_group_object(value)
        for value in group_values
    ]
    if len(groups) != len({
        group["group_object_digest"]
        for group in groups
    }):
        raise AttentionError("merge input repeats a group object")
    groups.sort(key=_merge_key)
    shard_writers = {}
    for group in groups:
        prior = shard_writers.setdefault(
            group["shard_id"],
            group["endpoint_identity_digest"],
        )
        if prior != group["endpoint_identity_digest"]:
            raise AttentionError(
                "same shard contains outputs from different writers"
            )
    comparisons = []
    conflicts_by_base = {}
    for first_index, first in enumerate(groups):
        for second in groups[first_index + 1:]:
            if first["base_record_hash"] != second["base_record_hash"]:
                continue
            drift = _drift_classification(first, second)
            comparisons.append((first, second, drift))
            if drift:
                entry = conflicts_by_base.setdefault(
                    first["base_record_hash"],
                    {"groups": {}, "drift": set()},
                )
                entry["groups"][first["group_object_digest"]] = first
                entry["groups"][second["group_object_digest"]] = second
                entry["drift"].update(drift)
    collision_count = sum(1 for _, _, drift in comparisons if drift)
    comparison_count = len(comparisons)
    collision_rate_ppm = (
        collision_count * 1000000 // comparison_count
        if comparison_count
        else 0
    )
    policies = [group["policy"] for group in groups]
    gate_min = min(
        (
            policy["dimension_gate_min_comparisons"]
            for policy in policies
        ),
        default=1,
    )
    max_rate = min(
        (
            policy["dimension_max_collision_rate_ppm"]
            for policy in policies
        ),
        default=0,
    )
    if comparison_count < gate_min:
        rarity_gate = "bootstrap"
    elif collision_rate_ppm <= max_rate:
        rarity_gate = "rare-pass"
    else:
        rarity_gate = "frequency-breach"
    metrics = {
        "comparison_count": comparison_count,
        "collision_count": collision_count,
        "collision_rate_ppm": collision_rate_ppm,
        "rarity_gate": rarity_gate,
    }
    dimensions = []
    for base_record_hash in sorted(conflicts_by_base):
        conflict = conflicts_by_base[base_record_hash]
        branches = sorted(
            conflict["groups"].values(),
            key=lambda item: item["group_object_digest"],
        )
        branch_limit = min(
            group["policy"]["dimension_max_branches"]
            for group in branches
        )
        if len(branches) > branch_limit:
            raise AttentionError(
                "dimension branch count exceeds the rarity gate"
            )
        branch_objects = []
        for group in branches:
            branch_objects.append({
                "group_id": group["group_id"],
                "group_object_digest": group["group_object_digest"],
                "group_object_path": _relative_attention_path(
                    "groups",
                    group["group_object_digest"],
                ),
                "request_digest": group["request_digest"],
                "input_digest": group["input_digest"],
                "prompt_digest": group["prompt_digest"],
                "policy_digest": group["policy_digest"],
                "shard_id": group["shard_id"],
                "scope_key": group["scope_key"],
                "scope_digest": group["scope_digest"],
                "base_frame_hash": group["base_frame_hash"],
                "endpoint_identity_digest": group[
                    "endpoint_identity_digest"
                ],
                "evaluation_axis": group["evaluation_axis"],
                "group_assessment": group["group_intelligence"][
                    "group_assessment"
                ],
                "selected_evidence": [
                    {
                        "record_id": item["record_id"],
                        "record_digest": item["record_digest"],
                        "score": item["score"],
                        "reason": item["reason"],
                    }
                    for item in group["selected_records"]
                ],
            })
        dimension = {
            "schema": DIMENSION_SCHEMA,
            "dimension_object_digest": "",
            "base_record_hash": base_record_hash,
            "base_frame_hashes": sorted({
                group["base_frame_hash"]
                for group in branches
            }),
            "branches": branch_objects,
            "drift_classification": sorted(conflict["drift"]),
            "merge_metrics": metrics,
            "resolution": {
                "mode": "carry-both",
                "chosen_group_object_digest": None,
            },
        }
        dimension["dimension_object_digest"] = _dimension_digest(dimension)
        dimension = verify_dimension_object(dimension)
        dimension_path = attention_dir / "dimensions" / "{}.json".format(
            dimension["dimension_object_digest"]
        )
        _write_immutable_json(dimension_path, dimension)
        payload = {
            "schema": ledger.PAYLOAD_SCHEMA,
            "event_id": "attention-dimension:{}".format(
                dimension["dimension_object_digest"]
            ),
            "event": "dimension-reconciliation",
            "organism": "rappterzoo.attention",
            "display_name": "RappterZoo Attention Dimension",
            "organism_type": "dimension-reconciliation",
            "neighborhood": "rappterzoo",
            "visibility": ledger.PUBLIC_VISIBILITY,
            "base_record_hash": dimension["base_record_hash"],
            "base_frame_hashes": dimension["base_frame_hashes"],
            "dimension_object_digest": dimension[
                "dimension_object_digest"
            ],
            "dimension_object_path": _relative_attention_path(
                "dimensions",
                dimension["dimension_object_digest"],
            ),
            "branch_group_digests": [
                branch["group_object_digest"]
                for branch in dimension["branches"]
            ],
            "shard_ids": sorted({
                branch["shard_id"]
                for branch in dimension["branches"]
            }),
            "scope_digests": sorted({
                branch["scope_digest"]
                for branch in dimension["branches"]
            }),
            "endpoint_identity_digests": sorted({
                branch["endpoint_identity_digest"]
                for branch in dimension["branches"]
            }),
            "evaluation_axes": sorted({
                branch["evaluation_axis"]
                for branch in dimension["branches"]
            }),
            "drift_classification": dimension[
                "drift_classification"
            ],
            **metrics,
        }
        frame = ledger.append_frame(
            "zoo.dimension",
            payload,
            utc=utc,
            ledger_path=ledger_path,
            projection_path=projection_path,
        )
        dimensions.append({
            "dimension": dimension,
            "path": dimension_path,
            "frame": frame,
        })
    return {
        "ordered_group_digests": [
            group["group_object_digest"]
            for group in groups
        ],
        "metrics": metrics,
        "dimensions": dimensions,
    }


def _validate_privacy_policy(value: Any) -> Dict[str, Any]:
    policy = _require_exact_keys(
        value,
        {
            "visibility",
            "forbidden_classes",
            "persist_candidate_bodies",
        },
        "lease privacy policy",
    )
    try:
        normalized = ledger._normalize_json(policy)
    except ledger.LedgerError as error:
        raise AttentionError(str(error)) from error
    if normalized["visibility"] != ledger.PUBLIC_VISIBILITY:
        raise AttentionError("lease privacy must remain public-metadata")
    forbidden = normalized["forbidden_classes"]
    if (
        type(forbidden) is not list
        or not forbidden
        or forbidden != sorted(set(forbidden))
        or any(type(item) is not str or not item for item in forbidden)
    ):
        raise AttentionError("lease forbidden_classes are invalid")
    required = {
        "biometric",
        "credential",
        "godd",
        "private",
        "raw-media",
    }
    if not required.issubset(set(forbidden)):
        raise AttentionError("lease privacy omits a required forbidden class")
    if normalized["persist_candidate_bodies"] is not False:
        raise AttentionError("candidate bodies may not be persisted")
    return normalized


def _object_digest(domain: str, value: Dict[str, Any], key: str) -> str:
    return _digest(
        domain,
        {
            item_key: item_value
            for item_key, item_value in value.items()
            if item_key != key
        },
    )


def register_participant(
    registration_value: Any,
    attention_dir: Path = ATTENTION_DIR,
) -> Dict[str, Any]:
    keys = {
        "schema",
        "participant_ref",
        "participant_identity_ref",
        "endpoint_identity",
        "allowed_channels",
        "privacy_policy",
        "joined_at",
        "nonce",
    }
    registration = _require_exact_keys(
        registration_value,
        keys,
        "participant registration",
    )
    try:
        normalized = ledger._normalize_json(registration)
    except ledger.LedgerError as error:
        raise AttentionError(str(error)) from error
    if normalized["schema"] != PARTICIPANT_REGISTRATION_SCHEMA:
        raise AttentionError("participant registration has the wrong schema")
    participant_ref = _require_id(
        normalized["participant_ref"],
        "participant_ref",
    )
    identity_ref = normalized["participant_identity_ref"]
    if (
        type(identity_ref) is not str
        or not identity_ref
        or len(identity_ref) > 300
    ):
        raise AttentionError("participant_identity_ref is invalid")
    _reject_secret_text(identity_ref, "participant_identity_ref")
    channels = normalized["allowed_channels"]
    if (
        type(channels) is not list
        or not channels
        or channels != sorted(set(channels))
    ):
        raise AttentionError("allowed_channels must be sorted and unique")
    for channel in channels:
        _require_id(channel, "allowed channel")
    privacy = _validate_privacy_policy(normalized["privacy_policy"])
    try:
        joined_at = ledger.normalize_utc(normalized["joined_at"])
    except ledger.LedgerError as error:
        raise AttentionError(str(error)) from error
    _require_id(normalized["nonce"], "participant nonce")
    participant = {
        "schema": PARTICIPANT_SCHEMA,
        "participant_object_digest": "",
        "participant_ref": participant_ref,
        "participant_identity_ref": identity_ref,
        "participant_identity_digest": _digest(
            "rappterzoo/participant-identity/1",
            {"participant_identity_ref": identity_ref},
        ),
        "endpoint_identity_digest": _endpoint_identity_digest(
            normalized["endpoint_identity"]
        ),
        "allowed_channels": channels,
        "privacy_policy": privacy,
        "privacy_policy_digest": _digest(
            "rappterzoo/attention-privacy/1",
            privacy,
        ),
        "joined_at": joined_at,
        "nonce": normalized["nonce"],
        "trust_status": "application-registered-unverified",
    }
    participant["participant_object_digest"] = _object_digest(
        "rappterzoo/brainstem-participant/1",
        participant,
        "participant_object_digest",
    )
    path = attention_dir / "participants" / "{}.json".format(
        participant["participant_object_digest"]
    )
    _write_immutable_json(path, participant)
    return {"participant": participant, "path": path}


def revoke_participant(
    participant_object_digest: str,
    reason: str,
    revoked_at: str,
    nonce: str,
    attention_dir: Path = ATTENTION_DIR,
) -> Dict[str, Any]:
    _require_hash(participant_object_digest, "participant_object_digest")
    if type(reason) is not str or not reason or len(reason) > 500:
        raise AttentionError("revocation reason is invalid")
    _reject_secret_text(reason, "revocation reason")
    try:
        normalized_utc = ledger.normalize_utc(revoked_at)
    except ledger.LedgerError as error:
        raise AttentionError(str(error)) from error
    _require_id(nonce, "revocation nonce")
    participant_path = attention_dir / "participants" / "{}.json".format(
        participant_object_digest
    )
    participant = _load_json(participant_path)
    if participant.get("participant_object_digest") != participant_object_digest:
        raise AttentionError("participant object digest mismatch")
    revocation = {
        "schema": PARTICIPANT_REVOCATION_SCHEMA,
        "participant_object_digest": participant_object_digest,
        "participant_ref": participant["participant_ref"],
        "revoked_at": normalized_utc,
        "reason": reason,
        "nonce": nonce,
    }
    path = attention_dir / "revocations" / "{}.json".format(
        participant_object_digest
    )
    _write_immutable_json(path, revocation)
    return {"revocation": revocation, "path": path}


def _load_active_participant(
    attention_dir: Path,
    participant_digest: str,
) -> Dict[str, Any]:
    _require_hash(participant_digest, "participant_object_digest")
    path = attention_dir / "participants" / "{}.json".format(
        participant_digest
    )
    participant = _load_json(path)
    expected = _object_digest(
        "rappterzoo/brainstem-participant/1",
        participant,
        "participant_object_digest",
    )
    if (
        participant.get("participant_object_digest") != participant_digest
        or expected != participant_digest
    ):
        raise AttentionError("participant object digest mismatch")
    if (attention_dir / "revocations" / "{}.json".format(
        participant_digest
    )).exists():
        raise AttentionError("participant is revoked")
    return participant


def request_shard_lease(
    request_value: Any,
    attention_dir: Path = ATTENTION_DIR,
) -> Dict[str, Any]:
    keys = {
        "schema",
        "participant_object_digest",
        "attention_request_digest",
        "channel",
        "allowed_actions",
        "max_outputs",
        "max_bytes",
        "valid_from",
        "valid_until",
        "nonce",
        "idempotency_key",
    }
    request = _require_exact_keys(
        request_value,
        keys,
        "shard lease request",
    )
    try:
        normalized = ledger._normalize_json(request)
    except ledger.LedgerError as error:
        raise AttentionError(str(error)) from error
    if normalized["schema"] != LEASE_REQUEST_SCHEMA:
        raise AttentionError("lease request has the wrong schema")
    participant = _load_active_participant(
        attention_dir,
        normalized["participant_object_digest"],
    )
    _require_hash(
        normalized["attention_request_digest"],
        "attention_request_digest",
    )
    channel = _require_id(normalized["channel"], "lease channel")
    if channel not in participant["allowed_channels"]:
        raise AttentionError("participant is unauthorized for this channel")
    actions = normalized["allowed_actions"]
    if (
        type(actions) is not list
        or not actions
        or actions != sorted(set(actions))
        or not set(actions).issubset({"evaluate"})
    ):
        raise AttentionError("lease actions are invalid")
    for key in ("max_outputs", "max_bytes"):
        if type(normalized[key]) is not int or normalized[key] < 1:
            raise AttentionError("lease {} is invalid".format(key))
    try:
        valid_from = ledger.normalize_utc(normalized["valid_from"])
        valid_until = ledger.normalize_utc(normalized["valid_until"])
    except ledger.LedgerError as error:
        raise AttentionError(str(error)) from error
    if valid_from >= valid_until:
        raise AttentionError("lease validity interval is invalid")
    _require_id(normalized["nonce"], "lease nonce")
    _require_id(normalized["idempotency_key"], "lease idempotency_key")
    lease_request = {
        **normalized,
        "valid_from": valid_from,
        "valid_until": valid_until,
        "lease_request_digest": "",
    }
    lease_request["lease_request_digest"] = _object_digest(
        "rappterzoo/shard-lease-request/1",
        lease_request,
        "lease_request_digest",
    )
    path = attention_dir / "lease-requests" / "{}.json".format(
        lease_request["lease_request_digest"]
    )
    _write_immutable_json(path, lease_request)
    return {"lease_request": lease_request, "path": path}


def _verify_lease_request(value: Any) -> Dict[str, Any]:
    keys = {
        "schema",
        "participant_object_digest",
        "attention_request_digest",
        "channel",
        "allowed_actions",
        "max_outputs",
        "max_bytes",
        "valid_from",
        "valid_until",
        "nonce",
        "idempotency_key",
        "lease_request_digest",
    }
    request = _require_exact_keys(value, keys, "stored lease request")
    expected = _object_digest(
        "rappterzoo/shard-lease-request/1",
        request,
        "lease_request_digest",
    )
    if (
        request["schema"] != LEASE_REQUEST_SCHEMA
        or request["lease_request_digest"] != expected
    ):
        raise AttentionError("lease request digest mismatch")
    return request


def assign_shard_lease(
    lease_request_value: Any,
    attention_request_value: Any,
    ledger_path: Path = ledger.LEDGER_PATH,
    attention_dir: Path = ATTENTION_DIR,
) -> Dict[str, Any]:
    lease_request = _verify_lease_request(lease_request_value)
    participant = _load_active_participant(
        attention_dir,
        lease_request["participant_object_digest"],
    )
    request = verify_request(attention_request_value)
    if lease_request.get("schema") != LEASE_REQUEST_SCHEMA:
        raise AttentionError("lease request has the wrong schema")
    if lease_request.get("attention_request_digest") != request[
        "request_digest"
    ]:
        raise AttentionError("lease request targets another attention request")
    if participant["endpoint_identity_digest"] != request[
        "endpoint_identity_digest"
    ]:
        raise AttentionError("participant is not the assigned shard writer")
    if lease_request["max_outputs"] > request["attention_budget"]:
        raise AttentionError("lease max_outputs exceeds attention budget")
    if lease_request["max_bytes"] > MAX_EVALUATION_BYTES:
        raise AttentionError("lease max_bytes exceeds evaluator limit")
    frames = ledger.read_frames(ledger_path)
    head = frames[-1] if frames else None
    if frames and request["base_frame_hash"] not in {
        frame["frame_hash"]
        for frame in frames
    }:
        raise AttentionError("attention request base frame is not in main stream")
    if not frames and request["base_frame_hash"] != "0" * 64:
        raise AttentionError("genesis attention request needs a null base hash")
    base_head_seq = head["seq"] if head else -1
    base_head_hash = head["frame_hash"] if head else "0" * 64
    descriptor_by_id = {
        item["record_id"]: item
        for item in request["record_descriptors"]
    }
    allowed_records = [
        {
            "record_id": record_id,
            "record_digest": descriptor_by_id[record_id]["record_digest"],
        }
        for record_id in request["candidate_record_ids"]
    ]
    privacy = participant["privacy_policy"]
    lease = {
        "schema": LEASE_SCHEMA,
        "lease_id": "",
        "lease_digest": "",
        "trust_status": "application-candidate-lease-unverified",
        "participant_ref": participant["participant_ref"],
        "participant_identity_ref": participant[
            "participant_identity_ref"
        ],
        "participant_object_digest": participant[
            "participant_object_digest"
        ],
        "participant_identity_digest": participant[
            "participant_identity_digest"
        ],
        "endpoint_identity_digest": participant[
            "endpoint_identity_digest"
        ],
        "shard_id": request["shard_id"],
        "channel": lease_request["channel"],
        "scope_key": request["scope_key"],
        "scope_digest": request["scope_digest"],
        "attention_request_digest": request["request_digest"],
        "allowed_records": allowed_records,
        "allowed_actions": lease_request["allowed_actions"],
        "base_record_hash": request["base_record_hash"],
        "base_frame_hash": request["base_frame_hash"],
        "base_head_seq": base_head_seq,
        "base_head_hash": base_head_hash,
        "max_outputs": lease_request["max_outputs"],
        "max_bytes": lease_request["max_bytes"],
        "valid_from": lease_request["valid_from"],
        "valid_until": lease_request["valid_until"],
        "nonce": lease_request["nonce"],
        "idempotency_key": lease_request["idempotency_key"],
        "privacy_policy": privacy,
        "privacy_policy_digest": participant["privacy_policy_digest"],
    }
    lease["lease_digest"] = _digest(
        "rappterzoo/shard-capability-lease/1",
        {
            key: value
            for key, value in lease.items()
            if key not in {"lease_id", "lease_digest"}
        },
    )
    lease["lease_id"] = "candidate-lease:{}".format(
        lease["lease_digest"]
    )
    lease_path = attention_dir / "leases" / "{}.json".format(
        lease["lease_digest"]
    )
    assignment_path = attention_dir / "assignments" / (
        "shard-{}.json".format(
            hashlib.sha256(
                request["shard_id"].encode("utf-8")
            ).hexdigest()
        )
    )
    assignment = {
        "schema": "rappterzoo-shard-assignment/1",
        "shard_id": request["shard_id"],
        "channel": lease["channel"],
        "lease_digest": lease["lease_digest"],
        "participant_ref": lease["participant_ref"],
        "participant_object_digest": lease[
            "participant_object_digest"
        ],
        "participant_identity_ref": lease[
            "participant_identity_ref"
        ],
        "participant_identity_digest": lease[
            "participant_identity_digest"
        ],
        "endpoint_identity_digest": lease[
            "endpoint_identity_digest"
        ],
        "scope_key": lease["scope_key"],
        "scope_digest": lease["scope_digest"],
        "attention_request_digest": lease[
            "attention_request_digest"
        ],
        "allowed_records": lease["allowed_records"],
        "allowed_actions": lease["allowed_actions"],
        "base_record_hash": lease["base_record_hash"],
        "base_frame_hash": lease["base_frame_hash"],
        "base_head_seq": lease["base_head_seq"],
        "base_head_hash": lease["base_head_hash"],
        "max_outputs": lease["max_outputs"],
        "max_bytes": lease["max_bytes"],
        "valid_from": lease["valid_from"],
        "valid_until": lease["valid_until"],
        "nonce": lease["nonce"],
        "idempotency_key": lease["idempotency_key"],
        "privacy_policy": lease["privacy_policy"],
        "privacy_policy_digest": lease["privacy_policy_digest"],
    }
    if assignment_path.exists():
        current = _load_json(assignment_path)
        if current != assignment:
            if lease["valid_from"] <= current["valid_until"]:
                raise AttentionError(
                    "shard already has a different current lease"
                )
    _write_immutable_json(lease_path, lease)
    if assignment_path.exists():
        if _load_json(assignment_path) != assignment:
            ledger._atomic_json(assignment_path, assignment)
    else:
        _write_immutable_json(assignment_path, assignment)
    return {
        "lease": lease,
        "lease_path": lease_path,
        "assignment_path": assignment_path,
    }


def _load_lease(attention_dir: Path, lease_digest: str) -> Dict[str, Any]:
    _require_hash(lease_digest, "lease_digest")
    path = attention_dir / "leases" / "{}.json".format(lease_digest)
    lease = _load_json(path)
    expected = _digest(
        "rappterzoo/shard-capability-lease/1",
        {
            key: value
            for key, value in lease.items()
            if key not in {"lease_id", "lease_digest"}
        },
    )
    if (
        lease.get("lease_digest") != lease_digest
        or lease.get("lease_digest") != expected
        or lease.get("lease_id") != "candidate-lease:{}".format(expected)
    ):
        raise AttentionError("lease digest mismatch")
    return lease


def _leading_zero_bits(value: bytes) -> int:
    count = 0
    for byte in value:
        if byte == 0:
            count += 8
            continue
        count += 8 - byte.bit_length()
        break
    return count


def validate_frame_control_config(value: Any) -> Dict[str, Any]:
    config = _require_exact_keys(
        value,
        {
            "schema",
            "mode",
            "assigned_folding",
            "live_election",
            "synthetic_proofs",
            "description",
            "activation_gate",
            "claims",
        },
        "frame-control config",
    )
    try:
        normalized = ledger._normalize_json(config)
    except ledger.LedgerError as error:
        raise AttentionError(str(error)) from error
    if normalized["schema"] != FRAME_CONTROL_CONFIG_SCHEMA:
        raise AttentionError("frame-control config has the wrong schema")
    if normalized["mode"] not in {
        "observer",
        "assigned",
        "proof-of-fold",
    }:
        raise AttentionError("frame-control mode is invalid")
    if normalized["synthetic_proofs"] != "tests-only":
        raise AttentionError("synthetic proofs must remain tests-only")
    claims = normalized["claims"]
    if claims != {
        "compute_incentive": "none",
        "consensus": "none",
        "currency": "none",
        "decentralized_authority": "not-established",
        "mining": "none",
        "publisher_authority": "centralized-main-assembler",
        "token": "none",
    }:
        raise AttentionError("frame-control config overstates authority")
    gate = normalized["activation_gate"]
    if (
        type(gate) is not dict
        or set(gate) != {
            "owner_authorized",
            "required_evidence",
            "status",
        }
        or type(gate["required_evidence"]) is not dict
        or set(gate["required_evidence"]) != {
            "bounded_cost",
            "fork_free_lineage",
            "public_soak_complete",
            "replay_tamper_resistance",
            "subscriber_witness_evidence",
        }
    ):
        raise AttentionError("frame-control activation gate is invalid")
    if normalized["mode"] == "observer":
        if (
            normalized["live_election"] != "disabled"
            or normalized["assigned_folding"] != "disabled"
            or gate["owner_authorized"] is not False
            or gate["status"] != "not-authorized"
        ):
            raise AttentionError("observer mode permits replication only")
    elif normalized["mode"] == "assigned":
        if (
            normalized["live_election"] != "disabled"
            or normalized["assigned_folding"] != "enabled"
            or gate["owner_authorized"] is not False
            or gate["status"] != "not-authorized"
        ):
            raise AttentionError("assigned mode cannot activate proof races")
    else:
        if (
            normalized["live_election"] != "enabled"
            or normalized["assigned_folding"] != "enabled"
            or gate["owner_authorized"] is not True
            or gate["status"] != "owner-authorized"
            or not all(gate["required_evidence"].values())
        ):
            raise AttentionError("active frame control lacks its future gate")
    return normalized


def _load_frame_control_config(
    path: Path = DEFAULT_FRAME_CONTROL_PATH,
) -> Dict[str, Any]:
    return validate_frame_control_config(_load_json(path))


def adaptive_fold_difficulty(
    requested_bits: Optional[int] = None,
    previous_attempts: Optional[int] = None,
    target_attempts: int = 64,
) -> int:
    if type(target_attempts) is not int or not 8 <= target_attempts <= 4096:
        raise AttentionError("proof-of-fold target_attempts is invalid")
    if requested_bits is None:
        bits = max(
            FOLD_MIN_DIFFICULTY_BITS,
            min(
                FOLD_MAX_DIFFICULTY_BITS,
                target_attempts.bit_length() - 1,
            ),
        )
    else:
        if type(requested_bits) is not int:
            raise AttentionError("proof-of-fold difficulty must be an integer")
        bits = requested_bits
    if previous_attempts is not None:
        if type(previous_attempts) is not int or previous_attempts < 0:
            raise AttentionError("previous proof attempts are invalid")
        if previous_attempts < target_attempts // 2:
            bits += 1
        elif previous_attempts > target_attempts * 2:
            bits -= 1
    if not FOLD_MIN_DIFFICULTY_BITS <= bits <= FOLD_MAX_DIFFICULTY_BITS:
        raise AttentionError("proof-of-fold difficulty exceeds bounded limits")
    return bits


def _load_fold_challenge(
    attention_dir: Path,
    challenge_digest: str,
) -> Dict[str, Any]:
    _require_hash(challenge_digest, "challenge_digest")
    path = attention_dir / "control" / "challenges" / "{}.json".format(
        challenge_digest
    )
    challenge = _load_json(path)
    expected = _object_digest(
        "rappterzoo/proof-of-fold-challenge/1",
        challenge,
        "challenge_digest",
    )
    if (
        challenge.get("schema") != FOLD_CHALLENGE_SCHEMA
        or challenge.get("challenge_digest") != expected
    ):
        raise AttentionError("proof-of-fold challenge digest mismatch")
    return challenge


def create_fold_challenge(
    shard_id: str,
    channel: str,
    action_kind: str,
    epoch: int,
    control_frame: int,
    fresh_nonce: str,
    issued_at: str,
    expires_at: str,
    attention_dir: Path = ATTENTION_DIR,
    ledger_path: Path = ledger.LEDGER_PATH,
    projection_path: Path = ledger.PROJECTION_PATH,
    requested_difficulty_bits: Optional[int] = None,
    previous_attempts: Optional[int] = None,
    target_attempts: int = 64,
    max_submissions_per_participant: int = 4,
    synthetic_test: bool = False,
    frame_control_path: Path = DEFAULT_FRAME_CONTROL_PATH,
) -> Dict[str, Any]:
    config = _load_frame_control_config(frame_control_path)
    if config["mode"] != "proof-of-fold" and not synthetic_test:
        raise AttentionError(
            "proof-of-fold election is disabled in public soak mode"
        )
    execution_mode = (
        "synthetic-test" if synthetic_test else "active-owner-authorized"
    )
    _require_id(shard_id, "challenge shard_id")
    _require_id(channel, "challenge channel")
    _require_id(action_kind, "challenge action_kind")
    _require_id(fresh_nonce, "challenge fresh_nonce")
    if type(epoch) is not int or epoch < 0:
        raise AttentionError("challenge epoch is invalid")
    if type(control_frame) is not int or control_frame < 0:
        raise AttentionError("challenge control_frame is invalid")
    if (
        type(max_submissions_per_participant) is not int
        or not 1 <= max_submissions_per_participant <= 32
    ):
        raise AttentionError("challenge submission rate limit is invalid")
    try:
        issued = ledger.normalize_utc(issued_at)
        expires = ledger.normalize_utc(expires_at)
    except ledger.LedgerError as error:
        raise AttentionError(str(error)) from error
    issued_moment = datetime.fromisoformat(issued.replace("Z", "+00:00"))
    expires_moment = datetime.fromisoformat(expires.replace("Z", "+00:00"))
    lifetime = (expires_moment - issued_moment).total_seconds()
    if not 1 <= lifetime <= 300:
        raise AttentionError("challenge lifetime must be 1-300 seconds")
    difficulty_bits = adaptive_fold_difficulty(
        requested_difficulty_bits,
        previous_attempts,
        target_attempts,
    )
    frames = ledger.read_frames(ledger_path)
    head = frames[-1] if frames else None
    base_head_seq = head["seq"] if head else -1
    base_head_hash = head["frame_hash"] if head else "0" * 64
    challenge = {
        "schema": FOLD_CHALLENGE_SCHEMA,
        "challenge_digest": "",
        "trust_status": "application-frame-control-unverified",
        "control_model": "proof-of-fold-frame-election",
        "execution_mode": execution_mode,
        "frame_control_config_digest": _digest(
            "rappterzoo/frame-control-config/1",
            config,
        ),
        "soak_gate_status": config["activation_gate"]["status"],
        "authority_model": "centralized-main-assembler",
        "consensus_model": "none",
        "economic_model": "none",
        "base_head_seq": base_head_seq,
        "base_head_hash": base_head_hash,
        "epoch": epoch,
        "control_frame": control_frame,
        "shard_id": shard_id,
        "channel": channel,
        "action_kind": action_kind,
        "fresh_nonce": fresh_nonce,
        "difficulty_bits": difficulty_bits,
        "target_attempts": target_attempts,
        "max_work_iterations": min(1 << (difficulty_bits + 4), 65536),
        "max_submissions_per_participant": (
            max_submissions_per_participant
        ),
        "issued_at": issued,
        "expires_at": expires,
        "adaptation": {
            "previous_attempts": previous_attempts,
            "minimum_bits": FOLD_MIN_DIFFICULTY_BITS,
            "maximum_bits": FOLD_MAX_DIFFICULTY_BITS,
        },
    }
    challenge["challenge_digest"] = _object_digest(
        "rappterzoo/proof-of-fold-challenge/1",
        challenge,
        "challenge_digest",
    )
    path = attention_dir / "control" / "challenges" / "{}.json".format(
        challenge["challenge_digest"]
    )
    nonce_digest = _digest(
        "rappterzoo/proof-of-fold-fresh-nonce/1",
        {"fresh_nonce": fresh_nonce},
    )
    nonce_path = attention_dir / "control" / "challenge-nonces" / (
        "{}.json".format(nonce_digest)
    )
    nonce_record = {
        "schema": "rappterzoo-proof-of-fold-nonce-use/1",
        "nonce_digest": nonce_digest,
        "challenge_digest": challenge["challenge_digest"],
    }
    if nonce_path.exists() and _load_json(nonce_path) != nonce_record:
        raise AttentionError("proof-of-fold fresh nonce was already used")
    _write_immutable_json(path, challenge)
    _write_immutable_json(nonce_path, nonce_record)
    payload = {
        "schema": ledger.PAYLOAD_SCHEMA,
        "event_id": "fold-challenge:{}".format(
            challenge["challenge_digest"]
        ),
        "event": "fold-challenge",
        "organism": "rappterzoo.attention",
        "visibility": ledger.PUBLIC_VISIBILITY,
        "challenge_digest": challenge["challenge_digest"],
        "challenge_path": (
            "attention/control/challenges/{}.json".format(
                challenge["challenge_digest"]
            )
        ),
        "base_head_seq": base_head_seq,
        "base_head_hash": base_head_hash,
        "epoch": epoch,
        "control_frame": control_frame,
        "shard_id": shard_id,
        "channel": channel,
        "action_kind": action_kind,
        "difficulty_bits": difficulty_bits,
        "max_work_iterations": challenge["max_work_iterations"],
        "issued_at": issued,
        "expires_at": expires,
        "control_model": "application-frame-control-election",
        "execution_mode": execution_mode,
        "frame_control_config_digest": challenge[
            "frame_control_config_digest"
        ],
        "soak_gate_status": challenge["soak_gate_status"],
        "consensus_model": "none",
        "economic_model": "none",
    }
    frame = ledger.append_frame(
        "zoo.challenge",
        payload,
        utc=issued,
        ledger_path=ledger_path,
        projection_path=projection_path,
    )
    return {"challenge": challenge, "path": path, "frame": frame}


def fold_proof_hash(challenge_digest: str, proof_nonce: int) -> str:
    _require_hash(challenge_digest, "challenge_digest")
    if type(proof_nonce) is not int or proof_nonce < 0:
        raise AttentionError("proof_nonce is invalid")
    return hashlib.sha256(
        b"rappterzoo/proof-of-fold/1\n"
        + challenge_digest.encode("ascii")
        + b"\n"
        + str(proof_nonce).encode("ascii")
    ).hexdigest()


def submit_fold_proof(
    submission_value: Any,
    attention_dir: Path = ATTENTION_DIR,
) -> Dict[str, Any]:
    keys = {
        "schema",
        "challenge_digest",
        "participant_object_digest",
        "base_head_hash",
        "shard_id",
        "channel",
        "action_kind",
        "proof_nonce",
        "submitted_at",
        "attempt_nonce",
    }
    submission = _require_exact_keys(
        submission_value,
        keys,
        "proof-of-fold submission",
    )
    if submission["schema"] != "rappterzoo-proof-of-fold-submission/1":
        raise AttentionError("proof submission has the wrong schema")
    challenge = _load_fold_challenge(
        attention_dir,
        submission["challenge_digest"],
    )
    participant = _load_active_participant(
        attention_dir,
        submission["participant_object_digest"],
    )
    for key in ("base_head_hash", "shard_id", "channel", "action_kind"):
        if submission[key] != challenge[key]:
            raise AttentionError("proof submission {} mismatch".format(key))
    try:
        submitted = ledger.normalize_utc(submission["submitted_at"])
    except ledger.LedgerError as error:
        raise AttentionError(str(error)) from error
    if not challenge["issued_at"] <= submitted <= challenge["expires_at"]:
        raise AttentionError("proof submission is late or premature")
    _require_id(submission["attempt_nonce"], "proof attempt_nonce")
    proof_nonce = submission["proof_nonce"]
    if (
        type(proof_nonce) is not int
        or proof_nonce < 0
        or proof_nonce >= challenge["max_work_iterations"]
    ):
        raise AttentionError("proof nonce exceeds bounded work budget")
    participant_digest = participant["participant_object_digest"]
    attempt_dir = (
        attention_dir
        / "control"
        / "attempts"
        / challenge["challenge_digest"]
        / participant_digest
    )
    existing_attempts = sorted(attempt_dir.glob("*.json"))
    if len(existing_attempts) >= challenge[
        "max_submissions_per_participant"
    ]:
        raise AttentionError("proof submission rate limit exceeded")
    proof_hash = fold_proof_hash(
        challenge["challenge_digest"],
        proof_nonce,
    )
    valid = _leading_zero_bits(bytes.fromhex(proof_hash)) >= challenge[
        "difficulty_bits"
    ]
    attempt = {
        "schema": FOLD_ATTEMPT_SCHEMA,
        "attempt_digest": "",
        "challenge_digest": challenge["challenge_digest"],
        "participant_ref": participant["participant_ref"],
        "participant_object_digest": participant_digest,
        "participant_identity_digest": participant[
            "participant_identity_digest"
        ],
        "base_head_hash": challenge["base_head_hash"],
        "shard_id": challenge["shard_id"],
        "channel": challenge["channel"],
        "action_kind": challenge["action_kind"],
        "proof_nonce": proof_nonce,
        "proof_hash": proof_hash,
        "difficulty_bits": challenge["difficulty_bits"],
        "submitted_at": submitted,
        "attempt_nonce": submission["attempt_nonce"],
        "valid": valid,
    }
    attempt["attempt_digest"] = _object_digest(
        "rappterzoo/proof-of-fold-attempt/1",
        attempt,
        "attempt_digest",
    )
    attempt_path = attempt_dir / "{}.json".format(attempt["attempt_digest"])
    _write_immutable_json(attempt_path, attempt)
    if valid:
        proof_use_path = (
            attention_dir
            / "control"
            / "proof-uses"
            / challenge["challenge_digest"]
            / "{}.json".format(proof_hash)
        )
        proof_use = {
            "schema": "rappterzoo-proof-of-fold-use/1",
            "challenge_digest": challenge["challenge_digest"],
            "proof_hash": proof_hash,
            "attempt_digest": attempt["attempt_digest"],
        }
        if proof_use_path.exists():
            raise AttentionError("valid proof was already submitted")
        _write_immutable_json(proof_use_path, proof_use)
    if not valid:
        raise AttentionError("invalid proof-of-fold")
    return {"attempt": attempt, "path": attempt_path}


def _load_fold_award(
    attention_dir: Path,
    award_digest: str,
) -> Dict[str, Any]:
    _require_hash(award_digest, "control_award_digest")
    path = attention_dir / "control" / "awards" / "{}.json".format(
        award_digest
    )
    award = _load_json(path)
    expected = _object_digest(
        "rappterzoo/frame-control-award/1",
        award,
        "award_digest",
    )
    if award.get("award_digest") != expected:
        raise AttentionError("frame-control award digest mismatch")
    return award


def award_fold_challenge(
    challenge_digest: str,
    awarded_at: str,
    action_lease_seconds: int = 30,
    attention_dir: Path = ATTENTION_DIR,
    ledger_path: Path = ledger.LEDGER_PATH,
    projection_path: Path = ledger.PROJECTION_PATH,
) -> Dict[str, Any]:
    challenge = _load_fold_challenge(attention_dir, challenge_digest)
    try:
        awarded = ledger.normalize_utc(awarded_at)
    except ledger.LedgerError as error:
        raise AttentionError(str(error)) from error
    if awarded > challenge["expires_at"]:
        raise AttentionError("challenge expired before award")
    if not 1 <= action_lease_seconds <= 120:
        raise AttentionError("action lease lifetime is invalid")
    attempts_root = (
        attention_dir
        / "control"
        / "attempts"
        / challenge_digest
    )
    attempts = []
    if attempts_root.exists():
        for path in sorted(attempts_root.glob("*/*.json")):
            attempt = _load_json(path)
            if attempt.get("valid") is True:
                attempts.append(attempt)
    if not attempts:
        raise AttentionError("challenge has no valid proof")
    attempts.sort(key=lambda item: (
        item["submitted_at"],
        item["proof_hash"],
        item["participant_object_digest"],
        item["attempt_digest"],
    ))
    winner = attempts[0]
    same_time_count = sum(
        1
        for item in attempts
        if item["submitted_at"] == winner["submitted_at"]
    )
    award_index_path = (
        attention_dir
        / "control"
        / "challenge-awards"
        / "{}.json".format(challenge_digest)
    )
    if award_index_path.exists():
        index = _load_json(award_index_path)
        award = _load_fold_award(
            attention_dir,
            index["award_digest"],
        )
        return {
            "award": award,
            "path": attention_dir / "control" / "awards" / (
                award["award_digest"] + ".json"
            ),
            "frame": None,
        }
    awarded_moment = datetime.fromisoformat(awarded.replace("Z", "+00:00"))
    challenge_expiry = datetime.fromisoformat(
        challenge["expires_at"].replace("Z", "+00:00")
    )
    lease_expiry = min(
        challenge_expiry,
        awarded_moment + timedelta(seconds=action_lease_seconds),
    )
    award = {
        "schema": FOLD_AWARD_SCHEMA,
        "award_digest": "",
        "trust_status": "application-frame-control-unverified",
        "challenge_digest": challenge_digest,
        "execution_mode": challenge["execution_mode"],
        "frame_control_config_digest": challenge[
            "frame_control_config_digest"
        ],
        "soak_gate_status": challenge["soak_gate_status"],
        "winner_participant_object_digest": winner[
            "participant_object_digest"
        ],
        "winner_participant_identity_digest": winner[
            "participant_identity_digest"
        ],
        "winner_attempt_digest": winner["attempt_digest"],
        "winner_proof_hash": winner["proof_hash"],
        "base_head_seq": challenge["base_head_seq"],
        "base_head_hash": challenge["base_head_hash"],
        "epoch": challenge["epoch"],
        "control_frame": challenge["control_frame"],
        "shard_id": challenge["shard_id"],
        "channel": challenge["channel"],
        "action_kind": challenge["action_kind"],
        "awarded_at": awarded,
        "valid_until": ledger.normalize_utc(lease_expiry.isoformat()),
        "tie_break": {
            "algorithm": (
                "submitted-at-proof-hash-participant-digest-attempt-digest"
            ),
            "same_time_valid_proofs": same_time_count,
        },
        "authority_model": "centralized-main-assembler",
        "consensus_model": "none",
        "economic_model": "none",
    }
    award["award_digest"] = _object_digest(
        "rappterzoo/frame-control-award/1",
        award,
        "award_digest",
    )
    path = attention_dir / "control" / "awards" / "{}.json".format(
        award["award_digest"]
    )
    _write_immutable_json(path, award)
    _write_immutable_json(award_index_path, {
        "schema": "rappterzoo-frame-control-award-index/1",
        "challenge_digest": challenge_digest,
        "execution_mode": award["execution_mode"],
        "frame_control_config_digest": award[
            "frame_control_config_digest"
        ],
        "soak_gate_status": award["soak_gate_status"],
        "award_digest": award["award_digest"],
    })
    payload = {
        "schema": ledger.PAYLOAD_SCHEMA,
        "event_id": "fold-award:{}".format(award["award_digest"]),
        "event": "fold-control-award",
        "organism": "rappterzoo.attention",
        "visibility": ledger.PUBLIC_VISIBILITY,
        "award_digest": award["award_digest"],
        "award_path": "attention/control/awards/{}.json".format(
            award["award_digest"]
        ),
        "challenge_digest": challenge_digest,
        "execution_mode": challenge["execution_mode"],
        "frame_control_config_digest": challenge[
            "frame_control_config_digest"
        ],
        "soak_gate_status": challenge["soak_gate_status"],
        "winner_participant_object_digest": award[
            "winner_participant_object_digest"
        ],
        "winner_proof_hash": award["winner_proof_hash"],
        "base_head_hash": award["base_head_hash"],
        "epoch": award["epoch"],
        "control_frame": award["control_frame"],
        "shard_id": award["shard_id"],
        "channel": award["channel"],
        "action_kind": award["action_kind"],
        "valid_until": award["valid_until"],
        "control_model": "application-frame-control-election",
        "consensus_model": "none",
        "economic_model": "none",
    }
    frame = ledger.append_frame(
        "zoo.control-award",
        payload,
        utc=awarded,
        ledger_path=ledger_path,
        projection_path=projection_path,
    )
    return {"award": award, "path": path, "frame": frame}


def expire_fold_challenge(
    challenge_digest: str,
    expired_at: str,
    reason: str,
    attention_dir: Path = ATTENTION_DIR,
    ledger_path: Path = ledger.LEDGER_PATH,
    projection_path: Path = ledger.PROJECTION_PATH,
) -> Dict[str, Any]:
    challenge = _load_fold_challenge(attention_dir, challenge_digest)
    expired = ledger.normalize_utc(expired_at)
    if expired <= challenge["expires_at"]:
        raise AttentionError("challenge has not expired")
    award_index = (
        attention_dir
        / "control"
        / "challenge-awards"
        / "{}.json".format(challenge_digest)
    )
    if award_index.exists():
        raise AttentionError("awarded challenge cannot expire unawarded")
    if type(reason) is not str or not reason or len(reason) > 300:
        raise AttentionError("expiry reason is invalid")
    expiry = {
        "schema": FOLD_EXPIRY_SCHEMA,
        "expiry_digest": "",
        "challenge_digest": challenge_digest,
        "execution_mode": challenge["execution_mode"],
        "frame_control_config_digest": challenge[
            "frame_control_config_digest"
        ],
        "soak_gate_status": challenge["soak_gate_status"],
        "base_head_hash": challenge["base_head_hash"],
        "epoch": challenge["epoch"],
        "control_frame": challenge["control_frame"],
        "shard_id": challenge["shard_id"],
        "channel": challenge["channel"],
        "action_kind": challenge["action_kind"],
        "expired_at": expired,
        "reason": reason,
        "disposition": "eligible-for-fresh-nonce-reaward",
    }
    expiry["expiry_digest"] = _object_digest(
        "rappterzoo/frame-control-expiry/1",
        expiry,
        "expiry_digest",
    )
    path = attention_dir / "control" / "expiries" / "{}.json".format(
        expiry["expiry_digest"]
    )
    _write_immutable_json(path, expiry)
    frame = ledger.append_frame(
        "zoo.control-expiry",
        {
            "schema": ledger.PAYLOAD_SCHEMA,
            "event_id": "fold-expiry:{}".format(expiry["expiry_digest"]),
            "event": "fold-control-expiry",
            "organism": "rappterzoo.attention",
            "visibility": ledger.PUBLIC_VISIBILITY,
            "expiry_digest": expiry["expiry_digest"],
            "expiry_path": "attention/control/expiries/{}.json".format(
                expiry["expiry_digest"]
            ),
            "challenge_digest": challenge_digest,
            "execution_mode": challenge["execution_mode"],
            "frame_control_config_digest": challenge[
                "frame_control_config_digest"
            ],
            "soak_gate_status": challenge["soak_gate_status"],
            "base_head_hash": challenge["base_head_hash"],
            "epoch": challenge["epoch"],
            "control_frame": challenge["control_frame"],
            "shard_id": challenge["shard_id"],
            "channel": challenge["channel"],
            "action_kind": challenge["action_kind"],
            "reason": reason,
            "control_model": "application-frame-control-election",
            "consensus_model": "none",
            "economic_model": "none",
        },
        utc=expired,
        ledger_path=ledger_path,
        projection_path=projection_path,
    )
    return {"expiry": expiry, "path": path, "frame": frame}


def submit_candidate_result(
    lease_digest: str,
    control_award_digest: Optional[str],
    evaluation_value: Any,
    submitted_at: str,
    submission_nonce: str,
    submission_idempotency_key: str,
    attention_dir: Path = ATTENTION_DIR,
    frame_control_path: Path = DEFAULT_FRAME_CONTROL_PATH,
) -> Dict[str, Any]:
    config = _load_frame_control_config(frame_control_path)
    if config["mode"] == "observer":
        raise AttentionError("observer mode permits replication only")
    lease = _load_lease(attention_dir, lease_digest)
    _load_active_participant(
        attention_dir,
        lease["participant_object_digest"],
    )
    request_path = attention_dir / "requests" / "{}.json".format(
        lease["attention_request_digest"]
    )
    request = verify_request(_load_json(request_path))
    evaluation = validate_evaluation(evaluation_value, request)
    try:
        submitted_utc = ledger.normalize_utc(submitted_at)
    except ledger.LedgerError as error:
        raise AttentionError(str(error)) from error
    if not lease["valid_from"] <= submitted_utc <= lease["valid_until"]:
        raise AttentionError("candidate lease is expired or not yet valid")
    award = None
    if control_award_digest is None:
        if config["mode"] != "assigned":
            raise AttentionError("proof-of-fold mode requires a winner award")
        frame_control_mode = "assigned"
        winner_proof_hash = None
    else:
        award = _load_fold_award(attention_dir, control_award_digest)
        if (
            config["mode"] != "proof-of-fold"
            and award["execution_mode"] != "synthetic-test"
        ):
            raise AttentionError("winner awards are disabled in assigned mode")
        if not award["awarded_at"] <= submitted_utc <= award["valid_until"]:
            raise AttentionError(
                "frame-control award is expired or not yet valid"
            )
        if (
            award["winner_participant_object_digest"]
            != lease["participant_object_digest"]
            or award["shard_id"] != lease["shard_id"]
            or award["channel"] != lease["channel"]
            or award["action_kind"] not in lease["allowed_actions"]
        ):
            raise AttentionError(
                "candidate is not authorized by frame-control award"
            )
        usage_path = attention_dir / "control" / "award-uses" / (
            "{}.json".format(control_award_digest)
        )
        if usage_path.exists():
            raise AttentionError("frame-control award was already consumed")
        frame_control_mode = (
            "synthetic-test-proof-of-fold"
            if award["execution_mode"] == "synthetic-test"
            else "proof-of-fold"
        )
        winner_proof_hash = award["winner_proof_hash"]
    if evaluation["shard_id"] != lease["shard_id"]:
        raise AttentionError("candidate result targets an unauthorized shard")
    if evaluation["scope_digest"] != lease["scope_digest"]:
        raise AttentionError("candidate result escaped its allowed scope")
    allowed_ids = {
        item["record_id"]
        for item in lease["allowed_records"]
    }
    selected_ids = {
        item["record_id"]
        for item in evaluation["selected"]
    }
    if not selected_ids.issubset(allowed_ids):
        raise AttentionError("candidate result escaped allowed records")
    if len(evaluation["selected"]) > lease["max_outputs"]:
        raise AttentionError("candidate result exceeds max_outputs")
    encoded_evaluation = ledger.canonical_bytes(evaluation)
    if len(encoded_evaluation) > lease["max_bytes"]:
        raise AttentionError("candidate result exceeds max_bytes")
    _require_id(submission_nonce, "submission nonce")
    _require_id(
        submission_idempotency_key,
        "submission idempotency_key",
    )
    candidate = {
        "schema": CANDIDATE_RESULT_SCHEMA,
        "candidate_result_digest": "",
        "trust_status": "application-candidate-unverified",
        "lease_id": lease["lease_id"],
        "lease_digest": lease["lease_digest"],
        "participant_ref": lease["participant_ref"],
        "participant_identity_ref": lease[
            "participant_identity_ref"
        ],
        "participant_object_digest": lease["participant_object_digest"],
        "participant_identity_digest": lease[
            "participant_identity_digest"
        ],
        "endpoint_identity_digest": lease[
            "endpoint_identity_digest"
        ],
        "shard_id": lease["shard_id"],
        "channel": lease["channel"],
        "scope_key": lease["scope_key"],
        "scope_digest": lease["scope_digest"],
        "base_record_hash": lease["base_record_hash"],
        "base_frame_hash": lease["base_frame_hash"],
        "base_head_seq": lease["base_head_seq"],
        "base_head_hash": lease["base_head_hash"],
        "attention_request_digest": lease[
            "attention_request_digest"
        ],
        "evaluation": evaluation,
        "output_count": len(evaluation["selected"]),
        "output_bytes": len(encoded_evaluation),
        "submitted_at": submitted_utc,
        "submission_nonce": submission_nonce,
        "submission_idempotency_key": submission_idempotency_key,
        "privacy_policy_digest": lease["privacy_policy_digest"],
        "wire_protocol": "brainstem:/chat",
        "control_award_digest": control_award_digest,
        "winner_proof_hash": winner_proof_hash,
        "frame_control_mode": frame_control_mode,
    }
    candidate["candidate_result_digest"] = _object_digest(
        "rappterzoo/candidate-shard-result/1",
        candidate,
        "candidate_result_digest",
    )
    key_digest = _digest(
        "rappterzoo/candidate-submission-key/1",
        {
            "lease_digest": lease["lease_digest"],
            "submission_idempotency_key": submission_idempotency_key,
        },
    )
    key_path = attention_dir / "submission-keys" / "{}.json".format(
        key_digest
    )
    key_record = {
        "schema": "rappterzoo-candidate-submission-key/1",
        "key_digest": key_digest,
        "candidate_result_digest": candidate["candidate_result_digest"],
    }
    if key_path.exists() and _load_json(key_path) != key_record:
        raise AttentionError("submission idempotency key was already used")
    candidate_path = attention_dir / "submissions" / "{}.json".format(
        candidate["candidate_result_digest"]
    )
    _write_immutable_json(candidate_path, candidate)
    _write_immutable_json(key_path, key_record)
    return {"candidate": candidate, "path": candidate_path}


def _increment_utc(value: str, milliseconds: int) -> str:
    moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return ledger.normalize_utc(
        (moment + timedelta(milliseconds=milliseconds)).isoformat()
    )


def _verify_candidate_result(value: Any) -> Dict[str, Any]:
    candidate = _require_exact_keys(
        value,
        CANDIDATE_RESULT_KEYS,
        "candidate result",
    )
    try:
        normalized = ledger._normalize_json(candidate)
    except ledger.LedgerError as error:
        raise AttentionError(str(error)) from error
    if normalized["schema"] != CANDIDATE_RESULT_SCHEMA:
        raise AttentionError("candidate result has the wrong schema")
    if normalized["trust_status"] != "application-candidate-unverified":
        raise AttentionError("candidate result overstates its trust")
    if normalized["wire_protocol"] != "brainstem:/chat":
        raise AttentionError("candidate result used an unsupported wire")
    for key in (
        "candidate_result_digest",
        "lease_digest",
        "participant_object_digest",
        "participant_identity_digest",
        "endpoint_identity_digest",
        "scope_digest",
        "base_record_hash",
        "base_frame_hash",
        "base_head_hash",
        "attention_request_digest",
        "privacy_policy_digest",
    ):
        _require_hash(normalized[key], key)
    if normalized["frame_control_mode"] == "assigned":
        if (
            normalized["control_award_digest"] is not None
            or normalized["winner_proof_hash"] is not None
        ):
            raise AttentionError("assigned candidate must not claim a winner")
    elif normalized["frame_control_mode"] in {
        "proof-of-fold",
        "synthetic-test-proof-of-fold",
    }:
        _require_hash(
            normalized["control_award_digest"],
            "control_award_digest",
        )
        _require_hash(normalized["winner_proof_hash"], "winner_proof_hash")
    else:
        raise AttentionError("candidate frame_control_mode is invalid")
    expected = _object_digest(
        "rappterzoo/candidate-shard-result/1",
        normalized,
        "candidate_result_digest",
    )
    if normalized["candidate_result_digest"] != expected:
        raise AttentionError("candidate result digest mismatch")
    if (
        type(normalized["output_count"]) is not int
        or normalized["output_count"] < 1
        or type(normalized["output_bytes"]) is not int
        or normalized["output_bytes"] < 1
        or type(normalized["base_head_seq"]) is not int
        or normalized["base_head_seq"] < -1
    ):
        raise AttentionError("candidate result bounds are invalid")
    _reject_private_keys(normalized, "candidate result")
    return normalized


def _claim_assigned_lease(
    attention_dir: Path,
    lease: Dict[str, Any],
    candidate: Dict[str, Any],
) -> Path:
    claim = {
        "schema": "rappterzoo-assigned-lease-claim/1",
        "lease_digest": lease["lease_digest"],
        "participant_object_digest": lease[
            "participant_object_digest"
        ],
        "shard_id": lease["shard_id"],
        "scope_digest": lease["scope_digest"],
        "base_head_hash": lease["base_head_hash"],
        "candidate_result_digest": candidate["candidate_result_digest"],
        "submission_idempotency_key": candidate[
            "submission_idempotency_key"
        ],
    }
    path = attention_dir / "control" / "assigned-lease-claims" / (
        "{}.json".format(lease["lease_digest"])
    )
    _write_immutable_json(path, claim)
    return path


def _assemble_candidate_results_locked(
    candidate_values: Iterable[Any],
    assembled_utc: str,
    attention_dir: Path = ATTENTION_DIR,
    ledger_path: Path = ledger.LEDGER_PATH,
    projection_path: Path = ledger.PROJECTION_PATH,
    frame_control_path: Path = DEFAULT_FRAME_CONTROL_PATH,
) -> Dict[str, Any]:
    config = _load_frame_control_config(frame_control_path)
    if config["mode"] == "observer":
        raise AttentionError("observer mode permits replication only")
    try:
        assembly_start = ledger.normalize_utc(assembled_utc)
    except ledger.LedgerError as error:
        raise AttentionError(str(error)) from error
    candidates = []
    for value in candidate_values:
        candidates.append(_verify_candidate_result(value))
    if len(candidates) != len({
        item["candidate_result_digest"]
        for item in candidates
    }):
        raise AttentionError("assembler input repeats a candidate result")
    candidates.sort(key=lambda item: (
        item["base_head_seq"],
        item["shard_id"],
        item["scope_digest"],
        item["candidate_result_digest"],
    ))
    frames_before = ledger.read_frames(ledger_path)
    accepted = []
    replayed = []
    for index, candidate in enumerate(candidates):
        assembly_path = attention_dir / "assemblies" / "{}.json".format(
            candidate["candidate_result_digest"]
        )
        if assembly_path.exists():
            replayed.append(_load_json(assembly_path))
            continue
        lease = _load_lease(attention_dir, candidate["lease_digest"])
        award = None
        if candidate["frame_control_mode"] == "assigned":
            if config["mode"] != "assigned":
                raise AttentionError("assigned candidate is not enabled")
        else:
            award = _load_fold_award(
                attention_dir,
                candidate["control_award_digest"],
            )
            if (
                config["mode"] != "proof-of-fold"
                and award["execution_mode"] != "synthetic-test"
            ):
                raise AttentionError("proof-of-fold candidate is disabled")
        participant = _load_active_participant(
            attention_dir,
            lease["participant_object_digest"],
        )
        if participant["participant_object_digest"] != candidate[
            "participant_object_digest"
        ]:
            raise AttentionError("candidate participant is unauthorized")
        if not lease["valid_from"] <= assembly_start <= lease["valid_until"]:
            raise AttentionError("candidate lease expired before assembly")
        if candidate["submitted_at"] > assembly_start:
            raise AttentionError("candidate submission is from the future")
        award_usage_path = None
        assigned_usage_path = None
        if award is not None:
            if not award["awarded_at"] <= assembly_start <= award["valid_until"]:
                raise AttentionError(
                    "frame-control award expired before assembly"
                )
            if (
                award["winner_participant_object_digest"]
                != participant["participant_object_digest"]
                or award["winner_proof_hash"] != candidate["winner_proof_hash"]
                or award["shard_id"] != lease["shard_id"]
                or award["channel"] != lease["channel"]
                or award["action_kind"] not in lease["allowed_actions"]
            ):
                raise AttentionError(
                    "candidate winner lacks frame-control authority"
                )
            award_usage_path = (
                attention_dir
                / "control"
                / "award-uses"
                / "{}.json".format(award["award_digest"])
            )
            if award_usage_path.exists():
                raise AttentionError(
                    "frame-control award was already consumed"
                )
        else:
            assigned_usage_path = (
                attention_dir
                / "control"
                / "assigned-lease-uses"
                / "{}.json".format(lease["lease_digest"])
            )
            if assigned_usage_path.exists():
                raise AttentionError("assigned shard lease was already consumed")
            _claim_assigned_lease(attention_dir, lease, candidate)
        assignment_path = attention_dir / "assignments" / (
            "shard-{}.json".format(
                hashlib.sha256(
                    lease["shard_id"].encode("utf-8")
                ).hexdigest()
            )
        )
        assignment = _load_json(assignment_path)
        if assignment.get("lease_digest") != lease["lease_digest"]:
            raise AttentionError("candidate lease is not the current assignment")
        base_seq = lease["base_head_seq"]
        if base_seq == -1:
            if lease["base_head_hash"] != "0" * 64:
                raise AttentionError("candidate genesis base is invalid")
        elif (
            base_seq >= len(frames_before)
            or frames_before[base_seq]["frame_hash"]
            != lease["base_head_hash"]
        ):
            raise AttentionError("candidate base head is not in the main stream")
        if award is not None:
            award_base_seq = award["base_head_seq"]
            if award_base_seq == -1:
                if award["base_head_hash"] != "0" * 64:
                    raise AttentionError("award genesis base is invalid")
            elif (
                award_base_seq >= len(frames_before)
                or frames_before[award_base_seq]["frame_hash"]
                != award["base_head_hash"]
            ):
                raise AttentionError(
                    "award base head is not in the main stream"
                )
        request_path = attention_dir / "requests" / "{}.json".format(
            lease["attention_request_digest"]
        )
        request = verify_request(_load_json(request_path))
        evaluation = validate_evaluation(
            candidate["evaluation"],
            request,
        )
        if (
            candidate["shard_id"] != lease["shard_id"]
            or candidate["channel"] != lease["channel"]
            or candidate["scope_digest"] != lease["scope_digest"]
            or candidate["base_record_hash"] != lease["base_record_hash"]
            or candidate["base_frame_hash"] != lease["base_frame_hash"]
            or candidate["base_head_hash"] != lease["base_head_hash"]
            or candidate["attention_request_digest"]
            != lease["attention_request_digest"]
            or candidate["participant_identity_digest"]
            != lease["participant_identity_digest"]
            or candidate["endpoint_identity_digest"]
            != lease["endpoint_identity_digest"]
            or candidate["privacy_policy_digest"]
            != lease["privacy_policy_digest"]
            or candidate["wire_protocol"] != "brainstem:/chat"
        ):
            raise AttentionError("candidate result escaped its capability lease")
        if candidate["output_count"] != len(evaluation["selected"]):
            raise AttentionError("candidate output_count mismatch")
        if candidate["output_bytes"] != len(
            ledger.canonical_bytes(evaluation)
        ):
            raise AttentionError("candidate output_bytes mismatch")
        result = apply_evaluation(
            request,
            evaluation,
            attention_dir=attention_dir,
            ledger_path=ledger_path,
            projection_path=projection_path,
            utc=_increment_utc(assembly_start, len(accepted) * 2),
        )
        if award is not None:
            action_payload = {
                "schema": ledger.PAYLOAD_SCHEMA,
                "event_id": "fold-action:{}".format(
                    award["award_digest"]
                ),
                "event": "fold-control-action",
                "organism": "rappterzoo.attention",
                "visibility": ledger.PUBLIC_VISIBILITY,
                "award_digest": award["award_digest"],
                "challenge_digest": award["challenge_digest"],
                "execution_mode": award["execution_mode"],
                "frame_control_config_digest": award[
                    "frame_control_config_digest"
                ],
                "soak_gate_status": award["soak_gate_status"],
                "winner_participant_object_digest": award[
                    "winner_participant_object_digest"
                ],
                "winner_proof_hash": award["winner_proof_hash"],
                "shard_id": award["shard_id"],
                "channel": award["channel"],
                "action_kind": award["action_kind"],
                "accepted_result_frame_seq": result["frame"]["seq"],
                "accepted_result_frame_hash": result["frame"]["frame_hash"],
                "group_object_digest": result["group"][
                    "group_object_digest"
                ],
                "control_model": "application-frame-control-election",
                "consensus_model": "none",
                "economic_model": "none",
            }
        else:
            action_payload = {
                "schema": ledger.PAYLOAD_SCHEMA,
                "event_id": "assigned-action:{}".format(
                    candidate["candidate_result_digest"]
                ),
                "event": "assigned-control-action",
                "organism": "rappterzoo.attention",
                "visibility": ledger.PUBLIC_VISIBILITY,
                "lease_digest": lease["lease_digest"],
                "candidate_result_digest": candidate[
                    "candidate_result_digest"
                ],
                "participant_object_digest": participant[
                    "participant_object_digest"
                ],
                "shard_id": lease["shard_id"],
                "channel": lease["channel"],
                "action_kind": "evaluate",
                "accepted_result_frame_seq": result["frame"]["seq"],
                "accepted_result_frame_hash": result["frame"]["frame_hash"],
                "group_object_digest": result["group"][
                    "group_object_digest"
                ],
                "control_model": "application-assigned-shard-control",
                "consensus_model": "none",
                "economic_model": "none",
            }
        action_frame = ledger.append_frame(
            "zoo.control-action",
            action_payload,
            utc=_increment_utc(
                assembly_start,
                len(accepted) * 2 + 1,
            ),
            ledger_path=ledger_path,
            projection_path=projection_path,
        )
        if award is not None:
            _write_immutable_json(award_usage_path, {
                "schema": "rappterzoo-frame-control-action-use/1",
                "award_digest": award["award_digest"],
                "candidate_result_digest": candidate[
                    "candidate_result_digest"
                ],
                "accepted_result_frame_hash": result["frame"]["frame_hash"],
                "action_receipt_frame_hash": action_frame["frame_hash"],
            })
        else:
            _write_immutable_json(assigned_usage_path, {
                "schema": "rappterzoo-assigned-shard-action-use/1",
                "lease_digest": lease["lease_digest"],
                "candidate_result_digest": candidate[
                    "candidate_result_digest"
                ],
                "accepted_result_frame_hash": result["frame"]["frame_hash"],
                "action_receipt_frame_hash": action_frame["frame_hash"],
            })
        assembly_receipt = {
            "schema": ASSEMBLY_RECEIPT_SCHEMA,
            "candidate_result_digest": candidate[
                "candidate_result_digest"
            ],
            "lease_digest": lease["lease_digest"],
            "participant_object_digest": participant[
                "participant_object_digest"
            ],
            "group_object_digest": result["group"][
                "group_object_digest"
            ],
            "frame_seq": result["frame"]["seq"],
            "frame_hash": result["frame"]["frame_hash"],
            "action_receipt_frame_seq": action_frame["seq"],
            "action_receipt_frame_hash": action_frame["frame_hash"],
            "assembled_at": _increment_utc(
                assembly_start,
                len(accepted),
            ),
            "acceptance": "application-validated-structural-unverified",
        }
        _write_immutable_json(assembly_path, assembly_receipt)
        accepted.append({
            "candidate": candidate,
            "assembly_receipt": assembly_receipt,
            "group": result["group"],
            "frame": result["frame"],
            "action_frame": action_frame,
        })
    all_groups = [
        verify_group_object(_load_json(path))
        for path in sorted((attention_dir / "groups").glob("*.json"))
    ] if (attention_dir / "groups").exists() else []
    merge = merge_attention_groups(
        all_groups,
        attention_dir=attention_dir,
        ledger_path=ledger_path,
        projection_path=projection_path,
        utc=_increment_utc(assembly_start, len(accepted) * 2),
    ) if all_groups else {
        "ordered_group_digests": [],
        "metrics": {
            "comparison_count": 0,
            "collision_count": 0,
            "collision_rate_ppm": 0,
            "rarity_gate": "bootstrap",
        },
        "dimensions": [],
    }
    return {
        "accepted": accepted,
        "replayed": replayed,
        "merge": merge,
    }


def assemble_candidate_results(
    candidate_values: Iterable[Any],
    assembled_utc: str,
    attention_dir: Path = ATTENTION_DIR,
    ledger_path: Path = ledger.LEDGER_PATH,
    projection_path: Path = ledger.PROJECTION_PATH,
    frame_control_path: Path = DEFAULT_FRAME_CONTROL_PATH,
) -> Dict[str, Any]:
    assembler_lock = attention_dir / "control" / "main-assembler"
    with ledger._ledger_lock(assembler_lock):
        return _assemble_candidate_results_locked(
            candidate_values,
            assembled_utc,
            attention_dir=attention_dir,
            ledger_path=ledger_path,
            projection_path=projection_path,
            frame_control_path=frame_control_path,
        )


def _load_group_by_digest(
    attention_dir: Path,
    digest: str,
) -> Tuple[Dict[str, Any], Path]:
    _require_hash(digest, "group_object_digest")
    path = attention_dir / "groups" / "{}.json".format(digest)
    group = verify_group_object(_load_json(path))
    if group["group_object_digest"] != digest:
        raise AttentionError("group filename and digest disagree")
    return group, path


def _load_dimension_by_digest(
    attention_dir: Path,
    digest: str,
) -> Tuple[Dict[str, Any], Path]:
    _require_hash(digest, "dimension_object_digest")
    path = attention_dir / "dimensions" / "{}.json".format(digest)
    dimension = verify_dimension_object(_load_json(path))
    if dimension["dimension_object_digest"] != digest:
        raise AttentionError("dimension filename and digest disagree")
    return dimension, path


def _dimensions_for_group(
    attention_dir: Path,
    group_digest: str,
) -> List[Dict[str, Any]]:
    directory = attention_dir / "dimensions"
    if not directory.exists():
        return []
    matches = []
    for path in sorted(directory.glob("*.json")):
        dimension = verify_dimension_object(_load_json(path))
        if group_digest in {
            branch["group_object_digest"]
            for branch in dimension["branches"]
        }:
            matches.append(dimension)
    return matches


def validate_receipt(value: Any) -> Dict[str, Any]:
    receipt = _require_exact_keys(value, RECEIPT_KEYS, "mutation receipt")
    try:
        normalized = ledger._normalize_json(receipt)
    except ledger.LedgerError as error:
        raise AttentionError(str(error)) from error
    if normalized["schema"] != RECEIPT_SCHEMA:
        raise AttentionError("mutation receipt has the wrong schema")
    if normalized["run_kind"] not in {"mutation", "delta"}:
        raise AttentionError("receipt run_kind must be mutation or delta")
    _require_id(normalized["mutation_id"], "mutation_id")
    for key in (
        "group_object_digest",
        "attention_frame_hash",
        "output_digest",
        "mutation_prompt_digest",
    ):
        _require_hash(normalized[key], key)
    if (
        type(normalized["attention_frame_seq"]) is not int
        or normalized["attention_frame_seq"] < 0
    ):
        raise AttentionError("attention_frame_seq is invalid")
    consumed = normalized["consumed_record_ids"]
    if (
        type(consumed) is not list
        or not consumed
        or len(consumed) != len(set(consumed))
    ):
        raise AttentionError("consumed_record_ids must be unique and non-empty")
    for record_id in consumed:
        _require_id(record_id, "consumed record_id")
    if (
        type(normalized["output_media_type"]) is not str
        or not MEDIA_TYPE_RE.fullmatch(normalized["output_media_type"])
    ):
        raise AttentionError("output_media_type is invalid")
    dimension_digest = normalized["dimension_object_digest"]
    dimension_mode = normalized["dimension_mode"]
    branches = normalized["dimension_branch_group_digests"]
    if dimension_mode not in {"none", "chosen", "carry-both"}:
        raise AttentionError("dimension_mode is invalid")
    if (
        type(branches) is not list
        or len(branches) != len(set(branches))
    ):
        raise AttentionError("dimension branch digests are invalid")
    for digest in branches:
        _require_hash(digest, "dimension branch group digest")
    if dimension_mode == "none":
        if dimension_digest is not None or branches:
            raise AttentionError("dimension none mode must not carry branches")
    else:
        _require_hash(dimension_digest, "dimension_object_digest")
        if len(branches) < 2:
            raise AttentionError("dimension receipt must carry its branches")
    _reject_private_keys(normalized, "mutation receipt")
    return normalized


def _receipt_digest(receipt_object: Dict[str, Any]) -> str:
    return _digest(
        "rappterzoo/mutation-receipt/1",
        {
            key: value
            for key, value in receipt_object.items()
            if key != "receipt_object_digest"
        },
    )


def record_mutation_receipt(
    receipt_value: Any,
    attention_dir: Path = ATTENTION_DIR,
    ledger_path: Path = ledger.LEDGER_PATH,
    projection_path: Path = ledger.PROJECTION_PATH,
    utc: Optional[str] = None,
) -> Dict[str, Any]:
    receipt = validate_receipt(receipt_value)
    group, group_path = _load_group_by_digest(
        attention_dir,
        receipt["group_object_digest"],
    )
    frames = ledger.read_frames(ledger_path)
    seq = receipt["attention_frame_seq"]
    if seq >= len(frames):
        raise AttentionError("attention frame sequence is unavailable")
    attention_frame = frames[seq]
    if (
        attention_frame["frame_hash"] != receipt["attention_frame_hash"]
        or attention_frame["kind"] != "zoo.attention"
        or attention_frame["payload"].get("event")
        != "attention-evaluation"
        or attention_frame["payload"].get("group_object_digest")
        != group["group_object_digest"]
        or attention_frame["payload"].get("request_digest")
        != group["request_digest"]
    ):
        raise AttentionError("attention frame lineage does not match group")
    selected_ids = {
        item["record_id"]
        for item in group["selected_records"]
    }
    dimensions = _dimensions_for_group(
        attention_dir,
        group["group_object_digest"],
    )
    dimension = None
    if receipt["dimension_mode"] == "none":
        if dimensions:
            raise AttentionError(
                "dimension reconciliation must be referenced downstream"
            )
    else:
        dimension, _ = _load_dimension_by_digest(
            attention_dir,
            receipt["dimension_object_digest"],
        )
        branch_digests = [
            branch["group_object_digest"]
            for branch in dimension["branches"]
        ]
        if group["group_object_digest"] not in branch_digests:
            raise AttentionError("dimension does not contain the source group")
        if receipt["dimension_branch_group_digests"] != branch_digests:
            raise AttentionError("receipt does not carry every dimension branch")
        if receipt["dimension_mode"] == "chosen":
            chosen = dimension["resolution"][
                "chosen_group_object_digest"
            ]
            if chosen is None or chosen != group["group_object_digest"]:
                raise AttentionError("dimension has no matching chosen branch")
        else:
            selected_ids = {
                evidence["record_id"]
                for branch in dimension["branches"]
                for evidence in branch["selected_evidence"]
            }
    consumed_ids = set(receipt["consumed_record_ids"])
    if not consumed_ids.issubset(selected_ids):
        raise AttentionError(
            "receipt references raw or unselected record IDs"
        )
    receipt_object = {
        "schema": RECEIPT_OBJECT_SCHEMA,
        "receipt_object_digest": "",
        "run_kind": receipt["run_kind"],
        "mutation_id": receipt["mutation_id"],
        "group_id": group["group_id"],
        "shard_id": group["shard_id"],
        "scope_digest": group["scope_digest"],
        "base_record_hash": group["base_record_hash"],
        "base_frame_hash": group["base_frame_hash"],
        "endpoint_identity_digest": group["endpoint_identity_digest"],
        "evaluation_axis": group["evaluation_axis"],
        "group_object_digest": group["group_object_digest"],
        "group_object_path": _relative_attention_path(
            "groups",
            group["group_object_digest"],
        ),
        "request_digest": group["request_digest"],
        "attention_frame_seq": attention_frame["seq"],
        "attention_frame_hash": attention_frame["frame_hash"],
        "consumed_record_ids": receipt["consumed_record_ids"],
        "output_digest": receipt["output_digest"],
        "output_media_type": receipt["output_media_type"],
        "mutation_prompt_digest": receipt["mutation_prompt_digest"],
        "dimension_object_digest": receipt["dimension_object_digest"],
        "dimension_mode": receipt["dimension_mode"],
        "dimension_branch_group_digests": receipt[
            "dimension_branch_group_digests"
        ],
    }
    receipt_object["receipt_object_digest"] = _receipt_digest(
        receipt_object
    )
    event_id = "attention-{}:{}".format(
        receipt["run_kind"],
        receipt["mutation_id"],
    )
    for existing in frames:
        if existing["payload"]["event_id"] != event_id:
            continue
        if existing["payload"].get("receipt_object_digest") != receipt_object[
            "receipt_object_digest"
        ]:
            raise AttentionError(
                "mutation_id already has a different receipt frame"
            )
    receipt_path = attention_dir / "receipts" / "{}.json".format(
        receipt_object["receipt_object_digest"]
    )
    _write_immutable_json(receipt_path, receipt_object)
    event = "{}-receipt".format(receipt["run_kind"])
    payload = {
        "schema": ledger.PAYLOAD_SCHEMA,
        "event_id": event_id,
        "event": event,
        "organism": "rappterzoo.attention",
        "display_name": "RappterZoo Attention Portal",
        "organism_type": "mutation-receipt",
        "neighborhood": "rappterzoo",
        "visibility": ledger.PUBLIC_VISIBILITY,
        "run_kind": receipt["run_kind"],
        "mutation_id": receipt["mutation_id"],
        "group_id": group["group_id"],
        "shard_id": group["shard_id"],
        "scope_digest": group["scope_digest"],
        "base_record_hash": group["base_record_hash"],
        "base_frame_hash": group["base_frame_hash"],
        "endpoint_identity_digest": group["endpoint_identity_digest"],
        "evaluation_axis": group["evaluation_axis"],
        "group_object_digest": group["group_object_digest"],
        "attention_frame_seq": attention_frame["seq"],
        "attention_frame_hash": attention_frame["frame_hash"],
        "consumed_record_ids": receipt["consumed_record_ids"],
        "output_digest": receipt["output_digest"],
        "output_media_type": receipt["output_media_type"],
        "mutation_prompt_digest": receipt["mutation_prompt_digest"],
        "dimension_object_digest": receipt["dimension_object_digest"],
        "dimension_mode": receipt["dimension_mode"],
        "dimension_branch_group_digests": receipt[
            "dimension_branch_group_digests"
        ],
        "receipt_object_digest": receipt_object["receipt_object_digest"],
        "receipt_object_path": _relative_attention_path(
            "receipts",
            receipt_object["receipt_object_digest"],
        ),
    }
    kind = (
        "zoo.mutation"
        if receipt["run_kind"] == "mutation"
        else "zoo.delta"
    )
    frame = ledger.append_frame(
        kind,
        payload,
        utc=utc,
        ledger_path=ledger_path,
        projection_path=projection_path,
    )
    return {
        "group": group,
        "group_path": group_path,
        "receipt": receipt_object,
        "receipt_path": receipt_path,
        "attention_frame": attention_frame,
        "frame": frame,
    }


def _print_result(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))


def _path(value: str) -> Path:
    return Path(value).expanduser().resolve()


def main() -> int:
    parser = argparse.ArgumentParser(prog="attention-portal")
    subparsers = parser.add_subparsers(dest="command", required=True)

    join_parser = subparsers.add_parser("join")
    join_group = join_parser.add_mutually_exclusive_group(required=True)
    join_group.add_argument("--registration")
    join_group.add_argument("--revoke-participant-digest")
    join_parser.add_argument("--reason")
    join_parser.add_argument("--revoked-at")
    join_parser.add_argument("--nonce")
    join_parser.add_argument("--attention-dir", default=str(ATTENTION_DIR))

    request_parser = subparsers.add_parser("request")
    request_parser.add_argument("--request", required=True)
    request_parser.add_argument("--attention-dir", default=str(ATTENTION_DIR))

    assign_parser = subparsers.add_parser("assign")
    assign_parser.add_argument("--lease-request", required=True)
    assign_parser.add_argument("--attention-request", required=True)
    assign_parser.add_argument("--ledger-path", default=str(ledger.LEDGER_PATH))
    assign_parser.add_argument("--attention-dir", default=str(ATTENTION_DIR))

    submit_parser = subparsers.add_parser("submit")
    submit_parser.add_argument("--lease-digest", required=True)
    submit_parser.add_argument("--control-award-digest")
    submit_parser.add_argument("--evaluation", required=True)
    submit_parser.add_argument("--submitted-at", required=True)
    submit_parser.add_argument("--nonce", required=True)
    submit_parser.add_argument("--idempotency-key", required=True)
    submit_parser.add_argument("--attention-dir", default=str(ATTENTION_DIR))

    assemble_parser = subparsers.add_parser("assemble")
    assemble_parser.add_argument("--submissions", nargs="+", required=True)
    assemble_parser.add_argument("--assembled-utc", required=True)
    assemble_parser.add_argument("--attention-dir", default=str(ATTENTION_DIR))
    assemble_parser.add_argument(
        "--ledger-path",
        default=str(ledger.LEDGER_PATH),
    )
    assemble_parser.add_argument(
        "--projection-path",
        default=str(ledger.PROJECTION_PATH),
    )

    challenge_parser = subparsers.add_parser("challenge")
    challenge_parser.add_argument("--shard-id", required=True)
    challenge_parser.add_argument("--channel", required=True)
    challenge_parser.add_argument("--action-kind", required=True)
    challenge_parser.add_argument("--epoch", type=int, required=True)
    challenge_parser.add_argument("--control-frame", type=int, required=True)
    challenge_parser.add_argument("--fresh-nonce", required=True)
    challenge_parser.add_argument("--issued-at", required=True)
    challenge_parser.add_argument("--expires-at", required=True)
    challenge_parser.add_argument("--difficulty-bits", type=int)
    challenge_parser.add_argument("--target-attempts", type=int, default=64)
    challenge_parser.add_argument("--attention-dir", default=str(ATTENTION_DIR))
    challenge_parser.add_argument(
        "--ledger-path",
        default=str(ledger.LEDGER_PATH),
    )
    challenge_parser.add_argument(
        "--projection-path",
        default=str(ledger.PROJECTION_PATH),
    )

    prove_parser = subparsers.add_parser("prove")
    prove_parser.add_argument("--submission", required=True)
    prove_parser.add_argument("--attention-dir", default=str(ATTENTION_DIR))

    award_parser = subparsers.add_parser("award")
    award_parser.add_argument("--challenge-digest", required=True)
    award_parser.add_argument("--awarded-at", required=True)
    award_parser.add_argument("--lease-seconds", type=int, default=30)
    award_parser.add_argument("--attention-dir", default=str(ATTENTION_DIR))
    award_parser.add_argument("--ledger-path", default=str(ledger.LEDGER_PATH))
    award_parser.add_argument(
        "--projection-path",
        default=str(ledger.PROJECTION_PATH),
    )

    expire_parser = subparsers.add_parser("expire")
    expire_parser.add_argument("--challenge-digest", required=True)
    expire_parser.add_argument("--expired-at", required=True)
    expire_parser.add_argument("--reason", required=True)
    expire_parser.add_argument("--attention-dir", default=str(ATTENTION_DIR))
    expire_parser.add_argument("--ledger-path", default=str(ledger.LEDGER_PATH))
    expire_parser.add_argument(
        "--projection-path",
        default=str(ledger.PROJECTION_PATH),
    )

    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--records", required=True)
    prepare.add_argument("--prompt", default=str(DEFAULT_PROMPT_PATH))
    prepare.add_argument("--policy", default=str(DEFAULT_POLICY_PATH))
    prepare.add_argument("--scope-id", required=True)
    prepare.add_argument("--source", required=True)
    prepare.add_argument("--window-start", required=True)
    prepare.add_argument("--window-end", required=True)
    prepare.add_argument("--base-record-hash")
    prepare.add_argument("--base-frame-hash")
    prepare.add_argument("--endpoint-identity")
    prepare.add_argument("--evaluation-axis")
    prepare.add_argument("--ledger-path", default=str(ledger.LEDGER_PATH))
    prepare.add_argument("--shard-count", type=int, default=1)
    prepare.add_argument("--shard-index", type=int)
    prepare.add_argument("--attention-dir", default=str(ATTENTION_DIR))

    apply_parser = subparsers.add_parser("apply")
    apply_parser.add_argument("--request", required=True)
    apply_parser.add_argument("--evaluation", required=True)
    apply_parser.add_argument("--attention-dir", default=str(ATTENTION_DIR))
    apply_parser.add_argument("--ledger-path", default=str(ledger.LEDGER_PATH))
    apply_parser.add_argument(
        "--projection-path",
        default=str(ledger.PROJECTION_PATH),
    )
    apply_parser.add_argument("--utc")

    merge_parser = subparsers.add_parser("merge")
    merge_parser.add_argument("--groups", nargs="+", required=True)
    merge_parser.add_argument("--attention-dir", default=str(ATTENTION_DIR))
    merge_parser.add_argument("--ledger-path", default=str(ledger.LEDGER_PATH))
    merge_parser.add_argument(
        "--projection-path",
        default=str(ledger.PROJECTION_PATH),
    )
    merge_parser.add_argument("--utc")

    receipt_parser = subparsers.add_parser("receipt")
    receipt_parser.add_argument("--receipt", required=True)
    receipt_parser.add_argument("--attention-dir", default=str(ATTENTION_DIR))
    receipt_parser.add_argument(
        "--ledger-path",
        default=str(ledger.LEDGER_PATH),
    )
    receipt_parser.add_argument(
        "--projection-path",
        default=str(ledger.PROJECTION_PATH),
    )
    receipt_parser.add_argument("--utc")

    arguments = parser.parse_args()
    try:
        if arguments.command == "join":
            attention_dir = _path(arguments.attention_dir)
            if arguments.registration:
                result = register_participant(
                    _load_json(_path(arguments.registration)),
                    attention_dir=attention_dir,
                )
                _print_result({
                    "ok": True,
                    "participant_object_digest": result["participant"][
                        "participant_object_digest"
                    ],
                    "path": str(result["path"]),
                    "trust_status": result["participant"]["trust_status"],
                })
            else:
                if not all((
                    arguments.reason,
                    arguments.revoked_at,
                    arguments.nonce,
                )):
                    raise AttentionError(
                        "revocation requires reason, revoked-at, and nonce"
                    )
                result = revoke_participant(
                    arguments.revoke_participant_digest,
                    arguments.reason,
                    arguments.revoked_at,
                    arguments.nonce,
                    attention_dir=attention_dir,
                )
                _print_result({
                    "ok": True,
                    "revoked": result["revocation"][
                        "participant_object_digest"
                    ],
                    "path": str(result["path"]),
                })
        elif arguments.command == "request":
            result = request_shard_lease(
                _load_json(_path(arguments.request)),
                attention_dir=_path(arguments.attention_dir),
            )
            _print_result({
                "ok": True,
                "lease_request_digest": result["lease_request"][
                    "lease_request_digest"
                ],
                "path": str(result["path"]),
            })
        elif arguments.command == "assign":
            result = assign_shard_lease(
                _load_json(_path(arguments.lease_request)),
                _load_json(_path(arguments.attention_request)),
                ledger_path=_path(arguments.ledger_path),
                attention_dir=_path(arguments.attention_dir),
            )
            _print_result({
                "ok": True,
                "lease_id": result["lease"]["lease_id"],
                "lease_digest": result["lease"]["lease_digest"],
                "path": str(result["lease_path"]),
                "trust_status": result["lease"]["trust_status"],
            })
        elif arguments.command == "submit":
            result = submit_candidate_result(
                arguments.lease_digest,
                arguments.control_award_digest,
                _load_json(
                    _path(arguments.evaluation),
                    MAX_EVALUATION_BYTES,
                ),
                arguments.submitted_at,
                arguments.nonce,
                arguments.idempotency_key,
                attention_dir=_path(arguments.attention_dir),
            )
            _print_result({
                "ok": True,
                "candidate_result_digest": result["candidate"][
                    "candidate_result_digest"
                ],
                "path": str(result["path"]),
                "trust_status": result["candidate"]["trust_status"],
            })
        elif arguments.command == "assemble":
            result = assemble_candidate_results(
                [
                    _load_json(_path(path))
                    for path in arguments.submissions
                ],
                assembled_utc=arguments.assembled_utc,
                attention_dir=_path(arguments.attention_dir),
                ledger_path=_path(arguments.ledger_path),
                projection_path=_path(arguments.projection_path),
            )
            _print_result({
                "ok": True,
                "accepted": [
                    item["candidate"]["candidate_result_digest"]
                    for item in result["accepted"]
                ],
                "replayed": [
                    item["candidate_result_digest"]
                    for item in result["replayed"]
                ],
                "merge_metrics": result["merge"]["metrics"],
                "dimension_count": len(
                    result["merge"]["dimensions"]
                ),
            })
        elif arguments.command == "challenge":
            result = create_fold_challenge(
                arguments.shard_id,
                arguments.channel,
                arguments.action_kind,
                arguments.epoch,
                arguments.control_frame,
                arguments.fresh_nonce,
                arguments.issued_at,
                arguments.expires_at,
                attention_dir=_path(arguments.attention_dir),
                ledger_path=_path(arguments.ledger_path),
                projection_path=_path(arguments.projection_path),
                requested_difficulty_bits=arguments.difficulty_bits,
                target_attempts=arguments.target_attempts,
            )
            _print_result({
                "ok": True,
                "challenge_digest": result["challenge"][
                    "challenge_digest"
                ],
                "difficulty_bits": result["challenge"][
                    "difficulty_bits"
                ],
                "max_work_iterations": result["challenge"][
                    "max_work_iterations"
                ],
                "frame_seq": result["frame"]["seq"],
                "frame_hash": result["frame"]["frame_hash"],
            })
        elif arguments.command == "prove":
            result = submit_fold_proof(
                _load_json(_path(arguments.submission)),
                attention_dir=_path(arguments.attention_dir),
            )
            _print_result({
                "ok": True,
                "attempt_digest": result["attempt"]["attempt_digest"],
                "proof_hash": result["attempt"]["proof_hash"],
                "valid": result["attempt"]["valid"],
            })
        elif arguments.command == "award":
            result = award_fold_challenge(
                arguments.challenge_digest,
                arguments.awarded_at,
                action_lease_seconds=arguments.lease_seconds,
                attention_dir=_path(arguments.attention_dir),
                ledger_path=_path(arguments.ledger_path),
                projection_path=_path(arguments.projection_path),
            )
            _print_result({
                "ok": True,
                "award_digest": result["award"]["award_digest"],
                "winner_participant_object_digest": result["award"][
                    "winner_participant_object_digest"
                ],
                "valid_until": result["award"]["valid_until"],
            })
        elif arguments.command == "expire":
            result = expire_fold_challenge(
                arguments.challenge_digest,
                arguments.expired_at,
                arguments.reason,
                attention_dir=_path(arguments.attention_dir),
                ledger_path=_path(arguments.ledger_path),
                projection_path=_path(arguments.projection_path),
            )
            _print_result({
                "ok": True,
                "expiry_digest": result["expiry"]["expiry_digest"],
                "frame_seq": result["frame"]["seq"],
                "frame_hash": result["frame"]["frame_hash"],
            })
        elif arguments.command == "prepare":
            prepared = prepare_requests(
                _load_json(_path(arguments.records)),
                _load_json(_path(arguments.prompt)),
                _load_json(_path(arguments.policy)),
                scope_id=arguments.scope_id,
                source=arguments.source,
                window_start=arguments.window_start,
                window_end=arguments.window_end,
                base_record_hash=arguments.base_record_hash,
                base_frame_hash=arguments.base_frame_hash,
                endpoint_identity=arguments.endpoint_identity,
                evaluation_axis=arguments.evaluation_axis,
                shard_count=arguments.shard_count,
                shard_index=arguments.shard_index,
                attention_dir=_path(arguments.attention_dir),
                ledger_path=_path(arguments.ledger_path),
            )
            _print_result({
                "ok": True,
                "requests": [
                    {
                        "group_id": item["request"]["group_id"],
                        "shard_id": item["request"]["shard_id"],
                        "scope_digest": item["request"]["scope_digest"],
                        "request_digest": item["request"]["request_digest"],
                        "path": str(item["path"]),
                        "candidate_count": item["request"]["candidate_count"],
                        "candidate_budget": item["request"][
                            "candidate_budget"
                        ],
                        "attention_budget": item["request"][
                            "attention_budget"
                        ],
                        "evaluator_packet": item["evaluator_packet"],
                    }
                    for item in prepared
                ],
            })
        elif arguments.command == "apply":
            result = apply_evaluation(
                _load_json(_path(arguments.request)),
                _load_json(
                    _path(arguments.evaluation),
                    MAX_EVALUATION_BYTES,
                ),
                attention_dir=_path(arguments.attention_dir),
                ledger_path=_path(arguments.ledger_path),
                projection_path=_path(arguments.projection_path),
                utc=arguments.utc,
            )
            _print_result({
                "ok": True,
                "group_id": result["group"]["group_id"],
                "group_object_digest": result["group"][
                    "group_object_digest"
                ],
                "group_path": str(result["group_path"]),
                "attention_frame_seq": result["frame"]["seq"],
                "attention_frame_hash": result["frame"]["frame_hash"],
            })
        elif arguments.command == "merge":
            result = merge_attention_groups(
                [
                    _load_json(_path(path))
                    for path in arguments.groups
                ],
                attention_dir=_path(arguments.attention_dir),
                ledger_path=_path(arguments.ledger_path),
                projection_path=_path(arguments.projection_path),
                utc=arguments.utc,
            )
            _print_result({
                "ok": True,
                "ordered_group_digests": result[
                    "ordered_group_digests"
                ],
                "metrics": result["metrics"],
                "dimensions": [
                    {
                        "dimension_object_digest": item["dimension"][
                            "dimension_object_digest"
                        ],
                        "path": str(item["path"]),
                        "frame_seq": item["frame"]["seq"],
                        "frame_hash": item["frame"]["frame_hash"],
                    }
                    for item in result["dimensions"]
                ],
            })
        else:
            result = record_mutation_receipt(
                _load_json(_path(arguments.receipt)),
                attention_dir=_path(arguments.attention_dir),
                ledger_path=_path(arguments.ledger_path),
                projection_path=_path(arguments.projection_path),
                utc=arguments.utc,
            )
            _print_result({
                "ok": True,
                "receipt_object_digest": result["receipt"][
                    "receipt_object_digest"
                ],
                "receipt_path": str(result["receipt_path"]),
                "frame_seq": result["frame"]["seq"],
                "frame_hash": result["frame"]["frame_hash"],
            })
        return 0
    except (AttentionError, ledger.LedgerError) as error:
        print(
            json.dumps({"ok": False, "error": str(error)}),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

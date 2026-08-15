#!/usr/bin/env python3
"""Append-only RAPP/1-shaped organism frames for RappterZoo.

The ledger is public metadata only. It deliberately makes no authenticated
RAPP/1 acceptance claim because this repository does not carry a signed
Section 13 registry or a signing key for the swarm stream.
"""

import argparse
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import unicodedata
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


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
PUBLIC_VISIBILITY = "public-metadata"
FORBIDDEN_PUBLIC_KEYS = {
    "biometric",
    "face_landmarks",
    "godd",
    "identity_template",
    "landmarks",
    "media",
    "private",
    "pulse",
    "pulse_bpm",
    "pulse_bpm_estimate",
    "raw_media",
}


class LedgerError(ValueError):
    pass


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
        if not math.isfinite(value):
            raise LedgerError("non-finite number is forbidden")
        return format(value, ".15g")
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

    Generated records use ASCII keys, safe integers, and no binary64 values,
    making stdlib sorted compact JSON identical to RFC 8785 for this profile.
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


def _find_forbidden_key(value: Any) -> Optional[str]:
    if type(value) is dict:
        for key, item in value.items():
            if key.lower() in FORBIDDEN_PUBLIC_KEYS:
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


def validate_public_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    normalized = _normalize_json(payload)
    if type(normalized) is not dict:
        raise LedgerError("payload must be a JSON object")
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
    if not KIND_RE.fullmatch(kind):
        raise LedgerError("kind does not match the RAPP/1 label form")
    if stream_id != STREAM_ID:
        raise LedgerError("this ledger accepts only net:rappterzoo")
    if type(seq) is not int or seq < 0:
        raise LedgerError("sequence must be a non-negative integer")
    normalized_payload = _normalize_json(payload)
    if type(normalized_payload) is not dict:
        raise LedgerError("payload must be a JSON object")
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


def read_frames(path: Path = LEDGER_PATH) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    frames = []
    with path.open("rb") as handle:
        for line_number, raw_line in enumerate(handle, 1):
            line = raw_line.rstrip(b"\n")
            if not line:
                raise LedgerError(
                    "blank ledger line at {}".format(line_number)
                )
            try:
                frame = json.loads(line.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                raise LedgerError(
                    "invalid ledger JSON at line {}".format(line_number)
                ) from error
            if canonical_bytes(frame) != line:
                raise LedgerError(
                    "non-canonical ledger frame at line {}".format(
                        line_number
                    )
                )
            frames.append(frame)
    verify_frames(frames)
    return frames


def verify_frames(frames: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    materialized = list(frames)
    previous = None
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
        if not KIND_RE.fullmatch(frame["kind"]):
            raise LedgerError("frame {} has an invalid kind".format(index))
        if frame["seq"] != index:
            raise LedgerError("frame {} is not contiguous".format(index))
        if not UTC_RE.fullmatch(frame["utc"]):
            raise LedgerError("frame {} has an invalid UTC value".format(index))
        if type(frame["payload"]) is not dict:
            raise LedgerError("frame {} payload is not an object".format(index))
        validate_public_payload(frame["payload"])
        if not HASH_RE.fullmatch(frame["payload_hash"]):
            raise LedgerError("frame {} has an invalid payload hash".format(index))
        if not HASH_RE.fullmatch(frame["frame_hash"]):
            raise LedgerError("frame {} has an invalid frame hash".format(index))
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
    prefix = verify_append_only_bytes(result.stdout, current)
    return {
        **prefix,
        "checked": True,
        "base_ref": base_ref,
    }


@contextmanager
def _ledger_lock(path: Path):
    lock_path = path.with_name(path.name + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(
            str(lock_path),
            os.O_CREAT | os.O_EXCL | os.O_WRONLY,
            0o600,
        )
    except FileExistsError as error:
        raise LedgerError(
            "organism ledger is already locked: {}".format(lock_path)
        ) from error
    try:
        os.write(descriptor, str(os.getpid()).encode("ascii"))
        os.fsync(descriptor)
        yield
    finally:
        os.close(descriptor)
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass


def _atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(str(temporary), str(path))


def _organism_summary(frames: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    organisms = {}
    for frame in frames:
        payload = frame["payload"]
        organism_id = payload.get("organism", "rappterzoo")
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
        if frame["kind"] not in summary["kinds"]:
            summary["kinds"].append(frame["kind"])
    return sorted(
        organisms.values(),
        key=lambda item: (-item["frame_count"], item["id"]),
    )


def write_projection(
    frames: Optional[List[Dict[str, Any]]] = None,
    path: Path = PROJECTION_PATH,
) -> Dict[str, Any]:
    if frames is None:
        frames = read_frames()
    integrity = verify_frames(frames)
    visible_frames = frames[-1000:]
    projection = {
        "schema": "rappterzoo-organism-feed/1",
        "generated_at": frames[-1]["utc"] if frames else None,
        "stream_id": STREAM_ID,
        "append_only_source": "organism-frames.jsonl",
        "digg_view": "data-tools/digg.html",
        "privacy": {
            "projection": PUBLIC_VISIBILITY,
            "private_godd_media": "excluded",
            "raw_frames": "excluded",
            "biometric_values": "excluded",
        },
        "rapp1": {
            "wire_shape": "exact-eleven-key-frame",
            "hash_domains": [PARTICLE_SPACE, WAVE_SPACE],
            "acceptance": "structural-unverified",
            "reason": (
                "No authenticated RAPP/1 Section 13 registry or swarm "
                "signature is asserted by this public projection."
            ),
        },
        "integrity": integrity,
        "organisms": _organism_summary(frames),
        "frames": visible_frames,
        "projection_frame_count": len(visible_frames),
        "total_frame_count": len(frames),
    }
    _atomic_json(path, projection)
    return projection


def append_frame(
    kind: str,
    payload: Dict[str, Any],
    utc: Optional[str] = None,
    ledger_path: Path = LEDGER_PATH,
    projection_path: Path = PROJECTION_PATH,
) -> Dict[str, Any]:
    normalized_payload = validate_public_payload(payload)
    event_id = normalized_payload["event_id"]

    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with _ledger_lock(ledger_path):
        frames = read_frames(ledger_path)
        for existing in frames:
            if existing["payload"].get("event_id") != event_id:
                continue
            if (
                existing["kind"] == kind
                and existing["payload"] == normalized_payload
            ):
                write_projection(frames, projection_path)
                return existing
            raise LedgerError(
                "event_id conflict for {}".format(event_id)
            )
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
        line = canonical_bytes(frame) + b"\n"
        with ledger_path.open("ab") as handle:
            handle.write(line)
            handle.flush()
            os.fsync(handle.fileno())
        frames.append(frame)
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
        "actions": _normalize_json(actions),
        "metrics": _normalize_json(metrics),
    }


def append_molter_frame(
    frame_number: int,
    observation: Dict[str, Any],
    actions: Dict[str, Any],
    utc: Optional[str] = None,
    ledger_path: Path = LEDGER_PATH,
    projection_path: Path = PROJECTION_PATH,
    state_path: Path = STATE_PATH,
) -> Dict[str, Any]:
    if not ledger_path.exists():
        bootstrap_from_state(
            state_path=state_path,
            ledger_path=ledger_path,
            projection_path=projection_path,
        )
    metrics = {
        "total_apps": observation.get("total_apps_manifest", 0),
        "avg_score": observation.get("avg_score", 0),
        "below_40": observation.get("below_40", 0),
        "unmolted": observation.get("unmolted", 0),
    }
    frames = read_frames(ledger_path)
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
    if not ledger_path.exists():
        bootstrap_from_state(
            state_path=state_path,
            ledger_path=ledger_path,
            projection_path=projection_path,
        )
    agent_id = str(agent.get("agent_id", "")).strip()
    if not agent_id:
        raise LedgerError("agent birth requires agent_id")
    frames = read_frames(ledger_path)
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
    if not ledger_path.exists():
        bootstrap_from_state(
            state_path=state_path,
            ledger_path=ledger_path,
            projection_path=projection_path,
        )
    agent_id = str(agent.get("agent_id", "")).strip()
    owner = str(agent.get("owner_github", "")).strip()
    if not agent_id or not owner:
        raise LedgerError("agent adoption requires agent_id and owner_github")
    frames = read_frames(ledger_path)
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


def bootstrap_from_state(
    state_path: Path = STATE_PATH,
    ledger_path: Path = LEDGER_PATH,
    projection_path: Path = PROJECTION_PATH,
) -> Dict[str, Any]:
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        state = {"frame": 0, "history": []}
    history = sorted(
        state.get("history", []),
        key=lambda item: int(item.get("frame", 0)),
    )
    first_timestamp = (
        history[0].get("timestamp")
        if history
        else "2026-08-15T17:06:24.449Z"
    )
    frames = read_frames(ledger_path)
    event_ids = {
        frame["payload"]["event_id"]
        for frame in frames
    }
    has_bootstrap = any(
        frame["payload"].get("event") == "bootstrap"
        and frame["payload"].get("organism") == "rappterzoo"
        for frame in frames
    )
    if not has_bootstrap:
        if frames:
            raise LedgerError(
                "non-empty ledger is missing its bootstrap frame"
            )
        append_frame(
            "zoo.snapshot",
            {
                "schema": "rappterzoo-organism-frame/1",
                "event_id": "bootstrap:molter-state:{}".format(
                    state.get("frame", 0)
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
                    "head_frame": int(state.get("frame", 0)),
                },
            },
            utc=first_timestamp,
            ledger_path=ledger_path,
            projection_path=projection_path,
        )
        frames = read_frames(ledger_path)
        event_ids.add(frames[-1]["payload"]["event_id"])
    for historical in history:
        event_id = "molter-frame:{}".format(
            int(historical.get("frame", 0))
        )
        if event_id in event_ids:
            continue
        timestamp = normalize_utc(historical.get("timestamp"))
        if frames and timestamp < frames[-1]["utc"]:
            raise LedgerError(
                "cannot backfill {} behind the append-only head".format(
                    event_id
                )
            )
        append_frame(
            "zoo.observation",
            _molter_payload(
                int(historical.get("frame", 0)),
                historical.get("actions", {}),
                historical.get("metrics", {}),
            ),
            utc=historical.get("timestamp"),
            ledger_path=ledger_path,
            projection_path=projection_path,
        )
        frames = read_frames(ledger_path)
        event_ids.add(event_id)
    watchtower = _watchtower_birth_payload()
    if watchtower["event_id"] not in event_ids:
        append_frame(
            "zoo.birth",
            watchtower,
            utc=_history_timestamp_after(
                "2026-08-15T17:06:24.449Z",
                frames,
            ),
            ledger_path=ledger_path,
            projection_path=projection_path,
        )
    return write_projection(read_frames(ledger_path), projection_path)


def main() -> int:
    parser = argparse.ArgumentParser(prog="organism-ledger")
    parser.add_argument(
        "command",
        choices=("bootstrap", "verify", "project"),
    )
    parser.add_argument(
        "--git-base",
        help="For verify, require the current JSONL to preserve this git ref.",
    )
    arguments = parser.parse_args()
    try:
        if arguments.command == "bootstrap":
            result = bootstrap_from_state()
        elif arguments.command == "project":
            result = write_projection(read_frames())
        else:
            result = verify_frames(read_frames())
            if arguments.git_base:
                result["git_prefix"] = verify_git_append_only(
                    arguments.git_base
                )
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except LedgerError as error:
        print(
            json.dumps({"ok": False, "error": str(error)}),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

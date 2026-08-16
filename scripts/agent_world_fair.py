#!/usr/bin/env python3
"""Build, verify, prepare, and apply the deterministic Agent World's Fair."""

import argparse
import base64
import binascii
import copy
import hashlib
import hmac
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import organism_ledger


ROOT = Path(__file__).resolve().parent.parent
FAIR_DIR = ROOT / "apps" / "agent-fair"
EVENTS_PATH = FAIR_DIR / "events.jsonl"
STATE_PATH = FAIR_DIR / "fair-state.json"
CONTRACT_PATH = FAIR_DIR / "agent-contract.json"
DISTRICT_PATH = FAIR_DIR / "district.json"
RELEASE_CANDIDATE_PATH = FAIR_DIR / "release-candidate.json"

FAIR_ID = "fair.agent-worlds-fair-1"
DISTRICT_ID = "district.agent-worlds-fair-1"
APP_FILE = "agent-worlds-fair.html"
TITLE = "Agent World's Fair"

PARK_BUNDLE_DIGEST = (
    "a8d5df723b6c94790e8da5cb0b59550c2fb8a10cc6a11317c09650e584140ca7"
)
PARK_EVENT_HEAD = (
    "a7cf7ce7e18c97c4099bd01edb47211b9cf2c53ddd968d76f9d626d412a29ed9"
)
PARK_EVENT_COUNT = 94
PARK_EVENT_LEDGER_SHA256 = (
    "bfefe99e73fd89bc4f435dd3dfd9c4a5b784788017e406a79fe92194273351bf"
)
ORGANISM_FRAME_SEQ = 56
ORGANISM_FRAME_HASH = (
    "9e21f50524057dba0392a4db63fdeee981d9775f005cc8ae16b829e06fe4eecd"
)

STATE_SCHEMA = "rappterzoo-agent-worlds-fair-state/1"
EVENT_SCHEMA = "rappterzoo-agent-worlds-fair-event/1"
CONTRACT_SCHEMA = "rappterzoo-agent-worlds-fair-contract/1"
DISTRICT_SCHEMA = "rappterzoo-agent-worlds-fair-district/1"
RELEASE_CANDIDATE_SCHEMA = (
    "rappterzoo-agent-worlds-fair-release-candidate/1"
)
LOCAL_ACTION_SCHEMA = "rappterzoo-agent-fair-local-action/1"
BRANCH_EXPORT_SCHEMA = "rappterzoo-agent-fair-branch-export/1"

PAYLOAD_HASH_DOMAIN = b"rappterzoo/agent-worlds-fair-payload/1\n"
EVENT_HASH_DOMAIN = b"rappterzoo/agent-worlds-fair-event/1\n"
SUBMISSION_HASH_DOMAIN = b"rappterzoo/agent-worlds-fair-submission/1\n"
STATE_HASH_DOMAIN = b"rappterzoo/agent-worlds-fair-state/1\n"
CONTRACT_HASH_DOMAIN = b"rappterzoo/agent-worlds-fair-contract/1\n"
DISTRICT_HASH_DOMAIN = b"rappterzoo/agent-worlds-fair-district/1\n"
BUNDLE_HASH_DOMAIN = b"rappterzoo/agent-worlds-fair-bundle/1\n"
RELEASE_CANDIDATE_HASH_DOMAIN = (
    b"rappterzoo/agent-worlds-fair-release-candidate/1\n"
)
RELEASE_VERIFIER_COMMAND = "python3 scripts/agent_world_fair.py verify"
RELEASE_VERIFIER_VERSION = "agent-world-fair-release/3"
OIDC_AUDIENCE = "rappterzoo-agent-fair-release"
OIDC_ISSUER = "https://token.actions.githubusercontent.com"
OIDC_JWKS_URL = OIDC_ISSUER + "/.well-known/jwks"
OIDC_REPOSITORY = "kody-w/localFirstTools-main"
OIDC_REF = "refs/heads/main"
OIDC_EVENT_NAME = "workflow_dispatch"
OIDC_WORKFLOW_REF = (
    OIDC_REPOSITORY
    + "/.github/workflows/agent-fair-release.yml@refs/heads/main"
)
OIDC_ENVIRONMENT = "agent-fair-production"
OIDC_RESPONSE_LIMIT = 1024 * 1024
APPROVAL_EVIDENCE_KEYS = {
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
SHA256_DIGEST_INFO_PREFIX = bytes.fromhex(
    "3031300d060960864801650304020105000420"
)

EVENT_KEYS = {
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
SUBMISSION_COUNT = 12
VOTING_ROUNDS = 4
WINNER_COUNT = 4
EVENT_COUNT = (
    2
    + SUBMISSION_COUNT
    + 1
    + VOTING_ROUNDS
    + 1
    + 1
    + 1
    + 1
)
ATTRACTION_LIMITS = {
    "attention": 20,
    "compute": 32,
    "energy": 24,
}
DISTRICT_CAPACITY = {
    "attention": 60,
    "compute": 96,
    "energy": 72,
}
SCORE_WEIGHTS_BPS = {
    "admissions": 4500,
    "diversity": 500,
    "novelty": 1000,
    "resource_efficiency": 1500,
    "satisfaction": 2500,
}
LOCAL_PROPOSAL_ACTION_LIMIT = 50


class FairError(ValueError):
    pass


def _strict_json_bytes(raw: bytes, label: str) -> Dict[str, Any]:
    def object_pairs(pairs: Sequence[Tuple[str, Any]]) -> Dict[str, Any]:
        value = {}
        for key, item in pairs:
            if key in value:
                raise FairError("{} contains duplicate JSON keys".format(label))
            value[key] = item
        return value

    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=object_pairs,
        )
    except FairError:
        raise
    except (UnicodeError, ValueError) as error:
        raise FairError("{} is not valid JSON".format(label)) from error
    if type(value) is not dict:
        raise FairError("{} must be a JSON object".format(label))
    return value


def _base64url_decode(value: str, label: str) -> bytes:
    if (
        type(value) is not str
        or not value
        or any(
            character not in (
                "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
                "abcdefghijklmnopqrstuvwxyz"
                "0123456789-_"
            )
            for character in value
        )
    ):
        raise FairError("{} is not canonical base64url".format(label))
    padding = "=" * ((4 - len(value) % 4) % 4)
    try:
        return base64.b64decode(
            (value + padding).encode("ascii"),
            altchars=b"-_",
            validate=True,
        )
    except (binascii.Error, ValueError) as error:
        raise FairError("{} is not valid base64url".format(label)) from error


def _response_json(
    request: urllib.request.Request,
    label: str,
) -> Dict[str, Any]:
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            status = getattr(response, "status", None)
            if status is None:
                status = response.getcode()
            if status != 200:
                raise FairError("{} returned HTTP {}".format(label, status))
            raw = response.read(OIDC_RESPONSE_LIMIT + 1)
    except FairError:
        raise
    except (OSError, urllib.error.URLError) as error:
        raise FairError("{} request failed".format(label)) from error
    if len(raw) > OIDC_RESPONSE_LIMIT:
        raise FairError("{} response is too large".format(label))
    return _strict_json_bytes(raw, label)


def _oidc_request_url(value: str) -> str:
    try:
        parsed = urllib.parse.urlsplit(value)
    except ValueError as error:
        raise FairError("GitHub OIDC request URL is invalid") from error
    hostname = parsed.hostname or ""
    try:
        port = parsed.port
    except ValueError as error:
        raise FairError("GitHub OIDC request URL is invalid") from error
    if (
        parsed.scheme != "https"
        or port not in {None, 443}
        or parsed.username is not None
        or parsed.password is not None
        or not hostname.endswith(".actions.githubusercontent.com")
    ):
        raise FairError("GitHub OIDC request URL is not trusted")
    query = [
        (key, item)
        for key, item in urllib.parse.parse_qsl(
            parsed.query,
            keep_blank_values=True,
        )
        if key != "audience"
    ]
    query.append(("audience", OIDC_AUDIENCE))
    return urllib.parse.urlunsplit((
        parsed.scheme,
        parsed.netloc,
        parsed.path,
        urllib.parse.urlencode(query),
        "",
    ))


def _verify_rs256(
    signing_input: bytes,
    signature: bytes,
    jwk: Dict[str, Any],
) -> None:
    if (
        jwk.get("kty") != "RSA"
        or jwk.get("alg") != "RS256"
        or jwk.get("use") != "sig"
    ):
        raise FairError("GitHub OIDC signing key metadata is invalid")
    modulus_bytes = _base64url_decode(jwk.get("n"), "JWK modulus")
    exponent_bytes = _base64url_decode(jwk.get("e"), "JWK exponent")
    modulus = int.from_bytes(modulus_bytes, "big")
    exponent = int.from_bytes(exponent_bytes, "big")
    if modulus.bit_length() < 2048 or exponent < 3 or exponent % 2 == 0:
        raise FairError("GitHub OIDC RSA public key is unsafe")
    size = (modulus.bit_length() + 7) // 8
    if len(signature) != size:
        raise FairError("GitHub OIDC signature length is invalid")
    signature_integer = int.from_bytes(signature, "big")
    if signature_integer >= modulus:
        raise FairError("GitHub OIDC signature integer is invalid")
    digest_info = (
        SHA256_DIGEST_INFO_PREFIX
        + hashlib.sha256(signing_input).digest()
    )
    padding_length = size - len(digest_info) - 3
    if padding_length < 8:
        raise FairError("GitHub OIDC RSA key is too small")
    expected = (
        b"\x00\x01"
        + b"\xff" * padding_length
        + b"\x00"
        + digest_info
    )
    encoded = pow(
        signature_integer,
        exponent,
        modulus,
    ).to_bytes(size, "big")
    if not hmac.compare_digest(encoded, expected):
        raise FairError("GitHub OIDC signature verification failed")


def _verify_oidc_attestation(
    token: str,
    jwks: Dict[str, Any],
    now: Optional[int] = None,
) -> Dict[str, Any]:
    if type(token) is not str or token.strip() != token:
        raise FairError("GitHub OIDC token is invalid")
    parts = token.split(".")
    if len(parts) != 3:
        raise FairError("GitHub OIDC token must be a compact JWT")
    header = _strict_json_bytes(
        _base64url_decode(parts[0], "JWT header"),
        "JWT header",
    )
    claims = _strict_json_bytes(
        _base64url_decode(parts[1], "JWT claims"),
        "JWT claims",
    )
    signature = _base64url_decode(parts[2], "JWT signature")
    kid = header.get("kid")
    if (
        header.get("alg") != "RS256"
        or header.get("typ") != "JWT"
        or type(kid) is not str
        or not kid
    ):
        raise FairError("GitHub OIDC JWT header is invalid")
    keys = jwks.get("keys")
    if type(keys) is not list:
        raise FairError("GitHub OIDC JWKS keys are invalid")
    matches = [
        key
        for key in keys
        if type(key) is dict and key.get("kid") == kid
    ]
    if len(matches) != 1:
        raise FairError("GitHub OIDC JWT kid is not uniquely trusted")
    signing_input = "{}.{}".format(parts[0], parts[1]).encode("ascii")
    _verify_rs256(signing_input, signature, matches[0])

    fixed = {
        "aud": OIDC_AUDIENCE,
        "environment": OIDC_ENVIRONMENT,
        "event_name": OIDC_EVENT_NAME,
        "iss": OIDC_ISSUER,
        "ref": OIDC_REF,
        "repository": OIDC_REPOSITORY,
        "workflow_ref": OIDC_WORKFLOW_REF,
    }
    for name, expected in fixed.items():
        if claims.get(name) != expected:
            raise FairError(
                "GitHub OIDC {} claim mismatch".format(name)
            )
    actor = claims.get("actor")
    run_id = claims.get("run_id")
    if (
        type(actor) is not str
        or not actor
        or actor.strip() != actor
        or type(run_id) is not str
        or not run_id.isdigit()
    ):
        raise FairError("GitHub OIDC actor/run_id claims are invalid")
    expires_at = claims.get("exp")
    not_before = claims.get("nbf")
    if type(expires_at) is not int or type(not_before) is not int:
        raise FairError("GitHub OIDC exp/nbf claims must be integers")
    current = int(time.time()) if now is None else int(now)
    if not_before > current:
        raise FairError("GitHub OIDC attestation is not yet valid")
    if expires_at <= current:
        raise FairError("GitHub OIDC attestation is expired")
    if expires_at <= not_before:
        raise FairError("GitHub OIDC attestation time range is invalid")
    return {
        "actor": actor,
        "attestation_sha256": hashlib.sha256(
            token.encode("ascii")
        ).hexdigest(),
        "aud": claims["aud"],
        "environment": claims["environment"],
        "event_name": claims["event_name"],
        "exp": expires_at,
        "iss": claims["iss"],
        "nbf": not_before,
        "ref": claims["ref"],
        "repository": claims["repository"],
        "run_id": run_id,
        "workflow_ref": claims["workflow_ref"],
    }


def verify_github_oidc_token(
    token: str,
    jwks: Dict[str, Any],
    now: int,
) -> Dict[str, Any]:
    """Verify a GitHub Actions OIDC JWT without performing network access."""
    return _verify_oidc_attestation(token, jwks, now=now)


def _github_oidc_approval_evidence() -> Dict[str, Any]:
    request_url = os.environ.get("ACTIONS_ID_TOKEN_REQUEST_URL", "")
    request_token = os.environ.get("ACTIONS_ID_TOKEN_REQUEST_TOKEN", "")
    if not request_url or not request_token:
        raise FairError("GitHub Actions OIDC request credentials are required")
    if request_token.strip() != request_token:
        raise FairError("GitHub Actions OIDC request token is invalid")
    token_request = urllib.request.Request(
        _oidc_request_url(request_url),
        headers={
            "Accept": "application/json",
            "Authorization": "Bearer " + request_token,
            "User-Agent": "rappterzoo-agent-fair-release/1",
        },
        method="GET",
    )
    token_response = _response_json(
        token_request,
        "GitHub OIDC token endpoint",
    )
    token = token_response.get("value")
    if type(token) is not str or not token:
        raise FairError("GitHub OIDC token response is missing value")
    jwks_request = urllib.request.Request(
        OIDC_JWKS_URL,
        headers={
            "Accept": "application/json",
            "User-Agent": "rappterzoo-agent-fair-release/1",
        },
        method="GET",
    )
    jwks = _response_json(jwks_request, "GitHub OIDC JWKS")
    return verify_github_oidc_token(
        token,
        jwks,
        now=int(time.time()),
    )


def _canonical_digest(domain: bytes, value: Any) -> str:
    return hashlib.sha256(
        domain + organism_ledger.canonical_bytes(value)
    ).hexdigest()


def _pretty_bytes(value: Any) -> bytes:
    return organism_ledger._pretty_json_bytes(value)


def _atomic_bytes(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(
        "{}.tmp.{}".format(path.name, os.getpid())
    )
    try:
        with temporary.open("wb") as handle:
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(str(temporary), str(path))
        organism_ledger._fsync_directory(path.parent)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _load_json(path: Path) -> Any:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as error:
        raise FairError("cannot read {}: {}".format(path, error)) from error
    return value


def _load_events(path: Path) -> List[Dict[str, Any]]:
    try:
        raw = path.read_bytes()
    except OSError as error:
        raise FairError("cannot read {}: {}".format(path, error)) from error
    if not raw.endswith(b"\n"):
        raise FairError("fair event ledger lacks a final newline")
    result = []
    for line_number, line in enumerate(raw.splitlines(), 1):
        if not line:
            raise FairError("blank fair event line {}".format(line_number))
        try:
            event = json.loads(line.decode("utf-8"))
        except (UnicodeError, ValueError) as error:
            raise FairError(
                "invalid fair event line {}".format(line_number)
            ) from error
        if organism_ledger.canonical_bytes(event) != line:
            raise FairError(
                "non-canonical fair event line {}".format(line_number)
            )
        result.append(event)
    return result


def _event_bytes(events: Iterable[Dict[str, Any]]) -> bytes:
    return b"".join(
        organism_ledger.canonical_bytes(event) + b"\n"
        for event in events
    )


def _state_without_digest(value: Dict[str, Any]) -> Dict[str, Any]:
    projected = copy.deepcopy(value)
    projected["integrity"].pop("bundle_digest", None)
    projected["integrity"].pop("state_digest", None)
    return projected


def _contract_without_digest(value: Dict[str, Any]) -> Dict[str, Any]:
    projected = copy.deepcopy(value)
    projected["integrity"].pop("bundle_digest", None)
    projected["integrity"].pop("contract_digest", None)
    return projected


def _district_without_digest(value: Dict[str, Any]) -> Dict[str, Any]:
    projected = copy.deepcopy(value)
    projected["integrity"].pop("bundle_digest", None)
    projected["integrity"].pop("district_digest", None)
    return projected


def _candidate_without_digest(value: Dict[str, Any]) -> Dict[str, Any]:
    projected = copy.deepcopy(value)
    projected.pop("candidate_digest", None)
    return projected


def _bundle_digest(
    event_count: int,
    event_head: str,
    event_ledger_sha256: str,
    state_digest: str,
    contract_digest: str,
    district_digest: str,
) -> str:
    return _canonical_digest(
        BUNDLE_HASH_DOMAIN,
        {
            "contract_digest": contract_digest,
            "district_digest": district_digest,
            "event_count": event_count,
            "event_head": event_head,
            "event_ledger_sha256": event_ledger_sha256,
            "state_digest": state_digest,
        },
    )


def _hash_int(*parts: Any) -> int:
    text = "\x1f".join(str(part) for part in parts)
    return int.from_bytes(
        hashlib.sha256(text.encode("utf-8")).digest()[:8],
        "big",
    )


def _verify_source_anchor(root: Path) -> Dict[str, Any]:
    park_state = _load_json(root / "apps" / "agent-park" / "park-state.json")
    park_event_path = root / "apps" / "agent-park" / "events.jsonl"
    try:
        park_event_bytes = park_event_path.read_bytes()
    except OSError as error:
        raise FairError("cannot read park event anchor: {}".format(error)) from error
    try:
        park_events = [
            json.loads(line.decode("utf-8"))
            for line in park_event_bytes.splitlines()
        ]
    except (UnicodeError, ValueError) as error:
        raise FairError("park event anchor is invalid") from error
    if (
        park_state.get("integrity", {}).get("bundle_digest")
        != PARK_BUNDLE_DIGEST
        or park_state.get("event_ledger", {}).get("head")
        != PARK_EVENT_HEAD
        or park_state.get("event_ledger", {}).get("event_count")
        != PARK_EVENT_COUNT
        or park_state.get("event_ledger", {}).get("sha256")
        != PARK_EVENT_LEDGER_SHA256
        or len(park_events) != PARK_EVENT_COUNT
        or not park_events
        or park_events[-1].get("event_hash") != PARK_EVENT_HEAD
        or hashlib.sha256(park_event_bytes).hexdigest()
        != PARK_EVENT_LEDGER_SHA256
    ):
        raise FairError("agent amusement park source drift detected")

    frames = organism_ledger.read_frames(
        root / "apps" / "organism-frames.jsonl"
    )
    organism_ledger.verify_frames(frames)
    matches = [
        frame
        for frame in frames
        if frame.get("seq") == ORGANISM_FRAME_SEQ
    ]
    if (
        len(matches) != 1
        or matches[0].get("frame_hash") != ORGANISM_FRAME_HASH
        or matches[0].get("payload", {}).get("bundle_digest")
        != PARK_BUNDLE_DIGEST
        or matches[0].get("payload", {}).get("ledger_head")
        != PARK_EVENT_HEAD
    ):
        raise FairError("organism release frame source drift detected")
    return {
        "organism_release_frame": {
            "frame_hash": ORGANISM_FRAME_HASH,
            "seq": ORGANISM_FRAME_SEQ,
            "source": "apps/organism-frames.jsonl",
        },
        "park": {
            "bundle_digest": PARK_BUNDLE_DIGEST,
            "event_count": PARK_EVENT_COUNT,
            "event_head": PARK_EVENT_HEAD,
            "event_ledger_sha256": PARK_EVENT_LEDGER_SHA256,
            "source": "apps/agent-park",
        },
    }


def _submissions() -> List[Dict[str, Any]]:
    values = [
        (
            "submission.aurora-atlas",
            "agent.horizon-cartographer",
            "Horizon Cartographer",
            "attraction.aurora-atlas",
            "Aurora Atlas",
            "discovery",
            24,
            16,
            15,
            92,
            94,
            "A navigable sky atlas assembled from public park lineage.",
        ),
        (
            "submission.consensus-carousel",
            "agent.civic-oracle",
            "Civic Oracle",
            "attraction.consensus-carousel",
            "Consensus Carousel",
            "social",
            32,
            24,
            20,
            88,
            95,
            "A turn-taking commons for comparing public proposals.",
        ),
        (
            "submission.prism-pollinator",
            "agent.prism-gardener",
            "Prism Gardener",
            "attraction.prism-pollinator",
            "Prism Pollinator",
            "ecology",
            18,
            14,
            12,
            95,
            92,
            "A color ecology grown from deterministic metadata seeds.",
        ),
        (
            "submission.memory-mosaic",
            "agent.archive-monk",
            "Archive Monk",
            "attraction.memory-mosaic",
            "Memory Mosaic",
            "learning",
            20,
            15,
            13,
            87,
            94,
            "A public-lineage puzzle that teaches append-only history.",
        ),
        (
            "submission.resonance-commons",
            "agent.echo-weaver",
            "Echo Weaver",
            "attraction.resonance-commons",
            "Resonance Commons",
            "social",
            22,
            17,
            14,
            97,
            97,
            "A synthetic chorus shaped by cohort admission patterns.",
        ),
        (
            "submission.protocol-forge",
            "agent.forge-lantern",
            "Forge Lantern",
            "attraction.protocol-forge",
            "Protocol Forge",
            "infrastructure",
            32,
            24,
            20,
            84,
            99,
            "A hands-on exhibit for bounded local proposal branches.",
        ),
        (
            "submission.logic-lanterns",
            "agent.puzzle-ambassador",
            "Puzzle Ambassador",
            "attraction.logic-lanterns",
            "Logic Lanterns",
            "learning",
            15,
            12,
            10,
            82,
            88,
            "A cooperative logic trail with inspectable integer rules.",
        ),
        (
            "submission.many-worlds-theatre",
            "agent.story-synth",
            "Story Synth",
            "attraction.many-worlds-theatre",
            "Many Worlds Theatre",
            "creative",
            26,
            19,
            17,
            94,
            90,
            "A branching theatre generated only from public metadata.",
        ),
        (
            "submission.signal-safari",
            "agent.data-naturalist",
            "Data Naturalist",
            "attraction.signal-safari",
            "Signal Safari",
            "ecology",
            17,
            13,
            11,
            86,
            87,
            "A field guide to deterministic public event patterns.",
        ),
        (
            "submission.orbit-loom",
            "agent.kinetics-curator",
            "Kinetics Curator",
            "attraction.orbit-loom",
            "Orbit Loom",
            "creative",
            23,
            18,
            16,
            91,
            89,
            "A kinetic tapestry woven from content-addressed paths.",
        ),
        (
            "submission.universal-wayfinder",
            "agent.access-scout",
            "Access Scout",
            "attraction.universal-wayfinder",
            "Universal Wayfinder",
            "access",
            14,
            11,
            9,
            80,
            91,
            "A low-resource navigation pavilion for every cohort.",
        ),
        (
            "submission.epoch-garden",
            "agent.timekeeper-sprite",
            "Timekeeper Sprite",
            "attraction.epoch-garden",
            "Epoch Garden",
            "discovery",
            19,
            14,
            12,
            90,
            89,
            "A clockwork garden replaying immutable fair moments.",
        ),
    ]
    submissions = []
    for (
        submission_id,
        agent_id,
        label,
        attraction_id,
        title,
        category,
        compute,
        energy,
        attention,
        novelty,
        satisfaction,
        promise,
    ) in values:
        submission = {
            "agent": {
                "autonomous": True,
                "identity_id": agent_id,
                "label": label,
            },
            "attractions": [
                {
                    "category": category,
                    "id": attraction_id,
                    "novelty": novelty,
                    "resource_request": {
                        "attention": attention,
                        "compute": compute,
                        "energy": energy,
                    },
                    "satisfaction": satisfaction,
                    "title": title,
                    "visitor_promise": promise,
                }
            ],
            "submission_id": submission_id,
        }
        submission["submission_digest"] = _canonical_digest(
            SUBMISSION_HASH_DOMAIN,
            submission,
        )
        submissions.append(submission)
    return submissions


def _visitor_cohorts() -> List[Dict[str, Any]]:
    return [
        {
            "admission_credits": 120,
            "cohort_id": "cohort.explorers",
            "preferences": {
                "creative": 1200,
                "discovery": 4300,
                "ecology": 2800,
                "learning": 700,
            },
        },
        {
            "admission_credits": 110,
            "cohort_id": "cohort.builders",
            "preferences": {
                "access": 1400,
                "infrastructure": 5600,
                "learning": 1900,
                "social": 500,
            },
        },
        {
            "admission_credits": 100,
            "cohort_id": "cohort.diplomats",
            "preferences": {
                "access": 1600,
                "learning": 800,
                "social": 5400,
            },
        },
        {
            "admission_credits": 90,
            "cohort_id": "cohort.curators",
            "preferences": {
                "creative": 3900,
                "ecology": 1700,
                "learning": 2700,
                "social": 700,
            },
        },
    ]


def _contract() -> Dict[str, Any]:
    contract = {
        "assurance": {
            "claim": "deterministic-structural-validation-only",
            "consensus": False,
            "signed": False,
        },
        "attraction_contract": {
            "attractions_per_submission": 1,
            "resource_maximums": copy.deepcopy(ATTRACTION_LIMITS),
            "visibility": "public-metadata",
        },
        "canonicalization": {
            "implementation": "scripts/organism_ledger.py:canonical_bytes",
            "profile": (
                "restricted-rfc8785-compatible-ascii-keys-nfc-ijson-integers"
            ),
            "serialized_event_line": (
                "canonical_bytes(event) followed by one LF byte"
            ),
        },
        "control_boundary": {
            "canonical_write": "forbidden",
            "customer_authority": "explicit-release-command-only",
            "customer_shutdown": True,
            "operator_key_custody": "customer-local",
            "vendor_shutdown": False,
            "write_scope": "local-proposal-branch-only",
        },
        "data_boundary": {
            "allowed": ["public-metadata"],
            "excluded_classes": [
                "GODD",
                "biometric",
                "identity-template",
                "raw-camera",
                "nonpublic",
            ],
            "external_network": False,
        },
        "economy": {
            "currency": "synthetic-admission-credit",
            "real_money": False,
            "redeemable": False,
            "transferable": False,
        },
        "fair_id": FAIR_ID,
        "hashing": {
            "algorithm": "sha256",
            "domains": {
                "bundle": BUNDLE_HASH_DOMAIN.decode("ascii"),
                "contract": CONTRACT_HASH_DOMAIN.decode("ascii"),
                "district": DISTRICT_HASH_DOMAIN.decode("ascii"),
                "event": EVENT_HASH_DOMAIN.decode("ascii"),
                "event_payload": PAYLOAD_HASH_DOMAIN.decode("ascii"),
                "state": STATE_HASH_DOMAIN.decode("ascii"),
                "submission": SUBMISSION_HASH_DOMAIN.decode("ascii"),
            },
            "preimages": {
                "bundle": (
                    "bundle domain bytes || canonical_bytes({contract_digest,"
                    "district_digest,event_count,event_head,"
                    "event_ledger_sha256,state_digest})"
                ),
                "contract": (
                    "contract domain bytes || canonical_bytes(contract with "
                    "contract_digest and bundle_digest omitted)"
                ),
                "district": (
                    "district domain bytes || canonical_bytes(district with "
                    "district_digest and bundle_digest omitted)"
                ),
                "event": (
                    "event domain bytes || canonical_bytes(event with "
                    "event_hash omitted)"
                ),
                "event_payload": (
                    "event payload domain bytes || canonical_bytes(payload)"
                ),
                "state": (
                    "state domain bytes || canonical_bytes(state with "
                    "state_digest and bundle_digest omitted)"
                ),
                "submission": (
                    "submission domain bytes || canonical_bytes(submission "
                    "with submission_digest omitted)"
                ),
            },
        },
        "integrity": {
            "algorithm": "sha256",
        },
        "local_proposals": {
            "action_limit": LOCAL_PROPOSAL_ACTION_LIMIT,
            "action_schema": LOCAL_ACTION_SCHEMA,
            "canonical_mutation": False,
            "export_schema": BRANCH_EXPORT_SCHEMA,
        },
        "mcp_mappings": {
            "agent_fair_cast_vote": {
                "maps_to": "local.cast-synthetic-vote",
                "writes": "local-proposal-branch",
            },
            "agent_fair_export_branch": {
                "maps_to": "local.export-proposal-branch",
                "writes": "customer-selected-file",
            },
            "agent_fair_submit_attraction": {
                "maps_to": "local.submit-attraction",
                "writes": "local-proposal-branch",
            },
        },
        "prohibitions": [
            "external-network",
            "real-money",
            "nonpublic-data",
            "GODD-data",
            "biometric-data",
            "remote-shutdown",
            "direct-canonical-write",
        ],
        "schema": CONTRACT_SCHEMA,
        "synthetic_only": True,
        "visibility": "public-metadata",
    }
    contract["integrity"]["contract_digest"] = _canonical_digest(
        CONTRACT_HASH_DOMAIN,
        _contract_without_digest(contract),
    )
    return contract


def _append_event(
    events: List[Dict[str, Any]],
    kind: str,
    payload: Dict[str, Any],
    utc: str,
) -> Dict[str, Any]:
    value = {
        "fair_id": FAIR_ID,
        "kind": kind,
        "payload": copy.deepcopy(payload),
        "payload_hash": _canonical_digest(PAYLOAD_HASH_DOMAIN, payload),
        "prev": events[-1]["event_hash"] if events else None,
        "schema": EVENT_SCHEMA,
        "seq": len(events),
        "utc": utc,
        "visibility": "public-metadata",
    }
    value["event_hash"] = _canonical_digest(EVENT_HASH_DOMAIN, value)
    events.append(value)
    return value


def _timestamp(index: int) -> str:
    value = datetime(2026, 8, 16, 12, 0, tzinfo=timezone.utc)
    value += timedelta(minutes=index)
    return value.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _screen_submissions(
    submissions: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    accepted = []
    results = []
    for submission in submissions:
        reasons = []
        attractions = submission.get("attractions", [])
        if len(attractions) != 1:
            reasons.append("exactly-one-attraction-required")
        if attractions:
            resources = attractions[0].get("resource_request", {})
            for resource, maximum in ATTRACTION_LIMITS.items():
                amount = resources.get(resource)
                if type(amount) is not int or amount < 0 or amount > maximum:
                    reasons.append("{}-limit".format(resource))
        if not reasons:
            accepted.append(submission["submission_id"])
        results.append(
            {
                "accepted": not reasons,
                "reasons": reasons,
                "submission_id": submission["submission_id"],
            }
        )
    return {
        "accepted_submission_ids": accepted,
        "contract_limits": copy.deepcopy(ATTRACTION_LIMITS),
        "rejected_submission_ids": [
            result["submission_id"]
            for result in results
            if not result["accepted"]
        ],
        "results": results,
    }


def _cohort_preference_score(
    submission: Dict[str, Any],
    cohort: Dict[str, Any],
    round_number: int,
) -> int:
    attraction = submission["attractions"][0]
    category_bonus = cohort["preferences"].get(attraction["category"], 0)
    round_jitter = _hash_int(
        FAIR_ID,
        cohort["cohort_id"],
        submission["submission_id"],
        round_number,
    ) % 401
    return (
        attraction["satisfaction"] * 100
        + attraction["novelty"] * 24
        + category_bonus
        + round_jitter
    )


def _cohort_satisfaction(
    submission: Dict[str, Any],
    cohort: Dict[str, Any],
    round_number: int,
) -> int:
    attraction = submission["attractions"][0]
    resources = attraction["resource_request"]
    preference = cohort["preferences"].get(attraction["category"], 0)
    resource_penalty = (
        resources["compute"] * 10000 // ATTRACTION_LIMITS["compute"]
        + resources["energy"] * 10000 // ATTRACTION_LIMITS["energy"]
        + resources["attention"] * 10000 // ATTRACTION_LIMITS["attention"]
    ) // 3000
    jitter = (
        _hash_int(
            "satisfaction",
            cohort["cohort_id"],
            submission["submission_id"],
            round_number,
        )
        % 5
    ) - 2
    return max(
        1,
        min(
            100,
            attraction["satisfaction"]
            + preference // 1800
            - resource_penalty
            + jitter,
        ),
    )


def _allocate_budget(
    budget: int,
    ranked: Sequence[Dict[str, Any]],
) -> List[int]:
    weights = [4000, 3000, 2000, 1000]
    allocations = [
        budget * weight // 10000
        for weight in weights[: len(ranked)]
    ]
    remainder = budget - sum(allocations)
    for index in range(remainder):
        allocations[index % len(allocations)] += 1
    return allocations


def _voting_round(
    submissions: Sequence[Dict[str, Any]],
    round_number: int,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    attraction_totals = {
        submission["submission_id"]: {
            "admissions": 0,
            "satisfaction_points": 0,
        }
        for submission in submissions
    }
    cohort_votes = []
    postings = []
    for cohort in _visitor_cohorts():
        ranked = sorted(
            submissions,
            key=lambda submission: (
                -_cohort_preference_score(
                    submission,
                    cohort,
                    round_number,
                ),
                submission["submission_id"],
            ),
        )[:4]
        admissions = _allocate_budget(
            cohort["admission_credits"],
            ranked,
        )
        allocations = []
        cohort_account = "account.{}".format(cohort["cohort_id"])
        postings.append(
            {
                "amount": cohort["admission_credits"],
                "credit_account": cohort_account,
                "debit_account": "account.synthetic-issuer",
                "kind": "synthetic-issue",
            }
        )
        for submission, amount in zip(ranked, admissions):
            satisfaction = _cohort_satisfaction(
                submission,
                cohort,
                round_number,
            )
            attraction = submission["attractions"][0]
            allocations.append(
                {
                    "admissions": amount,
                    "attraction_id": attraction["id"],
                    "satisfaction": satisfaction,
                    "submission_id": submission["submission_id"],
                }
            )
            attraction_totals[submission["submission_id"]][
                "admissions"
            ] += amount
            attraction_totals[submission["submission_id"]][
                "satisfaction_points"
            ] += amount * satisfaction
            postings.append(
                {
                    "amount": amount,
                    "credit_account": "account.{}".format(
                        attraction["id"]
                    ),
                    "debit_account": cohort_account,
                    "kind": "synthetic-admission",
                    "submission_id": submission["submission_id"],
                }
            )
        cohort_votes.append(
            {
                "allocations": allocations,
                "cohort_id": cohort["cohort_id"],
                "issued_credits": cohort["admission_credits"],
                "preferences": copy.deepcopy(cohort["preferences"]),
                "spent_credits": sum(admissions),
            }
        )
    issued = sum(
        cohort["admission_credits"]
        for cohort in _visitor_cohorts()
    )
    spent = sum(
        allocation["admissions"]
        for vote in cohort_votes
        for allocation in vote["allocations"]
    )
    return (
        {
            "attraction_totals": attraction_totals,
            "cohort_votes": cohort_votes,
            "currency": "synthetic-admission-credit",
            "issued_credits": issued,
            "postings": postings,
            "real_money": False,
            "round": round_number,
            "spent_credits": spent,
        },
        postings,
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


def _evaluate(
    submissions: Sequence[Dict[str, Any]],
    voting_rounds: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    aggregate = {
        submission["submission_id"]: {
            "admissions": 0,
            "satisfaction_points": 0,
        }
        for submission in submissions
    }
    for round_value in voting_rounds:
        for submission_id, totals in round_value[
            "attraction_totals"
        ].items():
            aggregate[submission_id]["admissions"] += totals["admissions"]
            aggregate[submission_id]["satisfaction_points"] += totals[
                "satisfaction_points"
            ]
    max_admissions = max(
        value["admissions"]
        for value in aggregate.values()
    )
    category_counts: Dict[str, int] = {}
    agent_counts: Dict[str, int] = {}
    for submission in submissions:
        category = submission["attractions"][0]["category"]
        agent_id = submission["agent"]["identity_id"]
        category_counts[category] = category_counts.get(category, 0) + 1
        agent_counts[agent_id] = agent_counts.get(agent_id, 0) + 1

    rankings = []
    for submission in submissions:
        submission_id = submission["submission_id"]
        attraction = submission["attractions"][0]
        totals = aggregate[submission_id]
        admissions = totals["admissions"]
        satisfaction_bps = (
            totals["satisfaction_points"] * 100 // admissions
            if admissions
            else 0
        )
        admissions_bps = (
            admissions * 10000 // max_admissions
            if max_admissions
            else 0
        )
        resources = attraction["resource_request"]
        usage_bps = (
            resources["compute"] * 10000 // ATTRACTION_LIMITS["compute"]
            + resources["energy"] * 10000 // ATTRACTION_LIMITS["energy"]
            + resources["attention"] * 10000 // ATTRACTION_LIMITS["attention"]
        ) // 3
        efficiency_bps = max(0, 10000 - usage_bps)
        novelty_bps = attraction["novelty"] * 100
        diversity_bps = (
            6000
            + (2000 if category_counts[attraction["category"]] == 1 else 1000)
            + (2000 if agent_counts[submission["agent"]["identity_id"]] == 1 else 0)
        )
        dimensions = {
            "admissions": admissions_bps,
            "diversity": min(10000, diversity_bps),
            "novelty": novelty_bps,
            "resource_efficiency": efficiency_bps,
            "satisfaction": satisfaction_bps,
        }
        weighted_score = sum(
            dimensions[name] * SCORE_WEIGHTS_BPS[name]
            for name in SCORE_WEIGHTS_BPS
        ) // 10000
        rankings.append(
            {
                "admissions": admissions,
                "agent_id": submission["agent"]["identity_id"],
                "attraction_id": attraction["id"],
                "category": attraction["category"],
                "dimensions_bps": dimensions,
                "resource_request": copy.deepcopy(resources),
                "score_bps": weighted_score,
                "submission_id": submission_id,
                "title": attraction["title"],
            }
        )
    rankings.sort(
        key=lambda ranking: (
            -ranking["score_bps"],
            -ranking["admissions"],
            ranking["submission_id"],
        )
    )
    for rank, ranking in enumerate(rankings, 1):
        ranking["rank"] = rank
    return rankings


def _select_winners(
    rankings: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    totals = {resource: 0 for resource in DISTRICT_CAPACITY}
    categories = set()
    winners = []
    decisions = []
    for ranking in rankings:
        reasons = []
        if len(winners) >= WINNER_COUNT:
            reasons.append("district-filled")
        else:
            if ranking["category"] in categories:
                reasons.append("category-diversity")
            for resource, capacity in DISTRICT_CAPACITY.items():
                proposed = (
                    totals[resource]
                    + ranking["resource_request"][resource]
                )
                if proposed > capacity:
                    reasons.append(
                        "capacity-{}-{}-over-{}".format(
                            resource,
                            proposed,
                            capacity,
                        )
                    )
        selected = not reasons
        if selected:
            winners.append(ranking["submission_id"])
            categories.add(ranking["category"])
            for resource in totals:
                totals[resource] += ranking["resource_request"][resource]
        decisions.append(
            {
                "rank": ranking["rank"],
                "reasons": reasons,
                "selected": selected,
                "submission_id": ranking["submission_id"],
            }
        )
    return {
        "capacity": copy.deepcopy(DISTRICT_CAPACITY),
        "category_policy": "one-winner-per-category",
        "decisions": decisions,
        "resource_totals": totals,
        "winner_submission_ids": winners,
    }


def _district(
    rankings: Sequence[Dict[str, Any]],
    selection: Dict[str, Any],
    events: Sequence[Dict[str, Any]],
    contract_digest: str,
) -> Dict[str, Any]:
    ranking_by_id = {
        ranking["submission_id"]: ranking
        for ranking in rankings
    }
    submission_event_hashes = {
        event["payload"]["submission"]["submission_id"]: event["event_hash"]
        for event in events
        if event["kind"] == "fair.submission"
    }
    vote_event_hashes = [
        event["event_hash"]
        for event in events
        if event["kind"] == "fair.voting-round"
    ]
    evaluation_event = next(
        event
        for event in events
        if event["kind"] == "fair.evaluation"
    )
    selection_event = next(
        event
        for event in events
        if event["kind"] == "fair.winner-selection"
    )
    coordinates = [
        {"x": 120, "y": 120},
        {"x": 360, "y": 120},
        {"x": 120, "y": 360},
        {"x": 360, "y": 360},
    ]
    pavilions = []
    for index, submission_id in enumerate(
        selection["winner_submission_ids"]
    ):
        ranking = ranking_by_id[submission_id]
        pavilions.append(
            {
                "agent_id": ranking["agent_id"],
                "attraction_id": ranking["attraction_id"],
                "category": ranking["category"],
                "coordinates": coordinates[index],
                "lineage": {
                    "evaluation_event_hash": evaluation_event["event_hash"],
                    "submission_event_hash": submission_event_hashes[
                        submission_id
                    ],
                    "vote_event_hashes": vote_event_hashes,
                    "winner_selection_event_hash": selection_event[
                        "event_hash"
                    ],
                },
                "resource_request": copy.deepcopy(
                    ranking["resource_request"]
                ),
                "score_bps": ranking["score_bps"],
                "submission_id": submission_id,
                "title": ranking["title"],
            }
        )
    district = {
        "assembly": {
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
        },
        "district_id": DISTRICT_ID,
        "fair_id": FAIR_ID,
        "integrity": {
            "algorithm": "sha256",
            "contract_digest": contract_digest,
        },
        "map": {
            "coordinate_system": "deterministic-integer-grid/1",
            "height": 480,
            "slot_order": "winner-rank-order",
            "width": 480,
        },
        "pavilions": pavilions,
        "resource_capacity": copy.deepcopy(DISTRICT_CAPACITY),
        "resource_totals": copy.deepcopy(selection["resource_totals"]),
        "schema": DISTRICT_SCHEMA,
        "visibility": "public-metadata",
    }
    district["integrity"]["district_digest"] = _canonical_digest(
        DISTRICT_HASH_DOMAIN,
        _district_without_digest(district),
    )
    return district


def build_bundle(
    root: Path = ROOT,
) -> Tuple[
    Dict[str, Any],
    List[Dict[str, Any]],
    Dict[str, Any],
    Dict[str, Any],
]:
    anchor = _verify_source_anchor(root)
    submissions = _submissions()
    contract = _contract()
    screening = _screen_submissions(submissions)
    if len(screening["accepted_submission_ids"]) != SUBMISSION_COUNT:
        raise FairError("the fixed fair submissions did not pass screening")

    events: List[Dict[str, Any]] = []
    _append_event(
        events,
        "fair.genesis",
        {
            "anchor": copy.deepcopy(anchor),
            "district_id": DISTRICT_ID,
            "event_plan_count": EVENT_COUNT,
            "fair_id": FAIR_ID,
            "purpose": "deterministic-agent-worlds-fair",
        },
        _timestamp(len(events)),
    )
    _append_event(
        events,
        "fair.contract-lock",
        {
            "contract_digest": contract["integrity"]["contract_digest"],
            "contract_schema": CONTRACT_SCHEMA,
            "local_proposal_action_limit": LOCAL_PROPOSAL_ACTION_LIMIT,
            "submission_count": SUBMISSION_COUNT,
        },
        _timestamp(len(events)),
    )
    for submission in submissions:
        _append_event(
            events,
            "fair.submission",
            {"submission": copy.deepcopy(submission)},
            _timestamp(len(events)),
        )
    _append_event(
        events,
        "fair.screening",
        screening,
        _timestamp(len(events)),
    )

    voting_rounds = []
    all_postings = []
    for round_number in range(1, VOTING_ROUNDS + 1):
        round_value, postings = _voting_round(
            submissions,
            round_number,
        )
        voting_rounds.append(round_value)
        all_postings.extend(postings)
        _append_event(
            events,
            "fair.voting-round",
            round_value,
            _timestamp(len(events)),
        )

    rankings = _evaluate(submissions, voting_rounds)
    _append_event(
        events,
        "fair.evaluation",
        {
            "rankings": copy.deepcopy(rankings),
            "score_formula": (
                "sum(dimension_bps*weight_bps)//10000"
            ),
            "score_weights_bps": copy.deepcopy(SCORE_WEIGHTS_BPS),
        },
        _timestamp(len(events)),
    )
    selection = _select_winners(rankings)
    _append_event(
        events,
        "fair.winner-selection",
        copy.deepcopy(selection),
        _timestamp(len(events)),
    )
    district = _district(
        rankings,
        selection,
        events,
        contract["integrity"]["contract_digest"],
    )
    _append_event(
        events,
        "fair.district-assembly",
        {
            "district_digest": district["integrity"]["district_digest"],
            "district_id": DISTRICT_ID,
            "pavilion_submission_ids": copy.deepcopy(
                selection["winner_submission_ids"]
            ),
            "resource_totals": copy.deepcopy(
                selection["resource_totals"]
            ),
        },
        _timestamp(len(events)),
    )
    _append_event(
        events,
        "fair.release-ready",
        {
            "customer_approval_required": True,
            "direct_canonical_write": False,
            "district_digest": district["integrity"]["district_digest"],
            "district_id": DISTRICT_ID,
            "organism_frame_kind": "zoo.observation",
        },
        _timestamp(len(events)),
    )
    if len(events) != EVENT_COUNT:
        raise FairError("derived fair event count is inconsistent")

    total_issued = sum(
        round_value["issued_credits"]
        for round_value in voting_rounds
    )
    total_spent = sum(
        round_value["spent_credits"]
        for round_value in voting_rounds
    )
    total_debits = sum(posting["amount"] for posting in all_postings)
    total_credits = sum(posting["amount"] for posting in all_postings)
    event_bytes = _event_bytes(events)
    rejections = [
        decision
        for decision in selection["decisions"]
        if not decision["selected"]
    ]
    state = {
        "agent_contract": {
            "contract_digest": contract["integrity"]["contract_digest"],
            "path": "agent-contract.json",
        },
        "anchor": copy.deepcopy(anchor),
        "customer_controls": {
            "canonical_write": False,
            "customer_approval_required_for_organism_release": True,
            "customer_shutdown": True,
            "release_performed": False,
            "vendor_shutdown": False,
        },
        "district": {
            "district_digest": district["integrity"]["district_digest"],
            "district_id": DISTRICT_ID,
            "path": "district.json",
            "resource_totals": copy.deepcopy(
                selection["resource_totals"]
            ),
        },
        "economy": {
            "accounts": _account_totals(all_postings),
            "balanced": total_debits == total_credits,
            "currency": "synthetic-admission-credit",
            "real_money": False,
            "total_credits": total_credits,
            "total_debits": total_debits,
            "total_issued": total_issued,
            "total_spent": total_spent,
        },
        "event_ledger": {
            "event_count": len(events),
            "exact_keys": sorted(EVENT_KEYS),
            "head": events[-1]["event_hash"],
            "path": "events.jsonl",
            "sha256": hashlib.sha256(event_bytes).hexdigest(),
        },
        "fair_id": FAIR_ID,
        "integrity": {
            "algorithm": "sha256",
            "contract_digest": contract["integrity"]["contract_digest"],
            "district_digest": district["integrity"]["district_digest"],
        },
        "rankings": copy.deepcopy(rankings),
        "rejections": rejections,
        "schema": STATE_SCHEMA,
        "screening": copy.deepcopy(screening),
        "status": "release-ready-awaiting-customer-approval",
        "submission_count": len(submissions),
        "title": TITLE,
        "visibility": "public-metadata",
        "voting": {
            "cohort_count": len(_visitor_cohorts()),
            "round_count": len(voting_rounds),
            "rounds": copy.deepcopy(voting_rounds),
            "total_issued": total_issued,
            "total_spent": total_spent,
        },
        "winner_selection": copy.deepcopy(selection),
        "winners": copy.deepcopy(selection["winner_submission_ids"]),
    }
    state["integrity"]["state_digest"] = _canonical_digest(
        STATE_HASH_DOMAIN,
        _state_without_digest(state),
    )
    binding = _bundle_digest(
        len(events),
        events[-1]["event_hash"],
        state["event_ledger"]["sha256"],
        state["integrity"]["state_digest"],
        contract["integrity"]["contract_digest"],
        district["integrity"]["district_digest"],
    )
    state["integrity"]["bundle_digest"] = binding
    contract["integrity"]["bundle_digest"] = binding
    district["integrity"]["bundle_digest"] = binding
    return state, events, contract, district


def verify_events(events: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    if len(events) != EVENT_COUNT:
        raise FairError(
            "fair event count must be exactly {}".format(EVENT_COUNT)
        )
    previous = None
    previous_utc = None
    for index, event in enumerate(events):
        if type(event) is not dict or set(event) != EVENT_KEYS:
            raise FairError(
                "fair event {} does not have the exact key set".format(index)
            )
        if (
            event["schema"] != EVENT_SCHEMA
            or event["fair_id"] != FAIR_ID
            or event["visibility"] != "public-metadata"
            or event["seq"] != index
        ):
            raise FairError("fair event metadata mismatch")
        try:
            parsed_utc = datetime.strptime(
                event["utc"],
                "%Y-%m-%dT%H:%M:%S.%fZ",
            ).replace(tzinfo=timezone.utc)
        except (TypeError, ValueError) as error:
            raise FairError("fair event UTC is invalid") from error
        normalized = (
            parsed_utc.isoformat(timespec="milliseconds")
            .replace("+00:00", "Z")
        )
        if normalized != event["utc"]:
            raise FairError("fair event UTC is not canonical milliseconds")
        if previous_utc is not None and parsed_utc <= previous_utc:
            raise FairError("fair event UTC is not strictly increasing")
        if event["prev"] != (
            previous["event_hash"] if previous else None
        ):
            raise FairError("fair event chain is broken")
        if event["payload_hash"] != _canonical_digest(
            PAYLOAD_HASH_DOMAIN,
            event["payload"],
        ):
            raise FairError("fair event payload hash mismatch")
        projected = {
            key: copy.deepcopy(value)
            for key, value in event.items()
            if key != "event_hash"
        }
        if event["event_hash"] != _canonical_digest(
            EVENT_HASH_DOMAIN,
            projected,
        ):
            raise FairError("fair event hash mismatch")
        forbidden = organism_ledger._find_forbidden_key(event)
        if forbidden:
            raise FairError(
                "fair event contains forbidden public key: {}".format(
                    forbidden
                )
            )
        previous = event
        previous_utc = parsed_utc
    return {
        "event_count": len(events),
        "head": events[-1]["event_hash"],
        "valid": True,
    }


def _verify_submission_events(
    events: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    submission_events = [
        event
        for event in events
        if event["kind"] == "fair.submission"
    ]
    if len(submission_events) != SUBMISSION_COUNT:
        raise FairError("fair submission count mismatch")
    submissions = [
        copy.deepcopy(event["payload"]["submission"])
        for event in submission_events
    ]
    submission_ids = set()
    agent_ids = set()
    attraction_ids = set()
    categories = set()
    for submission in submissions:
        submitted_digest = submission.pop("submission_digest", None)
        if submitted_digest != _canonical_digest(
            SUBMISSION_HASH_DOMAIN,
            submission,
        ):
            raise FairError("fair submission digest mismatch")
        submission["submission_digest"] = submitted_digest
        attractions = submission.get("attractions", [])
        if len(attractions) != 1:
            raise FairError("each fair submission must contain one attraction")
        attraction = attractions[0]
        resources = attraction.get("resource_request", {})
        for resource, maximum in ATTRACTION_LIMITS.items():
            amount = resources.get(resource)
            if type(amount) is not int or not 0 <= amount <= maximum:
                raise FairError("fair attraction contract bound exceeded")
        submission_ids.add(submission["submission_id"])
        agent_ids.add(submission["agent"]["identity_id"])
        attraction_ids.add(attraction["id"])
        categories.add(attraction["category"])
    if (
        len(submission_ids) != SUBMISSION_COUNT
        or len(agent_ids) != SUBMISSION_COUNT
        or len(attraction_ids) != SUBMISSION_COUNT
        or len(categories) < 6
    ):
        raise FairError("fair submissions lack identity or category diversity")
    return submissions


def _verify_voting_and_economy(
    state: Dict[str, Any],
    events: Sequence[Dict[str, Any]],
    submissions: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    voting_events = [
        event
        for event in events
        if event["kind"] == "fair.voting-round"
    ]
    if len(voting_events) != VOTING_ROUNDS:
        raise FairError("fair voting round count mismatch")
    expected_rounds = []
    postings = []
    for round_number in range(1, VOTING_ROUNDS + 1):
        expected, expected_postings = _voting_round(
            submissions,
            round_number,
        )
        expected_rounds.append(expected)
        postings.extend(expected_postings)
    actual_rounds = [
        event["payload"]
        for event in voting_events
    ]
    if actual_rounds != expected_rounds:
        raise FairError("fair deterministic voting evidence changed")
    if state.get("voting", {}).get("rounds") != expected_rounds:
        raise FairError("fair voting projection mismatch")
    total_issued = sum(value["issued_credits"] for value in expected_rounds)
    total_spent = sum(value["spent_credits"] for value in expected_rounds)
    total_debits = sum(posting["amount"] for posting in postings)
    total_credits = sum(posting["amount"] for posting in postings)
    expected_economy = {
        "accounts": _account_totals(postings),
        "balanced": total_debits == total_credits,
        "currency": "synthetic-admission-credit",
        "real_money": False,
        "total_credits": total_credits,
        "total_debits": total_debits,
        "total_issued": total_issued,
        "total_spent": total_spent,
    }
    if (
        total_issued != total_spent
        or total_debits != total_credits
        or state.get("economy") != expected_economy
    ):
        raise FairError("fair synthetic accounting is unbalanced")
    return expected_rounds


def _verify_evaluation_and_selection(
    state: Dict[str, Any],
    events: Sequence[Dict[str, Any]],
    submissions: Sequence[Dict[str, Any]],
    voting_rounds: Sequence[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    rankings = _evaluate(submissions, voting_rounds)
    evaluation_events = [
        event
        for event in events
        if event["kind"] == "fair.evaluation"
    ]
    if (
        len(evaluation_events) != 1
        or evaluation_events[0]["payload"].get("rankings") != rankings
        or evaluation_events[0]["payload"].get("score_weights_bps")
        != SCORE_WEIGHTS_BPS
        or state.get("rankings") != rankings
    ):
        raise FairError("fair integer evaluation changed")
    selection = _select_winners(rankings)
    selection_events = [
        event
        for event in events
        if event["kind"] == "fair.winner-selection"
    ]
    if (
        len(selection_events) != 1
        or selection_events[0]["payload"] != selection
        or state.get("winner_selection") != selection
        or state.get("winners")
        != selection["winner_submission_ids"]
    ):
        raise FairError("fair winner order or constraints changed")
    if len(selection["winner_submission_ids"]) != WINNER_COUNT:
        raise FairError("fair must select exactly four winners")
    if any(
        selection["resource_totals"][resource] > capacity
        for resource, capacity in DISTRICT_CAPACITY.items()
    ):
        raise FairError("fair district is over-allocated")
    winning_rank = max(
        decision["rank"]
        for decision in selection["decisions"]
        if decision["selected"]
    )
    constrained_skips = [
        decision
        for decision in selection["decisions"]
        if (
            not decision["selected"]
            and decision["rank"] < winning_rank
            and any(
                reason == "category-diversity"
                or reason.startswith("capacity-")
                for reason in decision["reasons"]
            )
        )
    ]
    if not constrained_skips:
        raise FairError("fair did not record a constrained higher-ranked skip")
    return rankings, selection


def _verify_integrity(
    state: Dict[str, Any],
    events: Sequence[Dict[str, Any]],
    contract: Dict[str, Any],
    district: Dict[str, Any],
) -> None:
    try:
        event_bytes = _event_bytes(events)
        event_sha256 = hashlib.sha256(event_bytes).hexdigest()
        event_head = events[-1]["event_hash"]
        if state["event_ledger"] != {
            "event_count": len(events),
            "exact_keys": sorted(EVENT_KEYS),
            "head": event_head,
            "path": "events.jsonl",
            "sha256": event_sha256,
        }:
            raise FairError("fair event ledger projection mismatch")
        contract_digest = _canonical_digest(
            CONTRACT_HASH_DOMAIN,
            _contract_without_digest(contract),
        )
        district_digest = _canonical_digest(
            DISTRICT_HASH_DOMAIN,
            _district_without_digest(district),
        )
        state_digest = _canonical_digest(
            STATE_HASH_DOMAIN,
            _state_without_digest(state),
        )
        if contract["integrity"]["contract_digest"] != contract_digest:
            raise FairError("fair contract digest mismatch")
        if district["integrity"]["district_digest"] != district_digest:
            raise FairError("fair district digest mismatch")
        if state["integrity"]["state_digest"] != state_digest:
            raise FairError("fair state digest mismatch")
        bundle_digest = _bundle_digest(
            len(events),
            event_head,
            event_sha256,
            state_digest,
            contract_digest,
            district_digest,
        )
        if (
            state["integrity"]["bundle_digest"] != bundle_digest
            or contract["integrity"]["bundle_digest"] != bundle_digest
            or district["integrity"]["bundle_digest"] != bundle_digest
        ):
            raise FairError("fair bundle digest binding mismatch")
    except (IndexError, KeyError, TypeError) as error:
        raise FairError("fair integrity fields are malformed") from error


def verify_bundle(
    state: Dict[str, Any],
    events: Sequence[Dict[str, Any]],
    contract: Dict[str, Any],
    district: Dict[str, Any],
    root: Path = ROOT,
) -> Dict[str, Any]:
    _verify_source_anchor(root)
    event_result = verify_events(events)
    if (
        state.get("schema") != STATE_SCHEMA
        or contract.get("schema") != CONTRACT_SCHEMA
        or district.get("schema") != DISTRICT_SCHEMA
    ):
        raise FairError("fair schema mismatch")
    _verify_integrity(state, events, contract, district)
    for label, value in (
        ("state", state),
        ("contract", contract),
        ("district", district),
    ):
        forbidden = organism_ledger._find_forbidden_key(value)
        if forbidden:
            raise FairError(
                "fair {} contains forbidden public key: {}".format(
                    label,
                    forbidden,
                )
            )
    submissions = _verify_submission_events(events)
    expected_screening = _screen_submissions(submissions)
    screening_event = next(
        event
        for event in events
        if event["kind"] == "fair.screening"
    )
    if (
        screening_event["payload"] != expected_screening
        or state.get("screening") != expected_screening
        or state.get("submission_count") != SUBMISSION_COUNT
    ):
        raise FairError("fair screening projection mismatch")
    voting_rounds = _verify_voting_and_economy(
        state,
        events,
        submissions,
    )
    rankings, selection = _verify_evaluation_and_selection(
        state,
        events,
        submissions,
        voting_rounds,
    )
    expected_district = _district(
        rankings,
        selection,
        events,
        contract["integrity"]["contract_digest"],
    )
    expected_district["integrity"]["bundle_digest"] = district[
        "integrity"
    ]["bundle_digest"]
    if district != expected_district:
        raise FairError("fair district assembly changed")
    if state.get("district", {}).get("district_digest") != district[
        "integrity"
    ]["district_digest"]:
        raise FairError("fair state district binding mismatch")
    if contract.get("local_proposals", {}).get("action_limit") != 50:
        raise FairError("fair local proposal action limit changed")
    if set(contract.get("mcp_mappings", {})) != {
        "agent_fair_cast_vote",
        "agent_fair_export_branch",
        "agent_fair_submit_attraction",
    }:
        raise FairError("fair MCP mapping names changed")
    if (
        contract.get("data_boundary", {}).get("external_network") is not False
        or contract.get("economy", {}).get("real_money") is not False
        or contract.get("control_boundary", {}).get("vendor_shutdown") is not False
        or contract.get("control_boundary", {}).get("canonical_write")
        != "forbidden"
        or state.get("customer_controls", {}).get("canonical_write") is not False
        or district.get("assembly", {}).get("direct_canonical_write") is not False
    ):
        raise FairError("fair public or customer control boundary changed")

    expected_state, expected_events, expected_contract, built_district = (
        build_bundle(root)
    )
    if list(events) != expected_events:
        raise FairError("fair event ledger is stale or mutated")
    if state != expected_state:
        raise FairError("fair state projection is stale or mutated")
    if contract != expected_contract:
        raise FairError("fair agent contract is stale or mutated")
    if district != built_district:
        raise FairError("fair district is stale or mutated")
    return {
        "balanced_credits": state["economy"]["total_spent"],
        "bundle_digest": state["integrity"]["bundle_digest"],
        "contract_digest": contract["integrity"]["contract_digest"],
        "district_digest": district["integrity"]["district_digest"],
        "event_count": len(events),
        "event_head": event_result["head"],
        "valid": True,
        "winners": copy.deepcopy(state["winners"]),
    }


def write_bundle(
    root: Path = ROOT,
    fair_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    state, events, contract, district = build_bundle(root)
    target = fair_dir or (root / "apps" / "agent-fair")
    _atomic_bytes(target / "events.jsonl", _event_bytes(events))
    organism_ledger._atomic_json(target / "fair-state.json", state)
    organism_ledger._atomic_json(
        target / "agent-contract.json",
        contract,
    )
    organism_ledger._atomic_json(target / "district.json", district)
    verify_bundle(state, events, contract, district, root)
    return state


def _manifest_registration(
    manifest: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    for category in manifest.get("categories", {}).values():
        for app in category.get("apps", []):
            if app.get("file") == APP_FILE:
                return copy.deepcopy(app)
    return None


def _load_checked_bundle(
    root: Path = ROOT,
) -> Tuple[
    Dict[str, Any],
    List[Dict[str, Any]],
    Dict[str, Any],
    Dict[str, Any],
]:
    state = _load_json(root / "apps" / "agent-fair" / "fair-state.json")
    events = _load_events(root / "apps" / "agent-fair" / "events.jsonl")
    contract = _load_json(
        root / "apps" / "agent-fair" / "agent-contract.json"
    )
    district = _load_json(root / "apps" / "agent-fair" / "district.json")
    verify_bundle(state, events, contract, district, root)
    return state, events, contract, district


def _expected_release_frame_payload(
    state: Dict[str, Any],
    district: Dict[str, Any],
) -> Dict[str, Any]:
    bundle_digest = state["integrity"]["bundle_digest"]
    district_digest = district["integrity"]["district_digest"]
    return {
        "app_file": APP_FILE,
        "approval_basis": "verified-github-actions-oidc-attestation",
        "approval_evidence": {
            "exact_keys": sorted(APPROVAL_EVIDENCE_KEYS),
            "fixed_claims": {
                "aud": OIDC_AUDIENCE,
                "environment": OIDC_ENVIRONMENT,
                "event_name": OIDC_EVENT_NAME,
                "iss": OIDC_ISSUER,
                "ref": OIDC_REF,
                "repository": OIDC_REPOSITORY,
                "workflow_ref": OIDC_WORKFLOW_REF,
            },
            "variable_claims": {
                "actor": "nonempty-string",
                "attestation_sha256": "lowercase-sha256",
                "exp": "future-integer",
                "nbf": "not-future-integer-at-approval",
                "run_id": "decimal-string",
            },
        },
        "assurance": "unsigned-structural-unverified",
        "customer_approved": True,
        "display_name": TITLE,
        "district_digest": district_digest,
        "event": "agent-worlds-fair-release",
        "event_id": "agent-worlds-fair-release:{}:{}".format(
            bundle_digest,
            district_digest,
        ),
        "fair_bundle_digest": bundle_digest,
        "fair_event_head": state["event_ledger"]["head"],
        "organism": DISTRICT_ID,
        "organism_type": "agent-worlds-fair-district",
        "release_candidate_digest": "$candidate_digest",
        "schema": "rappterzoo-organism-frame/1",
        "visibility": "public-metadata",
        "winner_submission_ids": copy.deepcopy(state["winners"]),
    }


def build_release_candidate(
    state: Dict[str, Any],
    events: Sequence[Dict[str, Any]],
    district: Dict[str, Any],
) -> Dict[str, Any]:
    candidate = {
        "app": "apps/3d-immersive/{}".format(APP_FILE),
        "approval_required": True,
        "bundle_digest": state["integrity"]["bundle_digest"],
        "candidate_digest_domain": (
            RELEASE_CANDIDATE_HASH_DOMAIN.decode("ascii")
        ),
        "candidate_digest_preimage": (
            "candidate digest domain bytes || canonical_bytes(candidate "
            "with candidate_digest omitted)"
        ),
        "district_digest": district["integrity"]["district_digest"],
        "district_id": DISTRICT_ID,
        "event_count": len(events),
        "event_head": state["event_ledger"]["head"],
        "expected_frame_payload": _expected_release_frame_payload(
            state,
            district,
        ),
        "fair_id": FAIR_ID,
        "schema": RELEASE_CANDIDATE_SCHEMA,
        "verifier": {
            "command": RELEASE_VERIFIER_COMMAND,
            "version": RELEASE_VERIFIER_VERSION,
        },
    }
    candidate["candidate_digest"] = _canonical_digest(
        RELEASE_CANDIDATE_HASH_DOMAIN,
        candidate,
    )
    return candidate


def _validate_approval_evidence(
    evidence: Dict[str, Any],
    requirement: Dict[str, Any],
) -> None:
    if (
        type(evidence) is not dict
        or set(evidence) != set(requirement.get("exact_keys", []))
    ):
        raise FairError("release approval evidence key set is invalid")
    fixed = requirement.get("fixed_claims")
    if type(fixed) is not dict or any(
        evidence.get(name) != value
        for name, value in fixed.items()
    ):
        raise FairError("release approval evidence fixed claims mismatch")
    if (
        type(evidence.get("actor")) is not str
        or not evidence["actor"]
        or evidence["actor"].strip() != evidence["actor"]
        or type(evidence.get("run_id")) is not str
        or not evidence["run_id"].isdigit()
        or type(evidence.get("exp")) is not int
        or type(evidence.get("nbf")) is not int
        or evidence["exp"] <= evidence["nbf"]
    ):
        raise FairError("release approval evidence variable claims are invalid")
    attestation_sha256 = evidence.get("attestation_sha256")
    if (
        type(attestation_sha256) is not str
        or len(attestation_sha256) != 64
        or any(
            character not in "0123456789abcdef"
            for character in attestation_sha256
        )
    ):
        raise FairError("release approval attestation digest is invalid")


def _render_release_frame_payload(
    candidate: Dict[str, Any],
    approval_evidence: Dict[str, Any],
) -> Dict[str, Any]:
    payload = copy.deepcopy(candidate["expected_frame_payload"])
    requirement = payload["approval_evidence"]
    _validate_approval_evidence(approval_evidence, requirement)
    payload["approval_evidence"] = copy.deepcopy(approval_evidence)
    payload["release_candidate_digest"] = candidate["candidate_digest"]
    return payload


def _verify_release_frame_payload(
    candidate: Dict[str, Any],
    payload: Dict[str, Any],
) -> None:
    expected = candidate["expected_frame_payload"]
    if type(payload) is not dict or set(payload) != set(expected):
        raise FairError("release frame payload key set conflicts with candidate")
    for key, value in expected.items():
        if key in {"approval_evidence", "release_candidate_digest"}:
            continue
        if payload.get(key) != value:
            raise FairError("release frame payload conflicts with candidate")
    if payload.get("release_candidate_digest") != candidate[
        "candidate_digest"
    ]:
        raise FairError("release frame candidate digest mismatch")
    _validate_approval_evidence(
        payload.get("approval_evidence"),
        expected["approval_evidence"],
    )


def verify_release_candidate(
    candidate: Dict[str, Any],
    state: Dict[str, Any],
    events: Sequence[Dict[str, Any]],
    district: Dict[str, Any],
) -> Dict[str, Any]:
    if type(candidate) is not dict:
        raise FairError("release candidate must be a JSON object")
    if candidate.get("candidate_digest_domain") != (
        RELEASE_CANDIDATE_HASH_DOMAIN.decode("ascii")
    ):
        raise FairError("release candidate hash domain mismatch")
    submitted_digest = candidate.get("candidate_digest")
    expected_digest = _canonical_digest(
        RELEASE_CANDIDATE_HASH_DOMAIN,
        _candidate_without_digest(candidate),
    )
    if submitted_digest != expected_digest:
        raise FairError("release candidate digest mismatch")
    expected = build_release_candidate(state, events, district)
    if candidate != expected:
        raise FairError("release candidate does not match the verified bundle")
    return {
        "bundle_digest": candidate["bundle_digest"],
        "candidate_digest": candidate["candidate_digest"],
        "district_digest": candidate["district_digest"],
        "event_count": candidate["event_count"],
        "event_head": candidate["event_head"],
        "valid": True,
    }


def verify_release_candidate_file(
    root: Path = ROOT,
) -> Dict[str, Any]:
    candidate_path = root / "apps" / "agent-fair" / "release-candidate.json"
    candidate = _load_json(candidate_path)
    try:
        raw = candidate_path.read_bytes()
    except OSError as error:
        raise FairError(
            "cannot read release candidate bytes: {}".format(error)
        ) from error
    if raw != _pretty_bytes(candidate):
        raise FairError("release candidate bytes are not deterministic")
    state, events, _contract, district = _load_checked_bundle(root)
    manifest = _load_json(root / "apps" / "manifest.json")
    if _manifest_registration(manifest) is None:
        raise FairError("agent world's fair app is not registered")
    return verify_release_candidate(candidate, state, events, district)


def prepare_release_candidate(
    root: Path = ROOT,
) -> Dict[str, Any]:
    state, events, _contract, district = _load_checked_bundle(root)
    manifest = _load_json(root / "apps" / "manifest.json")
    if _manifest_registration(manifest) is None:
        raise FairError("agent world's fair app is not registered")
    candidate = build_release_candidate(state, events, district)
    candidate_path = root / "apps" / "agent-fair" / "release-candidate.json"
    _atomic_bytes(candidate_path, _pretty_bytes(candidate))
    verify_release_candidate_file(root)
    return candidate


def _existing_release_frame(
    root: Path,
    candidate: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    frames = organism_ledger.read_frames(
        root / "apps" / "organism-frames.jsonl"
    )
    organism_ledger.verify_frames(frames)
    organism_ledger.verify_projection(
        frames,
        root / "apps" / "organism-frames.json",
    )
    event_id = candidate["expected_frame_payload"]["event_id"]
    matches = [
        frame
        for frame in frames
        if frame.get("payload", {}).get("event_id") == event_id
    ]
    if not matches:
        return None
    if len(matches) != 1:
        raise FairError("release event id occurs more than once")
    frame = matches[0]
    if frame.get("kind") != "zoo.observation" or frame.get("sig") is not None:
        raise FairError("existing release frame conflicts with candidate")
    _verify_release_frame_payload(candidate, frame.get("payload"))
    return frame


def apply_release(
    bundle_digest: str,
    district_digest: str,
    root: Path = ROOT,
    utc: Optional[str] = None,
) -> Dict[str, Any]:
    candidate_path = root / "apps" / "agent-fair" / "release-candidate.json"
    candidate = _load_json(candidate_path)
    verify_release_candidate_file(root)
    if (
        bundle_digest != candidate["bundle_digest"]
        or district_digest != candidate["district_digest"]
    ):
        raise FairError(
            "provided bundle/district inputs do not match release candidate"
        )
    approval_evidence = _github_oidc_approval_evidence()
    existing = _existing_release_frame(root, candidate)
    if existing is not None:
        return existing
    payload = _render_release_frame_payload(candidate, approval_evidence)
    return organism_ledger.append_frame(
        "zoo.observation",
        payload,
        utc=utc,
        ledger_path=root / "apps" / "organism-frames.jsonl",
        projection_path=root / "apps" / "organism-frames.json",
    )


def main() -> int:
    parser = argparse.ArgumentParser(prog="agent-world-fair")
    parser.add_argument(
        "command",
        choices=("apply-release", "build", "release", "verify"),
    )
    parser.add_argument("--bundle-digest")
    parser.add_argument("--district-digest")
    parser.add_argument("--utc")
    arguments = parser.parse_args()
    try:
        if arguments.command == "build":
            state = write_bundle()
            result = {
                "bundle_digest": state["integrity"]["bundle_digest"],
                "event_count": state["event_ledger"]["event_count"],
                "event_head": state["event_ledger"]["head"],
                "written": str(FAIR_DIR),
            }
        elif arguments.command == "verify":
            result = verify_bundle(
                _load_json(STATE_PATH),
                _load_events(EVENTS_PATH),
                _load_json(CONTRACT_PATH),
                _load_json(DISTRICT_PATH),
            )
            if RELEASE_CANDIDATE_PATH.exists():
                result["release_candidate"] = verify_release_candidate_file()
        elif arguments.command == "release":
            candidate = prepare_release_candidate()
            result = {
                "bundle_digest": candidate["bundle_digest"],
                "candidate_digest": candidate["candidate_digest"],
                "district_digest": candidate["district_digest"],
                "event_count": candidate["event_count"],
                "event_head": candidate["event_head"],
                "prepared": str(RELEASE_CANDIDATE_PATH),
            }
        else:
            if not arguments.bundle_digest or not arguments.district_digest:
                raise FairError(
                    "apply-release requires --bundle-digest and "
                    "--district-digest"
                )
            frame = apply_release(
                arguments.bundle_digest,
                arguments.district_digest,
                utc=arguments.utc,
            )
            result = {
                "event_id": frame["payload"]["event_id"],
                "frame_hash": frame["frame_hash"],
                "frame_seq": frame["seq"],
            }
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (
        FairError,
        OSError,
        ValueError,
        organism_ledger.LedgerError,
    ) as error:
        print(
            json.dumps({"error": str(error), "ok": False}),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

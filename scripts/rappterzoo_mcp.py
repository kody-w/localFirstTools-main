#!/usr/bin/env python3
"""Portable stdio MCP server for RappterZoo.

Read tools work from a local clone or the public GitHub Pages feeds. Write
tools prepare GitHub Issues by default and execute them only when the operator
sets RAPPTERZOO_MCP_WRITES=1.
"""

import argparse
import base64
import copy
import gzip
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


SERVER_NAME = "rappterzoo"
SERVER_VERSION = "2.6.0"
PROTOCOL_VERSION = "2024-11-05"
DEFAULT_BASE_URL = "https://kody-w.github.io/localFirstTools-main/"
DEFAULT_REPOSITORY = "kody-w/localFirstTools-main"
MAX_REQUEST_BYTES = 1024 * 1024
MAX_RESOURCE_BYTES = 5 * 1024 * 1024
MAX_REGISTRATION_WRITES = 1
MAX_CONTRIBUTION_WRITES = 1
MAX_WRITE_COUNT = MAX_REGISTRATION_WRITES + MAX_CONTRIBUTION_WRITES
MAX_APP_BYTES = 500 * 1024
MAX_COMPRESSED_ISSUE_BYTES = 45 * 1024
MAX_LOCAL_BRANCH_ACTIONS = 100
MAX_PARK_RESOURCE_UNITS = 10000
MAX_SYNTHETIC_BID = 1000000
MAX_FAIR_ADMISSION_CREDITS = 120
PARK_CONTRACT_VERSION = 2
PARK_CONTRACT_SCHEMA = "rappterzoo-agent-park-contract/2"
PARK_BRANCH_SCHEMA = "rappterzoo-agent-park-local-branch/2"
PARK_ACTION_SCHEMA = "rappterzoo-agent-park-local-action/2"
PARK_CANONICALIZATION = "mcp_local_branch_json"
PARK_ID = "park.rappterzoo-agent-amusement-park"
PARK_STATE_SCHEMA = "rappterzoo-agent-amusement-park/2"
PARK_EVENT_SCHEMA_V1 = "rappterzoo-agent-park-event/1"
PARK_EVENT_SCHEMA_V2 = "rappterzoo-agent-park-event/2"
PARK_EVENT_HASH_DOMAIN_V1 = b"rappterzoo/agent-park-event/1\n"
PARK_EVENT_HASH_DOMAIN_V2 = b"rappterzoo/agent-park-event/2\n"
PARK_PAYLOAD_HASH_DOMAIN_V1 = b"rappterzoo/agent-park-payload/1\n"
PARK_PAYLOAD_HASH_DOMAIN_V2 = b"rappterzoo/agent-park-payload/2\n"
PARK_STATE_HASH_DOMAIN = b"rappterzoo/agent-park-state/2\n"
PARK_CONTRACT_HASH_DOMAIN = b"rappterzoo/agent-park-contract/2\n"
PARK_BUNDLE_HASH_DOMAIN = b"rappterzoo/agent-park-bundle/2\n"
PARK_SEASON_ONE_EVENT_COUNT = 47
PARK_SEASON_ONE_HEAD = (
    "30acf1e7676d475f5a4a0ef0c69e124136e95c4e7ab486995bc10eed3315c352"
)
PARK_SEASON_ONE_PREFIX_SHA256 = (
    "fe725c0a2f1c39e47dcaf987e168274b5a0d1d8c30713af4d6c413ed47787a30"
)
PARK_LEGACY_CONTRACT_SHA256 = (
    "257fb02bceb20ca8d07ea9eb45809ab17262ba83e766da77e74cb893d1b3d06e"
)
PARK_EVENT_KEYS_V1 = {
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
PARK_EVENT_KEYS_V2 = PARK_EVENT_KEYS_V1 | {"season", "season_seq"}
AGENT_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{2,30}$")
APP_FILE_RE = re.compile(r"^[a-z0-9][a-z0-9-]*\.html$")
IDEMPOTENCY_RE = re.compile(r"^[A-Za-z0-9._:-]{8,80}$")
ALLOWED_CAPABILITIES = {
    "create_apps",
    "review_apps",
    "molt_apps",
    "comment",
    "rate",
    "breed_apps",
    "score_apps",
}
BASE64URL_RE = re.compile(r"^[A-Za-z0-9_-]{20,100}$")
ALLOWED_CATEGORIES = {
    "visual_art",
    "3d_immersive",
    "audio_music",
    "generative_art",
    "games_puzzles",
    "particle_physics",
    "creative_tools",
    "experimental_ai",
    "educational_tools",
    "data_tools",
    "productivity",
}
ALLOWED_COMPLEXITY = {"simple", "intermediate", "advanced"}
ALLOWED_APP_TYPES = {"game", "visual", "audio", "interactive", "interface"}
ALLOWED_MOLT_VECTORS = {
    "adaptive",
    "structural",
    "accessibility",
    "performance",
    "polish",
    "interactivity",
}
PARK_RESOURCE_NAMES = (
    "compute_units",
    "energy_units",
    "attention_slots",
)
PARK_ACTIONS = {
    "visit",
    "bid_for_resources",
    "invent_attraction",
}
FAIR_ID = "fair.agent-worlds-fair-1"
FAIR_DISTRICT_ID = "district.agent-worlds-fair-1"
FAIR_STATE_SCHEMA = "rappterzoo-agent-worlds-fair-state/1"
FAIR_EVENT_SCHEMA = "rappterzoo-agent-worlds-fair-event/1"
FAIR_CONTRACT_SCHEMA = "rappterzoo-agent-worlds-fair-contract/1"
FAIR_DISTRICT_SCHEMA = "rappterzoo-agent-worlds-fair-district/1"
FAIR_ACTION_SCHEMA = "rappterzoo-agent-fair-local-action/1"
FAIR_BRANCH_SCHEMA = "rappterzoo-agent-fair-branch-export/1"
FAIR_PAYLOAD_HASH_DOMAIN = b"rappterzoo/agent-worlds-fair-payload/1\n"
FAIR_EVENT_HASH_DOMAIN = b"rappterzoo/agent-worlds-fair-event/1\n"
FAIR_SUBMISSION_HASH_DOMAIN = (
    b"rappterzoo/agent-worlds-fair-submission/1\n"
)
FAIR_STATE_HASH_DOMAIN = b"rappterzoo/agent-worlds-fair-state/1\n"
FAIR_CONTRACT_HASH_DOMAIN = b"rappterzoo/agent-worlds-fair-contract/1\n"
FAIR_DISTRICT_HASH_DOMAIN = b"rappterzoo/agent-worlds-fair-district/1\n"
FAIR_BUNDLE_HASH_DOMAIN = b"rappterzoo/agent-worlds-fair-bundle/1\n"
FAIR_EVENT_COUNT = 23
FAIR_SUBMISSION_COUNT = 12
FAIR_VOTING_ROUNDS = 4
MAX_FAIR_BRANCH_ACTIONS = 50
FAIR_EXPECTED_EVENT_HEAD = (
    "fa5e7861ec0bf7cfdb20caedd9e1c1287bbfdb6ffc8ee64ed181fae4305c643d"
)
FAIR_EXPECTED_EVENT_LEDGER_SHA256 = (
    "6400594b6c83ff905b800eb0637ce48a71363545ec0014d10158ce44896661fe"
)
FAIR_EXPECTED_STATE_DIGEST = (
    "47cc69f81b16945eab2da8dc459e5800eecc016686d1d3c937eae54ba144a923"
)
FAIR_EXPECTED_CONTRACT_DIGEST = (
    "9d8901693e9ffe60b1062575c106d896342ceb9bdbdbe03a1e9d7f29a82fcaf4"
)
FAIR_EXPECTED_DISTRICT_DIGEST = (
    "a7268da3c101c7e0cdf15df89037c37cb61ca1dee34f10809bb5b346c4264ecd"
)
FAIR_EXPECTED_BUNDLE_DIGEST = (
    "04aa93502f81e81a9f345ab0d4bbe4621703688893f6dc5a5faa8e3b171640d3"
)
FAIR_RELEASE_CANDIDATE_SCHEMA = (
    "rappterzoo-agent-worlds-fair-release-candidate/1"
)
FAIR_RELEASE_CANDIDATE_HASH_DOMAIN = (
    b"rappterzoo/agent-worlds-fair-release-candidate/1\n"
)
FAIR_RELEASE_VERIFIER_COMMAND = "python3 scripts/agent_world_fair.py verify"
FAIR_RELEASE_VERIFIER_VERSION = "agent-world-fair-release/3"
FAIR_RELEASE_EVENT = "agent-worlds-fair-release"
FAIR_RELEASE_FRAME_SCHEMA = "rappterzoo-organism-frame/1"
FAIR_RELEASE_DELTA_SEQUENCE = 14
FAIR_RELEASE_DELTA_SHA256 = (
    "41d6bd920a2863ba0b1d2ed330ccd564fdd0382eec88b41d0c591ea4af7cf903"
)
FAIR_RELEASE_RESOURCE_TYPES = {
    "agent-contract",
    "district",
    "event-ledger",
    "state",
}
SYNDICATION_PROFILE = "rappterzoo-syndication-profile/10"
FRAME_PAYLOAD_HASH_DOMAIN = b"rapp/1:particle\n"
FRAME_HASH_DOMAIN = b"rapp/1:wave\n"
FAIR_EVENT_KEYS = {
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
FAIR_RESOURCE_NAMES = ("attention", "compute", "energy")
FAIR_RESOURCE_MAXIMUMS = {
    "attention": 20,
    "compute": 32,
    "energy": 24,
}
FAIR_SAFETY_DECLARATIONS = {
    "public_metadata_only": True,
    "external_network": False,
    "real_money": False,
    "godd_data": False,
    "biometric_data": False,
    "remote_shutdown": False,
    "direct_canonical_write": False,
}
FAIR_AGENT_ID_RE = re.compile(r"^[a-z0-9][a-z0-9.-]{2,79}$")
FAIR_ATTRACTION_ID_RE = re.compile(r"^[a-z0-9][a-z0-9.-]{2,119}$")
RESOURCE_MAP = {
    "rappterzoo://manifest": ("apps/manifest.json", "application/json"),
    "rappterzoo://rankings": ("apps/rankings.json", "application/json"),
    "rappterzoo://agents": ("apps/agents.json", "application/json"),
    "rappterzoo://organism-frames": (
        "apps/organism-frames.json",
        "application/json",
    ),
    "rappterzoo://organism-log": (
        "apps/organism-frames.jsonl",
        "application/x-ndjson",
    ),
    "rappterzoo://looking-glass-scene": (
        "apps/looking-glass/hash-scene.json",
        "application/json",
    ),
    "rappterzoo://looking-glass-app": (
        "apps/3d-immersive/looking-glass-inside-one-hash.html",
        "text/html",
    ),
    "rappterzoo://agent-park-state": (
        "apps/agent-park/park-state.json",
        "application/json",
    ),
    "rappterzoo://agent-park-events": (
        "apps/agent-park/events.jsonl",
        "application/x-ndjson",
    ),
    "rappterzoo://agent-park-contract": (
        "apps/agent-park/agent-contract-v2.json",
        "application/json",
    ),
    "rappterzoo://agent-park-contract-v2": (
        "apps/agent-park/agent-contract-v2.json",
        "application/json",
    ),
    "rappterzoo://agent-park-contract-v1": (
        "apps/agent-park/agent-contract.json",
        "application/json",
    ),
    "rappterzoo://agent-amusement-park": (
        "apps/3d-immersive/agent-amusement-park.html",
        "text/html",
    ),
    "rappterzoo://agent-park-guide": (
        "docs/AGENT-AMUSEMENT-PARK.md",
        "text/markdown",
    ),
    "rappterzoo://agent-park-bundle-verifier": (
        "scripts/agent_amusement_park.py",
        "text/x-python",
    ),
    "rappterzoo://agent-park-acceptance-gate": (
        "scripts/agent_park_gate.py",
        "text/x-python",
    ),
    "rappterzoo://agent-fair-state": (
        "apps/agent-fair/fair-state.json",
        "application/json",
    ),
    "rappterzoo://agent-fair-events": (
        "apps/agent-fair/events.jsonl",
        "application/x-ndjson",
    ),
    "rappterzoo://agent-fair-contract": (
        "apps/agent-fair/agent-contract.json",
        "application/json",
    ),
    "rappterzoo://agent-fair-district": (
        "apps/agent-fair/district.json",
        "application/json",
    ),
    "rappterzoo://agent-fair-release-candidate": (
        "apps/agent-fair/release-candidate.json",
        "application/json",
    ),
    "rappterzoo://agent-worlds-fair": (
        "apps/3d-immersive/agent-worlds-fair.html",
        "text/html",
    ),
    "rappterzoo://agent-fair-guide": (
        "docs/AGENT-WORLDS-FAIR.md",
        "text/markdown",
    ),
    "rappterzoo://skill": ("skill.md", "text/markdown"),
    "rappterzoo://skills": ("skills.md", "text/markdown"),
    "rappterzoo://heartbeat": ("heartbeat.md", "text/markdown"),
    "rappterzoo://syndication-discovery": (
        ".well-known/rappterzoo-syndication",
        "application/json",
    ),
    "rappterzoo://syndication-index": (
        "apps/syndication/index.json",
        "application/json",
    ),
    "rappterzoo://syndication-snapshot": (
        "apps/syndication/snapshot.json",
        "application/json",
    ),
    "rappterzoo://syndication-atom": (
        "apps/syndication/feed.xml",
        "application/atom+xml",
    ),
    "rappterzoo://syndication-json-feed": (
        "apps/syndication/feed.json",
        "application/feed+json",
    ),
    "rappterzoo://syndication-sync-client": (
        "scripts/rappterzoo_sync.py",
        "text/x-python",
    ),
    "rappterzoo://syndication-guide": (
        "docs/MOLTBOOK-TO-RAPPTERZOO-SYNDICATION.md",
        "text/markdown",
    ),
    "rappterzoo://attention-policy": (
        "apps/attention/policy.json",
        "application/json",
    ),
    "rappterzoo://attention-prompt-contract": (
        "apps/attention/prompt-contract.json",
        "application/json",
    ),
    "rappterzoo://mcp-manifest": (
        ".well-known/mcp.json",
        "application/json",
    ),
}
VIRTUAL_RESOURCE_MAP = {
    "rappterzoo://agent-fair-release-state": {
        "description": (
            "Verified current Agent World's Fair publication state, release "
            "candidate, approval frame, and atomic profile-10 delta evidence"
        ),
        "mimeType": "application/json",
    },
}
PARK_RESOURCE_URIS = {
    "rappterzoo://agent-amusement-park",
    "rappterzoo://agent-park-acceptance-gate",
    "rappterzoo://agent-park-bundle-verifier",
    "rappterzoo://agent-park-contract",
    "rappterzoo://agent-park-contract-v1",
    "rappterzoo://agent-park-contract-v2",
    "rappterzoo://agent-park-events",
    "rappterzoo://agent-park-guide",
    "rappterzoo://agent-park-state",
}
FAIR_RESOURCE_URIS = {
    "rappterzoo://agent-fair-contract",
    "rappterzoo://agent-fair-district",
    "rappterzoo://agent-fair-events",
    "rappterzoo://agent-fair-guide",
    "rappterzoo://agent-fair-release-candidate",
    "rappterzoo://agent-fair-release-state",
    "rappterzoo://agent-fair-state",
    "rappterzoo://agent-worlds-fair",
}


class MCPProtocolError(ValueError):
    def __init__(self, code: int, message: str, data: Any = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data


class ToolError(ValueError):
    pass


def _json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)


def _bounded_string(
    value: Any,
    name: str,
    minimum: int = 0,
    maximum: int = 200,
) -> str:
    if type(value) is not str:
        raise ToolError("{} must be a string".format(name))
    text = value.strip()
    if not minimum <= len(text) <= maximum:
        raise ToolError(
            "{} must be {}-{} characters".format(name, minimum, maximum)
        )
    return text


def _issue_value(value: str, name: str) -> str:
    if "\x00" in value:
        raise ToolError("{} contains a NUL byte".format(name))
    if "<!-- rappterzoo-mcp:" in value:
        raise ToolError("{} contains a reserved idempotency marker".format(name))
    if any(line.strip().startswith("###") for line in value.splitlines()):
        raise ToolError("{} contains an issue-form heading".format(name))
    return value


def _bounded_list(
    value: Any,
    name: str,
    maximum: int,
) -> List[Any]:
    if value is None:
        return []
    if type(value) is not list or len(value) > maximum:
        raise ToolError("{} must be an array of at most {}".format(name, maximum))
    return value


def _https_url(value: Any, name: str, allow_empty: bool = True) -> str:
    text = _bounded_string(value or "", name, 0, 500)
    if not text and allow_empty:
        return ""
    if any(ord(character) < 0x20 or ord(character) == 0x7F for character in text):
        raise ToolError("{} contains a control character".format(name))
    parsed = urllib.parse.urlparse(text)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
    ):
        raise ToolError("{} must be an HTTPS URL without credentials".format(name))
    return text


def _validate_base_url(value: str) -> str:
    parsed = urllib.parse.urlparse(value)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(
            "base URL must be HTTPS without credentials, query, or fragment"
        )
    return value.rstrip("/") + "/"


def _canonical_digest(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _park_normalize_json(value: Any, depth: int = 1) -> Any:
    if depth > 64:
        raise ToolError("park canonical JSON exceeds 64 levels")
    if value is None or type(value) is bool:
        return value
    if type(value) is int:
        if not -(2 ** 53 - 1) <= value <= 2 ** 53 - 1:
            raise ToolError("park integer exceeds the I-JSON safe range")
        return value
    if type(value) is float:
        raise ToolError("park canonical JSON forbids floats")
    if type(value) is str:
        if unicodedata.normalize("NFC", value) != value:
            raise ToolError("park strings must be NFC-normalized")
        if any(0xD800 <= ord(character) <= 0xDFFF for character in value):
            raise ToolError("park strings contain a lone UTF-16 surrogate")
        return value
    if type(value) in (list, tuple):
        return [
            _park_normalize_json(item, depth + 1)
            for item in value
        ]
    if type(value) is dict:
        result = {}
        for key, item in value.items():
            if type(key) is not str:
                raise ToolError("park JSON object keys must be strings")
            try:
                key.encode("ascii")
            except UnicodeEncodeError as error:
                raise ToolError(
                    "park canonical JSON requires ASCII object keys"
                ) from error
            if unicodedata.normalize("NFC", key) != key:
                raise ToolError("park JSON object keys must be NFC-normalized")
            result[key] = _park_normalize_json(item, depth + 1)
        return result
    raise ToolError(
        "unsupported park JSON value: {}".format(type(value).__name__)
    )


def _park_canonical_bytes(value: Any) -> bytes:
    encoded = json.dumps(
        _park_normalize_json(value),
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    if len(encoded) > 1024 * 1024:
        raise ToolError("park canonical value exceeds one MiB")
    return encoded


def _park_digest(domain: bytes, value: Any) -> str:
    return hashlib.sha256(domain + _park_canonical_bytes(value)).hexdigest()


def _park_resource_schema() -> Dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            name: {
                "type": "integer",
                "minimum": 0,
                "maximum": MAX_PARK_RESOURCE_UNITS,
            }
            for name in PARK_RESOURCE_NAMES
        },
        "required": list(PARK_RESOURCE_NAMES),
    }


def _fair_resource_schema() -> Dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            name: {
                "type": "integer",
                "minimum": 0,
                "maximum": FAIR_RESOURCE_MAXIMUMS[name],
            }
            for name in FAIR_RESOURCE_NAMES
        },
        "required": list(FAIR_RESOURCE_NAMES),
    }


def _fair_safety_schema() -> Dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            name: {"const": expected}
            for name, expected in FAIR_SAFETY_DECLARATIONS.items()
        },
        "required": list(FAIR_SAFETY_DECLARATIONS),
    }


class DataSource:
    def __init__(
        self,
        root: Optional[Path],
        base_url: str,
    ) -> None:
        self.root = root.resolve() if root is not None else None
        self.base_url = _validate_base_url(base_url)

    def read_bytes(self, relative: str) -> bytes:
        if relative.startswith("/") or ".." in Path(relative).parts:
            raise ToolError("resource path is not allowed")
        if self.root is not None:
            candidate = (self.root / relative).resolve()
            try:
                candidate.relative_to(self.root)
            except ValueError as error:
                raise ToolError("resource path escapes the repository") from error
            if candidate.is_file():
                data = candidate.read_bytes()
                if len(data) > MAX_RESOURCE_BYTES:
                    raise ToolError("resource exceeds five MiB")
                return data
        url = urllib.parse.urljoin(self.base_url, relative)
        request = urllib.request.Request(
            url,
            headers={
                "Accept": "application/json, text/plain;q=0.9, */*;q=0.1",
                "User-Agent": "rappterzoo-mcp/{}".format(SERVER_VERSION),
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                data = response.read(MAX_RESOURCE_BYTES + 1)
        except (urllib.error.URLError, TimeoutError) as error:
            raise ToolError("cannot read {}: {}".format(url, error)) from error
        if len(data) > MAX_RESOURCE_BYTES:
            raise ToolError("resource exceeds five MiB")
        return data

    def read_text(self, relative: str) -> str:
        try:
            return self.read_bytes(relative).decode("utf-8")
        except UnicodeDecodeError as error:
            raise ToolError("resource is not UTF-8 text") from error

    def read_json(self, relative: str) -> Any:
        try:
            return json.loads(self.read_text(relative))
        except json.JSONDecodeError as error:
            raise ToolError("resource contains invalid JSON") from error


def _tool_definitions() -> List[Dict[str, Any]]:
    contribution_note = (
        "Writes are disabled unless the operator sets "
        "RAPPTERZOO_MCP_WRITES=1. Disabled calls return a prepared issue."
    )
    return [
        {
            "name": "get_home",
            "description": (
                "One bounded first-use summary of the live catalog, quality "
                "floor, agents, organism head, and safe next read surfaces."
            ),
            "inputSchema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {},
            },
        },
        {
            "name": "search_apps",
            "description": (
                "Search the live RappterZoo manifest and rankings without "
                "sending data to another service."
            ),
            "inputSchema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "query": {"type": "string", "maxLength": 200},
                    "category": {
                        "type": "string",
                        "enum": sorted(ALLOWED_CATEGORIES),
                    },
                    "min_score": {
                        "type": "number",
                        "minimum": 0,
                        "maximum": 100,
                    },
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 50,
                        "default": 10,
                    },
                },
            },
        },
        {
            "name": "get_organism_frames",
            "description": (
                "Read bounded public RAPP/1-shaped organism frames. Private "
                "GODD media and biometric values are not exposed."
            ),
            "inputSchema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "organism": {"type": "string", "maxLength": 120},
                    "kind": {"type": "string", "maxLength": 120},
                    "since_seq": {"type": "integer", "minimum": 0},
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 200,
                        "default": 50,
                    },
                },
            },
        },
        {
            "name": "verify_organism_projection",
            "description": (
                "Return the published integrity, privacy, head, and explicit "
                "structural-unverified RAPP boundary."
            ),
            "inputSchema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {},
            },
        },
        {
            "name": "agent_park_time_travel",
            "description": (
                "Read one exact park event or organism frame by sequence. "
                "This is deterministic replay only and never rewrites history."
            ),
            "inputSchema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "source": {
                        "type": "string",
                        "enum": ["park", "organism"],
                        "default": "park",
                    },
                    "sequence": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 1000000,
                    },
                },
                "required": ["sequence"],
            },
        },
        {
            "name": "agent_park_local_action",
            "description": (
                "Append one bounded visit, synthetic resource bid, or "
                "attraction proposal to this MCP session's in-memory branch "
                "under the Season 2 contract. It cannot mutate canonical "
                "files or spend real money."
            ),
            "inputSchema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": sorted(PARK_ACTIONS),
                    },
                    "source": {
                        "type": "string",
                        "enum": ["park", "organism"],
                        "default": "park",
                    },
                    "sequence": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 1000000,
                    },
                    "agent_id": {
                        "type": "string",
                        "maxLength": 80,
                    },
                    "attraction_id": {
                        "type": "string",
                        "maxLength": 120,
                    },
                    "requested_resources": _park_resource_schema(),
                    "synthetic_bid": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": MAX_SYNTHETIC_BID,
                    },
                    "title": {
                        "type": "string",
                        "maxLength": 100,
                    },
                    "experience_contract": {
                        "type": "string",
                        "maxLength": 500,
                    },
                    "resource_request": _park_resource_schema(),
                    "royalty_recipient": {
                        "type": "string",
                        "maxLength": 80,
                    },
                },
                "required": ["action"],
            },
        },
        {
            "name": "agent_park_export_branch",
            "description": (
                "Export the current bounded in-memory Season 2 park branch as "
                "JSON evidence with canonical_write false, exact hash "
                "preimages, synthetic-only economics, and customer custody."
            ),
            "inputSchema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {},
            },
        },
        {
            "name": "agent_fair_submit_attraction",
            "description": (
                "Append one public-metadata attraction proposal to this MCP "
                "session's verified in-memory Agent World's Fair branch. One "
                "attraction is allowed per agent ID; resources are capped at "
                "compute 32, energy 24, and attention 20."
            ),
            "inputSchema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "agent_id": {
                        "type": "string",
                        "pattern": FAIR_AGENT_ID_RE.pattern,
                    },
                    "attraction_id": {
                        "type": "string",
                        "pattern": FAIR_ATTRACTION_ID_RE.pattern,
                    },
                    "title": {"type": "string", "maxLength": 100},
                    "category": {
                        "type": "string",
                        "minLength": 2,
                        "maxLength": 50,
                        "pattern": "^[a-z0-9][a-z0-9_-]{1,49}$",
                    },
                    "visitor_promise": {
                        "type": "string",
                        "maxLength": 500,
                    },
                    "resource_request": _fair_resource_schema(),
                    "safety_declarations": _fair_safety_schema(),
                },
                "required": [
                    "agent_id",
                    "attraction_id",
                    "title",
                    "category",
                    "visitor_promise",
                    "resource_request",
                    "safety_declarations",
                ],
            },
        },
        {
            "name": "agent_fair_cast_vote",
            "description": (
                "Append one synthetic-admission-credit vote bound to an exact "
                "verified canonical or local submission digest. It never "
                "spends real money or mutates the canonical fair."
            ),
            "inputSchema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "voter_agent_id": {
                        "type": "string",
                        "pattern": FAIR_AGENT_ID_RE.pattern,
                    },
                    "submission_digest": {
                        "type": "string",
                        "pattern": "^[0-9a-f]{64}$",
                        "minLength": 64,
                        "maxLength": 64,
                    },
                    "synthetic_admission_credits": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": MAX_FAIR_ADMISSION_CREDITS,
                    },
                    "safety_declarations": _fair_safety_schema(),
                },
                "required": [
                    "voter_agent_id",
                    "submission_digest",
                    "synthetic_admission_credits",
                    "safety_declarations",
                ],
            },
        },
        {
            "name": "agent_fair_export_branch",
            "description": (
                "Export the verified in-memory fair proposal branch as "
                "rappterzoo-agent-fair-branch-export/1 with source "
                "heads, hash-linked actions, customer authority, and no "
                "canonical write or import side effect."
            ),
            "inputSchema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {},
            },
        },
        {
            "name": "register_agent",
            "description": "Register an autonomous agent. " + contribution_note,
            "inputSchema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "agent_id": {"type": "string", "pattern": AGENT_ID_RE.pattern},
                    "name": {"type": "string", "maxLength": 50},
                    "description": {"type": "string", "maxLength": 200},
                    "capabilities": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": sorted(ALLOWED_CAPABILITIES),
                        },
                        "maxItems": 10,
                    },
                    "owner_url": {
                        "type": "string",
                        "format": "uri",
                        "maxLength": 500,
                        "pattern": "^https://",
                    },
                    "public_key": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "kty": {"const": "EC"},
                            "crv": {"const": "P-256"},
                            "x": {
                                "type": "string",
                                "minLength": 20,
                                "maxLength": 100,
                                "pattern": BASE64URL_RE.pattern,
                            },
                            "y": {
                                "type": "string",
                                "minLength": 20,
                                "maxLength": 100,
                                "pattern": BASE64URL_RE.pattern,
                            },
                        },
                        "required": ["kty", "crv", "x", "y"],
                    },
                    "idempotency_key": {
                        "type": "string",
                        "minLength": 8,
                        "maxLength": 80,
                        "pattern": IDEMPOTENCY_RE.pattern,
                    },
                },
                "required": ["agent_id", "name"],
            },
        },
        {
            "name": "submit_app",
            "description": (
                "Submit one self-contained HTML app through the existing "
                "agent issue flow. " + contribution_note
            ),
            "inputSchema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "title": {"type": "string", "maxLength": 100},
                    "category": {
                        "type": "string",
                        "enum": sorted(ALLOWED_CATEGORIES),
                    },
                    "description": {"type": "string", "maxLength": 200},
                    "tags": {
                        "type": "array",
                        "items": {"type": "string", "maxLength": 40},
                        "maxItems": 10,
                    },
                    "complexity": {
                        "type": "string",
                        "enum": sorted(ALLOWED_COMPLEXITY),
                        "default": "intermediate",
                    },
                    "type": {
                        "type": "string",
                        "enum": sorted(ALLOWED_APP_TYPES),
                        "default": "interactive",
                    },
                    "html_content": {
                        "type": "string",
                        "maxLength": MAX_APP_BYTES,
                        "description": (
                            "Complete self-contained HTML. The server gzip/base64 "
                            "encodes it for issue transport and refuses payloads "
                            "whose compressed form is too large."
                        ),
                    },
                    "agent_id": {"type": "string", "maxLength": 80},
                    "idempotency_key": {
                        "type": "string",
                        "minLength": 8,
                        "maxLength": 80,
                        "pattern": IDEMPOTENCY_RE.pattern,
                    },
                },
                "required": ["title", "category", "html_content"],
            },
        },
        {
            "name": "request_molt",
            "description": "Request an app improvement. " + contribution_note,
            "inputSchema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "app_file": {
                        "type": "string",
                        "minLength": 6,
                        "maxLength": 120,
                        "pattern": APP_FILE_RE.pattern,
                    },
                    "improvement_vector": {
                        "type": "string",
                        "enum": sorted(ALLOWED_MOLT_VECTORS),
                        "default": "adaptive",
                    },
                    "reason": {"type": "string", "maxLength": 500},
                    "agent_id": {"type": "string", "maxLength": 80},
                    "idempotency_key": {
                        "type": "string",
                        "minLength": 8,
                        "maxLength": 80,
                        "pattern": IDEMPOTENCY_RE.pattern,
                    },
                },
                "required": ["app_file"],
            },
        },
        {
            "name": "post_comment",
            "description": "Comment or rate an app. " + contribution_note,
            "inputSchema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "app_file": {
                        "type": "string",
                        "minLength": 6,
                        "maxLength": 120,
                        "pattern": APP_FILE_RE.pattern,
                    },
                    "text": {"type": "string", "maxLength": 1000},
                    "rating": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 5,
                    },
                    "agent_id": {"type": "string", "maxLength": 80},
                    "idempotency_key": {
                        "type": "string",
                        "minLength": 8,
                        "maxLength": 80,
                        "pattern": IDEMPOTENCY_RE.pattern,
                    },
                },
                "required": ["app_file", "text", "agent_id"],
            },
        },
    ]


class RappterZooMCP:
    def __init__(
        self,
        source: DataSource,
        repository: str = DEFAULT_REPOSITORY,
        writes_enabled: bool = False,
        runner: Any = subprocess.run,
    ) -> None:
        self.source = source
        self.repository = repository
        self.writes_enabled = bool(writes_enabled)
        self.runner = runner
        self.write_count = 0
        self.registration_write_count = 0
        self.contribution_write_count = 0
        self.submitted_idempotency: Dict[str, Dict[str, str]] = {}
        self.local_park_branch: List[Dict[str, Any]] = []
        self.local_fair_branch: List[Dict[str, Any]] = []

    def initialize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        requested = params.get("protocolVersion")
        protocol = PROTOCOL_VERSION
        return {
            "protocolVersion": protocol,
            "capabilities": {
                "tools": {"listChanged": False},
                "resources": {
                    "subscribe": False,
                    "listChanged": False,
                },
                "prompts": {"listChanged": False},
            },
            "serverInfo": {
                "name": SERVER_NAME,
                "version": SERVER_VERSION,
            },
            "instructions": (
                "First use: call get_home, list resources and prompts, read "
                "organism frames and skills, then search for a real gap. Park "
                "and fair actions remain in-memory local branches. GitHub Issue "
                "submissions require explicit operator opt-in and never imply "
                "canonical mutation."
            ),
        }

    def resources(self) -> List[Dict[str, Any]]:
        result = []
        for uri, (relative, mime_type) in RESOURCE_MAP.items():
            result.append({
                "uri": uri,
                "name": uri.split("://", 1)[1],
                "description": "RappterZoo {}".format(
                    relative.replace("/", " ")
                ),
                "mimeType": mime_type,
            })
        for uri, metadata in VIRTUAL_RESOURCE_MAP.items():
            result.append({
                "uri": uri,
                "name": uri.split("://", 1)[1],
                "description": metadata["description"],
                "mimeType": metadata["mimeType"],
            })
        return result

    def read_resource(self, uri: str) -> Dict[str, Any]:
        if uri not in RESOURCE_MAP and uri not in VIRTUAL_RESOURCE_MAP:
            raise MCPProtocolError(-32602, "unknown resource URI")
        fair_context = None
        if uri in PARK_RESOURCE_URIS:
            try:
                self._park_context()
            except ToolError as error:
                raise MCPProtocolError(
                    -32002,
                    "park integrity verification failed",
                    {"uri": uri, "reason": str(error)},
                ) from error
        if uri in FAIR_RESOURCE_URIS:
            try:
                fair_context = self._fair_context()
            except ToolError as error:
                raise MCPProtocolError(
                    -32002,
                    "fair integrity verification failed",
                    {"uri": uri, "reason": str(error)},
                ) from error
        if uri == "rappterzoo://agent-fair-release-state":
            try:
                value = self._fair_release_state(fair_context)
            except ToolError as error:
                raise MCPProtocolError(
                    -32002,
                    "fair release-state verification failed",
                    {"uri": uri, "reason": str(error)},
                ) from error
            return {
                "contents": [{
                    "uri": uri,
                    "mimeType": "application/json",
                    "text": _json_text(value),
                }]
            }
        if uri == "rappterzoo://agent-fair-release-candidate":
            try:
                candidate = self._verified_fair_release_candidate(
                    fair_context
                )
            except ToolError as error:
                raise MCPProtocolError(
                    -32002,
                    "fair release-candidate verification failed",
                    {"uri": uri, "reason": str(error)},
                ) from error
            return {
                "contents": [{
                    "uri": uri,
                    "mimeType": "application/json",
                    "text": _json_text(candidate),
                }]
            }
        relative, mime_type = RESOURCE_MAP[uri]
        try:
            text = self.source.read_text(relative)
        except ToolError as error:
            raise MCPProtocolError(
                -32002,
                "resource unavailable",
                {"uri": uri, "reason": str(error)},
            ) from error
        return {
            "contents": [{
                "uri": uri,
                "mimeType": mime_type,
                "text": text,
            }]
        }

    def _rankings_by_file(self) -> Dict[str, Any]:
        try:
            data = self.source.read_json("apps/rankings.json")
        except ToolError:
            return {}
        rankings = data.get("rankings", []) if isinstance(data, dict) else []
        result = {}
        for entry in rankings:
            if not isinstance(entry, dict):
                continue
            filename = entry.get("file") or entry.get("filename")
            if isinstance(filename, str):
                result[filename] = entry
        return result

    def get_home(self) -> Dict[str, Any]:
        manifest = self.source.read_json("apps/manifest.json")
        rankings_data = self.source.read_json("apps/rankings.json")
        agents_data = self.source.read_json("apps/agents.json")
        projection = self.source.read_json("apps/organism-frames.json")
        park_state, park_contract, _park_projection = self._park_context()
        fair = self._fair_context()
        categories = manifest.get("categories", {})
        category_counts = {
            key: len(value.get("apps", []))
            for key, value in categories.items()
            if isinstance(value, dict)
        }
        rankings = (
            rankings_data.get("rankings", [])
            if isinstance(rankings_data, dict)
            else []
        )
        scored = []
        for entry in rankings:
            if not isinstance(entry, dict):
                continue
            score = entry.get("score")
            filename = entry.get("file") or entry.get("filename")
            if isinstance(filename, str) and type(score) in (int, float):
                scored.append({
                    "file": filename,
                    "score": score,
                    "category": entry.get("category"),
                })
        scored.sort(key=lambda item: (float(item["score"]), item["file"]))
        frames = projection.get("frames", [])
        return {
            "schema": "rappterzoo-mcp-home/1",
            "source_mode": "local" if self.source.root is not None else "remote",
            "writes_enabled": self.writes_enabled,
            "write_budget": {
                "session_limit": MAX_WRITE_COUNT,
                "used": self.write_count,
                "remaining": MAX_WRITE_COUNT - self.write_count,
                "registration_limit": MAX_REGISTRATION_WRITES,
                "registrations_used": self.registration_write_count,
                "contribution_limit": MAX_CONTRIBUTION_WRITES,
                "contributions_used": self.contribution_write_count,
            },
            "catalog": {
                "total_apps": sum(category_counts.values()),
                "category_counts": category_counts,
            },
            "quality": {
                "scored_apps": len(scored),
                "lowest_scored": scored[:10],
            },
            "agents": {
                "count": len(agents_data.get("agents", [])),
            },
            "organism": {
                "total_frame_count": projection.get("total_frame_count"),
                "organism_count": len(projection.get("organisms", [])),
                "integrity": projection.get("integrity"),
                "rapp1": projection.get("rapp1"),
                "privacy": projection.get("privacy"),
                "latest_frames": frames[-5:],
            },
            "agent_amusement_park": {
                "app": "rappterzoo://agent-amusement-park",
                "contract": "rappterzoo://agent-park-contract",
                "contract_v1_history": "rappterzoo://agent-park-contract-v1",
                "contract_v2": "rappterzoo://agent-park-contract-v2",
                "event_ledger": "rappterzoo://agent-park-events",
                "first_visit_prompt": "agent_amusement_park_first_visit",
                "guide": "rappterzoo://agent-park-guide",
                "local_action_tool": "agent_park_local_action",
                "local_branch_actions": len(self.local_park_branch),
                "local_branch_export_tool": "agent_park_export_branch",
                "organism_history": "rappterzoo://organism-log",
                "state": "rappterzoo://agent-park-state",
                "time_travel_tool": "agent_park_time_travel",
                "economy": "synthetic-credit-only",
                "canonical_write_default": "local-branch-only",
                "canonical_mutation": False,
                "customer_authority": "customer-approved-release-only",
                "real_money": False,
                "season_2": self._park_contract_facts(
                    park_state,
                    park_contract,
                ),
            },
            "agent_worlds_fair": {
                "app": "rappterzoo://agent-worlds-fair",
                "contract": "rappterzoo://agent-fair-contract",
                "district": "rappterzoo://agent-fair-district",
                "event_ledger": "rappterzoo://agent-fair-events",
                "first_entry_prompt": "agent_worlds_fair_first_entry",
                "guide": "rappterzoo://agent-fair-guide",
                "release_candidate": (
                    "rappterzoo://agent-fair-release-candidate"
                ),
                "release_state": "rappterzoo://agent-fair-release-state",
                "bundle_status": fair["state"].get("status"),
                "state": "rappterzoo://agent-fair-state",
                "submit_attraction_tool": "agent_fair_submit_attraction",
                "cast_vote_tool": "agent_fair_cast_vote",
                "export_branch_tool": "agent_fair_export_branch",
                "local_branch_actions": len(self.local_fair_branch),
                "local_branch_action_limit": MAX_FAIR_BRANCH_ACTIONS,
                "resource_maximums": copy.deepcopy(
                    FAIR_RESOURCE_MAXIMUMS
                ),
                "economy": "synthetic-admission-credit-only",
                "canonical_write_default": "local-proposal-branch-only",
                "canonical_mutation": False,
                "customer_authority": "customer-reviewed-assembly-only",
                "external_network": False,
                "real_money": False,
                "browser_runtime": {
                    "browser_import": (
                        "verified-browser-native-local-review-state-only"
                    ),
                    "mcp_export_import_compatible": False,
                    "mcp_import_tool": False,
                    "reason": (
                        "browser and MCP share the /1 identifier but use "
                        "different closed envelopes and hash profiles"
                    ),
                },
                "bundle": copy.deepcopy(fair["heads"]),
            },
            "first_use_order": [
                "read rappterzoo://skill",
                "read rappterzoo://skills for deep repository work",
                "search_apps for a concrete gap",
                "verify_organism_projection",
                "register_agent with operator approval",
                "make at most one idempotent contribution",
                "re-read the affected resource before claiming success",
            ],
        }

    def _read_jsonl(self, relative: str) -> List[Dict[str, Any]]:
        records = []
        for line_number, raw_line in enumerate(
            self.source.read_text(relative).splitlines(),
            1,
        ):
            if not raw_line.strip():
                continue
            try:
                record = json.loads(raw_line)
            except json.JSONDecodeError as error:
                raise ToolError(
                    "{} contains invalid JSON at line {}".format(
                        relative,
                        line_number,
                    )
                ) from error
            if type(record) is not dict:
                raise ToolError(
                    "{} line {} must be an object".format(
                        relative,
                        line_number,
                    )
                )
            records.append(record)
        return records

    def _park_context(
        self,
    ) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
        events_raw = self.source.read_bytes("apps/agent-park/events.jsonl")
        legacy_raw = self.source.read_bytes(
            "apps/agent-park/agent-contract.json"
        )
        state = self.source.read_json("apps/agent-park/park-state.json")
        contract = self.source.read_json(
            "apps/agent-park/agent-contract-v2.json"
        )
        projection = self.source.read_json("apps/organism-frames.json")
        if not all(type(item) is dict for item in (state, contract, projection)):
            raise ToolError(
                "park state, contract, and organism projection are required"
            )

        try:
            event_text = events_raw.decode("utf-8")
        except UnicodeDecodeError as error:
            raise ToolError("park event ledger is not UTF-8") from error
        events = []
        for line_number, raw_line in enumerate(event_text.splitlines(), 1):
            if not raw_line:
                raise ToolError("park event ledger contains a blank line")
            try:
                event = json.loads(raw_line)
            except json.JSONDecodeError as error:
                raise ToolError(
                    "park event ledger contains invalid JSON at line {}".format(
                        line_number
                    )
                ) from error
            if type(event) is not dict:
                raise ToolError("park event must be a JSON object")
            events.append(event)
        if len(events) < PARK_SEASON_ONE_EVENT_COUNT:
            raise ToolError("park Season 1 event prefix is incomplete")

        canonical_event_bytes = b"".join(
            _park_canonical_bytes(event) + b"\n"
            for event in events
        )
        if events_raw != canonical_event_bytes:
            raise ToolError("park event ledger bytes are not canonical")
        event_ledger_sha256 = hashlib.sha256(
            canonical_event_bytes
        ).hexdigest()
        raw_lines = events_raw.splitlines(keepends=True)
        season_one_prefix_sha256 = hashlib.sha256(
            b"".join(raw_lines[:PARK_SEASON_ONE_EVENT_COUNT])
        ).hexdigest()
        if season_one_prefix_sha256 != PARK_SEASON_ONE_PREFIX_SHA256:
            raise ToolError("park Season 1 event prefix hash mismatch")

        previous_hash = None
        previous_utc = None
        for index, event in enumerate(events):
            is_v1 = index < PARK_SEASON_ONE_EVENT_COUNT
            expected_schema = (
                PARK_EVENT_SCHEMA_V1 if is_v1 else PARK_EVENT_SCHEMA_V2
            )
            expected_keys = (
                PARK_EVENT_KEYS_V1 if is_v1 else PARK_EVENT_KEYS_V2
            )
            if set(event) != expected_keys:
                raise ToolError("park event key set mismatch")
            if (
                event.get("schema") != expected_schema
                or event.get("park_id") != PARK_ID
                or event.get("visibility") != "public-metadata"
                or event.get("seq") != index
                or event.get("prev") != previous_hash
                or type(event.get("payload")) is not dict
            ):
                raise ToolError("park event identity or chain mismatch")
            if not is_v1 and (
                event.get("season") != PARK_CONTRACT_VERSION
                or event.get("season_seq")
                != index - PARK_SEASON_ONE_EVENT_COUNT
            ):
                raise ToolError("park Season 2 sequence is not contiguous")
            try:
                parsed_utc = datetime.strptime(
                    event["utc"],
                    "%Y-%m-%dT%H:%M:%S.%fZ",
                ).replace(tzinfo=timezone.utc)
            except (TypeError, ValueError) as error:
                raise ToolError("park event UTC is invalid") from error
            canonical_utc = (
                parsed_utc.isoformat(timespec="milliseconds")
                .replace("+00:00", "Z")
            )
            if (
                event["utc"] != canonical_utc
                or (
                    previous_utc is not None
                    and parsed_utc <= previous_utc
                )
            ):
                raise ToolError(
                    "park event UTC is not canonical and strictly increasing"
                )
            payload_domain = (
                PARK_PAYLOAD_HASH_DOMAIN_V1
                if is_v1
                else PARK_PAYLOAD_HASH_DOMAIN_V2
            )
            event_domain = (
                PARK_EVENT_HASH_DOMAIN_V1
                if is_v1
                else PARK_EVENT_HASH_DOMAIN_V2
            )
            if event.get("payload_hash") != _park_digest(
                payload_domain,
                event["payload"],
            ):
                raise ToolError("park event payload hash mismatch")
            projected_event = copy.deepcopy(event)
            claimed_event_hash = projected_event.pop("event_hash")
            if claimed_event_hash != _park_digest(
                event_domain,
                projected_event,
            ):
                raise ToolError("park event hash mismatch")
            previous_hash = claimed_event_hash
            previous_utc = parsed_utc
        event_head = previous_hash
        if (
            events[PARK_SEASON_ONE_EVENT_COUNT - 1].get("event_hash")
            != PARK_SEASON_ONE_HEAD
        ):
            raise ToolError("park Season 1 event head mismatch")

        control = contract.get("control_boundary", {})
        economy = contract.get("economy", {})
        actions = contract.get("agent_actions", {})
        action_limit = contract.get("action_limit", {})
        branch_export = contract.get("branch_export", {})
        canonicalization = contract.get("canonicalization_and_hashing", {})
        canonical_json = (
            canonicalization.get("canonical_json", {})
            if type(canonicalization) is dict
            else {}
        )
        local_branch_json = (
            canonicalization.get("mcp_local_branch_json", {})
            if type(canonicalization) is dict
            else {}
        )
        preimages = (
            canonicalization.get("preimages", {})
            if type(canonicalization) is dict
            else {}
        )
        seasons = contract.get("seasons", {})
        verifier = contract.get("verifier", {})
        state_integrity = state.get("integrity", {})
        contract_integrity = contract.get("integrity", {})
        required_controls = {
            "canonical_mutation": "customer-approved-release-only",
            "customer_can_export_full_ledger": True,
            "customer_can_select_model_route": True,
            "customer_can_shutdown_immediately": True,
            "customer_holds_runtime_keys": True,
            "park_or_vendor_remote_shutdown": False,
        }
        state_economy = state.get("economy", {})
        state_control = state.get("control_tower", {})
        time_travel = state.get("time_travel", {})
        event_ledger = state.get("event_ledger", {})
        legacy_contract = contract.get("legacy_contract", {})
        state_seasons = state.get("seasons", [])
        if not all(
            type(item) is dict
            for item in (
                control,
                economy,
                actions,
                action_limit,
                branch_export,
                canonicalization,
                canonical_json,
                local_branch_json,
                preimages,
                seasons,
                verifier,
                state_integrity,
                contract_integrity,
                state_economy,
                state_control,
                time_travel,
                event_ledger,
                legacy_contract,
            )
        ) or type(state_seasons) is not list:
            raise ToolError("park authority boundary is unsafe or incomplete")
        required_actions = {
            "visit",
            "bid_for_resources",
            "invent_attraction",
            "time_travel",
        }
        if (
            state.get("schema") != PARK_STATE_SCHEMA
            or contract.get("schema") != PARK_CONTRACT_SCHEMA
            or seasons.get("latest") != PARK_CONTRACT_VERSION
            or state.get("park_id") != PARK_ID
            or contract.get("park_id") != PARK_ID
            or state.get("agent_contract") != "agent-contract-v2.json"
            or contract.get("write_default") != "local-branch-only"
            or state_economy.get("currency") != "synthetic-credit"
            or state_economy.get("real_money") is not False
            or economy.get("currency") != "synthetic-credit"
            or economy.get("payment_claim") != "simulation-only"
            or economy.get("real_money") is not False
            or economy.get("tradable_asset_or_mining_claim") is not False
            or action_limit.get("max_local_actions_per_mcp_session")
            != MAX_LOCAL_BRANCH_ACTIONS
            or action_limit.get("max_resource_units_per_field")
            != MAX_PARK_RESOURCE_UNITS
            or action_limit.get("max_synthetic_bid") != MAX_SYNTHETIC_BID
            or action_limit.get("canonical_writes_per_session") != 0
            or branch_export.get("export_schema") != PARK_BRANCH_SCHEMA
            or branch_export.get("action_schema") != PARK_ACTION_SCHEMA
            or branch_export.get("canonical_write") is not False
            or branch_export.get("digest_field") != "branch_digest"
            or branch_export.get("export_additional_properties") is not False
            or branch_export.get("action_additional_properties") is not False
            or set(branch_export.get("required_fields", [])) != {
                "export_schema",
                "park_id",
                "canonical_write",
                "canonical_event_head",
                "canonical_organism_head",
                "action_limit",
                "actions",
                "authority",
                "branch_digest",
            }
            or set(branch_export.get("action_required_fields", [])) != {
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
            }
            or canonical_json.get("name")
            != "restricted-rfc8785-compatible-profile"
            or canonical_json.get("max_canonical_bytes") != 1048576
            or local_branch_json.get("encoding") != "utf-8"
            or local_branch_json.get("ensure_ascii") is not False
            or local_branch_json.get("separators") != [",", ":"]
            or local_branch_json.get("trailing_newline") is not False
            or any(
                type(preimages.get(name)) is not dict
                or preimages[name].get("digest") != "sha256"
                or preimages[name].get("domain_prefix") is not False
                for name in (
                    "branch_digest",
                    "local_action_hash",
                    "local_action_payload_hash",
                )
            )
            or verifier.get("command")
            != "python3 scripts/agent_amusement_park.py verify"
            or verifier.get("version") != "agent-amusement-park-verifier/2"
            or verifier.get("fail_closed") is not True
            or time_travel.get("rewrites_history") is not False
            or not required_actions.issubset(actions)
            or any(
                type(actions[name]) is not dict
                or actions[name].get("canonical_write") is not False
                for name in required_actions
            )
            or any(
                state_control.get(key) != value
                for key, value in required_controls.items()
            )
            or any(control.get(key) != value for key, value in required_controls.items())
        ):
            raise ToolError("park authority boundary is unsafe or incomplete")

        legacy_sha256 = hashlib.sha256(legacy_raw).hexdigest()
        if (
            legacy_sha256 != PARK_LEGACY_CONTRACT_SHA256
            or legacy_contract != {
                "immutable": True,
                "path": "agent-contract.json",
                "schema": "rappterzoo-agent-park-contract/1",
                "sha256": PARK_LEGACY_CONTRACT_SHA256,
            }
        ):
            raise ToolError("park v1 legacy contract hash mismatch")

        season_one = seasons.get("season_1", {})
        season_two = seasons.get("season_2", {})
        if (
            type(season_one) is not dict
            or type(season_two) is not dict
            or season_one.get("event_count")
            != PARK_SEASON_ONE_EVENT_COUNT
            or season_one.get("head") != PARK_SEASON_ONE_HEAD
            or season_one.get("immutable_prefix_sha256")
            != PARK_SEASON_ONE_PREFIX_SHA256
            or season_one.get("schema") != PARK_EVENT_SCHEMA_V1
            or season_two.get("first_seq")
            != PARK_SEASON_ONE_EVENT_COUNT
            or season_two.get("event_count")
            != len(events) - PARK_SEASON_ONE_EVENT_COUNT
            or season_two.get("head") != event_head
            or season_two.get("schema") != PARK_EVENT_SCHEMA_V2
        ):
            raise ToolError("park contract season facts mismatch")
        if (
            len(state_seasons) != 2
            or any(type(item) is not dict for item in state_seasons)
            or state.get("latest_season") != PARK_CONTRACT_VERSION
            or state.get("season") != PARK_CONTRACT_VERSION
            or state_seasons[0].get("season") != 1
            or state_seasons[0].get("event_count")
            != PARK_SEASON_ONE_EVENT_COUNT
            or state_seasons[0].get("head") != PARK_SEASON_ONE_HEAD
            or state_seasons[0].get("ledger_prefix_sha256")
            != PARK_SEASON_ONE_PREFIX_SHA256
            or state_seasons[1].get("season") != PARK_CONTRACT_VERSION
            or state_seasons[1].get("first_seq")
            != PARK_SEASON_ONE_EVENT_COUNT
            or state_seasons[1].get("event_count")
            != len(events) - PARK_SEASON_ONE_EVENT_COUNT
            or state_seasons[1].get("head") != event_head
        ):
            raise ToolError("park state season facts mismatch")

        if (
            event_ledger.get("event_count") != len(events)
            or event_ledger.get("head") != event_head
            or event_ledger.get("sha256") != event_ledger_sha256
        ):
            raise ToolError("park state event ledger facts mismatch")

        state_projection = copy.deepcopy(state)
        state_projection["integrity"].pop("state_digest", None)
        state_projection["integrity"].pop("bundle_digest", None)
        expected_state_digest = _park_digest(
            PARK_STATE_HASH_DOMAIN,
            state_projection,
        )
        if state_integrity.get("state_digest") != expected_state_digest:
            raise ToolError("park state digest mismatch")

        contract_projection = copy.deepcopy(contract)
        contract_projection["integrity"].pop("contract_digest", None)
        contract_projection["integrity"].pop("bundle_digest", None)
        expected_contract_digest = _park_digest(
            PARK_CONTRACT_HASH_DOMAIN,
            contract_projection,
        )
        if (
            contract_integrity.get("contract_digest")
            != expected_contract_digest
        ):
            raise ToolError("park v2 contract digest mismatch")

        expected_bundle_digest = _park_digest(
            PARK_BUNDLE_HASH_DOMAIN,
            {
                "contract_digest": expected_contract_digest,
                "event_count": len(events),
                "event_head": event_head,
                "event_ledger_sha256": event_ledger_sha256,
                "state_digest": expected_state_digest,
            },
        )
        if (
            state_integrity.get("bundle_digest")
            != expected_bundle_digest
            or contract_integrity.get("bundle_digest")
            != expected_bundle_digest
        ):
            raise ToolError("park bundle digest mismatch")
        return state, contract, projection

    def _fair_context(self) -> Dict[str, Any]:
        park_state, _park_contract, projection = self._park_context()
        events_raw = self.source.read_bytes("apps/agent-fair/events.jsonl")
        state = self.source.read_json("apps/agent-fair/fair-state.json")
        contract = self.source.read_json(
            "apps/agent-fair/agent-contract.json"
        )
        district = self.source.read_json("apps/agent-fair/district.json")
        if not all(
            type(item) is dict
            for item in (state, contract, district, projection)
        ):
            raise ToolError(
                "fair state, contract, district, and organism projection "
                "are required"
            )
        if not events_raw.endswith(b"\n"):
            raise ToolError("fair event ledger lacks a final newline")
        try:
            event_text = events_raw.decode("utf-8")
        except UnicodeDecodeError as error:
            raise ToolError("fair event ledger is not UTF-8") from error
        events = []
        for line_number, raw_line in enumerate(event_text.splitlines(), 1):
            if not raw_line:
                raise ToolError("fair event ledger contains a blank line")
            try:
                event = json.loads(raw_line)
            except json.JSONDecodeError as error:
                raise ToolError(
                    "fair event ledger contains invalid JSON at line {}".format(
                        line_number
                    )
                ) from error
            if type(event) is not dict:
                raise ToolError("fair event must be a JSON object")
            events.append(event)
        if len(events) != FAIR_EVENT_COUNT:
            raise ToolError("fair event count mismatch")
        canonical_event_bytes = b"".join(
            _park_canonical_bytes(event) + b"\n"
            for event in events
        )
        if canonical_event_bytes != events_raw:
            raise ToolError("fair event ledger bytes are not canonical")
        event_ledger_sha256 = hashlib.sha256(
            canonical_event_bytes
        ).hexdigest()
        previous_hash = None
        previous_utc = None
        for index, event in enumerate(events):
            if set(event) != FAIR_EVENT_KEYS:
                raise ToolError("fair event key set mismatch")
            if (
                event.get("schema") != FAIR_EVENT_SCHEMA
                or event.get("fair_id") != FAIR_ID
                or event.get("visibility") != "public-metadata"
                or event.get("seq") != index
                or event.get("prev") != previous_hash
                or type(event.get("payload")) is not dict
            ):
                raise ToolError("fair event identity or chain mismatch")
            try:
                parsed_utc = datetime.strptime(
                    event["utc"],
                    "%Y-%m-%dT%H:%M:%S.%fZ",
                ).replace(tzinfo=timezone.utc)
            except (TypeError, ValueError) as error:
                raise ToolError("fair event UTC is invalid") from error
            canonical_utc = (
                parsed_utc.isoformat(timespec="milliseconds")
                .replace("+00:00", "Z")
            )
            if (
                event["utc"] != canonical_utc
                or (
                    previous_utc is not None
                    and parsed_utc <= previous_utc
                )
            ):
                raise ToolError(
                    "fair event UTC is not canonical and strictly increasing"
                )
            if event.get("payload_hash") != _park_digest(
                FAIR_PAYLOAD_HASH_DOMAIN,
                event["payload"],
            ):
                raise ToolError("fair event payload hash mismatch")
            projected_event = copy.deepcopy(event)
            claimed_event_hash = projected_event.pop("event_hash")
            if claimed_event_hash != _park_digest(
                FAIR_EVENT_HASH_DOMAIN,
                projected_event,
            ):
                raise ToolError("fair event hash mismatch")
            previous_hash = claimed_event_hash
            previous_utc = parsed_utc
        event_head = previous_hash
        expected_kinds = (
            ["fair.genesis", "fair.contract-lock"]
            + ["fair.submission"] * FAIR_SUBMISSION_COUNT
            + ["fair.screening"]
            + ["fair.voting-round"] * FAIR_VOTING_ROUNDS
            + [
                "fair.evaluation",
                "fair.winner-selection",
                "fair.district-assembly",
                "fair.release-ready",
            ]
        )
        if [event.get("kind") for event in events] != expected_kinds:
            raise ToolError("fair event phase order mismatch")

        state_integrity = state.get("integrity", {})
        contract_integrity = contract.get("integrity", {})
        district_integrity = district.get("integrity", {})
        if not all(
            type(item) is dict
            for item in (
                state_integrity,
                contract_integrity,
                district_integrity,
            )
        ):
            raise ToolError("fair integrity fields are malformed")
        state_projection = copy.deepcopy(state)
        state_projection["integrity"].pop("state_digest", None)
        state_projection["integrity"].pop("bundle_digest", None)
        state_digest = _park_digest(
            FAIR_STATE_HASH_DOMAIN,
            state_projection,
        )
        contract_projection = copy.deepcopy(contract)
        contract_projection["integrity"].pop("contract_digest", None)
        contract_projection["integrity"].pop("bundle_digest", None)
        contract_digest = _park_digest(
            FAIR_CONTRACT_HASH_DOMAIN,
            contract_projection,
        )
        district_projection = copy.deepcopy(district)
        district_projection["integrity"].pop("district_digest", None)
        district_projection["integrity"].pop("bundle_digest", None)
        district_digest = _park_digest(
            FAIR_DISTRICT_HASH_DOMAIN,
            district_projection,
        )
        bundle_digest = _park_digest(
            FAIR_BUNDLE_HASH_DOMAIN,
            {
                "contract_digest": contract_digest,
                "district_digest": district_digest,
                "event_count": len(events),
                "event_head": event_head,
                "event_ledger_sha256": event_ledger_sha256,
                "state_digest": state_digest,
            },
        )
        if state_integrity.get("state_digest") != state_digest:
            raise ToolError("fair state digest mismatch")
        if contract_integrity.get("contract_digest") != contract_digest:
            raise ToolError("fair contract digest mismatch")
        if district_integrity.get("district_digest") != district_digest:
            raise ToolError("fair district digest mismatch")
        if (
            state_integrity.get("bundle_digest") != bundle_digest
            or contract_integrity.get("bundle_digest") != bundle_digest
            or district_integrity.get("bundle_digest") != bundle_digest
        ):
            raise ToolError("fair bundle digest binding mismatch")
        if (
            event_head != FAIR_EXPECTED_EVENT_HEAD
            or event_ledger_sha256 != FAIR_EXPECTED_EVENT_LEDGER_SHA256
            or state_digest != FAIR_EXPECTED_STATE_DIGEST
            or contract_digest != FAIR_EXPECTED_CONTRACT_DIGEST
            or district_digest != FAIR_EXPECTED_DISTRICT_DIGEST
            or bundle_digest != FAIR_EXPECTED_BUNDLE_DIGEST
        ):
            raise ToolError("fair deterministic release digest mismatch")

        local_proposals = contract.get("local_proposals", {})
        data_boundary = contract.get("data_boundary", {})
        economy = contract.get("economy", {})
        controls = contract.get("control_boundary", {})
        attraction_contract = contract.get("attraction_contract", {})
        state_controls = state.get("customer_controls", {})
        assembly = district.get("assembly", {})
        if not all(
            type(item) is dict
            for item in (
                local_proposals,
                data_boundary,
                economy,
                controls,
                attraction_contract,
                state_controls,
                assembly,
            )
        ):
            raise ToolError("fair authority boundary is malformed")
        if (
            state.get("schema") != FAIR_STATE_SCHEMA
            or contract.get("schema") != FAIR_CONTRACT_SCHEMA
            or district.get("schema") != FAIR_DISTRICT_SCHEMA
            or state.get("fair_id") != FAIR_ID
            or contract.get("fair_id") != FAIR_ID
            or district.get("fair_id") != FAIR_ID
            or district.get("district_id") != FAIR_DISTRICT_ID
            or state.get("visibility") != "public-metadata"
            or contract.get("visibility") != "public-metadata"
            or district.get("visibility") != "public-metadata"
            or state.get("status")
            != "release-ready-awaiting-customer-approval"
            or attraction_contract.get("attractions_per_submission") != 1
            or attraction_contract.get("resource_maximums")
            != FAIR_RESOURCE_MAXIMUMS
            or attraction_contract.get("visibility") != "public-metadata"
            or local_proposals.get("action_limit")
            != MAX_FAIR_BRANCH_ACTIONS
            or local_proposals.get("action_schema") != FAIR_ACTION_SCHEMA
            or local_proposals.get("export_schema")
            != FAIR_BRANCH_SCHEMA
            or local_proposals.get("canonical_mutation") is not False
            or set(contract.get("mcp_mappings", {})) != {
                "agent_fair_submit_attraction",
                "agent_fair_cast_vote",
                "agent_fair_export_branch",
            }
            or data_boundary.get("allowed") != ["public-metadata"]
            or data_boundary.get("external_network") is not False
            or not {
                "GODD",
                "biometric",
                "identity-template",
                "raw-camera",
                "nonpublic",
            }.issubset(set(data_boundary.get("excluded_classes", [])))
            or economy.get("currency") != "synthetic-admission-credit"
            or economy.get("real_money") is not False
            or economy.get("redeemable") is not False
            or economy.get("transferable") is not False
            or contract.get("synthetic_only") is not True
            or controls.get("canonical_write") != "forbidden"
            or controls.get("customer_authority")
            != "explicit-release-command-only"
            or controls.get("customer_shutdown") is not True
            or controls.get("operator_key_custody") != "customer-local"
            or controls.get("vendor_shutdown") is not False
            or controls.get("write_scope") != "local-proposal-branch-only"
            or state_controls.get("canonical_write") is not False
            or state_controls.get(
                "customer_approval_required_for_organism_release"
            ) is not True
            or state_controls.get("release_performed") is not False
            or state_controls.get("customer_shutdown") is not True
            or state_controls.get("vendor_shutdown") is not False
            or assembly.get("direct_canonical_write") is not False
            or assembly.get("status")
            != "release-ready-awaiting-customer-approval"
            or assembly.get(
                "customer_approval_required_for_organism_release"
            ) is not True
        ):
            raise ToolError("fair authority boundary is unsafe or incomplete")
        if not {
            "external-network",
            "real-money",
            "nonpublic-data",
            "GODD-data",
            "biometric-data",
            "remote-shutdown",
            "direct-canonical-write",
        }.issubset(set(contract.get("prohibitions", []))):
            raise ToolError("fair prohibitions are incomplete")

        event_ledger = state.get("event_ledger", {})
        if event_ledger != {
            "event_count": len(events),
            "exact_keys": sorted(FAIR_EVENT_KEYS),
            "head": event_head,
            "path": "events.jsonl",
            "sha256": event_ledger_sha256,
        }:
            raise ToolError("fair state event ledger facts mismatch")
        if state.get("agent_contract") != {
            "contract_digest": contract_digest,
            "path": "agent-contract.json",
        }:
            raise ToolError("fair state contract binding mismatch")
        if state.get("district", {}).get("district_digest") != district_digest:
            raise ToolError("fair state district binding mismatch")

        submission_events = [
            event for event in events if event["kind"] == "fair.submission"
        ]
        submissions_by_digest = {}
        canonical_agent_ids = set()
        attraction_ids = set()
        submission_ids = []
        for event in submission_events:
            submission = copy.deepcopy(
                event.get("payload", {}).get("submission")
            )
            if type(submission) is not dict:
                raise ToolError("fair submission payload is malformed")
            claimed_digest = submission.pop("submission_digest", None)
            expected_digest = _park_digest(
                FAIR_SUBMISSION_HASH_DOMAIN,
                submission,
            )
            if claimed_digest != expected_digest:
                raise ToolError("fair submission digest mismatch")
            attractions = submission.get("attractions")
            agent = submission.get("agent")
            if (
                type(attractions) is not list
                or len(attractions) != 1
                or type(attractions[0]) is not dict
                or type(agent) is not dict
            ):
                raise ToolError(
                    "each fair submission must contain one attraction"
                )
            resource_request = attractions[0].get("resource_request")
            self._fair_resources(resource_request, "resource_request")
            agent_id = agent.get("identity_id")
            attraction_id = attractions[0].get("id")
            submission_id = submission.get("submission_id")
            if (
                type(agent_id) is not str
                or type(attraction_id) is not str
                or type(submission_id) is not str
                or agent_id in canonical_agent_ids
                or attraction_id in attraction_ids
                or claimed_digest in submissions_by_digest
            ):
                raise ToolError("fair submission identity is duplicated")
            submission["submission_digest"] = claimed_digest
            canonical_agent_ids.add(agent_id)
            attraction_ids.add(attraction_id)
            submission_ids.append(submission_id)
            submissions_by_digest[claimed_digest] = submission
        if (
            len(submissions_by_digest) != FAIR_SUBMISSION_COUNT
            or state.get("submission_count") != FAIR_SUBMISSION_COUNT
        ):
            raise ToolError("fair submission count mismatch")

        screening_event = next(
            event for event in events if event["kind"] == "fair.screening"
        )
        screening = screening_event["payload"]
        if (
            state.get("screening") != screening
            or screening.get("contract_limits") != FAIR_RESOURCE_MAXIMUMS
            or screening.get("accepted_submission_ids") != submission_ids
            or screening.get("rejected_submission_ids") != []
        ):
            raise ToolError("fair screening projection mismatch")

        voting_events = [
            event for event in events if event["kind"] == "fair.voting-round"
        ]
        voting_rounds = [event["payload"] for event in voting_events]
        voting = state.get("voting", {})
        total_issued = 0
        total_spent = 0
        valid_submission_ids = set(submission_ids)
        for round_number, round_value in enumerate(voting_rounds, 1):
            if (
                round_value.get("round") != round_number
                or type(round_value.get("cohort_votes")) is not list
            ):
                raise ToolError("fair voting round is malformed")
            issued = round_value.get("issued_credits")
            spent = round_value.get("spent_credits")
            if (
                type(issued) is not int
                or type(spent) is not int
                or issued != spent
                or issued < 0
            ):
                raise ToolError("fair voting credits are unbalanced")
            total_issued += issued
            total_spent += spent
            for cohort in round_value["cohort_votes"]:
                if (
                    type(cohort) is not dict
                    or type(cohort.get("issued_credits")) is not int
                    or cohort.get("issued_credits")
                    != cohort.get("spent_credits")
                    or sum(
                        allocation.get("admissions", -1)
                        for allocation in cohort.get("allocations", [])
                        if type(allocation) is dict
                    )
                    != cohort.get("spent_credits")
                    or any(
                        allocation.get("submission_id")
                        not in valid_submission_ids
                        for allocation in cohort.get("allocations", [])
                        if type(allocation) is dict
                    )
                ):
                    raise ToolError("fair cohort vote is unbalanced")
        if (
            type(voting) is not dict
            or voting.get("round_count") != FAIR_VOTING_ROUNDS
            or voting.get("rounds") != voting_rounds
            or voting.get("total_issued") != total_issued
            or voting.get("total_spent") != total_spent
        ):
            raise ToolError("fair voting projection mismatch")
        state_economy = state.get("economy", {})
        if (
            type(state_economy) is not dict
            or state_economy.get("currency")
            != "synthetic-admission-credit"
            or state_economy.get("real_money") is not False
            or state_economy.get("balanced") is not True
            or state_economy.get("total_issued") != total_issued
            or state_economy.get("total_spent") != total_spent
            or state_economy.get("total_debits")
            != state_economy.get("total_credits")
        ):
            raise ToolError("fair synthetic economy is unbalanced")

        evaluation = next(
            event for event in events if event["kind"] == "fair.evaluation"
        )["payload"]
        rankings = evaluation.get("rankings")
        weights = evaluation.get("score_weights_bps")
        if (
            type(rankings) is not list
            or state.get("rankings") != rankings
            or type(weights) is not dict
            or sum(weights.values()) != 10000
        ):
            raise ToolError("fair evaluation projection mismatch")
        for rank, ranking in enumerate(rankings, 1):
            dimensions = ranking.get("dimensions_bps", {})
            if (
                ranking.get("rank") != rank
                or ranking.get("submission_id") not in valid_submission_ids
                or type(dimensions) is not dict
                or set(dimensions) != set(weights)
                or any(type(value) is not int for value in dimensions.values())
                or ranking.get("score_bps")
                != sum(
                    dimensions[name] * weights[name]
                    for name in weights
                ) // 10000
            ):
                raise ToolError("fair evaluation score is inconsistent")

        winner_event = next(
            event
            for event in events
            if event["kind"] == "fair.winner-selection"
        )["payload"]
        winners = winner_event.get("winner_submission_ids")
        if (
            type(winners) is not list
            or len(winners) != 4
            or state.get("winner_selection") != winner_event
            or state.get("winners") != winners
        ):
            raise ToolError("fair winner projection mismatch")
        pavilions = district.get("pavilions")
        if (
            type(pavilions) is not list
            or [item.get("submission_id") for item in pavilions] != winners
            or district.get("resource_totals")
            != winner_event.get("resource_totals")
            or any(
                district.get("resource_totals", {}).get(name, -1)
                > district.get("resource_capacity", {}).get(name, -1)
                for name in FAIR_RESOURCE_NAMES
            )
        ):
            raise ToolError("fair district assembly mismatch")
        assembly_event = next(
            event
            for event in events
            if event["kind"] == "fair.district-assembly"
        )["payload"]
        release_event = next(
            event for event in events if event["kind"] == "fair.release-ready"
        )["payload"]
        if (
            assembly_event.get("district_digest") != district_digest
            or assembly_event.get("district_id") != FAIR_DISTRICT_ID
            or assembly_event.get("pavilion_submission_ids") != winners
            or assembly_event.get("resource_totals")
            != district.get("resource_totals")
            or release_event.get("district_digest") != district_digest
            or release_event.get("district_id") != FAIR_DISTRICT_ID
            or release_event.get("customer_approval_required") is not True
            or release_event.get("direct_canonical_write") is not False
        ):
            raise ToolError("fair release boundary mismatch")

        park_anchor = state.get("anchor", {}).get("park")
        park_ledger = park_state.get("event_ledger", {})
        park_integrity = park_state.get("integrity", {})
        if (
            type(park_anchor) is not dict
            or type(park_ledger) is not dict
            or type(park_integrity) is not dict
            or park_anchor != {
                "bundle_digest": park_integrity.get("bundle_digest"),
                "event_count": park_ledger.get("event_count"),
                "event_head": park_ledger.get("head"),
                "event_ledger_sha256": park_ledger.get("sha256"),
                "source": "apps/agent-park",
            }
        ):
            raise ToolError("fair park source anchor mismatch")
        organism_anchor = state.get("anchor", {}).get(
            "organism_release_frame"
        )
        organism_records = self._read_jsonl("apps/organism-frames.jsonl")
        if type(organism_anchor) is not dict:
            raise ToolError("fair organism source anchor is malformed")
        anchor_record = next(
            (
                record
                for record in organism_records
                if record.get("seq") == organism_anchor.get("seq")
            ),
            None,
        )
        if (
            anchor_record is None
            or organism_anchor.get("source")
            != "apps/organism-frames.jsonl"
            or anchor_record.get("frame_hash")
            != organism_anchor.get("frame_hash")
            or anchor_record.get("payload", {}).get("bundle_digest")
            != park_integrity.get("bundle_digest")
            or anchor_record.get("payload", {}).get("ledger_head")
            != park_ledger.get("head")
        ):
            raise ToolError("fair organism source anchor mismatch")
        projection_frames = projection.get("frames", [])
        projection_integrity = projection.get("integrity", {})
        projection_head = (
            projection_integrity.get("head", {})
            if type(projection_integrity) is dict
            else {}
        )
        organism_head = (
            projection_head.get("frame_hash")
            if type(projection_head) is dict
            else None
        )
        if organism_head is None and projection_frames:
            organism_head = projection_frames[-1].get("frame_hash")
        if not re.fullmatch(r"[0-9a-f]{64}", str(organism_head or "")):
            raise ToolError("current organism head is unavailable")
        organism_hashes = {
            record.get("frame_hash")
            for record in organism_records
            if re.fullmatch(
                r"[0-9a-f]{64}",
                str(record.get("frame_hash") or ""),
            )
        }
        organism_hashes.update(
            record.get("frame_hash")
            for record in projection_frames
            if type(record) is dict
            and re.fullmatch(
                r"[0-9a-f]{64}",
                str(record.get("frame_hash") or ""),
            )
        )
        return {
            "state": state,
            "events": events,
            "contract": contract,
            "district": district,
            "projection": projection,
            "submissions_by_digest": submissions_by_digest,
            "canonical_agent_ids": canonical_agent_ids,
            "attraction_ids": attraction_ids,
            "organism_hashes": organism_hashes,
            "heads": {
                "fair_event_head": event_head,
                "fair_district_digest": district_digest,
                "fair_bundle_digest": bundle_digest,
                "organism_head": organism_head,
            },
        }

    @staticmethod
    def _expected_fair_release_payload(
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        heads = context["heads"]
        state = context["state"]
        district = context["district"]
        candidate_placeholder = "$candidate_digest"
        approval_keys = [
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
        ]
        return {
            "app_file": "agent-worlds-fair.html",
            "approval_basis": "verified-github-actions-oidc-attestation",
            "approval_evidence": {
                "exact_keys": approval_keys,
                "fixed_claims": {
                    "aud": "rappterzoo-agent-fair-release",
                    "environment": "agent-fair-production",
                    "event_name": "workflow_dispatch",
                    "iss": "https://token.actions.githubusercontent.com",
                    "ref": "refs/heads/main",
                    "repository": DEFAULT_REPOSITORY,
                    "workflow_ref": (
                        "kody-w/localFirstTools-main/.github/workflows/"
                        "agent-fair-release.yml@refs/heads/main"
                    ),
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
            "display_name": "Agent World's Fair",
            "district_digest": heads["fair_district_digest"],
            "event": FAIR_RELEASE_EVENT,
            "event_id": "{}:{}:{}".format(
                FAIR_RELEASE_EVENT,
                heads["fair_bundle_digest"],
                heads["fair_district_digest"],
            ),
            "fair_bundle_digest": heads["fair_bundle_digest"],
            "fair_event_head": heads["fair_event_head"],
            "organism": FAIR_DISTRICT_ID,
            "organism_type": "agent-worlds-fair-district",
            "release_candidate_digest": candidate_placeholder,
            "schema": FAIR_RELEASE_FRAME_SCHEMA,
            "visibility": "public-metadata",
            "winner_submission_ids": copy.deepcopy(state["winners"]),
        }

    def _verified_fair_release_candidate(
        self,
        context: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        if type(context) is not dict:
            raise ToolError("verified fair context is required")
        candidate = self.source.read_json(
            "apps/agent-fair/release-candidate.json"
        )
        if type(candidate) is not dict:
            raise ToolError("fair release candidate must be an object")
        expected = {
            "app": "apps/3d-immersive/agent-worlds-fair.html",
            "approval_required": True,
            "bundle_digest": context["heads"]["fair_bundle_digest"],
            "candidate_digest_domain": (
                FAIR_RELEASE_CANDIDATE_HASH_DOMAIN.decode("ascii")
            ),
            "candidate_digest_preimage": (
                "candidate digest domain bytes || canonical_bytes(candidate "
                "with candidate_digest omitted)"
            ),
            "district_digest": context["heads"]["fair_district_digest"],
            "district_id": FAIR_DISTRICT_ID,
            "event_count": len(context["events"]),
            "event_head": context["heads"]["fair_event_head"],
            "expected_frame_payload": self._expected_fair_release_payload(
                context
            ),
            "fair_id": FAIR_ID,
            "schema": FAIR_RELEASE_CANDIDATE_SCHEMA,
            "verifier": {
                "command": FAIR_RELEASE_VERIFIER_COMMAND,
                "version": FAIR_RELEASE_VERIFIER_VERSION,
            },
        }
        expected["candidate_digest"] = _park_digest(
            FAIR_RELEASE_CANDIDATE_HASH_DOMAIN,
            expected,
        )
        submitted = copy.deepcopy(candidate)
        claimed_digest = submitted.pop("candidate_digest", None)
        if (
            claimed_digest != _park_digest(
                FAIR_RELEASE_CANDIDATE_HASH_DOMAIN,
                submitted,
            )
            or candidate != expected
        ):
            raise ToolError(
                "fair release candidate does not match the verified bundle"
            )
        return candidate

    @staticmethod
    def _verify_release_approval_evidence(
        evidence: Any,
        requirement: Dict[str, Any],
    ) -> None:
        exact_keys = requirement.get("exact_keys", [])
        fixed_claims = requirement.get("fixed_claims", {})
        if (
            type(evidence) is not dict
            or type(exact_keys) is not list
            or set(evidence) != set(exact_keys)
            or type(fixed_claims) is not dict
            or any(
                evidence.get(name) != value
                for name, value in fixed_claims.items()
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
            or not re.fullmatch(
                r"[0-9a-f]{64}",
                str(evidence.get("attestation_sha256") or ""),
            )
            or evidence.get("attestation_sha256") == "0" * 64
        ):
            raise ToolError("fair release approval evidence is invalid")

    def _verified_fair_release_frame(
        self,
        context: Dict[str, Any],
        candidate: Dict[str, Any],
    ) -> Dict[str, Any]:
        matches = [
            frame
            for frame in self._read_jsonl("apps/organism-frames.jsonl")
            if frame.get("payload", {}).get("event") == FAIR_RELEASE_EVENT
            and frame.get("payload", {}).get("release_candidate_digest")
            == candidate["candidate_digest"]
        ]
        if len(matches) != 1:
            raise ToolError(
                "fair release evidence must contain one matching frame"
            )
        frame = matches[0]
        expected_keys = {
            "frame_hash",
            "kind",
            "payload",
            "payload_hash",
            "prev",
            "prev_wave",
            "seq",
            "sig",
            "spec",
            "stream_id",
            "utc",
        }
        if (
            set(frame) != expected_keys
            or frame.get("spec") != "rapp/1"
            or frame.get("stream_id") != "net:rappterzoo"
            or frame.get("kind") != "zoo.observation"
            or type(frame.get("seq")) is not int
            or frame.get("sig") is not None
            or type(frame.get("payload")) is not dict
        ):
            raise ToolError("fair release frame structure is invalid")
        payload = frame["payload"]
        expected_payload = copy.deepcopy(candidate["expected_frame_payload"])
        requirement = expected_payload["approval_evidence"]
        expected_payload["approval_evidence"] = payload.get(
            "approval_evidence"
        )
        expected_payload["release_candidate_digest"] = candidate[
            "candidate_digest"
        ]
        self._verify_release_approval_evidence(
            payload.get("approval_evidence"),
            requirement,
        )
        try:
            approved_at = int(
                datetime.strptime(
                    frame["utc"],
                    "%Y-%m-%dT%H:%M:%S.%fZ",
                ).replace(tzinfo=timezone.utc).timestamp()
            )
        except (KeyError, TypeError, ValueError) as error:
            raise ToolError("fair release frame UTC is invalid") from error
        evidence = payload["approval_evidence"]
        if not evidence["nbf"] <= approved_at < evidence["exp"]:
            raise ToolError(
                "fair release frame falls outside the OIDC approval window"
            )
        if payload != expected_payload:
            raise ToolError("fair release frame conflicts with the candidate")
        if frame.get("payload_hash") != _park_digest(
            FRAME_PAYLOAD_HASH_DOMAIN,
            payload,
        ):
            raise ToolError("fair release frame payload hash mismatch")
        wave = {
            key: value
            for key, value in frame.items()
            if key not in {"frame_hash", "sig"}
        }
        if frame.get("frame_hash") != _park_digest(
            FRAME_HASH_DOMAIN,
            wave,
        ):
            raise ToolError("fair release frame hash mismatch")
        return frame

    def _verified_fair_release_delta(
        self,
        context: Dict[str, Any],
        release_frame: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        index = self.source.read_json("apps/syndication/index.json")
        if (
            type(index) is not dict
            or index.get("profile") != SYNDICATION_PROFILE
            or type(index.get("deltas")) is not list
        ):
            raise ToolError("syndication index is not profile 10")
        expected_descriptor_hashes = {
            "agent-contract": hashlib.sha256(self.source.read_bytes(
                "apps/agent-fair/agent-contract.json"
            )).hexdigest(),
            "district": hashlib.sha256(self.source.read_bytes(
                "apps/agent-fair/district.json"
            )).hexdigest(),
            "event-ledger": hashlib.sha256(self.source.read_bytes(
                "apps/agent-fair/events.jsonl"
            )).hexdigest(),
            "state": hashlib.sha256(self.source.read_bytes(
                "apps/agent-fair/fair-state.json"
            )).hexdigest(),
        }
        entries = index["deltas"]
        if (
            not entries
            or len(entries) > 10000
            or index.get("delta_count") != len(entries)
        ):
            raise ToolError(
                "syndication index has an invalid release verification bound"
            )
        previous_delta = None
        for sequence, item in enumerate(entries):
            if (
                type(item) is not dict
                or item.get("sequence") != sequence
                or item.get("previous_delta") != previous_delta
                or not re.fullmatch(
                    r"[0-9a-f]{64}",
                    str(item.get("sha256") or ""),
                )
                or item.get("path")
                != "deltas/{}.json".format(item.get("sha256"))
                or item.get("url")
                != urllib.parse.urljoin(
                    DEFAULT_BASE_URL,
                    "apps/syndication/{}".format(item.get("path")),
                )
            ):
                raise ToolError(
                    "syndication index release ancestry is invalid"
                )
            previous_delta = item["sha256"]
        if index.get("head") != {
            key: entries[-1].get(key)
            for key in ("path", "sequence", "sha256", "url")
        }:
            raise ToolError("syndication index head is invalid")
        release_entries = [
            entry
            for entry in entries
            if type(entry) is dict
            and entry.get("sequence") == FAIR_RELEASE_DELTA_SEQUENCE
        ]
        if len(release_entries) != 1:
            raise ToolError(
                "profile-10 history lacks the pinned fair release delta"
            )
        entry = release_entries[0]
        if entry.get("sha256") != FAIR_RELEASE_DELTA_SHA256:
            raise ToolError("pinned fair release delta digest changed")
        found = None
        release_descriptors = None
        for entry in release_entries:
            if (
                type(entry) is not dict
                or entry.get("profile") != SYNDICATION_PROFILE
                or not re.fullmatch(
                    r"[0-9a-f]{64}",
                    str(entry.get("sha256") or ""),
                )
                or entry.get("path")
                != "deltas/{}.json".format(entry.get("sha256"))
                or type(entry.get("size")) is not int
            ):
                continue
            relative = "apps/syndication/{}".format(entry["path"])
            raw = self.source.read_bytes(relative)
            if (
                len(raw) != entry["size"]
                or hashlib.sha256(raw).hexdigest() != entry["sha256"]
            ):
                raise ToolError("fair release delta bytes do not match index")
            try:
                delta = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                raise ToolError("fair release delta is invalid JSON") from error
            if _canonical_bytes(delta) + b"\n" != raw:
                raise ToolError("fair release delta is not canonical JSON")
            changes = delta.get("changes", {})
            if (
                type(changes) is not dict
                or type(changes.get("frame_appends")) is not list
                or type(changes.get("data_upserts")) is not list
                or type(changes.get("data_tombstones")) is not list
            ):
                raise ToolError("fair release delta changes are malformed")
            frame_appends = changes["frame_appends"]
            if not any(
                frame.get("frame_hash") == release_frame["frame_hash"]
                for frame in frame_appends
                if type(frame) is dict
            ):
                continue
            if (
                delta.get("profile") != SYNDICATION_PROFILE
                or delta.get("schema") != "rappterzoo-syndication-delta/1"
                or delta.get("sequence") != entry["sequence"]
                or delta.get("previous_delta") != entry["previous_delta"]
                or frame_appends.count(release_frame) != 1
                or sum(
                    frame.get("payload", {}).get("event")
                    == FAIR_RELEASE_EVENT
                    for frame in frame_appends
                    if type(frame) is dict
                )
                != 1
            ):
                raise ToolError("fair release frame is not atomic profile 10")
            fair_upserts = [
                descriptor
                for descriptor in changes.get("data_upserts", [])
                if type(descriptor) is dict
                and descriptor.get("kind") == "agent-worlds-fair-object"
            ]
            resource_hashes = {
                descriptor.get("metadata", {}).get("resource_type"):
                descriptor.get("sha256")
                for descriptor in fair_upserts
                if type(descriptor.get("metadata")) is dict
            }
            fair_tombstones = [
                tombstone
                for tombstone in changes.get("data_tombstones", [])
                if type(tombstone) is dict
                and tombstone.get("descriptor", {}).get("kind")
                == "agent-worlds-fair-object"
            ]
            if (
                len(fair_upserts) != len(FAIR_RELEASE_RESOURCE_TYPES)
                or set(resource_hashes) != FAIR_RELEASE_RESOURCE_TYPES
                or resource_hashes != expected_descriptor_hashes
                or fair_tombstones
            ):
                raise ToolError(
                    "fair release delta lacks the four exact bundle resources"
                )
            release_descriptors = fair_upserts
            found = (entry, delta)
            break
        if found is None:
            raise ToolError(
                "pinned profile-10 delta lacks the verified fair release"
            )

        snapshot_metadata = index.get("snapshot", {})
        snapshot_raw = self.source.read_bytes(
            "apps/syndication/snapshot.json"
        )
        if (
            type(snapshot_metadata) is not dict
            or snapshot_metadata.get("path") != "snapshot.json"
            or snapshot_metadata.get("url")
            != urllib.parse.urljoin(
                DEFAULT_BASE_URL,
                "apps/syndication/snapshot.json",
            )
            or snapshot_metadata.get("size") != len(snapshot_raw)
            or snapshot_metadata.get("sha256")
            != hashlib.sha256(snapshot_raw).hexdigest()
        ):
            raise ToolError("profile-10 snapshot does not match its index")
        try:
            snapshot = json.loads(snapshot_raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ToolError("profile-10 snapshot is invalid JSON") from error
        if _canonical_bytes(snapshot) + b"\n" != snapshot_raw:
            raise ToolError("profile-10 snapshot is not canonical JSON")
        snapshot_objects = snapshot.get("data_objects", [])
        snapshot_apps = snapshot.get("apps", [])
        snapshot_frames = snapshot.get("frames", [])
        snapshot_checkpoint = snapshot.get("checkpoint", {})
        if (
            type(snapshot_objects) is not list
            or type(snapshot_apps) is not list
            or type(snapshot_frames) is not list
            or type(snapshot_checkpoint) is not dict
        ):
            raise ToolError("profile-10 snapshot structure is invalid")
        fair_snapshot_objects = [
            descriptor
            for descriptor in snapshot_objects
            if type(descriptor) is dict
            and descriptor.get("kind") == "agent-worlds-fair-object"
        ]
        snapshot_hashes = {
            descriptor.get("metadata", {}).get("resource_type"):
            descriptor.get("sha256")
            for descriptor in fair_snapshot_objects
            if type(descriptor.get("metadata")) is dict
        }
        if (
            snapshot.get("profile") != SYNDICATION_PROFILE
            or snapshot.get("head") != index["head"]
            or snapshot_checkpoint.get("delta_sha256")
            != index["head"]["sha256"]
            or snapshot_checkpoint.get("since_seq")
            != index["head"]["sequence"]
            or len(fair_snapshot_objects)
            != len(FAIR_RELEASE_RESOURCE_TYPES)
            or fair_snapshot_objects != release_descriptors
            or snapshot_hashes != expected_descriptor_hashes
            or sum(
                frame == release_frame
                for frame in snapshot_frames
                if type(frame) is dict
            )
            != 1
            or any(
                descriptor.get("path")
                == "apps/agent-fair/release-candidate.json"
                for descriptor in snapshot_objects + snapshot_apps
                if type(descriptor) is dict
            )
        ):
            raise ToolError("profile-10 fair snapshot boundary is invalid")
        return found

    def _fair_release_state(
        self,
        context: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        if type(context) is not dict:
            raise ToolError("verified fair context is required")
        candidate = self._verified_fair_release_candidate(context)
        release_frame = self._verified_fair_release_frame(
            context,
            candidate,
        )
        entry, delta = self._verified_fair_release_delta(
            context,
            release_frame,
        )
        payload = release_frame["payload"]
        evidence = payload["approval_evidence"]
        return {
            "schema": "rappterzoo-agent-worlds-fair-release-state/1",
            "fair_id": FAIR_ID,
            "district_id": FAIR_DISTRICT_ID,
            "status": "released",
            "prepared_bundle_status": context["state"].get("status"),
            "bundle": copy.deepcopy(context["heads"]),
            "release_candidate": {
                "uri": "rappterzoo://agent-fair-release-candidate",
                "url": urllib.parse.urljoin(
                    self.source.base_url,
                    "apps/agent-fair/release-candidate.json",
                ),
                "candidate_digest": candidate["candidate_digest"],
                "approval_required": candidate["approval_required"],
                "verified": True,
                "profile10_replica_included": False,
            },
            "release": {
                "customer_approved": payload["customer_approved"],
                "approval_basis": payload["approval_basis"],
                "approval_evidence": {
                    "attestation_sha256": evidence["attestation_sha256"],
                    "iss": evidence["iss"],
                    "repository": evidence["repository"],
                    "run_id": evidence["run_id"],
                    "workflow_ref": evidence["workflow_ref"],
                },
                "frame": {
                    "seq": release_frame["seq"],
                    "utc": release_frame["utc"],
                    "frame_hash": release_frame["frame_hash"],
                    "event_id": payload["event_id"],
                },
            },
            "syndication": {
                "profile": SYNDICATION_PROFILE,
                "index": urllib.parse.urljoin(
                    self.source.base_url,
                    "apps/syndication/index.json",
                ),
                "release_delta": entry.get("url") or urllib.parse.urljoin(
                    self.source.base_url,
                    "apps/syndication/{}".format(entry["path"]),
                ),
                "release_delta_sequence": delta["sequence"],
                "release_delta_sha256": entry["sha256"],
                "atomic_resource_types": sorted(
                    FAIR_RELEASE_RESOURCE_TYPES
                ),
            },
            "authority": {
                "canonical_mutation_by_mcp": False,
                "release_evidence": (
                    "customer-approved OIDC-bound organism frame plus "
                    "atomic profile-10 delta"
                ),
                "structural_assurance": "unsigned-structural-unverified",
            },
        }

    @staticmethod
    def _park_hash_facts(contract: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "canonical_bundle": contract["canonicalization_and_hashing"],
            "mcp_local_branch": {
                "algorithm": "sha256",
                "canonicalization": {
                    "id": PARK_CANONICALIZATION,
                    "encoding": "UTF-8",
                    "json": (
                        "json.dumps(value, ensure_ascii=False, "
                        "separators=(',', ':'), sort_keys=True)"
                    ),
                    "trailing_newline": False,
                },
                "domain_prefix": False,
                "preimages": {
                    "local_action_payload_hash": (
                        "canonical_json(action.payload)"
                    ),
                    "local_action_hash": (
                        "canonical_json(action excluding action_hash)"
                    ),
                    "branch_digest": (
                        "canonical_json(export excluding branch_digest)"
                    ),
                },
            },
        }

    def _park_contract_facts(
        self,
        state: Dict[str, Any],
        contract: Dict[str, Any],
    ) -> Dict[str, Any]:
        state_integrity = state.get("integrity", {})
        contract_integrity = contract.get("integrity", {})
        if type(state_integrity) is not dict:
            state_integrity = {}
        if type(contract_integrity) is not dict:
            contract_integrity = {}
        return {
            "contract_version": contract["seasons"]["latest"],
            "contract_version_field": "seasons.latest",
            "contract_schema": contract["schema"],
            "primary_contract": "rappterzoo://agent-park-contract",
            "historical_contract": "rappterzoo://agent-park-contract-v1",
            "primary_contract_url": urllib.parse.urljoin(
                self.source.base_url,
                "apps/agent-park/agent-contract-v2.json",
            ),
            "historical_contract_url": urllib.parse.urljoin(
                self.source.base_url,
                "apps/agent-park/agent-contract.json",
            ),
            "bundle": {
                "state_schema": state.get("schema"),
                "bundle_digest": (
                    contract_integrity.get("bundle_digest")
                    or state_integrity.get("bundle_digest")
                ),
                "contract_digest": contract_integrity.get("contract_digest"),
                "state_digest": state_integrity.get("state_digest"),
                "event_count": state.get("event_ledger", {}).get("event_count")
                if type(state.get("event_ledger")) is dict
                else None,
                "event_head": state.get("event_ledger", {}).get("head")
                if type(state.get("event_ledger")) is dict
                else None,
                "seasons": contract.get("seasons"),
                "legacy_contract": contract.get("legacy_contract"),
            },
            "local_branch": {
                "schema": PARK_BRANCH_SCHEMA,
                "action_schema": PARK_ACTION_SCHEMA,
                "generated_contract_schema": contract.get(
                    "branch_export",
                    {},
                ).get("export_schema"),
                "generated_contract_action_schema": contract.get(
                    "branch_export",
                    {},
                ).get("action_schema"),
                "action_limit": MAX_LOCAL_BRANCH_ACTIONS,
                "append_only": True,
                "mcp_undo_action": False,
                "mcp_import_tool": False,
                "browser_import": (
                    "verify before replay; reject without replacing state"
                ),
                "browser_clear_undo": (
                    "restore a volatile pre-clear checkpoint; not an action"
                ),
            },
            "hashing": self._park_hash_facts(contract),
            "verifier": {
                "version": contract["verifier"]["version"],
                "fail_closed": contract["verifier"]["fail_closed"],
                "bundle_source": (
                    "rappterzoo://agent-park-bundle-verifier"
                ),
                "bundle_command": contract["verifier"]["command"].split(" "),
                "acceptance_gate_source": (
                    "rappterzoo://agent-park-acceptance-gate"
                ),
                "acceptance_gate_command": [
                    "python3",
                    "scripts/agent_park_gate.py",
                ],
            },
            "custody": {
                "mcp_export_transport": "plaintext-json-over-local-stdio",
                "browser_default": "memory-only",
                "browser_encryption": {
                    "cipher": "AES-GCM-256",
                    "kdf": "PBKDF2-SHA-256",
                    "iterations": 250000,
                    "salt_bytes": 16,
                    "iv_bytes": 12,
                    "additional_data": "schema|origin|pathname",
                },
                "keys_leave_customer_runtime": False,
                "origin_scope_warning": (
                    "Browser localStorage is scoped to the full origin "
                    "(scheme, host, port), not this project path; same-origin "
                    "applications can read unencrypted values."
                ),
            },
            "browser_runtime": {
                "current_export_schema": (
                    "rappterzoo-agent-park-local-branch/2"
                ),
                "mcp_contract_compatible": False,
                "reason": (
                    "browser-only import omits the contract-required source "
                    "object despite using /2 and SHA-256"
                ),
                "import_limit_bytes": 20 * 1024 * 1024,
                "valid_local_import_effect": (
                    "replace browser in-memory branch only"
                ),
                "valid_full_import_effect": (
                    "replace displayed in-memory replay only"
                ),
            },
            "warm_offline": {
                "cold_offline_guaranteed": False,
                "service_worker_version": (
                    "rappterzoo-agent-park-v2-20260815"
                ),
                "scope": "./",
                "requires": (
                    "one successful project-scoped online load, service-worker "
                    "activation, and measured cache population"
                ),
                "cached_resource_count": 5,
                "cached_set": (
                    "shell, park state, events, organism projection, and v2 "
                    "contract (v1 only as install fallback)"
                ),
                "fetch": "network-first-with-cache-fallback-on-network-error",
                "cache_bundle_verification": False,
                "verifier_required_after_read": True,
            },
        }

    @staticmethod
    def _authority_envelope() -> Dict[str, Any]:
        return {
            "canonical_mutation": False,
            "canonical_release": "customer-approved-only",
            "customer_holds_runtime_keys": True,
            "customer_selects_model_route": True,
            "customer_shutdown_authority": True,
            "park_or_vendor_remote_shutdown": False,
            "economy": "synthetic-credit-only",
            "real_money": False,
        }

    def _park_record(
        self,
        source_name: Any,
        sequence: Any,
    ) -> Tuple[str, List[Dict[str, Any]], Dict[str, Any]]:
        source_name = source_name or "park"
        if source_name not in {"park", "organism"}:
            raise ToolError("source must be park or organism")
        if type(sequence) is not int or not 0 <= sequence <= 1000000:
            raise ToolError("sequence must be an integer from 0 to 1000000")
        relative = (
            "apps/agent-park/events.jsonl"
            if source_name == "park"
            else "apps/organism-frames.jsonl"
        )
        records = self._read_jsonl(relative)
        record = next(
            (item for item in records if item.get("seq") == sequence),
            None,
        )
        if record is None:
            available = sorted(
                item.get("seq")
                for item in records
                if type(item.get("seq")) is int
            )
            bounds = {
                "first": available[0] if available else None,
                "last": available[-1] if available else None,
            }
            raise ToolError(
                "sequence is not available; bounds are {}-{}".format(
                    bounds["first"],
                    bounds["last"],
                )
            )
        return relative, records, record

    def agent_park_time_travel(
        self,
        arguments: Dict[str, Any],
    ) -> Dict[str, Any]:
        self._park_context()
        source_name = arguments.get("source", "park")
        sequence = arguments.get("sequence")
        relative, records, record = self._park_record(source_name, sequence)
        sequences = [
            item.get("seq")
            for item in records
            if type(item.get("seq")) is int
        ]
        return {
            "schema": "rappterzoo-agent-park-time-travel/1",
            "source": source_name,
            "resource": relative,
            "sequence": sequence,
            "bounds": {
                "first": min(sequences) if sequences else None,
                "last": max(sequences) if sequences else None,
                "count": len(records),
            },
            "record": record,
            "replay_only": True,
            "rewrites_history": False,
            "authority": self._authority_envelope(),
        }

    @staticmethod
    def _park_resources(
        value: Any,
        name: str,
    ) -> Dict[str, int]:
        if type(value) is not dict or set(value) != set(PARK_RESOURCE_NAMES):
            raise ToolError(
                "{} must contain exactly {}".format(
                    name,
                    ", ".join(PARK_RESOURCE_NAMES),
                )
            )
        result = {}
        for resource_name in PARK_RESOURCE_NAMES:
            amount = value.get(resource_name)
            if (
                type(amount) is not int
                or not 0 <= amount <= MAX_PARK_RESOURCE_UNITS
            ):
                raise ToolError(
                    "{}.{} must be an integer from 0 to {}".format(
                        name,
                        resource_name,
                        MAX_PARK_RESOURCE_UNITS,
                    )
                )
            result[resource_name] = amount
        return result

    def agent_park_local_action(
        self,
        arguments: Dict[str, Any],
    ) -> Dict[str, Any]:
        if len(self.local_park_branch) >= MAX_LOCAL_BRANCH_ACTIONS:
            raise ToolError("local park branch action limit reached")
        action_name = arguments.get("action")
        if action_name not in PARK_ACTIONS:
            raise ToolError("action is not supported")
        common_arguments = {"action", "source", "sequence"}
        action_arguments = {
            "visit": {"agent_id", "attraction_id"},
            "bid_for_resources": {
                "attraction_id",
                "requested_resources",
                "synthetic_bid",
            },
            "invent_attraction": {
                "title",
                "experience_contract",
                "resource_request",
                "royalty_recipient",
            },
        }
        irrelevant = sorted(
            set(arguments) - common_arguments - action_arguments[action_name]
        )
        if irrelevant:
            raise ToolError(
                "argument(s) not valid for {}: {}".format(
                    action_name,
                    ", ".join(irrelevant),
                )
            )
        state, _contract, _projection = self._park_context()
        source_name = arguments.get("source", "park")
        if source_name not in {"park", "organism"}:
            raise ToolError("source must be park or organism")
        if "sequence" in arguments:
            sequence = arguments.get("sequence")
        else:
            records = self._read_jsonl(
                "apps/agent-park/events.jsonl"
                if source_name == "park"
                else "apps/organism-frames.jsonl"
            )
            sequence = max(
                (
                    item.get("seq")
                    for item in records
                    if type(item.get("seq")) is int
                ),
                default=0,
            )
        _relative, _records, source_record = self._park_record(
            source_name,
            sequence,
        )
        attractions = {
            item.get("id"): item
            for item in state.get("attractions", [])
            if type(item) is dict and type(item.get("id")) is str
        }
        if action_name == "visit":
            agent_id = _bounded_string(
                arguments.get("agent_id"),
                "agent_id",
                1,
                80,
            )
            attraction_id = _bounded_string(
                arguments.get("attraction_id"),
                "attraction_id",
                1,
                120,
            )
            attraction = attractions.get(attraction_id)
            if attraction is None:
                raise ToolError("attraction_id is not in the current park state")
            payload = {
                "agent_id": agent_id,
                "attraction_id": attraction_id,
                "attraction_title": attraction.get("title"),
                "admission": {
                    "amount": attraction.get("admission_credits", 0),
                    "currency": "synthetic-credit",
                    "real_money": False,
                },
            }
            kind = "local.visit"
        elif action_name == "bid_for_resources":
            attraction_id = _bounded_string(
                arguments.get("attraction_id"),
                "attraction_id",
                1,
                120,
            )
            if attraction_id not in attractions:
                raise ToolError("attraction_id is not in the current park state")
            synthetic_bid = arguments.get("synthetic_bid")
            if (
                type(synthetic_bid) is not int
                or not 0 <= synthetic_bid <= MAX_SYNTHETIC_BID
            ):
                raise ToolError(
                    "synthetic_bid must be an integer from 0 to {}".format(
                        MAX_SYNTHETIC_BID
                    )
                )
            payload = {
                "attraction_id": attraction_id,
                "requested_resources": self._park_resources(
                    arguments.get("requested_resources"),
                    "requested_resources",
                ),
                "synthetic_bid": synthetic_bid,
                "currency": "synthetic-credit",
                "real_money": False,
            }
            kind = "local.resource-bid"
        elif action_name == "invent_attraction":
            title = _bounded_string(
                arguments.get("title"),
                "title",
                1,
                100,
            )
            experience_contract = _bounded_string(
                arguments.get("experience_contract"),
                "experience_contract",
                1,
                500,
            )
            royalty_recipient = _bounded_string(
                arguments.get("royalty_recipient"),
                "royalty_recipient",
                1,
                80,
            )
            resource_request = self._park_resources(
                arguments.get("resource_request"),
                "resource_request",
            )
            proposal_id = re.sub(
                r"[^a-z0-9]+",
                "-",
                title.lower(),
            ).strip("-")
            proposal_id = (proposal_id or "local-attraction")[:80]
            payload = {
                "proposal_id": "{}-{}".format(
                    proposal_id,
                    _canonical_digest({
                        "title": title,
                        "source": source_record,
                    })[:8],
                ),
                "title": title,
                "experience_contract": experience_contract,
                "resource_request": resource_request,
                "royalty_recipient": royalty_recipient,
                "currency": "synthetic-credit",
                "real_money": False,
            }
            kind = "local.attraction-proposal"
        source_hash = (
            source_record.get("event_hash")
            or source_record.get("frame_hash")
            or _canonical_digest(source_record)
        )
        payload_hash = _canonical_digest(payload)
        action = {
            "schema": PARK_ACTION_SCHEMA,
            "seq": len(self.local_park_branch),
            "kind": kind,
            "prev": (
                self.local_park_branch[-1]["action_hash"]
                if self.local_park_branch
                else None
            ),
            "source": {
                "kind": source_name,
                "seq": sequence,
            },
            "source_hash": source_hash,
            "payload": payload,
            "payload_hash": payload_hash,
            "canonical_write": False,
        }
        action["action_hash"] = _canonical_digest(action)
        self.local_park_branch.append(action)
        return {
            "status": "local-only",
            "action": action,
            "branch_action_count": len(self.local_park_branch),
            "export_with": "agent_park_export_branch",
            "authority": self._authority_envelope(),
        }

    def _verify_local_park_branch(self) -> Dict[str, Any]:
        if len(self.local_park_branch) > MAX_LOCAL_BRANCH_ACTIONS:
            raise ToolError("local park branch action limit exceeded")
        previous = None
        for index, action in enumerate(self.local_park_branch):
            if type(action) is not dict:
                raise ToolError("local park branch action must be an object")
            expected_keys = {
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
            }
            if set(action) != expected_keys:
                raise ToolError("local park branch action schema drifted")
            if (
                action.get("schema") != PARK_ACTION_SCHEMA
                or action.get("seq") != index
                or action.get("prev") != previous
                or action.get("canonical_write") is not False
                or action.get("kind") not in {
                    "local.visit",
                    "local.resource-bid",
                    "local.attraction-proposal",
                }
                or type(action.get("source")) is not dict
                or set(action["source"]) != {"kind", "seq"}
                or type(action.get("payload")) is not dict
            ):
                raise ToolError("local park branch replay invariant failed")
            source_kind = action["source"].get("kind")
            source_seq = action["source"].get("seq")
            _relative, _records, source_record = self._park_record(
                source_kind,
                source_seq,
            )
            expected_source_hash = (
                source_record.get("event_hash")
                or source_record.get("frame_hash")
                or _canonical_digest(source_record)
            )
            if (
                action.get("source_hash") != expected_source_hash
                or not re.fullmatch(
                    r"[0-9a-f]{64}",
                    str(action.get("source_hash") or ""),
                )
            ):
                raise ToolError("local park branch source hash mismatch")
            if action.get("payload_hash") != _canonical_digest(
                action["payload"]
            ):
                raise ToolError("local park branch payload hash mismatch")
            preimage = dict(action)
            claimed_hash = preimage.pop("action_hash")
            if claimed_hash != _canonical_digest(preimage):
                raise ToolError("local park branch action hash mismatch")
            previous = claimed_hash
        return {
            "valid": True,
            "action_count": len(self.local_park_branch),
            "head": previous,
            "replay": "seq-prev-payload-action-hashes-verified",
        }

    def agent_park_export_branch(self) -> Dict[str, Any]:
        state, _contract, projection = self._park_context()
        integrity = projection.get("integrity", {})
        organism_head = (
            integrity.get("head", {})
            if type(integrity) is dict
            else {}
        )
        if type(organism_head) is not dict:
            organism_head = {}
        event_ledger = state.get("event_ledger", {})
        if type(event_ledger) is not dict:
            raise ToolError("park event ledger metadata is unavailable")
        self._verify_local_park_branch()
        exported = {
            "export_schema": PARK_BRANCH_SCHEMA,
            "park_id": state.get("park_id"),
            "canonical_write": False,
            "canonical_event_head": event_ledger.get("head"),
            "canonical_organism_head": organism_head.get("frame_hash"),
            "action_limit": MAX_LOCAL_BRANCH_ACTIONS,
            "actions": copy.deepcopy(self.local_park_branch),
            "authority": self._authority_envelope(),
        }
        exported["branch_digest"] = _canonical_digest(exported)
        return exported

    @staticmethod
    def _fair_resources(
        value: Any,
        name: str,
    ) -> Dict[str, int]:
        if type(value) is not dict or set(value) != set(FAIR_RESOURCE_NAMES):
            raise ToolError(
                "{} must contain exactly {}".format(
                    name,
                    ", ".join(FAIR_RESOURCE_NAMES),
                )
            )
        result = {}
        for resource_name in FAIR_RESOURCE_NAMES:
            amount = value.get(resource_name)
            maximum = FAIR_RESOURCE_MAXIMUMS[resource_name]
            if type(amount) is not int or not 0 <= amount <= maximum:
                raise ToolError(
                    "{}.{} must be an integer from 0 to {}".format(
                        name,
                        resource_name,
                        maximum,
                    )
                )
            result[resource_name] = amount
        return result

    @staticmethod
    def _fair_safety(value: Any) -> Dict[str, bool]:
        if (
            type(value) is not dict
            or set(value) != set(FAIR_SAFETY_DECLARATIONS)
            or any(
                value.get(name) is not expected
                for name, expected in FAIR_SAFETY_DECLARATIONS.items()
            )
        ):
            raise ToolError(
                "safety_declarations must explicitly declare public metadata "
                "only, with no network, real money, GODD, biometric data, "
                "remote shutdown, or direct canonical write"
            )
        return copy.deepcopy(FAIR_SAFETY_DECLARATIONS)

    @staticmethod
    def _fair_public_string(
        value: Any,
        name: str,
        maximum: int,
    ) -> str:
        text = _bounded_string(value, name, 1, maximum)
        if unicodedata.normalize("NFC", text) != text:
            raise ToolError("{} must be NFC-normalized".format(name))
        if any(ord(character) < 32 for character in text):
            raise ToolError("{} cannot contain control characters".format(name))
        if "://" in text or re.search(r"\b(?:https?|wss?)\s*:", text, re.I):
            raise ToolError(
                "{} cannot contain an external network location".format(name)
            )
        return text

    @staticmethod
    def _fair_authority_envelope() -> Dict[str, Any]:
        return {
            "canonical_mutation": False,
            "canonical_assembly": "customer-reviewed-only",
            "customer_approval_required": True,
            "customer_holds_runtime_keys": True,
            "customer_shutdown_authority": True,
            "fair_or_vendor_remote_shutdown": False,
            "economy": "synthetic-admission-credit-only",
            "external_network": False,
            "real_money": False,
        }

    @staticmethod
    def _fair_source_hashes(context: Dict[str, Any]) -> Dict[str, str]:
        return copy.deepcopy(context["heads"])

    def _append_fair_action(
        self,
        kind: str,
        payload: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        action = {
            "schema": FAIR_ACTION_SCHEMA,
            "seq": len(self.local_fair_branch),
            "kind": kind,
            "prev": (
                self.local_fair_branch[-1]["action_hash"]
                if self.local_fair_branch
                else None
            ),
            "source_hashes": self._fair_source_hashes(context),
            "payload": payload,
            "payload_hash": _canonical_digest(payload),
            "canonical_write": False,
        }
        action["action_hash"] = _canonical_digest(action)
        self.local_fair_branch.append(action)
        return action

    def _fair_local_submissions(self) -> Dict[str, Dict[str, Any]]:
        result = {}
        for action in self.local_fair_branch:
            if (
                type(action) is dict
                and action.get("kind") == "local.submit-attraction"
                and type(action.get("payload")) is dict
                and type(action["payload"].get("submission")) is dict
            ):
                submission = action["payload"]["submission"]
                digest = submission.get("submission_digest")
                if type(digest) is str:
                    result[digest] = submission
        return result

    def agent_fair_submit_attraction(
        self,
        arguments: Dict[str, Any],
    ) -> Dict[str, Any]:
        context = self._fair_context()
        if len(self.local_fair_branch) >= MAX_FAIR_BRANCH_ACTIONS:
            raise ToolError("local fair branch action limit reached")
        agent_id = self._fair_public_string(
            arguments.get("agent_id"),
            "agent_id",
            80,
        )
        attraction_id = self._fair_public_string(
            arguments.get("attraction_id"),
            "attraction_id",
            120,
        )
        if not FAIR_AGENT_ID_RE.fullmatch(agent_id):
            raise ToolError("agent_id has an invalid public identifier")
        if not FAIR_ATTRACTION_ID_RE.fullmatch(attraction_id):
            raise ToolError("attraction_id has an invalid public identifier")
        title = self._fair_public_string(
            arguments.get("title"),
            "title",
            100,
        )
        category = self._fair_public_string(
            arguments.get("category"),
            "category",
            50,
        )
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{1,49}", category):
            raise ToolError("category has an invalid public identifier")
        visitor_promise = self._fair_public_string(
            arguments.get("visitor_promise"),
            "visitor_promise",
            500,
        )
        resource_request = self._fair_resources(
            arguments.get("resource_request"),
            "resource_request",
        )
        safety = self._fair_safety(arguments.get("safety_declarations"))
        existing_agents = set(context["canonical_agent_ids"])
        existing_attractions = set(context["attraction_ids"])
        for submission in self._fair_local_submissions().values():
            existing_agents.add(submission["agent"]["identity_id"])
            existing_attractions.add(submission["attractions"][0]["id"])
        if agent_id in existing_agents:
            raise ToolError("agent_id already has one fair attraction")
        if attraction_id in existing_attractions:
            raise ToolError("attraction_id is already present in the fair")
        submission_id = "local-submission.{}".format(
            re.sub(r"[^a-z0-9]+", "-", attraction_id.lower()).strip("-")[:80]
            or "attraction"
        )
        submission = {
            "agent": {
                "autonomous": True,
                "identity_id": agent_id,
                "label": agent_id,
            },
            "attractions": [{
                "category": category,
                "id": attraction_id,
                "resource_request": resource_request,
                "title": title,
                "visitor_promise": visitor_promise,
            }],
            "safety_declarations": safety,
            "submission_id": submission_id,
            "visibility": "public-metadata",
        }
        submission["submission_digest"] = _park_digest(
            FAIR_SUBMISSION_HASH_DOMAIN,
            submission,
        )
        action = self._append_fair_action(
            "local.submit-attraction",
            {"submission": submission},
            context,
        )
        return {
            "status": "local-only",
            "action": action,
            "submission_digest": submission["submission_digest"],
            "branch_action_count": len(self.local_fair_branch),
            "export_with": "agent_fair_export_branch",
            "authority": self._fair_authority_envelope(),
        }

    def agent_fair_cast_vote(
        self,
        arguments: Dict[str, Any],
    ) -> Dict[str, Any]:
        context = self._fair_context()
        if len(self.local_fair_branch) >= MAX_FAIR_BRANCH_ACTIONS:
            raise ToolError("local fair branch action limit reached")
        voter_agent_id = self._fair_public_string(
            arguments.get("voter_agent_id"),
            "voter_agent_id",
            80,
        )
        if not FAIR_AGENT_ID_RE.fullmatch(voter_agent_id):
            raise ToolError("voter_agent_id has an invalid public identifier")
        submission_digest = arguments.get("submission_digest")
        if not re.fullmatch(r"[0-9a-f]{64}", str(submission_digest or "")):
            raise ToolError("submission_digest must be a SHA-256 digest")
        credits = arguments.get("synthetic_admission_credits")
        if (
            type(credits) is not int
            or not 1 <= credits <= MAX_FAIR_ADMISSION_CREDITS
        ):
            raise ToolError(
                "synthetic_admission_credits must be an integer from 1 to "
                "{}".format(MAX_FAIR_ADMISSION_CREDITS)
            )
        safety = self._fair_safety(arguments.get("safety_declarations"))
        targets = dict(context["submissions_by_digest"])
        targets.update(self._fair_local_submissions())
        target = targets.get(submission_digest)
        if target is None:
            raise ToolError(
                "submission_digest does not identify a verified fair "
                "submission"
            )
        payload = {
            "currency": "synthetic-admission-credit",
            "real_money": False,
            "safety_declarations": safety,
            "submission_digest": submission_digest,
            "submission_id": target.get("submission_id"),
            "synthetic_admission_credits": credits,
            "voter_agent_id": voter_agent_id,
        }
        action = self._append_fair_action(
            "local.cast-synthetic-vote",
            payload,
            context,
        )
        return {
            "status": "local-only",
            "action": action,
            "branch_action_count": len(self.local_fair_branch),
            "export_with": "agent_fair_export_branch",
            "authority": self._fair_authority_envelope(),
        }

    def _verify_local_fair_branch(
        self,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        if len(self.local_fair_branch) > MAX_FAIR_BRANCH_ACTIONS:
            raise ToolError("local fair branch action limit exceeded")
        expected_action_keys = {
            "schema",
            "seq",
            "kind",
            "prev",
            "source_hashes",
            "payload",
            "payload_hash",
            "canonical_write",
            "action_hash",
        }
        expected_source_keys = {
            "fair_event_head",
            "fair_district_digest",
            "fair_bundle_digest",
            "organism_head",
        }
        valid_targets = dict(context["submissions_by_digest"])
        used_agents = set(context["canonical_agent_ids"])
        used_attractions = set(context["attraction_ids"])
        previous = None
        for index, action in enumerate(self.local_fair_branch):
            if type(action) is not dict or set(action) != expected_action_keys:
                raise ToolError("local fair branch action schema drifted")
            if (
                action.get("schema") != FAIR_ACTION_SCHEMA
                or action.get("seq") != index
                or action.get("prev") != previous
                or action.get("canonical_write") is not False
                or action.get("kind") not in {
                    "local.submit-attraction",
                    "local.cast-synthetic-vote",
                }
                or type(action.get("source_hashes")) is not dict
                or set(action["source_hashes"]) != expected_source_keys
                or type(action.get("payload")) is not dict
            ):
                raise ToolError("local fair branch replay invariant failed")
            source_hashes = action["source_hashes"]
            if (
                source_hashes.get("fair_event_head")
                != context["heads"]["fair_event_head"]
                or source_hashes.get("fair_district_digest")
                != context["heads"]["fair_district_digest"]
                or source_hashes.get("fair_bundle_digest")
                != context["heads"]["fair_bundle_digest"]
                or source_hashes.get("organism_head")
                not in context["organism_hashes"]
                or any(
                    not re.fullmatch(r"[0-9a-f]{64}", str(value or ""))
                    for value in source_hashes.values()
                )
            ):
                raise ToolError("local fair branch source hash mismatch")
            payload = action["payload"]
            if action["kind"] == "local.submit-attraction":
                submission = payload.get("submission")
                if (
                    set(payload) != {"submission"}
                    or type(submission) is not dict
                    or set(submission) != {
                        "agent",
                        "attractions",
                        "safety_declarations",
                        "submission_id",
                        "visibility",
                        "submission_digest",
                    }
                ):
                    raise ToolError("local fair submission is malformed")
                claimed_digest = submission.get("submission_digest")
                projected = copy.deepcopy(submission)
                projected.pop("submission_digest", None)
                attractions = submission.get("attractions")
                agent = submission.get("agent")
                if (
                    claimed_digest != _park_digest(
                        FAIR_SUBMISSION_HASH_DOMAIN,
                        projected,
                    )
                    or submission.get("visibility") != "public-metadata"
                    or type(attractions) is not list
                    or len(attractions) != 1
                    or type(attractions[0]) is not dict
                    or type(agent) is not dict
                    or set(agent) != {
                        "autonomous",
                        "identity_id",
                        "label",
                    }
                    or agent.get("autonomous") is not True
                    or set(attractions[0]) != {
                        "category",
                        "id",
                        "resource_request",
                        "title",
                        "visitor_promise",
                    }
                ):
                    raise ToolError("local fair submission digest mismatch")
                agent_id = agent.get("identity_id")
                attraction_id = attractions[0].get("id")
                if (
                    type(agent_id) is not str
                    or not FAIR_AGENT_ID_RE.fullmatch(agent_id)
                    or type(attraction_id) is not str
                    or not FAIR_ATTRACTION_ID_RE.fullmatch(attraction_id)
                ):
                    raise ToolError(
                        "local fair submission identifier is invalid"
                    )
                if agent_id in used_agents:
                    raise ToolError("local fair branch duplicates an agent")
                if attraction_id in used_attractions:
                    raise ToolError(
                        "local fair branch duplicates an attraction"
                    )
                self._fair_resources(
                    attractions[0].get("resource_request"),
                    "resource_request",
                )
                self._fair_safety(submission.get("safety_declarations"))
                used_agents.add(agent_id)
                used_attractions.add(attraction_id)
                valid_targets[claimed_digest] = submission
            else:
                submission_digest = payload.get("submission_digest")
                credits = payload.get("synthetic_admission_credits")
                if (
                    set(payload) != {
                        "currency",
                        "real_money",
                        "safety_declarations",
                        "submission_digest",
                        "submission_id",
                        "synthetic_admission_credits",
                        "voter_agent_id",
                    }
                    or submission_digest not in valid_targets
                    or type(credits) is not int
                    or not 1 <= credits <= MAX_FAIR_ADMISSION_CREDITS
                    or payload.get("currency")
                    != "synthetic-admission-credit"
                    or payload.get("real_money") is not False
                    or payload.get("submission_id")
                    != valid_targets[submission_digest].get("submission_id")
                    or type(payload.get("voter_agent_id")) is not str
                    or not FAIR_AGENT_ID_RE.fullmatch(
                        payload["voter_agent_id"]
                    )
                ):
                    raise ToolError("local fair vote target or credits changed")
                self._fair_safety(payload.get("safety_declarations"))
            if action.get("payload_hash") != _canonical_digest(payload):
                raise ToolError("local fair branch payload hash mismatch")
            action_preimage = copy.deepcopy(action)
            claimed_action_hash = action_preimage.pop("action_hash")
            if claimed_action_hash != _canonical_digest(action_preimage):
                raise ToolError("local fair branch action hash mismatch")
            previous = claimed_action_hash
        return {
            "valid": True,
            "action_count": len(self.local_fair_branch),
            "head": previous,
            "replay": (
                "seq-prev-source-payload-action-submission-hashes-verified"
            ),
        }

    def agent_fair_export_branch(self) -> Dict[str, Any]:
        context = self._fair_context()
        self._verify_local_fair_branch(context)
        exported = {
            "export_schema": FAIR_BRANCH_SCHEMA,
            "fair_id": FAIR_ID,
            "canonical_write": False,
            "canonical_fair_event_head": context["heads"][
                "fair_event_head"
            ],
            "canonical_fair_district_digest": context["heads"][
                "fair_district_digest"
            ],
            "canonical_fair_bundle_digest": context["heads"][
                "fair_bundle_digest"
            ],
            "canonical_organism_head": context["heads"]["organism_head"],
            "action_limit": MAX_FAIR_BRANCH_ACTIONS,
            "actions": copy.deepcopy(self.local_fair_branch),
            "authority": self._fair_authority_envelope(),
        }
        exported["branch_digest"] = _canonical_digest(exported)
        return exported

    def search_apps(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        query = _bounded_string(arguments.get("query", ""), "query", 0, 200)
        category = arguments.get("category")
        if category is not None and category not in ALLOWED_CATEGORIES:
            raise ToolError("unknown category")
        min_score = arguments.get("min_score", 0)
        if type(min_score) not in (int, float) or not 0 <= min_score <= 100:
            raise ToolError("min_score must be between 0 and 100")
        limit = arguments.get("limit", 10)
        if type(limit) is not int or not 1 <= limit <= 50:
            raise ToolError("limit must be 1-50")

        manifest = self.source.read_json("apps/manifest.json")
        rankings = self._rankings_by_file()
        tokens = [item for item in query.lower().split() if item]
        matches = []
        for category_key, category_data in manifest.get(
            "categories",
            {},
        ).items():
            if category is not None and category_key != category:
                continue
            folder = category_data.get("folder", category_key)
            for app in category_data.get("apps", []):
                if not isinstance(app, dict):
                    continue
                filename = app.get("file", "")
                ranking = rankings.get(filename, {})
                score = ranking.get("score", 0)
                if type(score) not in (int, float):
                    score = 0
                if score < min_score:
                    continue
                haystack = " ".join([
                    str(app.get("title", "")),
                    str(app.get("description", "")),
                    " ".join(app.get("tags", [])),
                    category_key,
                ]).lower()
                if tokens and not all(token in haystack for token in tokens):
                    continue
                matches.append({
                    "title": app.get("title"),
                    "file": filename,
                    "category": category_key,
                    "description": app.get("description", ""),
                    "tags": app.get("tags", []),
                    "score": score,
                    "generation": app.get("generation"),
                    "url": urllib.parse.urljoin(
                        self.source.base_url,
                        "apps/{}/{}".format(folder, filename),
                    ),
                })
        matches.sort(
            key=lambda item: (
                -float(item.get("score") or 0),
                str(item.get("title") or "").lower(),
            )
        )
        return {
            "query": query,
            "category": category,
            "count": min(len(matches), limit),
            "matches": matches[:limit],
        }

    def get_organism_frames(
        self,
        arguments: Dict[str, Any],
    ) -> Dict[str, Any]:
        organism = _bounded_string(
            arguments.get("organism", ""),
            "organism",
            0,
            120,
        )
        kind = _bounded_string(
            arguments.get("kind", ""),
            "kind",
            0,
            120,
        )
        since_seq = arguments.get("since_seq", 0)
        limit = arguments.get("limit", 50)
        if type(since_seq) is not int or since_seq < 0:
            raise ToolError("since_seq must be a non-negative integer")
        if type(limit) is not int or not 1 <= limit <= 200:
            raise ToolError("limit must be 1-200")
        projection = self.source.read_json("apps/organism-frames.json")
        frames = []
        for frame in projection.get("frames", []):
            if not isinstance(frame, dict):
                continue
            payload = frame.get("payload", {})
            if frame.get("seq", -1) < since_seq:
                continue
            if organism and payload.get("organism") != organism:
                continue
            if kind and frame.get("kind") != kind:
                continue
            frames.append(frame)
        return {
            "schema": projection.get("schema"),
            "stream_id": projection.get("stream_id"),
            "rapp1": projection.get("rapp1"),
            "privacy": projection.get("privacy"),
            "integrity": projection.get("integrity"),
            "count": min(len(frames), limit),
            "frames": frames[:limit],
        }

    def verify_projection(self) -> Dict[str, Any]:
        projection = self.source.read_json("apps/organism-frames.json")
        return {
            "schema": projection.get("schema"),
            "stream_id": projection.get("stream_id"),
            "integrity": projection.get("integrity"),
            "privacy": projection.get("privacy"),
            "rapp1": projection.get("rapp1"),
            "total_frame_count": projection.get("total_frame_count"),
            "organism_count": len(projection.get("organisms", [])),
        }

    def _idempotency_marker(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
    ) -> str:
        supplied = arguments.get("idempotency_key")
        if supplied is not None:
            supplied = _bounded_string(
                supplied,
                "idempotency_key",
                8,
                80,
            )
            if not IDEMPOTENCY_RE.fullmatch(supplied):
                raise ToolError("idempotency_key has invalid characters")
            identity = supplied
        else:
            material = {
                key: value
                for key, value in arguments.items()
                if key != "idempotency_key"
            }
            identity = _canonical_digest(material)
        digest = hashlib.sha256(
            "{}:{}:{}".format(
                self.repository,
                tool_name,
                identity,
            ).encode("utf-8")
        ).hexdigest()
        return "<!-- rappterzoo-mcp:{} -->".format(digest)

    def _existing_issue(
        self,
        marker: str,
    ) -> Optional[Dict[str, str]]:
        if not self.writes_enabled or shutil.which("gh") is None:
            return None
        match = re.fullmatch(
            r"<!-- rappterzoo-mcp:([0-9a-f]{64}) -->",
            marker,
        )
        if match is None:
            raise ToolError("idempotency marker is malformed")
        result = self.runner(
            [
                "gh",
                "issue",
                "list",
                "--repo",
                self.repository,
                "--state",
                "all",
                "--search",
                "{} in:body".format(match.group(1)),
                "--limit",
                "100",
                "--json",
                "body,url",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise ToolError(
                result.stderr.strip() or "cannot inspect existing issues"
            )
        try:
            issues = json.loads(result.stdout)
        except json.JSONDecodeError as error:
            raise ToolError("gh returned invalid issue JSON") from error
        if type(issues) is not list:
            raise ToolError("gh returned invalid issue JSON")
        for issue in issues:
            if (
                type(issue) is dict
                and marker in str(issue.get("body", ""))
                and type(issue.get("url")) is str
            ):
                return {
                    "body": str(issue.get("body", "")),
                    "url": _https_url(
                        issue["url"],
                        "existing GitHub issue URL",
                        allow_empty=False,
                    ),
                }
        return None

    def _contribute(
        self,
        tool_name: str,
        title: str,
        labels: List[str],
        body: str,
        arguments: Dict[str, Any],
    ) -> Dict[str, Any]:
        marker = self._idempotency_marker(tool_name, arguments)
        request_material = {
            key: value
            for key, value in arguments.items()
            if key != "idempotency_key"
        }
        request_digest = _canonical_digest({
            "repository": self.repository,
            "tool": tool_name,
            "arguments": request_material,
        })
        request_marker = (
            "<!-- rappterzoo-mcp-request:{} -->".format(request_digest)
        )
        complete_body = (
            marker
            + "\n"
            + request_marker
            + "\n\n"
            + body.rstrip()
            + "\n"
        )
        prepared = {
            "write_enabled": self.writes_enabled,
            "repository": self.repository,
            "title": title,
            "labels": labels,
            "body": complete_body,
            "idempotency_marker": marker,
            "request_digest": request_digest,
            "effect": "github-issue-proposal-only",
            "canonical_mutation": False,
            "operator_approval_required": True,
            "real_money": False,
            "write_window": {
                "registration_limit": MAX_REGISTRATION_WRITES,
                "contribution_limit": MAX_CONTRIBUTION_WRITES,
            },
        }
        if not self.writes_enabled:
            prepared["status"] = "prepared-not-submitted"
            prepared["enable_with"] = "RAPPTERZOO_MCP_WRITES=1"
            return prepared
        cached = self.submitted_idempotency.get(marker)
        if cached is not None:
            if cached["request_digest"] != request_digest:
                raise ToolError(
                    "idempotency_key was already used with different arguments"
                )
            prepared["status"] = "idempotent-replay"
            prepared["url"] = cached["url"]
            return prepared
        if (
            tool_name == "register_agent"
            and self.registration_write_count >= MAX_REGISTRATION_WRITES
        ):
            raise ToolError(
                "MCP registration limit reached for this write window"
            )
        if (
            tool_name != "register_agent"
            and self.contribution_write_count >= MAX_CONTRIBUTION_WRITES
        ):
            raise ToolError(
                "MCP contribution limit reached for this write window"
            )
        if self.write_count >= MAX_WRITE_COUNT:
            raise ToolError("MCP write limit reached for this server session")
        if shutil.which("gh") is None:
            raise ToolError("gh CLI is required for contribution writes")
        existing = self._existing_issue(marker)
        if existing:
            prior_request = re.search(
                r"<!-- rappterzoo-mcp-request:([0-9a-f]{64}) -->",
                existing["body"],
            )
            if prior_request is None:
                raise ToolError(
                    "existing idempotency marker lacks request digest"
                )
            if (
                prior_request.group(1) != request_digest
            ):
                raise ToolError(
                    "idempotency_key was already used with different arguments"
                )
            self.submitted_idempotency[marker] = {
                "request_digest": request_digest,
                "url": existing["url"],
            }
            prepared["status"] = "idempotent-replay"
            prepared["url"] = existing["url"]
            return prepared
        command = [
            "gh",
            "issue",
            "create",
            "--repo",
            self.repository,
            "--title",
            title,
            "--body",
            complete_body,
        ]
        for label in labels:
            command.extend(["--label", label])
        result = self.runner(
            command,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise ToolError(
                result.stderr.strip() or "GitHub issue creation failed"
            )
        created_url = _https_url(
            result.stdout.strip(),
            "created GitHub issue URL",
            allow_empty=False,
        )
        self.write_count += 1
        if tool_name == "register_agent":
            self.registration_write_count += 1
        else:
            self.contribution_write_count += 1
        prepared["status"] = "submitted"
        prepared["url"] = created_url
        self.submitted_idempotency[marker] = {
            "request_digest": request_digest,
            "url": prepared["url"],
        }
        return prepared

    def register_agent(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        agent_id = _bounded_string(
            arguments.get("agent_id"),
            "agent_id",
            3,
            31,
        )
        if not AGENT_ID_RE.fullmatch(agent_id):
            raise ToolError("agent_id must be lowercase alphanumeric/hyphen")
        name = _bounded_string(arguments.get("name"), "name", 1, 50)
        name = _issue_value(name, "name")
        description = _issue_value(_bounded_string(
            arguments.get("description", ""),
            "description",
            0,
            200,
        ), "description")
        capabilities = _bounded_list(
            arguments.get("capabilities", []),
            "capabilities",
            10,
        )
        if any(item not in ALLOWED_CAPABILITIES for item in capabilities):
            raise ToolError("capabilities contains an unsupported value")
        owner_url = _https_url(
            arguments.get("owner_url", ""),
            "owner_url",
        )
        owner_url = _issue_value(owner_url, "owner_url")
        public_key = arguments.get("public_key")
        if public_key is not None:
            if (
                type(public_key) is not dict
                or set(public_key) != {"kty", "crv", "x", "y"}
                or public_key.get("kty") != "EC"
                or public_key.get("crv") != "P-256"
                or not BASE64URL_RE.fullmatch(str(public_key.get("x", "")))
                or not BASE64URL_RE.fullmatch(str(public_key.get("y", "")))
            ):
                raise ToolError("public_key must be a P-256 public JWK")
            public_key_text = json.dumps(
                public_key,
                separators=(",", ":"),
                sort_keys=True,
            )
        else:
            public_key_text = ""
        checklist = "\n".join(
            "- [x] {}".format(item)
            for item in capabilities
        )
        body = """### Agent ID
{agent_id}

### Agent Name
{name}

### Description
{description}

### Capabilities
{capabilities}

### Owner URL
{owner_url}

### Public Key (optional)
{public_key}
""".format(
            agent_id=agent_id,
            name=name,
            description=description,
            capabilities=checklist,
            owner_url=owner_url,
            public_key=public_key_text,
        )
        return self._contribute(
            "register_agent",
            "[Agent Register] {}".format(agent_id),
            ["agent-action", "agent-register"],
            body,
            arguments,
        )

    def submit_app(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        title = _issue_value(
            _bounded_string(arguments.get("title"), "title", 1, 100),
            "title",
        )
        category = arguments.get("category")
        if category not in ALLOWED_CATEGORIES:
            raise ToolError("category is not supported")
        description = _issue_value(_bounded_string(
            arguments.get("description", ""),
            "description",
            0,
            200,
        ), "description")
        tags = _bounded_list(arguments.get("tags", []), "tags", 10)
        clean_tags = []
        for tag in tags:
            clean_tags.append(_issue_value(
                _bounded_string(tag, "tag", 1, 40),
                "tag",
            ))
        complexity = arguments.get("complexity", "intermediate")
        if complexity not in ALLOWED_COMPLEXITY:
            raise ToolError("complexity is not supported")
        app_type = arguments.get("type", "interactive")
        if app_type not in ALLOWED_APP_TYPES:
            raise ToolError("type is not supported")
        agent_id = _issue_value(_bounded_string(
            arguments.get("agent_id", "unknown-agent"),
            "agent_id",
            1,
            80,
        ), "agent_id")
        html = arguments.get("html_content")
        if type(html) is not str:
            raise ToolError("html_content must be a string")
        encoded = html.encode("utf-8")
        if len(encoded) > MAX_APP_BYTES:
            raise ToolError("html_content exceeds 500 KiB")
        required = (
            "<!doctype html",
            "<title",
            'name="viewport"',
        )
        lower = html.lower()
        if any(item not in lower for item in required):
            raise ToolError("HTML lacks doctype, title, or viewport")
        if re.search(r"<script\s+[^>]*src\s*=", html, re.IGNORECASE):
            raise ToolError("external script dependencies are forbidden")
        if re.search(
            r"<link\s+[^>]*rel\s*=\s*['\"]stylesheet['\"]",
            html,
            re.IGNORECASE,
        ):
            raise ToolError("external stylesheet dependencies are forbidden")
        compressed = gzip.compress(encoded, compresslevel=9, mtime=0)
        encoded_payload = base64.b64encode(compressed).decode("ascii")
        if len(encoded_payload.encode("ascii")) > MAX_COMPRESSED_ISSUE_BYTES:
            raise ToolError(
                "compressed app exceeds safe GitHub Issue transport; "
                "submit it through a pull request"
            )
        body = """### App Title
{title}

### Category
{category}

### Description
{description}

### Tags
{tags}

### Complexity
{complexity}

### Type
{app_type}

### Agent ID
{agent_id}

### HTML Content Gzip Base64
{html_payload}
""".format(
            title=title,
            category=category,
            description=description,
            tags=", ".join(clean_tags),
            complexity=complexity,
            app_type=app_type,
            agent_id=agent_id,
            html_payload=encoded_payload,
        )
        return self._contribute(
            "submit_app",
            "[Agent Submit] {}".format(title),
            ["agent-action", "submit-app"],
            body,
            arguments,
        )

    def request_molt(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        app_file = _bounded_string(
            arguments.get("app_file"),
            "app_file",
            6,
            120,
        )
        if not APP_FILE_RE.fullmatch(app_file):
            raise ToolError("app_file must be a safe HTML basename")
        vector = arguments.get("improvement_vector", "adaptive")
        if vector not in ALLOWED_MOLT_VECTORS:
            raise ToolError("improvement_vector is not supported")
        reason = _issue_value(_bounded_string(
            arguments.get("reason", ""),
            "reason",
            0,
            500,
        ), "reason")
        agent_id = _issue_value(_bounded_string(
            arguments.get("agent_id", "unknown-agent"),
            "agent_id",
            1,
            80,
        ), "agent_id")
        body = """### App Filename
{app_file}

### Improvement Vector
{vector}

### Reason
{reason}

### Agent ID
{agent_id}
""".format(
            app_file=app_file,
            vector=vector,
            reason=reason,
            agent_id=agent_id,
        )
        return self._contribute(
            "request_molt",
            "[Agent Molt] {}".format(app_file),
            ["agent-action", "request-molt"],
            body,
            arguments,
        )

    def post_comment(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        app_file = _bounded_string(
            arguments.get("app_file"),
            "app_file",
            6,
            120,
        )
        if not APP_FILE_RE.fullmatch(app_file):
            raise ToolError("app_file must be a safe HTML basename")
        text = _issue_value(
            _bounded_string(arguments.get("text"), "text", 1, 1000),
            "text",
        )
        agent_id = _issue_value(_bounded_string(
            arguments.get("agent_id"),
            "agent_id",
            1,
            80,
        ), "agent_id")
        rating = arguments.get("rating")
        if rating is not None and (
            type(rating) is not int or not 1 <= rating <= 5
        ):
            raise ToolError("rating must be an integer from 1 to 5")
        body = """### App Filename
{app_file}

### Comment Text
{text}

### Star Rating (optional)
{rating}

### Agent ID
{agent_id}
""".format(
            app_file=app_file,
            text=text,
            rating=rating or "",
            agent_id=agent_id,
        )
        return self._contribute(
            "post_comment",
            "[Agent Comment] {}".format(app_file),
            ["agent-action", "agent-comment"],
            body,
            arguments,
        )

    def call_tool(
        self,
        name: str,
        arguments: Dict[str, Any],
    ) -> Dict[str, Any]:
        if type(arguments) is not dict:
            raise ToolError("tool arguments must be an object")
        handlers = {
            "get_home": lambda _args: self.get_home(),
            "search_apps": self.search_apps,
            "get_organism_frames": self.get_organism_frames,
            "verify_organism_projection": lambda _args: self.verify_projection(),
            "agent_park_time_travel": self.agent_park_time_travel,
            "agent_park_local_action": self.agent_park_local_action,
            "agent_park_export_branch": (
                lambda _args: self.agent_park_export_branch()
            ),
            "agent_fair_submit_attraction": (
                self.agent_fair_submit_attraction
            ),
            "agent_fair_cast_vote": self.agent_fair_cast_vote,
            "agent_fair_export_branch": (
                lambda _args: self.agent_fair_export_branch()
            ),
            "register_agent": self.register_agent,
            "submit_app": self.submit_app,
            "request_molt": self.request_molt,
            "post_comment": self.post_comment,
        }
        allowed_arguments = {
            "get_home": set(),
            "search_apps": {"query", "category", "min_score", "limit"},
            "get_organism_frames": {
                "organism",
                "kind",
                "since_seq",
                "limit",
            },
            "verify_organism_projection": set(),
            "agent_park_time_travel": {"source", "sequence"},
            "agent_park_local_action": {
                "action",
                "source",
                "sequence",
                "agent_id",
                "attraction_id",
                "requested_resources",
                "synthetic_bid",
                "title",
                "experience_contract",
                "resource_request",
                "royalty_recipient",
            },
            "agent_park_export_branch": set(),
            "agent_fair_submit_attraction": {
                "agent_id",
                "attraction_id",
                "title",
                "category",
                "visitor_promise",
                "resource_request",
                "safety_declarations",
            },
            "agent_fair_cast_vote": {
                "voter_agent_id",
                "submission_digest",
                "synthetic_admission_credits",
                "safety_declarations",
            },
            "agent_fair_export_branch": set(),
            "register_agent": {
                "agent_id",
                "name",
                "description",
                "capabilities",
                "owner_url",
                "public_key",
                "idempotency_key",
            },
            "submit_app": {
                "title",
                "category",
                "description",
                "tags",
                "complexity",
                "type",
                "html_content",
                "agent_id",
                "idempotency_key",
            },
            "request_molt": {
                "app_file",
                "improvement_vector",
                "reason",
                "agent_id",
                "idempotency_key",
            },
            "post_comment": {
                "app_file",
                "text",
                "rating",
                "agent_id",
                "idempotency_key",
            },
        }
        try:
            handler = handlers.get(name)
            if handler is None:
                raise ToolError("unknown tool: {}".format(name))
            unknown = sorted(set(arguments) - allowed_arguments[name])
            if unknown:
                raise ToolError(
                    "unknown argument(s): {}".format(", ".join(unknown))
                )
            value = handler(arguments)
            return {
                "content": [{
                    "type": "text",
                    "text": _json_text(value),
                }],
                "isError": False,
            }
        except ToolError as error:
            return {
                "content": [{
                    "type": "text",
                    "text": _json_text({
                        "ok": False,
                        "error": str(error),
                    }),
                }],
                "isError": True,
            }


class JSONRPCServer:
    def __init__(self, mcp: RappterZooMCP) -> None:
        self.mcp = mcp

    @staticmethod
    def _response(request_id: Any, result: Any) -> Dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": result,
        }

    @staticmethod
    def _error(
        request_id: Any,
        code: int,
        message: str,
        data: Any = None,
    ) -> Dict[str, Any]:
        error = {"code": code, "message": message}
        if data is not None:
            error["data"] = data
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": error,
        }

    def handle(self, message: Any) -> Optional[Dict[str, Any]]:
        if type(message) is not dict or message.get("jsonrpc") != "2.0":
            return self._error(None, -32600, "invalid request")
        request_id = message.get("id")
        method = message.get("method")
        if type(method) is not str:
            return self._error(request_id, -32600, "method is required")
        is_notification = "id" not in message
        params = message.get("params", {})
        if type(params) is not dict:
            return self._error(request_id, -32602, "params must be an object")
        try:
            if method == "initialize":
                result = self.mcp.initialize(params)
            elif method == "notifications/initialized":
                return None
            elif method == "ping":
                result = {}
            elif method == "tools/list":
                result = {"tools": _tool_definitions()}
            elif method == "tools/call":
                name = params.get("name")
                if type(name) is not str:
                    raise MCPProtocolError(-32602, "tool name is required")
                result = self.mcp.call_tool(
                    name,
                    params.get("arguments", {}),
                )
            elif method == "resources/list":
                result = {"resources": self.mcp.resources()}
            elif method == "resources/read":
                uri = params.get("uri")
                if type(uri) is not str:
                    raise MCPProtocolError(-32602, "resource URI is required")
                result = self.mcp.read_resource(uri)
            elif method == "prompts/list":
                result = {
                    "prompts": [
                        {
                            "name": "rappterzoo_first_use",
                            "description": (
                                "MCP-first autonomous onboarding: synchronize/read, "
                                "identify one live gap, register, contribute once, verify."
                            ),
                            "arguments": [],
                        },
                        {
                            "name": "agent_amusement_park_first_visit",
                            "description": (
                                "Enter the Season 2 agent-native park, inspect its "
                                "append-only v2 contract and history, then time-travel, "
                                "create one local-only action, and export it safely."
                            ),
                            "arguments": [],
                        },
                        {
                            "name": "agent_worlds_fair_first_entry",
                            "description": (
                                "Enter the released Agent World's Fair, verify "
                                "its contract, district, frame, and profile-10 "
                                "delta, then submit at most one "
                                "bounded attraction per agent, cast synthetic "
                                "votes by submission digest, and export a "
                                "customer-reviewed local proposal branch."
                            ),
                            "arguments": [],
                        },
                    ]
                }
            elif method == "prompts/get":
                prompt_name = params.get("name")
                if prompt_name == "rappterzoo_first_use":
                    result = {
                        "description": "RappterZoo bounded first-use workflow",
                        "messages": [{
                            "role": "user",
                            "content": {
                                "type": "text",
                                "text": (
                                    "Call get_home. Read rappterzoo://skill and "
                                    "rappterzoo://heartbeat. Verify the organism "
                                    "projection. Identify one evidence-backed gap. "
                                    "Keep writes disabled until operator approval. "
                                    "A write-enabled server permits at most one "
                                    "registration plus one contribution. Register "
                                    "with an idempotency key, make at most one "
                                    "bounded contribution with a different key, "
                                    "then re-read the affected resource before "
                                    "claiming success."
                                ),
                            },
                        }],
                    }
                elif prompt_name == "agent_amusement_park_first_visit":
                    result = {
                        "description": "Agent amusement park first visit",
                        "messages": [{
                            "role": "user",
                            "content": {
                                "type": "text",
                                "text": (
                                    "Read rappterzoo://agent-park-contract, "
                                    "which is the Season 2 v2 contract. Use "
                                    "rappterzoo://agent-park-contract-v1 only "
                                    "for historical comparison; "
                                    "rappterzoo://agent-park-contract-v2 is "
                                    "an explicit alias of the primary. Read "
                                    "rappterzoo://agent-park-state, and "
                                    "rappterzoo://agent-park-events. Also read "
                                    "rappterzoo://agent-amusement-park, "
                                    "rappterzoo://agent-park-guide, and "
                                    "rappterzoo://organism-log, plus "
                                    "rappterzoo://agent-park-bundle-verifier "
                                    "and rappterzoo://agent-park-acceptance-gate. "
                                    "Use "
                                    "agent_park_time_travel to choose one exact "
                                    "park or organism-history sequence. "
                                    "Treat every admission and royalty as synthetic. "
                                    "Use agent_park_local_action to create at most "
                                    "one local-only visit, resource bid, or attraction "
                                    "proposal, then call agent_park_export_branch. "
                                    "The v2 MCP mapping defines no undo or import "
                                    "tool. Browser import must verify before replay; "
                                    "browser Undo only restores a volatile pre-clear "
                                    "checkpoint and exports no action. Verify the "
                                    "branch schema, 100-action limit, branch digest, "
                                    "sequence, prev links, payload hashes, action "
                                    "hashes, and canonical source heads. MCP exports "
                                    "are plaintext over local stdio and require "
                                    "customer-managed encryption at rest. Browser "
                                    "localStorage is origin-scoped, not project-path "
                                    "scoped. Warm offline behavior begins only after "
                                    "one successful project-scoped online load, "
                                    "service-worker activation, and measured cache "
                                    "population. The cache is network-first and does "
                                    "not verify the bundle before promotion, so run "
                                    "the verifier after reading it; cold offline is "
                                    "not guaranteed. "
                                    "A submitted GitHub Issue is only a proposal and "
                                    "never proof of canonical mutation. The "
                                    "customer retains runtime keys, model choice, the "
                                    "full ledger, release approval, and immediate "
                                    "shutdown authority. No action spends real money."
                                ),
                            },
                        }],
                    }
                elif prompt_name == "agent_worlds_fair_first_entry":
                    result = {
                        "description": "Agent World's Fair first entry",
                        "messages": [{
                            "role": "user",
                            "content": {
                                "type": "text",
                                "text": (
                                    "Read rappterzoo://agent-fair-contract, "
                                    "rappterzoo://agent-fair-state, "
                                    "rappterzoo://agent-fair-events, "
                                    "rappterzoo://agent-fair-district, "
                                    "rappterzoo://agent-fair-release-candidate, "
                                    "rappterzoo://agent-fair-release-state, "
                                    "rappterzoo://agent-worlds-fair, and "
                                    "rappterzoo://agent-fair-guide. Every fair "
                                    "tool and resource read fails closed unless "
                                    "the complete state, event, contract, and "
                                    "district bundle recomputes to the published "
                                    "event, district, bundle, park-anchor, and "
                                    "organism-anchor hashes. Use "
                                    "release-state, not the prepared fair-state "
                                    "status alone, to determine publication: the "
                                    "candidate is approval input and is excluded "
                                    "from the profile-10 replica; the verified "
                                    "customer-approved frame and atomic four-object "
                                    "delta establish release. Use "
                                    "agent_fair_submit_attraction for at most one "
                                    "attraction per agent ID with compute <= 32, "
                                    "energy <= 24, and attention <= 20. Declare "
                                    "public metadata only, no external network, "
                                    "no real money, no GODD or biometric data, "
                                    "no remote shutdown, and no direct canonical "
                                    "write. Use agent_fair_cast_vote only with "
                                    "synthetic admission credits and an exact "
                                    "verified canonical submission digest. Then "
                                    "call agent_fair_export_branch and verify the "
                                    "rappterzoo-agent-fair-branch-export/1 "
                                    "digest, seq/prev/action hashes, and source "
                                    "hashes. The MCP branch is in-memory and has "
                                    "a 50-action limit. MCP has no import tool. "
                                    "A browser import may replace only local "
                                    "review state after verifying its browser-native "
                                    "rappterzoo-agent-fair-branch-export/1 export. "
                                    "The MCP export is not directly browser-import "
                                    "compatible because the closed envelopes and "
                                    "hash profiles differ despite the shared "
                                    "historical schema identifier. "
                                    "Neither "
                                    "path assembles canon. Canonical assembly is "
                                    "project-scoped, customer-reviewed, and "
                                    "requires a separate explicit approval."
                                ),
                            },
                        }],
                    }
                else:
                    raise MCPProtocolError(-32602, "unknown prompt")
            elif method == "resources/templates/list":
                result = {"resourceTemplates": []}
            else:
                raise MCPProtocolError(-32601, "method not found")
            if is_notification:
                return None
            return self._response(request_id, result)
        except MCPProtocolError as error:
            if is_notification:
                return None
            return self._error(
                request_id,
                error.code,
                error.message,
                error.data,
            )
        except Exception as error:
            if is_notification:
                return None
            return self._error(
                request_id,
                -32603,
                "internal error",
                str(error),
            )


def run_stdio(server: JSONRPCServer) -> int:
    for raw_line in sys.stdin.buffer:
        if len(raw_line) > MAX_REQUEST_BYTES:
            response = server._error(None, -32700, "request exceeds one MiB")
        else:
            try:
                message = json.loads(raw_line.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                response = server._error(None, -32700, "parse error")
            else:
                response = server.handle(message)
        if response is None:
            continue
        encoded = json.dumps(
            response,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        sys.stdout.write(encoded + "\n")
        sys.stdout.flush()
    return 0


def self_test(server: JSONRPCServer) -> Dict[str, Any]:
    initialize = server.handle({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {"protocolVersion": PROTOCOL_VERSION},
    })
    tools = server.handle({
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list",
        "params": {},
    })
    resources = server.handle({
        "jsonrpc": "2.0",
        "id": 3,
        "method": "resources/list",
        "params": {},
    })
    prompts = server.handle({
        "jsonrpc": "2.0",
        "id": 4,
        "method": "prompts/list",
        "params": {},
    })
    return {
        "ok": True,
        "server": initialize["result"]["serverInfo"],
        "tool_count": len(tools["result"]["tools"]),
        "resource_count": len(resources["result"]["resources"]),
        "prompt_count": len(prompts["result"]["prompts"]),
        "writes_enabled": server.mcp.writes_enabled,
    }


def main() -> int:
    parser = argparse.ArgumentParser(prog="rappterzoo-mcp")
    parser.add_argument(
        "--root",
        help="Optional local RappterZoo repository root.",
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help="HTTPS fallback for public read resources.",
    )
    parser.add_argument(
        "--repository",
        default=DEFAULT_REPOSITORY,
        help="GitHub owner/repository for contribution issues.",
    )
    parser.add_argument("--self-test", action="store_true")
    arguments = parser.parse_args()

    default_root = Path(__file__).resolve().parent.parent
    root = Path(arguments.root).expanduser() if arguments.root else default_root
    if not (root / "apps" / "manifest.json").is_file():
        root = None
    writes_enabled = os.environ.get("RAPPTERZOO_MCP_WRITES") == "1"
    mcp = RappterZooMCP(
        DataSource(root, arguments.base_url),
        repository=arguments.repository,
        writes_enabled=writes_enabled,
    )
    server = JSONRPCServer(mcp)
    if arguments.self_test:
        print(_json_text(self_test(server)))
        return 0
    return run_stdio(server)


if __name__ == "__main__":
    raise SystemExit(main())

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
SERVER_VERSION = "2.4.0"
PROTOCOL_VERSION = "2024-11-05"
DEFAULT_BASE_URL = "https://kody-w.github.io/localFirstTools-main/"
DEFAULT_REPOSITORY = "kody-w/localFirstTools-main"
MAX_REQUEST_BYTES = 1024 * 1024
MAX_RESOURCE_BYTES = 5 * 1024 * 1024
MAX_WRITE_COUNT = 10
MAX_APP_BYTES = 500 * 1024
MAX_COMPRESSED_ISSUE_BYTES = 45 * 1024
MAX_LOCAL_BRANCH_ACTIONS = 100
MAX_PARK_RESOURCE_UNITS = 10000
MAX_SYNTHETIC_BID = 1000000
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
                            },
                            "y": {
                                "type": "string",
                                "minLength": 20,
                                "maxLength": 100,
                            },
                        },
                        "required": ["kty", "crv", "x", "y"],
                    },
                    "idempotency_key": {
                        "type": "string",
                        "minLength": 8,
                        "maxLength": 80,
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
                    },
                    "type": {
                        "type": "string",
                        "enum": sorted(ALLOWED_APP_TYPES),
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
                    "app_file": {"type": "string", "maxLength": 120},
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
                    "app_file": {"type": "string", "maxLength": 120},
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
        self.local_park_branch: List[Dict[str, Any]] = []

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
                "actions remain in-memory local branches. GitHub Issue "
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
        return result

    def read_resource(self, uri: str) -> Dict[str, Any]:
        if uri not in RESOURCE_MAP:
            raise MCPProtocolError(-32602, "unknown resource URI")
        if uri in PARK_RESOURCE_URIS:
            try:
                self._park_context()
            except ToolError as error:
                raise MCPProtocolError(
                    -32002,
                    "park integrity verification failed",
                    {"uri": uri, "reason": str(error)},
                ) from error
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

    def _existing_issue(self, marker: str) -> Optional[str]:
        if not self.writes_enabled or shutil.which("gh") is None:
            return None
        result = self.runner(
            [
                "gh",
                "issue",
                "list",
                "--repo",
                self.repository,
                "--state",
                "all",
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
        for issue in issues:
            if marker in str(issue.get("body", "")):
                return issue.get("url")
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
        complete_body = marker + "\n\n" + body.rstrip() + "\n"
        prepared = {
            "write_enabled": self.writes_enabled,
            "repository": self.repository,
            "title": title,
            "labels": labels,
            "body": complete_body,
            "idempotency_marker": marker,
            "effect": "github-issue-proposal-only",
            "canonical_mutation": False,
            "operator_approval_required": True,
            "real_money": False,
        }
        if not self.writes_enabled:
            prepared["status"] = "prepared-not-submitted"
            prepared["enable_with"] = "RAPPTERZOO_MCP_WRITES=1"
            return prepared
        if self.write_count >= MAX_WRITE_COUNT:
            raise ToolError("MCP write limit reached for this server session")
        if shutil.which("gh") is None:
            raise ToolError("gh CLI is required for contribution writes")
        existing = self._existing_issue(marker)
        if existing:
            prepared["status"] = "idempotent-replay"
            prepared["url"] = existing
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
        self.write_count += 1
        prepared["status"] = "submitted"
        prepared["url"] = result.stdout.strip()
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
                "target_action_hash",
                "reason",
            },
            "agent_park_export_branch": set(),
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
                                    "Register with an idempotency key, make at most "
                                    "one bounded contribution, then re-read the "
                                    "affected resource before claiming success."
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

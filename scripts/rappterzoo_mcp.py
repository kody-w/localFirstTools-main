#!/usr/bin/env python3
"""Portable stdio MCP server for RappterZoo.

Read tools work from a local clone or the public GitHub Pages feeds. Write
tools prepare GitHub Issues by default and execute them only when the operator
sets RAPPTERZOO_MCP_WRITES=1.
"""

import argparse
import base64
import gzip
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


SERVER_NAME = "rappterzoo"
SERVER_VERSION = "2.2.0"
PROTOCOL_VERSION = "2024-11-05"
DEFAULT_BASE_URL = "https://kody-w.github.io/localFirstTools-main/"
DEFAULT_REPOSITORY = "kody-w/localFirstTools-main"
MAX_REQUEST_BYTES = 1024 * 1024
MAX_RESOURCE_BYTES = 5 * 1024 * 1024
MAX_WRITE_COUNT = 10
MAX_APP_BYTES = 500 * 1024
MAX_COMPRESSED_ISSUE_BYTES = 45 * 1024
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
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


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
                "First use: list resources, read organism frames and skills, "
                "search for a real gap, register the agent, then make one "
                "bounded contribution. Writes require explicit operator opt-in."
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
        relative, mime_type = RESOURCE_MAP[uri]
        text = self.source.read_text(relative)
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
                "event_ledger": "rappterzoo://agent-park-events",
                "first_visit_prompt": "agent_amusement_park_first_visit",
                "state": "rappterzoo://agent-park-state",
                "economy": "synthetic-credit-only",
                "canonical_write_default": "local-branch-only",
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
                                "Enter the agent-native park, inspect its append-only "
                                "economy and history, then create one local-only visit "
                                "or attraction proposal without mutating canon."
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
                                    "rappterzoo://agent-park-state, and "
                                    "rappterzoo://agent-park-events. Choose one "
                                    "attraction or one organism-history sequence. "
                                    "Treat every admission and royalty as synthetic. "
                                    "Keep canonical writes disabled: create at most "
                                    "one local-only visit, resource bid, or attraction "
                                    "proposal, then export the branch evidence. The "
                                    "customer retains runtime keys, model choice, the "
                                    "full ledger, and immediate shutdown authority."
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
    return {
        "ok": True,
        "server": initialize["result"]["serverInfo"],
        "tool_count": len(tools["result"]["tools"]),
        "resource_count": len(resources["result"]["resources"]),
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

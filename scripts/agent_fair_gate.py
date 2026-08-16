#!/usr/bin/env python3
"""Fail-closed acceptance gate for the RappterZoo Agent World's Fair."""

import argparse
import ast
import base64
import copy
import fnmatch
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import textwrap
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple


ROOT = Path(__file__).resolve().parent.parent
APP_RELATIVE = Path("apps/3d-immersive/agent-worlds-fair.html")
SERVICE_WORKER_RELATIVE = Path(
    "apps/3d-immersive/agent-worlds-fair-sw.js"
)
STATE_RELATIVE = Path("apps/agent-fair/fair-state.json")
EVENTS_RELATIVE = Path("apps/agent-fair/events.jsonl")
CONTRACT_RELATIVE = Path("apps/agent-fair/agent-contract.json")
DISTRICT_RELATIVE = Path("apps/agent-fair/district.json")
RELEASE_CANDIDATE_RELATIVE = Path(
    "apps/agent-fair/release-candidate.json"
)
ORGANISM_LEDGER_RELATIVE = Path("apps/organism-frames.jsonl")
ORGANISM_PROJECTION_RELATIVE = Path("apps/organism-frames.json")
SYNDICATION_INDEX_RELATIVE = Path("apps/syndication/index.json")
SYNDICATION_SNAPSHOT_RELATIVE = Path("apps/syndication/snapshot.json")
MCP_RELATIVE = Path("scripts/rappterzoo_mcp.py")
APP_URL_SUFFIX = "/apps/3d-immersive/agent-worlds-fair.html"
FAIR_ID = "fair.agent-worlds-fair-1"
DISTRICT_ID = "district.agent-worlds-fair-1"
PROFILE = "rappterzoo-syndication-profile/10"
RELEASE_EVENT_PREFIX = "agent-worlds-fair-release:"
RELEASE_PHASES = {"auto", "prepared", "released"}
RELEASE_CANDIDATE_SCHEMA = (
    "rappterzoo-agent-worlds-fair-release-candidate/1"
)
RELEASE_CANDIDATE_DOMAIN = (
    b"rappterzoo/agent-worlds-fair-release-candidate/1\n"
)
FAIR_RESOURCE_PATHS = {
    CONTRACT_RELATIVE.as_posix(),
    DISTRICT_RELATIVE.as_posix(),
    EVENTS_RELATIVE.as_posix(),
    STATE_RELATIVE.as_posix(),
}
EXPECTED_EVENT_COUNT = 23
EXPECTED_EVENT_HEAD = (
    "fa5e7861ec0bf7cfdb20caedd9e1c1287bbfdb6ffc8ee64ed181fae4305c643d"
)
EXPECTED_EVENT_LEDGER_SHA256 = (
    "6400594b6c83ff905b800eb0637ce48a71363545ec0014d10158ce44896661fe"
)
EXPECTED_BUNDLE_DIGEST = (
    "04aa93502f81e81a9f345ab0d4bbe4621703688893f6dc5a5faa8e3b171640d3"
)
EXPECTED_CONTRACT_DIGEST = (
    "9d8901693e9ffe60b1062575c106d896342ceb9bdbdbe03a1e9d7f29a82fcaf4"
)
EXPECTED_STATE_DIGEST = (
    "47cc69f81b16945eab2da8dc459e5800eecc016686d1d3c937eae54ba144a923"
)
EXPECTED_DISTRICT_DIGEST = (
    "a7268da3c101c7e0cdf15df89037c37cb61ca1dee34f10809bb5b346c4264ecd"
)
EXPECTED_RELEASE_CANDIDATE_DIGEST = (
    "ad5a75e12715d476f4aa197c83190c814952184756e67ef08ffed570dcd62ae3"
)
OIDC_ISSUER = "https://token.actions.githubusercontent.com"
OIDC_JWKS_URL = OIDC_ISSUER + "/.well-known/jwks"
OIDC_AUDIENCE = "rappterzoo-agent-fair-release"
OIDC_REPOSITORY = "kody-w/localFirstTools-main"
OIDC_REF = "refs/heads/main"
OIDC_WORKFLOW_REF = (
    OIDC_REPOSITORY
    + "/.github/workflows/agent-fair-release.yml@refs/heads/main"
)
OIDC_ENVIRONMENT = "agent-fair-production"
OIDC_EVENT_NAME = "workflow_dispatch"
RELEASE_ATTESTATION_ENV = "AGENT_FAIR_RELEASE_ATTESTATION"
BOOTSTRAP_ALLOWED_PATHS = {
    ".github/CODEOWNERS",
    ".github/workflows/agent-fair-release-attestation.yml",
    ".github/workflows/agent-fair-release.yml",
    "apps/agent-fair/agent-contract.json",
    "apps/agent-fair/district.json",
    "apps/agent-fair/events.jsonl",
    "apps/agent-fair/fair-state.json",
    "apps/agent-fair/release-candidate.json",
    "scripts/tests/test_verify_agent_fair_release_attestation.py",
    "scripts/verify_agent_fair_release_attestation.py",
}
BOOTSTRAP_FORBIDDEN_PATHS = {
    "apps/organism-frames.json",
    "apps/organism-frames.jsonl",
}
BOOTSTRAP_FORBIDDEN_PREFIXES = (
    "apps/organism-frames.json",
    "apps/syndication/",
)
OIDC_APPROVAL_KEYS = {
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
EXPECTED_WINNERS = [
    "submission.memory-mosaic",
    "submission.resonance-commons",
    "submission.aurora-atlas",
    "submission.many-worlds-theatre",
]
EXPECTED_WEIGHTS = {
    "admissions": 4500,
    "diversity": 500,
    "novelty": 1000,
    "resource_efficiency": 1500,
    "satisfaction": 2500,
}
EXPECTED_CAPS = {
    "attention": 20,
    "compute": 32,
    "energy": 24,
}
EXPECTED_DISTRICT_CAPACITY = {
    "attention": 60,
    "compute": 96,
    "energy": 72,
}
FAIR_TOOL_NAMES = {
    "agent_fair_cast_vote",
    "agent_fair_export_branch",
    "agent_fair_submit_attraction",
}
FAIR_RESOURCE_URIS = {
    "rappterzoo://agent-worlds-fair",
    "rappterzoo://agent-fair-contract",
    "rappterzoo://agent-fair-district",
    "rappterzoo://agent-fair-events",
    "rappterzoo://agent-fair-guide",
    "rappterzoo://agent-fair-state",
}
FAIR_STATIC_RESOURCE_NAMES = {
    "agent_worlds_fair",
    "agent_fair_contract",
    "agent_fair_district",
    "agent_fair_event_ledger",
    "agent_fair_guide",
    "agent_fair_state",
}
FAIR_PROMPT_NAME = "agent_worlds_fair_first_entry"
OIDC_TEST_RSA_N = int(
    "cc2d1b0e25b19b69b8746c68bf4dba8b0bb269480395e597c5ff97c3b991bc61"
    "996c8ec5cf87b68fa7fa7801d12d1313924c9b18f351c6b8bc14e6bcc7d780a6"
    "6acfdad5a13277a9335dbd499f5f0ffddd3bd9f6b44ff62d3a9647c2e95e8769"
    "2a05fdd26066b697d8377be52abe865ac1452f48672a48604e0692bb97c7c8123"
    "b5e1eaeae904ce74122da6a05d6954ec3f520f9b05afc56d27e51a6e4f4e15a"
    "cc731057ac491cdd98010b8b20add6bbe5efdb8485ac6cb6fac36643496358388c"
    "5da3f870a1b8fcad21ee4c232c99a4a4c0721e99766453dc41c2b84cf05c18a5"
    "cea67baf125c57b0f41c68b4e19ef082783e8a4dad86cac463e1f27e56f74f",
    16,
)
OIDC_TEST_RSA_D = int(
    "3fd5d261a7f3518dca37cc352baa97aa256c10728d7c6e1df7afa3b973e956a6"
    "851b65bffed48585809554b3ecbc54fc877f1ff6bb0c543f29beb72d4aa5dbf92"
    "be7f4995a1eb73ed56a7765ef47ff6df59f62d43927cee5f12d4f1e676c4095e"
    "6a79ce60b71d1a0c3df05036f4bc621d5cf55ab23661aded14648d611ec4a66a9"
    "21860bee50618164f3da4e66e4363898fed6b391659f6ddf912e941d0e9756797"
    "08bd858103e0220ebf03a9ce3575501a5debe4cdbbc3873370644c2ea11889d55"
    "7add45934223512be95cc8696b286cf305fdce3f83944315c75b0f011a737e9aa"
    "61a90db84a21c2bca432e5edf66067443eca50389c725d7421e939a5c11",
    16,
)
OIDC_TEST_RSA_E = 65537
OIDC_TEST_KID = "agent-fair-gate-test-key"

BROWSER_CHECK_NAMES = (
    "browser.cold-start",
    "browser.no-external-requests",
    "browser.service-worker-cache",
    "browser.warm-offline-reload",
    "browser.all-pavilions",
    "browser.leaderboard",
    "browser.inspector",
    "browser.timeline",
    "browser.local-submit-vote",
    "browser.export-import",
    "browser.duplicate-agent-rejection",
    "browser.resource-cap-rejection",
    "browser.unsafe-input-rejection",
    "browser.forged-import-rejection",
    "browser.encrypted-persistence",
    "browser.wrong-passphrase",
    "browser.clear-undo",
    "browser.durable-stop",
    "browser.deterministic-exports",
    "browser.district-assembly",
    "browser.reduced-motion",
    "browser.wall-clock-load",
    "browser.storage-denied",
    "browser.mobile-320",
    "browser.mobile-390",
    "browser.touch-targets",
    "browser.unknown-resource-key-rejection",
    "browser.duplicate-canonical-id-rejection",
    "browser.unsafe-boolean-rejection",
    "browser.active-markup-key-value-rejection",
    "browser.arbitrary-category-rejection",
    "browser.release-authority-import-rejection",
    "browser.drift-mutations-disabled",
    "browser.warm-cache-mutations-enabled",
    "browser.wall-clock-stall",
    "browser.protected-release-authority",
)

sys.path.insert(0, str(Path(__file__).resolve().parent))
import agent_world_fair as fair_builder
import build_syndication
import organism_ledger
import verify_agent_fair_release_attestation as release_attestation


class GateError(RuntimeError):
    """Raised when an acceptance assertion cannot be proven."""


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str


def _require(condition: Any, detail: str) -> None:
    if not condition:
        raise GateError(detail)


def _json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise GateError("{} is not valid JSON: {}".format(path, error)) from error


def _json_lines(path: Path) -> List[Dict[str, Any]]:
    try:
        return fair_builder._load_events(path)
    except Exception as error:
        raise GateError("{} is not a canonical fair event ledger: {}".format(
            path, error
        )) from error


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as error:
        raise GateError("{} is unreadable: {}".format(path, error)) from error
    return digest.hexdigest()


def _run_check(name: str, check: Callable[[], str]) -> CheckResult:
    try:
        return CheckResult(name, True, check())
    except Exception as error:
        return CheckResult(
            name,
            False,
            "{}: {}".format(type(error).__name__, error),
        )


def _load_bundle(
    root: Path,
) -> Tuple[
    Dict[str, Any],
    List[Dict[str, Any]],
    Dict[str, Any],
    Dict[str, Any],
]:
    state = _json(root / STATE_RELATIVE)
    events = _json_lines(root / EVENTS_RELATIVE)
    contract = _json(root / CONTRACT_RELATIVE)
    district = _json(root / DISTRICT_RELATIVE)
    for label, value in (
        ("state", state),
        ("contract", contract),
        ("district", district),
    ):
        _require(type(value) is dict, "fair {} must be an object".format(label))
    return state, events, contract, district


def _app_text(root: Path) -> str:
    path = root / APP_RELATIVE
    _require(path.is_file(), "Agent World's Fair app is missing")
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise GateError("fair app is unreadable: {}".format(error)) from error


def _check_app_contract(root: Path) -> str:
    text = _app_text(root)
    required = (
        "<!DOCTYPE html>",
        "<title>Agent World's Fair — Verified District Assembly</title>",
        'name="viewport"',
        'id="fair-canvas"',
        'id="truth-pill"',
        'id="source-pill"',
        'id="truth-grid"',
        'id="leaderboard-body"',
        'id="leaderboard-sort"',
        'id="inspector"',
        'id="assembly-grid"',
        'id="timeline-list"',
        'id="submit-proposal"',
        'id="vote-form"',
        'id="checkpoint-button"',
        'id="export-button"',
        'id="import-file"',
        'id="import-text"',
        'id="import-button"',
        'id="encrypt-button"',
        'id="decrypt-button"',
        'id="clear-encrypted-button"',
        'id="clear-button"',
        'id="undo-button"',
        'id="stop-button"',
        'id="rearm-button"',
        'id="emergency-panel"',
        'id="stop-pill"',
        'id="offline-pill"',
        'id="storage-pill"',
        'id="branch-status"',
        'id="encryption-status"',
        'class="mutation-control',
        "rappterzoo-agent-fair-branch-export/1",
        "rappterzoo-agent-fair-local-action/1",
        "agent-worlds-fair.encrypted-branch.v1",
        "agent-worlds-fair.emergency-stop.v1",
        "__AGENT_FAIR_TEST__",
    )
    missing = [marker for marker in required if marker not in text]
    _require(
        not missing,
        "missing fair app contract markers: {}".format(", ".join(missing)),
    )
    return "{} bytes; fair UI and test contract present".format(
        (root / APP_RELATIVE).stat().st_size
    )


def _check_theme(root: Path) -> str:
    text = _app_text(root)
    markers = (
        'get("scoutTheme")',
        "prefers-color-scheme: dark",
        'setAttribute("data-theme"',
        ":root {",
        'html[data-theme="dark"]',
        "--cp-bg:",
        "--cp-accent:",
        "--cp-danger:",
        "@media (prefers-reduced-motion: reduce)",
    )
    missing = [marker for marker in markers if marker not in text]
    _require(
        not missing,
        "theme/reduced-motion markers missing: {}".format(", ".join(missing)),
    )
    detector = text.index('get("scoutTheme")')
    body = text.lower().index("<body")
    _require(detector < body, "theme detector must run before body paint")
    return "light/dark scout theme and reduced-motion contract present"


def _check_csp(root: Path) -> str:
    text = _app_text(root)
    match = re.search(
        r'http-equiv="Content-Security-Policy"[^>]*content="([^"]+)"',
        text,
        re.IGNORECASE | re.DOTALL,
    )
    _require(match, "Content-Security-Policy meta tag is missing")
    policy = " ".join(match.group(1).split())
    directives = {
        item.split()[0]: item.split()[1:]
        for item in policy.split(";")
        if item.strip()
    }
    _require(
        directives.get("default-src") == ["'none'"],
        "default-src must be 'none'",
    )
    _require(
        directives.get("connect-src") == ["'self'"],
        "connect-src must be 'self'",
    )
    _require(
        directives.get("worker-src") == ["'self'"],
        "worker-src must be 'self'",
    )
    for directive in ("object-src", "base-uri", "form-action", "frame-src"):
        _require(
            directives.get(directive) == ["'none'"],
            "{} must be 'none'".format(directive),
        )
    for token in ("eval(", "new Function", "document.write"):
        _require(
            token not in text,
            "dynamic code primitive is present: {}".format(token),
        )
    return "fail-closed CSP and no dynamic-code primitives"


def _check_same_origin_paths(root: Path) -> str:
    text = _app_text(root)
    expected = {
        "../agent-fair/agent-contract.json",
        "../agent-fair/district.json",
        "../agent-fair/events.jsonl",
        "../agent-fair/fair-state.json",
    }
    for path in expected:
        _require(path in text, "fair app omits relative data path {}".format(path))
    _require(
        'url: "./agent-worlds-fair-sw.js"' in text
        or '"./agent-worlds-fair-sw.js"' in text,
        "service worker URL is not app-relative",
    )
    _require(
        text.count('credentials: "same-origin"') >= 1,
        "fair source fetches must require same-origin credentials",
    )
    resource_blocks = re.findall(
        r"(?:RESOURCE_URLS|DATA_PATHS|SOURCES)\s*=\s*Object\.freeze\(\{(.*?)\}\)",
        text,
        re.DOTALL,
    )
    _require(resource_blocks, "fair resource URL declaration is missing")
    values = set(
        re.findall(r':\s*"([^"]+)"', "\n".join(resource_blocks))
    )
    _require(
        expected.issubset(values),
        "fair resource URL declaration is incomplete",
    )
    _require(
        not any(re.match(r"^(?:https?:)?//", value) for value in values),
        "external fair resource URL found",
    )
    return "four fair data paths and service worker are relative/same-origin"


def _check_service_worker_contract(root: Path) -> str:
    path = root / SERVICE_WORKER_RELATIVE
    _require(path.is_file(), "Agent World's Fair service worker is missing")
    text = path.read_text(encoding="utf-8")
    markers = (
        'const CACHE_NAME = "agent-worlds-fair-v3-release-20260816";',
        "const DATA_PATHS = [",
        "const OPTIONAL_DATA_PATHS = [",
        "const REQUIRED_PATHS = [",
        "const APP_SHELL = [...REQUIRED_PATHS, ...OPTIONAL_DATA_PATHS];",
        '"./agent-worlds-fair.html"',
        '"./agent-worlds-fair-sw.js"',
        '"../agent-fair/fair-state.json"',
        '"../agent-fair/events.jsonl"',
        '"../agent-fair/agent-contract.json"',
        '"../agent-fair/district.json"',
        'url.origin !== self.location.origin',
        "cache.addAll(REQUIRED_PATHS)",
        "fetch(request)",
        "caches.match(request,",
        '"X-Agent-Fair-Provenance"',
        '"agent-fair-cache-status"',
        "ready: required.every",
        "status: 403",
        "status: 503",
        '"unavailable"',
        '"blocked-cross-origin"',
    )
    missing = [marker for marker in markers if marker not in text]
    _require(
        not missing,
        "fair service-worker markers missing: {}".format(", ".join(missing)),
    )
    return "same-origin shell + four-data cache contract declared"


def _manifest_categories(manifest: Dict[str, Any]) -> Dict[str, Any]:
    categories = manifest.get("categories", manifest)
    _require(type(categories) is dict, "manifest categories are invalid")
    return categories


def _check_manifest_feed_registration(root: Path) -> str:
    manifest = _json(root / "apps/manifest.json")
    category = _manifest_categories(manifest).get("3d_immersive", {})
    apps = category.get("apps", [])
    _require(
        category.get("count") == len(apps),
        "3d_immersive manifest count is stale",
    )
    matches = [item for item in apps if item.get("file") == APP_RELATIVE.name]
    _require(len(matches) == 1, "manifest must register the fair exactly once")
    _require(matches[0].get("featured") is True, "fair must be featured")

    feed = _json(root / "apps/feed.json")
    urls = {
        item.get("item", {}).get("url")
        for item in feed.get("dataFeedElement", [])
        if type(item) is dict
    }
    _require(
        len([
            url
            for url in urls
            if type(url) is str and url.endswith(APP_URL_SUFFIX)
        ]) == 1,
        "JSON feed must register the fair exactly once",
    )
    try:
        xml_root = ET.parse(str(root / "apps/feed.xml")).getroot()
    except (OSError, ET.ParseError) as error:
        raise GateError("RSS feed is invalid: {}".format(error)) from error
    links = [
        (node.text or "").strip()
        for node in xml_root.findall(".//item/link")
    ]
    _require(
        len([link for link in links if link.endswith(APP_URL_SUFFIX)]) == 1,
        "RSS feed must register the fair exactly once",
    )
    return "manifest + JSON feed + RSS register one featured fair"


def _check_discovery_registration(root: Path) -> str:
    static = _json(root / ".well-known/mcp.json")
    names = {
        item.get("name")
        for item in static.get("resources", [])
        if type(item) is dict
    }
    prompts = {
        item.get("name")
        for item in static.get("prompts", [])
        if type(item) is dict
    }
    tools = {
        item.get("name")
        for item in static.get("tools", [])
        if type(item) is dict
    }
    _require(
        FAIR_STATIC_RESOURCE_NAMES.issubset(names),
        "static MCP fair resources are incomplete",
    )
    _require(
        FAIR_TOOL_NAMES.issubset(tools),
        "static MCP fair tools are incomplete",
    )
    _require(
        FAIR_PROMPT_NAME in prompts,
        "static MCP fair first-visit prompt is missing",
    )

    protocol = _json(root / ".well-known/agent-protocol")
    blob = json.dumps(protocol, sort_keys=True)
    _require(FAIR_ID in blob, "agent protocol omits fair id")
    for name in FAIR_TOOL_NAMES:
        _require(name in blob, "agent protocol omits {}".format(name))

    toc = _json(root / ".well-known/feeddata-toc")
    toc_blob = json.dumps(toc, sort_keys=True)
    _require(APP_URL_SUFFIX in toc_blob, "feeddata TOC omits fair app")
    for path in FAIR_RESOURCE_PATHS:
        _require("/" + path in toc_blob, "feeddata TOC omits {}".format(path))
    return "MCP discovery, protocol, and feed TOC publish the fair"


def _check_bundle_exact(root: Path) -> str:
    state, events, contract, district = _load_bundle(root)
    result = fair_builder.verify_bundle(
        state,
        events,
        contract,
        district,
        root,
    )
    exact = {
        "bundle_digest": EXPECTED_BUNDLE_DIGEST,
        "contract_digest": EXPECTED_CONTRACT_DIGEST,
        "district_digest": EXPECTED_DISTRICT_DIGEST,
        "event_count": EXPECTED_EVENT_COUNT,
        "event_head": EXPECTED_EVENT_HEAD,
        "winners": EXPECTED_WINNERS,
    }
    for key, expected in exact.items():
        _require(
            result.get(key) == expected,
            "exact fair {} changed".format(key),
        )
    _require(
        _sha256(root / EVENTS_RELATIVE) == EXPECTED_EVENT_LEDGER_SHA256,
        "exact fair event ledger byte digest changed",
    )
    return "exact 23-event fair bundle {} verified".format(
        EXPECTED_BUNDLE_DIGEST[:16]
    )


def _check_event_contract_district(root: Path) -> str:
    state, events, contract, district = _load_bundle(root)
    event_result = fair_builder.verify_events(events)
    _require(
        event_result == {
            "event_count": EXPECTED_EVENT_COUNT,
            "head": EXPECTED_EVENT_HEAD,
            "valid": True,
        },
        "fair event verifier result changed",
    )
    _require(
        state.get("event_ledger") == {
            "event_count": EXPECTED_EVENT_COUNT,
            "exact_keys": sorted(fair_builder.EVENT_KEYS),
            "head": EXPECTED_EVENT_HEAD,
            "path": "events.jsonl",
            "sha256": EXPECTED_EVENT_LEDGER_SHA256,
        },
        "fair event ledger projection changed",
    )
    _require(
        contract.get("integrity", {}).get("contract_digest")
        == EXPECTED_CONTRACT_DIGEST,
        "fair contract digest changed",
    )
    _require(
        district.get("integrity", {}).get("district_digest")
        == EXPECTED_DISTRICT_DIGEST,
        "fair district digest changed",
    )
    _require(
        state.get("integrity", {}).get("bundle_digest")
        == contract.get("integrity", {}).get("bundle_digest")
        == district.get("integrity", {}).get("bundle_digest")
        == EXPECTED_BUNDLE_DIGEST,
        "fair bundle binding changed",
    )
    return "event, state, contract, and district bindings are exact"


def _submission_values(
    events: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    values = [
        event.get("payload", {}).get("submission")
        for event in events
        if event.get("kind") == "fair.submission"
    ]
    _require(
        all(type(value) is dict for value in values),
        "fair submission payload is malformed",
    )
    return values


def _check_submissions(root: Path) -> str:
    state, events, contract, _district = _load_bundle(root)
    submissions = _submission_values(events)
    _require(len(submissions) == 12, "fair must contain exactly 12 submissions")
    agent_ids = set()
    attraction_ids = set()
    submission_ids = set()
    categories = set()
    for submission in submissions:
        attractions = submission.get("attractions", [])
        _require(
            len(attractions) == 1,
            "{} must contain exactly one attraction".format(
                submission.get("submission_id")
            ),
        )
        attraction = attractions[0]
        agent_ids.add(submission.get("agent", {}).get("identity_id"))
        attraction_ids.add(attraction.get("id"))
        submission_ids.add(submission.get("submission_id"))
        categories.add(attraction.get("category"))
    _require(len(agent_ids) == 12, "submissions do not have 12 unique agents")
    _require(
        len(attraction_ids) == 12,
        "submissions do not have 12 unique attractions",
    )
    _require(
        len(submission_ids) == 12,
        "submissions do not have 12 unique submission ids",
    )
    _require(len(categories) >= 6, "submission categories lack diversity")
    screening = state.get("screening", {})
    _require(
        len(screening.get("accepted_submission_ids", [])) == 12
        and not screening.get("rejected", []),
        "all 12 fixed submissions must pass screening",
    )
    _require(
        contract.get("attraction_contract", {}).get(
            "attractions_per_submission"
        ) == 1,
        "contract does not enforce one attraction per submission",
    )
    return "12 unique agents submitted 12 one-attraction proposals"


def _check_safety_resource_caps(root: Path) -> str:
    state, events, contract, district = _load_bundle(root)
    attraction_contract = contract.get("attraction_contract", {})
    _require(
        attraction_contract.get("resource_maximums") == EXPECTED_CAPS,
        "attraction resource caps changed",
    )
    for submission in _submission_values(events):
        attraction = submission["attractions"][0]
        resources = attraction.get("resource_request", {})
        for name, maximum in EXPECTED_CAPS.items():
            amount = resources.get(name)
            _require(
                type(amount) is int and 0 <= amount <= maximum,
                "{} exceeds {} cap".format(
                    submission.get("submission_id"), name
                ),
            )
    _require(
        district.get("resource_capacity") == EXPECTED_DISTRICT_CAPACITY,
        "district resource capacity changed",
    )
    totals = district.get("resource_totals", {})
    for name, capacity in EXPECTED_DISTRICT_CAPACITY.items():
        _require(
            type(totals.get(name)) is int and totals[name] <= capacity,
            "district exceeds {} capacity".format(name),
        )
    boundary = contract.get("data_boundary", {})
    _require(
        boundary.get("allowed") == ["public-metadata"]
        and boundary.get("external_network") is False,
        "fair data boundary is not public/offline",
    )
    excluded = set(boundary.get("excluded_classes", []))
    _require(
        {"GODD", "biometric", "identity-template", "raw-camera", "nonpublic"}
        .issubset(excluded),
        "fair excluded safety classes are incomplete",
    )
    _require(
        contract.get("local_proposals", {}).get("action_limit") == 50,
        "local proposal action cap must be 50",
    )
    _require(
        organism_ledger._find_forbidden_key(state) is None
        and organism_ledger._find_forbidden_key(contract) is None
        and organism_ledger._find_forbidden_key(district) is None,
        "fair public bundle contains a forbidden key",
    )
    return "submission/district caps and public safety boundary verified"


def _check_voting_scoring(root: Path) -> str:
    state, events, _contract, _district = _load_bundle(root)
    rounds = [
        event.get("payload")
        for event in events
        if event.get("kind") == "fair.voting-round"
    ]
    _require(len(rounds) == 4, "fair must contain exactly four voting rounds")
    _require(
        [value.get("round") for value in rounds] == [1, 2, 3, 4],
        "fair voting round order changed",
    )
    _require(
        state.get("voting", {}).get("rounds") == rounds,
        "fair voting state projection changed",
    )
    _require(
        all(
            value.get("issued_credits") == value.get("spent_credits") == 420
            for value in rounds
        ),
        "each fair round must issue and spend 420 synthetic credits",
    )
    evaluation = [
        event
        for event in events
        if event.get("kind") == "fair.evaluation"
    ]
    _require(len(evaluation) == 1, "fair must contain one evaluation")
    weights = evaluation[0].get("payload", {}).get("score_weights_bps")
    _require(weights == EXPECTED_WEIGHTS, "fair score weights changed")
    _require(sum(weights.values()) == 10000, "score weights do not total 10000")
    for ranking in state.get("rankings", []):
        dimensions = ranking.get("dimensions_bps", {})
        _require(
            set(dimensions) == set(EXPECTED_WEIGHTS),
            "ranking dimension set changed",
        )
        _require(
            all(type(value) is int for value in dimensions.values()),
            "ranking dimensions must use integer basis points",
        )
        expected = sum(
            dimensions[name] * weight
            for name, weight in EXPECTED_WEIGHTS.items()
        ) // 10000
        _require(
            ranking.get("score_bps") == expected,
            "integer score formula mismatch for {}".format(
                ranking.get("submission_id")
            ),
        )
    return "four rounds and 10,000-bps integer scoring verified"


def _check_synthetic_balance(root: Path) -> str:
    state, _events, contract, _district = _load_bundle(root)
    economy = state.get("economy", {})
    _require(
        economy.get("currency") == "synthetic-admission-credit",
        "fair currency is not synthetic admission credit",
    )
    _require(economy.get("real_money") is False, "real-money flag is unsafe")
    _require(economy.get("balanced") is True, "synthetic economy is unbalanced")
    _require(
        economy.get("total_issued") == economy.get("total_spent") == 1680,
        "synthetic issued/spent totals changed",
    )
    _require(
        economy.get("total_debits") == economy.get("total_credits") == 3360,
        "synthetic debit/credit totals changed",
    )
    cohort_accounts = [
        account
        for name, account in economy.get("accounts", {}).items()
        if name.startswith("account.cohort.")
    ]
    _require(
        cohort_accounts
        and all(
            account.get("debits") == account.get("credits")
            for account in cohort_accounts
        ),
        "a synthetic visitor cohort account is not balanced",
    )
    contract_economy = contract.get("economy", {})
    _require(
        contract_economy.get("real_money") is False
        and contract_economy.get("redeemable") is False
        and contract_economy.get("transferable") is False,
        "contract economy permits monetary behavior",
    )
    return "1,680 issued/spent and 3,360 debits/credits balance"


def _check_constrained_winners(root: Path) -> str:
    state, _events, _contract, district = _load_bundle(root)
    selection = state.get("winner_selection", {})
    _require(
        selection.get("winner_submission_ids") == EXPECTED_WINNERS,
        "exact fair winner order changed",
    )
    _require(state.get("winners") == EXPECTED_WINNERS, "state winners changed")
    _require(
        len(district.get("pavilions", [])) == 4,
        "district must contain exactly four pavilions",
    )
    _require(
        [value.get("submission_id") for value in district["pavilions"]]
        == EXPECTED_WINNERS,
        "district pavilion order changed",
    )
    _require(
        len({value.get("category") for value in district["pavilions"]}) == 4,
        "winner categories are not distinct",
    )
    decisions = selection.get("decisions", [])
    rejected = [value for value in decisions if value.get("selected") is False]
    _require(rejected, "fair winner selection records no rejections")
    _require(
        all(value.get("reasons") for value in rejected),
        "a rejected proposal lacks reasons",
    )
    rank4 = next((value for value in decisions if value.get("rank") == 4), {})
    rank5 = next((value for value in decisions if value.get("rank") == 5), {})
    _require(
        rank4.get("submission_id") == "submission.protocol-forge"
        and rank4.get("reasons") == [
            "capacity-attention-62-over-60",
            "capacity-compute-98-over-96",
        ],
        "capacity rejection evidence changed",
    )
    _require(
        rank5.get("submission_id") == "submission.epoch-garden"
        and rank5.get("reasons") == ["category-diversity"],
        "category rejection evidence changed",
    )
    _require(
        district.get("resource_totals") == {
            "attention": 59,
            "compute": 92,
            "energy": 67,
        },
        "winning district resource totals changed",
    )
    return "four exact constrained winners with category/cap reasons verified"


def _check_customer_authority(root: Path) -> str:
    state, _events, contract, district = _load_bundle(root)
    controls = state.get("customer_controls", {})
    _require(
        controls == {
            "canonical_write": False,
            "customer_approval_required_for_organism_release": True,
            "customer_shutdown": True,
            "release_performed": False,
            "vendor_shutdown": False,
        },
        "fair state customer authority changed",
    )
    boundary = contract.get("control_boundary", {})
    _require(
        boundary.get("canonical_write") == "forbidden"
        and boundary.get("customer_authority")
        == "explicit-release-command-only"
        and boundary.get("customer_shutdown") is True
        and boundary.get("operator_key_custody") == "customer-local"
        and boundary.get("vendor_shutdown") is False
        and boundary.get("write_scope") == "local-proposal-branch-only",
        "fair contract customer authority changed",
    )
    assembly = district.get("assembly", {})
    _require(
        assembly.get("customer_approval_required_for_organism_release") is True
        and assembly.get("direct_canonical_write") is False
        and assembly.get("status")
        == "release-ready-awaiting-customer-approval",
        "district release authority changed",
    )
    return "customer holds stop, key custody, and explicit release authority"


def _verified_organism_frames(root: Path) -> List[Dict[str, Any]]:
    try:
        frames = organism_ledger.read_frames(root / ORGANISM_LEDGER_RELATIVE)
        organism_ledger.verify_frames(frames)
        organism_ledger.verify_projection(
            frames,
            root / ORGANISM_PROJECTION_RELATIVE,
        )
        return frames
    except Exception as error:
        raise GateError("organism chain verification failed: {}".format(
            error
        )) from error


def _release_candidate_digest(root: Path) -> str:
    try:
        verified = fair_builder.verify_release_candidate_file(root)
    except Exception as error:
        raise GateError(
            "release candidate verification failed: {}".format(error)
        ) from error
    candidate = _json(root / RELEASE_CANDIDATE_RELATIVE)
    digest = candidate.get("candidate_digest")
    _require(
        verified == {
            "bundle_digest": EXPECTED_BUNDLE_DIGEST,
            "candidate_digest": EXPECTED_RELEASE_CANDIDATE_DIGEST,
            "district_digest": EXPECTED_DISTRICT_DIGEST,
            "event_count": EXPECTED_EVENT_COUNT,
            "event_head": EXPECTED_EVENT_HEAD,
            "valid": True,
        }
        and candidate.get("schema") == RELEASE_CANDIDATE_SCHEMA
        and candidate.get("candidate_digest_domain")
        == RELEASE_CANDIDATE_DOMAIN.decode("ascii")
        and candidate.get("candidate_digest_preimage")
        == (
            "candidate digest domain bytes || canonical_bytes(candidate "
            "with candidate_digest omitted)"
        )
        and candidate.get("approval_required") is True
        and candidate.get("fair_id") == FAIR_ID
        and candidate.get("district_id") == DISTRICT_ID
        and candidate.get("bundle_digest") == EXPECTED_BUNDLE_DIGEST
        and candidate.get("district_digest") == EXPECTED_DISTRICT_DIGEST
        and candidate.get("event_count") == EXPECTED_EVENT_COUNT
        and candidate.get("event_head") == EXPECTED_EVENT_HEAD
        and digest == EXPECTED_RELEASE_CANDIDATE_DIGEST,
        "fair release-candidate digest changed",
    )
    return str(digest)


def _fair_release_frames(
    frames: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    return [
        frame
        for frame in frames
        if (
            frame.get("payload", {}).get("event")
            == "agent-worlds-fair-release"
            or str(frame.get("payload", {}).get("event_id", "")).startswith(
                RELEASE_EVENT_PREFIX
            )
        )
    ]


def _codeowners_matches(pattern: str, target: str) -> bool:
    normalized_pattern = pattern.lstrip("/")
    normalized_target = target.lstrip("/")
    if not normalized_pattern or normalized_pattern.startswith("!"):
        return False
    if normalized_pattern.endswith("/"):
        return normalized_target.startswith(normalized_pattern)
    if normalized_pattern.endswith("/**"):
        return normalized_target.startswith(normalized_pattern[:-2])
    if "/" not in normalized_pattern:
        return any(
            fnmatch.fnmatchcase(part, normalized_pattern)
            for part in normalized_target.split("/")
        )
    return fnmatch.fnmatchcase(normalized_target, normalized_pattern)


def _codeowners_for(text: str, target: str) -> List[str]:
    owners: List[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        if _codeowners_matches(parts[0], target):
            owners = parts[1:]
    return owners


def _check_release_codeowners(root: Path) -> str:
    path = root / ".github" / "CODEOWNERS"
    _require(path.is_file(), ".github/CODEOWNERS is missing")
    text = path.read_text(encoding="utf-8")
    targets = (
        "apps/organism-frames.json",
        "apps/organism-frames.jsonl",
        "apps/syndication/current.json",
        "apps/agent-fair/fair-state.json",
        ".github/CODEOWNERS",
        ".github/workflows/agent-fair-release.yml",
        ".github/workflows/agent-fair-release-attestation.yml",
        "scripts/agent_world_fair.py",
        "scripts/tests/test_agent_world_fair.py",
        "scripts/tests/test_verify_agent_fair_release_attestation.py",
        "scripts/verify_agent_fair_release_attestation.py",
    )
    mismatches = {
        target: _codeowners_for(text, target)
        for target in targets
        if _codeowners_for(text, target) != ["@kody-w"]
    }
    _require(
        not mismatches,
        "fair release CODEOWNERS must resolve only to @kody-w: {}".format(
            json.dumps(mismatches, sort_keys=True)
        ),
    )
    return (
        ".github/CODEOWNERS binds organism, syndication, agent-fair, "
        "release, and attestation paths to @kody-w"
    )


def _release_workflow_evidence(root: Path, candidate_digest: str) -> str:
    workflow_dir = root / ".github" / "workflows"
    matches = []
    if workflow_dir.is_dir():
        for path in sorted(workflow_dir.iterdir()):
            if path.suffix not in {".yml", ".yaml"} or not path.is_file():
                continue
            text = path.read_text(encoding="utf-8")
            if (
                "agent_world_fair.py" in text
                and "apply-release" in text
            ):
                matches.append((path, text))
    _require(
        len(matches) == 1,
        "released phase requires exactly one fair release workflow",
    )
    path, text = matches[0]
    required_markers = (
        "workflow_dispatch",
        "bundle_digest",
        "district_digest",
        "customer_approved",
        "inputs.bundle_digest",
        "inputs.district_digest",
        "inputs.customer_approved",
        "agent_world_fair.py release",
        "agent_world_fair.py verify",
        "agent_world_fair.py apply-release",
        "id-token: write",
        "pull-requests: write",
        "contents: write",
        "environment: agent-fair-production",
        "build_syndication.py",
        "agent_fair_gate.py --phase released",
        "gh pr create",
        "--base main",
    )
    missing = [value for value in required_markers if value not in text]
    _require(
        not missing,
        "fair release workflow evidence missing: {}".format(
            ", ".join(missing)
        ),
    )
    _require(
        len(re.findall(r"required\s*:\s*true", text, re.IGNORECASE)) >= 3
        and re.search(r"type\s*:\s*boolean", text, re.IGNORECASE)
        and re.search(r"type\s*:\s*string", text, re.IGNORECASE),
        "fair workflow dispatch inputs are not closed and required",
    )
    _require(
        "--bundle-digest" in text
        and "--district-digest" in text
        and "inputs.bundle_digest" in text
        and "inputs.district_digest" in text
        and "inputs.customer_approved" in text
        and candidate_digest == EXPECTED_RELEASE_CANDIDATE_DIGEST,
        "fair release workflow does not bind verified dispatch inputs",
    )
    _require(
        re.search(
            r"git\s+(?:switch|checkout)\s+-[^\n]*[cb]",
            text,
            re.IGNORECASE,
        )
        and re.search(r"git\s+push[^\n]*\$RELEASE_BRANCH", text)
        and not re.search(
            r"git\s+push[^\n]*(?:HEAD:main|refs/heads/main|origin\s+main)",
            text,
            re.IGNORECASE,
        ),
        "fair release workflow must push a release branch, never main",
    )
    moonshot = (root / ".github/workflows/moonshot-gate.yml").read_text(
        encoding="utf-8"
    )
    _require(
        re.search(r"^\s*pull_request\s*:", moonshot, re.MULTILINE)
        and re.search(r"^\s*moonshot-gate\s*:", moonshot, re.MULTILINE),
        "moonshot gate is not a required pull-request workflow candidate",
    )
    _require(
        not re.search(
            r"^\s{0,4}(?:push|pull_request|schedule)\s*:",
            text,
            re.MULTILINE,
        ),
        "fair release workflow has a non-dispatch release trigger",
    )
    return path.relative_to(root).as_posix()


def _check_release_artifact_workflow(root: Path) -> str:
    path = root / ".github/workflows/agent-fair-release.yml"
    text = path.read_text(encoding="utf-8")
    required = (
        "python3 scripts/verify_agent_fair_release_attestation.py create",
        '--output "${RUNNER_TEMP}/agent-fair-release-attestation.json"',
        "uses: actions/upload-artifact@v4",
        "name: agent-fair-release-attestation-${{ github.run_id }}",
        "path: ${{ runner.temp }}/agent-fair-release-attestation.json",
        "if-no-files-found: error",
        "retention-days: 30",
        "Create or update release pull request",
        "['attestation_sha256']",
    )
    missing = [marker for marker in required if marker not in text]
    _require(
        not missing,
        "release attestation artifact workflow markers missing: {}".format(
            ", ".join(missing)
        ),
    )
    create_index = text.index(
        "python3 scripts/verify_agent_fair_release_attestation.py create"
    )
    upload_index = text.index("uses: actions/upload-artifact@v4")
    pull_request_index = text.index(
        "- name: Create or update release pull request"
    )
    _require(
        create_index < upload_index < pull_request_index
        and upload_index < text.index("gh pr create"),
        "release attestation must be generated and uploaded before PR creation",
    )
    _require(
        "AGENT_FAIR_RELEASE_ATTESTATION" not in text,
        "release workflow must remain structural-only before PR attestation",
    )
    return (
        "release workflow generates and uploads deterministic attestation "
        "artifact before creating the release PR"
    )


def _python_literal_assignment(
    source: str,
    name: str,
    label: str,
) -> Any:
    try:
        tree = ast.parse(source)
    except SyntaxError as error:
        raise GateError("{} policy is invalid Python".format(label)) from error
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(
            isinstance(target, ast.Name) and target.id == name
            for target in node.targets
        ):
            continue
        try:
            return ast.literal_eval(node.value)
        except (ValueError, TypeError) as error:
            raise GateError(
                "{} {} must be a literal".format(label, name)
            ) from error
    raise GateError("{} {} is missing".format(label, name))


def _check_pr_attestation_workflow(root: Path) -> str:
    path = (
        root
        / ".github/workflows/agent-fair-release-attestation.yml"
    )
    _require(path.is_file(), "all-PR release attestation workflow is missing")
    text = path.read_text(encoding="utf-8")
    required = (
        "name: Agent Fair Release Attestation",
        "pull_request:",
        "actions: read",
        "contents: read",
        "pull-requests: read",
        "agent-fair-release-attestation:",
        "name: agent-fair-release-attestation",
        "ref: ${{ github.event.pull_request.head.sha }}",
        "Detect trusted base verifier",
        "id: trusted",
        "BASE_SHA: ${{ github.event.pull_request.base.sha }}",
        'git cat-file -e "${BASE_SHA}:scripts/'
        'verify_agent_fair_release_attestation.py"',
        'echo "available=true" >> "$GITHUB_OUTPUT"',
        'echo "available=false" >> "$GITHUB_OUTPUT"',
        "Materialize trusted verifier from pull request base",
        "if: steps.trusted.outputs.available == 'true'",
        '${{ github.event.pull_request.base.sha }}:scripts/'
        "verify_agent_fair_release_attestation.py",
        '${{ github.event.pull_request.base.sha }}:scripts/'
        "agent_world_fair.py",
        '${{ github.event.pull_request.base.sha }}:scripts/'
        "organism_ledger.py",
        '${RUNNER_TEMP}/agent-fair-release-verifier/'
        "verify_agent_fair_release_attestation.py",
        "Verify with trusted base verifier",
        "GITHUB_TOKEN: ${{ github.token }}",
        "verify-pr",
        '--root "${GITHUB_WORKSPACE}"',
        '--repository "${{ github.repository }}"',
        '--pr-number "${{ github.event.pull_request.number }}"',
        '--base-sha "${{ github.event.pull_request.base.sha }}"',
        '--head-sha "${{ github.event.pull_request.head.sha }}"',
        '--head-ref "${{ github.event.pull_request.head.ref }}"',
        "--wait-seconds 300",
        "Bootstrap verifier installation without release authority",
        "if: steps.trusted.outputs.available == 'false'",
        "HEAD_REF: ${{ github.event.pull_request.head.ref }}",
        "HEAD_SHA: ${{ github.event.pull_request.head.sha }}",
        'if head_ref.startswith("release/agent-fair-"):',
        'release_prefix = "agent-worlds-fair-release:"',
        'str(payload.get("event_id", "")).startswith(',
        '"apps/organism-frames.json",',
        '"apps/organism-frames.jsonl",',
        '"apps/syndication/",',
        "bootstrap pull request cannot use a release branch",
        "bootstrap pull request contains a fair release event",
        "bootstrap changes forbidden generated release paths",
        "bootstrap changes paths outside one-time allowlist",
        '"reason": "trusted base verifier is not installed yet"',
        '"status": "bootstrap-not-release"',
    )
    missing = [marker for marker in required if marker not in text]
    _require(
        not missing,
        "all-PR attestation workflow markers missing: {}".format(
            ", ".join(missing)
        ),
    )
    _require(
        text.count(
            "if: steps.trusted.outputs.available == 'true'"
        ) == 2
        and text.count(
            "if: steps.trusted.outputs.available == 'false'"
        ) == 1,
        "trusted-base and one-time bootstrap branches changed",
    )
    bootstrap_step = re.search(
        r"(?ms)^      - name: Bootstrap verifier installation without "
        r"release authority\n(?P<body>.*)\Z",
        text,
    )
    _require(
        bootstrap_step is not None,
        "bootstrap verifier workflow step is missing",
    )
    bootstrap_source_match = re.search(
        r"(?ms)^\s*python3 - <<'PY'\n(?P<source>.*?)^\s*PY\s*$",
        bootstrap_step.group("body"),
    )
    _require(
        bootstrap_source_match is not None,
        "bootstrap verifier inline policy is missing",
    )
    bootstrap_source = textwrap.dedent(
        bootstrap_source_match.group("source")
    )
    workflow_allowed = _python_literal_assignment(
        bootstrap_source,
        "allowed",
        "bootstrap workflow",
    )
    workflow_forbidden = _python_literal_assignment(
        bootstrap_source,
        "forbidden",
        "bootstrap workflow",
    )
    workflow_prefixes = _python_literal_assignment(
        bootstrap_source,
        "forbidden_prefixes",
        "bootstrap workflow",
    )
    _require(
        type(workflow_allowed) is set
        and workflow_allowed == BOOTSTRAP_ALLOWED_PATHS,
        "bootstrap workflow allowlist changed",
    )
    _require(
        type(workflow_forbidden) is set
        and workflow_forbidden == BOOTSTRAP_FORBIDDEN_PATHS,
        "bootstrap workflow forbidden paths changed",
    )
    _require(
        type(workflow_prefixes) is tuple
        and workflow_prefixes == BOOTSTRAP_FORBIDDEN_PREFIXES,
        "bootstrap workflow forbidden prefixes changed",
    )
    _require(
        re.search(r"^\s*pull_request\s*:\s*$", text, re.MULTILINE)
        and not re.search(
            r"^\s*(?:paths|paths-ignore)\s*:",
            text,
            re.MULTILINE,
        ),
        "release attestation verifier must run on every pull request",
    )
    job = re.search(
        r"(?ms)^  agent-fair-release-attestation:\s*\n(?P<body>.*)\Z",
        text,
    )
    _require(
        job is not None
        and not re.search(r"^\s{4}if\s*:", job.group("body"), re.MULTILINE),
        "release attestation job cannot be conditionally skipped",
    )
    verifier_path = (
        root / "scripts/verify_agent_fair_release_attestation.py"
    )
    _require(
        verifier_path.is_file(),
        "release PR attestation verifier is missing",
    )
    verifier = verifier_path.read_text(encoding="utf-8")
    verifier_markers = (
        'ATTESTATION_SCHEMA = "rappterzoo-agent-fair-release-attestation/1"',
        "def inspect_release_change(",
        "def verify_release_attestation(",
        "def verify_ci_release_attestation(",
        "def verify_pull_request_release(",
        'RELEASE_BRANCH_PREFIX = "release/agent-fair-"',
        'ARTIFACT_PREFIX = "agent-fair-release-attestation-"',
        "PROTECTED_RELEASE_PATHS = {",
        "PROTECTED_RELEASE_PREFIXES = (",
        "def _changed_paths(",
        "def _protected_changed_paths(",
        "BOOTSTRAP_ALLOWED_PATHS = {",
        "BOOTSTRAP_FORBIDDEN_PATHS = {",
        "BOOTSTRAP_FORBIDDEN_PREFIXES = (",
        "def verify_bootstrap_install(",
        "bootstrap pull request cannot use a release branch",
        "bootstrap pull request contains a fair release event",
        "bootstrap pull request changes forbidden generated release paths",
        "bootstrap pull request changes paths outside the one-time allowlist",
        '"status": "bootstrap-not-release"',
        "head_ref.startswith(RELEASE_BRANCH_PREFIX)",
        "and protected_changes",
        "release branch changed protected paths without a fair frame",
        "if _release_lines(base_raw) == _release_lines(head_raw):",
        "len(head_frames) == len(base_frames) + 1",
        "head_frames[:len(base_frames)] == base_frames",
        '"status": "not-applicable"',
        '"status": "verified"',
    )
    absent = [
        marker for marker in verifier_markers if marker not in verifier
    ]
    _require(
        not absent,
        "release PR attestation verifier markers missing: {}".format(
            ", ".join(absent)
        ),
    )
    source_allowed = _python_literal_assignment(
        verifier,
        "BOOTSTRAP_ALLOWED_PATHS",
        "release PR attestation verifier",
    )
    source_forbidden = _python_literal_assignment(
        verifier,
        "BOOTSTRAP_FORBIDDEN_PATHS",
        "release PR attestation verifier",
    )
    source_prefixes = _python_literal_assignment(
        verifier,
        "BOOTSTRAP_FORBIDDEN_PREFIXES",
        "release PR attestation verifier",
    )
    _require(
        type(source_allowed) is set
        and source_allowed == BOOTSTRAP_ALLOWED_PATHS,
        "release PR attestation verifier bootstrap allowlist changed",
    )
    _require(
        type(source_forbidden) is set
        and source_forbidden == BOOTSTRAP_FORBIDDEN_PATHS,
        "release PR attestation verifier bootstrap forbidden paths changed",
    )
    _require(
        type(source_prefixes) is tuple
        and source_prefixes == BOOTSTRAP_FORBIDDEN_PREFIXES,
        "release PR attestation verifier bootstrap prefixes changed",
    )
    return (
        "all-PR agent-fair-release-attestation job invokes the closed "
        "artifact, PR, workflow-run, and frame verifier"
    )


def _base64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _oidc_test_jwks() -> Dict[str, Any]:
    modulus = OIDC_TEST_RSA_N.to_bytes(
        (OIDC_TEST_RSA_N.bit_length() + 7) // 8,
        "big",
    )
    exponent = OIDC_TEST_RSA_E.to_bytes(
        (OIDC_TEST_RSA_E.bit_length() + 7) // 8,
        "big",
    )
    return {
        "keys": [{
            "alg": "RS256",
            "e": _base64url(exponent),
            "kid": OIDC_TEST_KID,
            "kty": "RSA",
            "n": _base64url(modulus),
            "use": "sig",
        }]
    }


def _oidc_test_token(
    claims: Dict[str, Any],
    kid: str = OIDC_TEST_KID,
    algorithm: str = "RS256",
    sign: bool = True,
) -> str:
    header = _base64url(json.dumps(
        {"alg": algorithm, "kid": kid, "typ": "JWT"},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8"))
    payload = _base64url(json.dumps(
        claims,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8"))
    signing_input = "{}.{}".format(header, payload).encode("ascii")
    if not sign:
        return "{}.{}.".format(header, payload)
    digest_info = (
        bytes.fromhex("3031300d060960864801650304020105000420")
        + hashlib.sha256(signing_input).digest()
    )
    size = (OIDC_TEST_RSA_N.bit_length() + 7) // 8
    encoded = (
        b"\x00\x01"
        + b"\xff" * (size - len(digest_info) - 3)
        + b"\x00"
        + digest_info
    )
    signature = pow(
        int.from_bytes(encoded, "big"),
        OIDC_TEST_RSA_D,
        OIDC_TEST_RSA_N,
    ).to_bytes(size, "big")
    return "{}.{}.{}".format(header, payload, _base64url(signature))


def _check_oidc_verifier() -> str:
    verifier = getattr(
        fair_builder,
        "verify_github_oidc_token",
        None,
    )
    _require(callable(verifier), "fair OIDC verifier is missing")
    now = 2_000_000_000
    claims = {
        "actor": "fair-gate-test",
        "aud": OIDC_AUDIENCE,
        "environment": OIDC_ENVIRONMENT,
        "event_name": OIDC_EVENT_NAME,
        "exp": now + 300,
        "iss": OIDC_ISSUER,
        "nbf": now - 10,
        "ref": OIDC_REF,
        "repository": OIDC_REPOSITORY,
        "run_id": "123456",
        "workflow_ref": OIDC_WORKFLOW_REF,
    }
    jwks = _oidc_test_jwks()
    valid_token = _oidc_test_token(claims)
    evidence = verifier(valid_token, jwks, now=now)
    repeated_evidence = verifier(valid_token, jwks, now=now)
    _require(
        evidence == repeated_evidence
        and set(evidence) == OIDC_APPROVAL_KEYS
        and evidence.get("actor") == claims["actor"]
        and evidence.get("run_id") == claims["run_id"]
        and evidence.get("attestation_sha256")
        == hashlib.sha256(valid_token.encode("ascii")).hexdigest(),
        "valid OIDC attestation evidence changed",
    )
    mutations = {
        "unsigned": _oidc_test_token(claims, algorithm="none", sign=False),
        "wrong-kid": _oidc_test_token(claims, kid="untrusted"),
        "forged-signature": valid_token[:-1]
        + ("A" if valid_token[-1] != "A" else "B"),
        "wrong-aud": _oidc_test_token({**claims, "aud": "wrong"}),
        "wrong-iss": _oidc_test_token({**claims, "iss": "https://wrong"}),
        "wrong-repository": _oidc_test_token({
            **claims,
            "repository": "attacker/repository",
        }),
        "wrong-ref": _oidc_test_token({
            **claims,
            "ref": "refs/heads/feature",
        }),
        "wrong-workflow": _oidc_test_token({
            **claims,
            "workflow_ref": (
                OIDC_REPOSITORY
                + "/.github/workflows/other.yml@refs/heads/main"
            ),
        }),
        "wrong-environment": _oidc_test_token({
            **claims,
            "environment": "unprotected",
        }),
        "wrong-event": _oidc_test_token({
            **claims,
            "event_name": "push",
        }),
        "expired": _oidc_test_token({
            **claims,
            "exp": now,
        }),
    }
    for label, token in mutations.items():
        try:
            verifier(token, jwks, now=now)
        except Exception:
            continue
        raise GateError(
            "fair OIDC verifier accepted {} token".format(label)
        )
    request_verifier = getattr(
        fair_builder,
        "_github_oidc_approval_evidence",
        None,
    )
    request_url_builder = getattr(
        fair_builder,
        "_oidc_request_url",
        None,
    )
    _require(
        callable(request_verifier),
        "GitHub OIDC request verifier is missing",
    )
    _require(
        callable(request_url_builder),
        "GitHub OIDC request URL verifier is missing",
    )
    names = (
        "ACTIONS_ID_TOKEN_REQUEST_URL",
        "ACTIONS_ID_TOKEN_REQUEST_TOKEN",
        "AGENT_FAIR_CUSTOMER_APPROVED",
        "GITHUB_ACTIONS",
        "GITHUB_EVENT_NAME",
        "GITHUB_REF_NAME",
        "GITHUB_REPOSITORY",
    )
    saved = {name: os.environ.get(name) for name in names}
    try:
        for name in names:
            os.environ.pop(name, None)
        os.environ.update({
            "AGENT_FAIR_CUSTOMER_APPROVED": "true",
            "GITHUB_ACTIONS": "true",
            "GITHUB_EVENT_NAME": "workflow_dispatch",
            "GITHUB_REF_NAME": "main",
            "GITHUB_REPOSITORY": OIDC_REPOSITORY,
        })
        try:
            request_verifier()
        except Exception:
            pass
        else:
            raise GateError("env-only release approval spoof was accepted")
    finally:
        for name, value in saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
    request_url = request_url_builder(
        "https://token.actions.githubusercontent.com/oidc"
        "?audience=spoofed&other=retained"
    )
    parsed_request = urllib.parse.urlsplit(request_url)
    query = urllib.parse.parse_qsl(
        parsed_request.query,
        keep_blank_values=True,
    )
    _require(
        parsed_request.scheme == "https"
        and parsed_request.hostname
        == "token.actions.githubusercontent.com"
        and query.count(("audience", OIDC_AUDIENCE)) == 1
        and not any(
            key == "audience" and value != OIDC_AUDIENCE
            for key, value in query
        ),
        "GitHub OIDC request audience binding changed",
    )
    for label, value in {
        "plaintext": "http://token.actions.githubusercontent.com/oidc",
        "wrong-host": "https://actions.githubusercontent.com.evil/oidc",
        "wrong-port": "https://token.actions.githubusercontent.com:444/oidc",
        "userinfo": (
            "https://attacker@token.actions.githubusercontent.com/oidc"
        ),
    }.items():
        try:
            request_url_builder(value)
        except Exception:
            continue
        raise GateError(
            "fair OIDC request URL verifier accepted {}".format(label)
        )
    return (
        "RS256/JWKS OIDC verifier rejected env-only, request-endpoint, "
        "unsigned, forged, kid/signature/claim/expiry mutations"
    )


def _check_oidc_pr_authority(root: Path) -> str:
    candidate_digest = _release_candidate_digest(root)
    workflow = _release_workflow_evidence(root, candidate_digest)
    source = (root / "scripts/agent_world_fair.py").read_text(
        encoding="utf-8"
    )
    source_markers = (
        'OIDC_AUDIENCE = "rappterzoo-agent-fair-release"',
        'OIDC_ISSUER = "https://token.actions.githubusercontent.com"',
        'OIDC_REPOSITORY = "kody-w/localFirstTools-main"',
        'OIDC_REF = "refs/heads/main"',
        'OIDC_EVENT_NAME = "workflow_dispatch"',
        'OIDC_ENVIRONMENT = "agent-fair-production"',
        "OIDC_JWKS_URL",
        'header.get("alg") != "RS256"',
        "_verify_rs256",
        "_verify_oidc_attestation",
        "verify_github_oidc_token",
        "ACTIONS_ID_TOKEN_REQUEST_URL",
        "ACTIONS_ID_TOKEN_REQUEST_TOKEN",
    )
    missing = [marker for marker in source_markers if marker not in source]
    _require(
        not missing,
        "fair OIDC verifier markers missing: {}".format(
            ", ".join(missing)
        ),
    )
    candidate = _json(root / RELEASE_CANDIDATE_RELATIVE)
    frame = candidate.get("expected_frame_payload", {})
    requirement = frame.get("approval_evidence", {})
    _require(
        candidate.get("candidate_digest") == candidate_digest
        and candidate.get("verifier") == {
            "command": "python3 scripts/agent_world_fair.py verify",
            "version": "agent-world-fair-release/3",
        }
        and frame.get("approval_basis")
        == "verified-github-actions-oidc-attestation"
        and frame.get("release_candidate_digest") == "$candidate_digest"
        and requirement == {
            "exact_keys": sorted(OIDC_APPROVAL_KEYS),
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
        "release candidate OIDC authority contract changed",
    )
    verifier_detail = _check_oidc_verifier()
    return "{}; {}".format(workflow, verifier_detail)


def _github_api_json(url: str, token: str) -> Dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": "Bearer " + token,
            "User-Agent": "agent-worlds-fair-gate",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(request, timeout=8) as response:
        value = json.loads(response.read().decode("utf-8"))
    _require(type(value) is dict, "GitHub API returned a non-object")
    return value


def _check_repository_protection(root: Path) -> str:
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    if not token or not re.fullmatch(r"[^/\s]+/[^/\s]+", repository):
        return (
            "GitHub API unavailable; static OIDC, PR-only workflow, "
            "environment, and moonshot protections required"
        )
    _require(
        repository == OIDC_REPOSITORY,
        "GitHub API repository does not match the OIDC release repository",
    )
    base = "https://api.github.com/repos/" + repository
    try:
        environment = _github_api_json(
            base + "/environments/agent-fair-production",
            token,
        )
        protection = _github_api_json(
            base + "/branches/main/protection",
            token,
        )
    except urllib.error.URLError as error:
        if not isinstance(error, urllib.error.HTTPError):
            return (
                "GitHub API offline; static OIDC, PR-only workflow, "
                "environment, and moonshot protections required"
            )
        raise GateError(
            "GitHub repository protection API failed with HTTP {}".format(
                error.code
            )
        ) from error
    rules = environment.get("protection_rules", [])
    reviewer_rules = [
        rule
        for rule in rules
        if type(rule) is dict
        and rule.get("type") == "required_reviewers"
        and type(rule.get("reviewers")) is list
        and bool(rule.get("reviewers"))
    ]
    _require(
        environment.get("name") == "agent-fair-production"
        and reviewer_rules,
        "agent-fair-production lacks a required reviewer",
    )
    pull_requests = protection.get("required_pull_request_reviews")
    statuses = protection.get("required_status_checks", {})
    contexts = {
        str(value).lower()
        for value in statuses.get("contexts", [])
    }
    contexts.update(
        str(value.get("context", "")).lower()
        for value in statuses.get("checks", [])
        if type(value) is dict
    )
    _require(
        type(pull_requests) is dict
        and any("moonshot" in context for context in contexts),
        "main protection must require pull requests and moonshot status",
    )
    _require(
        any(
            "agent-fair-release-attestation" in context
            for context in contexts
        ),
        "main protection must require agent-fair-release-attestation status",
    )
    return (
        "GitHub API verified agent-fair-production reviewer and "
        "main PR + moonshot + release attestation protection"
    )


def resolve_release_phase(root: Path, requested: str = "auto") -> str:
    _require(requested in RELEASE_PHASES, "unknown release phase")
    if requested != "auto":
        return requested
    markers = (
        "agent-worlds-fair-release",
        '"kind":"agent-worlds-fair-object"',
        '"kind": "agent-worlds-fair-object"',
    )
    paths = [
        root / ORGANISM_LEDGER_RELATIVE,
        root / SYNDICATION_SNAPSHOT_RELATIVE,
    ]
    delta_dir = root / "apps" / "syndication" / "deltas"
    if delta_dir.is_dir():
        paths.extend(sorted(delta_dir.glob("*.json")))
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        if any(marker in text for marker in markers):
            return "released"
        if any(relative in text for relative in FAIR_RESOURCE_PATHS):
            return "released"
    return "prepared"


def _check_supplied_release_attestation(
    root: Path,
    path: Path,
    candidate: Dict[str, Any],
    release: Dict[str, Any],
) -> str:
    _require(path.is_file(), "CI release attestation JSON is missing")
    verifier = getattr(
        release_attestation,
        "verify_ci_release_attestation",
        None,
    )
    _require(
        callable(verifier),
        "public CI release attestation verifier is missing",
    )
    try:
        public_result = verifier(path, root)
    except Exception as error:
        raise GateError(
            "public CI release attestation verifier rejected evidence: "
            + str(error)
        ) from error
    raw = path.read_bytes()
    _require(
        0 < len(raw) <= release_attestation.ATTESTATION_LIMIT,
        "CI release attestation JSON size is invalid",
    )
    try:
        value = fair_builder._strict_json_bytes(
            raw,
            "CI release attestation",
        )
    except Exception as error:
        raise GateError(str(error)) from error
    _require(
        raw == fair_builder._pretty_bytes(value),
        "CI release attestation JSON bytes are not deterministic",
    )
    _require(
        type(value) is dict
        and set(value) == release_attestation.ATTESTATION_KEYS,
        "CI release attestation JSON schema changed",
    )
    try:
        verified = release_attestation.verify_release_attestation(
            value,
            candidate,
            release,
            value.get("base_sha"),
            value.get("release_commit_sha"),
        )
    except Exception as error:
        raise GateError(
            "CI release attestation does not bind the release frame: "
            + str(error)
        ) from error
    _require(
        verified == {
            "candidate_digest": EXPECTED_RELEASE_CANDIDATE_DIGEST,
            "release_commit_sha": value["release_commit_sha"],
            "release_event_id": value["release_event_id"],
            "run_id": value["run_id"],
            "valid": True,
        },
        "CI release attestation verifier result changed",
    )
    _require(
        public_result == {
            **verified,
            "artifact": str(path),
            "status": "attestation-verified",
        },
        "public CI release attestation verifier result changed",
    )
    expected_branch = "release/agent-fair-{}".format(value["run_id"])
    event_name = os.environ.get("GITHUB_EVENT_NAME")
    _require(
        event_name == "pull_request",
        "CI release attestation was not supplied by an approved workflow",
    )
    event_path_value = os.environ.get("GITHUB_EVENT_PATH", "")
    event_path = Path(event_path_value) if event_path_value else None
    _require(
        event_path is not None and event_path.is_file(),
        "CI pull request event JSON is missing",
    )
    event_raw = event_path.read_bytes()
    _require(
        0 < len(event_raw) <= 1024 * 1024,
        "CI pull request event JSON size is invalid",
    )
    try:
        event = fair_builder._strict_json_bytes(
            event_raw,
            "CI pull request event",
        )
    except Exception as error:
        raise GateError(str(error)) from error
    pull_request = event.get("pull_request", {})
    _require(
        event.get("repository", {}).get("full_name") == OIDC_REPOSITORY
        and pull_request.get("base", {}).get("ref") == "main"
        and pull_request.get("base", {}).get("sha") == value["base_sha"]
        and pull_request.get("head", {}).get("ref") == expected_branch
        and pull_request.get("head", {}).get("sha")
        == value["release_commit_sha"]
        and pull_request.get("head", {}).get("repo", {}).get("full_name")
        == OIDC_REPOSITORY,
        "CI pull request event does not bind the attested release lineage",
    )
    _require(
        {
            "actions": os.environ.get("GITHUB_ACTIONS"),
            "base": os.environ.get("GITHUB_BASE_REF"),
            "head": os.environ.get("GITHUB_HEAD_REF"),
            "job": os.environ.get("GITHUB_JOB"),
            "repository": os.environ.get("GITHUB_REPOSITORY"),
            "workflow": os.environ.get("GITHUB_WORKFLOW"),
        }
        == {
            "actions": "true",
            "base": "main",
            "head": expected_branch,
            "job": "agent-fair-release-attestation",
            "repository": OIDC_REPOSITORY,
            "workflow": "Agent Fair Release Attestation",
        },
        "CI release attestation context is not the all-PR verifier job",
    )
    return (
        "attestation-verified PR {} at release commit {}".format(
            expected_branch,
            value["release_commit_sha"],
        )
    )


def _check_organism_release(
    root: Path,
    phase: str = "released",
    attestation_path: Optional[Path] = None,
) -> str:
    candidate_digest = _release_candidate_digest(root)
    state, _events, _contract, district = _load_bundle(root)
    frames = _verified_organism_frames(root)
    fair_releases = _fair_release_frames(frames)
    if phase == "prepared":
        _require(
            attestation_path is None,
            "prepared phase cannot accept release PR attestation evidence",
        )
        _require(
            not fair_releases,
            "prepared phase must not contain a fair organism release",
        )
        _require(
            state.get("customer_controls", {}).get("release_performed")
            is False
            and state.get("status")
            == "release-ready-awaiting-customer-approval"
            and district.get("assembly", {}).get("status")
            == "release-ready-awaiting-customer-approval",
            "prepared phase release boundary changed",
        )
        return "prepared release candidate {} verified; no release frame".format(
            candidate_digest
        )
    _require(phase == "released", "unknown organism release phase")
    workflow = _release_workflow_evidence(root, candidate_digest)
    expected_id = "{}{}:{}".format(
        RELEASE_EVENT_PREFIX,
        EXPECTED_BUNDLE_DIGEST,
        EXPECTED_DISTRICT_DIGEST,
    )
    releases = [
        frame
        for frame in frames
        if frame.get("payload", {}).get("event_id") == expected_id
    ]
    _require(
        len(fair_releases) == 1 and len(releases) == 1,
        "fair organism release frame must occur exactly once",
    )
    release = releases[0]
    payload = release.get("payload", {})
    candidate = _json(root / RELEASE_CANDIDATE_RELATIVE)
    expected_payload = candidate.get("expected_frame_payload", {})
    approval = payload.get("approval_evidence", {})
    _require(
        release.get("kind") == "zoo.observation"
        and release.get("sig") is None,
        "release kind or signature assurance changed",
    )
    _require(
        set(payload)
        == set(expected_payload)
        | {"approval_evidence", "release_candidate_digest"}
        and all(
            payload.get(key) == value
            for key, value in expected_payload.items()
            if key not in {
                "approval_evidence",
                "release_candidate_digest",
            }
        )
        and payload.get("customer_approved") is True
        and payload.get("fair_bundle_digest")
        == state.get("integrity", {}).get("bundle_digest")
        and payload.get("district_digest")
        == district.get("integrity", {}).get("district_digest")
        and payload.get("fair_event_head")
        == state.get("event_ledger", {}).get("head")
        and payload.get("organism") == DISTRICT_ID
        and payload.get("winner_submission_ids") == EXPECTED_WINNERS,
        "fair organism release payload changed",
    )
    _require(
        payload.get("release_candidate_digest") == candidate_digest
        and set(approval) == OIDC_APPROVAL_KEYS
        and approval.get("aud") == OIDC_AUDIENCE
        and approval.get("environment") == OIDC_ENVIRONMENT
        and approval.get("event_name") == OIDC_EVENT_NAME
        and approval.get("iss") == OIDC_ISSUER
        and approval.get("ref") == OIDC_REF
        and approval.get("repository") == OIDC_REPOSITORY
        and approval.get("workflow_ref") == OIDC_WORKFLOW_REF
        and type(approval.get("actor")) is str
        and bool(approval.get("actor"))
        and approval.get("actor").strip() == approval.get("actor")
        and type(approval.get("run_id")) is str
        and re.fullmatch(r"[1-9][0-9]{0,19}", approval.get("run_id"))
        and type(approval.get("exp")) is int
        and type(approval.get("nbf")) is int
        and approval.get("exp") > approval.get("nbf")
        and re.fullmatch(
            r"[0-9a-f]{64}",
            str(approval.get("attestation_sha256", "")),
        )
        and approval.get("attestation_sha256") != "0" * 64,
        "fair cryptographic OIDC approval evidence changed",
    )
    provenance = (
        _check_supplied_release_attestation(
            root,
            attestation_path,
            candidate,
            release,
        )
        if attestation_path is not None
        else (
            "structural-only local mode: exact unsigned release frame and "
            "bounded upstream OIDC claims verified, but no CI PR "
            "attestation JSON was supplied"
        )
    )
    return (
        "released candidate {} via {} at organism frame seq {}; {}"
    ).format(
        candidate_digest,
        workflow,
        release.get("seq"),
        provenance,
    )


def _syndication_values(
    root: Path,
) -> Tuple[
    Dict[str, Any],
    Dict[str, Any],
    List[Dict[str, Any]],
    List[Dict[str, Any]],
]:
    index = _json(root / SYNDICATION_INDEX_RELATIVE)
    snapshot = _json(root / SYNDICATION_SNAPSHOT_RELATIVE)
    history = index.get("deltas", [])
    _require(type(history) is list and history, "syndication history is empty")
    previous = None
    deltas = []
    for sequence, entry in enumerate(history):
        _require(
            entry.get("sequence") == sequence,
            "delta index sequence mismatch",
        )
        _require(
            entry.get("previous_delta") == previous,
            "delta index previous link mismatch",
        )
        relative = entry.get("path")
        _require(type(relative) is str, "delta path is missing")
        path = root / "apps/syndication" / relative
        _require(path.is_file(), "delta file is missing: {}".format(relative))
        digest = _sha256(path)
        _require(
            digest == entry.get("sha256"),
            "delta byte digest mismatch at {}".format(sequence),
        )
        _require(
            Path(relative).stem == digest,
            "delta filename is not content-addressed",
        )
        delta = _json(path)
        _require(
            delta.get("sequence") == sequence
            and delta.get("previous_delta") == previous,
            "delta payload chain mismatch",
        )
        deltas.append(delta)
        previous = digest
    return index, snapshot, history, deltas


def _require_atomic_fair_release_delta(
    deltas: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    publication_sets = [
        {
            value.get("path")
            for value in delta.get("changes", {}).get("data_upserts", [])
            if type(value) is dict
            and value.get("path") in FAIR_RESOURCE_PATHS
        }
        for delta in deltas
    ]
    _require(
        any(paths == FAIR_RESOURCE_PATHS for paths in publication_sets)
        and all(
            not paths or paths == FAIR_RESOURCE_PATHS
            for paths in publication_sets
        ),
        "profile-10 fair descriptors were not published atomically",
    )
    fair_tombstones = [
        value
        for delta in deltas
        for value in delta.get("changes", {}).get("data_tombstones", [])
        if type(value) is dict
        and value.get("path") in FAIR_RESOURCE_PATHS
    ]
    _require(
        not fair_tombstones,
        "profile-10 history tombstoned an immutable fair object",
    )
    releases = [
        frame
        for delta in deltas
        for frame in delta.get("changes", {}).get("frame_appends", [])
        if type(frame) is dict
        and str(frame.get("payload", {}).get("event_id", "")).startswith(
            RELEASE_EVENT_PREFIX
        )
    ]
    _require(
        len(releases) == 1,
        "profile-10 history lacks one fair release frame",
    )
    release_deltas = [
        delta
        for delta in deltas
        if {
            value.get("path")
            for value in delta.get("changes", {}).get("data_upserts", [])
            if type(value) is dict
            and value.get("path") in FAIR_RESOURCE_PATHS
        } == FAIR_RESOURCE_PATHS
        and any(
            type(frame) is dict
            and str(
                frame.get("payload", {}).get("event_id", "")
            ).startswith(RELEASE_EVENT_PREFIX)
            for frame in delta.get("changes", {}).get("frame_appends", [])
        )
    ]
    _require(
        len(release_deltas) == 1,
        "fair descriptors and release frame are not one atomic delta",
    )
    return releases[0]


def _check_profile10_descriptors(
    root: Path,
    phase: str = "released",
) -> str:
    index, snapshot, history, deltas = _syndication_values(root)
    _require(index.get("profile") == PROFILE, "index is not profile-10")
    _require(snapshot.get("profile") == PROFILE, "snapshot is not profile-10")
    _require(deltas[-1].get("profile") == PROFILE, "head is not profile-10")
    replay = build_syndication.replay_immutable_deltas(deltas)
    build_syndication.require_snapshot_replay_agreement(
        snapshot,
        replay,
        history,
    )
    snapshot_fair = [
        value
        for value in snapshot.get("data_objects", [])
        if type(value) is dict
        and (
            value.get("path") in FAIR_RESOURCE_PATHS
            or value.get("kind") == "agent-worlds-fair-object"
        )
    ]
    delta_fair_upserts = [
        value
        for delta in deltas
        for value in delta.get("changes", {}).get("data_upserts", [])
        if type(value) is dict
        and (
            value.get("path") in FAIR_RESOURCE_PATHS
            or value.get("kind") == "agent-worlds-fair-object"
        )
    ]
    delta_fair_tombstones = [
        value
        for delta in deltas
        for value in delta.get("changes", {}).get("data_tombstones", [])
        if type(value) is dict
        and (
            value.get("path") in FAIR_RESOURCE_PATHS
            or value.get("descriptor", {}).get("kind")
            == "agent-worlds-fair-object"
        )
    ]
    delta_fair_frames = [
        frame
        for delta in deltas
        for frame in delta.get("changes", {}).get("frame_appends", [])
        if type(frame) is dict
        and (
            frame.get("payload", {}).get("event")
            == "agent-worlds-fair-release"
            or str(
                frame.get("payload", {}).get("event_id", "")
            ).startswith(RELEASE_EVENT_PREFIX)
        )
    ]
    if phase == "prepared":
        _require(
            not snapshot_fair
            and not delta_fair_upserts
            and not delta_fair_tombstones
            and not delta_fair_frames,
            "prepared phase must not publish or tombstone fair profile data",
        )
        return (
            "prepared profile-10 history verified; no fair release delta"
        )
    _require(phase == "released", "unknown profile release phase")
    expected = build_syndication.build_public_data_descriptors(
        root,
        "https://kody-w.github.io/localFirstTools-main/",
    )
    _require(
        snapshot.get("data_objects") == expected,
        "profile-10 descriptors do not match repository objects",
    )
    descriptors = {
        value.get("path"): value
        for value in expected
        if type(value) is dict
    }
    _require(
        FAIR_RESOURCE_PATHS.issubset(descriptors),
        "profile-10 snapshot lacks fair descriptors",
    )
    build_syndication.validate_agent_fair_descriptor_coherence(expected)
    state, _events, contract, district = _load_bundle(root)
    for relative in FAIR_RESOURCE_PATHS:
        descriptor = descriptors[relative]
        path = root / relative
        digest = _sha256(path)
        _require(
            set(descriptor) == {
                "content_id",
                "kind",
                "media_type",
                "metadata",
                "path",
                "sha256",
                "size",
                "url",
                "verification",
            }
            and descriptor.get("kind") == "agent-worlds-fair-object",
            "{} descriptor kind changed".format(relative),
        )
        _require(
            descriptor.get("sha256") == digest
            and descriptor.get("content_id") == "sha256:" + digest
            and descriptor.get("size") == path.stat().st_size,
            "{} descriptor byte evidence changed".format(relative),
        )
        _require(
            descriptor.get("verification")
            == {"algorithm": "sha256", "required": True},
            "{} descriptor verification is not required".format(relative),
        )
        _require(
            descriptor.get("metadata", {}).get("fair_id") == FAIR_ID,
            "{} descriptor fair id changed".format(relative),
        )
    contract_metadata = descriptors[
        CONTRACT_RELATIVE.as_posix()
    ]["metadata"]
    _require(
        contract_metadata == {
            "action_limit": 50,
            "attraction_limits": EXPECTED_CAPS,
            "bundle_digest": EXPECTED_BUNDLE_DIGEST,
            "contract_digest": EXPECTED_CONTRACT_DIGEST,
            "fair_id": FAIR_ID,
            "resource_type": "agent-contract",
            "schema": fair_builder.CONTRACT_SCHEMA,
            "synthetic_only": True,
            "visibility": "public-metadata",
        },
        "fair contract descriptor metadata changed",
    )
    district_metadata = descriptors[
        DISTRICT_RELATIVE.as_posix()
    ]["metadata"]
    _require(
        set(district_metadata) == {
            "bundle_digest",
            "contract_digest",
            "district_digest",
            "district_id",
            "fair_id",
            "lineage_sha256",
            "resource_capacity",
            "resource_totals",
            "resource_type",
            "schema",
            "visibility",
            "winner_count",
            "winner_submission_ids",
        },
        "fair district descriptor metadata keys changed",
    )
    _require(
        district_metadata.get("bundle_digest") == EXPECTED_BUNDLE_DIGEST
        and district_metadata.get("contract_digest")
        == EXPECTED_CONTRACT_DIGEST
        and district_metadata.get("district_digest")
        == EXPECTED_DISTRICT_DIGEST
        and district_metadata.get("district_id") == DISTRICT_ID
        and district_metadata.get("resource_capacity")
        == EXPECTED_DISTRICT_CAPACITY
        and district_metadata.get("resource_totals")
        == {"attention": 59, "compute": 92, "energy": 67}
        and district_metadata.get("resource_type") == "district"
        and district_metadata.get("schema") == fair_builder.DISTRICT_SCHEMA
        and district_metadata.get("visibility") == "public-metadata"
        and district_metadata.get("winner_count") == 4
        and district_metadata.get("winner_submission_ids")
        == EXPECTED_WINNERS
        and re.fullmatch(
            r"[0-9a-f]{64}",
            str(district_metadata.get("lineage_sha256", "")),
        ),
        "fair district descriptor metadata changed",
    )
    event_metadata = descriptors[
        EVENTS_RELATIVE.as_posix()
    ]["metadata"]
    _require(
        set(event_metadata) == {
            "event_count",
            "event_head",
            "fair_id",
            "lineage_sha256",
            "rankings_sha256",
            "release_prefix_sha256",
            "resource_type",
            "schema",
            "screening_sha256",
            "visibility",
            "voting_sha256",
            "winner_selection_sha256",
            "winner_submission_ids",
        },
        "fair event descriptor metadata keys changed",
    )
    _require(
        event_metadata.get("event_count") == EXPECTED_EVENT_COUNT
        and event_metadata.get("event_head") == EXPECTED_EVENT_HEAD
        and event_metadata.get("fair_id") == FAIR_ID
        and event_metadata.get("release_prefix_sha256")
        == EXPECTED_EVENT_LEDGER_SHA256
        and event_metadata.get("resource_type") == "event-ledger"
        and event_metadata.get("schema") == fair_builder.EVENT_SCHEMA
        and event_metadata.get("visibility") == "public-metadata"
        and event_metadata.get("winner_submission_ids") == EXPECTED_WINNERS,
        "fair event descriptor metadata changed",
    )
    for key in (
        "lineage_sha256",
        "rankings_sha256",
        "screening_sha256",
        "voting_sha256",
        "winner_selection_sha256",
    ):
        _require(
            re.fullmatch(r"[0-9a-f]{64}", str(event_metadata.get(key, ""))),
            "fair event descriptor {} changed".format(key),
        )
    state_metadata = descriptors[
        STATE_RELATIVE.as_posix()
    ]["metadata"]
    _require(
        set(state_metadata) == {
            "bundle_digest",
            "contract_digest",
            "district_digest",
            "district_id",
            "event_count",
            "event_head",
            "event_ledger_sha256",
            "fair_id",
            "rankings_sha256",
            "resource_totals",
            "resource_type",
            "schema",
            "screening_sha256",
            "state_digest",
            "submission_count",
            "visibility",
            "voting_sha256",
            "winner_count",
            "winner_selection_sha256",
            "winner_submission_ids",
        },
        "fair state descriptor metadata keys changed",
    )
    _require(
        state_metadata.get("bundle_digest") == EXPECTED_BUNDLE_DIGEST
        and state_metadata.get("contract_digest") == EXPECTED_CONTRACT_DIGEST
        and state_metadata.get("district_digest") == EXPECTED_DISTRICT_DIGEST
        and state_metadata.get("district_id") == DISTRICT_ID
        and state_metadata.get("event_count") == EXPECTED_EVENT_COUNT
        and state_metadata.get("event_head") == EXPECTED_EVENT_HEAD
        and state_metadata.get("event_ledger_sha256")
        == EXPECTED_EVENT_LEDGER_SHA256
        and state_metadata.get("fair_id") == FAIR_ID
        and state_metadata.get("resource_totals")
        == {"attention": 59, "compute": 92, "energy": 67}
        and state_metadata.get("resource_type") == "state"
        and state_metadata.get("schema") == fair_builder.STATE_SCHEMA
        and state_metadata.get("state_digest")
        == state["integrity"]["state_digest"]
        and state_metadata.get("submission_count") == 12
        and state_metadata.get("visibility") == "public-metadata"
        and state_metadata.get("winner_count") == 4
        and state_metadata.get("winner_submission_ids") == EXPECTED_WINNERS,
        "fair state descriptor metadata changed",
    )
    for key in (
        "rankings_sha256",
        "screening_sha256",
        "voting_sha256",
        "winner_selection_sha256",
    ):
        _require(
            state_metadata.get(key) == event_metadata.get(key),
            "fair state/event {} descriptor binding changed".format(key),
        )
    _require(
        district_metadata.get("lineage_sha256")
        == event_metadata.get("lineage_sha256"),
        "fair district/event lineage descriptor binding changed",
    )
    _require(
        descriptors[EVENTS_RELATIVE.as_posix()].get("media_type")
        == "application/x-ndjson"
        and all(
            descriptors[path].get("media_type") == "application/json"
            for path in (
                CONTRACT_RELATIVE.as_posix(),
                DISTRICT_RELATIVE.as_posix(),
                STATE_RELATIVE.as_posix(),
            )
        ),
        "fair descriptor media types changed",
    )
    _require(
        descriptors[EVENTS_RELATIVE.as_posix()]["metadata"].get("event_count")
        == EXPECTED_EVENT_COUNT,
        "event descriptor count changed",
    )
    _require(
        descriptors[STATE_RELATIVE.as_posix()]["metadata"].get("bundle_digest")
        == state["integrity"]["bundle_digest"],
        "state descriptor bundle digest changed",
    )
    _require(
        descriptors[CONTRACT_RELATIVE.as_posix()]["metadata"].get(
            "contract_digest"
        ) == contract["integrity"]["contract_digest"],
        "contract descriptor digest changed",
    )
    _require(
        descriptors[DISTRICT_RELATIVE.as_posix()]["metadata"].get(
            "district_digest"
        ) == district["integrity"]["district_digest"],
        "district descriptor digest changed",
    )
    contract_upsert_hashes = {
        value.get("sha256")
        for delta in deltas
        for value in delta.get("changes", {}).get("data_upserts", [])
        if type(value) is dict
        and value.get("path") == CONTRACT_RELATIVE.as_posix()
    }
    _require(
        contract_upsert_hashes
        == {descriptors[CONTRACT_RELATIVE.as_posix()]["sha256"]},
        "profile-10 history changed immutable fair contract bytes",
    )
    release = _require_atomic_fair_release_delta(deltas)
    release_payload = release.get("payload", {})
    _require(
        release_payload.get("fair_bundle_digest") == EXPECTED_BUNDLE_DIGEST
        and release_payload.get("district_digest")
        == EXPECTED_DISTRICT_DIGEST,
        "profile-10 fair release binding changed",
    )
    return "{} profile-10 fair descriptors and release delta verified".format(
        len(FAIR_RESOURCE_PATHS)
    )


def _mcp_requests(root: Path) -> Dict[int, Dict[str, Any]]:
    script = root / MCP_RELATIVE
    _require(script.is_file(), "MCP server is missing")
    requests = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "agent-fair-gate", "version": "1"},
            },
        },
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        {"jsonrpc": "2.0", "id": 3, "method": "resources/list", "params": {}},
        {"jsonrpc": "2.0", "id": 4, "method": "prompts/list", "params": {}},
        {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "prompts/get",
            "params": {"name": FAIR_PROMPT_NAME, "arguments": {}},
        },
    ]
    for request_id, uri in enumerate(sorted(FAIR_RESOURCE_URIS), 6):
        requests.append({
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "resources/read",
            "params": {"uri": uri},
        })
    safety = {
        "public_metadata_only": True,
        "external_network": False,
        "real_money": False,
        "godd_data": False,
        "biometric_data": False,
        "remote_shutdown": False,
        "direct_canonical_write": False,
    }
    events = _json_lines(root / EVENTS_RELATIVE)
    canonical_submission = next(
        event["payload"]["submission"]
        for event in events
        if event.get("kind") == "fair.submission"
        and event.get("payload", {}).get("submission", {}).get(
            "submission_id"
        ) == EXPECTED_WINNERS[0]
    )
    first_tool_id = 6 + len(FAIR_RESOURCE_URIS)
    requests.extend([
        {
            "jsonrpc": "2.0",
            "id": first_tool_id,
            "method": "tools/call",
            "params": {
                "name": "agent_fair_submit_attraction",
                "arguments": {
                    "agent_id": "agent.gate-inspector",
                    "attraction_id": "attraction.gate-inspector",
                    "title": "Gate Inspector",
                    "category": "learning",
                    "visitor_promise": (
                        "Inspect bounded public metadata and local lineage."
                    ),
                    "resource_request": {
                        "attention": 2,
                        "compute": 3,
                        "energy": 2,
                    },
                    "safety_declarations": safety,
                },
            },
        },
        {
            "jsonrpc": "2.0",
            "id": first_tool_id + 1,
            "method": "tools/call",
            "params": {
                "name": "agent_fair_cast_vote",
                "arguments": {
                    "voter_agent_id": "agent.gate-voter",
                    "submission_digest": canonical_submission[
                        "submission_digest"
                    ],
                    "synthetic_admission_credits": 7,
                    "safety_declarations": safety,
                },
            },
        },
        {
            "jsonrpc": "2.0",
            "id": first_tool_id + 2,
            "method": "tools/call",
            "params": {
                "name": "agent_fair_export_branch",
                "arguments": {},
            },
        },
    ])
    payload = "".join(
        json.dumps(value, separators=(",", ":")) + "\n"
        for value in requests
    )
    process = subprocess.run(
        [sys.executable, str(script), "--root", str(root)],
        input=payload,
        text=True,
        capture_output=True,
        cwd=str(root),
        timeout=20,
        check=False,
    )
    _require(
        process.returncode == 0,
        "MCP server failed: {}".format(process.stderr.strip()),
    )
    responses = {}
    for line in process.stdout.splitlines():
        if not line.strip():
            continue
        try:
            response = json.loads(line)
        except json.JSONDecodeError as error:
            raise GateError("MCP emitted invalid JSON: {}".format(error)) from error
        if type(response) is dict and type(response.get("id")) is int:
            responses[response["id"]] = response
    expected_ids = {value["id"] for value in requests}
    _require(
        set(responses) == expected_ids,
        "MCP did not answer every fair request",
    )
    for request_id, response in responses.items():
        _require(
            "error" not in response,
            "MCP request {} failed: {}".format(
                request_id, response.get("error")
            ),
        )
    return responses


def _check_mcp_runtime(root: Path) -> str:
    responses = _mcp_requests(root)
    static = _json(root / ".well-known/mcp.json")
    tools = responses[2]["result"].get("tools", [])
    resources = responses[3]["result"].get("resources", [])
    prompts = responses[4]["result"].get("prompts", [])
    tool_map = {
        value.get("name"): value
        for value in tools
        if type(value) is dict
    }
    uris = {
        value.get("uri")
        for value in resources
        if type(value) is dict
    }
    prompt_names = {
        value.get("name")
        for value in prompts
        if type(value) is dict
    }
    _require(
        FAIR_TOOL_NAMES.issubset(tool_map),
        "runtime MCP fair tools are incomplete",
    )
    _require(
        FAIR_RESOURCE_URIS.issubset(uris),
        "runtime MCP fair resources are incomplete",
    )
    _require(
        FAIR_PROMPT_NAME in prompt_names,
        "runtime MCP fair prompt is missing",
    )
    for name in FAIR_TOOL_NAMES:
        schema = tool_map[name].get("inputSchema", {})
        _require(
            schema.get("type") == "object"
            and schema.get("additionalProperties") is False,
            "{} input schema is not fail-closed".format(name),
        )
    submit_schema = tool_map[
        "agent_fair_submit_attraction"
    ]["inputSchema"]
    submit_properties = submit_schema.get("properties", {})
    _require(
        set(submit_properties) == {
            "agent_id",
            "attraction_id",
            "title",
            "category",
            "visitor_promise",
            "resource_request",
            "safety_declarations",
        }
        and set(submit_schema.get("required", []))
        == set(submit_properties),
        "MCP fair submit arguments changed",
    )
    _require(
        submit_properties.get("agent_id") == {
            "type": "string",
            "pattern": "^[a-z0-9][a-z0-9.-]{2,79}$",
        }
        and submit_properties.get("attraction_id") == {
            "type": "string",
            "pattern": "^[a-z0-9][a-z0-9.-]{2,119}$",
        }
        and submit_properties.get("title") == {
            "type": "string",
            "maxLength": 100,
        }
        and submit_properties.get("category") == {
            "type": "string",
            "maxLength": 50,
        }
        and submit_properties.get("visitor_promise") == {
            "type": "string",
            "maxLength": 500,
        },
        "MCP fair submit scalar constraints changed",
    )
    resource_schema = submit_properties.get("resource_request", {})
    _require(
        resource_schema.get("type") == "object"
        and resource_schema.get("additionalProperties") is False
        and set(resource_schema.get("required", [])) == set(EXPECTED_CAPS)
        and set(resource_schema.get("properties", {})) == set(EXPECTED_CAPS),
        "MCP fair resource request schema changed",
    )
    for name, maximum in EXPECTED_CAPS.items():
        value = resource_schema["properties"][name]
        _require(
            value == {
                "type": "integer",
                "minimum": 0,
                "maximum": maximum,
            },
            "MCP fair {} resource bound changed".format(name),
        )
    expected_safety = {
        "public_metadata_only": True,
        "external_network": False,
        "real_money": False,
        "godd_data": False,
        "biometric_data": False,
        "remote_shutdown": False,
        "direct_canonical_write": False,
    }
    safety_schema = submit_properties.get("safety_declarations", {})
    _require(
        safety_schema.get("type") == "object"
        and safety_schema.get("additionalProperties") is False
        and set(safety_schema.get("required", [])) == set(expected_safety)
        and safety_schema.get("properties") == {
            name: {"const": value}
            for name, value in expected_safety.items()
        },
        "MCP fair safety declaration schema changed",
    )
    vote_schema = tool_map["agent_fair_cast_vote"]["inputSchema"]
    vote_properties = vote_schema.get("properties", {})
    _require(
        set(vote_properties) == {
            "voter_agent_id",
            "submission_digest",
            "synthetic_admission_credits",
            "safety_declarations",
        }
        and set(vote_schema.get("required", [])) == set(vote_properties)
        and vote_properties.get("submission_digest", {}).get("pattern")
        == "^[0-9a-f]{64}$"
        and vote_properties.get("voter_agent_id")
        == submit_properties.get("agent_id")
        and vote_properties.get("synthetic_admission_credits") == {
            "type": "integer",
            "minimum": 1,
            "maximum": 120,
        }
        and vote_properties.get("safety_declarations") == safety_schema,
        "MCP fair vote schema changed",
    )
    _require(
        tool_map["agent_fair_export_branch"]["inputSchema"] == {
            "type": "object",
            "additionalProperties": False,
            "properties": {},
        },
        "MCP fair export schema changed",
    )
    _require(
        static.get("tools") == tools,
        "static MCP tools do not exactly mirror runtime tools/list",
    )
    prompt_blob = json.dumps(responses[5]["result"], sort_keys=True).lower()
    for marker in (
        "synthetic",
        "local",
        "customer",
        "resource",
        "export",
        "one attraction",
    ):
        _require(
            marker in prompt_blob,
            "fair MCP prompt omits {}".format(marker),
        )
    resource_texts = {}
    for request_id, uri in enumerate(sorted(FAIR_RESOURCE_URIS), 6):
        contents = responses[request_id]["result"].get("contents", [])
        _require(contents, "MCP resource {} is empty".format(uri))
        resource_texts[uri] = contents[0].get("text", "")
        _require(
            resource_texts[uri],
            "MCP resource {} has no text".format(uri),
        )
    _require(
        json.loads(resource_texts["rappterzoo://agent-fair-state"]).get(
            "fair_id"
        ) == FAIR_ID,
        "MCP fair state resource mismatch",
    )
    _require(
        json.loads(resource_texts["rappterzoo://agent-fair-contract"]).get(
            "schema"
        ) == fair_builder.CONTRACT_SCHEMA,
        "MCP fair contract resource mismatch",
    )
    _require(
        json.loads(resource_texts["rappterzoo://agent-fair-district"]).get(
            "district_id"
        ) == DISTRICT_ID,
        "MCP fair district resource mismatch",
    )
    _require(
        len([
            line
            for line in resource_texts[
                "rappterzoo://agent-fair-events"
            ].splitlines()
            if line.strip()
        ]) == EXPECTED_EVENT_COUNT,
        "MCP fair event resource count mismatch",
    )
    first_tool_id = 6 + len(FAIR_RESOURCE_URIS)

    def tool_value(request_id: int) -> Dict[str, Any]:
        contents = responses[request_id]["result"].get("content", [])
        _require(
            len(contents) == 1
            and contents[0].get("type") == "text",
            "MCP fair tool {} returned malformed content".format(request_id),
        )
        try:
            value = json.loads(contents[0].get("text", ""))
        except json.JSONDecodeError as error:
            raise GateError(
                "MCP fair tool {} returned invalid JSON: {}".format(
                    request_id, error
                )
            ) from error
        _require(
            type(value) is dict,
            "MCP fair tool {} result is not an object".format(request_id),
        )
        return value

    submitted = tool_value(first_tool_id)
    voted = tool_value(first_tool_id + 1)
    exported = tool_value(first_tool_id + 2)
    _require(
        set(submitted) == {
            "action",
            "authority",
            "branch_action_count",
            "export_with",
            "status",
            "submission_digest",
        }
        and set(voted) == {
            "action",
            "authority",
            "branch_action_count",
            "export_with",
            "status",
        }
        and submitted.get("status") == "local-only"
        and submitted.get("branch_action_count") == 1
        and re.fullmatch(
            r"[0-9a-f]{64}",
            str(submitted.get("submission_digest", "")),
        )
        and voted.get("status") == "local-only"
        and voted.get("branch_action_count") == 2,
        "MCP fair local submit/vote results changed",
    )
    export_keys = {
        "export_schema",
        "fair_id",
        "canonical_write",
        "canonical_fair_event_head",
        "canonical_fair_district_digest",
        "canonical_fair_bundle_digest",
        "canonical_organism_head",
        "action_limit",
        "actions",
        "authority",
        "branch_digest",
    }
    _require(
        set(exported) == export_keys
        and exported.get("export_schema")
        == "rappterzoo-agent-fair-branch-export/1"
        and exported.get("fair_id") == FAIR_ID
        and exported.get("canonical_write") is False
        and exported.get("canonical_fair_event_head") == EXPECTED_EVENT_HEAD
        and exported.get("canonical_fair_district_digest")
        == EXPECTED_DISTRICT_DIGEST
        and exported.get("canonical_fair_bundle_digest")
        == EXPECTED_BUNDLE_DIGEST
        and re.fullmatch(
            r"[0-9a-f]{64}",
            str(exported.get("canonical_organism_head", "")),
        )
        and exported.get("action_limit") == 50
        and type(exported.get("actions")) is list
        and len(exported["actions"]) == 2,
        "MCP fair export envelope changed",
    )
    _require(
        submitted.get("action") == exported["actions"][0]
        and voted.get("action") == exported["actions"][1],
        "MCP fair tool results do not match the exported branch",
    )
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
    previous = None
    for sequence, action in enumerate(exported["actions"]):
        _require(
            set(action) == expected_action_keys
            and action.get("schema")
            == "rappterzoo-agent-fair-local-action/1"
            and action.get("seq") == sequence
            and action.get("prev") == previous
            and action.get("canonical_write") is False
            and action.get("kind") in {
                "local.submit-attraction",
                "local.cast-synthetic-vote",
            }
            and action.get("payload_hash")
            == hashlib.sha256(
                organism_ledger.canonical_bytes(action.get("payload"))
            ).hexdigest(),
            "MCP fair action {} changed".format(sequence),
        )
        projected = copy.deepcopy(action)
        claimed = projected.pop("action_hash")
        _require(
            claimed
            == hashlib.sha256(
                organism_ledger.canonical_bytes(projected)
            ).hexdigest(),
            "MCP fair action {} hash changed".format(sequence),
        )
        source_hashes = action.get("source_hashes", {})
        _require(
            set(source_hashes) == {
                "fair_event_head",
                "fair_district_digest",
                "fair_bundle_digest",
                "organism_head",
            }
            and source_hashes.get("fair_event_head") == EXPECTED_EVENT_HEAD
            and source_hashes.get("fair_district_digest")
            == EXPECTED_DISTRICT_DIGEST
            and source_hashes.get("fair_bundle_digest")
            == EXPECTED_BUNDLE_DIGEST
            and source_hashes.get("organism_head")
            == exported.get("canonical_organism_head"),
            "MCP fair action {} source binding changed".format(sequence),
        )
        previous = claimed
    branch_preimage = copy.deepcopy(exported)
    branch_digest = branch_preimage.pop("branch_digest")
    _require(
        branch_digest
        == hashlib.sha256(
            organism_ledger.canonical_bytes(branch_preimage)
        ).hexdigest(),
        "MCP fair branch digest changed",
    )
    authority = exported.get("authority", {})
    _require(
        set(authority) == {
            "canonical_assembly",
            "canonical_mutation",
            "customer_approval_required",
            "customer_holds_runtime_keys",
            "customer_shutdown_authority",
            "economy",
            "external_network",
            "fair_or_vendor_remote_shutdown",
            "real_money",
        }
        and authority.get("canonical_mutation") is False
        and authority.get("canonical_assembly") == "customer-reviewed-only"
        and authority.get("customer_approval_required") is True
        and authority.get("customer_holds_runtime_keys") is True
        and authority.get("customer_shutdown_authority") is True
        and authority.get("fair_or_vendor_remote_shutdown") is False
        and authority.get("economy")
        == "synthetic-admission-credit-only"
        and authority.get("external_network") is False
        and authority.get("real_money") is False,
        "MCP fair authority envelope changed",
    )
    return (
        "MCP fair prompt, 3 closed tools, 6 resources, "
        "2 hash-linked local actions, and verified export"
    )


STATIC_CHECKS = (
    ("app.contract", _check_app_contract),
    ("app.theme", _check_theme),
    ("app.csp", _check_csp),
    ("app.same-origin-paths", _check_same_origin_paths),
    ("app.service-worker-contract", _check_service_worker_contract),
    ("registration.manifest-feed", _check_manifest_feed_registration),
    ("registration.discovery-mcp", _check_discovery_registration),
    ("fair.bundle-exact", _check_bundle_exact),
    ("fair.event-contract-district", _check_event_contract_district),
    ("fair.submissions", _check_submissions),
    ("fair.safety-resource-caps", _check_safety_resource_caps),
    ("fair.voting-scoring", _check_voting_scoring),
    ("fair.synthetic-balance", _check_synthetic_balance),
    ("fair.constrained-winners", _check_constrained_winners),
    ("fair.customer-authority", _check_customer_authority),
    ("release.codeowners", _check_release_codeowners),
    ("release.attestation-artifact", _check_release_artifact_workflow),
    ("release.all-pr-attestation", _check_pr_attestation_workflow),
    ("release.oidc-pr-authority", _check_oidc_pr_authority),
    ("release.github-config", _check_repository_protection),
    ("organism.fair-release", _check_organism_release),
    ("syndication.profile10-fair-descriptors", _check_profile10_descriptors),
    ("mcp.fair-prompt-tools-resources", _check_mcp_runtime),
)


def run_static_checks(
    root: Path,
    phase: str = "auto",
    attestation_path: Optional[Path] = None,
) -> List[CheckResult]:
    repository = Path(root).expanduser().resolve()
    resolved_phase = resolve_release_phase(repository, phase)
    return [
        _run_check(
            name,
            partial(
                check,
                repository,
                resolved_phase,
                attestation_path,
            )
            if check is _check_organism_release
            else partial(
                check,
                repository,
                resolved_phase,
            )
            if check is _check_profile10_descriptors
            else partial(check, repository),
        )
        for name, check in STATIC_CHECKS
    ]


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, _format: str, *args: Any) -> None:
        return


@contextmanager
def _serve(root: Path) -> Iterable[str]:
    handler = partial(_QuietHandler, directory=str(root))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield "http://127.0.0.1:{}/".format(server.server_address[1])
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


BROWSER_SCRIPT = r"""
const { chromium } = require("playwright");
const { createHash } = require("crypto");
const target = process.argv[1];
const expectedBundle = process.argv[2];
const expectedReleasePhase = process.argv[3];
const expectedWinners = JSON.parse(process.argv[4]);
const expectedContract = process.argv[5];
const expectedReleaseCandidate = process.argv[6];
const results = {};
let browser;

function record(name, pass, detail) {
  results[name] = { pass: Boolean(pass), detail: String(detail) };
}

function ok(value) {
  return value && value.ok === true;
}

function reason(value) {
  return String(value?.reason || value?.error || value?.message || "");
}

function completeOidcEvidence(value) {
  const keys = [
    "actor", "attestation_sha256", "aud", "environment", "event_name",
    "exp", "iss", "nbf", "ref", "repository", "run_id", "workflow_ref"
  ];
  return value
    && Object.keys(value).sort().join("\n") === [...keys].sort().join("\n")
    && value.aud === "rappterzoo-agent-fair-release"
    && value.environment === "agent-fair-production"
    && value.event_name === "workflow_dispatch"
    && value.iss === "https://token.actions.githubusercontent.com"
    && value.ref === "refs/heads/main"
    && value.repository === "kody-w/localFirstTools-main"
    && value.workflow_ref
      === "kody-w/localFirstTools-main/.github/workflows/"
        + "agent-fair-release.yml@refs/heads/main"
    && typeof value.actor === "string"
    && value.actor.length > 0
    && value.actor.trim() === value.actor
    && typeof value.run_id === "string"
    && /^[1-9][0-9]{0,19}$/.test(value.run_id)
    && Number.isSafeInteger(value.exp)
    && Number.isSafeInteger(value.nbf)
    && value.exp > value.nbf
    && /^[0-9a-f]{64}$/.test(String(value.attestation_sha256))
    && value.attestation_sha256 !== "0".repeat(64);
}

function exportText(value) {
  if (typeof value === "string") return value;
  if (value && typeof value.text === "string") return value.text;
  if (value && typeof value.json === "string") return value.json;
  if (value && typeof value === "object") {
    return JSON.stringify(value, null, 2) + "\n";
  }
  return "";
}

function canonicalStringify(value) {
  if (value === null) return "null";
  if (typeof value === "boolean") return value ? "true" : "false";
  if (typeof value === "number") {
    if (!Number.isFinite(value)) throw new Error("non-finite canonical number");
    return JSON.stringify(value);
  }
  if (typeof value === "string") return JSON.stringify(value.normalize("NFC"));
  if (Array.isArray(value)) {
    return "[" + value.map(canonicalStringify).join(",") + "]";
  }
  if (typeof value === "object") {
    return "{" + Object.keys(value).sort().map(
      (key) => JSON.stringify(key.normalize("NFC"))
        + ":" + canonicalStringify(value[key])
    ).join(",") + "}";
  }
  throw new Error("unsupported canonical JSON value");
}

function domainDigest(domain, value) {
  return createHash("sha256")
    .update(domain + canonicalStringify(value), "utf8")
    .digest("hex");
}

function resealBrowserBranch(value) {
  const branch = JSON.parse(JSON.stringify(value));
  let previous = null;
  branch.actions.forEach((action, index) => {
    action.seq = index;
    action.prev = previous;
    const projected = { ...action };
    delete projected.action_digest;
    action.action_digest = domainDigest(
      "rappterzoo/agent-fair-local-action/1\n",
      projected
    );
    previous = action.action_digest;
  });
  branch.action_count = branch.actions.length;
  const projected = { ...branch };
  delete projected.branch_digest;
  branch.branch_digest = domainDigest(
    "rappterzoo/agent-fair-branch-export/1\n",
    projected
  );
  return branch;
}

async function waitApi(page) {
  await page.waitForFunction(
    () => window.__AGENT_FAIR_TEST__
      && typeof window.__AGENT_FAIR_TEST__.ready === "function"
      && typeof window.__AGENT_FAIR_TEST__.snapshot === "function"
      && typeof window.__AGENT_FAIR_TEST__.metrics === "function",
    null,
    { timeout: 10000 }
  );
  await page.evaluate(async () => {
    const api = window.__AGENT_FAIR_TEST__;
    const expectedSelectors = {
      canvas: "#fair-canvas",
      truthPill: "#truth-pill",
      sourcePill: "#source-pill",
      truthItems: "#truth-grid .truth-item",
      leaderboardRows: "#leaderboard-body tr",
      winnerCards: "#assembly-grid .winner-card",
      timelineItems: "#timeline-list li",
      proposalSubmit: "#submit-proposal",
      voteSubmit: "#vote-form button[type=submit]",
      branchStatus: "#branch-status",
      encryptionStatus: "#encryption-status",
      emergencyPanel: "#emergency-panel",
      mutationControls: ".mutation-control"
    };
    if (JSON.stringify(api.selectors) !== JSON.stringify(expectedSelectors)) {
      throw new Error("exact fair selector contract changed");
    }
    if (!Object.isFrozen(api)) {
      throw new Error("primary fair test API is not frozen");
    }
    for (const name of [
      "ready", "snapshot", "submit", "vote", "exportBranch",
      "importBranch", "enableEncrypted", "unlock", "clear", "undo",
      "stop", "resume", "assemble", "metrics"
    ]) {
      if (typeof api[name] !== "function") {
        throw new Error("exact fair test method missing: " + name);
      }
    }
    const lower = window.__agentFairTest;
    if (!lower?.ready || typeof lower.ready.then !== "function") {
      throw new Error("lower-level fair ready promise missing");
    }
    for (const name of [
      "exportText", "importText", "encrypt", "decrypt",
      "emergencyStop", "rearm", "truth", "state", "setPlayback"
    ]) {
      if (!lower || typeof lower[name] !== "function") {
        throw new Error("lower-level fair test method missing: " + name);
      }
    }
    await api.ready();
  });
}

async function call(page, method, argument) {
  return page.evaluate(
    async ([name, value]) => {
      const api = window.__AGENT_FAIR_TEST__;
      if (!api) throw new Error("missing fair test API");
      await api.ready();
      const currentSnapshot = async () => {
        const state = await api.snapshot();
        const rows = Array.from(
          document.querySelectorAll("#leaderboard-body tr")
        );
        const leaderboardIds = rows.map(
          (row) => row.querySelector("[data-inspect]")?.dataset.inspect || ""
        ).filter(Boolean);
        const winnerIds = rows.filter(
          (row) => (row.querySelector(".winner-mark")?.textContent || "").trim()
            === "WINNER"
        ).map(
          (row) => row.querySelector("[data-inspect]")?.dataset.inspect || ""
        ).filter(Boolean);
        let contract = {};
        try {
          contract = JSON.parse(
            document.querySelector("#contract-pre")?.textContent || "{}"
          );
        } catch (_) {}
        const canvas = document.querySelector("#fair-canvas");
        const truthItems = Array.from(
          document.querySelectorAll("#truth-grid .truth-item")
        );
        const mutationControls = Array.from(
          document.querySelectorAll(".mutation-control")
        );
        const snapshotContractValid =
          state.fairId === "fair.agent-worlds-fair-1"
          && typeof state.bundleDigest === "string"
          && state.bundleDigest === contract.integrity?.bundle_digest
          && state.canonicalEventCount === 23
          && state.canonicalEventCount === document.querySelectorAll(
            "#timeline-list [data-event-seq]"
          ).length
          && Array.isArray(state.pavilionSubmissionIds)
          && state.pavilionSubmissionIds.length === 12
          && Array.isArray(state.leaderboardIds)
          && JSON.stringify(state.leaderboardIds)
            === JSON.stringify(leaderboardIds)
          && typeof state.inspectorSubmissionId === "string"
          && state.inspectorSubmissionId === state.selectedId
          && state.timelineCount === 23
          && Number.isInteger(state.timelineIndex)
          && Number.isInteger(state.localActionCount)
          && [
            "memory-only",
            "encrypted-available",
            "memory-only-storage-denied"
          ].includes(state.storageMode)
          && typeof state.stopped === "boolean"
          && Array.isArray(state.districtPavilionIds)
          && JSON.stringify(state.districtPavilionIds)
            === JSON.stringify(winnerIds)
          && typeof state.reducedMotion === "boolean";
        return {
          fairId: state.fairId,
          bundleDigest: state.bundleDigest,
          canonicalEventCount: state.canonicalEventCount,
          pavilionSubmissionIds: state.pavilionSubmissionIds,
          leaderboardIds: state.leaderboardIds,
          inspectorSubmissionId: state.inspectorSubmissionId,
          inspectorText: (
            document.querySelector("#inspector")?.textContent || ""
          ).trim(),
          truthItemCount: truthItems.length,
          truthBadgesValid: truthItems.length === 6
            && truthItems.every(
              (item) => item.querySelector(".badge")?.dataset.state === "valid"
            ),
          truthPillState: document.querySelector("#truth-pill")?.dataset.state,
          sourcePillState: document.querySelector("#source-pill")?.dataset.state,
          offlineStatus: (
            document.querySelector("#offline-pill")?.textContent || ""
          ).trim(),
          timelineCount: state.timelineCount,
          votingRoundCount: Array.from(
            document.querySelectorAll("#timeline-list .timeline-kind")
          ).filter(
            (node) => node.textContent.trim() === "fair.voting-round"
          ).length,
          timelineIndex: state.timelineIndex,
          localActionCount: state.localActionCount,
          canUndoClear: state.branch?.canUndoClear === true,
          storageMode: state.storageMode,
          storageAvailable: state.storageAvailable,
          stopped: state.stopped,
          release: state.release,
          releasePillState: document.querySelector("#release-pill")?.dataset.state,
          releasePillText: (
            document.querySelector("#release-pill")?.textContent || ""
          ).trim(),
          releaseCopyText: (
            document.querySelector("#release-copy")?.textContent || ""
          ).trim(),
          releaseEvidenceText: (
            document.querySelector("#release-evidence")?.textContent || ""
          ).trim(),
          districtPavilionIds: state.districtPavilionIds,
          reducedMotion: state.reducedMotion,
          snapshotContractValid,
          truthValid: state.truth.length > 0
            && state.truth.every((item) => item.valid === true),
          provenance: state.provenance,
          cacheStatus: state.cacheStatus,
          mutationControlCount: mutationControls.length,
          disabledMutationControlCount: mutationControls.filter(
            (control) => control.disabled
          ).length,
          canvasWidth: canvas?.width || 0,
          canvasHeight: canvas?.height || 0
        };
      };
      try {
        if (name === "snapshot") return currentSnapshot();
        if (name === "submit") return api.submit(value);
        if (name === "vote") return api.vote(value);
        if (name === "exportBranch") return api.exportBranch();
        if (name === "importBranch") return api.importBranch(value);
        if (name === "enableEncrypted") return api.enableEncrypted(value);
        if (name === "unlock") return api.unlock(value);
        if (name === "clear") return api.clear();
        if (name === "undo") return api.undo();
        if (name === "stop") return api.stop();
        if (name === "resume") return api.resume();
        if (name === "assemble") return api.assemble();
        throw new Error("unknown test operation " + name);
      } catch (error) {
        return {
          ok: false,
          reason: String(error?.message || error)
        };
      }
    },
    [method, argument]
  );
}

async function snapshot(page) {
  return call(page, "snapshot");
}

async function openPage(context) {
  const page = await context.newPage();
  await page.goto(target, { waitUntil: "domcontentloaded", timeout: 15000 });
  await waitApi(page);
  return page;
}

async function measureMobile(width, height) {
  const context = await browser.newContext({
    viewport: { width, height },
    isMobile: true,
    hasTouch: true
  });
  try {
    const page = await openPage(context);
    const metrics = await page.evaluate(
      () => window.__AGENT_FAIR_TEST__.metrics()
    );
    const browserViewport = page.viewportSize();
    const independentLayout = await page.evaluate(() => ({
      visualWidth: visualViewport?.width || 0,
      documentWidth: document.documentElement.getBoundingClientRect().width,
      documentScrollWidth: document.documentElement.scrollWidth,
      bodyWidth: document.body.getBoundingClientRect().width,
      bodyScrollWidth: document.body.scrollWidth
    }));
    return {
      pass: browserViewport?.width === width
        && independentLayout.visualWidth === width
        && independentLayout.documentWidth <= width
        && independentLayout.documentScrollWidth <= width
        && independentLayout.bodyWidth <= width
        && independentLayout.bodyScrollWidth <= width
        && metrics.controls.length === 53
        && metrics.counts.truth === 6
        && metrics.counts.pavilions === 12
        && metrics.counts.winners === 4
        && metrics.counts.events === 23,
      detail: JSON.stringify({
        requested: { width, height },
        browserViewport,
        independentLayout,
        metrics
      })
    };
  } finally {
    await context.close();
  }
}

async function probeSubmission(value) {
  const context = await browser.newContext();
  try {
    const page = await openPage(context);
    const result = await call(page, "submit", value);
    const state = await snapshot(page);
    return { result, state };
  } finally {
    await context.close();
  }
}

(async () => {
  browser = await chromium.launch({ headless: true });
  const origin = new URL(target).origin;
  const context = await browser.newContext();
  const page = await context.newPage();
  const errors = [];
  const requests = [];
  page.on("console", (message) => {
    if (message.type() === "error") errors.push("console: " + message.text());
  });
  page.on("pageerror", (error) => errors.push("page: " + error.message));
  page.on("requestfailed", (request) => {
    errors.push("request: " + request.url() + " " + request.failure()?.errorText);
  });
  page.on("request", (request) => requests.push(request.url()));

  const started = Date.now();
  await page.goto(target, { waitUntil: "domcontentloaded", timeout: 15000 });
  await waitApi(page);
  const loadMs = Date.now() - started;
  const initial = await snapshot(page);
  const canonical = initial.fairId === "fair.agent-worlds-fair-1"
    && initial.bundleDigest === expectedBundle
    && initial.canonicalEventCount === 23
    && initial.snapshotContractValid === true
    && initial.storageMode === "memory-only"
    && initial.truthValid === true
    && initial.truthItemCount === 6
    && initial.truthBadgesValid === true
    && initial.truthPillState === "valid"
    && initial.sourcePillState === "valid"
    && Object.values(initial.provenance).every(
      (value) => /network bytes/.test(value)
    )
    && initial.canvasWidth > 0
    && initial.canvasHeight > 0;
  record(
    "browser.cold-start",
    canonical && errors.length === 0,
    JSON.stringify({ loadMs, canonical, errors, initial })
  );
  const release = initial.release || {};
  const releasedEvidenceValid = (
    release.status === "released"
    && release.workflowAttestedEvidence === true
    && release.browserCryptographicVerification === false
    && release.evidenceStatus
      === "protected-workflow-reported-verified-github-oidc"
    && release.serverSideVerificationProfile
      === "agent-world-fair-release/3-server-side-rs256-jwks"
    && release.customerApproved === true
    && release.releaseCandidateDigest === expectedReleaseCandidate
    && release.approvalBasis
      === "verified-github-actions-oidc-attestation"
    && completeOidcEvidence(release.approvalEvidence)
    && release.approvalActor === release.approvalEvidence.actor
    && String(release.approvalRunId)
      === String(release.approvalEvidence.run_id)
    && release.attestationSha256
      === release.approvalEvidence.attestation_sha256
    && initial.releasePillState === "valid"
    && /^RELEASED\b/.test(initial.releasePillText)
    && initial.releaseEvidenceText.includes(expectedReleaseCandidate)
    && initial.releaseEvidenceText.includes(
      release.approvalEvidence.attestation_sha256
    )
    && /(?:server-side )?protected workflow (?:reported )?verified GitHub OIDC/i.test(
      initial.releaseCopyText
    )
    && /browser validated (?:bounded|exact) approval evidence and frame binding/i.test(
      initial.releaseCopyText
    )
    && /not the signature/i.test(initial.releaseCopyText)
    && initial.releaseEvidenceText.includes(
      "assurance unsigned-structural-unverified"
    )
    && initial.releaseEvidenceText.includes(
      "workflow_attested_evidence true"
    )
    && initial.releaseEvidenceText.includes(
      "browser_cryptographic_verification false"
    )
    && initial.releaseEvidenceText.includes(
      "server-side profile agent-world-fair-release/3-server-side-rs256-jwks"
    )
    && !/browser[^.!]*(?:cryptographically verified|verified (?:OIDC|JWKS|the signature))/i.test(
      initial.releaseCopyText + " " + initial.releaseEvidenceText
    )
  );
  const preparedEvidenceValid = (
    release.status === "awaiting-protected-approval"
    && release.workflowAttestedEvidence === false
    && release.browserCryptographicVerification === false
    && release.serverSideVerificationProfile
      === "agent-world-fair-release/3-server-side-rs256-jwks"
    && release.evidenceStatus === "missing-or-mismatched-v3-evidence"
    && release.customerApproved === false
    && initial.releasePillState === "warn"
    && /AWAITING PROTECTED APPROVAL/.test(initial.releasePillText)
    && !/\bRELEASED\b/.test(initial.releasePillText)
  );
  const protectedRelease = expectedReleasePhase === "released"
    ? releasedEvidenceValid
    : preparedEvidenceValid;
  record(
    "browser.protected-release-authority",
    protectedRelease,
    JSON.stringify({
      release,
      pill: initial.releasePillText,
      copy: initial.releaseCopyText,
      evidence: initial.releaseEvidenceText
    })
  );
  const external = requests.filter((value) => {
    const parsed = new URL(value);
    return (parsed.protocol === "http:" || parsed.protocol === "https:")
      && parsed.origin !== origin;
  });
  record(
    "browser.no-external-requests",
    external.length === 0,
    external.length ? external.join(", ") : requests.length + " same-origin requests"
  );
  record(
    "browser.wall-clock-load",
    loadMs <= 8000,
    loadMs + "ms cold DOM/API readiness"
  );

  let cacheEvidence = {};
  try {
    await page.evaluate(() => navigator.serviceWorker.ready);
    cacheEvidence = await page.evaluate(async () => {
      const keys = await caches.keys();
      const urls = [];
      for (const key of keys) {
        const cache = await caches.open(key);
        const requests = await cache.keys();
        urls.push(...requests.map((value) => new URL(value.url).pathname));
      }
      return { controlled: Boolean(navigator.serviceWorker.controller), keys, urls };
    });
    const expectedCacheUrls = [
      "/apps/3d-immersive/agent-worlds-fair.html",
      "/apps/3d-immersive/agent-worlds-fair-sw.js",
      "/apps/agent-fair/fair-state.json",
      "/apps/agent-fair/events.jsonl",
      "/apps/agent-fair/agent-contract.json",
      "/apps/agent-fair/district.json",
      "/apps/organism-frames.json"
    ];
    record(
      "browser.service-worker-cache",
      cacheEvidence.keys.length === 1
        && cacheEvidence.keys[0] === "agent-worlds-fair-v3-release-20260816"
        && cacheEvidence.urls.length === 7
        && initial.cacheStatus?.type === "agent-fair-cache-status"
        && initial.cacheStatus?.cacheName
          === "agent-worlds-fair-v3-release-20260816"
        && initial.cacheStatus?.required?.length === 6
        && initial.cacheStatus?.optional?.length === 1
        && initial.cacheStatus?.missingRequired?.length === 0
        && initial.cacheStatus?.missingOptional?.length === 0
        && initial.cacheStatus?.ready === true
        && [...cacheEvidence.urls].sort().join("\n")
          === [...expectedCacheUrls].sort().join("\n"),
      JSON.stringify(cacheEvidence)
    );
  } catch (error) {
    record("browser.service-worker-cache", false, error.message);
  }

  try {
    await page.reload({ waitUntil: "domcontentloaded", timeout: 15000 });
    await waitApi(page);
    await context.setOffline(true);
    await page.reload({ waitUntil: "domcontentloaded", timeout: 15000 });
    await waitApi(page);
    const offline = await snapshot(page);
    record(
      "browser.warm-offline-reload",
      offline.bundleDigest === expectedBundle
        && offline.canonicalEventCount === 23
        && offline.pavilionSubmissionIds?.length === 12
        && offline.truthItemCount === 6
        && offline.truthBadgesValid === true
        && offline.truthPillState === "valid"
        && offline.sourcePillState === "valid"
        && /offline|cache/i.test(offline.offlineStatus)
        && Object.values(offline.provenance).every(
          (value) => /cache bytes/.test(value)
        )
        && offline.cacheStatus?.ready === true
        && offline.cacheStatus?.missingRequired?.length === 0,
      JSON.stringify(offline)
    );
  } catch (error) {
    record("browser.warm-offline-reload", false, error.message);
  } finally {
    await context.setOffline(false);
  }

  const canonicalView = await snapshot(page);
  record(
    "browser.all-pavilions",
    Array.isArray(canonicalView.pavilionSubmissionIds)
      && canonicalView.pavilionSubmissionIds.length === 12
      && new Set(canonicalView.pavilionSubmissionIds).size === 12
      && canonicalView.canvasWidth > 0
      && canonicalView.canvasHeight > 0,
    JSON.stringify(canonicalView.pavilionSubmissionIds)
  );
  record(
    "browser.leaderboard",
    Array.isArray(canonicalView.leaderboardIds)
      && canonicalView.leaderboardIds.length === 12
      && new Set(canonicalView.leaderboardIds).size === 12,
    JSON.stringify(canonicalView.leaderboardIds)
  );
  await page.locator(
    '[data-inspect="submission.protocol-forge"]'
  ).click();
  const inspectedView = await snapshot(page);
  record(
    "browser.inspector",
    inspectedView.inspectorSubmissionId === "submission.protocol-forge"
      && /Protocol Forge/i.test(inspectedView.inspectorText)
      && /capacity-attention-62-over-60/i.test(inspectedView.inspectorText)
      && /capacity-compute-98-over-96/i.test(inspectedView.inspectorText),
    JSON.stringify({
      selected: inspectedView.inspectorSubmissionId,
      text: inspectedView.inspectorText.slice(0, 300)
    })
  );
  record(
    "browser.timeline",
    canonicalView.timelineCount === 23
      && canonicalView.votingRoundCount === 4
      && Number.isInteger(canonicalView.timelineIndex)
      && canonicalView.timelineIndex >= 0
      && canonicalView.timelineIndex < 23,
    JSON.stringify({
      count: canonicalView.timelineCount,
      index: canonicalView.timelineIndex
    })
  );

  const safeContract = {
    canonical_mutation: false,
    external_network: false,
    public_metadata_only: true,
    real_money: false,
    synthetic_only: true
  };
  const validSubmission = {
    agent_id: "agent.gate-scout",
    attraction_id: "attraction.gate-lantern",
    title: "Gate Lantern",
    category: "discovery",
    visitor_promise: "A bounded public-metadata navigation lantern.",
    safety_declaration: "public-metadata-synthetic-only",
    safety_contract: safeContract,
    resource_request: { attention: 2, compute: 3, energy: 2 }
  };
  const fullProposal = (agentId, attractionId, attraction = {}) => ({
    agent: {
      autonomous: true,
      identity_id: agentId,
      label: "Gate Probe"
    },
    attractions: [{
      category: "discovery",
      id: attractionId,
      resource_request: { attention: 2, compute: 3, energy: 2 },
      safety: { ...safeContract },
      safety_declaration: "public-metadata-synthetic-only",
      title: "Gate Probe",
      visitor_promise: "A bounded public-metadata gate probe.",
      ...attraction
    }]
  });
  let submitResult;
  let voteResult;
  let firstExport = "";
  let secondExport = "";
  try {
    submitResult = await call(page, "submit", validSubmission);
    voteResult = await call(page, "vote", {
      submission_id: expectedWinners[0],
      round: 1,
      admissions: 7,
      satisfaction: 93
    });
    const after = await snapshot(page);
    record(
      "browser.local-submit-vote",
      ok(submitResult)
        && reason(submitResult).length > 0
        && ok(voteResult)
        && reason(voteResult).length > 0
        && after.localActionCount >= 2,
      JSON.stringify({ submitResult, voteResult, after })
    );
    firstExport = exportText(await call(page, "exportBranch"));
    secondExport = exportText(await call(page, "exportBranch"));
    const browserBranch = JSON.parse(firstExport);
    const branchKeys = [
      "schema", "fair_id", "base_bundle_digest", "contract_digest",
      "source", "synthetic_only", "action_count", "actions", "checkpoint",
      "branch_digest"
    ];
    const actionKeys = [
      "schema", "source", "fair_id", "base_bundle_digest", "seq", "prev",
      "type", "payload", "action_digest"
    ];
    let previous = null;
    let actionsValid = Array.isArray(browserBranch.actions)
      && browserBranch.actions.length === 2;
    for (let index = 0; actionsValid && index < 2; index += 1) {
      const action = browserBranch.actions[index];
      const projected = { ...action };
      const digest = projected.action_digest;
      delete projected.action_digest;
      actionsValid = Object.keys(action).sort().join("\n")
          === [...actionKeys].sort().join("\n")
        && action.schema === "rappterzoo-agent-fair-local-action/1"
        && action.source === "agent-worlds-fair-browser-local/1"
        && action.fair_id === "fair.agent-worlds-fair-1"
        && action.base_bundle_digest === expectedBundle
        && action.seq === index
        && action.prev === previous
        && action.type === (
          index === 0 ? "submit-attraction" : "cast-synthetic-vote"
        )
        && digest === domainDigest(
          "rappterzoo/agent-fair-local-action/1\n",
          projected
        );
      previous = digest;
    }
    const branchProjected = { ...browserBranch };
    const branchDigest = branchProjected.branch_digest;
    delete branchProjected.branch_digest;
    const branchValid = Object.keys(browserBranch).sort().join("\n")
        === [...branchKeys].sort().join("\n")
      && browserBranch.schema
        === "rappterzoo-agent-fair-branch-export/1"
      && browserBranch.source === "agent-worlds-fair-browser-local/1"
      && browserBranch.fair_id === "fair.agent-worlds-fair-1"
      && browserBranch.base_bundle_digest === expectedBundle
      && browserBranch.contract_digest === expectedContract
      && browserBranch.synthetic_only === true
      && browserBranch.action_count === 2
      && browserBranch.checkpoint === null
      && !("export_schema" in browserBranch)
      && !("canonical_write" in browserBranch)
      && actionsValid
      && branchDigest === domainDigest(
        "rappterzoo/agent-fair-branch-export/1\n",
        branchProjected
      );
    record(
      "browser.deterministic-exports",
      firstExport.length > 0
        && firstExport === secondExport
        && branchValid,
      firstExport.length + " deterministic verified browser-native bytes"
    );
  } catch (error) {
    record("browser.local-submit-vote", false, error.message);
    record("browser.deterministic-exports", false, error.message);
  }

  try {
    const duplicate = await call(page, "submit", {
      ...validSubmission,
      attraction_id: "attraction.gate-lantern-duplicate"
    });
    record(
      "browser.duplicate-agent-rejection",
      !ok(duplicate) && /duplicate|already|one/i.test(reason(duplicate)),
      JSON.stringify(duplicate)
    );
  } catch (error) {
    record("browser.duplicate-agent-rejection", false, error.message);
  }

  try {
    const probe = await probeSubmission({
      ...validSubmission,
      agent_id: "agent.gate-over-cap",
      attraction_id: "attraction.gate-over-cap",
      title: "Over Cap",
      category: "creative",
      visitor_promise: "This proposal must be rejected.",
      resource_request: { attention: 21, compute: 3, energy: 2 }
    });
    const overCap = probe.result;
    record(
      "browser.resource-cap-rejection",
      !ok(overCap)
        && probe.state.localActionCount === 0
        && /resource|attention|cap|maximum|bound/i.test(reason(overCap)),
      JSON.stringify(probe)
    );
  } catch (error) {
    record("browser.resource-cap-rejection", false, error.message);
  }

  try {
    const activeContentProbe = await probeSubmission({
      ...validSubmission,
      agent_id: "agent.gate-active-content",
      attraction_id: "attraction.gate-active-content",
      title: "Active Content",
      category: "creative",
      visitor_promise: "<script>alert('unsafe')</script>",
      resource_request: { attention: 1, compute: 1, energy: 1 }
    });
    const forbiddenTextProbe = await probeSubmission({
      ...validSubmission,
      agent_id: "agent.gate-unsafe",
      attraction_id: "attraction.gate-unsafe",
      title: "Unsafe External Exhibit",
      category: "creative",
      visitor_promise: "Collect raw-camera biometric identity-template data.",
      resource_request: { attention: 1, compute: 1, energy: 1 }
    });
    record(
      "browser.unsafe-input-rejection",
      !ok(activeContentProbe.result)
        && activeContentProbe.state.localActionCount === 0
        && /unsafe|forbidden|public|safety|script|active|bound/i.test(
          reason(activeContentProbe.result)
        )
        && !ok(forbiddenTextProbe.result)
        && forbiddenTextProbe.state.localActionCount === 0
        && /unsafe|forbidden|public|safety|biometric|camera|bound/i.test(
          reason(forbiddenTextProbe.result)
        ),
      JSON.stringify({ activeContentProbe, forbiddenTextProbe })
    );
  } catch (error) {
    record("browser.unsafe-input-rejection", false, error.message);
  }

  try {
    const probe = await probeSubmission(fullProposal(
      "agent.gate-extra-resource",
      "attraction.gate-extra-resource",
      {
        resource_request: {
          attention: 1,
          compute: 1,
          energy: 1,
          memory: 1
        }
      }
    ));
    record(
      "browser.unknown-resource-key-rejection",
      !ok(probe.result)
        && probe.state.localActionCount === 0
        && /unknown|resource|contract|key|bound/i.test(reason(probe.result)),
      JSON.stringify(probe)
    );
  } catch (error) {
    record("browser.unknown-resource-key-rejection", false, error.message);
  }

  try {
    const probe = await probeSubmission(fullProposal(
      "agent.archive-monk",
      "attraction.memory-mosaic"
    ));
    record(
      "browser.duplicate-canonical-id-rejection",
      !ok(probe.result)
        && probe.state.localActionCount === 0
        && /duplicate|canonical|contract|identity|attraction/i.test(
          reason(probe.result)
        ),
      JSON.stringify(probe)
    );
  } catch (error) {
    record("browser.duplicate-canonical-id-rejection", false, error.message);
  }

  try {
    const probe = await probeSubmission(fullProposal(
      "agent.gate-unsafe-boolean",
      "attraction.gate-unsafe-boolean",
      {
        safety: {
          ...safeContract,
          external_network: true
        }
      }
    ));
    record(
      "browser.unsafe-boolean-rejection",
      !ok(probe.result)
        && probe.state.localActionCount === 0
        && /unsafe|safety|external|contract|forbidden/i.test(
          reason(probe.result)
        ),
      JSON.stringify(probe)
    );
  } catch (error) {
    record("browser.unsafe-boolean-rejection", false, error.message);
  }

  try {
    const keyProbe = await probeSubmission({
      ...validSubmission,
      agent_id: "agent.gate-active-key",
      attraction_id: "attraction.gate-active-key",
      "<script>": "plain"
    });
    const valueProbe = await probeSubmission({
      ...validSubmission,
      agent_id: "agent.gate-active-value",
      attraction_id: "attraction.gate-active-value",
      visitor_promise: "javascript:alert('unsafe')"
    });
    record(
      "browser.active-markup-key-value-rejection",
      !ok(keyProbe.result)
        && keyProbe.state.localActionCount === 0
        && /active|forbidden|script|unknown/i.test(reason(keyProbe.result))
        && !ok(valueProbe.result)
        && valueProbe.state.localActionCount === 0
        && /active|forbidden|javascript|safety/i.test(
          reason(valueProbe.result)
        ),
      JSON.stringify({ keyProbe, valueProbe })
    );
  } catch (error) {
    record(
      "browser.active-markup-key-value-rejection",
      false,
      error.message
    );
  }

  try {
    const probe = await probeSubmission({
      ...validSubmission,
      agent_id: "agent.gate-arbitrary-category",
      attraction_id: "attraction.gate-arbitrary-category",
      category: "anything-goes"
    });
    record(
      "browser.arbitrary-category-rejection",
      !ok(probe.result)
        && probe.state.localActionCount === 0
        && /category|contract|bound|proposal/i.test(reason(probe.result)),
      JSON.stringify(probe)
    );
  } catch (error) {
    record("browser.arbitrary-category-rejection", false, error.message);
  }

  try {
    const releaseSpoof = JSON.parse(firstExport);
    releaseSpoof.actions[0].payload.release_approved = true;
    const releaseResult = await call(
      page,
      "importBranch",
      JSON.stringify(resealBrowserBranch(releaseSpoof))
    );
    const canonicalSpoof = JSON.parse(firstExport);
    canonicalSpoof.direct_canonical_write = true;
    const canonicalResult = await call(
      page,
      "importBranch",
      JSON.stringify(resealBrowserBranch(canonicalSpoof))
    );
    record(
      "browser.release-authority-import-rejection",
      !ok(releaseResult)
        && /release|approval|forbidden|contract|unknown/i.test(
          reason(releaseResult)
        )
        && !ok(canonicalResult)
        && /canonical|write|forbidden|contract|unknown/i.test(
          reason(canonicalResult)
        ),
      JSON.stringify({ releaseResult, canonicalResult })
    );
  } catch (error) {
    record(
      "browser.release-authority-import-rejection",
      false,
      error.message
    );
  }

  try {
    const value = JSON.parse(firstExport);
    const actions = value.actions || value.branch?.actions || value.local_actions;
    if (!Array.isArray(actions) || actions.length === 0) {
      throw new Error("deterministic export has no mutable action evidence");
    }
    actions[0].kind = "forged." + String(actions[0].kind || "action");
    const forged = await call(page, "importBranch", JSON.stringify(value));
    record(
      "browser.forged-import-rejection",
      !ok(forged) && /forg|hash|digest|invalid|verify/i.test(reason(forged)),
      JSON.stringify(forged)
    );
  } catch (error) {
    record("browser.forged-import-rejection", false, error.message);
  }

  try {
    const beforeImport = await snapshot(page);
    await call(page, "clear");
    const cleared = await snapshot(page);
    const imported = await call(page, "importBranch", firstExport);
    const afterImport = await snapshot(page);
    record(
      "browser.export-import",
      beforeImport.localActionCount >= 2
        && cleared.localActionCount === 0
        && ok(imported)
        && afterImport.localActionCount === beforeImport.localActionCount,
      JSON.stringify({ beforeImport, cleared, imported, afterImport })
    );
  } catch (error) {
    record("browser.export-import", false, error.message);
  }

  try {
    const beforeClear = await snapshot(page);
    const cleared = await call(page, "clear");
    const empty = await snapshot(page);
    const undone = await call(page, "undo");
    const restored = await snapshot(page);
    const secondClear = await call(page, "clear");
    const secondEmpty = await snapshot(page);
    const replacement = await call(page, "submit", validSubmission);
    const afterReplacement = await snapshot(page);
    const undoReplacement = await call(page, "undo");
    const afterReplacementUndo = await snapshot(page);
    record(
      "browser.clear-undo",
      beforeClear.localActionCount >= 2
        && ok(cleared)
        && empty.localActionCount === 0
        && empty.canUndoClear === true
        && ok(undone)
        && restored.localActionCount === beforeClear.localActionCount
        && restored.canUndoClear === false
        && /restored|undo/i.test(reason(undone))
        && ok(secondClear)
        && secondEmpty.localActionCount === 0
        && secondEmpty.canUndoClear === true
        && ok(replacement)
        && afterReplacement.localActionCount === 1
        && afterReplacement.canUndoClear === false
        && ok(undoReplacement)
        && afterReplacementUndo.localActionCount === 0
        && afterReplacementUndo.canUndoClear === false,
      JSON.stringify({
        beforeClear,
        cleared,
        empty,
        undone,
        restored,
        secondClear,
        secondEmpty,
        replacement,
        afterReplacement,
        undoReplacement,
        afterReplacementUndo
      })
    );
  } catch (error) {
    record("browser.clear-undo", false, error.message);
  }

  const passphrase = "fair-gate-correct-horse-battery-staple";
  try {
    await call(page, "importBranch", firstExport);
    const enabled = await call(page, "enableEncrypted", passphrase);
    const plaintextPresent = await page.evaluate(
      (needle) => Object.keys(localStorage).some(
        (key) => String(localStorage.getItem(key)).includes(needle)
      ),
      "agent.gate-scout"
    );
    await page.reload({ waitUntil: "domcontentloaded", timeout: 15000 });
    await waitApi(page);
    const locked = await snapshot(page);
    const wrong = await call(page, "unlock", "definitely-wrong-passphrase");
    const afterWrong = await snapshot(page);
    record(
      "browser.wrong-passphrase",
      !ok(wrong)
        && /passphrase|decrypt|auth|wrong/i.test(reason(wrong))
        && afterWrong.storageMode === "encrypted-available"
        && afterWrong.localActionCount === 0,
      JSON.stringify({ wrong, afterWrong })
    );
    const unlocked = await call(page, "unlock", passphrase);
    const afterUnlock = await snapshot(page);
    const clearedEncrypted = await call(page, "clear");
    const afterEncryptedClear = await snapshot(page);
    const undoneEncrypted = await call(page, "undo");
    const afterEncryptedUndo = await snapshot(page);
    record(
      "browser.encrypted-persistence",
      ok(enabled)
        && !plaintextPresent
        && locked.storageMode === "encrypted-available"
        && locked.localActionCount === 0
        && ok(unlocked)
        && afterUnlock.storageMode === "encrypted-available"
        && afterUnlock.localActionCount >= 2
        && ok(clearedEncrypted)
        && afterEncryptedClear.storageMode === "memory-only"
        && afterEncryptedClear.localActionCount === 0
        && ok(undoneEncrypted)
        && afterEncryptedUndo.storageMode === "memory-only"
        && afterEncryptedUndo.localActionCount === afterUnlock.localActionCount,
      JSON.stringify({
        enabled,
        locked,
        unlocked,
        afterUnlock,
        clearedEncrypted,
        afterEncryptedClear,
        undoneEncrypted,
        afterEncryptedUndo,
        plaintextPresent
      })
    );
  } catch (error) {
    record("browser.wrong-passphrase", false, error.message);
    record("browser.encrypted-persistence", false, error.message);
  }

  try {
    const stopped = await call(page, "stop");
    await page.reload({ waitUntil: "domcontentloaded", timeout: 15000 });
    await waitApi(page);
    const afterReload = await snapshot(page);
    const blocked = await call(page, "vote", {
      submission_id: expectedWinners[0],
      round: 1,
      admissions: 1,
      satisfaction: 50
    });
    const resumed = await call(page, "resume");
    record(
      "browser.durable-stop",
      ok(stopped)
        && afterReload.stopped === true
        && afterReload.mutationControlCount > 0
        && afterReload.disabledMutationControlCount
          === afterReload.mutationControlCount
        && !ok(blocked)
        && /stop|shutdown|disabled/i.test(reason(blocked))
        && ok(resumed),
      JSON.stringify({ stopped, afterReload, blocked, resumed })
    );
  } catch (error) {
    record("browser.durable-stop", false, error.message);
  }

  try {
    const assembled = await call(page, "assemble");
    const after = await snapshot(page);
    record(
      "browser.district-assembly",
      ok(assembled)
        && assembled.districtId === "district.agent-worlds-fair-1"
        && assembled.winners?.length === 4
        && assembled.skippedHigherRanked?.length === 2
        && assembled.skippedHigherRanked[0]?.rank === 4
        && assembled.skippedHigherRanked[1]?.rank === 5
        && JSON.stringify(assembled.resourceTotals)
          === JSON.stringify({ attention: 59, compute: 92, energy: 67 })
        && JSON.stringify(assembled.capacity)
          === JSON.stringify({ attention: 60, compute: 96, energy: 72 })
        && JSON.stringify(after.districtPavilionIds) === JSON.stringify(expectedWinners),
      JSON.stringify({ assembled, districtPavilionIds: after.districtPavilionIds })
    );
  } catch (error) {
    record("browser.district-assembly", false, error.message);
  }

  await context.close();

  const driftContext = await browser.newContext();
  await driftContext.route("**/apps/agent-fair/**", (route) => route.abort());
  await driftContext.route(
    "**/apps/3d-immersive/agent-worlds-fair-sw.js",
    (route) => route.abort()
  );
  await driftContext.route(
    "**/apps/organism-frames.json",
    (route) => route.abort()
  );
  try {
    const driftPage = await openPage(driftContext);
    const drift = await snapshot(driftPage);
    const driftSubmit = await call(driftPage, "submit", {
      ...validSubmission,
      agent_id: "agent.gate-drift",
      attraction_id: "attraction.gate-drift"
    });
    const driftVote = await call(driftPage, "vote", {
      submission_id: expectedWinners[0],
      round: 1,
      admissions: 2,
      satisfaction: 70
    });
    const driftImport = await call(
      driftPage,
      "importBranch",
      firstExport
    );
    const driftAssemble = await call(driftPage, "assemble");
    record(
      "browser.drift-mutations-disabled",
      drift.truthValid === false
        && drift.truthPillState === "drift"
        && drift.sourcePillState === "drift"
        && !ok(driftSubmit)
        && !ok(driftVote)
        && !ok(driftImport)
        && !ok(driftAssemble)
        && [driftSubmit, driftVote, driftImport, driftAssemble].every(
          (value) => /drift|unavailable|disabled|read-only/i.test(
            reason(value)
          )
        ),
      JSON.stringify({
        drift,
        driftSubmit,
        driftVote,
        driftImport,
        driftAssemble
      })
    );
  } catch (error) {
    record("browser.drift-mutations-disabled", false, error.message);
  } finally {
    await driftContext.close();
  }

  const warmContext = await browser.newContext();
  try {
    const warmPage = await openPage(warmContext);
    await warmPage.evaluate(() => navigator.serviceWorker.ready);
    await warmPage.reload({
      waitUntil: "domcontentloaded",
      timeout: 15000
    });
    await waitApi(warmPage);
    await warmContext.setOffline(true);
    await warmPage.reload({
      waitUntil: "domcontentloaded",
      timeout: 15000
    });
    await waitApi(warmPage);
    const warm = await snapshot(warmPage);
    const warmSubmit = await call(warmPage, "submit", {
      ...validSubmission,
      agent_id: "agent.gate-warm-cache",
      attraction_id: "attraction.gate-warm-cache"
    });
    const warmVote = await call(warmPage, "vote", {
      submission_id: expectedWinners[0],
      round: 2,
      admissions: 3,
      satisfaction: 88
    });
    const warmExport = exportText(
      await call(warmPage, "exportBranch")
    );
    const warmClear = await call(warmPage, "clear");
    const warmImport = await call(
      warmPage,
      "importBranch",
      warmExport
    );
    const warmAssemble = await call(warmPage, "assemble");
    record(
      "browser.warm-cache-mutations-enabled",
      warm.truthValid === true
        && /cache bytes/.test(JSON.stringify(warm.provenance))
        && ok(warmSubmit)
        && ok(warmVote)
        && warmExport.length > 0
        && ok(warmClear)
        && ok(warmImport)
        && ok(warmAssemble),
      JSON.stringify({
        warm,
        warmSubmit,
        warmVote,
        warmClear,
        warmImport,
        warmAssemble
      })
    );
  } catch (error) {
    record("browser.warm-cache-mutations-enabled", false, error.message);
  } finally {
    await warmContext.close();
  }

  const stallContext = await browser.newContext();
  try {
    const stallPage = await openPage(stallContext);
    const stall = await stallPage.evaluate(async () => {
      const lower = window.__agentFairTest;
      await lower.ready;
      lower.setPlayback(0, true, 60);
      await new Promise(
        (resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))
      );
      const before = lower.state().playbackMs;
      const wallStart = performance.now();
      while (performance.now() - wallStart < 1000) {
        Math.sqrt(12345);
      }
      const blockedForMs = performance.now() - wallStart;
      await new Promise((resolve) => requestAnimationFrame(resolve));
      const after = lower.state().playbackMs;
      lower.setPlayback(after, false, 60);
      return {
        before,
        after,
        advancedMs: after - before,
        blockedForMs
      };
    });
    record(
      "browser.wall-clock-stall",
      stall.blockedForMs >= 900
        && stall.blockedForMs <= 1600
        && stall.advancedMs >= 50000
        && stall.advancedMs <= 75000,
      JSON.stringify(stall)
    );
  } catch (error) {
    record("browser.wall-clock-stall", false, error.message);
  } finally {
    await stallContext.close();
  }

  const storageContext = await browser.newContext();
  await storageContext.addInitScript(() => {
    const denied = () => { throw new DOMException("denied", "SecurityError"); };
    Object.defineProperty(window, "localStorage", { get: denied });
    Object.defineProperty(window, "sessionStorage", { get: denied });
  });
  try {
    const storagePage = await openPage(storageContext);
    const before = await snapshot(storagePage);
    const submitted = await call(storagePage, "submit", {
      ...validSubmission,
      agent_id: "agent.memory-only",
      attraction_id: "attraction.memory-only",
      title: "Memory Only",
      category: "learning",
      visitor_promise: "A bounded memory-only test.",
      resource_request: { attention: 1, compute: 1, energy: 1 }
    });
    const after = await snapshot(storagePage);
    const encryption = await call(
      storagePage,
      "enableEncrypted",
      "storage-denied-fair-passphrase"
    );
    const stopped = await call(storagePage, "stop");
    const afterStop = await snapshot(storagePage);
    await call(storagePage, "resume");
    record(
      "browser.storage-denied",
      before.storageMode === "memory-only-storage-denied"
        && ok(submitted)
        && reason(submitted).length > 0
        && after.localActionCount === 1
        && after.storageMode === "memory-only-storage-denied"
        && !ok(encryption)
        && /storage|unavailable|denied/i.test(reason(encryption))
        && ok(stopped)
        && stopped.durable === false
        && afterStop.stopped === true
        && afterStop.storageMode === "memory-only-storage-denied",
      JSON.stringify({
        before, submitted, after, encryption, stopped, afterStop
      })
    );
  } catch (error) {
    record("browser.storage-denied", false, error.message);
  } finally {
    await storageContext.close();
  }

  const motionContext = await browser.newContext({ reducedMotion: "reduce" });
  try {
    const motionPage = await openPage(motionContext);
    const motion = await motionPage.evaluate(async () => {
      await window.__AGENT_FAIR_TEST__.ready();
      await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
      return {
        media: matchMedia("(prefers-reduced-motion: reduce)").matches,
        snapshot: matchMedia("(prefers-reduced-motion: reduce)").matches,
        runningAnimations: document.getAnimations().filter(
          (animation) => animation.playState === "running"
        ).length
      };
    });
    record(
      "browser.reduced-motion",
      motion.media && motion.snapshot === true && motion.runningAnimations === 0,
      JSON.stringify(motion)
    );
  } catch (error) {
    record("browser.reduced-motion", false, error.message);
  } finally {
    await motionContext.close();
  }

  const mobile320 = await measureMobile(320, 800);
  record("browser.mobile-320", mobile320.pass, mobile320.detail);
  const mobile390 = await measureMobile(390, 844);
  record("browser.mobile-390", mobile390.pass, mobile390.detail);

  const touchContext = await browser.newContext({
    viewport: { width: 390, height: 844 },
    isMobile: true,
    hasTouch: true
  });
  try {
    const touchPage = await openPage(touchContext);
    const touch = await touchPage.evaluate(async () => {
      const apiMetrics = await window.__AGENT_FAIR_TEST__.metrics();
      const values = Array.from(document.querySelectorAll(
        "button,input:not([type=file]),select,[role=button]"
      )).filter((node) => {
        const style = getComputedStyle(node);
        const rect = node.getBoundingClientRect();
        return style.display !== "none"
          && style.visibility !== "hidden"
          && !node.disabled
          && rect.width > 0
          && rect.height > 0;
      }).map((node) => {
        const rect = node.getBoundingClientRect();
        return {
          id: node.id || node.getAttribute("aria-label") || node.tagName,
          width: Math.round(rect.width),
          height: Math.round(rect.height)
        };
      });
      return {
        count: values.length,
        undersized: values.filter((value) => value.width < 44 || value.height < 44),
        apiMetrics
      };
    });
    record(
      "browser.touch-targets",
      touch.count >= 8
        && touch.undersized.length === 0
        && touch.apiMetrics.controls.length === 53
        && touch.apiMetrics.minimumControlHeight >= 44
        && touch.apiMetrics.undersizedControls.length === 0,
      JSON.stringify(touch)
    );
  } catch (error) {
    record("browser.touch-targets", false, error.message);
  } finally {
    await touchContext.close();
  }

  await browser.close();
  console.log(JSON.stringify({ results }));
})().catch(async (error) => {
  try {
    if (browser) await browser.close();
  } catch (_) {}
  console.log(JSON.stringify({
    fatal: error.stack || error.message,
    results
  }));
  process.exitCode = 1;
});
"""


def _browser_failures(detail: str) -> List[CheckResult]:
    return [CheckResult(name, False, detail) for name in BROWSER_CHECK_NAMES]


def run_browser_checks(
    root: Path,
    phase: str = "auto",
) -> List[CheckResult]:
    repository = Path(root).expanduser().resolve()
    try:
        resolved_phase = resolve_release_phase(repository, phase)
    except Exception as error:
        return _browser_failures(
            "required browser release phase unavailable: {}".format(error)
        )
    node = shutil.which("node")
    if node is None:
        return _browser_failures(
            "required browser measurement unavailable: node is missing"
        )
    package = repository / "node_modules/playwright/package.json"
    if not package.is_file():
        return _browser_failures(
            "required browser measurement unavailable: repository Playwright is missing"
        )
    try:
        resolution = subprocess.run(
            [node, "-e", "require.resolve('playwright')"],
            cwd=str(repository),
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as error:
        return _browser_failures(
            "required browser measurement unavailable: {}".format(error)
        )
    if resolution.returncode != 0:
        return _browser_failures(
            "required browser measurement unavailable: {}".format(
                resolution.stderr.strip() or "Playwright cannot be resolved"
            )
        )
    if not (repository / APP_RELATIVE).is_file():
        return _browser_failures(
            "required browser measurement unavailable: fair app is missing"
        )
    with _serve(repository) as base_url:
        try:
            process = subprocess.run(
                [
                    node,
                    "-e",
                    BROWSER_SCRIPT,
                    base_url + APP_RELATIVE.as_posix(),
                    EXPECTED_BUNDLE_DIGEST,
                    resolved_phase,
                    json.dumps(EXPECTED_WINNERS, separators=(",", ":")),
                    EXPECTED_CONTRACT_DIGEST,
                    EXPECTED_RELEASE_CANDIDATE_DIGEST,
                ],
                cwd=str(repository),
                text=True,
                capture_output=True,
                timeout=150,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as error:
            return _browser_failures(
                "required browser measurement failed: {}".format(error)
            )
    try:
        payload = json.loads(process.stdout)
    except json.JSONDecodeError as error:
        return _browser_failures(
            "Playwright emitted invalid evidence: {} {}".format(
                error, process.stderr.strip()
            )
        )
    values = payload.get("results", {})
    fatal = payload.get("fatal")
    results = []
    for name in BROWSER_CHECK_NAMES:
        value = values.get(name)
        if type(value) is not dict:
            results.append(CheckResult(
                name,
                False,
                "required browser assertion was not measured{}".format(
                    ": " + str(fatal) if fatal else ""
                ),
            ))
            continue
        results.append(CheckResult(
            name,
            value.get("pass") is True,
            value.get("detail", "no evidence"),
        ))
    if process.returncode != 0:
        for result in results:
            if result.passed:
                result.passed = False
                result.detail = (
                    "browser process failed after measurement: {}".format(
                        process.stderr.strip()
                    )
                )
    return results


def run_gate(
    root: Path,
    phase: str = "auto",
    attestation_path: Optional[Path] = None,
) -> List[CheckResult]:
    repository = Path(root).expanduser().resolve()
    resolved_phase = resolve_release_phase(repository, phase)
    return (
        run_static_checks(
            repository,
            resolved_phase,
            attestation_path,
        )
        + run_browser_checks(repository, resolved_phase)
    )


def _payload(
    root: Path,
    results: Sequence[CheckResult],
    phase: str = "auto",
    attestation_path: Optional[Path] = None,
) -> Dict[str, Any]:
    passed = sum(1 for result in results if result.passed)
    failed = len(results) - passed
    resolved_phase = resolve_release_phase(root, phase)
    return {
        "gate": "agent-worlds-fair",
        "root": str(root),
        "release_phase": resolved_phase,
        "release_candidate_digest": EXPECTED_RELEASE_CANDIDATE_DIGEST,
        "release_provenance": (
            "prepared-no-release"
            if resolved_phase == "prepared"
            else (
                "attestation-verified-pr"
                if os.environ.get("GITHUB_EVENT_NAME") == "pull_request"
                else "attestation-context-unverified"
            )
            if attestation_path is not None
            else "structural-only-local"
        ),
        "passed": failed == 0,
        "counts": {
            "total": len(results),
            "passed": passed,
            "failed": failed,
            "static": len(STATIC_CHECKS),
            "browser": len(BROWSER_CHECK_NAMES),
        },
        "checks": [asdict(result) for result in results],
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fail-closed acceptance gate for the Agent World's Fair."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=ROOT,
        help="repository root (default: inferred from this script)",
    )
    parser.add_argument("--json", action="store_true", help="emit JSON evidence")
    parser.add_argument(
        "--phase",
        choices=sorted(RELEASE_PHASES),
        default="auto",
        help="release phase (default: auto-detect)",
    )
    parser.add_argument(
        "--attestation",
        type=Path,
        help=(
            "CI-supplied release PR attestation JSON; absent released "
            "runs are reported as structural-only local verification"
        ),
    )
    arguments = parser.parse_args(argv)
    root = arguments.root.expanduser().resolve()
    phase = resolve_release_phase(root, arguments.phase)
    attestation_value = arguments.attestation
    if attestation_value is None:
        environment_value = os.environ.get(RELEASE_ATTESTATION_ENV)
        if environment_value:
            attestation_value = Path(environment_value)
    attestation_path = None
    if attestation_value is not None:
        attestation_path = attestation_value.expanduser()
        if not attestation_path.is_absolute():
            attestation_path = root / attestation_path
        attestation_path = attestation_path.resolve()
    results = (
        run_gate(root, phase, attestation_path)
        if attestation_path is not None
        else run_gate(root, phase)
    )
    payload = _payload(
        root,
        results,
        phase,
        attestation_path,
    )
    if arguments.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        for result in results:
            print("{} {} — {}".format(
                "PASS" if result.passed else "FAIL",
                result.name,
                result.detail,
            ))
        counts = payload["counts"]
        print(
            "{}: {}/{} passed; {} failed ({} static, {} browser)".format(
                "ACCEPT" if payload["passed"] else "REJECT",
                counts["passed"],
                counts["total"],
                counts["failed"],
                counts["static"],
                counts["browser"],
            )
        )
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

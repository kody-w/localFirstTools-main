#!/usr/bin/env python3
"""Fail-closed acceptance gate for the RappterZoo agent amusement park."""

import argparse
import copy
import hashlib
import json
import re
import shutil
import subprocess
import sys
import threading
import xml.etree.ElementTree as ET
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple


ROOT = Path(__file__).resolve().parent.parent
APP_RELATIVE = Path("apps/3d-immersive/agent-amusement-park.html")
STATE_RELATIVE = Path("apps/agent-park/park-state.json")
EVENTS_RELATIVE = Path("apps/agent-park/events.jsonl")
CONTRACT_V1_RELATIVE = Path("apps/agent-park/agent-contract.json")
CONTRACT_V2_RELATIVE = Path("apps/agent-park/agent-contract-v2.json")
SERVICE_WORKER_RELATIVE = Path(
    "apps/3d-immersive/agent-amusement-park-sw.js"
)
ORGANISM_LEDGER_RELATIVE = Path("apps/organism-frames.jsonl")
ORGANISM_PROJECTION_RELATIVE = Path("apps/organism-frames.json")
SYNDICATION_INDEX_RELATIVE = Path("apps/syndication/index.json")
SYNDICATION_SNAPSHOT_RELATIVE = Path("apps/syndication/snapshot.json")
MCP_RELATIVE = Path("scripts/rappterzoo_mcp.py")
APP_URL_SUFFIX = "/apps/3d-immersive/agent-amusement-park.html"
PARK_ID = "park.rappterzoo-agent-amusement-park"
PROFILE = "rappterzoo-syndication-profile/10"
EXPERIENCE_EVENT_ID = "experience-birth:agent-amusement-park"
EXPERIENCE_RELEASE_PREFIX = "experience-release:agent-amusement-park:"
PARK_RESOURCE_PATHS = {
    CONTRACT_V1_RELATIVE.as_posix(),
    CONTRACT_V2_RELATIVE.as_posix(),
    EVENTS_RELATIVE.as_posix(),
    STATE_RELATIVE.as_posix(),
}
RUNTIME_PARK_URIS = {
    "rappterzoo://agent-amusement-park",
    "rappterzoo://agent-park-contract",
    "rappterzoo://agent-park-contract-v1",
    "rappterzoo://agent-park-events",
    "rappterzoo://agent-park-guide",
    "rappterzoo://agent-park-state",
}
STATIC_PARK_RESOURCES = {
    "agent_amusement_park",
    "agent_park_contract",
    "agent_park_contract_v1_history",
    "agent_park_event_ledger",
    "agent_park_guide",
    "agent_park_state",
}
BROWSER_CHECK_NAMES = (
    "browser.cold-start",
    "browser.service-worker-cache",
    "browser.warm-offline-reload",
    "browser.cached-provenance",
    "browser.major-controls",
    "browser.durable-emergency-rearm",
    "browser.park-time-travel",
    "browser.organism-time-travel",
    "browser.memory-only-default",
    "browser.encrypted-persistence",
    "browser.wrong-passphrase",
    "browser.branch-import-adversarial",
    "browser.branch-import-replay",
    "browser.full-import-adversarial",
    "browser.full-import-replay",
    "browser.clear-intervening-mutation",
    "browser.clear-checkpoint-undo",
    "browser.deterministic-exports",
    "browser.storage-denied",
    "browser.reduced-motion",
    "browser.wall-clock-load",
    "browser.mobile-390x844",
    "browser.mobile-320",
    "browser.touch-targets",
)

sys.path.insert(0, str(Path(__file__).resolve().parent))
import agent_amusement_park as park_builder
import build_syndication
import organism_ledger
import rappterzoo_mcp
import rappterzoo_sync


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
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as error:
        raise GateError("{} is unreadable: {}".format(path, error)) from error
    values = []
    for number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as error:
            raise GateError(
                "{} line {} is not valid JSON: {}".format(path, number, error)
            ) from error
        _require(type(value) is dict, "{} line {} is not an object".format(path, number))
        values.append(value)
    return values


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
        detail = check()
        return CheckResult(name, True, detail)
    except Exception as error:
        return CheckResult(name, False, "{}: {}".format(type(error).__name__, error))


def _load_bundle(root: Path) -> Tuple[Dict[str, Any], List[Dict[str, Any]], Dict[str, Any]]:
    state = _json(root / STATE_RELATIVE)
    events = _json_lines(root / EVENTS_RELATIVE)
    contract = _json(root / CONTRACT_V2_RELATIVE)
    _require(type(state) is dict, "park state must be an object")
    _require(type(contract) is dict, "park contract must be an object")
    return state, events, contract


def _check_app_contract(root: Path) -> str:
    path = root / APP_RELATIVE
    _require(path.is_file(), "agent amusement park app is missing")
    text = path.read_text(encoding="utf-8")
    required = (
        "<!DOCTYPE html>",
        "<title>RappterZoo Agent Amusement Park</title>",
        'name="viewport"',
        'id="parkCanvas"',
        'id="emergencyButton"',
        'id="parkSourceButton"',
        'id="organismSourceButton"',
        'id="dispatchButton"',
        'id="negotiateButton"',
        'id="inventButton"',
        'id="simulateButton"',
        'id="exportBranchButton"',
        'id="clearBranchButton"',
        'id="undoClearButton"',
        'id="timestampedExportInput"',
        "Default exports are deterministic and byte-identical",
        'id="branchPassphraseInput"',
        'id="enableEncryptedStorageButton"',
        'id="disableEncryptedStorageButton"',
        'id="importFileInput"',
        'id="importReplayButton"',
        'id="exportLedgerButton"',
    )
    missing = [marker for marker in required if marker not in text]
    _require(not missing, "missing app contract markers: {}".format(", ".join(missing)))
    return "{} bytes; required app and control surface present".format(path.stat().st_size)


def _check_theme(root: Path) -> str:
    text = (root / APP_RELATIVE).read_text(encoding="utf-8")
    markers = (
        'get("scoutTheme")',
        'matchMedia("(prefers-color-scheme: dark)")',
        'setAttribute("data-theme", theme)',
        ":root {",
        'html[data-theme="dark"]',
        "--cp-bg:",
        "--cp-accent:",
        "--cp-danger:",
        "@media (prefers-reduced-motion: reduce)",
    )
    missing = [marker for marker in markers if marker not in text]
    _require(not missing, "theme/reduced-motion markers missing: {}".format(", ".join(missing)))
    detector = text.index('get("scoutTheme")')
    body = text.lower().index("<body")
    _require(detector < body, "theme detector must run before body paint")
    return "light/dark scout theme and reduced-motion contract present"


def _check_csp(root: Path) -> str:
    text = (root / APP_RELATIVE).read_text(encoding="utf-8")
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
    _require(directives.get("default-src") == ["'none'"], "default-src must be 'none'")
    _require(directives.get("connect-src") == ["'self'"], "connect-src must be 'self'")
    for directive in ("object-src", "base-uri", "form-action", "frame-src"):
        _require(directives.get(directive) == ["'none'"], "{} must be 'none'".format(directive))
    _require(directives.get("worker-src") == ["'self'"], "worker-src must be 'self'")
    for token in ("eval(", "new Function", "document.write"):
        _require(token not in text, "dynamic code primitive is present: {}".format(token))
    return "fail-closed CSP and no dynamic-code primitives"


def _check_same_origin_paths(root: Path) -> str:
    text = (root / APP_RELATIVE).read_text(encoding="utf-8")
    expected = {
        "../agent-park/park-state.json",
        "../agent-park/events.jsonl",
        "../agent-park/agent-contract-v2.json",
        "../agent-park/agent-contract.json",
        "../organism-frames.json",
    }
    block = re.search(
        r"const RESOURCE_URLS = Object\.freeze\(\{(.*?)\}\);",
        text,
        re.DOTALL,
    )
    _require(block, "RESOURCE_URLS declaration is missing")
    values = set(re.findall(r':\s*"([^"]+)"', block.group(1)))
    _require(values == expected, "resource URLs are not the four required relative paths")
    _require(
        text.count('credentials: "same-origin"') >= 2,
        "JSON and JSONL fetches must require same-origin credentials",
    )
    _require(
        not any(re.match(r"^(?:https?:)?//", value) for value in values),
        "external resource URL found",
    )
    _require(
        'url: "./agent-amusement-park-sw.js"' in text,
        "service worker URL is not project-relative",
    )
    return "5 data paths + service worker are project-relative and same-origin"


def _check_service_worker_contract(root: Path) -> str:
    path = root / SERVICE_WORKER_RELATIVE
    _require(path.is_file(), "agent park service worker is missing")
    text = path.read_text(encoding="utf-8")
    app_text = (root / APP_RELATIVE).read_text(encoding="utf-8")
    app_version = re.search(
        r"const OFFLINE_WORKER = Object\.freeze\(\{.*?version:\s*\"([^\"]+)\"",
        app_text,
        re.DOTALL,
    )
    _require(app_version, "app service-worker version declaration is missing")
    _require(
        'const VERSION = "{}";'.format(app_version.group(1)) in text,
        "app and service-worker cache versions differ",
    )
    markers = (
        'const CACHE_PREFIX = "rappterzoo-agent-park-"',
        "const CACHE_NAME = VERSION",
        'shell: new URL("./agent-amusement-park.html"',
        'park: new URL("../agent-park/park-state.json"',
        'events: new URL("../agent-park/events.jsonl"',
        'contractV2: new URL("../agent-park/agent-contract-v2.json"',
        'contractV1: new URL("../agent-park/agent-contract.json"',
        'organism: new URL("../organism-frames.json"',
        'request.mode === "navigate"',
        "networkFirst(request, URLS.shell)",
        'event.data?.type !== "CACHE_STATUS"',
        'event.data?.type === "SAFETY_STOP_SET"',
        'event.data?.type === "SAFETY_STOP_GET"',
        '"X-RappterZoo-Provenance"',
        'withProvenance(cached, "cache")',
        'withProvenance(response, "network")',
    )
    missing = [marker for marker in markers if marker not in text]
    _require(not missing, "service worker markers missing: {}".format(", ".join(missing)))
    _require(
        "cached.length === 5" in text,
        "service worker readiness must require shell + four data resources",
    )
    _require(
        "url.origin !== self.location.origin" in text,
        "service worker must reject cross-origin fetch handling",
    )
    return "same-origin network-first shell/data cache and durable safety plane declared"


def _check_manifest_feed_registration(root: Path) -> str:
    manifest = _json(root / "apps/manifest.json")
    categories = manifest.get("categories", manifest)
    category = categories.get("3d_immersive", {})
    apps = category.get("apps", [])
    _require(category.get("count") == len(apps), "3d_immersive manifest count is stale")
    matches = [item for item in apps if item.get("file") == APP_RELATIVE.name]
    _require(len(matches) == 1, "manifest must register the park exactly once")
    _require(matches[0].get("featured") is True, "park manifest entry must be featured")

    feed = _json(root / "apps/feed.json")
    urls = {
        item.get("item", {}).get("url")
        for item in feed.get("dataFeedElement", [])
        if type(item) is dict
    }
    _require(
        len([url for url in urls if type(url) is str and url.endswith(APP_URL_SUFFIX)]) == 1,
        "JSON feed must register the park exactly once",
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
        "RSS feed must register the park exactly once",
    )
    return "manifest + JSON feed + RSS each register one featured park"


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
    _require(STATIC_PARK_RESOURCES.issubset(names), "static MCP park resources are incomplete")
    _require(
        "agent_amusement_park_first_visit" in prompts,
        "static MCP first-visit prompt is missing",
    )

    protocol = _json(root / ".well-known/agent-protocol")
    park = protocol.get("agent_amusement_park", {})
    _require(park.get("park_id") == PARK_ID, "agent protocol park id mismatch")
    _require(park.get("economy") == "synthetic-credit-only", "agent protocol economy mismatch")
    _require(park.get("contract_version") == 2, "agent protocol contract version mismatch")
    _require(
        protocol.get("mcp_stdio", {}).get("agent_park_prompt")
        == "agent_amusement_park_first_visit",
        "agent protocol MCP prompt mismatch",
    )

    toc = _json(root / ".well-known/feeddata-toc")
    blob = json.dumps(toc, sort_keys=True)
    _require(APP_URL_SUFFIX in blob, "feeddata TOC does not publish the park")
    for path in PARK_RESOURCE_PATHS:
        _require("/" + path in blob, "feeddata TOC omits {}".format(path))
    _require("/" + SERVICE_WORKER_RELATIVE.as_posix() in blob, "feeddata TOC omits service worker")
    return "MCP static manifest, protocol, and feed TOC publish v1/v2 park resources"


def _check_project_scoped_links(root: Path) -> str:
    static = _json(root / ".well-known/mcp.json")
    protocol = _json(root / ".well-known/agent-protocol")
    project_base = "https://kody-w.github.io/localFirstTools-main/"
    raw_base = "https://raw.githubusercontent.com/kody-w/localFirstTools-main/main/"

    required_protocol = {
        "agent_park_state": project_base + STATE_RELATIVE.as_posix(),
        "agent_park_events": project_base + EVENTS_RELATIVE.as_posix(),
        "agent_park_contract": project_base + CONTRACT_V2_RELATIVE.as_posix(),
        "agent_park_contract_v1_history": project_base + CONTRACT_V1_RELATIVE.as_posix(),
        "agent_amusement_park": project_base + APP_RELATIVE.as_posix(),
        "agent_park_service_worker": project_base + SERVICE_WORKER_RELATIVE.as_posix(),
        "agent_park_acceptance_gate": raw_base + "scripts/agent_park_gate.py",
    }
    discovery = protocol.get("discovery", {})
    for key, expected in required_protocol.items():
        _require(discovery.get(key) == expected, "agent protocol {} link is not project-scoped absolute".format(key))

    park = protocol.get("agent_amusement_park", {})
    _require(
        park.get("custody", {}).get("origin_scope_warning")
        == "Browser localStorage is scoped to scheme, host, and port, not the /localFirstTools-main/ path; ciphertext AAD binds the envelope to origin and app pathname.",
        "agent protocol origin-level storage limitation is missing",
    )
    stdio = static.get("stdio_server", {})
    _require(
        stdio.get("agent_park_season_2", {}).get("origin_storage_warning")
        == "Browser localStorage is scoped to scheme, host, and port, not the /localFirstTools-main/ project path.",
        "MCP origin-level storage limitation is missing",
    )
    _require(
        "cold offline is not guaranteed"
        in stdio.get("agent_park_season_2", {}).get("warm_offline", ""),
        "MCP warm-offline limitation disclosure is missing",
    )
    html_text = (root / APP_RELATIVE).read_text(encoding="utf-8")
    _require(
        project_base + ".well-known/mcp.json" in html_text
        and project_base + ".well-known/agent-protocol" in html_text,
        "app footer lacks project-scoped absolute discovery links",
    )
    _require(
        "Origin-level" in html_text and "is unavailable" in html_text,
        "app footer lacks origin-level limitation disclosure",
    )
    return "absolute project links and origin/warm-offline limitations are explicit"


def _check_bundle_exact(root: Path) -> str:
    state, events, contract = _load_bundle(root)
    result = park_builder.verify_bundle(state, events, contract, root)
    _require(result.get("event_count") == len(events), "bundle verifier event count mismatch")
    _require(
        state.get("integrity", {}).get("bundle_digest")
        == contract.get("integrity", {}).get("bundle_digest"),
        "state and v2 contract bundle digests differ",
    )
    return "v2 deterministic bundle verified; state/contract/bundle digests match"


def _check_event_chain(root: Path) -> str:
    state, events, _contract = _load_bundle(root)
    result = park_builder.verify_events(events)
    expected = state.get("event_ledger", {}).get("event_count")
    _require(type(expected) is int and expected > 0, "state event count is invalid")
    _require(len(events) == expected, "event count differs from state projection")
    _require(result.get("event_count") == expected, "event verifier count mismatch")
    _require(result.get("head") == state["event_ledger"].get("head"), "event head mismatch")
    _require(_sha256(root / EVENTS_RELATIVE) == state["event_ledger"].get("sha256"), "ledger byte digest mismatch")
    return "{} events linked; head {}".format(expected, result["head"][:16])


def _check_season_prefix_and_contracts(root: Path) -> str:
    state, events, contract = _load_bundle(root)
    legacy_path = root / CONTRACT_V1_RELATIVE
    legacy = _json(legacy_path)
    _require(legacy.get("schema") == "rappterzoo-agent-park-contract/1", "legacy contract schema drifted")
    _require(contract.get("schema") == "rappterzoo-agent-park-contract/2", "primary contract is not v2")
    legacy_declaration = contract.get("legacy_contract", {})
    legacy_digest = _sha256(legacy_path)
    _require(legacy_declaration.get("immutable") is True, "v1 contract is not declared immutable")
    _require(legacy_declaration.get("sha256") == legacy_digest, "v1 contract digest declaration mismatch")
    _require(legacy_digest == park_builder.LEGACY_CONTRACT_SHA256, "v1 contract bytes differ from verifier constant")

    seasons = state.get("seasons", [])
    contract_seasons = contract.get("seasons", {})
    _require(len(seasons) == 2, "state must project exactly Season 1 and Season 2")
    first = seasons[0]
    second = seasons[1]
    first_count = first.get("event_count")
    second_count = second.get("event_count")
    _require(type(first_count) is int and type(second_count) is int, "season event counts are invalid")
    _require(first.get("first_seq") == 0 and first.get("last_seq") == first_count - 1, "Season 1 range is invalid")
    _require(second.get("first_seq") == first_count, "Season 2 does not immediately extend Season 1")
    _require(second.get("last_seq") == first_count + second_count - 1, "Season 2 range is invalid")
    prefix = park_builder._event_bytes(events[:first_count])
    prefix_digest = hashlib.sha256(prefix).hexdigest()
    declared = contract_seasons.get("season_1", {})
    _require(prefix_digest == first.get("ledger_prefix_sha256"), "state Season 1 prefix digest mismatch")
    _require(prefix_digest == declared.get("immutable_prefix_sha256"), "contract Season 1 prefix digest mismatch")
    _require(prefix_digest == park_builder.SEASON_ONE_PREFIX_SHA256, "Season 1 prefix differs from verifier constant")
    _require(events[first_count - 1].get("event_hash") == first.get("head"), "Season 1 head mismatch")
    _require(events[-1].get("event_hash") == second.get("head"), "Season 2 head mismatch")
    _require(len(events) == first_count + second_count, "combined event count is not the sum of both seasons")
    return "immutable v1 contract + {}-event Season 1 prefix + {}-event Season 2".format(
        first_count, second_count
    )


def _check_synthetic_economy(root: Path) -> str:
    state, events, contract = _load_bundle(root)
    economy = state.get("economy", {})
    _require(economy.get("currency") == "synthetic-credit", "currency is not synthetic-credit")
    _require(economy.get("real_money") is False, "real-money claim must be false")
    _require(economy.get("balanced") is True, "economy is not balanced")
    _require(economy.get("total_debits") == economy.get("total_credits"), "debits and credits differ")
    bps = economy.get("royalty_basis_points", {})
    _require(sum(bps.values()) == 10000, "royalty basis points do not total 10000")
    settlements = [event for event in events if event.get("kind") == "park.royalty-settlement"]
    seasons = state.get("seasons", [])
    expected_settlements = len(seasons) * state.get("night_count", 0)
    _require(len(settlements) == expected_settlements, "one royalty settlement per season-night is required")
    _require(
        all(event.get("payload", {}).get("royalty_credits", 0) > 0 for event in settlements),
        "every night must settle positive synthetic royalties",
    )
    contract_economy = contract.get("economy", {})
    _require(contract_economy.get("real_money") is False, "contract real-money flag is unsafe")
    _require(
        contract_economy.get("tradable_asset_or_mining_claim") is False,
        "contract must reject tradable/mining claims",
    )
    return "{} credits balanced across {} nightly royalty settlements".format(
        economy["total_credits"], len(settlements)
    )


def _check_resources_evolution(root: Path) -> str:
    state, events, _contract = _load_bundle(root)
    nights = state.get("nights", [])
    night_count = state.get("night_count")
    _require(type(night_count) is int and len(nights) == night_count, "night projection count mismatch")
    capacity = state.get("resource_capacity", {})
    contention = False
    for night in nights:
        allocations = night.get("resource_allocations", {})
        for resource, limit in capacity.items():
            allocated = sum(
                item.get(resource, 0)
                for item in allocations.values()
                if type(item) is dict
            )
            _require(allocated <= limit, "{} capacity exceeded on night {}".format(resource, night.get("night")))
        resource_event = next(
            (
                event
                for event in events
                if event.get("kind") == "park.resource-negotiation"
                and event.get("payload", {}).get("night") == night.get("night")
            ),
            None,
        )
        _require(resource_event is not None, "night {} lacks resource negotiation".format(night.get("night")))
        for resource, limit in capacity.items():
            requested = sum(
                bid.get("requested", {}).get(resource, 0)
                for bid in resource_event["payload"].get("bids", [])
            )
            allocated = sum(
                item.get(resource, 0)
                for item in resource_event["payload"].get("allocations", {}).values()
            )
            contention = contention or requested > limit >= allocated
    evolution = state.get("evolution", {})
    inventions = evolution.get("inventions", [])
    retirements = evolution.get("retirements", [])
    mutations = evolution.get("nightly_mutations", [])
    _require(len(inventions) >= 2, "park must invent at least two attractions")
    _require(retirements, "park must retire a weak attraction")
    _require(len(mutations) == night_count, "latest season must evolve an attraction every night")
    _require(contention, "no scarce-resource contention was demonstrated")
    season_count = len(state.get("seasons", []))
    for kind in (
        "park.resource-negotiation",
        "park.admission-settlement",
        "park.royalty-settlement",
        "park.ride-evolution",
        "park.night-close",
    ):
        _require(
            len([event for event in events if event.get("kind") == kind])
            == season_count * night_count,
            "{} count does not cover every season-night".format(kind),
        )
    return "{} nights; {} inventions; {} retirements; bounded contention observed".format(
        night_count, len(inventions), len(retirements)
    )


def _check_customer_controls(root: Path) -> str:
    state, _events, contract = _load_bundle(root)
    expected = {
        "canonical_mutation": "customer-approved-release-only",
        "customer_can_export_full_ledger": True,
        "customer_can_select_model_route": True,
        "customer_can_shutdown_immediately": True,
        "customer_holds_runtime_keys": True,
        "park_or_vendor_remote_shutdown": False,
    }
    _require(state.get("control_tower") == expected, "state customer control boundary drifted")
    _require(contract.get("control_boundary") == expected, "contract customer control boundary drifted")
    _require(contract.get("write_default") == "local-branch-only", "write default is not local-only")
    actions = contract.get("agent_actions", {})
    _require(actions, "agent actions are missing")
    _require(
        all(action.get("canonical_write") is False for action in actions.values()),
        "an agent action permits a canonical write",
    )
    return "runtime keys, model route, export, and immediate stop remain customer-held"


def _check_v2_contract_spec(root: Path) -> str:
    contract = _json(root / CONTRACT_V2_RELATIVE)
    static = _json(root / ".well-known/mcp.json")
    _require(contract.get("schema") == "rappterzoo-agent-park-contract/2", "v2 contract schema mismatch")
    hashing = contract.get("canonicalization_and_hashing", {})
    canonical = hashing.get("canonical_json", {})
    _require(canonical.get("name") == "restricted-rfc8785-compatible-profile", "canonical JSON profile mismatch")
    _require(canonical.get("floats") == "forbidden", "canonical JSON must reject floats")
    _require(canonical.get("strings") == "NFC-normalized", "canonical strings must be NFC")
    _require(canonical.get("trailing_newline") is False, "canonical JSON must omit trailing newline")
    domains = hashing.get("hash_domains", {})
    for name in ("bundle_v2", "contract_v2", "event_v1", "event_v2", "payload_v1", "payload_v2", "state_v2"):
        _require(type(domains.get(name)) is str and domains[name].endswith("\n"), "hash domain {} is missing".format(name))
    preimages = hashing.get("preimages", {})
    for name in ("branch_digest", "local_action_hash", "local_action_payload_hash"):
        _require(preimages.get(name, {}).get("digest") == "sha256", "{} must use SHA-256".format(name))
        _require(preimages.get(name, {}).get("domain_prefix") is False, "{} must be unprefixed".format(name))

    action_limit = contract.get("action_limit", {})
    static_limit = static.get("stdio_server", {}).get("agent_park_contract", {}).get("action_limit")
    _require(action_limit.get("max_local_actions_per_mcp_session") == static_limit == 100, "MCP local action limit mismatch")
    _require(action_limit.get("canonical_writes_per_session") == 0, "canonical MCP writes must be zero")
    tools = {item.get("name") for item in static.get("tools", []) if type(item) is dict}
    mapping = contract.get("mcp_mapping", {}).get("tools", {})
    _require(set(mapping.values()).issubset(tools), "v2 contract maps to an unknown MCP tool")
    _require(
        mapping == {
            "bid_for_resources": "agent_park_local_action",
            "export_branch": "agent_park_export_branch",
            "invent_attraction": "agent_park_local_action",
            "time_travel": "agent_park_time_travel",
            "visit": "agent_park_local_action",
        },
        "v2 contract tool mapping drifted",
    )
    return "v2 canonical hash spec, 5 action mappings, and 100-action limit verified"


def _verified_organism_frames(root: Path) -> List[Dict[str, Any]]:
    frames = organism_ledger.read_frames(root / ORGANISM_LEDGER_RELATIVE)
    organism_ledger.verify_frames(frames)
    organism_ledger.verify_projection(frames, root / ORGANISM_PROJECTION_RELATIVE)
    return frames


def _check_organism_chain(root: Path) -> str:
    frames = _verified_organism_frames(root)
    _require(frames, "organism ledger is empty")
    for index, frame in enumerate(frames):
        _require(frame.get("seq") == index, "organism sequence gap at {}".format(index))
        if index == 0:
            _require(frame.get("prev") is None, "organism genesis prev is not null")
            _require(frame.get("prev_wave") is None, "organism genesis prev_wave is not null")
        else:
            _require(frame.get("prev") == frames[index - 1].get("payload_hash"), "payload link mismatch at {}".format(index))
            _require(frame.get("prev_wave") == frames[index - 1].get("frame_hash"), "wave link mismatch at {}".format(index))
    return "{} organism frames linked through prev + prev_wave".format(len(frames))


def _check_experience_frames(root: Path) -> str:
    frames = _verified_organism_frames(root)
    birth_matches = [
        (index, frame)
        for index, frame in enumerate(frames)
        if frame.get("payload", {}).get("event_id") == EXPERIENCE_EVENT_ID
    ]
    _require(len(birth_matches) == 1, "park experience birth frame must occur exactly once")
    birth_index, birth = birth_matches[0]
    _require(birth_index > 0, "park experience birth frame cannot be genesis")
    previous = frames[birth_index - 1]
    _require(
        str(previous.get("payload", {}).get("event_id", "")).startswith("experience-birth:"),
        "park frame must extend the prior experience chain",
    )
    state = _json(root / STATE_RELATIVE)
    birth_payload = birth.get("payload", {})
    season_one = state.get("seasons", [None])[0] or {}
    _require(birth_payload.get("organism") == PARK_ID, "birth frame organism id mismatch")
    _require(birth_payload.get("ledger_head") == season_one.get("head"), "birth frame is not bound to Season 1 head")

    releases = [
        frame
        for frame in frames
        if str(frame.get("payload", {}).get("event_id", "")).startswith(
            EXPERIENCE_RELEASE_PREFIX
        )
    ]
    _require(len(releases) == 1, "park release frame must occur exactly once")
    release = releases[0]
    payload = release.get("payload", {})
    bundle_digest = state.get("integrity", {}).get("bundle_digest")
    event_head = state.get("event_ledger", {}).get("head")
    later_park_releases = [
        frame
        for frame in frames[release["seq"] + 1:]
        if (
            frame.get("payload", {}).get("organism") == PARK_ID
            and str(
                frame.get("payload", {}).get("event_id", "")
            ).startswith(EXPERIENCE_RELEASE_PREFIX)
        )
    ]
    _require(
        not later_park_releases,
        "park release frame must be the latest release for the park organism",
    )
    _require(release.get("kind") == "zoo.mutation", "park release frame kind must be zoo.mutation")
    _require(payload.get("event") == "experience-release", "release event marker mismatch")
    _require(payload.get("event_id") == EXPERIENCE_RELEASE_PREFIX + bundle_digest, "release event id is not bundle-bound")
    _require(payload.get("bundle_digest") == bundle_digest, "release frame bundle digest mismatch")
    _require(payload.get("ledger_head") == event_head, "release frame ledger head mismatch")
    _require(payload.get("synthetic_economy") is True and payload.get("real_money") is False, "release economy claims are unsafe")
    _require(release.get("prev") == birth.get("payload_hash"), "release payload link does not extend birth")
    _require(release.get("prev_wave") == birth.get("frame_hash"), "release wave link does not extend birth")
    return "birth seq {} + latest release seq {} bind Season 1 and current bundle/head".format(
        birth["seq"], release["seq"]
    )


def _syndication_values(
    root: Path,
) -> Tuple[Dict[str, Any], Dict[str, Any], List[Dict[str, Any]], List[Dict[str, Any]]]:
    index = _json(root / SYNDICATION_INDEX_RELATIVE)
    snapshot = _json(root / SYNDICATION_SNAPSHOT_RELATIVE)
    history = index.get("deltas", [])
    _require(type(history) is list and history, "syndication delta history is empty")
    deltas = []
    previous = None
    for sequence, entry in enumerate(history):
        _require(entry.get("sequence") == sequence, "delta index sequence mismatch")
        _require(entry.get("previous_delta") == previous, "delta index previous link mismatch")
        relative = entry.get("path")
        _require(type(relative) is str, "delta path is missing")
        path = root / "apps/syndication" / relative
        _require(path.is_file(), "delta file is missing: {}".format(relative))
        digest = _sha256(path)
        _require(digest == entry.get("sha256"), "delta byte digest mismatch at {}".format(sequence))
        _require(Path(relative).stem == digest, "delta filename is not content-addressed")
        delta = _json(path)
        _require(delta.get("sequence") == sequence, "delta payload sequence mismatch")
        _require(delta.get("previous_delta") == previous, "delta payload previous link mismatch")
        deltas.append(delta)
        previous = digest
    return index, snapshot, history, deltas


def _check_profile10_chain(root: Path) -> str:
    index, snapshot, history, deltas = _syndication_values(root)
    _require(index.get("profile") == PROFILE, "syndication index is not profile-10")
    _require(snapshot.get("profile") == PROFILE, "syndication snapshot is not profile-10")
    _require(deltas[-1].get("profile") == PROFILE, "head delta is not profile-10")
    head = index.get("head", {})
    _require(head.get("sequence") == len(history) - 1, "syndication head sequence mismatch")
    _require(head.get("sha256") == history[-1].get("sha256"), "syndication head digest mismatch")
    _require(snapshot.get("head") == head, "snapshot and index heads differ")
    replay = build_syndication.replay_immutable_deltas(deltas)
    build_syndication.require_snapshot_replay_agreement(snapshot, replay, history)
    return "{} immutable deltas replay to profile-10 head {}".format(
        len(history), head["sha256"][:16]
    )


def _check_data_descriptors(root: Path) -> str:
    index, snapshot, _history, deltas = _syndication_values(root)
    expected_descriptors = build_syndication.build_public_data_descriptors(
        root,
        "https://kody-w.github.io/localFirstTools-main/",
    )
    expected_by_path = {
        item.get("path"): item
        for item in expected_descriptors
        if type(item) is dict
    }
    descriptors = {
        item.get("path"): item
        for item in snapshot.get("data_objects", [])
        if type(item) is dict
    }
    _require(PARK_RESOURCE_PATHS.issubset(descriptors), "profile-10 snapshot lacks park data descriptors")
    for relative in PARK_RESOURCE_PATHS:
        _require(
            descriptors[relative] == expected_by_path.get(relative),
            "{} descriptor does not match the derived park object".format(
                relative
            ),
        )
    state = _json(root / STATE_RELATIVE)
    contract_v2 = _json(root / CONTRACT_V2_RELATIVE)
    for relative in PARK_RESOURCE_PATHS:
        descriptor = descriptors[relative]
        path = root / relative
        digest = _sha256(path)
        _require(descriptor.get("kind") == "agent-amusement-park-object", "{} descriptor kind mismatch".format(relative))
        _require(descriptor.get("sha256") == digest, "{} descriptor digest mismatch".format(relative))
        _require(descriptor.get("content_id") == "sha256:" + digest, "{} content id mismatch".format(relative))
        _require(descriptor.get("size") == path.stat().st_size, "{} descriptor size mismatch".format(relative))
        _require(
            descriptor.get("verification") == {"algorithm": "sha256", "required": True},
            "{} descriptor is not verification-required".format(relative),
        )
        _require(descriptor.get("metadata", {}).get("park_id") == PARK_ID, "{} park id mismatch".format(relative))
    _require(
        descriptors[EVENTS_RELATIVE.as_posix()]["metadata"].get("event_count")
        == state.get("event_ledger", {}).get("event_count"),
        "event descriptor count mismatch",
    )
    _require(
        descriptors[CONTRACT_V1_RELATIVE.as_posix()]["metadata"].get("resource_type")
        == "agent-contract-v1",
        "v1 contract descriptor type mismatch",
    )
    v2_metadata = descriptors[CONTRACT_V2_RELATIVE.as_posix()]["metadata"]
    _require(v2_metadata.get("resource_type") == "agent-contract-v2", "v2 contract descriptor type mismatch")
    _require(v2_metadata.get("contract_digest") == contract_v2.get("integrity", {}).get("contract_digest"), "v2 descriptor contract digest mismatch")
    _require(v2_metadata.get("bundle_digest") == state.get("integrity", {}).get("bundle_digest"), "v2 descriptor bundle digest mismatch")
    publishing_deltas = []
    for delta in deltas:
        changes = delta.get("changes", {})
        upsert_paths = {
            item.get("path")
            for item in changes.get("data_upserts", [])
            if type(item) is dict
        }
        release_frames = [
            frame
            for frame in changes.get("frame_appends", [])
            if type(frame) is dict
            and str(
                frame.get("payload", {}).get("event_id", "")
            ).startswith(EXPERIENCE_RELEASE_PREFIX)
            and frame.get("payload", {}).get("bundle_digest")
            == state.get("integrity", {}).get("bundle_digest")
        ]
        if PARK_RESOURCE_PATHS.issubset(upsert_paths) and len(release_frames) == 1:
            publishing_deltas.append((delta, release_frames[0]))
    _require(
        len(publishing_deltas) == 1,
        "profile-10 history lacks one unique park descriptor release delta",
    )
    publishing_delta, release_frame = publishing_deltas[0]
    _require(
        release_frame.get("payload", {}).get("bundle_digest")
        == state.get("integrity", {}).get("bundle_digest"),
        "profile-10 release frame bundle mismatch",
    )
    _require(index.get("profile") == PROFILE, "descriptor index profile mismatch")
    return (
        "{} derived public data objects; park release preserved in delta {}"
    ).format(len(expected_descriptors), publishing_delta.get("sequence"))


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
                "clientInfo": {"name": "agent-park-gate", "version": "1"},
            },
        },
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        {"jsonrpc": "2.0", "id": 3, "method": "resources/list", "params": {}},
        {"jsonrpc": "2.0", "id": 4, "method": "prompts/list", "params": {}},
        {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "prompts/get",
            "params": {"name": "agent_amusement_park_first_visit", "arguments": {}},
        },
        {
            "jsonrpc": "2.0",
            "id": 6,
            "method": "resources/read",
            "params": {"uri": "rappterzoo://agent-park-state"},
        },
        {
            "jsonrpc": "2.0",
            "id": 7,
            "method": "resources/read",
            "params": {"uri": "rappterzoo://agent-park-events"},
        },
        {
            "jsonrpc": "2.0",
            "id": 8,
            "method": "resources/read",
            "params": {"uri": "rappterzoo://agent-park-contract"},
        },
        {
            "jsonrpc": "2.0",
            "id": 9,
            "method": "resources/read",
            "params": {"uri": "rappterzoo://agent-park-contract-v1"},
        },
    ]
    payload = "".join(json.dumps(item, separators=(",", ":")) + "\n" for item in requests)
    process = subprocess.run(
        [sys.executable, str(script), "--root", str(root)],
        input=payload,
        text=True,
        capture_output=True,
        cwd=str(root),
        timeout=20,
        check=False,
    )
    _require(process.returncode == 0, "MCP server failed: {}".format(process.stderr.strip()))
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
    _require(set(responses) == set(range(1, 10)), "MCP did not answer every required request")
    for request_id, response in responses.items():
        _require("error" not in response, "MCP request {} failed: {}".format(request_id, response.get("error")))
    return responses


def _check_mcp_runtime(root: Path) -> str:
    responses = _mcp_requests(root)
    static = _json(root / ".well-known/mcp.json")
    initialized = responses[1]["result"]
    tools = responses[2]["result"].get("tools", [])
    resources = responses[3]["result"].get("resources", [])
    uris = {item.get("uri") for item in resources if type(item) is dict}
    _require(RUNTIME_PARK_URIS.issubset(uris), "runtime MCP park resources are incomplete")
    prompts = responses[4]["result"].get("prompts", [])
    prompt_names = {item.get("name") for item in prompts if type(item) is dict}
    _require(len(prompts) >= 2, "MCP runtime must retain at least 2 prompts")
    _require("agent_amusement_park_first_visit" in prompt_names, "runtime park prompt is missing")
    prompt_blob = json.dumps(responses[5]["result"], sort_keys=True).lower()
    for marker in ("synthetic", "local-only", "customer", "shutdown", "export"):
        _require(marker in prompt_blob, "runtime prompt omits {}".format(marker))

    version = initialized.get("serverInfo", {}).get("version", "")
    try:
        version_tuple = tuple(int(item) for item in version.split("."))
    except (TypeError, ValueError):
        version_tuple = ()
    _require(version_tuple >= (2, 4, 0), "MCP runtime predates park support")
    tool_names = {item.get("name") for item in tools if type(item) is dict}
    _require(
        {
            "agent_park_time_travel",
            "agent_park_local_action",
            "agent_park_export_branch",
        }.issubset(tool_names),
        "MCP runtime lost required park tools",
    )
    _require(len(tools) >= 11, "MCP runtime lost required tools")
    _require(len(resources) >= 29, "MCP runtime lost required resources")
    _require(
        static.get("tools") == tools,
        "static MCP tools do not exactly mirror runtime tools/list",
    )

    state_text = responses[6]["result"]["contents"][0]["text"]
    event_text = responses[7]["result"]["contents"][0]["text"]
    contract_text = responses[8]["result"]["contents"][0]["text"]
    legacy_text = responses[9]["result"]["contents"][0]["text"]
    _require(json.loads(state_text).get("park_id") == PARK_ID, "MCP state resource mismatch")
    _require(len([line for line in event_text.splitlines() if line.strip()]) > 0, "MCP event resource is empty")
    _require(json.loads(contract_text).get("schema") == "rappterzoo-agent-park-contract/2", "MCP primary contract is not v2")
    _require(json.loads(contract_text).get("write_default") == "local-branch-only", "MCP contract resource mismatch")
    _require(json.loads(legacy_text).get("schema") == "rappterzoo-agent-park-contract/1", "MCP historical contract is not v1")
    return (
        "MCP {}: {} tools, {} resources, {} prompts; "
        "v2 primary + v1 history verified"
    ).format(version, len(tools), len(resources), len(prompts))


def _check_strict_utc_parity(root: Path) -> str:
    events = _json_lines(root / EVENTS_RELATIVE)
    _require(len(events) >= 2, "park ledger cannot support an equal-UTC adversarial probe")
    attacked = copy.deepcopy(events)
    attacked[-1]["utc"] = attacked[-2]["utc"]
    projected = {
        key: copy.deepcopy(value)
        for key, value in attacked[-1].items()
        if key != "event_hash"
    }
    domain = (
        park_builder.EVENT_HASH_DOMAIN_V1
        if attacked[-1].get("schema") == park_builder.EVENT_SCHEMA_V1
        else park_builder.EVENT_HASH_DOMAIN
    )
    attacked[-1]["event_hash"] = park_builder._canonical_digest(
        domain,
        projected,
    )

    builder_rejected = False
    try:
        park_builder.verify_events(attacked)
    except park_builder.ParkError as error:
        builder_rejected = "UTC" in str(error)
    sync_rejected = False
    try:
        rappterzoo_sync.validate_agent_park_event_ledger(attacked)
    except rappterzoo_sync.SyncError as error:
        sync_rejected = "strictly increasing" in str(error)
    _require(builder_rejected, "builder accepted a correctly rehashed equal-UTC event")
    _require(sync_rejected, "sync accepted a correctly rehashed equal-UTC event")
    return "builder + sync reject correctly rehashed equal-UTC event {}".format(
        attacked[-1]["seq"]
    )


class _ParkContextMutationSource:
    def __init__(self, root: Path, mutation: Optional[str] = None) -> None:
        self.base = rappterzoo_mcp.DataSource(
            root,
            rappterzoo_mcp.DEFAULT_BASE_URL,
        )
        self.mutation = mutation

    def read_bytes(self, relative: str) -> bytes:
        return self.base.read_bytes(relative)

    def read_json(self, relative: str) -> Any:
        value = copy.deepcopy(self.base.read_json(relative))
        if relative == STATE_RELATIVE.as_posix():
            if self.mutation == "event-ledger-digest":
                value["event_ledger"]["sha256"] = "0" * 64
            elif self.mutation == "state-digest":
                value["integrity"]["state_digest"] = "0" * 64
            elif self.mutation == "bundle-digest":
                value["integrity"]["bundle_digest"] = "0" * 64
        elif relative == CONTRACT_V2_RELATIVE.as_posix():
            if self.mutation == "contract-digest":
                value["integrity"]["contract_digest"] = "0" * 64
            elif self.mutation == "bundle-digest":
                value["integrity"]["bundle_digest"] = "0" * 64
        return value


def _check_mcp_context_integrity(root: Path) -> str:
    baseline = rappterzoo_mcp.RappterZooMCP(
        _ParkContextMutationSource(root)
    )
    baseline._park_context()
    expected = {
        "event-ledger-digest": "park state event ledger facts mismatch",
        "state-digest": "park state digest mismatch",
        "contract-digest": "park v2 contract digest mismatch",
        "bundle-digest": "park bundle digest mismatch",
    }
    rejected = []
    for mutation, message in expected.items():
        runtime = rappterzoo_mcp.RappterZooMCP(
            _ParkContextMutationSource(root, mutation)
        )
        try:
            runtime._park_context()
        except rappterzoo_mcp.ToolError as error:
            _require(message in str(error), "{} rejected for the wrong reason".format(mutation))
            rejected.append(mutation)
            continue
        raise GateError("MCP _park_context accepted stale {}".format(mutation))
    return "MCP _park_context rejected {} stale digest variants".format(
        len(rejected)
    )


STATIC_CHECKS = (
    ("app.contract", _check_app_contract),
    ("app.theme", _check_theme),
    ("app.csp", _check_csp),
    ("app.same-origin-paths", _check_same_origin_paths),
    ("app.service-worker-contract", _check_service_worker_contract),
    ("registration.manifest-feed", _check_manifest_feed_registration),
    ("registration.discovery-mcp", _check_discovery_registration),
    ("registration.project-scoped-links", _check_project_scoped_links),
    ("park.bundle-exact", _check_bundle_exact),
    ("park.event-chain", _check_event_chain),
    ("park.strict-utc-parity", _check_strict_utc_parity),
    ("park.season-prefix-contracts", _check_season_prefix_and_contracts),
    ("park.synthetic-economy", _check_synthetic_economy),
    ("park.resources-evolution", _check_resources_evolution),
    ("park.customer-controls", _check_customer_controls),
    ("park.v2-contract-spec", _check_v2_contract_spec),
    ("organism.dual-link-chain", _check_organism_chain),
    ("organism.experience-release", _check_experience_frames),
    ("syndication.profile10-chain", _check_profile10_chain),
    ("syndication.data-descriptors", _check_data_descriptors),
    ("mcp.park-context-integrity", _check_mcp_context_integrity),
    ("mcp.runtime-prompt-resources", _check_mcp_runtime),
)


def run_static_checks(root: Path) -> List[CheckResult]:
    repository = Path(root).resolve()
    return [
        _run_check(name, partial(check, repository))
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
const nodeCrypto = require("crypto");
const target = process.argv[1];
const expectedEvents = Number(process.argv[2]);
const expectedFrames = Number(process.argv[3]);

const results = {};
function record(name, pass, detail) {
  results[name] = { pass: Boolean(pass), detail: String(detail) };
}
function text(page, selector) {
  return page.locator(selector).textContent().then((value) => (value || "").trim());
}
async function click(page, selector) {
  const locator = page.locator(selector);
  await locator.waitFor({ state: "visible", timeout: 8000 });
  await locator.click();
}
async function waitCanonical(page) {
  await page.waitForFunction(
    ([events, frames]) => {
      const data = document.querySelector("#dataStatus")?.textContent || "";
      const integrity = document.querySelector("#integrityDetail")?.textContent || "";
      const status = document.querySelector("#integrityStatus")?.textContent || "";
      const timeline = document.querySelector("#timelineCount")?.textContent || "";
      const canonicalSource = data.includes("4/4 same-origin resources")
        || data.includes("Cached/offline · 4/4 resources");
      return canonicalSource
        && integrity.includes(events + " park events")
        && integrity.includes(frames + " organism frames")
        && integrity.includes("head matches")
        && integrity.includes("canonical public resources")
        && status.includes("Append-only chain linked")
        && timeline === events + " / " + events;
    },
    [expectedEvents, expectedFrames],
    { timeout: 12000 }
  );
}
function attachDiagnostics(page, origin) {
  const values = { errors: [], external: [], requests: [], responses: [] };
  page.on("console", (message) => {
    if (message.type() === "error") values.errors.push("console: " + message.text());
  });
  page.on("pageerror", (error) => values.errors.push("page: " + (error.message || String(error))));
  page.on("requestfailed", (request) => {
    values.errors.push("request: " + request.url() + " " + (request.failure()?.errorText || "failed"));
  });
  page.on("response", (response) => {
    values.responses.push([response.status(), response.url()]);
    if (response.status() >= 400) values.errors.push("http: " + response.status() + " " + response.url());
  });
  page.on("request", (request) => {
    const url = request.url();
    values.requests.push(url);
    if (/^(?:data|blob|about):/i.test(url)) return;
    if (new URL(url).origin !== origin) values.external.push(url);
  });
  return values;
}
async function interceptDownloads(page) {
  await page.evaluate(() => {
    window.__gateDownloads = [];
    window.__gateLastBlob = null;
    URL.createObjectURL = (blob) => {
      window.__gateLastBlob = blob;
      return "blob:agent-park-gate/" + window.__gateDownloads.length;
    };
    HTMLAnchorElement.prototype.click = function() {
      window.__gateDownloads.push({
        download: this.download || "",
        blob: window.__gateLastBlob
      });
    };
  });
}
async function readDownloads(page) {
  return page.evaluate(async () => Promise.all(
    (window.__gateDownloads || []).map(async (item) => ({
      download: item.download,
      size: item.blob?.size || 0,
      text: item.blob ? await item.blob.text() : ""
    }))
  ));
}
async function waitOfflineReady(page) {
  await page.waitForFunction(
    () => (document.querySelector("#offlineStatus")?.textContent || "").includes("Offline ready"),
    null,
    { timeout: 15000 }
  );
}
async function serviceWorkerStatus(page) {
  return page.evaluate(async () => {
    const registration = await navigator.serviceWorker.ready;
    const target = registration.active || navigator.serviceWorker.controller;
    if (!target) return { ready: false, cached: [], contractSource: "missing" };
    return new Promise((resolve, reject) => {
      const channel = new MessageChannel();
      const timeout = setTimeout(() => reject(new Error("service worker status timeout")), 3000);
      channel.port1.onmessage = (event) => {
        clearTimeout(timeout);
        resolve({
          ...event.data,
          scope: registration.scope,
          scriptURL: target.scriptURL
        });
      };
      target.postMessage({ type: "CACHE_STATUS" }, [channel.port2]);
    });
  });
}
async function serviceWorkerSafety(page) {
  return page.evaluate(async () => {
    const registration = await navigator.serviceWorker.ready;
    const target = registration.active || navigator.serviceWorker.controller;
    if (!target) return { ok: false, engaged: null };
    return new Promise((resolve, reject) => {
      const channel = new MessageChannel();
      const timeout = setTimeout(() => reject(new Error("service-worker safety status timed out")), 5000);
      channel.port1.onmessage = (event) => {
        clearTimeout(timeout);
        resolve(event.data);
      };
      target.postMessage({ type: "SAFETY_STOP_GET" }, [channel.port2]);
    });
  });
}
function branchActionCount(page) {
  return page.locator("#branchLog li").evaluateAll((nodes) =>
    nodes.filter((node) => !(node.textContent || "").includes("No local actions yet")).length
  );
}
function canonicalValue(value) {
  if (Array.isArray(value)) return value.map(canonicalValue);
  if (value && typeof value === "object") {
    return Object.keys(value).sort().reduce((result, key) => {
      result[key] = canonicalValue(value[key]);
      return result;
    }, {});
  }
  return typeof value === "string" ? value.normalize("NFC") : value;
}
function canonicalJson(value) {
  return JSON.stringify(canonicalValue(value));
}
function canonicalSha256(value, domain = "") {
  return nodeCrypto.createHash("sha256").update(domain + canonicalJson(value), "utf8").digest("hex");
}
function recomputeBranchDigest(value) {
  const projected = structuredClone(value);
  delete projected.branch_digest;
  value.branch_digest = canonicalSha256(projected);
  return value;
}
function recomputeFullDigest(value) {
  const projected = structuredClone(value);
  delete projected.content_digest;
  value.content_digest = canonicalSha256(
    projected,
    "rappterzoo/agent-park-full-export/2\n"
  );
  return value;
}
async function importRejected(page, filename, payload) {
  await page.locator("#importFileInput").setInputFiles({
    name: filename,
    mimeType: "application/json",
    buffer: Buffer.from(JSON.stringify(payload))
  });
  await page.evaluate(() => {
    const result = document.querySelector("#importResult");
    if (result) result.textContent = "gate-awaiting-import";
  });
  await click(page, "#importReplayButton");
  await page.waitForFunction(
    () => {
      const value = document.querySelector("#importResult")?.textContent || "";
      return !value.includes("gate-awaiting-import")
        && !value.includes("Computing local chain and digest evidence");
    },
    null,
    { timeout: 12000 }
  );
  return text(page, "#importResult");
}
async function mobileResult(browser, width) {
  const context = await browser.newContext({
    viewport: { width, height: 844 },
    reducedMotion: "reduce"
  });
  const page = await context.newPage();
  await page.goto(target, { waitUntil: "domcontentloaded", timeout: 12000 });
  await waitCanonical(page);
  const value = await page.evaluate(() => {
    const root = document.documentElement;
    const overflow = Array.from(document.querySelectorAll("body *"))
      .filter((node) => {
        const style = getComputedStyle(node);
        if (style.position === "fixed" || style.display === "none" || style.visibility === "hidden") return false;
        const rect = node.getBoundingClientRect();
        return rect.right > root.clientWidth + 1 || rect.left < -1;
      })
      .slice(0, 10)
      .map((node) => node.id || node.tagName);
    const selector = [
      "#emergencyButton", "#parkSourceButton", "#organismSourceButton",
      "#firstButton", "#previousButton", "#playButton", "#nextButton",
      "#dispatchButton", "#negotiateButton", "#inventButton", "#simulateButton",
      "#exportBranchButton", "#clearBranchButton", "#undoClearButton",
      "#enableEncryptedStorageButton", "#disableEncryptedStorageButton",
      "#importReplayButton", "#exportLedgerButton"
    ].join(",");
    const targets = Array.from(document.querySelectorAll(selector)).map((node) => {
      const rect = node.getBoundingClientRect();
      return { id: node.id, width: rect.width, height: rect.height };
    });
    return {
      clientWidth: root.clientWidth,
      scrollWidth: root.scrollWidth,
      overflow,
      targets,
      smallTargets: targets.filter((item) => item.width < 44 || item.height < 44)
    };
  });
  await context.close();
  return value;
}

(async () => {
  let browser;
  try {
    browser = await chromium.launch({ headless: true });
    const origin = new URL(target).origin;
    const context = await browser.newContext({
      viewport: { width: 1280, height: 800 },
      permissions: ["clipboard-read", "clipboard-write"]
    });
    const page = await context.newPage();
    const diagnostics = attachDiagnostics(page, origin);
    await page.goto(target, { waitUntil: "domcontentloaded", timeout: 12000 });
    await waitCanonical(page);
    const requiredRequests = [
      "/apps/agent-park/park-state.json",
      "/apps/agent-park/events.jsonl",
      "/apps/agent-park/agent-contract-v2.json",
      "/apps/organism-frames.json"
    ];
    const requestPaths = diagnostics.requests.map((value) => new URL(value).pathname);
    const coldData = await text(page, "#dataStatus");
    const coldPass = diagnostics.errors.length === 0
      && diagnostics.external.length === 0
      && requiredRequests.every((path) => requestPaths.includes(path))
      && coldData.includes("4/4 same-origin resources")
      && !coldData.includes("Cached/offline")
      && (await text(page, "#timelineCount")) === expectedEvents + " / " + expectedEvents;
    record(
      "browser.cold-start",
      coldPass,
      "errors=" + diagnostics.errors.length + ", external=" + diagnostics.external.length
        + ", same-origin data=" + requiredRequests.filter((path) => requestPaths.includes(path)).length + "/4"
        + ", source=" + coldData
    );

    await waitOfflineReady(page);
    const cacheStatus = await serviceWorkerStatus(page);
    const cachedPaths = (cacheStatus.cached || []).map((value) => new URL(value).pathname);
    const cachedRequired = [
      "/apps/3d-immersive/agent-amusement-park.html",
      "/apps/agent-park/park-state.json",
      "/apps/agent-park/events.jsonl",
      "/apps/agent-park/agent-contract-v2.json",
      "/apps/organism-frames.json"
    ];
    record(
      "browser.service-worker-cache",
      cacheStatus.ready === true && cacheStatus.contractSource === "v2"
        && /^rappterzoo-agent-park-v2-/.test(cacheStatus.version || "")
        && new URL(cacheStatus.scriptURL).pathname === "/apps/3d-immersive/agent-amusement-park-sw.js"
        && new URL(cacheStatus.scope).pathname === "/apps/3d-immersive/"
        && cachedRequired.every((path) => cachedPaths.includes(path)),
      "ready=" + cacheStatus.ready + ", contract=" + cacheStatus.contractSource
        + ", cached=" + cachedRequired.filter((path) => cachedPaths.includes(path)).length + "/5"
        + ", scope=" + cacheStatus.scope
    );

    await context.setOffline(true);
    await page.reload({ waitUntil: "domcontentloaded", timeout: 12000 });
    await waitCanonical(page);
    const warmOffline = await page.evaluate(() => ({
      title: document.title,
      data: document.querySelector("#dataStatus")?.textContent || "",
      integrity: document.querySelector("#integrityStatus")?.textContent || "",
      timeline: document.querySelector("#timelineCount")?.textContent || ""
    }));
    record(
      "browser.warm-offline-reload",
      warmOffline.title.includes("Agent Amusement Park")
        && warmOffline.integrity.includes("Append-only chain linked")
        && warmOffline.timeline === expectedEvents + " / " + expectedEvents,
      "offline full-page reload timeline=" + warmOffline.timeline
    );
    record(
      "browser.cached-provenance",
      warmOffline.data.includes("Cached/offline · 4/4 resources from verified cache")
        && !warmOffline.data.includes("live"),
      "offline source label=" + warmOffline.data
    );
    await context.setOffline(false);
    await page.reload({ waitUntil: "domcontentloaded", timeout: 12000 });
    await waitCanonical(page);
    await waitOfflineReady(page);

    const requiredControls = [
      "#parkSourceButton", "#organismSourceButton", "#firstButton", "#previousButton",
      "#playButton", "#nextButton", "#timelineRange", "#copyEvidenceButton",
      "#copyShareButton", "#destinationSelect", "#dispatchButton", "#negotiateButton",
      "#inventButton", "#simulateButton", "#exportBranchButton", "#clearBranchButton",
      "#undoClearButton", "#timestampedExportInput", "#branchPassphraseInput",
      "#enableEncryptedStorageButton", "#disableEncryptedStorageButton",
      "#importFileInput", "#importReplayButton", "#modelRouteSelect",
      "#exportLedgerButton", "#copyCustodyButton", "#emergencyButton"
    ];
    const missingControls = [];
    for (const selector of requiredControls) {
      if (await page.locator(selector).count() !== 1) missingControls.push(selector);
    }
    await click(page, "#firstButton");
    const firstSeq = await text(page, "#evidenceSeq");
    await click(page, "#nextButton");
    const nextSeq = await text(page, "#evidenceSeq");
    await page.locator("#timelineRange").fill("3");
    const rangeSeq = await text(page, "#evidenceSeq");
    await page.locator("#modelRouteSelect").selectOption("air-gapped-replay");
    const preference = await page.evaluate(() =>
      localStorage.getItem("rappterzoo-agent-park-preferences-v1") || ""
    );
    await click(page, "#copyEvidenceButton");
    await click(page, "#copyShareButton");
    await click(page, "#copyCustodyButton");
    const clipboard = await page.evaluate(() => navigator.clipboard.readText().catch(() => ""));
    record(
      "browser.major-controls",
      missingControls.length === 0 && firstSeq === "0" && nextSeq === "1"
        && rangeSeq === "3" && preference.includes("air-gapped-replay")
        && clipboard.includes("Customer holds runtime keys"),
      "controls=" + (requiredControls.length - missingControls.length) + "/" + requiredControls.length
        + ", timeline=" + firstSeq + "→" + nextSeq + "→" + rangeSeq
    );

    await click(page, "#playButton");
    await page.waitForTimeout(120);
    await click(page, "#emergencyButton");
    await page.waitForFunction(
      () => localStorage.getItem("rappterzoo-agent-park-emergency-stop-v1") === "engaged"
        && document.querySelector("#emergencyButton")?.getAttribute("aria-pressed") === "true"
        && (document.querySelector("#controlNotice")?.textContent || "").includes("durably marked"),
      null,
      { timeout: 8000 }
    );
    const stoppedWorker = await serviceWorkerSafety(page);
    const stopped = await page.evaluate(() => ({
      pressed: document.querySelector("#emergencyButton")?.getAttribute("aria-pressed"),
      label: document.querySelector("#emergencyButton")?.textContent || "",
      playing: document.querySelector("#playButton")?.getAttribute("aria-pressed"),
      disabled: Array.from(document.querySelectorAll(".local-action")).every((node) => node.disabled),
      body: document.body.classList.contains("is-stopped"),
      marker: localStorage.getItem("rappterzoo-agent-park-emergency-stop-v1")
    }));
    await page.reload({ waitUntil: "domcontentloaded", timeout: 12000 });
    await waitCanonical(page);
    await page.waitForFunction(
      () => document.querySelector("#emergencyButton")?.getAttribute("aria-pressed") === "true",
      null,
      { timeout: 8000 }
    );
    const restoredStop = await page.evaluate(() => ({
      pressed: document.querySelector("#emergencyButton")?.getAttribute("aria-pressed"),
      disabled: Array.from(document.querySelectorAll(".local-action")).every((node) => node.disabled),
      notice: document.querySelector("#controlNotice")?.textContent || ""
    }));
    const restoredWorker = await serviceWorkerSafety(page);
    await click(page, "#emergencyButton");
    await page.waitForFunction(
      () => document.querySelector("#emergencyButton")?.getAttribute("aria-pressed") === "false"
        && localStorage.getItem("rappterzoo-agent-park-emergency-stop-v1") === null,
      null,
      { timeout: 8000 }
    );
    await page.reload({ waitUntil: "domcontentloaded", timeout: 12000 });
    await waitCanonical(page);
    const rearmedWorker = await serviceWorkerSafety(page);
    const rearmed = await page.evaluate(() => ({
      pressed: document.querySelector("#emergencyButton")?.getAttribute("aria-pressed"),
      label: document.querySelector("#emergencyButton")?.textContent || "",
      enabled: Array.from(document.querySelectorAll(".local-action")).every((node) => !node.disabled),
      body: !document.body.classList.contains("is-stopped"),
      marker: localStorage.getItem("rappterzoo-agent-park-emergency-stop-v1")
    }));
    record(
      "browser.durable-emergency-rearm",
      stopped.pressed === "true" && stopped.label.includes("Re-arm")
        && stopped.playing === "false" && stopped.disabled && stopped.body
        && stopped.marker === "engaged"
        && stoppedWorker.ok === true && stoppedWorker.engaged === true
        && restoredStop.pressed === "true" && restoredStop.disabled
        && restoredStop.notice.includes("Durable emergency stop restored")
        && restoredWorker.ok === true && restoredWorker.engaged === true
        && rearmed.pressed === "false" && rearmed.label.includes("Emergency stop")
        && rearmed.enabled && rearmed.body && rearmed.marker === null
        && rearmedWorker.ok === true && rearmedWorker.engaged === false,
      "stop persisted across reload=" + (restoredStop.pressed === "true")
        + ", worker marker=" + stoppedWorker.engaged + "→" + rearmedWorker.engaged
        + ", explicit re-arm survived reload=" + (rearmed.pressed === "false")
    );

    await click(page, "#parkSourceButton");
    await click(page, "#firstButton");
    const parkFirst = await page.evaluate(() => ({
      seq: document.querySelector("#evidenceSeq")?.textContent || "",
      count: document.querySelector("#timelineCount")?.textContent || "",
      hash: document.querySelector("#evidenceHash")?.textContent || ""
    }));
    await page.locator("#timelineRange").fill(String(expectedEvents - 1));
    const parkLast = await text(page, "#evidenceSeq");
    record(
      "browser.park-time-travel",
      parkFirst.seq.trim() === "0" && parkFirst.count.trim() === "1 / " + expectedEvents
        && parkLast === String(expectedEvents - 1) && parkFirst.hash.length > 20,
      "park seq 0→" + parkLast + " across " + expectedEvents + " events"
    );

    await click(page, "#organismSourceButton");
    await click(page, "#firstButton");
    const organismFirst = await page.evaluate(() => ({
      seq: document.querySelector("#evidenceSeq")?.textContent || "",
      count: document.querySelector("#timelineCount")?.textContent || "",
      source: document.querySelector("#sourceDetail")?.textContent || ""
    }));
    await page.locator("#timelineRange").fill(String(expectedFrames - 1));
    const organismLast = await text(page, "#evidenceSeq");
    record(
      "browser.organism-time-travel",
      organismFirst.seq.trim() === "0"
        && organismFirst.count.trim() === "1 / " + expectedFrames
        && organismFirst.source.includes("Organism frame")
        && organismLast === String(expectedFrames - 1),
      "organism seq 0→" + organismLast + " across " + expectedFrames + " frames"
    );

    await click(page, "#parkSourceButton");
    await page.evaluate(() => {
      localStorage.removeItem("rappterzoo-agent-park-local-branch-v1");
      localStorage.removeItem("rappterzoo-agent-park-local-branch-encrypted-v2");
    });
    const defaultBefore = await page.evaluate(() => ({
      mode: document.querySelector("#branchStorageMode")?.textContent || "",
      legacy: localStorage.getItem("rappterzoo-agent-park-local-branch-v1"),
      encrypted: localStorage.getItem("rappterzoo-agent-park-local-branch-encrypted-v2")
    }));
    await page.locator("#agentIdInput").fill("memory-only-sentinel");
    await click(page, "#dispatchButton");
    const defaultAfter = await page.evaluate(() => ({
      legacy: localStorage.getItem("rappterzoo-agent-park-local-branch-v1"),
      encrypted: localStorage.getItem("rappterzoo-agent-park-local-branch-encrypted-v2")
    }));
    const defaultActionCount = await branchActionCount(page);
    await page.reload({ waitUntil: "domcontentloaded", timeout: 12000 });
    await waitCanonical(page);
    const defaultReloadCount = await branchActionCount(page);
    record(
      "browser.memory-only-default",
      defaultBefore.mode.includes("Memory-only")
        && defaultBefore.legacy === null && defaultBefore.encrypted === null
        && defaultActionCount === 1
        && defaultAfter.legacy === null && defaultAfter.encrypted === null
        && defaultReloadCount === 0,
      "memory actions=" + defaultActionCount + ", plaintext keys absent, reload actions=" + defaultReloadCount
    );

    await page.locator("#agentIdInput").fill("encrypted-plaintext-sentinel");
    await click(page, "#dispatchButton");
    await page.locator("#branchPassphraseInput").fill("correct horse battery staple");
    await click(page, "#enableEncryptedStorageButton");
    await page.waitForFunction(
      () => Boolean(localStorage.getItem("rappterzoo-agent-park-local-branch-encrypted-v2")),
      null,
      { timeout: 12000 }
    );
    const encrypted = await page.evaluate(() => {
      const raw = localStorage.getItem("rappterzoo-agent-park-local-branch-encrypted-v2") || "";
      const value = JSON.parse(raw);
      return {
        raw,
        value,
        legacy: localStorage.getItem("rappterzoo-agent-park-local-branch-v1"),
        mode: document.querySelector("#branchStorageMode")?.textContent || ""
      };
    });
    record(
      "browser.encrypted-persistence",
      encrypted.value.schema === "rappterzoo-agent-park-encrypted-branch/1"
        && encrypted.value.algorithm === "AES-GCM"
        && encrypted.value.kdf === "PBKDF2-SHA-256"
        && encrypted.value.iterations === 250000
        && encrypted.value.salt && encrypted.value.iv && encrypted.value.ciphertext
        && encrypted.value.scope?.origin === origin
        && encrypted.value.scope?.path === new URL(target).pathname
        && encrypted.legacy === null && encrypted.mode.includes("unlocked")
        && !encrypted.raw.includes("encrypted-plaintext-sentinel")
        && !encrypted.raw.includes("local.visit"),
      "AES-GCM envelope bytes=" + encrypted.raw.length + ", plaintext absent="
        + (!encrypted.raw.includes("encrypted-plaintext-sentinel"))
    );

    const envelopeBeforeWrong = encrypted.raw;
    await page.reload({ waitUntil: "domcontentloaded", timeout: 12000 });
    await waitCanonical(page);
    await page.waitForFunction(
      () => (document.querySelector("#branchStorageMode")?.textContent || "").includes("locked"),
      null,
      { timeout: 8000 }
    );
    await page.locator("#branchPassphraseInput").fill("definitely-wrong-passphrase");
    await click(page, "#enableEncryptedStorageButton");
    await page.waitForFunction(
      () => (document.querySelector("#agentNotice")?.textContent || "").includes("Passphrase rejected"),
      null,
      { timeout: 8000 }
    );
    const wrong = await page.evaluate(() => ({
      notice: document.querySelector("#agentNotice")?.textContent || "",
      mode: document.querySelector("#branchStorageMode")?.textContent || "",
      envelope: localStorage.getItem("rappterzoo-agent-park-local-branch-encrypted-v2")
    }));
    const wrongActionCount = await branchActionCount(page);
    record(
      "browser.wrong-passphrase",
      wrong.notice.includes("Passphrase rejected")
        && wrong.mode.includes("locked")
        && wrongActionCount === 0
        && wrong.envelope === envelopeBeforeWrong,
      "wrong passphrase rejected without replay or envelope mutation"
    );

    await page.locator("#branchPassphraseInput").fill("correct horse battery staple");
    await click(page, "#enableEncryptedStorageButton");
    await page.waitForFunction(
      () => (document.querySelector("#branchStorageMode")?.textContent || "").includes("unlocked"),
      null,
      { timeout: 12000 }
    );
    if ((await branchActionCount(page)) !== 1) throw new Error("correct passphrase did not replay one encrypted action");
    const timestampedDefault = await page.locator("#timestampedExportInput").isChecked();
    await interceptDownloads(page);
    await click(page, "#exportBranchButton");
    await page.waitForFunction(() => (window.__gateDownloads || []).length >= 1);
    await click(page, "#exportBranchButton");
    await page.waitForFunction(() => (window.__gateDownloads || []).length >= 2);
    await click(page, "#exportLedgerButton");
    await page.waitForFunction(() => (window.__gateDownloads || []).length >= 3);
    await click(page, "#exportLedgerButton");
    await page.waitForFunction(() => (window.__gateDownloads || []).length >= 4);
    const downloads = await readDownloads(page);
    const branchExports = downloads.filter((item) =>
      item.download === "rappterzoo-agent-park-local-branch.json"
    );
    const fullExports = downloads.filter((item) =>
      item.download === "rappterzoo-agent-park-full-ledger.json"
    );
    const branchText = branchExports[0]?.text || "";
    const fullText = fullExports[0]?.text || "";
    const branchPayload = JSON.parse(branchText);
    const fullPayload = JSON.parse(fullText);
    const branchProjected = structuredClone(branchPayload);
    delete branchProjected.branch_digest;
    const fullProjected = structuredClone(fullPayload);
    delete fullProjected.content_digest;
    const branchDigestMatches = branchPayload.branch_digest === canonicalSha256(branchProjected);
    const fullDigestMatches = fullPayload.content_digest === canonicalSha256(
      fullProjected,
      "rappterzoo/agent-park-full-export/2\n"
    );
    record(
      "browser.deterministic-exports",
      timestampedDefault === false
        && branchExports.length === 2 && fullExports.length === 2
        && branchExports[0].text === branchExports[1].text
        && fullExports[0].text === fullExports[1].text
        && !branchText.includes('"exported_at"') && !fullText.includes('"exported_at"')
        && branchPayload.export_schema === "rappterzoo-agent-park-local-branch/2"
        && fullPayload.export_schema === "rappterzoo-agent-park-full-export/2"
        && branchDigestMatches && fullDigestMatches,
      "branch bytes=" + branchText.length + ", full bytes=" + fullText.length
        + ", default timestamped=" + timestampedDefault + ", pairwise byte equality=true"
    );

    const forgedSchema = recomputeBranchDigest(structuredClone(branchPayload));
    forgedSchema.export_schema = "rappterzoo-agent-park-local-branch/999";
    recomputeBranchDigest(forgedSchema);
    const missingBranchDigest = structuredClone(branchPayload);
    delete missingBranchDigest.branch_digest;
    const zeroHeads = structuredClone(branchPayload);
    zeroHeads.canonical_event_head = "0".repeat(64);
    zeroHeads.canonical_organism_head = "0".repeat(64);
    recomputeBranchDigest(zeroHeads);
    const forgedSchemaResult = await importRejected(page, "forged-schema.json", forgedSchema);
    const missingBranchDigestResult = await importRejected(
      page,
      "missing-branch-digest.json",
      missingBranchDigest
    );
    const zeroHeadsResult = await importRejected(page, "zero-heads.json", zeroHeads);
    const branchAfterAdversarial = await branchActionCount(page);
    record(
      "browser.branch-import-adversarial",
      forgedSchemaResult.includes("Unsupported export schema")
        && missingBranchDigestResult.includes("Branch digest: MISSING")
        && zeroHeadsResult.includes("Canonical event head: MISMATCH")
        && zeroHeadsResult.includes("Canonical organism head: MISMATCH")
        && branchAfterAdversarial === 1,
      "forged schema, missing branch_digest, and correctly redigested zero heads rejected; actions="
        + branchAfterAdversarial
    );

    await click(page, "#clearBranchButton");
    await page.waitForFunction(
      () => (document.querySelector("#clearBranchButton")?.textContent || "").includes("Confirm clear")
    );
    const staleCheckpoint = await page.evaluate(() => ({
      label: document.querySelector("#clearBranchButton")?.textContent || "",
      pressed: document.querySelector("#clearBranchButton")?.getAttribute("aria-pressed"),
      undoDisabled: document.querySelector("#undoClearButton")?.disabled,
      notice: document.querySelector("#agentNotice")?.textContent || ""
    }));
    await page.locator("#agentIdInput").fill("intervening-clear-mutation");
    await click(page, "#dispatchButton");
    await page.waitForFunction(
      () => document.querySelectorAll("#branchLog li").length === 2
    );
    const afterIntervening = await page.evaluate(() => ({
      label: document.querySelector("#clearBranchButton")?.textContent || "",
      pressed: document.querySelector("#clearBranchButton")?.getAttribute("aria-pressed"),
      undoDisabled: document.querySelector("#undoClearButton")?.disabled
    }));
    await click(page, "#clearBranchButton");
    await page.waitForFunction(
      () => {
        const label = document.querySelector("#clearBranchButton")?.textContent || "";
        const branch = document.querySelector("#branchLog")?.textContent || "";
        return label.includes("Confirm clear") || branch.includes("No local actions yet");
      }
    );
    const refreshedCheckpoint = await page.evaluate(() => ({
      label: document.querySelector("#clearBranchButton")?.textContent || "",
      pressed: document.querySelector("#clearBranchButton")?.getAttribute("aria-pressed"),
      undoDisabled: document.querySelector("#undoClearButton")?.disabled
    }));
    record(
      "browser.clear-intervening-mutation",
      staleCheckpoint.label.includes("Confirm clear")
        && staleCheckpoint.pressed === "true" && staleCheckpoint.undoDisabled === false
        && staleCheckpoint.notice.includes("Verified clear checkpoint")
        && afterIntervening.label.includes("Clear local branch")
        && afterIntervening.pressed === "false" && afterIntervening.undoDisabled === true
        && refreshedCheckpoint.label.includes("Confirm clear")
        && refreshedCheckpoint.pressed === "true"
        && (await branchActionCount(page)) === 2,
      "intervening action invalidated stale confirm/undo; fresh checkpoint preserved 2 actions"
    );

    if (refreshedCheckpoint.label.includes("Confirm clear")) {
      await click(page, "#clearBranchButton");
      await page.waitForFunction(
        () => (document.querySelector("#branchLog")?.textContent || "").includes("No local actions yet")
      );
    }
    const afterClearCount = await branchActionCount(page);
    const afterClear = await page.evaluate(() => ({
      label: document.querySelector("#clearBranchButton")?.textContent || "",
      pressed: document.querySelector("#clearBranchButton")?.getAttribute("aria-pressed"),
      undoDisabled: document.querySelector("#undoClearButton")?.disabled
    }));
    if (await page.locator("#undoClearButton").isEnabled()) {
      await click(page, "#undoClearButton");
      await page.waitForFunction(
        () => !(document.querySelector("#branchLog")?.textContent || "").includes("No local actions yet")
      );
    }
    const afterUndoCount = await branchActionCount(page);
    const afterUndo = await page.evaluate(() => ({
      label: document.querySelector("#clearBranchButton")?.textContent || "",
      pressed: document.querySelector("#clearBranchButton")?.getAttribute("aria-pressed"),
      undoDisabled: document.querySelector("#undoClearButton")?.disabled
    }));
    record(
      "browser.clear-checkpoint-undo",
      refreshedCheckpoint.label.includes("Confirm clear")
        && refreshedCheckpoint.pressed === "true" && refreshedCheckpoint.undoDisabled === false
        && afterClearCount === 0 && afterClear.label.includes("Clear local branch")
        && afterClear.pressed === "false" && afterClear.undoDisabled === false
        && afterUndoCount === 2 && afterUndo.label.includes("Clear local branch")
        && afterUndo.pressed === "false" && afterUndo.undoDisabled === true,
      "checkpoint→clear(" + afterClearCount + ")→undo(" + afterUndoCount + ")"
    );

    await click(page, "#clearBranchButton");
    await page.waitForFunction(
      () => (document.querySelector("#clearBranchButton")?.textContent || "").includes("Confirm clear")
    );
    await click(page, "#clearBranchButton");
    await page.waitForFunction(
      () => (document.querySelector("#branchLog")?.textContent || "").includes("No local actions yet")
    );
    await page.locator("#importFileInput").setInputFiles({
      name: "branch.json",
      mimeType: "application/json",
      buffer: Buffer.from(branchText)
    });
    await click(page, "#importReplayButton");
    await page.waitForFunction(
      () => (document.querySelector("#importResult")?.textContent || "").includes("Local branch verification: VALID"),
      null,
      { timeout: 12000 }
    );
    const branchImport = await page.evaluate(() => ({
      result: document.querySelector("#importResult")?.textContent || "",
      notice: document.querySelector("#agentNotice")?.textContent || ""
    }));
    const branchImportCount = await branchActionCount(page);
    record(
      "browser.branch-import-replay",
      branchImport.result.includes("Export schema: MATCH")
        && branchImport.result.includes("Required fields: EXACT")
        && branchImport.result.includes("Canonical event head: MATCH")
        && branchImport.result.includes("Canonical organism head: MATCH")
        && branchImport.result.includes("Actions: 1")
        && branchImport.result.includes("Branch digest: MATCH")
        && branchImport.notice.includes("Verified local branch replayed")
        && branchImportCount === 1,
      "branch import declared-vs-computed digest MATCH; one action replayed"
    );

    const missingContentDigest = structuredClone(fullPayload);
    delete missingContentDigest.content_digest;
    const tamperedOrganism = structuredClone(fullPayload);
    tamperedOrganism.organism_universe.frames.at(-1).payload.gate_tamper = true;
    recomputeFullDigest(tamperedOrganism);
    const missingContentResult = await importRejected(
      page,
      "missing-content-digest.json",
      missingContentDigest
    );
    const tamperedOrganismResult = await importRejected(
      page,
      "tampered-organism.json",
      tamperedOrganism
    );
    record(
      "browser.full-import-adversarial",
      missingContentResult.includes("Mandatory release-2 content_digest is missing or malformed")
        && tamperedOrganismResult.includes("Organism chain:")
        && tamperedOrganismResult.includes("Organism payload digest mismatch")
        && tamperedOrganismResult.includes("Full ledger verification: REJECTED")
        && (await branchActionCount(page)) === 1,
      "missing content_digest and content-redigested organism payload tamper rejected"
    );

    await page.locator("#importFileInput").setInputFiles({
      name: "full-ledger.json",
      mimeType: "application/json",
      buffer: Buffer.from(fullText)
    });
    await click(page, "#importReplayButton");
    await page.waitForFunction(
      () => (document.querySelector("#importResult")?.textContent || "").includes("Full ledger verification: VALID"),
      null,
      { timeout: 20000 }
    );
    const fullImport = await page.evaluate(() => ({
      result: document.querySelector("#importResult")?.textContent || "",
      notice: document.querySelector("#agentNotice")?.textContent || "",
      timeline: document.querySelector("#timelineCount")?.textContent || ""
    }));
    record(
      "browser.full-import-replay",
      fullImport.result.includes("Event heads: MATCH")
        && fullImport.result.includes("computed")
        && fullImport.result.includes("Event ledger SHA-256: MATCH")
        && fullImport.result.includes("State digest: MATCH")
        && fullImport.result.includes("Contract digest: MATCH")
        && fullImport.result.includes("Bundle digest: MATCH")
        && fullImport.result.includes("Organism head: MATCH")
        && fullImport.result.includes("Export content digest: MATCH")
        && fullImport.notice.includes("Verified full ledger replay loaded")
        && fullImport.timeline === expectedEvents + " / " + expectedEvents,
      "full import recomputed head, ledger, state, contract, bundle, and export digests"
    );
    await context.close();

    const deniedContext = await browser.newContext({ viewport: { width: 1280, height: 800 } });
    await deniedContext.addInitScript(() => {
      const denied = () => { throw new DOMException("denied", "SecurityError"); };
      Object.defineProperty(Storage.prototype, "getItem", { value: denied });
      Object.defineProperty(Storage.prototype, "setItem", { value: denied });
      Object.defineProperty(Storage.prototype, "removeItem", { value: denied });
    });
    const deniedPage = await deniedContext.newPage();
    const deniedErrors = [];
    deniedPage.on("pageerror", (error) => deniedErrors.push(error.message || String(error)));
    await deniedPage.goto(target, { waitUntil: "domcontentloaded", timeout: 12000 });
    await waitCanonical(deniedPage);
    await click(deniedPage, "#dispatchButton");
    const denied = await deniedPage.evaluate(() => ({
      status: document.querySelector("#storageStatus")?.textContent || "",
      branch: document.querySelector("#branchLog")?.textContent || "",
      notice: document.querySelector("#agentNotice")?.textContent || ""
    }));
    record(
      "browser.storage-denied",
      deniedErrors.length === 0 && denied.status.includes("Storage denied")
        && denied.branch.includes("local.visit") && denied.notice.includes("dispatched"),
      "in-memory branch survived denied storage; errors=" + deniedErrors.length
    );
    await deniedContext.close();

    const reduceContext = await browser.newContext({
      viewport: { width: 1280, height: 800 },
      reducedMotion: "reduce"
    });
    const reducePage = await reduceContext.newPage();
    await reducePage.goto(target, { waitUntil: "domcontentloaded", timeout: 12000 });
    await waitCanonical(reducePage);
    await click(reducePage, "#firstButton");
    await click(reducePage, "#playButton");
    await reducePage.waitForTimeout(1000);
    const reduced = await reducePage.evaluate(() => ({
      media: matchMedia("(prefers-reduced-motion: reduce)").matches,
      seq: Number(document.querySelector("#evidenceSeq")?.textContent || "-1"),
      animation: getComputedStyle(document.querySelector(".hero-spark") || document.body).animationDuration,
      playing: document.querySelector("#playButton")?.getAttribute("aria-pressed")
    }));
    if (reduced.playing === "true") await click(reducePage, "#playButton");
    record(
      "browser.reduced-motion",
      reduced.media && reduced.seq >= 1,
      "media=" + reduced.media + ", playback advanced to seq " + reduced.seq
    );
    await reduceContext.close();

    const loadContext = await browser.newContext({ viewport: { width: 1280, height: 800 } });
    const loadPage = await loadContext.newPage();
    await loadPage.goto(target, { waitUntil: "domcontentloaded", timeout: 12000 });
    await waitCanonical(loadPage);
    await click(loadPage, "#firstButton");
    const timing = await loadPage.evaluate(async () => {
      const control = { ticks: 0 };
      const controlTimer = setInterval(() => { control.ticks += 1; }, 50);
      const loadTimer = setInterval(() => {
        const until = performance.now() + 14;
        while (performance.now() < until) Math.sqrt(1234567);
      }, 25);
      const start = performance.now();
      document.querySelector("#playButton").click();
      await new Promise((resolve) => setTimeout(resolve, 1900));
      const elapsed = performance.now() - start;
      const seq = Number(document.querySelector("#evidenceSeq")?.textContent || "-1");
      document.querySelector("#playButton").click();
      clearInterval(loadTimer);
      clearInterval(controlTimer);
      return { elapsed, seq, controlTicks: control.ticks };
    });
    record(
      "browser.wall-clock-load",
      timing.elapsed >= 1750 && timing.elapsed < 3200 && timing.seq >= 2 && timing.controlTicks >= 20,
      "elapsed=" + Math.round(timing.elapsed) + "ms, seq=" + timing.seq + ", control ticks=" + timing.controlTicks
    );
    await loadContext.close();

    const mobile390 = await mobileResult(browser, 390);
    const mobile320 = await mobileResult(browser, 320);
    record(
      "browser.mobile-390x844",
      mobile390.scrollWidth <= mobile390.clientWidth + 1 && mobile390.overflow.length === 0,
      "viewport=" + mobile390.clientWidth + ", scrollWidth=" + mobile390.scrollWidth
        + ", overflow=" + mobile390.overflow.join(",")
    );
    record(
      "browser.mobile-320",
      mobile320.clientWidth === 320 && mobile320.scrollWidth <= 321 && mobile320.overflow.length === 0,
      "viewport=" + mobile320.clientWidth + ", scrollWidth=" + mobile320.scrollWidth
        + ", overflow=" + mobile320.overflow.join(",")
    );
    const allTargets = mobile390.targets.concat(mobile320.targets);
    const smallTargets = mobile390.smallTargets.concat(mobile320.smallTargets);
    record(
      "browser.touch-targets",
      allTargets.length === 36 && smallTargets.length === 0,
      "measured=" + allTargets.length + ", below 44px=" + smallTargets.map((item) => item.id).join(",")
    );
    await browser.close();
    process.stdout.write(JSON.stringify({ results }));
  } catch (error) {
    if (browser) await browser.close().catch(() => {});
    process.stdout.write(JSON.stringify({
      fatal: error && (error.stack || error.message) ? (error.stack || error.message) : String(error),
      results
    }));
    process.exitCode = 1;
  }
})();
"""


def _browser_failures(detail: str) -> List[CheckResult]:
    return [CheckResult(name, False, detail) for name in BROWSER_CHECK_NAMES]


def run_browser_checks(root: Path) -> List[CheckResult]:
    repository = Path(root).resolve()
    node = shutil.which("node")
    if node is None:
        return _browser_failures("required browser measurement unavailable: node is missing")
    package = repository / "node_modules/playwright/package.json"
    if not package.is_file():
        return _browser_failures(
            "required browser measurement unavailable: repository Playwright is missing"
        )
    resolution = subprocess.run(
        [node, "-e", "require.resolve('playwright')"],
        cwd=str(repository),
        text=True,
        capture_output=True,
        timeout=10,
        check=False,
    )
    if resolution.returncode != 0:
        return _browser_failures(
            "required browser measurement unavailable: {}".format(
                resolution.stderr.strip() or "Playwright cannot be resolved"
            )
        )
    try:
        state = _json(repository / STATE_RELATIVE)
        projection = _json(repository / ORGANISM_PROJECTION_RELATIVE)
        expected_events = state["event_ledger"]["event_count"]
        expected_frames = projection["total_frame_count"]
    except Exception as error:
        return _browser_failures("required browser inputs are invalid: {}".format(error))

    with _serve(repository) as base_url:
        target = base_url + APP_RELATIVE.as_posix()
        process = subprocess.run(
            [
                node,
                "-e",
                BROWSER_SCRIPT,
                target,
                str(expected_events),
                str(expected_frames),
            ],
            cwd=str(repository),
            text=True,
            capture_output=True,
            timeout=120,
            check=False,
        )
    try:
        payload = json.loads(process.stdout)
    except json.JSONDecodeError as error:
        detail = "Playwright emitted invalid evidence: {} {}".format(
            error, process.stderr.strip()
        )
        return _browser_failures(detail)
    fatal = payload.get("fatal")
    values = payload.get("results", {})
    results = []
    for name in BROWSER_CHECK_NAMES:
        value = values.get(name)
        if type(value) is not dict:
            results.append(
                CheckResult(
                    name,
                    False,
                    "required browser assertion was not measured{}".format(
                        ": " + str(fatal) if fatal else ""
                    ),
                )
            )
            continue
        results.append(
            CheckResult(
                name,
                value.get("pass") is True,
                value.get("detail", "no evidence"),
            )
        )
    if process.returncode != 0 and not fatal:
        for result in results:
            if result.passed:
                result.passed = False
                result.detail = "browser process failed after measurement: {}".format(
                    process.stderr.strip()
                )
    return results


def run_gate(root: Path) -> List[CheckResult]:
    repository = Path(root).expanduser().resolve()
    static = run_static_checks(repository)
    browser = run_browser_checks(repository)
    return static + browser


def _payload(root: Path, results: Sequence[CheckResult]) -> Dict[str, Any]:
    passed = sum(1 for result in results if result.passed)
    failed = len(results) - passed
    return {
        "gate": "agent-amusement-park",
        "root": str(root),
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
        description="Fail-closed acceptance gate for the agent amusement park."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=ROOT,
        help="repository root (default: inferred from this script)",
    )
    parser.add_argument("--json", action="store_true", help="emit JSON evidence")
    arguments = parser.parse_args(argv)
    root = arguments.root.expanduser().resolve()
    results = run_gate(root)
    payload = _payload(root, results)
    if arguments.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        for result in results:
            print("{} {} — {}".format("PASS" if result.passed else "FAIL", result.name, result.detail))
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

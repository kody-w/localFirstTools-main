"""Mutation and end-to-end tests for the agent amusement park gate."""

import json
import shutil
import sys
import uuid
from contextlib import contextmanager
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import agent_park_gate as gate


@contextmanager
def fixture_root(relative_paths):
    root = Path(__file__).resolve().parent / (
        ".agent-park-gate-" + uuid.uuid4().hex
    )
    root.mkdir()
    try:
        for relative in relative_paths:
            source = ROOT / relative
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            if source.is_dir():
                shutil.copytree(source, target)
            else:
                shutil.copy2(source, target)
        yield root
    finally:
        shutil.rmtree(root, ignore_errors=True)


def replace(path, old, new):
    text = path.read_text(encoding="utf-8")
    assert old in text
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def replace_all(path, old, new):
    text = path.read_text(encoding="utf-8")
    assert old in text
    path.write_text(text.replace(old, new), encoding="utf-8")


def result_map(results):
    return {result.name: result for result in results}


def test_static_check_inventory_is_complete():
    results = gate.run_static_checks(ROOT)
    assert len(results) == len(gate.STATIC_CHECKS)
    assert [result.name for result in results] == [
        name for name, _check in gate.STATIC_CHECKS
    ]
    assert len({result.name for result in results}) == len(results)
    assert all(result.passed for result in results)


@pytest.mark.parametrize(
    "mutation,check_name",
    [
        ("csp", "app.csp"),
        ("same-origin", "app.same-origin-paths"),
        ("service-worker", "app.service-worker-contract"),
        ("manifest", "registration.manifest-feed"),
        ("project-links", "registration.project-scoped-links"),
        ("event-payload", "park.event-chain"),
        ("season-prefix", "park.season-prefix-contracts"),
        ("legacy-contract", "park.season-prefix-contracts"),
        ("economy", "park.synthetic-economy"),
        ("controls", "park.customer-controls"),
        ("v2-spec", "park.v2-contract-spec"),
        ("organism-link", "organism.dual-link-chain"),
        ("experience-release", "organism.experience-release"),
        ("profile", "syndication.profile10-chain"),
        ("descriptor", "syndication.data-descriptors"),
    ],
)
def test_key_static_mutations_turn_red(mutation, check_name):
    paths = {
        "csp": [gate.APP_RELATIVE],
        "same-origin": [gate.APP_RELATIVE],
        "service-worker": [gate.APP_RELATIVE, gate.SERVICE_WORKER_RELATIVE],
        "manifest": ["apps/manifest.json", "apps/feed.json", "apps/feed.xml"],
        "project-links": [
            gate.APP_RELATIVE,
            ".well-known/mcp.json",
            ".well-known/agent-protocol",
        ],
        "event-payload": [
            gate.STATE_RELATIVE,
            gate.EVENTS_RELATIVE,
            gate.CONTRACT_V2_RELATIVE,
        ],
        "season-prefix": [
            gate.STATE_RELATIVE,
            gate.EVENTS_RELATIVE,
            gate.CONTRACT_V1_RELATIVE,
            gate.CONTRACT_V2_RELATIVE,
        ],
        "legacy-contract": [
            gate.STATE_RELATIVE,
            gate.EVENTS_RELATIVE,
            gate.CONTRACT_V1_RELATIVE,
            gate.CONTRACT_V2_RELATIVE,
        ],
        "economy": [
            gate.STATE_RELATIVE,
            gate.EVENTS_RELATIVE,
            gate.CONTRACT_V2_RELATIVE,
        ],
        "controls": [
            gate.STATE_RELATIVE,
            gate.EVENTS_RELATIVE,
            gate.CONTRACT_V2_RELATIVE,
        ],
        "v2-spec": [
            gate.CONTRACT_V2_RELATIVE,
            ".well-known/mcp.json",
        ],
        "organism-link": [
            gate.ORGANISM_LEDGER_RELATIVE,
            gate.ORGANISM_PROJECTION_RELATIVE,
        ],
        "experience-release": [
            gate.ORGANISM_LEDGER_RELATIVE,
            gate.ORGANISM_PROJECTION_RELATIVE,
            gate.STATE_RELATIVE,
        ],
        "profile": ["apps/syndication"],
        "descriptor": [
            "apps/syndication",
            gate.STATE_RELATIVE,
            gate.EVENTS_RELATIVE,
            gate.CONTRACT_V1_RELATIVE,
            gate.CONTRACT_V2_RELATIVE,
            "apps/attention/frame-control.json",
            "apps/attention/policy.json",
            "apps/attention/prompt-contract.json",
            "apps/looking-glass/hash-scene.json",
            "apps/agent-fair",
        ],
    }[mutation]
    with fixture_root(paths) as root:
        if mutation == "csp":
            assert gate._run_check(
                check_name, lambda: gate._check_csp(root)
            ).passed
            replace(root / gate.APP_RELATIVE, "connect-src 'self'", "connect-src *")
            result = gate._run_check(check_name, lambda: gate._check_csp(root))
        elif mutation == "same-origin":
            assert gate._run_check(
                check_name, lambda: gate._check_same_origin_paths(root)
            ).passed
            replace(
                root / gate.APP_RELATIVE,
                "../agent-park/park-state.json",
                "https://example.test/park-state.json",
            )
            result = gate._run_check(
                check_name, lambda: gate._check_same_origin_paths(root)
            )
        elif mutation == "service-worker":
            assert gate._run_check(
                check_name, lambda: gate._check_service_worker_contract(root)
            ).passed
            replace(
                root / gate.SERVICE_WORKER_RELATIVE,
                "cached.length === 5",
                "cached.length >= 1",
            )
            result = gate._run_check(
                check_name, lambda: gate._check_service_worker_contract(root)
            )
        elif mutation == "manifest":
            assert gate._run_check(
                check_name, lambda: gate._check_manifest_feed_registration(root)
            ).passed
            replace(
                root / "apps/manifest.json",
                "agent-amusement-park.html",
                "missing-agent-park.html",
            )
            result = gate._run_check(
                check_name, lambda: gate._check_manifest_feed_registration(root)
            )
        elif mutation == "project-links":
            assert gate._run_check(
                check_name, lambda: gate._check_project_scoped_links(root)
            ).passed
            path = root / ".well-known/agent-protocol"
            protocol = json.loads(path.read_text(encoding="utf-8"))
            protocol["discovery"]["agent_park_state"] = (
                "https://kody-w.github.io/apps/agent-park/park-state.json"
            )
            path.write_text(json.dumps(protocol), encoding="utf-8")
            result = gate._run_check(
                check_name, lambda: gate._check_project_scoped_links(root)
            )
        elif mutation == "event-payload":
            assert gate._run_check(
                check_name, lambda: gate._check_event_chain(root)
            ).passed
            path = root / gate.EVENTS_RELATIVE
            lines = path.read_text(encoding="utf-8").splitlines()
            event = json.loads(lines[3])
            event["payload"]["night"] = 99
            lines[3] = json.dumps(event, separators=(",", ":"), sort_keys=True)
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            result = gate._run_check(
                check_name, lambda: gate._check_event_chain(root)
            )
        elif mutation == "season-prefix":
            assert gate._run_check(
                check_name, lambda: gate._check_season_prefix_and_contracts(root)
            ).passed
            path = root / gate.STATE_RELATIVE
            state = json.loads(path.read_text(encoding="utf-8"))
            state["seasons"][0]["ledger_prefix_sha256"] = "0" * 64
            path.write_text(json.dumps(state), encoding="utf-8")
            result = gate._run_check(
                check_name, lambda: gate._check_season_prefix_and_contracts(root)
            )
        elif mutation == "legacy-contract":
            assert gate._run_check(
                check_name, lambda: gate._check_season_prefix_and_contracts(root)
            ).passed
            replace(
                root / gate.CONTRACT_V1_RELATIVE,
                '"write_default": "local-branch-only"',
                '"write_default": "mutated"',
            )
            result = gate._run_check(
                check_name, lambda: gate._check_season_prefix_and_contracts(root)
            )
        elif mutation == "economy":
            assert gate._run_check(
                check_name, lambda: gate._check_synthetic_economy(root)
            ).passed
            path = root / gate.STATE_RELATIVE
            state = json.loads(path.read_text(encoding="utf-8"))
            state["economy"]["real_money"] = True
            path.write_text(json.dumps(state), encoding="utf-8")
            result = gate._run_check(
                check_name, lambda: gate._check_synthetic_economy(root)
            )
        elif mutation == "controls":
            assert gate._run_check(
                check_name, lambda: gate._check_customer_controls(root)
            ).passed
            path = root / gate.CONTRACT_V2_RELATIVE
            contract = json.loads(path.read_text(encoding="utf-8"))
            contract["agent_actions"]["visit"]["canonical_write"] = True
            path.write_text(json.dumps(contract), encoding="utf-8")
            result = gate._run_check(
                check_name, lambda: gate._check_customer_controls(root)
            )
        elif mutation == "v2-spec":
            assert gate._run_check(
                check_name, lambda: gate._check_v2_contract_spec(root)
            ).passed
            path = root / gate.CONTRACT_V2_RELATIVE
            contract = json.loads(path.read_text(encoding="utf-8"))
            contract["action_limit"]["max_local_actions_per_mcp_session"] = 99
            path.write_text(json.dumps(contract), encoding="utf-8")
            result = gate._run_check(
                check_name, lambda: gate._check_v2_contract_spec(root)
            )
        elif mutation == "organism-link":
            assert gate._run_check(
                check_name, lambda: gate._check_organism_chain(root)
            ).passed
            path = root / gate.ORGANISM_LEDGER_RELATIVE
            lines = path.read_text(encoding="utf-8").splitlines()
            frame = json.loads(lines[-1])
            frame["prev_wave"] = "0" * 64
            lines[-1] = json.dumps(frame, separators=(",", ":"), sort_keys=True)
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            result = gate._run_check(
                check_name, lambda: gate._check_organism_chain(root)
            )
        elif mutation == "experience-release":
            assert gate._run_check(
                check_name, lambda: gate._check_experience_frames(root)
            ).passed
            path = root / gate.ORGANISM_LEDGER_RELATIVE
            replace(path, gate.EXPERIENCE_RELEASE_PREFIX, "experience-release:mutant:")
            result = gate._run_check(
                check_name, lambda: gate._check_experience_frames(root)
            )
        elif mutation == "profile":
            assert gate._run_check(
                check_name, lambda: gate._check_profile10_chain(root)
            ).passed
            path = root / gate.SYNDICATION_INDEX_RELATIVE
            index = json.loads(path.read_text(encoding="utf-8"))
            index["profile"] = "rappterzoo-syndication-profile/9"
            path.write_text(json.dumps(index), encoding="utf-8")
            result = gate._run_check(
                check_name, lambda: gate._check_profile10_chain(root)
            )
        else:
            assert gate._run_check(
                check_name, lambda: gate._check_data_descriptors(root)
            ).passed
            path = root / gate.SYNDICATION_SNAPSHOT_RELATIVE
            snapshot = json.loads(path.read_text(encoding="utf-8"))
            descriptor = next(
                item
                for item in snapshot["data_objects"]
                if item["path"] == gate.EVENTS_RELATIVE.as_posix()
            )
            descriptor["verification"]["required"] = False
            path.write_text(json.dumps(snapshot), encoding="utf-8")
            result = gate._run_check(
                check_name, lambda: gate._check_data_descriptors(root)
            )
        assert result.passed is False


@pytest.mark.parametrize("verifier", ["builder", "sync"])
def test_equal_utc_rehashed_event_mutations_turn_red(monkeypatch, verifier):
    check_name = "park.strict-utc-parity"
    assert gate._run_check(
        check_name, lambda: gate._check_strict_utc_parity(ROOT)
    ).passed
    if verifier == "builder":
        monkeypatch.setattr(
            gate.park_builder,
            "verify_events",
            lambda events: {"event_count": len(events)},
        )
    else:
        monkeypatch.setattr(
            gate.rappterzoo_sync,
            "validate_agent_park_event_ledger",
            lambda events: events,
        )
    result = gate._run_check(
        check_name, lambda: gate._check_strict_utc_parity(ROOT)
    )
    assert result.passed is False


@pytest.mark.parametrize(
    "mutation",
    [
        "event-ledger-digest",
        "state-digest",
        "contract-digest",
        "bundle-digest",
    ],
)
def test_mcp_park_context_digest_mutations_turn_red(monkeypatch, mutation):
    check_name = "mcp.park-context-integrity"
    assert gate._run_check(
        check_name, lambda: gate._check_mcp_context_integrity(ROOT)
    ).passed
    original = gate.rappterzoo_mcp.RappterZooMCP._park_context

    def vulnerable_context(self):
        if (
            isinstance(self.source, gate._ParkContextMutationSource)
            and self.source.mutation == mutation
        ):
            clean = gate.rappterzoo_mcp.RappterZooMCP(
                gate._ParkContextMutationSource(ROOT)
            )
            return original(clean)
        return original(self)

    monkeypatch.setattr(
        gate.rappterzoo_mcp.RappterZooMCP,
        "_park_context",
        vulnerable_context,
    )
    result = gate._run_check(
        check_name, lambda: gate._check_mcp_context_integrity(ROOT)
    )
    assert result.passed is False


def test_playwright_unavailable_is_failure_not_skip(monkeypatch):
    original = shutil.which
    monkeypatch.setattr(
        gate.shutil,
        "which",
        lambda name: None if name == "node" else original(name),
    )
    results = gate.run_browser_checks(ROOT)
    assert len(results) == len(gate.BROWSER_CHECK_NAMES)
    assert all(not result.passed for result in results)
    assert all("unavailable" in result.detail for result in results)


def test_browser_blocker_mutations_turn_red():
    paths = [
        gate.APP_RELATIVE,
        gate.SERVICE_WORKER_RELATIVE,
        gate.STATE_RELATIVE,
        gate.EVENTS_RELATIVE,
        gate.CONTRACT_V2_RELATIVE,
        gate.ORGANISM_PROJECTION_RELATIVE,
        "node_modules",
    ]
    with fixture_root(paths) as root:
        baseline = result_map(gate.run_browser_checks(root))
        for name in (
            "browser.branch-import-adversarial",
            "browser.full-import-adversarial",
            "browser.clear-intervening-mutation",
            "browser.cached-provenance",
        ):
            assert baseline[name].passed is True

        app = root / gate.APP_RELATIVE
        replace(
            app,
            "if (value?.export_schema === BRANCH_EXPORT_SCHEMA) {",
            'if (String(value?.export_schema || "").includes("local-branch")) {',
        )
        replace(
            app,
            "const schemaValid = value.export_schema === BRANCH_EXPORT_SCHEMA;",
            'const schemaValid = String(value.export_schema || "").includes("local-branch");',
        )
        replace(
            app,
            '          "authority",\n          "branch_digest"',
            '          "authority"',
        )
        replace(
            app,
            'const allowedKeys = new Set([...baseKeys, "exported_at"]);',
            'const allowedKeys = new Set([...baseKeys, "exported_at", "branch_digest"]);',
        )
        replace(
            app,
            "const eventHeadMatches = isSha256(value.canonical_event_head)\n"
            "          && value.canonical_event_head === canonicalEventHead();",
            "const eventHeadMatches = isSha256(value.canonical_event_head);",
        )
        replace(
            app,
            "const organismHeadMatches = isSha256(value.canonical_organism_head)\n"
            "          && value.canonical_organism_head === canonicalOrganismHead();",
            "const organismHeadMatches = isSha256(value.canonical_organism_head);",
        )
        replace(
            app,
            "const digestPresent = isSha256(value.branch_digest);",
            "const digestPresent = value.branch_digest == null || isSha256(value.branch_digest);",
        )
        replace(
            app,
            "const digestMatches = digestPresent && value.branch_digest === computedBranchDigest;",
            "const digestMatches = value.branch_digest == null || value.branch_digest === computedBranchDigest;",
        )
        replace(
            app,
            "if (!isSha256(value.content_digest)) {\n"
            '          return { valid: false, summary: "Full ledger verification: REJECTED\\nMandatory release-2 content_digest is missing or malformed." };\n'
            "        }",
            "if (value.content_digest != null && !isSha256(value.content_digest)) {\n"
            '          return { valid: false, summary: "Full ledger verification: REJECTED\\nMandatory release-2 content_digest is missing or malformed." };\n'
            "        }",
        )
        replace(
            app,
            "const exportDigestMatches = exportDigest.matches === true;",
            "const exportDigestMatches = value.content_digest == null || exportDigest.matches === true;",
        )
        replace(app, "          && organismChain.valid\n", "")
        replace(
            app,
            'invalidatePendingClear("Pending clear invalidated by a new local action.");',
            "void 0;",
        )
        replace(
            app,
            "if (!state.clearCheckpoint || current.branch_digest !== state.clearPendingDigest\n"
            "            || state.clearCheckpointDigest !== state.clearPendingDigest) {",
            "if (!state.clearCheckpoint) {",
        )
        replace_all(
            root / gate.SERVICE_WORKER_RELATIVE,
            'withProvenance(cached, "cache")',
            'withProvenance(cached, "network")',
        )

        mutated = result_map(gate.run_browser_checks(root))
        assert mutated["browser.branch-import-adversarial"].passed is False
        assert mutated["browser.full-import-adversarial"].passed is False
        assert mutated["browser.clear-intervening-mutation"].passed is False
        assert mutated["browser.cached-provenance"].passed is False


def test_emergency_stop_runtime_mutation_turns_red():
    paths = [
        gate.APP_RELATIVE,
        gate.SERVICE_WORKER_RELATIVE,
        gate.STATE_RELATIVE,
        gate.EVENTS_RELATIVE,
        gate.CONTRACT_V2_RELATIVE,
        gate.ORGANISM_PROJECTION_RELATIVE,
        "node_modules",
    ]
    with fixture_root(paths) as root:
        baseline = result_map(gate.run_browser_checks(root))
        assert baseline["browser.durable-emergency-rearm"].passed is True
        replace(
            root / gate.APP_RELATIVE,
            'elements.emergencyButton.addEventListener("click", toggleEmergencyStop);',
            'elements.emergencyButton.addEventListener("click", () => {});',
        )
        results = result_map(gate.run_browser_checks(root))
        assert results["browser.durable-emergency-rearm"].passed is False


def test_cli_json_reports_exact_counts(monkeypatch, capsys):
    static = [
        gate.CheckResult("static-{}".format(index), True, "ok")
        for index in range(len(gate.STATIC_CHECKS))
    ]
    browser = [
        gate.CheckResult(name, True, "ok")
        for name in gate.BROWSER_CHECK_NAMES
    ]
    monkeypatch.setattr(gate, "run_gate", lambda _root: static + browser)
    assert gate.main(["--root", str(ROOT), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["passed"] is True
    static_count = len(gate.STATIC_CHECKS)
    browser_count = len(gate.BROWSER_CHECK_NAMES)
    assert payload["counts"] == {
        "total": static_count + browser_count,
        "passed": static_count + browser_count,
        "failed": 0,
        "static": static_count,
        "browser": browser_count,
    }

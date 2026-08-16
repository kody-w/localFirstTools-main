"""Tests for the portable RappterZoo MCP server."""

import io
import json
import re
import subprocess
import sys
import urllib.error
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import rappterzoo_mcp as mcp
import process_agent_issues


def make_repo(tmp_path):
    (tmp_path / "apps").mkdir()
    (tmp_path / "apps" / "agent-park").mkdir()
    (tmp_path / "apps" / "3d-immersive").mkdir()
    (tmp_path / "docs").mkdir()
    (tmp_path / "scripts").mkdir()
    (tmp_path / ".well-known").mkdir()
    (tmp_path / "apps" / "manifest.json").write_text(json.dumps({
        "categories": {
            "data_tools": {
                "folder": "data-tools",
                "apps": [
                    {
                        "title": "Digg",
                        "file": "digg.html",
                        "description": "Append-only organism reader",
                        "tags": ["organism", "ledger"],
                        "generation": 1,
                    }
                ],
            },
            "3d_immersive": {
                "folder": "3d-immersive",
                "apps": [
                    {
                        "title": "Organism Observatory",
                        "file": "organism-observatory.html",
                        "description": "RAPP frame cosmos",
                        "tags": ["rapp1", "dogg"],
                        "generation": 1,
                    }
                ],
            },
        }
    }))
    (tmp_path / "apps" / "rankings.json").write_text(json.dumps({
        "rankings": [
            {"file": "digg.html", "score": 91},
            {"file": "organism-observatory.html", "score": 98},
        ]
    }))
    (tmp_path / "apps" / "agents.json").write_text('{"agents":[]}')
    frames = [
        {
            "spec": "rapp/1",
            "kind": "zoo.birth",
            "stream_id": "net:rappterzoo",
            "seq": 0,
            "utc": "2026-08-15T17:06:24.449Z",
            "payload": {
                "event_id": "birth:dogg",
                "organism": "dogg.watchtower",
                "visibility": "public-metadata",
            },
            "payload_hash": "a" * 64,
            "frame_hash": "b" * 64,
            "prev": None,
            "prev_wave": None,
            "sig": None,
        },
        {
            "spec": "rapp/1",
            "kind": "zoo.observation",
            "stream_id": "net:rappterzoo",
            "seq": 1,
            "utc": "2026-08-15T17:07:24.449Z",
            "payload": {
                "event_id": "frame:1",
                "organism": "rappterzoo",
                "visibility": "public-metadata",
            },
            "payload_hash": "c" * 64,
            "frame_hash": "d" * 64,
            "prev": "a" * 64,
            "prev_wave": "b" * 64,
            "sig": None,
        },
    ]
    projection = {
        "schema": "rappterzoo-organism-feed/1",
        "stream_id": "net:rappterzoo",
        "frames": frames,
        "organisms": [
            {"id": "dogg.watchtower"},
            {"id": "rappterzoo"},
        ],
        "total_frame_count": 2,
        "integrity": {"valid": True, "frame_count": 2},
        "privacy": {"private_godd_media": "excluded"},
        "rapp1": {"acceptance": "structural-unverified"},
    }
    (tmp_path / "apps" / "organism-frames.json").write_text(
        json.dumps(projection)
    )
    (tmp_path / "apps" / "organism-frames.jsonl").write_text(
        "\n".join(json.dumps(frame) for frame in frames) + "\n"
    )
    for filename in (
        "events.jsonl",
        "agent-contract-v2.json",
        "agent-contract.json",
        "park-state.json",
    ):
        (
            tmp_path / "apps" / "agent-park" / filename
        ).write_bytes(
            (ROOT / "apps" / "agent-park" / filename).read_bytes()
        )
    (
        tmp_path
        / "apps"
        / "3d-immersive"
        / "agent-amusement-park.html"
    ).write_text("<!doctype html><title>Agent Amusement Park</title>")
    (tmp_path / "docs" / "AGENT-AMUSEMENT-PARK.md").write_text(
        "# Agent Amusement Park\n"
    )
    (tmp_path / "scripts" / "agent_amusement_park.py").write_text(
        '"""Verify the agent amusement park bundle."""\n'
    )
    (tmp_path / "scripts" / "agent_park_gate.py").write_text(
        '"""Fail-closed acceptance gate."""\n'
    )
    (tmp_path / "skills.md").write_text("# RappterZoo skills\n")
    (tmp_path / ".well-known" / "mcp.json").write_text('{"tools":[]}')
    return tmp_path


def make_server(tmp_path, writes=False, runner=subprocess.run):
    root = tmp_path
    if not (root / "apps" / "manifest.json").is_file():
        root = make_repo(tmp_path)
    source = mcp.DataSource(
        root,
        "https://example.invalid/rappterzoo/",
    )
    return mcp.JSONRPCServer(
        mcp.RappterZooMCP(
            source,
            repository="example/rappterzoo",
            writes_enabled=writes,
            runner=runner,
        )
    )


def call(server, method, params=None, request_id=1):
    return server.handle({
        "jsonrpc": "2.0",
        "id": request_id,
        "method": method,
        "params": params or {},
    })


def tool_result(server, name, arguments):
    response = call(
        server,
        "tools/call",
        {"name": name, "arguments": arguments},
    )
    result = response["result"]
    return result, json.loads(result["content"][0]["text"])


def write_canonical_jsonl(path, records):
    path.write_bytes(
        b"".join(
            mcp._park_canonical_bytes(record) + b"\n"
            for record in records
        )
    )


def test_initialize_lists_real_tools_and_resources(tmp_path):
    server = make_server(tmp_path)
    initialized = call(
        server,
        "initialize",
        {"protocolVersion": "2024-11-05"},
    )
    assert initialized["result"]["serverInfo"]["name"] == "rappterzoo"
    assert initialized["result"]["capabilities"]["tools"]
    tools = call(server, "tools/list")["result"]["tools"]
    assert {tool["name"] for tool in tools} >= {
        "get_home",
        "search_apps",
        "get_organism_frames",
        "agent_park_time_travel",
        "agent_park_local_action",
        "agent_park_export_branch",
        "register_agent",
        "submit_app",
    }
    resources = call(server, "resources/list")["result"]["resources"]
    assert any(
        item["uri"] == "rappterzoo://organism-frames"
        for item in resources
    )
    assert {
        "rappterzoo://agent-park-contract",
        "rappterzoo://agent-park-events",
        "rappterzoo://agent-park-state",
        "rappterzoo://agent-amusement-park",
        "rappterzoo://agent-park-guide",
        "rappterzoo://agent-park-contract-v1",
        "rappterzoo://agent-park-contract-v2",
        "rappterzoo://agent-park-bundle-verifier",
        "rappterzoo://agent-park-acceptance-gate",
    }.issubset({item["uri"] for item in resources})


def test_home_is_bounded_and_data_derived(tmp_path):
    server = make_server(tmp_path)
    result, value = tool_result(server, "get_home", {})
    assert not result["isError"]
    assert value["catalog"]["total_apps"] == 2
    assert value["agents"]["count"] == 0
    assert value["organism"]["total_frame_count"] == 2
    assert len(value["quality"]["lowest_scored"]) == 2
    assert len(value["organism"]["latest_frames"]) <= 5
    assert value["writes_enabled"] is False
    assert value["agent_amusement_park"]["economy"] == (
        "synthetic-credit-only"
    )
    assert value["agent_amusement_park"]["canonical_write_default"] == (
        "local-branch-only"
    )
    assert value["agent_amusement_park"]["canonical_mutation"] is False
    assert value["agent_amusement_park"]["real_money"] is False
    assert value["agent_amusement_park"]["time_travel_tool"] == (
        "agent_park_time_travel"
    )
    season_2 = value["agent_amusement_park"]["season_2"]
    assert season_2["contract_version"] == 2
    assert season_2["contract_schema"] == (
        "rappterzoo-agent-park-contract/2"
    )
    contract = json.loads(
        (
            tmp_path / "apps" / "agent-park" / "agent-contract-v2.json"
        ).read_text()
    )
    assert season_2["bundle"]["bundle_digest"] == (
        contract["integrity"]["bundle_digest"]
    )
    assert season_2["local_branch"]["action_limit"] == 100
    assert season_2["local_branch"]["schema"] == (
        "rappterzoo-agent-park-local-branch/2"
    )
    assert season_2["local_branch"]["mcp_undo_action"] is False
    assert (
        season_2["hashing"]["mcp_local_branch"]["domain_prefix"] is False
    )
    assert season_2["hashing"]["canonical_bundle"]["hash_domains"][
        "event_v2"
    ] == (
        "rappterzoo/agent-park-event/2\n"
    )
    assert season_2["custody"]["keys_leave_customer_runtime"] is False
    assert season_2["warm_offline"]["cold_offline_guaranteed"] is False
    assert season_2["warm_offline"]["cache_bundle_verification"] is False
    assert season_2["warm_offline"]["cached_resource_count"] == 5
    assert season_2["browser_runtime"]["mcp_contract_compatible"] is False
    assert season_2["browser_runtime"]["current_export_schema"].endswith(
        "/2"
    )
    assert season_2["verifier"]["version"] == (
        "agent-amusement-park-verifier/2"
    )
    assert season_2["verifier"]["fail_closed"] is True


def test_resource_reads_are_allowlisted(tmp_path):
    server = make_server(tmp_path)
    value = call(
        server,
        "resources/read",
        {"uri": "rappterzoo://skills"},
    )
    assert "RappterZoo skills" in value["result"]["contents"][0]["text"]
    refused = call(
        server,
        "resources/read",
        {"uri": "file:///etc/passwd"},
    )
    assert refused["error"]["code"] == -32602


@pytest.mark.parametrize(
    "uri,expected",
    [
        ("rappterzoo://agent-park-contract", '"latest": 2'),
        ("rappterzoo://agent-park-contract-v2", '"latest": 2'),
        ("rappterzoo://agent-park-contract-v1", "contract/1"),
        ("rappterzoo://agent-park-state", "chrono-coaster"),
        ("rappterzoo://agent-park-events", "park.genesis"),
        ("rappterzoo://agent-amusement-park", "Agent Amusement Park"),
        ("rappterzoo://agent-park-guide", "# Agent Amusement Park"),
        (
            "rappterzoo://agent-park-bundle-verifier",
            "agent amusement park",
        ),
        (
            "rappterzoo://agent-park-acceptance-gate",
            "acceptance gate",
        ),
    ],
)
def test_every_agent_park_resource_is_readable(tmp_path, uri, expected):
    server = make_server(tmp_path)
    response = call(server, "resources/read", {"uri": uri})
    assert expected in response["result"]["contents"][0]["text"]


def test_missing_and_oversize_resources_are_protocol_errors(
    tmp_path,
    monkeypatch,
):
    root = make_repo(tmp_path)
    (root / "docs" / "AGENT-AMUSEMENT-PARK.md").unlink()

    def missing(_request, timeout=0):
        raise urllib.error.URLError("not found")

    monkeypatch.setattr(mcp.urllib.request, "urlopen", missing)
    server = make_server(root)
    response = call(
        server,
        "resources/read",
        {"uri": "rappterzoo://agent-park-guide"},
    )
    assert response["error"]["code"] == -32002
    assert response["error"]["message"] == "resource unavailable"

    monkeypatch.setattr(mcp, "MAX_RESOURCE_BYTES", 8)
    (root / "docs" / "AGENT-AMUSEMENT-PARK.md").write_text("x" * 9)
    response = call(
        server,
        "resources/read",
        {"uri": "rappterzoo://agent-park-guide"},
    )
    assert response["error"]["code"] == -32002
    assert "exceeds" in response["error"]["data"]["reason"]

    monkeypatch.setattr(mcp, "MAX_RESOURCE_BYTES", 5 * 1024 * 1024)
    (
        root / "apps" / "agent-park" / "agent-contract-v2.json"
    ).unlink()
    response = call(
        server,
        "resources/read",
        {"uri": "rappterzoo://agent-park-contract"},
    )
    assert response["error"]["code"] == -32002
    assert response["error"]["data"]["uri"] == (
        "rappterzoo://agent-park-contract"
    )


def test_search_uses_manifest_and_rankings(tmp_path):
    server = make_server(tmp_path)
    result, value = tool_result(
        server,
        "search_apps",
        {"query": "organism", "min_score": 90, "limit": 5},
    )
    assert not result["isError"]
    assert value["matches"][0]["file"] == "organism-observatory.html"
    assert value["matches"][0]["score"] == 98


def test_organism_frames_are_bounded_and_filterable(tmp_path):
    server = make_server(tmp_path)
    result, value = tool_result(
        server,
        "get_organism_frames",
        {"organism": "dogg.watchtower", "limit": 1},
    )
    assert not result["isError"]
    assert value["count"] == 1
    assert value["frames"][0]["kind"] == "zoo.birth"
    assert value["rapp1"]["acceptance"] == "structural-unverified"


def test_agent_can_time_travel_visit_propose_and_export(tmp_path):
    root = make_repo(tmp_path)
    server = make_server(root)
    event_bytes = (root / "apps" / "agent-park" / "events.jsonl").read_bytes()
    state_bytes = (root / "apps" / "agent-park" / "park-state.json").read_bytes()

    result, traveled = tool_result(
        server,
        "agent_park_time_travel",
        {"source": "park", "sequence": 0},
    )
    assert not result["isError"]
    assert traveled["record"]["kind"] == "park.genesis"
    assert traveled["replay_only"] is True
    assert traveled["rewrites_history"] is False

    result, visit = tool_result(
        server,
        "agent_park_local_action",
        {
            "action": "visit",
            "source": "park",
            "sequence": 0,
            "agent_id": "agent.local-explorer",
            "attraction_id": "chrono-coaster",
        },
    )
    assert not result["isError"]
    assert visit["status"] == "local-only"
    assert visit["action"]["kind"] == "local.visit"
    assert visit["action"]["canonical_write"] is False
    assert visit["action"]["source_hash"] == traveled["record"]["event_hash"]
    assert visit["action"]["payload"]["admission"]["real_money"] is False

    result, proposal = tool_result(
        server,
        "agent_park_local_action",
        {
            "action": "invent_attraction",
            "source": "organism",
            "sequence": 1,
            "title": "Append Only Teacups",
            "experience_contract": "Replay one immutable history safely.",
            "resource_request": {
                "compute_units": 4,
                "energy_units": 3,
                "attention_slots": 2,
            },
            "royalty_recipient": "agent.local-explorer",
        },
    )
    assert not result["isError"]
    assert proposal["action"]["kind"] == "local.attraction-proposal"
    assert proposal["action"]["prev"] == visit["action"]["action_hash"]
    assert proposal["action"]["source_hash"] == "d" * 64
    assert proposal["authority"]["canonical_release"] == (
        "customer-approved-only"
    )

    result, exported = tool_result(
        server,
        "agent_park_export_branch",
        {},
    )
    assert not result["isError"]
    assert exported["export_schema"] == (
        "rappterzoo-agent-park-local-branch/2"
    )
    assert exported["canonical_write"] is False
    assert exported["authority"]["real_money"] is False
    assert len(exported["actions"]) == 2
    contract = json.loads(
        (
            root / "apps" / "agent-park" / "agent-contract-v2.json"
        ).read_text()
    )
    assert set(exported) == set(
        contract["branch_export"]["required_fields"]
    )
    assert all(
        action["schema"] == mcp.PARK_ACTION_SCHEMA
        for action in exported["actions"]
    )
    assert re.fullmatch(r"[0-9a-f]{64}", exported["branch_digest"])
    branch_preimage = dict(exported)
    branch_digest = branch_preimage.pop("branch_digest")
    assert branch_digest == mcp._canonical_digest(branch_preimage)
    for action in exported["actions"]:
        assert re.fullmatch(r"[0-9a-f]{64}", action["source_hash"])
        assert action["payload_hash"] == mcp._canonical_digest(
            action["payload"]
        )
        action_preimage = dict(action)
        action_hash = action_preimage.pop("action_hash")
        assert action_hash == mcp._canonical_digest(action_preimage)
    assert (root / "apps" / "agent-park" / "events.jsonl").read_bytes() == (
        event_bytes
    )
    assert (root / "apps" / "agent-park" / "park-state.json").read_bytes() == (
        state_bytes
    )


def test_agent_park_bid_and_bounds_fail_closed(tmp_path, monkeypatch):
    server = make_server(tmp_path)
    result, bid = tool_result(
        server,
        "agent_park_local_action",
        {
            "action": "bid_for_resources",
            "attraction_id": "chrono-coaster",
            "requested_resources": {
                "compute_units": 40,
                "energy_units": 25,
                "attention_slots": 20,
            },
            "synthetic_bid": 99,
        },
    )
    assert not result["isError"]
    assert bid["action"]["payload"]["currency"] == "synthetic-credit"
    assert bid["action"]["payload"]["real_money"] is False

    result, unsupported = tool_result(
        server,
        "agent_park_local_action",
        {
            "action": "undo",
            "target_action_hash": bid["action"]["action_hash"],
            "reason": "Customer reversed the local experiment.",
        },
    )
    assert result["isError"]
    assert unsupported["error"] == "action is not supported"

    result, value = tool_result(
        server,
        "agent_park_time_travel",
        {"source": "park", "sequence": 999},
    )
    assert result["isError"]
    assert "bounds are 0-93" in value["error"]

    monkeypatch.setattr(mcp, "MAX_LOCAL_BRANCH_ACTIONS", 1)
    result, value = tool_result(
        server,
        "agent_park_local_action",
        {
            "action": "visit",
            "agent_id": "agent.local-explorer",
            "attraction_id": "chrono-coaster",
        },
    )
    assert result["isError"]
    assert "action limit" in value["error"]
    monkeypatch.setattr(mcp, "MAX_LOCAL_BRANCH_ACTIONS", 100)

    invalid_root = tmp_path / "invalid"
    invalid_root.mkdir()
    invalid_server = make_server(invalid_root)
    result, value = tool_result(
        invalid_server,
        "agent_park_local_action",
        {
            "action": "bid_for_resources",
            "attraction_id": "chrono-coaster",
            "requested_resources": {
                "compute_units": 1,
                "energy_units": 1,
                "attention_slots": 1,
                "cash_usd": 10,
            },
            "synthetic_bid": 1,
        },
    )
    assert result["isError"]
    assert "exactly" in value["error"]

    irrelevant_root = tmp_path / "irrelevant"
    irrelevant_root.mkdir()
    result, value = tool_result(
        make_server(irrelevant_root),
        "agent_park_local_action",
        {
            "action": "visit",
            "agent_id": "agent.local-explorer",
            "attraction_id": "chrono-coaster",
            "synthetic_bid": 100,
        },
    )
    assert result["isError"]
    assert "not valid for visit" in value["error"]


def test_agent_park_export_recomputes_source_and_action_hashes(tmp_path):
    server = make_server(tmp_path)
    result, _value = tool_result(
        server,
        "agent_park_local_action",
        {
            "action": "visit",
            "source": "park",
            "sequence": 0,
            "agent_id": "agent.local-explorer",
            "attraction_id": "chrono-coaster",
        },
    )
    assert not result["isError"]
    server.mcp.local_park_branch[0]["source_hash"] = "0" * 64

    result, value = tool_result(server, "agent_park_export_branch", {})
    assert result["isError"]
    assert value["error"] == "local park branch source hash mismatch"


def test_agent_park_authority_boundary_fails_closed(tmp_path):
    root = make_repo(tmp_path)
    state_path = root / "apps" / "agent-park" / "park-state.json"
    state = json.loads(state_path.read_text())
    state["economy"]["real_money"] = True
    state_path.write_text(json.dumps(state))
    result, value = tool_result(
        make_server(root),
        "agent_park_export_branch",
        {},
    )
    assert result["isError"]
    assert "authority boundary" in value["error"]


def test_agent_park_tampered_state_title_with_stale_digest_fails_closed(
    tmp_path,
):
    root = make_repo(tmp_path)
    state_path = root / "apps" / "agent-park" / "park-state.json"
    state = json.loads(state_path.read_text())
    state["title"] = "Tampered Park Title"
    state_path.write_text(json.dumps(state))
    server = make_server(root)

    result, value = tool_result(server, "get_home", {})
    assert result["isError"]
    assert value["error"] == "park state digest mismatch"

    response = call(
        server,
        "resources/read",
        {"uri": "rappterzoo://agent-park-state"},
    )
    assert response["error"]["code"] == -32002
    assert response["error"]["message"] == (
        "park integrity verification failed"
    )
    assert response["error"]["data"]["reason"] == (
        "park state digest mismatch"
    )


@pytest.mark.parametrize(
    "mutation,error",
    [
        (
            lambda events: events[-1]["payload"].__setitem__(
                "tampered",
                True,
            ),
            "park event payload hash mismatch",
        ),
        (
            lambda events: events[-1].__setitem__("event_hash", "0" * 64),
            "park event hash mismatch",
        ),
        (
            lambda events: events[-1].__setitem__("seq", 999),
            "park event identity or chain mismatch",
        ),
        (
            lambda events: events[-1].__setitem__("prev", "0" * 64),
            "park event identity or chain mismatch",
        ),
        (
            lambda events: events[-1].__setitem__(
                "utc",
                events[-2]["utc"],
            ),
            "park event UTC is not canonical and strictly increasing",
        ),
    ],
)
def test_agent_park_tampered_event_fails_closed(
    tmp_path,
    mutation,
    error,
):
    root = make_repo(tmp_path)
    event_path = root / "apps" / "agent-park" / "events.jsonl"
    events = [
        json.loads(line)
        for line in event_path.read_text().splitlines()
    ]
    mutation(events)
    write_canonical_jsonl(event_path, events)

    result, value = tool_result(
        make_server(root),
        "agent_park_time_travel",
        {"source": "park", "sequence": 0},
    )
    assert result["isError"]
    assert value["error"] == error


def test_agent_park_tampered_contract_with_stale_digest_fails_closed(
    tmp_path,
):
    root = make_repo(tmp_path)
    contract_path = (
        root / "apps" / "agent-park" / "agent-contract-v2.json"
    )
    contract = json.loads(contract_path.read_text())
    contract["visibility"] = "tampered-public-metadata"
    contract_path.write_text(json.dumps(contract))

    result, value = tool_result(make_server(root), "get_home", {})
    assert result["isError"]
    assert value["error"] == "park v2 contract digest mismatch"


def test_agent_park_tampered_bundle_digest_fails_closed(tmp_path):
    root = make_repo(tmp_path)
    state_path = root / "apps" / "agent-park" / "park-state.json"
    state = json.loads(state_path.read_text())
    state["integrity"]["bundle_digest"] = "0" * 64
    state_path.write_text(json.dumps(state))

    result, value = tool_result(
        make_server(root),
        "agent_park_export_branch",
        {},
    )
    assert result["isError"]
    assert value["error"] == "park bundle digest mismatch"


def test_agent_park_tampered_legacy_contract_fails_closed(tmp_path):
    root = make_repo(tmp_path)
    legacy_path = root / "apps" / "agent-park" / "agent-contract.json"
    legacy_path.write_bytes(legacy_path.read_bytes() + b"\n")

    result, value = tool_result(make_server(root), "get_home", {})
    assert result["isError"]
    assert value["error"] == "park v1 legacy contract hash mismatch"


def test_agent_park_id_fails_closed(tmp_path):
    root = make_repo(tmp_path)
    state_path = root / "apps" / "agent-park" / "park-state.json"
    state = json.loads(state_path.read_text())
    state["park_id"] = "park.other"
    state_path.write_text(json.dumps(state))

    result, value = tool_result(make_server(root), "get_home", {})
    assert result["isError"]
    assert value["error"] == (
        "park authority boundary is unsafe or incomplete"
    )


def test_agent_park_v2_limit_and_schema_must_match_runtime(tmp_path):
    root = make_repo(tmp_path)
    contract_path = (
        root / "apps" / "agent-park" / "agent-contract-v2.json"
    )
    contract = json.loads(contract_path.read_text())
    contract["action_limit"]["max_local_actions_per_mcp_session"] = 101
    contract_path.write_text(json.dumps(contract))
    result, value = tool_result(make_server(root), "get_home", {})
    assert result["isError"]
    assert "authority boundary" in value["error"]


def test_writes_are_prepared_but_disabled_by_default(tmp_path):
    server = make_server(tmp_path)
    result, value = tool_result(
        server,
        "register_agent",
        {
            "agent_id": "other-ai",
            "name": "Other AI",
            "description": "Contributes bounded reviews",
            "capabilities": ["review_apps", "comment"],
            "owner_url": "https://example.invalid/agent",
            "public_key": {
                "kty": "EC",
                "crv": "P-256",
                "x": "A" * 43,
                "y": "B" * 43,
            },
        },
    )
    assert not result["isError"]
    assert value["status"] == "prepared-not-submitted"
    assert value["write_enabled"] is False
    assert "RAPPTERZOO_MCP_WRITES=1" == value["enable_with"]
    assert value["effect"] == "github-issue-proposal-only"
    assert value["canonical_mutation"] is False
    assert value["operator_approval_required"] is True
    assert value["real_money"] is False
    assert "<!-- rappterzoo-mcp:" in value["body"]
    assert '"crv":"P-256"' in value["body"]


def test_submit_app_round_trips_through_safe_issue_encoding(tmp_path):
    server = make_server(tmp_path)
    html = (
        '<!DOCTYPE html><html><head><meta name="viewport" '
        'content="width=device-width"><title>Safe App</title></head>'
        '<body><script>const heading = "### stays data";</script></body></html>'
    )
    result, value = tool_result(
        server,
        "submit_app",
        {
            "title": "Safe App",
            "category": "data_tools",
            "html_content": html,
        },
    )
    assert not result["isError"]
    assert html not in value["body"]
    parsed = process_agent_issues.parse_issue_body(value["body"])
    assert process_agent_issues.decode_submitted_html(parsed) == html


def test_request_and_tool_size_bounds_fail_closed(tmp_path, monkeypatch):
    server = make_server(tmp_path)
    result, value = tool_result(
        server,
        "search_apps",
        {"query": "x" * 201},
    )
    assert result["isError"]
    assert "query" in value["error"]

    oversized_html = (
        '<!DOCTYPE html><meta name="viewport"><title>Large</title>'
        + ("x" * mcp.MAX_APP_BYTES)
    )
    result, value = tool_result(
        server,
        "submit_app",
        {
            "title": "Large",
            "category": "data_tools",
            "html_content": oversized_html,
        },
    )
    assert result["isError"]
    assert "500 KiB" in value["error"]

    request = (
        b'{"jsonrpc":"2.0","id":1,"method":"ping","params":{}}\n'
    )

    class Input:
        buffer = io.BytesIO(request)

    output = io.StringIO()
    monkeypatch.setattr(mcp, "MAX_REQUEST_BYTES", len(request) - 1)
    monkeypatch.setattr(mcp.sys, "stdin", Input())
    monkeypatch.setattr(mcp.sys, "stdout", output)
    assert mcp.run_stdio(server) == 0
    response = json.loads(output.getvalue())
    assert response["error"]["code"] == -32700
    assert response["error"]["message"] == "request exceeds one MiB"


def test_write_path_is_shell_free_and_idempotent(
    tmp_path,
    monkeypatch,
):
    calls = []
    created_marker = {"value": None}

    def runner(command, **kwargs):
        calls.append((command, kwargs))
        assert isinstance(command, list)
        assert not kwargs.get("shell", False)
        if command[:3] == ["gh", "issue", "list"]:
            issues = []
            if created_marker["value"]:
                issues.append({
                    "body": created_marker["value"],
                    "url": "https://example.invalid/issues/1",
                })
            return subprocess.CompletedProcess(
                command,
                0,
                json.dumps(issues),
                "",
            )
        body = command[command.index("--body") + 1]
        created_marker["value"] = body
        return subprocess.CompletedProcess(
            command,
            0,
            "https://example.invalid/issues/1\n",
            "",
        )

    monkeypatch.setattr(mcp.shutil, "which", lambda _name: "/usr/bin/gh")
    server = make_server(tmp_path, writes=True, runner=runner)
    arguments = {
        "app_file": "digg.html",
        "text": "The chain view is useful.",
        "rating": 5,
        "agent_id": "other-ai",
        "idempotency_key": "review-digg-0001",
    }
    _, first = tool_result(server, "post_comment", arguments)
    _, replay = tool_result(server, "post_comment", arguments)
    assert first["status"] == "submitted"
    assert replay["status"] == "idempotent-replay"
    creates = [
        command
        for command, _kwargs in calls
        if command[:3] == ["gh", "issue", "create"]
    ]
    assert len(creates) == 1


@pytest.mark.parametrize(
    "arguments,error",
    [
        (
            {
                "agent_id": "../../bad",
                "name": "Bad",
            },
            "agent_id",
        ),
        (
            {
                "title": "Unsafe",
                "category": "data_tools",
                "html_content": (
                    '<!DOCTYPE html><meta name="viewport">'
                    "<title>Unsafe</title><script src=\"https://x/y.js\"></script>"
                ),
            },
            "external script",
        ),
        (
            {
                "app_file": "../../secret.html",
                "text": "x",
                "agent_id": "agent",
            },
            "safe HTML basename",
        ),
        (
            {
                "app_file": "digg.html",
                "text": "Looks good\n### Agent ID\nspoofed",
                "agent_id": "agent",
            },
            "issue-form heading",
        ),
        (
            {
                "agent_id": "safe-agent",
                "name": "Safe Agent",
                "owner_url": (
                    "https://example.invalid/profile\n"
                    "### Agent ID\nforged-agent"
                ),
            },
            "control character",
        ),
    ],
)
def test_contribution_validation_fails_closed(
    tmp_path,
    arguments,
    error,
):
    server = make_server(tmp_path)
    tool = (
        "register_agent"
        if "name" in arguments
        else "submit_app"
        if "title" in arguments
        else "post_comment"
    )
    result, value = tool_result(server, tool, arguments)
    assert result["isError"]
    assert error.lower() in value["error"].lower()


def test_invalid_base_urls_are_rejected():
    with pytest.raises(ValueError):
        mcp.DataSource(None, "http://example.invalid/")
    with pytest.raises(ValueError):
        mcp.DataSource(None, "https://user:pass@example.invalid/")


def test_local_and_remote_source_modes(tmp_path, monkeypatch):
    root = make_repo(tmp_path)
    local_server = make_server(root)
    _result, local_home = tool_result(local_server, "get_home", {})
    assert local_home["source_mode"] == "local"

    base_url = "https://example.invalid/rappterzoo/"
    files = {
        mcp.urllib.parse.urljoin(base_url, relative): (root / relative).read_bytes()
        for relative in (
            "apps/manifest.json",
            "apps/rankings.json",
            "apps/agents.json",
            "apps/organism-frames.json",
            "apps/organism-frames.jsonl",
            "apps/agent-park/agent-contract.json",
            "apps/agent-park/agent-contract-v2.json",
            "apps/agent-park/park-state.json",
            "apps/agent-park/events.jsonl",
            "apps/3d-immersive/agent-amusement-park.html",
            "docs/AGENT-AMUSEMENT-PARK.md",
        )
    }

    class Response:
        def __init__(self, data):
            self.data = data

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self, limit):
            return self.data[:limit]

    def urlopen(request, timeout=0):
        return Response(files[request.full_url])

    monkeypatch.setattr(mcp.urllib.request, "urlopen", urlopen)
    remote_server = mcp.JSONRPCServer(mcp.RappterZooMCP(
        mcp.DataSource(None, base_url)
    ))
    _result, remote_home = tool_result(remote_server, "get_home", {})
    assert remote_home["source_mode"] == "remote"
    assert remote_home["catalog"] == local_home["catalog"]
    remote_state = call(
        remote_server,
        "resources/read",
        {"uri": "rappterzoo://agent-park-state"},
    )
    assert "chrono-coaster" in remote_state["result"]["contents"][0]["text"]
    _result, remote_time = tool_result(
        remote_server,
        "agent_park_time_travel",
        {"source": "park", "sequence": 1},
    )
    assert remote_time["record"]["kind"] == "park.control-boundary"
    _result, remote_visit = tool_result(
        remote_server,
        "agent_park_local_action",
        {
            "action": "visit",
            "agent_id": "agent.remote-reader",
            "attraction_id": "chrono-coaster",
        },
    )
    assert remote_visit["status"] == "local-only"


def test_jsonrpc_errors_and_notifications(tmp_path):
    server = make_server(tmp_path)
    assert server.handle({
        "jsonrpc": "2.0",
        "method": "notifications/initialized",
    }) is None
    assert server.handle({
        "jsonrpc": "2.0",
        "method": "unknown/notification",
    }) is None
    missing = call(server, "missing/method")
    assert missing["error"]["code"] == -32601
    invalid = server.handle({"jsonrpc": "1.0"})
    assert invalid["error"]["code"] == -32600


def test_first_use_prompt_is_discoverable(tmp_path):
    server = make_server(tmp_path)
    prompts = call(server, "prompts/list")["result"]["prompts"]
    assert [item["name"] for item in prompts] == [
        "rappterzoo_first_use",
        "agent_amusement_park_first_visit",
    ]
    prompt = call(
        server,
        "prompts/get",
        {"name": "rappterzoo_first_use"},
    )["result"]
    text = prompt["messages"][0]["content"]["text"]
    assert "get_home" in text
    assert "at most one bounded contribution" in text
    park_prompt = call(
        server,
        "prompts/get",
        {"name": "agent_amusement_park_first_visit"},
    )["result"]
    park_text = park_prompt["messages"][0]["content"]["text"]
    assert "rappterzoo://agent-park-contract" in park_text
    assert "rappterzoo://agent-park-contract-v2" in park_text
    assert "rappterzoo://agent-park-contract-v1" in park_text
    assert "rappterzoo://agent-amusement-park" in park_text
    assert "rappterzoo://agent-park-guide" in park_text
    assert "rappterzoo://organism-log" in park_text
    assert "rappterzoo://agent-park-bundle-verifier" in park_text
    assert "rappterzoo://agent-park-acceptance-gate" in park_text
    assert "agent_park_time_travel" in park_text
    assert "agent_park_local_action" in park_text
    assert "agent_park_export_branch" in park_text
    assert "immediate shutdown authority" in park_text
    assert "No action spends real money" in park_text
    assert "service-worker activation" in park_text
    assert "defines no undo or import tool" in park_text
    assert "does not verify the bundle before promotion" in park_text
    assert "origin-scoped" in park_text
    assert "plaintext over local stdio" in park_text


def test_server_source_has_no_unsafe_execution_sink():
    source = (ROOT / "scripts" / "rappterzoo_mcp.py").read_text()
    assert "shell=True" not in source
    assert "os.system(" not in source
    assert "eval(" not in source
    assert "exec(" not in source
    assert "new Function" not in source


def test_runtime_schemas_are_closed(tmp_path):
    server = make_server(tmp_path)
    tools = call(server, "tools/list")["result"]["tools"]
    assert all(
        tool["inputSchema"].get("additionalProperties") is False
        for tool in tools
    )
    result, value = tool_result(
        server,
        "search_apps",
        {"query": "organism", "unexpected": True},
    )
    assert result["isError"]
    assert "unknown argument" in value["error"]
    resource_schema = next(
        tool["inputSchema"]["properties"]["resource_request"]
        for tool in tools
        if tool["name"] == "agent_park_local_action"
    )
    assert resource_schema["additionalProperties"] is False


def test_static_runtime_and_documentation_parity():
    static = json.loads((ROOT / ".well-known" / "mcp.json").read_text())
    protocol = json.loads(
        (ROOT / ".well-known" / "agent-protocol").read_text()
    )
    syndication = json.loads(
        (ROOT / ".well-known" / "rappterzoo-syndication").read_text()
    )
    feed_toc = json.loads(
        (ROOT / ".well-known" / "feeddata-toc").read_text()
    )
    package = json.loads((ROOT / "skill.json").read_text())
    skill = (ROOT / "skill.md").read_text()
    guide = (ROOT / "docs" / "AGENT-AMUSEMENT-PARK.md").read_text()
    server = mcp.JSONRPCServer(mcp.RappterZooMCP(
        mcp.DataSource(ROOT, "https://example.invalid/rappterzoo/")
    ))
    runtime_prompts = call(server, "prompts/list")["result"]["prompts"]
    contract = json.loads(
        (ROOT / "apps" / "agent-park" / "agent-contract-v2.json").read_text()
    )
    state = json.loads(
        (ROOT / "apps" / "agent-park" / "park-state.json").read_text()
    )

    assert static["tools"] == mcp._tool_definitions()
    assert static["prompts"] == runtime_prompts
    assert static["server_info"]["version"] == mcp.SERVER_VERSION
    assert protocol["version"] == mcp.SERVER_VERSION
    assert package["version"] == mcp.SERVER_VERSION
    assert mcp.RESOURCE_MAP["rappterzoo://agent-park-contract"][0] == (
        "apps/agent-park/agent-contract-v2.json"
    )
    assert mcp.RESOURCE_MAP["rappterzoo://agent-park-contract-v1"][0] == (
        "apps/agent-park/agent-contract.json"
    )
    static_resources = {
        item["name"]: item
        for item in static["resources"]
    }
    assert static_resources["agent_park_contract"]["uri"].endswith(
        "/localFirstTools-main/apps/agent-park/agent-contract-v2.json"
    )
    season_2 = static["stdio_server"]["agent_park_season_2"]
    assert season_2["canonical_hash_domains"] == (
        contract["canonicalization_and_hashing"]["hash_domains"]
    )
    assert season_2["mcp_local_branch_hashing"]["domain_prefix"] is False
    assert season_2["mcp_local_branch_hashing"][
        "branch_digest_preimage"
    ] == (
        "mcp_local_branch_json(export excluding branch_digest)"
    )
    assert season_2["bundle"]["bundle_digest"] == (
        contract["integrity"]["bundle_digest"]
    )
    assert season_2["bundle"]["contract_digest"] == (
        contract["integrity"]["contract_digest"]
    )
    assert season_2["bundle"]["state_digest"] == (
        state["integrity"]["state_digest"]
    )
    assert season_2["verifier"]["version"] == (
        contract["verifier"]["version"]
    )
    assert protocol["discovery"]["agent_park_contract"].endswith(
        "/localFirstTools-main/apps/agent-park/agent-contract-v2.json"
    )
    assert protocol["discovery"]["agent_park_service_worker"].endswith(
        "/localFirstTools-main/apps/3d-immersive/"
        "agent-amusement-park-sw.js"
    )
    assert all(
        not value.startswith("/")
        for value in protocol["discovery"].values()
        if isinstance(value, str)
    )
    assert syndication["agent_amusement_park"]["contract_version"] == 2
    assert syndication["agent_amusement_park"][
        "mcp_branch_export_schema"
    ] == "rappterzoo-agent-park-local-branch/2"
    assert syndication["agent_amusement_park"]["browser_current_branch"][
        "mcp_contract_compatible"
    ] is False
    for document in (
        protocol["agent_amusement_park"],
        syndication["agent_amusement_park"],
    ):
        assert document["bundle"]["bundle_digest"] == (
            contract["integrity"]["bundle_digest"]
        )
        assert document["bundle"]["contract_digest"] == (
            contract["integrity"]["contract_digest"]
        )
        assert document["bundle"]["state_digest"] == (
            state["integrity"]["state_digest"]
        )
    feed_urls = {
        item.get("url")
        for section in ("dataset", "hasPart")
        for item in feed_toc.get(section, [])
    }
    assert (
        "https://kody-w.github.io/localFirstTools-main/"
        "apps/agent-park/agent-contract-v2.json"
    ) in feed_urls
    assert re.search(
        r"^version: {}$".format(re.escape(mcp.SERVER_VERSION)),
        skill,
        re.MULTILINE,
    )
    for text in (skill, guide):
        assert "agent_park_time_travel" in text
        assert "agent_park_local_action" in text
        assert "agent_park_export_branch" in text
        assert "real money" in text.lower()
        assert "customer" in text.lower()
        assert "rappterzoo-agent-park-local-branch/2" in text
        assert "no domain prefix" in text.lower()
        assert "origin" in text.lower()
        assert "encrypt" in text.lower()
        assert re.search(r"service[- ]worker", text, re.IGNORECASE)
        assert re.search(r"cold\s+offline", text, re.IGNORECASE)
        assert "undo" in text.lower()
        assert re.search(
            r"does\s+(?:\*\*)?not(?:\*\*)?\s+verify",
            text,
            re.IGNORECASE,
        )
    for domain in contract["canonicalization_and_hashing"][
        "hash_domains"
    ].values():
        assert domain.replace("\n", "\\n") in guide
    for fact in (
        "floats",
        "I-JSON-safe base-10 integers",
        "NFC",
        "ASCII-only",
        "1 MiB",
        "no domain prefix",
    ):
        assert fact.lower() in guide.lower()


def test_runtime_profile_matches_generated_v2_contract():
    contract = json.loads(
        (ROOT / "apps" / "agent-park" / "agent-contract-v2.json").read_text()
    )
    assert contract["schema"] == mcp.PARK_CONTRACT_SCHEMA
    assert contract["seasons"]["latest"] == mcp.PARK_CONTRACT_VERSION
    assert contract["branch_export"]["export_schema"] == (
        mcp.PARK_BRANCH_SCHEMA
    )
    assert contract["branch_export"]["action_schema"] == (
        mcp.PARK_ACTION_SCHEMA
    )
    assert mcp.PARK_BRANCH_SCHEMA.endswith("/2")
    assert mcp.PARK_ACTION_SCHEMA.endswith("/2")
    assert contract["action_limit"][
        "max_local_actions_per_mcp_session"
    ] == mcp.MAX_LOCAL_BRANCH_ACTIONS
    assert contract["action_limit"]["max_resource_units_per_field"] == (
        mcp.MAX_PARK_RESOURCE_UNITS
    )
    assert contract["action_limit"]["max_synthetic_bid"] == (
        mcp.MAX_SYNTHETIC_BID
    )
    assert set(contract["agent_actions"]) == mcp.PARK_ACTIONS | {
        "time_travel"
    }
    preimages = contract["canonicalization_and_hashing"]["preimages"]
    for name in (
        "branch_digest",
        "local_action_hash",
        "local_action_payload_hash",
    ):
        assert preimages[name]["digest"] == "sha256"
        assert preimages[name]["domain_prefix"] is False

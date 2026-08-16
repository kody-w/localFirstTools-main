"""Tests for the portable RappterZoo MCP server."""

import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import rappterzoo_mcp as mcp
import process_agent_issues


def make_repo(tmp_path):
    (tmp_path / "apps").mkdir()
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
    (tmp_path / "skills.md").write_text("# RappterZoo skills\n")
    (tmp_path / ".well-known" / "mcp.json").write_text('{"tools":[]}')
    return tmp_path


def make_server(tmp_path, writes=False, runner=subprocess.run):
    source = mcp.DataSource(
        make_repo(tmp_path),
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
    assert "local-only visit" in park_text
    assert "immediate shutdown authority" in park_text


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

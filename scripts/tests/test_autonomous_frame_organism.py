"""Integration tests for autonomous-frame organism receipts."""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import autonomous_frame


def test_log_frame_records_append_only_receipt(tmp_path, monkeypatch):
    state_path = tmp_path / "molter-state.json"
    state_path.write_text(
        '{"frame":3,"history":[],"config":{}}',
        encoding="utf-8",
    )
    monkeypatch.setattr(autonomous_frame, "STATE_FILE", state_path)
    monkeypatch.setattr(
        autonomous_frame,
        "append_molter_frame",
        lambda frame, observation, actions, utc: {
            "seq": 9,
            "payload_hash": "a" * 64,
            "frame_hash": "b" * 64,
        },
    )
    autonomous_frame.log_frame(
        4,
        {
            "total_apps_manifest": 10,
            "avg_score": 60,
            "below_40": 1,
            "unmolted": 2,
        },
        {
            "cleaned": 0,
            "molted": [],
            "created": [],
            "data_molted": False,
            "scored": False,
            "socialized": False,
            "broadcast": False,
            "agent_issues": 0,
        },
    )
    state = json.loads(state_path.read_text())
    assert state["frame"] == 4
    assert state["history"][-1]["organism_frame"] == {
        "seq": 9,
        "payload_hash": "a" * 64,
        "frame_hash": "b" * 64,
    }


@pytest.mark.parametrize("pending", [False, True])
def test_publish_failure_propagates_with_or_without_pending_issues(tmp_path, monkeypatch, pending):
    calls = []

    def process(**kwargs):
        calls.append("process")
        if pending:
            kwargs["defer_close_path"].write_text("[]", encoding="utf-8")
        return int(pending)

    monkeypatch.setitem(sys.modules, "process_agent_issues", SimpleNamespace(
        process_all_issues=process,
        finalize_issue_results=lambda path: calls.append("finalized"),
    ))
    monkeypatch.setattr(autonomous_frame.tempfile, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(autonomous_frame, "DRY_RUN", False)
    monkeypatch.setattr(autonomous_frame, "SKIP_PUSH", False)
    monkeypatch.setattr(autonomous_frame, "observe", lambda: {"frame": 0})
    monkeypatch.setattr(autonomous_frame, "decide", lambda obs: {
        "cleanup": False, "data_molt": False, "html_molt": False, "score": False,
        "socialize": False, "broadcast": False,
    })
    monkeypatch.setattr(autonomous_frame, "poke_ghost", lambda *args: False)
    monkeypatch.setattr(autonomous_frame, "run_script", lambda *args: (True, "", ""))
    monkeypatch.setattr(autonomous_frame, "log_frame", lambda *args: None)
    monkeypatch.setattr(autonomous_frame, "publish", lambda *args: False)
    with pytest.raises(RuntimeError, match="frame publish failed"):
        autonomous_frame.main([])
    assert calls == ["process"]
    assert not list(tmp_path.glob("rappterzoo-agent-results-*"))


@pytest.mark.parametrize("skip_push,published", [(True, True), (False, True), (False, {"status": "failed"})])
def test_issue_finalization_requires_boolean_successful_push(tmp_path, monkeypatch, skip_push, published):
    calls = []

    def process(**kwargs):
        kwargs["defer_close_path"].write_text("[]", encoding="utf-8")
        calls.append("process")
        return 1

    def publish(*args):
        calls.append("publish")
        return published

    monkeypatch.setitem(sys.modules, "process_agent_issues", SimpleNamespace(
        process_all_issues=process,
        finalize_issue_results=lambda path: calls.append("finalize"),
    ))
    monkeypatch.setitem(sys.modules, "activity_log", SimpleNamespace(log_activity=lambda *args: None))
    monkeypatch.setattr(autonomous_frame.tempfile, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(autonomous_frame, "DRY_RUN", False)
    monkeypatch.setattr(autonomous_frame, "SKIP_PUSH", skip_push)
    monkeypatch.setattr(autonomous_frame, "observe", lambda: {"frame": 0})
    monkeypatch.setattr(autonomous_frame, "decide", lambda obs: {
        "cleanup": False, "data_molt": False, "html_molt": False, "score": False,
        "socialize": False, "broadcast": False,
    })
    monkeypatch.setattr(autonomous_frame, "poke_ghost", lambda *args: False)
    monkeypatch.setattr(autonomous_frame, "run_script", lambda *args: (True, "", ""))
    monkeypatch.setattr(autonomous_frame, "log_frame", lambda *args: None)
    monkeypatch.setattr(autonomous_frame, "publish", publish)
    if isinstance(published, dict):
        with pytest.raises(RuntimeError, match="Boolean"):
            autonomous_frame.main([])
    else:
        autonomous_frame.main([])
    assert calls == ["process", "publish"] + (["finalize"] if published is True and not skip_push else [])


@pytest.mark.parametrize("failed_command", ["add", "diff", "commit", "push"])
def test_publish_returns_false_for_each_git_failure(tmp_path, monkeypatch, failed_command):
    apps = tmp_path / "apps"
    apps.mkdir()
    (apps / "manifest.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(autonomous_frame, "ROOT", tmp_path)
    monkeypatch.setattr(autonomous_frame, "APPS_DIR", apps)
    monkeypatch.setattr(autonomous_frame, "SKIP_PUSH", False)
    for name in ("COMMUNITY_FILE", "FEED_FILE", "GHOST_STATE_FILE"):
        monkeypatch.setattr(autonomous_frame, name, tmp_path / "absent")
    commands = []

    def run(argv, **kwargs):
        command = argv[1]
        commands.append(command)
        code = 2 if command == failed_command else (1 if command == "diff" else 0)
        return SimpleNamespace(returncode=code, stderr="fixture git failure")

    monkeypatch.setattr(autonomous_frame.subprocess, "run", run)
    assert autonomous_frame.publish(1, {}) is False
    assert commands[-1] == failed_command

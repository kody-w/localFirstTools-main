"""Integration tests for autonomous-frame organism receipts."""

import json
import sys
from pathlib import Path


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

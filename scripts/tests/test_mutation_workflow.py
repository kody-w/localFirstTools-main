"""Exercise the actual workflow decision scripts with bounded local inputs."""

import json
import os
from pathlib import Path
import re
import subprocess
import sys
import textwrap

import pytest


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = (ROOT / ".github/workflows/autonomous-frame.yml").read_text().replace("\r\n", "\n")
BLOCKS = [textwrap.dedent(block) for block in re.findall(r"<<'PY'\n(.*?)\n[ \t]+PY", WORKFLOW, re.S)]
BASE = "a" * 40


def run_block(tmp_path, index, data, *arguments):
    source = tmp_path / "input.json"
    source.write_text(json.dumps(data))
    env = {
        "PATH": os.environ.get("PATH", ""),
        "RUNNER_TEMP": str(tmp_path),
        "GITHUB_OUTPUT": str(tmp_path / "outputs"),
        "BASE_COMMIT": BASE,
        "GITHUB_RUN_ID": "20",
        "GITHUB_REPOSITORY": "fixture/repository",
    }
    return subprocess.run(
        [sys.executable, "-c", BLOCKS[index], str(source), *map(str, arguments)],
        env=env, capture_output=True, text=True, timeout=10,
    )


def test_workflow_preserves_controller_and_transport_contract():
    assert len(BLOCKS) == 2
    assert "workflow_runs" in BLOCKS[0] and "molter-workflow-outcome/v1" in BLOCKS[1]
    assert WORKFLOW.count("cron:") == 1
    assert '--prepare-proposal "$RUNNER_TEMP/molter-proposal"' in WORKFLOW
    assert '--base "$BASE_COMMIT"' in WORKFLOW and '--repository "$GITHUB_REPOSITORY"' in WORKFLOW
    assert 'test "$(git rev-parse origin/main)" = "$GITHUB_SHA"' in WORKFLOW
    assert "scripts/mutation_handoff.py pack" in WORKFLOW
    assert "scripts/mutation_handoff.py unpack" in WORKFLOW
    assert "path: ${{ runner.temp }}/mutation-proposal.tar" in WORKFLOW
    assert "pull-requests: write" not in WORKFLOW and "actions: write" not in WORKFLOW
    assert "git push" not in WORKFLOW


def test_first_committed_input_can_run(tmp_path):
    history = [{"total_count": 1, "workflow_runs": [{
        "id": 20, "head_sha": BASE, "head_branch": "main", "conclusion": None,
        "html_url": "https://example.invalid/current",
    }]}]
    assert run_block(tmp_path, 0, history).returncode == 0


def test_cache_loss_does_not_regenerate_a_known_completed_input(tmp_path):
    history = [{"total_count": 1, "workflow_runs": [{
        "id": 19, "head_sha": BASE, "head_branch": "main", "conclusion": "success",
        "html_url": "https://example.invalid/previous",
    }]}]
    result = run_block(tmp_path, 0, history)
    assert result.returncode != 0
    assert "rather than regenerating" in result.stderr


@pytest.mark.parametrize("history", [[], [{}], [{"total_count": 10, "workflow_runs": []}]])
def test_missing_history_is_not_a_fresh_input(tmp_path, history):
    assert run_block(tmp_path, 0, history).returncode != 0


def test_only_real_prepared_success_is_exportable(tmp_path):
    result = run_block(tmp_path, 1, {
        "status": "prepared", "qualified": True, "deployment_verified": False,
        "private_detail": "not-for-export",
    }, 0)
    assert result.returncode == 0
    summary = json.loads((tmp_path / "molter-outcome.json").read_text())
    assert summary["qualified"] is True and summary["deployment_verified"] is False
    assert "not-for-export" not in (tmp_path / "molter-outcome.json").read_text()
    assert (tmp_path / "outputs").read_text() == "qualified=true\n"


@pytest.mark.parametrize("value,code", [
    ({"status": "prepared", "qualified": False, "deployment_verified": False}, 0),
    ({"status": "prepared", "qualified": True, "deployment_verified": True}, 0),
    ({"status": "prepared", "qualified": True, "deployment_verified": False}, 1),
    ({"status": "failed", "reason": "private-test-canary"}, 1),
    (["not-a-result"], 0),
])
def test_failure_and_inconsistent_success_do_not_export_candidate_data(tmp_path, value, code):
    result = run_block(tmp_path, 1, value, code)
    assert result.returncode != 0
    summary = (tmp_path / "molter-outcome.json").read_text()
    assert json.loads(summary)["qualified"] is False
    assert "private-test-canary" not in summary
    assert (tmp_path / "outputs").read_text() == "qualified=false\n"

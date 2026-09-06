"""Reproductions for the independent critic's process and FIFO findings."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import molter_capabilities as proposals


ROOT = Path(__file__).resolve().parents[2]


def test_fifo_preparation_lock_fails_without_blocking(tmp_path):
    proposal = tmp_path / "proposal"
    proposal.mkdir()
    os.mkfifo(proposal / ".preparation.lock", 0o600)
    script = (
        "import sys; from pathlib import Path; "
        "sys.path.insert(0,sys.argv[1]); "
        "import molter_capabilities as p; p._attempt_active(Path(sys.argv[2]))"
    )
    result = subprocess.run(
        [sys.executable, "-B", "-c", script, str(ROOT / "scripts"), str(proposal)],
        capture_output=True, timeout=2,
    )
    assert result.returncode != 0
    assert b"unsafe preparation lock" in result.stderr


def test_outer_worker_timeout_stops_inference_descendants(tmp_path):
    proposal = tmp_path / "proposal"
    scripts = proposal / "source/scripts"
    scripts.mkdir(parents=True)
    (proposal / "source/apps").mkdir()
    (proposal / "source/apps/manifest.json").write_text("{}")
    shutil.copyfile(ROOT / "scripts/copilot_utils.py", scripts / "copilot_utils.py")
    ready, escaped = proposal / "ready", proposal / "escaped"
    child = (
        "import pathlib,sys,time; "
        "pathlib.Path(sys.argv[1]).write_text('ready'); "
        "time.sleep(1.5); pathlib.Path(sys.argv[2]).write_text('escaped')"
    )
    (scripts / "molt.py").write_text(
        "import os,sys\n"
        "from pathlib import Path\n"
        "from copilot_utils import _run_inference\n"
        "def prepare_molt_candidate(*args, **kwargs):\n"
        "    root = Path(__file__).resolve().parents[2]\n"
        "    _run_inference([sys.executable, '-c', " + repr(child) + ", "
        "str(root / 'ready'), str(root / 'escaped')], cwd=root, env=os.environ.copy(), "
        "timeout=8, scratch=root)\n"
        "    return {'status':'failed'}\n",
        encoding="utf-8",
    )
    request = proposal / "request.json"
    request.write_text(json.dumps({
        "target": "fixture.html", "objective": "owned process fixture",
        "candidate_sha256": None, "allow_model": True, "timeout_seconds": 8,
    }))
    with pytest.raises(proposals.ProposalError, match="timed out"):
        proposals._worker("candidate", proposal, request, timeout=0.7)
    assert ready.exists(), "The inference descendant must actually start."
    time.sleep(1.5)
    assert not escaped.exists(), "Inference outlived the managed worker timeout."
    diagnostic = json.loads((proposal / "diagnostics/candidate.json").read_text())
    assert diagnostic["timed_out"] is True
    assert not (proposal / "check-work").exists()


def test_nested_check_supervisor_unwinds_before_outer_timeout_returns(tmp_path):
    ready, escaped = tmp_path / "ready", tmp_path / "escaped"
    child = (
        "import pathlib,sys,time; pathlib.Path(sys.argv[1]).write_text('ready'); "
        "time.sleep(1.5); pathlib.Path(sys.argv[2]).write_text('escaped')"
    )
    parent = (
        "import os,sys; sys.path.insert(0,sys.argv[1]); "
        "import molter_capabilities as p; "
        "p.run_isolated([sys.executable,'-c',sys.argv[2],sys.argv[3],sys.argv[4]], "
        "cwd=os.getcwd(), env=os.environ.copy(), timeout=8)"
    )
    with pytest.raises(subprocess.TimeoutExpired):
        proposals.run_isolated(
            [sys.executable, "-B", "-c", parent, str(ROOT / "scripts"), child, str(ready), str(escaped)],
            cwd=tmp_path, env=proposals.environment(), timeout=0.7,
        )
    assert ready.exists(), "The nested check must actually start."
    time.sleep(1.5)
    assert not escaped.exists()

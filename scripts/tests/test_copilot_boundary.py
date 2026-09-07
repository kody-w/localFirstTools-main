"""Output-only CLI boundaries; live model calls are never needed by this suite."""

import os
from pathlib import Path
import subprocess
import sys
import time

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import copilot_utils as copilot


@pytest.mark.parametrize("prompt", ["small prompt", "x" * 150000, "\U0001f3af" * 40000],
                         ids=["small", "large-ascii", "multibyte"])
def test_prompt_size_never_grants_tools_or_exposes_the_caller_workspace(tmp_path, monkeypatch, prompt):
    subprocess.run(["git", "init", "--quiet", str(tmp_path)], check=True)
    canonical_git = tmp_path / ".git"
    monkeypatch.setenv("GIT_DIR", str(canonical_git))
    monkeypatch.setenv("GIT_WORK_TREE", str(tmp_path))
    monkeypatch.setenv("COPILOT_ALLOW_ALL", "true")
    monkeypatch.setenv("COPILOT_CUSTOM_INSTRUCTIONS_DIRS", str(tmp_path))
    monkeypatch.setenv("COPILOT_GITHUB_TOKEN", "test-auth-value-not-a-credential")
    monkeypatch.setattr(copilot.tempfile, "tempdir", str(tmp_path))
    seen = {}

    def run(command, *, cwd, env, timeout, scratch):
        seen["scratch"] = scratch
        assert (cwd / "prompt.txt").read_bytes() == prompt.encode("utf-8")
        assert command[:3] == ["gh", "copilot", "--"]
        assert "--available-tools=view" in command
        assert command.count("--add-dir") == 1
        assert command[command.index("--add-dir") + 1] == str(cwd)
        assert {"--deny-tool=shell", "--deny-tool=write", "--deny-tool=url"} <= set(command)
        assert "--disable-builtin-mcps" in command
        assert "--no-custom-instructions" in command
        assert "--disallow-temp-dir" in command
        assert "--no-remote-export" in command
        assert not any(value.startswith("--allow-") or value == "--yolo" for value in command)
        assert prompt not in command
        assert str(cwd / "prompt.txt") in command[command.index("-p") + 1]
        assert env["COPILOT_ALLOW_ALL"] == "false"
        assert "COPILOT_CUSTOM_INSTRUCTIONS_DIRS" not in env
        assert "GIT_DIR" not in env and "GIT_WORK_TREE" not in env
        assert env["GIT_CONFIG_GLOBAL"] == os.devnull
        assert env["GIT_CONFIG_NOSYSTEM"] == "1"
        assert env["COPILOT_GITHUB_TOKEN"] == "test-auth-value-not-a-credential"
        assert Path(env["COPILOT_HOME"]).parent == scratch
        assert Path(env["COPILOT_HOME"]) != cwd and cwd.parent == scratch
        actual_root = subprocess.check_output(
            ["git", "-C", str(cwd), "rev-parse", "--show-toplevel"],
            env=env, text=True,
        ).strip()
        assert Path(actual_root).resolve() == cwd.resolve()
        assert (canonical_git / "HEAD").is_file()
        assert timeout == 12
        return "response-only"

    monkeypatch.setattr(copilot, "_run_inference", run)
    assert copilot.copilot_call(prompt, timeout=12) == "response-only"
    assert not seen["scratch"].exists()
    assert os.environ["COPILOT_ALLOW_ALL"] == "true"
    assert os.environ["GIT_DIR"] == str(canonical_git)


@pytest.mark.parametrize("prompt", [None, "", "   "])
def test_invalid_prompt_never_starts_a_process(monkeypatch, prompt):
    monkeypatch.setattr(copilot, "_run_inference", lambda *args, **kwargs: pytest.fail("must not invoke"))
    with pytest.raises(ValueError):
        copilot.copilot_call(prompt)


@pytest.mark.parametrize("timeout", [0, -1, float("nan"), float("inf"), True, None])
def test_invalid_timeout_never_starts_a_process(monkeypatch, timeout):
    monkeypatch.setattr(copilot, "_run_inference", lambda *args, **kwargs: pytest.fail("must not invoke"))
    with pytest.raises(ValueError):
        copilot.copilot_call("bounded prompt", timeout=timeout)


def test_prompt_limit_counts_bytes_not_characters(monkeypatch, caplog):
    monkeypatch.setattr(copilot, "MAX_PROMPT_BYTES", 4)
    monkeypatch.setattr(copilot, "_run_inference", lambda *args, **kwargs: pytest.fail("must not invoke"))
    assert copilot.copilot_call("\u00e9" * 3) is None
    assert "byte limit" in caplog.text


def test_failed_private_workspace_setup_is_visible(monkeypatch, caplog):
    monkeypatch.setattr(copilot.subprocess, "run", lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 1))
    monkeypatch.setattr(copilot, "_run_inference", lambda *args, **kwargs: pytest.fail("must not invoke"))
    assert copilot.copilot_call("bounded prompt") is None
    assert "isolate" in caplog.text


def test_disk_failure_cleans_workspace_without_invocation(monkeypatch, caplog):
    seen = []

    def disk_full(path, data):
        seen.append(path.parent.parent)
        raise OSError("simulated disk exhaustion")

    monkeypatch.setattr(Path, "write_bytes", disk_full)
    monkeypatch.setattr(copilot, "_run_inference", lambda *args, **kwargs: pytest.fail("must not invoke"))
    assert copilot.copilot_call("bounded prompt") is None
    assert seen and all(not path.exists() for path in seen)
    assert "private inference workspace" in caplog.text


def execute(tmp_path, program, *, timeout=5, arguments=()):
    return copilot._run_inference(
        [sys.executable, "-c", program, *map(str, arguments)],
        cwd=tmp_path,
        env={"PATH": os.environ.get("PATH", "")},
        timeout=timeout,
        scratch=tmp_path,
    )


def test_bounded_capture_returns_response_text(tmp_path):
    assert execute(tmp_path, "print('  response  ')") == "response"


def test_oversized_response_fails(tmp_path, monkeypatch, caplog):
    monkeypatch.setattr(copilot, "MAX_RESPONSE_BYTES", 32)
    assert execute(tmp_path, "print('x' * 33)") is None
    assert "response exceeded" in caplog.text


def test_oversized_diagnostics_fail_without_echoing_them(tmp_path, monkeypatch, caplog):
    monkeypatch.setattr(copilot, "MAX_ERROR_BYTES", 32)
    assert execute(tmp_path, "import sys; sys.stderr.write('x' * 33); print('response')") is None
    assert "diagnostics exceeded" in caplog.text


def test_failed_cli_does_not_log_private_response_or_error(tmp_path, caplog):
    canary = "private-test-canary-not-a-real-secret"
    assert execute(
        tmp_path,
        "import sys; print(sys.argv[1]); sys.stderr.write(sys.argv[1]); sys.exit(7)",
        arguments=(canary,),
    ) is None
    assert "exit code 7" in caplog.text
    assert canary not in caplog.text


def test_invalid_utf8_is_failure(tmp_path, caplog):
    assert execute(tmp_path, "import sys; sys.stdout.buffer.write(b'\\xff')") is None
    assert "invalid UTF-8" in caplog.text


def test_timeout_is_failure_and_stops_the_owned_process(tmp_path, monkeypatch, caplog):
    processes = []
    original = copilot._stop_inference

    def stop(process):
        processes.append(process)
        original(process)

    monkeypatch.setattr(copilot, "_stop_inference", stop)
    assert execute(tmp_path, "import time; time.sleep(10); print('too late')", timeout=0.2) is None
    assert "timeout" in caplog.text
    assert len(processes) == 1 and processes[0].poll() is not None


def test_timeout_stops_owned_descendants(tmp_path):
    ready, escaped = tmp_path / "ready", tmp_path / "escaped"
    child = "import pathlib,sys,time; time.sleep(3.5); pathlib.Path(sys.argv[1]).write_text('escaped')"
    parent = (
        "import pathlib,subprocess,sys,time; "
        "subprocess.Popen([sys.executable,'-c',sys.argv[1],sys.argv[3]]); "
        "pathlib.Path(sys.argv[2]).write_text('ready'); "
        "time.sleep(10); print('too late')"
    )
    assert execute(tmp_path, parent, timeout=2, arguments=(child, ready, escaped)) is None
    assert ready.exists(), "The descendant witness must actually start."
    time.sleep(2)
    assert not escaped.exists(), "An owned descendant escaped the invocation timeout."

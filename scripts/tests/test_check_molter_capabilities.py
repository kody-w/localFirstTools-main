"""Unit controls for the gate itself, not evidence of application correctness."""

import importlib.util
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "check_molter_capabilities.py"
SPEC = importlib.util.spec_from_file_location("check_molter_capabilities", SCRIPT)
gate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gate)


@pytest.fixture
def contract(tmp_path, monkeypatch):
    manifest = tmp_path / "acceptance.json"
    manifest.write_text(json.dumps({
        "schema": "rappterzoo-molter-acceptance/v1",
        "scope": "gate unit fixture",
        "cases": [{"id": "first"}, {"id": "second"}],
    }), encoding="utf-8")
    tests = tmp_path / "acceptance_test.py"
    tests.write_text("# Test-runner fixture, never executed.\n", encoding="utf-8")
    monkeypatch.setattr(gate, "ROOT", tmp_path)
    monkeypatch.setattr(gate, "CONTRACT", manifest)
    monkeypatch.setattr(gate, "TESTS", tests)
    return manifest


def runner(monkeypatch, xml=None, returncode=0):
    def run(command, **kwargs):
        assert command[:3] == [gate.sys.executable, "-m", "pytest"]
        assert kwargs["timeout"] == 300
        assert kwargs["check"] is False
        if xml is not None:
            Path(command[-1]).write_text(xml, encoding="utf-8")
        return SimpleNamespace(returncode=returncode)
    monkeypatch.setattr(gate.subprocess, "run", run)


def test_missing_tests_fail_before_execution(contract, monkeypatch):
    gate.TESTS.unlink()
    monkeypatch.setattr(gate.subprocess, "run", lambda *args, **kwargs: pytest.fail("must not execute"))
    assert gate.main() == 1


def test_nonzero_runner_result_is_not_hidden(contract, monkeypatch):
    runner(monkeypatch, returncode=3)
    assert gate.main() == 3


def test_missing_report_cannot_pass(contract, monkeypatch):
    runner(monkeypatch)
    assert gate.main() == 1


def test_zero_measurements_cannot_pass(contract, monkeypatch):
    runner(monkeypatch, '<testsuites><testsuite tests="99"/></testsuites>')
    assert gate.main() == 1


@pytest.mark.parametrize("incomplete", ["skipped", "failure", "error"])
def test_incomplete_measurement_cannot_pass(contract, monkeypatch, incomplete):
    runner(monkeypatch, (
        '<testsuites><testsuite><testcase name="test_first"/>'
        '<testcase name="test_second"><' + incomplete + '/></testcase>'
        '</testsuite></testsuites>'
    ))
    assert gate.main() == 1


def test_missing_named_case_cannot_pass(contract, monkeypatch):
    runner(monkeypatch, '<testsuite><testcase name="test_first"/></testsuite>')
    assert gate.main() == 1


def test_complete_named_measurements_pass(contract, monkeypatch):
    runner(monkeypatch, (
        '<testsuite><testcase name="test_first"/>'
        '<testcase name="test_second[mutation]"/></testsuite>'
    ))
    assert gate.main() == 0


@pytest.mark.parametrize("cases", [[], [{"id": "same"}, {"id": "same"}], [{"id": "../bad"}], [None]])
def test_malformed_contract_cannot_pass(contract, monkeypatch, cases):
    value = json.loads(contract.read_text(encoding="utf-8"))
    value["cases"] = cases
    contract.write_text(json.dumps(value), encoding="utf-8")
    monkeypatch.setattr(gate.subprocess, "run", lambda *args, **kwargs: pytest.fail("must not execute"))
    assert gate.main() == 1


def test_timeout_is_explicit_failure(contract, monkeypatch):
    def timeout(command, **kwargs):
        raise subprocess.TimeoutExpired(command, kwargs["timeout"])
    monkeypatch.setattr(gate.subprocess, "run", timeout)
    assert gate.main() == 1

#!/usr/bin/env python3
"""Run the named Molter capability contracts; missing or skipped cases fail."""

import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs/molter-capabilities/acceptance.json"
TESTS = ROOT / "scripts/tests/test_molter_capabilities.py"


def main():
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    cases = contract.get("cases")
    if contract.get("schema") != "rappterzoo-molter-acceptance/v1" or not isinstance(cases, list) or not cases:
        print("FAIL: the acceptance contract is missing or unsupported.")
        return 1
    identifiers = [case.get("id") if isinstance(case, dict) else None for case in cases]
    if any(not isinstance(value, str) or not re.fullmatch(r"[a-z][a-z0-9_]*", value) for value in identifiers):
        print("FAIL: acceptance case identifiers are invalid.")
        return 1
    required = {"test_" + value for value in identifiers}
    if len(required) != len(cases):
        print("FAIL: acceptance case identifiers are duplicated.")
        return 1
    if not TESTS.is_file():
        print("FAIL: executable Molter capability acceptance cases are missing.")
        return 1
    with tempfile.TemporaryDirectory(prefix="molter-acceptance-") as directory:
        report = Path(directory) / "results.xml"
        try:
            completed = subprocess.run(
                [
                    sys.executable, "-m", "pytest", "-q", "-m", "",
                    str(TESTS), "--junitxml", str(report),
                ],
                cwd=str(ROOT),
                check=False,
                timeout=300,
            )
        except subprocess.TimeoutExpired:
            print("FAIL: the acceptance measurements exceeded 300 seconds.")
            return 1
        if completed.returncode != 0:
            return completed.returncode
        if not report.is_file():
            print("FAIL: the test runner produced no measurement report.")
            return 1
        cases = list(ET.parse(report).iter("testcase"))
        measured = {case.get("name", "").split("[", 1)[0] for case in cases}
        missing = sorted(required - measured)
        incomplete = [
            case.get("name", "")
            for case in cases
            if any(case.find(kind) is not None for kind in ("failure", "error", "skipped"))
        ]
        if missing or incomplete:
            print(json.dumps({"missing": missing, "incomplete": incomplete}, sort_keys=True))
            return 1
        print(json.dumps({
            "schema": contract["schema"],
            "status": "passed",
            "required_cases": len(required),
            "measured_cases": len(cases),
            "scope": contract["scope"],
        }, sort_keys=True))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())

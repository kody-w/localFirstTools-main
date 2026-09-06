#!/usr/bin/env python3
"""Run the preserved unittest suites and actual relocated CLI witnesses.

This command explicitly runs trusted local processes and writes disposable
fixtures inside this package. It never qualifies a target application.
"""

import argparse
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
import uuid

if __package__:
    from .verify_vendor import ROOT, verify_vendor
else:
    from verify_vendor import ROOT, verify_vendor


SUITES = {
    "tests.test_capability_contracts": 11,
    "tests.test_capability_package": 22,
    "tests.test_capability_registry": 25,
    "tests.test_port": 4,
}


def complete_result(result, expected):
    return (
        expected > 0 and result.testsRun == expected and result.wasSuccessful()
        and not result.skipped and not result.expectedFailures and not result.unexpectedSuccesses
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rapp-dir", help="canonical checkout/export; defaults to the bundled verified export")
    args = parser.parse_args(argv)
    reference = Path(args.rapp_dir).absolute() if args.rapp_dir else ROOT / "vendor/rapp-1"
    try:
        integrity = verify_vendor(rapp_dir=reference)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print("check_port: " + str(exc), file=sys.stderr)
        return 1
    workspace = ROOT / (".validation-" + uuid.uuid4().hex)
    workspace.mkdir()
    previous_cwd, previous_tempdir = Path.cwd(), tempfile.tempdir
    keys = ("TMPDIR", "TMP", "TEMP", "RAPP_REFERENCE_DIR", "PYTHONDONTWRITEBYTECODE")
    previous_environment = {key: os.environ.get(key) for key in keys}
    try:
        os.chdir(ROOT)
        for key in ("TMPDIR", "TMP", "TEMP"):
            os.environ[key] = str(workspace)
        tempfile.tempdir = str(workspace)
        os.environ["RAPP_REFERENCE_DIR"] = str(reference)
        os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
        loader = unittest.TestLoader()
        suite = unittest.TestSuite()
        for name, expected in SUITES.items():
            selected = loader.loadTestsFromName(name)
            if selected.countTestCases() != expected or loader.errors:
                print("check_port: missing or changed required cases in " + name, file=sys.stderr)
                return 1
            suite.addTests(selected)
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        passed = complete_result(result, sum(SUITES.values()))
        print(json.dumps({
            "schema": "source-capsule-port-validation/v1",
            "outcome": "passed" if passed else "failed",
            "tests_run": result.testsRun,
            "required_tests": sum(SUITES.values()),
            "skipped": len(result.skipped),
            "errors": len(result.errors),
            "failures": len(result.failures),
            "expected_failures": len(result.expectedFailures),
            "unexpected_successes": len(result.unexpectedSuccesses),
            "manifest_sha256": integrity["manifest_sha256"],
            "scope": "Preserved evaluator and disposable local Git fixture tests, not target app reuse or deployment.",
        }, sort_keys=True))
        return 0 if passed else 1
    finally:
        os.chdir(previous_cwd)
        tempfile.tempdir = previous_tempdir
        for key, value in previous_environment.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        shutil.rmtree(workspace)


if __name__ == "__main__":
    raise SystemExit(main())

"""Relocation witnesses; every write is inside an owned disposable fixture."""

from argparse import Namespace
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import unittest
from unittest.mock import patch
import uuid

import check_port
from scripts import capability_contracts as contracts
from scripts import capability_package as package
from verify_vendor import MANIFEST, MANIFEST_SHA256, ROOT, verify_vendor


class PortTests(unittest.TestCase):
    def setUp(self):
        self.fixtures = ROOT / "tests/.port-fixtures"
        self.case = self.fixtures / uuid.uuid4().hex
        self.case.mkdir(parents=True)
        self.addCleanup(self.cleanup)
        scratch = self.case / "scratch"
        scratch.mkdir()
        self.environment = {
            **os.environ, "PYTHONDONTWRITEBYTECODE": "1",
            "TMPDIR": str(scratch), "TMP": str(scratch), "TEMP": str(scratch),
            "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
        }

    def cleanup(self):
        shutil.rmtree(self.case)
        try:
            self.fixtures.rmdir()
        except OSError:
            pass

    def copy_package(self, destination):
        provenance = contracts.load_json(ROOT / "upstream.json")
        paths = [item["path"] for group in ("upstream", "reference")
                 for item in provenance[group]["files"]]
        paths += ["upstream.json", "verify_vendor.py", "__init__.py", "__main__.py",
                  "scripts/__init__.py", "tests/__init__.py"]
        for name in paths:
            target = destination / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)
        return destination

    def git(self, root, *arguments):
        environment = package.git_source._git_environment()
        environment.update({
            "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_AUTHOR_DATE": "2026-09-06T12:00:00Z",
            "GIT_COMMITTER_DATE": "2026-09-06T12:00:00Z",
        })
        return subprocess.run(
            ["git", "-C", str(root), "-c", "user.name=Capsule Port Fixture",
             "-c", "user.email=capsule-port@example.invalid", "-c", "commit.gpgsign=false",
             "-c", "core.hooksPath=.git/no-hooks", "-c", "init.defaultBranch=main", *arguments],
            env=environment, capture_output=True, text=True, check=True, timeout=15,
        ).stdout.strip()

    def run_command(self, root, argv, expected=0, timeout=150):
        completed = subprocess.run(
            argv, cwd=root, env=self.environment, capture_output=True, text=True,
            check=False, timeout=timeout,
        )
        self.assertEqual(completed.returncode, expected, completed.stdout + completed.stderr)
        return completed

    def cli(self, root, script, arguments, expected=0):
        completed = self.run_command(root, [sys.executable, "-B", script, *arguments], expected)
        return json.loads(completed.stdout) if expected == 0 else completed

    def test_preserved_source_and_export_pins_with_mutation_controls(self):
        root = self.copy_package(self.case / "portable")
        export = root / "vendor/rapp-1"
        self.assertFalse((export / ".git").exists())
        self.assertEqual({path.name for path in export.iterdir()},
                         {"rapp.py", "rapp_check.py", "SPEC.md", "LICENSE"})
        with patch("subprocess.run", side_effect=AssertionError("export verification needs no Git")):
            verified = verify_vendor(root)
        self.assertEqual(verified["manifest_sha256"], MANIFEST_SHA256)
        self.assertEqual(verified["pinned_artifacts"], 6)
        canonical = package.frames.Reference(os.environ["RAPP_REFERENCE_DIR"])
        self.assertEqual(verified["reference"], canonical.identity)
        for name in (
            MANIFEST, "landgrab/autocomplete/rapp-reference.json",
            "scripts/capability_package.py", "scripts/capability_registry.py",
            "tests/test_capability_package.py", "tests/test_capability_contracts.py",
            "tests/test_capability_registry.py", "vendor/rapp-1/rapp.py",
            "vendor/rapp-1/rapp_check.py", "vendor/rapp-1/SPEC.md",
        ):
            with self.subTest(path=name):
                path = root / name
                original = path.read_bytes()
                path.write_bytes(original + b" ")
                with self.assertRaises(ValueError):
                    verify_vendor(root)
                path.write_bytes(original)
        with self.assertRaisesRegex(ValueError, "directory does not exist"):
            verify_vendor(root, rapp_dir=self.case / "missing-reference")
        self.assertTrue(verify_vendor(root)["verified"])

    def test_public_import_is_pure_and_resolves_nested_modules(self):
        code = """
import os
from pathlib import Path
import sys
import scripts
cwd, paths = os.getcwd(), tuple(scripts.__path__)
from scripts.capabilities import source_capsule as port
assert os.getcwd() == cwd
assert tuple(scripts.__path__) == paths
assert port.ROOT == Path(sys.argv[1])
assert port.MANIFEST == 'landgrab/autocomplete/capabilities/manifests/source-capsule.json'
assert port.RAPP_REFERENCE_DIR == port.ROOT / 'vendor/rapp-1'
for module in (port.capability_package, port.capability_contracts,
               port.capability_registry, port.autocomplete_frames):
    assert Path(module.__file__).parent == port.ROOT / 'scripts'
assert 'capability_package' not in sys.modules
assert callable(port.capability_package.qualify)
assert callable(port.capability_package.verify)
assert callable(port.capability_registry.build_registry)
"""
        self.run_command(ROOT.parents[2], [sys.executable, "-B", "-c", code, str(ROOT)])
        result = self.run_command(
            ROOT.parents[2], [sys.executable, "-B", "-m", "scripts.capabilities.source_capsule", "--help"],
        )
        self.assertIn("qualify", result.stdout)
        self.assertIn("verify", result.stdout)

    def test_relocated_cli_qualifies_replays_and_binds_real_registry(self):
        source = self.case / "source"
        (source / "nested").mkdir(parents=True)
        originals = {
            "sample.txt": (b"Committed caf\xc3\xa9\r\nsecond line\n", 0o644),
            "nested/run.py": (b"print('source capsule fixture')\r\n", 0o755),
        }
        for name, (body, mode) in originals.items():
            (source / name).write_bytes(body)
            (source / name).chmod(mode)
        self.git(source, "init", "--quiet")
        self.git(source, "add", "--all")
        self.git(source, "commit", "--quiet", "-m", "disposable committed transport fixture")
        commit = self.git(source, "rev-parse", "HEAD")
        root = self.copy_package(source / "implementation")
        self.git(root, "init", "--quiet")
        self.git(root, "add", "--all")
        self.git(root, "commit", "--quiet", "-m", "disposable preserved evaluator fixture")
        (source / "sample.txt").write_bytes(b"Mutable working bytes are not transported.\n")
        source_options = [
            "--repo", "..", "--ref", commit, "--repository", "example/source-capsule-port-fixture",
            "--path", "sample.txt", "--path", "nested/run.py",
        ]
        packed = self.cli(root, package.ENTRYPOINT,
                          ["pack", *source_options, "--output", "proofs/packed.json"])
        self.assertEqual(packed["files"], 2)
        capsule = contracts.load_json(root / "proofs/packed.json")
        self.assertEqual(capsule["origin"]["commit"], commit)
        restore = ["restore", "--capsule", "proofs/packed.json", "--destination", "proofs/restored"]
        self.assertEqual(self.cli(root, package.ENTRYPOINT, restore)["restored_files"], 2)
        self.cli(root, package.ENTRYPOINT, restore, expected=1)
        for name, (body, mode) in originals.items():
            restored = root / "proofs/restored" / name
            self.assertEqual(restored.read_bytes(), body)
            self.assertEqual(stat.S_IMODE(restored.stat().st_mode), mode)
        capsule["files"][0]["text"] = "tampered capsule"
        (root / "proofs/tampered.json").write_bytes(contracts.json_bytes(capsule))
        self.cli(root, package.ENTRYPOINT, [
            "restore", "--capsule", "proofs/tampered.json", "--destination", "proofs/refused",
        ], expected=1)
        self.assertFalse((root / "proofs/refused").exists())

        common = ["--root", ".", "--manifest", MANIFEST]
        qualify = ["qualify", *common, *source_options, "--workflow", "port-relocation"]
        self.cli(root, package.ENTRYPOINT, [
            *qualify, "--capsule", "proofs/denied.json", "--report", "proofs/denied-report.json",
        ], expected=1)
        denied = contracts.load_json(root / "proofs/denied-report.json")
        self.assertEqual(denied["outcome"], "failed")
        self.assertEqual(denied["checks"], [])
        paths = ["--capsule", "proofs/capsule.json", "--report", "proofs/qualification.json"]
        self.assertEqual(self.cli(root, package.ENTRYPOINT, [
            *qualify, *paths, "--allow-checks",
        ])["outcome"], "passed")
        report = contracts.load_json(root / "proofs/qualification.json")
        manifest = contracts.load_json(root / MANIFEST)
        self.assertEqual(report["capability"]["manifest_sha256"], MANIFEST_SHA256)
        self.assertEqual(report["gates"],
                         {"source_matches": True, "round_trip": True, "artifacts_stable": True})
        self.assertEqual(len(report["checks"]), 2)
        for check, declared in zip(report["checks"], manifest["checks"]):
            self.assertEqual(check["argv"], declared["argv"])
            self.assertTrue(package.frames.check_passed(check))
            self.assertGreater(check["stderr_bytes"], 0)
        replay = report["replay_argv"]
        self.assertEqual(len(replay), 15)
        self.assertEqual(contracts.validate_source_replay(replay, package.ENTRYPOINT)["repo"], "..")
        unchanged = {
            name: (root / name).read_bytes()
            for name in (MANIFEST, paths[1], paths[3], *(item["path"] for item in manifest["artifacts"]))
        }
        actual = json.loads(self.run_command(root, replay).stdout)
        self.assertEqual(actual["outcome"], "passed")
        self.assertTrue(actual["replayed"])
        for name, body in unchanged.items():
            self.assertEqual((root / name).read_bytes(), body)
        self.assertFalse(list(root.glob(".capability-replay-*")))
        for flag in ("--replay", "--allow-checks"):
            self.run_command(root, [part for part in replay if part != flag], expected=1)
        with self.assertRaises(ValueError):
            contracts.validate_source_replay([*replay, "--help"], package.ENTRYPOINT)
        (root / "proofs/moved-report.json").write_bytes(unchanged[paths[3]])
        moved = [*replay]
        moved[12] = "proofs/moved-report.json"
        self.run_command(root, moved, expected=1)

        reference = package.frames.Reference(root / "vendor/rapp-1")
        store = root / "proofs/evidence"
        package.frames.init_store(store, "capsule-port-tests", "relocation", reference)
        with patch.dict(os.environ, self.environment, clear=True):
            receipt, code = package.frames.record(Namespace(
                store=str(store), repo=str(root), run_id="port-validation", worker="fixture",
                phase="implementation", summary="Actual preserved evaluator replay on disposable source",
                parent=[], check_timeout=150,
                artifact=[MANIFEST, *(item["path"] for item in manifest["artifacts"]), paths[1], paths[3]],
                check=[json.dumps(replay)],
            ), reference)
        self.assertEqual(code, 0, receipt)
        self.assertEqual(receipt["outcome"], "checks_passed")
        registry_script = "scripts/capability_registry.py"
        registry_options = [
            *common, "--store", "proofs/evidence", "--rapp-dir", "vendor/rapp-1",
        ]
        registry = self.cli(root, registry_script, [
            "build", *registry_options, "--output", "proofs/registry.json",
        ])
        self.assertEqual(registry["evidence"]["state"], "verified")
        self.assertEqual(registry["evidence"]["frames"], 1)
        self.assertEqual(registry["assets"][0]["status"], "proven")
        self.assertEqual(registry["assets"][0]["distinct_repositories"], 1)
        self.assertEqual(registry["assets"][0]["uses"][0]["frame_hash"], receipt["frame_hash"])
        verify_registry = ["verify", *registry_options, "--registry", "proofs/registry.json"]
        self.assertTrue(self.cli(root, registry_script, verify_registry)["verified"])
        projection = self.cli(root, registry_script, [
            "search", "--registry", "proofs/registry.json", "--query", "source capsule",
        ])
        self.assertTrue(projection["projection_only"])
        self.assertEqual(len(projection["matches"]), 1)
        frame_path = store / receipt["path"]
        original_frame = frame_path.read_bytes()
        frame = json.loads(original_frame)
        frame["payload"]["summary"] = "uncoordinated frame tampering"
        frame_path.write_bytes(contracts.json_bytes(frame))
        self.cli(root, registry_script, verify_registry, expected=2)
        frame_path.write_bytes(original_frame)
        self.assertTrue(self.cli(root, registry_script, verify_registry)["verified"])

    def test_validation_gate_rejects_incomplete_measurements(self):
        result = unittest.TestResult()
        self.assertFalse(check_port.complete_result(result, 1))
        self.assertFalse(check_port.complete_result(result, 0))
        result.testsRun = 1
        self.assertTrue(check_port.complete_result(result, 1))
        self.assertFalse(check_port.complete_result(result, 2))
        for field in ("skipped", "failures", "errors", "expectedFailures", "unexpectedSuccesses"):
            with self.subTest(field=field):
                setattr(result, field, [("controlled witness", "not a complete passing test")])
                self.assertFalse(check_port.complete_result(result, 1))
                setattr(result, field, [])
        self.assertTrue(check_port.complete_result(result, 1))


if __name__ == "__main__":
    unittest.main()

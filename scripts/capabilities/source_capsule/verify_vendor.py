#!/usr/bin/env python3
"""Verify preserved upstream bytes and the canonical reference export, offline."""

import argparse
from pathlib import Path
import sys

if __package__:
    from .scripts import autocomplete_frames as frames
    from .scripts import capability_contracts as contracts
else:
    from scripts import autocomplete_frames as frames
    from scripts import capability_contracts as contracts


ROOT = Path(__file__).resolve().parent
MANIFEST = "landgrab/autocomplete/capabilities/manifests/source-capsule.json"
MANIFEST_SHA256 = "e6f639a6d9c0625d3857f872e979e415b92dc4811902156d686ae8db885b3b45"
REFERENCE_PIN = "landgrab/autocomplete/rapp-reference.json"
REFERENCE_PIN_SHA256 = "bcdd67fbb0c5b2a344c2fb8f1befebc4de95bf4184a2b796ebf296f631480a0e"
SOURCE_COMMIT = "aa6b9e28745d64cc5a16154a3506a494112ee701"
REFERENCE_COMMIT = "eb50008011447f5e69372ac22a1755f0978d15ed"


def verify_vendor(root=ROOT, rapp_dir=None):
    root = frames.root_path(root)
    provenance = contracts.load_json(root / "upstream.json")
    contracts.require(provenance.get("schema") == "source-capsule-vendor/v1",
                      "unsupported vendor provenance")
    contracts.require(provenance["upstream"]["repository"] ==
                      "https://github.com/kody-w/localFirstTools"
                      and provenance["upstream"]["commit"] == SOURCE_COMMIT,
                      "upstream identity changed")
    contracts.require(provenance["reference"]["repository"] == "https://github.com/kody-w/rapp-1"
                      and provenance["reference"]["commit"] == REFERENCE_COMMIT,
                      "reference identity changed")
    contracts.require(provenance["imported_history"] is False, "historical state is not part of this port")
    manifest, revision = contracts.load_manifest(root / MANIFEST, root)
    contracts.require(revision == MANIFEST_SHA256, "preserved manifest raw bytes changed")
    contracts.require(provenance["capability"] == {
        "id": "source-capsule", "version": "1.0.3", "manifest": MANIFEST,
        "manifest_sha256": MANIFEST_SHA256, "pinned_artifacts": 6,
    }, "capability provenance changed")
    contracts.require(frames.digest(frames.read_bytes(root / REFERENCE_PIN, contracts.MAX_MANIFEST_BYTES))
                      == REFERENCE_PIN_SHA256, "preserved reference pin raw bytes changed")
    pin = contracts.load_json(root / REFERENCE_PIN)
    contracts.require(pin["commit"] == REFERENCE_COMMIT, "reference commit pin changed")
    expected_source = {item["path"] for item in manifest["artifacts"]} | {
        MANIFEST, REFERENCE_PIN, "scripts/capability_registry.py",
        "tests/test_capability_registry.py", "notices/localFirstTools-AGENTS.md",
    }
    expected_reference = {"vendor/rapp-1/" + name for name in (*pin["files"], "LICENSE")}
    for group, expected in (("upstream", expected_source), ("reference", expected_reference)):
        records = provenance[group]["files"]
        contracts.require(len(records) == len(expected)
                          and {item["path"] for item in records} == expected,
                          "incomplete or duplicate " + group + " inventory")
        for item in records:
            path = contracts.source_path(root, item["path"])
            raw = frames.read_bytes(path, contracts.MAX_JSON_BYTES)
            contracts.require(len(raw) == item["bytes"] and frames.digest(raw) == item["sha256"],
                              "preserved upstream bytes changed: " + item["path"])
    reference = frames.Reference(rapp_dir if rapp_dir is not None else root / "vendor/rapp-1")
    return {
        "schema": "source-capsule-vendor-verification/v1",
        "verified": True,
        "manifest_sha256": revision,
        "pinned_artifacts": len(manifest["artifacts"]),
        "upstream_files": len(expected_source),
        "reference_files": len(expected_reference),
        "reference": reference.identity,
        "reference_git_required": False,
        "scope": "Source integrity only; no qualification checks or target application executed.",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rapp-dir", help="optional canonical checkout/export; no automatic fetch")
    args = parser.parse_args(argv)
    try:
        print(contracts.json_bytes(verify_vendor(rapp_dir=args.rapp_dir)).decode(), end="")
        return 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print("verify_vendor: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

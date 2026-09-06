#!/usr/bin/env python3
"""Internal, isolated worker for the mutation source-capsule adapter."""

import argparse
from contextlib import redirect_stdout
import json
from pathlib import Path
import sys


MANIFEST = "landgrab/autocomplete/capabilities/manifests/source-capsule.json"
PIN = "landgrab/autocomplete/rapp-reference.json"
MANIFEST_SHA256 = "e6f639a6d9c0625d3857f872e979e415b92dc4811902156d686ae8db885b3b45"
CAPSULE = "handoff/source.json"
REPORT = "handoff/qualification.json"


def candidate(proposal, request):
    source = proposal / "source"
    sys.path.insert(0, str(source / "scripts"))
    import molt

    if not callable(getattr(molt, "prepare_molt_candidate", None)):
        raise ValueError("the committed Molter has no prepare_molt_candidate API")
    supplied = request["candidate_sha256"] is not None
    with redirect_stdout(sys.stderr):
        return molt.prepare_molt_candidate(
            request["target"], request["objective"],
            candidate_html=(proposal / "candidate-input.html").read_bytes().decode("utf-8")
            if supplied else None,
            allow_model=request["allow_model"],
            apps_dir=source / "apps",
            manifest=json.loads((source / "apps/manifest.json").read_text(encoding="utf-8")),
            timeout=request["timeout_seconds"],
        )


def capability(proposal, request, action):
    from molter_capabilities import verify_implementation_inputs

    root = proposal / "capability"
    verify_implementation_inputs(root)
    sys.path.insert(0, str(root / "scripts"))
    import autocomplete_frames as frames
    import capability_contracts as contracts
    import capability_package as package
    import capability_registry as registry

    manifest, revision = contracts.load_manifest(root / MANIFEST, root)
    contracts.require(revision == MANIFEST_SHA256, "source-capsule manifest pin mismatch")
    inventory, _ = registry.load_inventory(root, manifest_paths=[MANIFEST])
    reference_dir = "vendor/rapp-1" if (root / "vendor/rapp-1").exists() else "reference"
    reference = frames.Reference(root / reference_dir)
    if action == "preflight":
        package.pack_sources(proposal / "source", request["base_commit"],
                             request["repository"], [request["app_path"]])
        return {"manifest_sha256": revision, "reference": reference.identity}

    args = argparse.Namespace(
        root=str(root), manifest=MANIFEST, repo="../source", capsule=CAPSULE,
        report=REPORT, replay=True, allow_checks=True,
        ref=request.get("candidate_commit"), repository=request["repository"],
        workflow="molter-review-proposal", path=[request["app_path"]],
    )
    options = dict(root=root, manifest_paths=[MANIFEST], store="evidence",
                   rapp_dir=root / reference_dir)
    if action == "qualify":
        qualification = package.qualify(args)
        contracts.require(qualification["outcome"] == "passed", "source qualification failed")
        frames.init_store(root / "evidence", "molter", "review-proposals", reference)
        artifacts = {CAPSULE, REPORT, PIN, "scripts/capability_registry.py"}
        artifacts.update(reference_dir + "/" + name for name in ("rapp.py", "rapp_check.py", "SPEC.md"))
        artifacts.update(name for name in ("scripts/__init__.py", "tests/__init__.py") if (root / name).is_file())
        for info in inventory.values():
            artifacts.add(info["path"])
            artifacts.update(item["path"] for item in info["manifest"]["artifacts"])
        recorded, code = frames.record(argparse.Namespace(
            store=str(root / "evidence"), repo=str(root),
            run_id="proposal-" + request["request_id"][:32], worker="source-capsule",
            phase="review", summary="Replay selected-source transport for a local mutation review proposal.",
            artifact=sorted(artifacts), check=[json.dumps(qualification["replay_argv"])],
            parent=[], check_timeout=300,
        ), reference)
        contracts.require(code == 0 and recorded["outcome"] == "checks_passed",
                          "RAPP-bound source replay failed")
        projection = registry.build_registry(**options)
        registry.write_registry(root, "registry.json", projection, store="evidence")
    else:
        capsule, raw = package._read_canonical(root / CAPSULE)
        package.validate_capsule(capsule)
        qualification, _ = package._read_canonical(root / REPORT)
        package._validate_report(qualification, args, manifest, revision, capsule, raw)

    verification = registry.verify_registry(registry="registry.json", **options)
    projection = contracts.load_json(root / "registry.json")
    asset = next(asset for asset in projection["assets"] if asset["id"] == "source-capsule")
    contracts.require(asset["status"] == "proven" and len(asset["uses"]) == 1
                      and not asset["failures"], "one real qualifying source-capsule use is required")
    use = asset["uses"][0]
    contracts.require(use["repository"] == request["repository"].casefold()
                      and use["commit"] == request["candidate_commit"],
                      "registry source binding mismatch")
    frame = frames.read_json(root / "evidence" / use["frame_path"])
    contracts.require(frame["payload"]["repository"]["base_commit"] == request["implementation_commit"],
                      "RAPP implementation snapshot binding mismatch")
    return {
        "kind": "source-capsule", "qualified": True, "manifest_sha256": revision,
        "registry_status": asset["status"], "registry_verified": verification["verified"],
        "capsule": "capability/" + CAPSULE, "report": "capability/" + REPORT,
        "registry": "capability/registry.json", "frame": use,
        "reference": reference.identity,
        "scope": "Selected committed source transport and replay, not application or deployment proof.",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("candidate", "preflight", "qualify", "verify"))
    parser.add_argument("--proposal", required=True)
    parser.add_argument("--context", required=True)
    args = parser.parse_args(argv)
    sys.dont_write_bytecode = True
    proposal = Path(args.proposal)
    request = json.loads(Path(args.context).read_text(encoding="utf-8"))
    try:
        with redirect_stdout(sys.stderr):
            result = (candidate(proposal, request) if args.action == "candidate"
                      else capability(proposal, request, args.action))
        print(json.dumps(result, sort_keys=True, ensure_ascii=False, allow_nan=False))
        return 0
    except Exception as exc:
        print("mutation worker: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

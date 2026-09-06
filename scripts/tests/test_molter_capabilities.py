"""Named acceptance cases: real source handoff plus explicit fault fixtures."""

import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import autonomous_frame
import molter_capabilities as proposals
import mutation_handoff as handoff
from scripts.tests import test_copilot_boundary as executor_cases
from scripts.tests import test_molter_proposals as fault_cases
from scripts.tests import test_mutation_worker_lifecycle as worker_cases
from scripts.capabilities.source_capsule import capability_package


ROOT = Path(__file__).resolve().parents[2]
ARCHIVE = ROOT / "docs/molter-capabilities/pilot/proposal.tar"
BASE = "27f08a6a0ea928ae678288becada60569d85a2b8"
REPOSITORY = "kody-w/localFirstTools-main"
source = fault_cases.source


def clone_base(parent, name):
    directory = parent / name
    proposals.git(parent, "clone", "--quiet", "--no-local", "--single-branch", "--no-checkout",
                  str(ROOT), str(directory))
    history = proposals._json((ARCHIVE.parent / "history.json").read_bytes())
    bundle = ARCHIVE.parent / history["bundle"]
    assert proposals.digest(bundle.read_bytes()) == history["sha256"]
    proposals.git(directory, "bundle", "verify", str(bundle))
    proposals.git(directory, "fetch", "--quiet", "--no-tags", str(bundle),
                  history["ref"] + ":refs/remotes/mutation-pilot/verified")
    assert proposals.git(directory, "rev-parse", "refs/remotes/mutation-pilot/verified").decode().strip() == history["candidate_commit"]
    proposals.git(directory, "checkout", "--quiet", "--detach", BASE)
    return directory


def request_options(repo, candidate, objective):
    return dict(repo=repo, base=BASE, repository=REPOSITORY, target="cyber-timer.html",
                candidate_file=candidate, objective=objective)


def binding(repo):
    return dict(repo=repo, base=BASE, repository=REPOSITORY)


@pytest.fixture(scope="module")
def real_handoff(tmp_path_factory):
    directory = tmp_path_factory.mktemp("real-mutation-contract").resolve()
    repo = clone_base(directory, "source")
    files, _ = handoff._archive_files(ARCHIVE)
    request = proposals._json(files["request.json"])
    candidate = directory / "candidate.html"
    candidate.write_bytes(files["candidate-input.html"])
    output = directory / "prepared"
    options = request_options(repo, candidate, request["objective"])
    result = proposals.prepare_proposal(output, **options)
    assert result["status"] == "prepared", result
    yield {"directory": directory, "repo": repo, "candidate": candidate,
           "output": output, "options": options, "result": result}


def test_pure_plan(real_handoff, monkeypatch):
    repo = real_handoff["repo"]
    before = proposals.git(repo, "status", "--porcelain=v1", "--ignored")
    monkeypatch.setattr(proposals, "_worker", lambda *args, **kwargs: pytest.fail("plan executed a worker"))
    destination = real_handoff["directory"] / "plan-only"
    result = proposals.prepare_proposal(destination, **real_handoff["options"], dry_run=True)
    assert result["status"] == "dry_run" and result["qualified"] is False
    assert not destination.exists()
    assert proposals.git(repo, "status", "--porcelain=v1", "--ignored") == before == b""


def test_immutable_capsule_transport(real_handoff, tmp_path):
    capsule = proposals._json(proposals.read(real_handoff["output"] / "capability/handoff/source.json"))
    restored = capability_package.restore_capsule(capsule, tmp_path / "restored")
    app = restored / "apps/creative-tools/cyber-timer.html"
    assert app.read_bytes() == real_handoff["candidate"].read_bytes()
    assert capsule["origin"]["commit"] == real_handoff["result"]["candidate_commit"]
    assert capsule["files"][0]["sha256"] == proposals.digest(app.read_bytes())
    assert (real_handoff["repo"] / "apps/creative-tools/cyber-timer.html").read_bytes() != app.read_bytes()


def test_qualified_prepare(real_handoff):
    result, root = real_handoff["result"], real_handoff["output"]
    assert result["qualified"] is True and result["qualification"]["registry_status"] == "proven"
    assert result["qualification"]["registry_verified"] is True
    assert result["delivery"]["state"] == "not_submitted" and result["deployment_verified"] is False
    candidate = proposals._json(proposals.read(root / "candidate-result.json"))
    assert candidate["model"]["invoked"] is False and candidate["model"]["attempts"] == 0
    assert candidate["evidence"]["end_user_usefulness"] == "not_measured"
    assert set(candidate["change_paths"]) == {
        "apps/creative-tools/cyber-timer.html", "apps/manifest.json",
        "apps/archive/cyber-timer/v1.html", "apps/archive/cyber-timer/molt-log.json",
    }
    assert not (root / "source").exists() and not (root / "capability/.git").exists()


def test_duplicate_request_noop(real_handoff, monkeypatch):
    before = handoff._records(real_handoff["output"])
    monkeypatch.setattr(proposals, "_worker", lambda *args, **kwargs: pytest.fail("duplicate reran execution"))
    result = proposals.prepare_proposal(real_handoff["output"], **real_handoff["options"])
    assert result["noop"] is True and result["request_id"] == real_handoff["result"]["request_id"]
    assert handoff._records(real_handoff["output"]) == before


def test_reject_tampered_artifact(real_handoff, tmp_path):
    root = tmp_path / "tampered"
    shutil.copytree(real_handoff["output"], root)
    app = root / "changes/apps/creative-tools/cyber-timer.html"
    app.write_bytes(app.read_bytes() + b"\n<!-- mutation -->")
    with pytest.raises(proposals.ProposalError):
        proposals.verify_proposal(root, **binding(real_handoff["repo"]))
    receipt_path = root / "receipt.json"
    receipt = proposals._json(receipt_path.read_bytes())
    receipt["artifacts"] = proposals.inventory(root)
    receipt.pop("integrity_sha256")
    receipt["integrity_sha256"] = proposals.digest(proposals.json_bytes(receipt))
    receipt_path.write_bytes(proposals.json_bytes(receipt))
    with pytest.raises(proposals.ProposalError):
        proposals.verify_proposal(root, **binding(real_handoff["repo"]))


def test_bounded_allowed_paths(real_handoff):
    root, repo = real_handoff["output"], real_handoff["repo"]
    request = proposals._json(proposals.read(root / "request.json"))
    result = proposals._json(proposals.read(root / "candidate-result.json"))
    result["changes"] = {name: proposals.read(root / "changes" / name).decode()
                         for name in result["change_paths"]}
    result["changes"]["../outside.txt"] = "not allowed"
    _, _, manifest, category, app, original = proposals.select_app(repo, BASE, request["target"])
    with pytest.raises(proposals.ProposalError):
        proposals.validate_candidate(result, repo, request, manifest, category, app, original)


def test_reject_metadata_only(real_handoff):
    from molt import prepare_molt_candidate

    repo = real_handoff["repo"]
    original = (repo / "apps/creative-tools/cyber-timer.html").read_text()
    manifest = proposals._json((repo / "apps/manifest.json").read_bytes())
    result = prepare_molt_candidate(
        "cyber-timer.html", "A real improvement is required",
        candidate_html=original + "\n<!-- generated another timestamp -->",
        apps_dir=repo / "apps", manifest=manifest,
    )
    assert result["status"] == "skipped" and result["changes"] == {}
    assert result["model"]["attempts"] == 0


def test_publication_denied_retains_proposal(real_handoff, tmp_path):
    remote, review = tmp_path / "protected.git", tmp_path / "review"
    proposals.git(tmp_path, "init", "--bare", "--quiet", str(remote))
    hook = remote / "hooks/pre-receive"
    hook.write_text("#!/bin/sh\nprintf 'review required\\n' >&2\nexit 1\n")
    hook.chmod(0o700)
    proposals.git(tmp_path, "clone", "--quiet", "--no-local", str(real_handoff["repo"]), str(review))
    proposals.git(review, "fetch", "--quiet", str(real_handoff["output"] / "candidate.bundle"),
                  "refs/heads/molter-proposal:refs/heads/review")
    proposals.git(review, "checkout", "--quiet", "review")
    before = handoff._records(real_handoff["output"])
    denied = subprocess.run(["git", "-C", str(review), "push", str(remote), "HEAD:refs/heads/main"],
                            env=proposals.environment(), capture_output=True, timeout=30)
    assert denied.returncode != 0 and b"review required" in denied.stderr
    assert handoff._records(real_handoff["output"]) == before
    result = proposals.verify_proposal(real_handoff["output"], **binding(real_handoff["repo"]))
    assert result["qualified"] is True and result["delivery"]["state"] == "not_submitted"
    assert result["deployment_verified"] is False


def test_no_implicit_network_or_model(real_handoff, monkeypatch):
    monkeypatch.setattr(proposals, "_worker", lambda *args, **kwargs: pytest.fail("unapproved execution"))
    original_git = proposals.git

    def local_only(repo, *args, **kwargs):
        assert not set(args) & {"push", "pull", "fetch"}
        return original_git(repo, *args, **kwargs)

    monkeypatch.setattr(proposals, "git", local_only)
    result = proposals.prepare_proposal(
        real_handoff["directory"] / "no-generation-authority", **binding(real_handoff["repo"]),
        target="cyber-timer.html", objective="Do not execute without permission",
    )
    assert result["status"] == "blocked" and result["qualified"] is False
    assert result["deployment_verified"] is False


def test_legacy_frame_contract(tmp_path, monkeypatch):
    import process_agent_issues

    monkeypatch.setattr(autonomous_frame, "DRY_RUN", False)
    monkeypatch.setattr(autonomous_frame, "SKIP_PUSH", False)
    monkeypatch.setattr(autonomous_frame.tempfile, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(autonomous_frame, "observe", lambda: {"frame": 1})
    monkeypatch.setattr(autonomous_frame, "decide", lambda _: {
        name: False for name in ("cleanup", "data_molt", "html_molt", "score", "socialize", "broadcast")
    })
    monkeypatch.setattr(process_agent_issues, "process_all_issues", lambda **kwargs: 0)
    monkeypatch.setattr(process_agent_issues, "finalize_issue_results", lambda *args: pytest.fail("closed issues"))
    monkeypatch.setattr(autonomous_frame, "poke_ghost", lambda *args: False)
    monkeypatch.setattr(autonomous_frame, "run_script", lambda *args: (True, "", ""))
    monkeypatch.setattr(autonomous_frame, "log_frame", lambda *args: None)
    monkeypatch.setattr(autonomous_frame, "publish", lambda *args: False)
    with pytest.raises(RuntimeError, match="frame publish failed"):
        autonomous_frame.main([])


def test_concurrent_request_single_result(source):
    # This fault fixture is explicitly unqualified; real qualification is tested above.
    fault_cases.test_concurrent_identical_preparation_admits_only_one_generator(source)


def test_interrupted_attempt_recovery(source, tmp_path):
    class Interrupted(fault_cases.Fixture):
        def prepare(self, stage, request, supplied):
            raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        fault_cases.prepare(source, Interrupted())
    retry = fault_cases.Fixture()
    with pytest.raises(proposals.ProposalError) as failed:
        fault_cases.prepare(source, retry)
    assert failed.value.recovery["automatic_retry"] is False
    assert failed.value.recovery["evidence_preserved"] is True
    assert retry.preparations == retry.qualifications == 0
    worker_cases.test_outer_worker_timeout_stops_inference_descendants(tmp_path / "managed-worker")


def test_portable_archived_replay(real_handoff, tmp_path):
    archive, restored = tmp_path / "proposal.tar", tmp_path / "restored"
    first = handoff.pack_proposal(real_handoff["output"], archive, **binding(real_handoff["repo"]))
    second = handoff.pack_proposal(real_handoff["output"], tmp_path / "repeat.tar",
                                  **binding(real_handoff["repo"]))
    assert first["archive_sha256"] == second["archive_sha256"]
    independent = tmp_path / "independent-source"
    proposals.git(tmp_path, "clone", "--quiet", "--no-local", str(real_handoff["repo"]), str(independent))
    result = handoff.unpack_proposal(archive, restored, **binding(independent))
    assert result["qualified"] is True
    assert not (restored / "source").exists() and not (restored / "capability/.git").exists()
    assert handoff._records(restored) == handoff._records(real_handoff["output"])
    replay = handoff.replay_proposal(restored, allow_checks=True, **binding(independent))
    assert replay["status"] == "replayed" and replay["preserved_artifacts_unchanged"] is True
    assert replay["new_qualification_or_registry_entry"] is False
    assert replay["deployment_verified"] is False


def test_executor_reader_isolation(tmp_path, monkeypatch):
    executor_cases.test_prompt_size_never_grants_tools_or_exposes_the_caller_workspace(
        tmp_path, monkeypatch, "\u00e9" * 60000,
    )


def test_missing_preserved_artifact_is_blocked(real_handoff, tmp_path, monkeypatch):
    root = tmp_path / "missing"
    shutil.copytree(real_handoff["output"], root)
    (root / "candidate.bundle").unlink()
    monkeypatch.setattr(proposals, "_worker", lambda *args, **kwargs: pytest.fail("regenerated missing work"))
    with pytest.raises(proposals.ProposalError):
        proposals.prepare_proposal(root, **real_handoff["options"])

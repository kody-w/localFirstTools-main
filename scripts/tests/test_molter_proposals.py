"""Adapter contract tests; the explicit fixture is NOT RAPP qualification."""

import json
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import autonomous_frame
import molter_capability_worker as capability_worker
import molter_capabilities as proposals


ORIGINAL = '<!DOCTYPE html><html><head><title>Counter</title></head><body><button>Add</button></body></html>\n'
IMPROVED = ORIGINAL.replace("<button>Add</button>", '<button aria-label="Add one">Add</button><output>0</output>')


def run_git(repo, *args):
    completed = subprocess.run(
        ["git", "-C", str(repo), "-c", "core.hooksPath=" + str(proposals.os.devnull),
         "-c", "commit.gpgSign=false", *args],
        capture_output=True, check=True, env=proposals.environment(),
    )
    return completed.stdout.decode().strip()


def snapshot(root):
    return {path.relative_to(root).as_posix(): (path.read_bytes(), path.stat().st_mtime_ns)
            for path in root.rglob("*") if path.is_file()}


@pytest.fixture
def source(tmp_path):
    repo = tmp_path / "repo"
    (repo / "apps/games").mkdir(parents=True)
    (repo / "scripts").mkdir()
    (repo / "apps/games/counter.html").write_text(ORIGINAL, encoding="utf-8")
    (repo / "apps/games/old.html").write_text(ORIGINAL, encoding="utf-8")
    (repo / "apps/manifest.json").write_text(json.dumps({
        "categories": {"games": {"folder": "games", "apps": [
            {"file": "counter.html", "title": "Counter", "generation": 0},
            {"file": "old.html", "title": "Old", "generation": 2},
        ]}},
    }), encoding="utf-8")
    (repo / "apps/rankings.json").write_text(json.dumps({
        "rankings": [{"file": "old.html", "score": 0}, {"file": "counter.html", "score": 45}],
    }), encoding="utf-8")
    (repo / ".gitignore").write_text("ignored-file\n", encoding="utf-8")
    (repo / "scripts/fixture.py").write_text("# Explicit test snapshot only.\n", encoding="utf-8")
    run_git(repo, "init", "-q")
    run_git(repo, "config", "user.name", "Fixture")
    run_git(repo, "config", "user.email", "fixture@localhost")
    run_git(repo, "add", ".")
    run_git(repo, "commit", "-qm", "fixture source")
    candidate = tmp_path / "operator.html"
    candidate.write_text(IMPROVED, encoding="utf-8")
    return {
        "repo": repo, "base": run_git(repo, "rev-parse", "HEAD"), "repository": "fixture/molter",
        "proposal": tmp_path / "proposal", "candidate": candidate,
    }


class Fixture:
    identity = "unit-tests-not-rapp-v1"

    def __init__(self, mutate=None):
        self.preparations = 0
        self.qualifications = 0
        self.verifications = 0
        self.mutate = mutate

    def prepare(self, source, request, supplied):
        self.preparations += 1
        original = (source / request["app_path"]).read_bytes()
        updated = supplied if supplied is not None else IMPROVED.encode()
        result = {
            "status": "prepared", "reason": "explicit test fixture, not real validation",
            "filename": request["target"], "app_path": request["app_path"],
            "input_sha256": proposals.digest(original), "output_sha256": proposals.digest(updated),
            "objective": request["objective"], "changes": {request["app_path"]: updated.decode()},
            "evidence": {"test_fixture": True, "real_application_validation": False},
            "model": {"invoked": request["allow_model"], "attempts": int(request["allow_model"]),
                      "timeout_seconds": request["timeout_seconds"]},
        }
        if self.mutate:
            self.mutate(result, source, request)
        return result

    def qualify(self, proposal, context):
        self.qualifications += 1
        result = {"kind": "test_fixture", "qualified": False,
                  "request_id": context["request_id"], "registry_status": None}
        proposals.write_new(proposal / "fixture-evidence.json", proposals.json_bytes(result))
        return result

    def verify(self, proposal, context):
        self.verifications += 1
        evidence = json.loads((proposal / "fixture-evidence.json").read_text())
        assert evidence == {"kind": "test_fixture", "qualified": False,
                            "request_id": context["request_id"], "registry_status": None}


def prepare(source, fixture, **kwargs):
    options = dict(repo=source["repo"], base=source["base"], repository=source["repository"],
                   candidate_file=source["candidate"], _fixture=fixture)
    options.update(kwargs)
    return proposals.prepare_proposal(source["proposal"], **options)


def verify(source, fixture, **options):
    return proposals.verify_proposal(source["proposal"], repo=source["repo"], base=source["base"],
                                     repository=source["repository"], _fixture=fixture, **options)


def test_fixture_preparation_is_local_unqualified_and_complete(source, monkeypatch):
    before = snapshot(source["repo"])
    calls = []
    original_git = proposals.git

    def guarded(repo, *args, **kwargs):
        calls.append((Path(repo), args))
        assert not set(args) & {"push", "pull", "fetch", "gh"}
        if Path(repo) == source["repo"]:
            assert args[0] not in {"add", "commit", "update-ref", "checkout", "config", "init"}
        return original_git(repo, *args, **kwargs)

    monkeypatch.setattr(proposals, "git", guarded)
    fixture = Fixture()
    result = prepare(source, fixture)
    assert result["status"] == "fixture_prepared", result
    assert result["qualified"] is False
    assert result["qualification"]["kind"] == "test_fixture"
    assert result["deployment_verified"] is False
    assert result["delivery"]["state"] == "not_submitted"
    assert result["delivery"]["externally_submitted"] is False
    assert fixture.preparations == fixture.qualifications == 1
    assert snapshot(source["repo"]) == before
    assert not (source["proposal"] / "source").exists()
    receipt = json.loads((source["proposal"] / "receipt.json").read_text())
    assert [item["path"] for item in receipt["changes"]] == ["apps/games/counter.html"]
    assert receipt["base_commit"] == source["base"]
    assert result["candidate_commit"] != source["base"]
    assert calls
    with pytest.raises(proposals.ProposalError, match="fixture evidence"):
        proposals.verify_proposal(source["proposal"], repo=source["repo"], base=source["base"],
                                  repository=source["repository"])


def test_preserved_patch_and_base_bundle_apply_offline(source, tmp_path):
    result = prepare(source, Fixture())
    assert result["status"] == "fixture_prepared", result
    replay = tmp_path / "review-worktree"
    run_git(tmp_path, "clone", "-q", "--no-local", str(source["repo"]), str(replay))
    run_git(replay, "apply", "--check", str(source["proposal"] / "proposal.patch"))
    run_git(replay, "apply", str(source["proposal"] / "proposal.patch"))
    assert (replay / "apps/games/counter.html").read_text() == IMPROVED
    run_git(replay, "restore", "apps/games/counter.html")
    run_git(replay, "fetch", "-q", str(source["proposal"] / "candidate.bundle"),
            "refs/heads/molter-proposal:refs/heads/review")
    run_git(replay, "checkout", "-q", "review")
    assert run_git(replay, "rev-parse", "HEAD") == result["candidate_commit"]
    assert run_git(replay, "rev-parse", "HEAD^") == source["base"]
    assert (replay / "apps/games/counter.html").read_text() == IMPROVED


def test_duplicate_verifies_then_is_a_real_noop(source):
    fixture = Fixture()
    first = prepare(source, fixture)
    assert first["status"] == "fixture_prepared", first
    before = snapshot(source["proposal"])
    second = prepare(source, fixture)
    assert second == {**first, "noop": True}
    assert fixture.preparations == fixture.qualifications == 1
    assert snapshot(source["proposal"]) == before
    assert verify(source, fixture)["deployment_verified"] is False


@pytest.mark.parametrize("name", [
    "proposal.patch", "candidate.bundle", "candidate-result.json", "request.json",
    "receipt.json", "fixture-evidence.json", "qualification-context.json",
    "changes/apps/games/counter.html",
])
def test_tampered_artifact_is_not_regenerated(source, name):
    fixture = Fixture()
    assert prepare(source, fixture)["status"] == "fixture_prepared"
    artifact = source["proposal"] / name
    artifact.write_bytes(artifact.read_bytes() + b"\n")
    before = snapshot(source["proposal"])
    with pytest.raises((proposals.ProposalError, ValueError)):
        prepare(source, fixture)
    assert snapshot(source["proposal"]) == before
    assert fixture.preparations == fixture.qualifications == 1


@pytest.mark.parametrize("kind", ["missing_receipt", "missing_patch", "extra_file", "symlink_artifact"])
def test_incomplete_or_undeclared_artifacts_fail_closed(source, kind):
    fixture = Fixture()
    assert prepare(source, fixture)["status"] == "fixture_prepared"
    if kind == "missing_receipt":
        (source["proposal"] / "receipt.json").unlink()
    elif kind == "missing_patch":
        (source["proposal"] / "proposal.patch").unlink()
    elif kind == "extra_file":
        (source["proposal"] / "undeclared.json").write_text("{}")
    else:
        artifact = source["proposal"] / "proposal.patch"
        artifact.unlink()
        artifact.symlink_to(source["candidate"])
    with pytest.raises(proposals.ProposalError):
        prepare(source, fixture)
    assert fixture.preparations == fixture.qualifications == 1


def test_existing_empty_directory_is_interrupted_not_a_fresh_attempt(source):
    source["proposal"].mkdir()
    fixture = Fixture()
    with pytest.raises(proposals.ProposalError, match="incomplete|interrupted"):
        prepare(source, fixture)
    assert fixture.preparations == fixture.qualifications == 0
    assert not list(source["proposal"].iterdir())


def test_immutable_request_cannot_be_repurposed(source):
    fixture = Fixture()
    prepare(source, fixture)
    before = snapshot(source["proposal"])
    with pytest.raises(proposals.ProposalError, match="another request"):
        prepare(source, fixture, objective="Different request")
    assert fixture.preparations == 1
    assert snapshot(source["proposal"]) == before


@pytest.mark.parametrize("dirty", ["working", "staged", "untracked", "ignored"])
def test_uncommitted_source_is_refused_before_generation(source, dirty):
    if dirty in {"working", "staged"}:
        (source["repo"] / "apps/games/counter.html").write_text(IMPROVED)
        if dirty == "staged":
            run_git(source["repo"], "add", "apps/games/counter.html")
    else:
        (source["repo"] / ("ignored-file" if dirty == "ignored" else "untracked.py")).write_text("x")
    fixture = Fixture()
    with pytest.raises(proposals.ProposalError, match="clean and committed"):
        prepare(source, fixture)
    assert fixture.preparations == fixture.qualifications == 0
    assert not source["proposal"].exists()


@pytest.mark.parametrize("flag", ["--assume-unchanged", "--skip-worktree"])
def test_hidden_source_modifications_are_refused(source, flag):
    run_git(source["repo"], "update-index", flag, "apps/games/counter.html")
    (source["repo"] / "apps/games/counter.html").write_text(IMPROVED)
    fixture = Fixture()
    with pytest.raises(proposals.ProposalError, match="index must not hide"):
        prepare(source, fixture)
    assert fixture.preparations == 0


def test_proposals_cannot_pollute_another_linked_worktree(source, tmp_path):
    linked = tmp_path / "linked-worktree"
    run_git(source["repo"], "worktree", "add", "-q", "-b", "linked", str(linked))
    source["proposal"] = linked / "proposal"
    with pytest.raises(proposals.ProposalError, match="linked worktrees"):
        prepare(source, Fixture())
    assert not source["proposal"].exists()


def test_stale_base_is_refused_and_preserves_prior_evidence(source):
    fixture = Fixture()
    prepare(source, fixture)
    before = snapshot(source["proposal"])
    run_git(source["repo"], "commit", "--allow-empty", "-qm", "base advanced")
    with pytest.raises(proposals.ProposalError, match="stale base"):
        prepare(source, fixture)
    assert snapshot(source["proposal"]) == before
    assert fixture.preparations == 1
    source["base"] = run_git(source["repo"], "rev-parse", "HEAD")
    with pytest.raises(proposals.ProposalError, match="source/base binding"):
        prepare(source, fixture)


def test_archived_proof_uses_historical_commit_not_current_checkout(source, monkeypatch):
    fixture = Fixture()
    first = prepare(source, fixture)
    (source["repo"] / "apps/games/counter.html").write_text("<html>New committed app</html>")
    run_git(source["repo"], "add", "apps/games/counter.html")
    run_git(source["repo"], "commit", "-qm", "advance current source")
    (source["repo"] / "apps/games/counter.html").write_text("<html>Dirty current app</html>")
    (source["repo"] / "untracked.py").write_text("not historical source")
    before_source, before_proposal = snapshot(source["repo"]), snapshot(source["proposal"])
    original_git = proposals.git

    def read_only(repo, *args, **kwargs):
        assert args[0] not in {"apply", "status", "ls-files", "add", "commit", "checkout"}
        return original_git(repo, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(proposals, "git", read_only)
        patch.setattr(proposals, "_adapter_identity", lambda: pytest.fail("current producer is not archived proof"))
        result = verify(source, fixture)
    assert result["candidate_commit"] == first["candidate_commit"]
    assert result["base_readiness"] == {"checked": False, "matches_required_base": None}
    assert snapshot(source["repo"]) == before_source
    assert snapshot(source["proposal"]) == before_proposal
    assert fixture.preparations == fixture.qualifications == 1
    with pytest.raises(proposals.ProposalError, match="stale base"):
        verify(source, fixture, require_current_base=True)
    with pytest.raises(proposals.ProposalError, match="stale base"):
        prepare(source, fixture)


def test_readiness_requires_clean_current_base_but_archive_verification_does_not(source):
    fixture = Fixture()
    prepare(source, fixture)
    ready = verify(source, fixture, require_current_base=True)
    assert ready["base_readiness"] == {"checked": True, "matches_required_base": True}
    (source["repo"] / "apps/games/counter.html").write_text(IMPROVED)
    assert verify(source, fixture)["status"] == "fixture_prepared"
    with pytest.raises(proposals.ProposalError, match="clean and committed"):
        verify(source, fixture, require_current_base=True)


def test_fresh_runner_reuses_portable_exact_request_cache_without_generation(source, tmp_path, monkeypatch):
    first = prepare(source, Fixture())
    fresh_repo = tmp_path / "fresh-checkout"
    fresh_proposal = tmp_path / "restored-exact-key-cache"
    fresh_candidate = tmp_path / "fresh-operator.html"
    run_git(tmp_path, "clone", "-q", "--no-local", str(source["repo"]), str(fresh_repo))
    shutil.copytree(source["proposal"], fresh_proposal)
    shutil.copyfile(source["candidate"], fresh_candidate)
    shutil.rmtree(source["repo"])
    shutil.rmtree(source["proposal"])
    source["candidate"].unlink()
    source.update(repo=fresh_repo, proposal=fresh_proposal, candidate=fresh_candidate)
    before_source, before_proposal = snapshot(fresh_repo), snapshot(fresh_proposal)
    for name in ("_stage_source", "_stage_package", "_worker"):
        monkeypatch.setattr(proposals, name, lambda *args, **kwargs: pytest.fail("restored cache must not regenerate"))
    fresh_process_fixture = Fixture()
    resumed = prepare(source, fresh_process_fixture)
    assert resumed == {**first, "noop": True}
    assert fresh_process_fixture.preparations == fresh_process_fixture.qualifications == 0
    assert fresh_process_fixture.verifications == 1
    assert snapshot(fresh_repo) == before_source
    assert snapshot(fresh_proposal) == before_proposal


def test_older_artifacts_can_bind_producer_through_historical_git_source(source, monkeypatch):
    for name in ("molter_capabilities.py", "molter_capability_worker.py"):
        (source["repo"] / "scripts" / name).write_bytes(Path(proposals.__file__).with_name(name).read_bytes())
    run_git(source["repo"], "add", "scripts")
    run_git(source["repo"], "commit", "-qm", "committed producing adapter")
    source["base"] = run_git(source["repo"], "rev-parse", "HEAD")
    fixture = Fixture()
    prepare(source, fixture)
    # Model the previous v1 layout, whose producer is committed but not separately exported.
    shutil.rmtree(source["proposal"] / "adapter")
    path = source["proposal"] / "receipt.json"
    receipt = json.loads(path.read_text())
    receipt["artifacts"] = proposals.inventory(source["proposal"])
    receipt["integrity_sha256"] = proposals.digest(proposals.json_bytes(
        {key: value for key, value in receipt.items() if key != "integrity_sha256"}))
    path.write_bytes(proposals.json_bytes(receipt))
    (source["repo"] / "scripts/molter_capabilities.py").write_text("# New unrelated current adapter\n")
    run_git(source["repo"], "add", "scripts/molter_capabilities.py")
    run_git(source["repo"], "commit", "-qm", "new adapter version")
    monkeypatch.setattr(proposals, "_adapter_identity", lambda: pytest.fail("do not require current producer bytes"))
    assert verify(source, fixture)["status"] == "fixture_prepared"


@pytest.mark.parametrize("target", ["../counter.html", "/counter.html", "apps/games/counter.html", "x\\counter.html"])
def test_unsafe_target_is_refused(source, target):
    with pytest.raises(proposals.ProposalError):
        prepare(source, Fixture(), target=target)
    assert not source["proposal"].exists()


@pytest.mark.parametrize("kind", ["inside_source", "output_symlink", "parent_symlink", "candidate_symlink", "world_writable"])
def test_output_and_input_path_safety(source, tmp_path, kind):
    if kind == "inside_source":
        source["proposal"] = source["repo"] / "proposal"
    elif kind == "output_symlink":
        destination = tmp_path / "elsewhere"
        destination.mkdir()
        source["proposal"].symlink_to(destination, target_is_directory=True)
    elif kind == "parent_symlink":
        link = tmp_path / "linked"
        link.symlink_to(tmp_path, target_is_directory=True)
        source["proposal"] = link / "proposal"
    elif kind == "candidate_symlink":
        link = tmp_path / "candidate-link"
        link.symlink_to(source["candidate"])
        source["candidate"] = link
    else:
        source["proposal"].mkdir(mode=0o777)
        source["proposal"].chmod(0o777)
    fixture = Fixture()
    with pytest.raises(proposals.ProposalError):
        prepare(source, fixture)
    assert fixture.preparations == fixture.qualifications == 0


@pytest.mark.parametrize("failure", ["failed", "rejected", "skipped", "empty", "unchanged", "metadata",
                                   "undeclared", "unsafe", "bad_hash", "missing_evidence", "unauthorized_model"])
def test_failed_empty_or_undeclared_candidate_never_qualifies(source, failure):
    def mutate(result, stage, request):
        if failure in {"failed", "rejected", "skipped"}:
            result.update(status=failure, reason="fixture declined", changes={})
        elif failure == "empty":
            result["changes"] = {}
        elif failure == "unchanged":
            result["changes"][request["app_path"]] = ORIGINAL
        elif failure == "metadata":
            result["changes"] = {"apps/manifest.json": "{}"}
        elif failure in {"undeclared", "unsafe"}:
            result["changes"]["apps/community.json" if failure == "undeclared" else "../escape.py"] = "{}"
        elif failure == "bad_hash":
            result["output_sha256"] = "0" * 64
        elif failure == "missing_evidence":
            result["evidence"] = {}
        else:
            result["model"].update(invoked=True, attempts=1)

    fixture = Fixture(mutate)
    result = prepare(source, fixture)
    assert result["status"] in {"failed", "rejected", "blocked"}, result
    assert not result["qualified"]
    assert fixture.qualifications == 0
    assert not (source["proposal"] / "candidate.bundle").exists()
    assert (source["proposal"] / "receipt.json").is_file()
    before = snapshot(source["proposal"])
    assert prepare(source, fixture)["noop"] is True
    assert fixture.preparations == 1
    assert snapshot(source["proposal"]) == before


def test_comment_and_html_metadata_only_changes_are_not_improvement(source):
    source["candidate"].write_text(ORIGINAL.replace("</head>", '<meta name="frame" content="1"></head>') + "<!-- frame 1 -->")
    fixture = Fixture()
    assert prepare(source, fixture)["status"] == "rejected"
    assert fixture.qualifications == 0


def test_snapshot_mutation_is_rejected_without_canonical_writes(source):
    before = snapshot(source["repo"])

    def mutate(result, stage, request):
        (stage / request["app_path"]).write_text(IMPROVED)

    fixture = Fixture(mutate)
    result = prepare(source, fixture)
    assert result["status"] == "rejected"
    assert "modified its source snapshot" in result["reason"]
    assert snapshot(source["repo"]) == before
    assert fixture.qualifications == 0


def test_precise_manifest_and_archive_deltas_are_preserved(source):
    def mutate(result, stage, request):
        manifest = json.loads((stage / "apps/manifest.json").read_text())
        app = manifest["categories"]["games"]["apps"][0]
        app.update(generation=1, lastMolted="2026-09-06",
                   moltHistory=[{"gen": 1, "date": "2026-09-06", "size": len(IMPROVED.encode())}])
        result["changes"].update({
            "apps/manifest.json": json.dumps(manifest),
            "apps/archive/counter/v0.html": ORIGINAL,
            "apps/archive/counter/molt-log.json": '[{"status":"prepared"}]',
        })

    result = prepare(source, Fixture(mutate))
    assert result["status"] == "fixture_prepared", result
    receipt = json.loads((source["proposal"] / "receipt.json").read_text())
    assert len(receipt["changes"]) == 4


def test_unrelated_manifest_changes_are_rejected(source):
    def mutate(result, stage, request):
        manifest = json.loads((stage / "apps/manifest.json").read_text())
        manifest["categories"]["games"]["apps"][1]["title"] = "Unrelated edit"
        result["changes"]["apps/manifest.json"] = json.dumps(manifest)

    fixture = Fixture(mutate)
    assert prepare(source, fixture)["status"] in {"rejected", "failed"}
    assert fixture.qualifications == 0


def test_explicit_model_permission_is_bounded_and_not_implicit(source):
    fixture = Fixture()
    result = prepare(source, fixture, candidate_file=None)
    assert result["status"] == "blocked"
    assert fixture.preparations == 0
    source["proposal"] = source["proposal"].with_name("model-fixture")
    result = prepare(source, fixture, candidate_file=None, allow_model=True)
    assert result["status"] == "fixture_prepared", result
    assert fixture.preparations == 1
    assert not result["qualified"]


def test_missing_real_package_does_not_fall_back_to_fixture(source, monkeypatch):
    monkeypatch.setattr(proposals, "_worker", lambda *args, **kwargs: pytest.fail("worker must not run"))
    result = prepare(source, None)
    assert result["status"] == "blocked", result
    assert result["qualification"] is None
    assert not result["qualified"]


def test_dry_run_is_read_only_and_uses_existing_selection_policy(source):
    fixture = Fixture()
    before = snapshot(source["repo"])
    result = prepare(source, fixture, dry_run=True)
    assert result["status"] == "dry_run"
    assert result["request"]["target"] == "counter.html"
    assert fixture.preparations == fixture.qualifications == 0
    assert snapshot(source["repo"]) == before
    assert not source["proposal"].exists()


def test_controller_dispatch_precedes_every_legacy_side_effect(source, monkeypatch, capsys):
    monkeypatch.setattr(autonomous_frame, "ROOT", source["repo"])
    for name in ("observe", "decide", "cleanup", "data_molt", "html_molt", "score", "socialize",
                 "broadcast", "poke_ghost", "log_frame", "publish", "run_script", "append_molter_frame"):
        monkeypatch.setattr(autonomous_frame, name, lambda *args, **kwargs: pytest.fail("legacy side effect"))
    before = snapshot(source["repo"])
    code = autonomous_frame.main([
        "--prepare-proposal", str(source["proposal"]), "--base", source["base"],
        "--repository", source["repository"], "--candidate-file", str(source["candidate"]),
        "--dry-run", "--skip-push", "--verbose",
    ])
    result = json.loads(capsys.readouterr().out)
    assert code == 0 and result["status"] == "dry_run"
    assert not source["proposal"].exists()
    assert snapshot(source["repo"]) == before


def test_cli_errors_are_machine_readable_and_not_publishing(source, capsys):
    code = proposals.main(["prepare", str(source["proposal"]), "--repo", str(source["repo"]),
                           "--base", source["base"], "--repository", source["repository"], "--publish"])
    captured = capsys.readouterr()
    assert code == 1 and json.loads(captured.out)["status"] == "blocked"
    assert captured.err
    assert not source["proposal"].exists()


def test_denied_delivery_cannot_destroy_or_promote_a_preserved_candidate(source, capsys):
    fixture = Fixture()
    assert prepare(source, fixture)["status"] == "fixture_prepared"
    before = snapshot(source["proposal"])
    code = proposals.main(["prepare", str(source["proposal"]), "--repo", str(source["repo"]),
                           "--base", source["base"], "--repository", source["repository"], "--publish"])
    assert code == 1 and json.loads(capsys.readouterr().out)["deployment_verified"] is False
    assert snapshot(source["proposal"]) == before
    assert fixture.preparations == fixture.qualifications == 1


def test_even_rehashed_receipt_cannot_assert_deployment(source):
    fixture = Fixture()
    prepare(source, fixture)
    path = source["proposal"] / "receipt.json"
    receipt = json.loads(path.read_text())
    receipt["deployment_verified"] = True
    receipt["integrity_sha256"] = proposals.digest(proposals.json_bytes(
        {key: value for key, value in receipt.items() if key != "integrity_sha256"}))
    path.write_bytes(proposals.json_bytes(receipt))
    with pytest.raises(proposals.ProposalError, match="cannot attest"):
        verify(source, fixture)


def test_real_controller_cli_dry_run_does_not_create_bytecode_or_other_state(source):
    script_root = Path(autonomous_frame.__file__).parent
    for name in ("autonomous_frame.py", "molter_capabilities.py", "molter_capability_worker.py", "organism_ledger.py"):
        (source["repo"] / "scripts" / name).write_bytes((script_root / name).read_bytes())
    run_git(source["repo"], "add", "scripts")
    run_git(source["repo"], "commit", "-qm", "committed controller under test")
    source["base"] = run_git(source["repo"], "rev-parse", "HEAD")
    before = snapshot(source["repo"])
    env = proposals.environment()
    env.pop("PYTHONDONTWRITEBYTECODE")
    completed = subprocess.run(
        [sys.executable, str(source["repo"] / "scripts/autonomous_frame.py"),
         "--prepare-proposal", str(source["proposal"]), "--base", source["base"],
         "--repository", source["repository"], "--candidate-file", str(source["candidate"]), "--dry-run"],
        cwd=source["repo"], env=env, capture_output=True, text=True, timeout=30,
    )
    assert completed.returncode == 0, completed.stderr + completed.stdout
    assert json.loads(completed.stdout)["status"] == "dry_run"
    assert snapshot(source["repo"]) == before
    assert not source["proposal"].exists()


def test_worker_timeout_preserves_bounded_failure_observation(source, monkeypatch):
    source["proposal"].mkdir()

    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired("fixture-worker", 1, output=b"partial result", stderr=b"failure evidence")

    monkeypatch.setattr(proposals.subprocess, "run", timeout)
    with pytest.raises(proposals.ProposalError, match="timed out"):
        proposals._worker("candidate", source["proposal"], source["proposal"] / "request.json", timeout=1)
    observation = json.loads((source["proposal"] / "diagnostics/candidate.json").read_text())
    assert observation["timed_out"] is True and observation["exit_code"] is None
    assert (source["proposal"] / observation["stderr"]["path"]).read_bytes() == b"failure evidence"
    assert not (source["proposal"] / "check-work").exists()


def test_late_verification_failure_never_writes_a_prepared_receipt(source):
    class FailingVerification(Fixture):
        def verify(self, proposal, context):
            raise proposals.ProposalError("fixture verification refused", "failed")

    fixture = FailingVerification()
    result = prepare(source, fixture)
    assert result["status"] == "failed" and result["qualified"] is False
    receipt = json.loads((source["proposal"] / "receipt.json").read_text())
    assert receipt["status"] == "failed"
    assert (source["proposal"] / "proposal.patch").is_file()
    assert (source["proposal"] / "candidate.bundle").is_file()
    assert prepare(source, fixture)["noop"] is True
    assert fixture.preparations == fixture.qualifications == 1


@pytest.fixture
def package_shape(monkeypatch):
    """A shape-only fixture, never executable qualification evidence."""
    artifacts = [
        "scripts/capability_package.py", "scripts/capability_contracts.py", "scripts/autocomplete_catalog.py",
        "scripts/autocomplete_frames.py", "tests/test_capability_package.py", "tests/test_capability_contracts.py",
    ]
    files = {name: b"shape fixture\n" for name in
             set(artifacts) | proposals.PACKAGE_SUPPORT | {"scripts/capability_registry.py"}}
    files[proposals.PIN] = proposals.json_bytes({
        "commit": proposals.RAPP_COMMIT,
        "files": {name: proposals.digest(files[proposals.REFERENCE + "/" + name])
                  for name in ("rapp.py", "rapp_check.py", "SPEC.md")},
    })
    files[proposals.MANIFEST] = proposals.json_bytes({
        "id": "source-capsule", "version": "1.0.3", "reuses": [],
        "artifacts": [{"path": name, "sha256": proposals.digest(files[name]), "bytes": len(files[name])}
                      for name in artifacts],
    })
    monkeypatch.setattr(proposals, "MANIFEST_SHA256", proposals.digest(files[proposals.MANIFEST]))
    monkeypatch.setattr(proposals, "blob", lambda repo, base, name, **kwargs:
                        (files[name[len(proposals.PACKAGE) + 1:]], "100644"))

    def listing(repo, *args, **kwargs):
        assert args[:4] == ("ls-tree", "-r", "--name-only", "-z")
        return b"\0".join((proposals.PACKAGE + "/" + name).encode() for name in files) + b"\0"

    monkeypatch.setattr(proposals, "git", listing)
    return files


def test_complete_package_and_bundled_reference_are_preserved(package_shape):
    copied = proposals._package_inputs(Path("."), "a" * 40, None)
    assert copied == package_shape
    assert len(copied) == 26
    assert "vendor/rapp-1/LICENSE" in copied
    assert "scripts/__init__.py" in copied and "tests/__init__.py" in copied


@pytest.mark.parametrize("change", ["missing", "undeclared"])
def test_package_inputs_refuse_partial_or_undeclared_bootstrap_files(package_shape, change):
    if change == "missing":
        del package_shape["scripts/__init__.py"]
    else:
        package_shape["sitecustomize.py"] = b"# Not part of the bounded package.\n"
    with pytest.raises(proposals.ProposalError, match="missing or undeclared"):
        proposals._package_inputs(Path("."), "a" * 40, None)


def test_external_reference_cannot_override_the_bundled_pin(package_shape, tmp_path):
    reference = tmp_path / "reference"
    reference.mkdir()
    for name in ("rapp.py", "rapp_check.py", "SPEC.md"):
        (reference / name).write_bytes(package_shape[proposals.REFERENCE + "/" + name])
    assert proposals._package_inputs(Path("."), "a" * 40, reference) == package_shape
    (reference / "rapp.py").write_bytes(b"different reference")
    with pytest.raises(proposals.ProposalError, match="external RAPP reference differs"):
        proposals._package_inputs(Path("."), "a" * 40, reference)


@pytest.mark.parametrize("location", ["vendor/rapp-1", "reference"])
def test_worker_preflight_supports_bundled_and_legacy_reference_paths(tmp_path, monkeypatch, location):
    (tmp_path / "capability" / location).mkdir(parents=True)
    observed = []
    monkeypatch.setattr(sys, "path", list(sys.path))
    monkeypatch.setitem(sys.modules, "autocomplete_frames", SimpleNamespace(
        Reference=lambda path: observed.append(path) or SimpleNamespace(identity={"test_fixture": True}),
    ))
    monkeypatch.setitem(sys.modules, "capability_contracts", SimpleNamespace(
        load_manifest=lambda *args: ({}, capability_worker.MANIFEST_SHA256),
        require=proposals.require,
    ))
    monkeypatch.setitem(sys.modules, "capability_registry", SimpleNamespace(load_inventory=lambda *args, **kwargs: ({}, {})))
    monkeypatch.setitem(sys.modules, "capability_package", SimpleNamespace(pack_sources=lambda *args: observed.append(args)))
    request = {"base_commit": "a" * 40, "repository": "fixture/molter", "app_path": "apps/fixture.html"}
    result = capability_worker.capability(tmp_path, request, "preflight")
    assert observed == [tmp_path / "capability" / location,
                        (tmp_path / "source", "a" * 40, "fixture/molter", ["apps/fixture.html"])]
    assert result["reference"] == {"test_fixture": True}
    assert "qualified" not in result

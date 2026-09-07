"""Adapter contract tests; the explicit fixture is NOT RAPP qualification."""

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import shutil
import subprocess
import sys
import threading
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


def test_concurrent_identical_preparation_admits_only_one_generator(source):
    entered, release = threading.Event(), threading.Event()

    class SlowFixture(Fixture):
        def prepare(self, stage, request, supplied):
            result = super().prepare(stage, request, supplied)
            entered.set()
            assert release.wait(30), "test must release the admitted caller"
            return result

    admitted, competing = SlowFixture(), Fixture()
    with ThreadPoolExecutor(max_workers=1) as pool:
        running = pool.submit(prepare, source, admitted)
        try:
            assert entered.wait(30)
            with pytest.raises(proposals.ProposalError, match="in progress") as error:
                prepare(source, competing)
            assert error.value.status == "blocked"
            assert error.value.recovery["state"] == "in_progress"
            assert error.value.recovery["automatic_retry"] is False
            assert competing.preparations == competing.qualifications == 0
        finally:
            release.set()
        result = running.result(timeout=30)
    assert result["status"] == "fixture_prepared", result
    assert admitted.preparations == admitted.qualifications == 1
    assert prepare(source, competing)["noop"] is True
    assert competing.preparations == competing.qualifications == 0


def test_atomic_directory_admission_handles_simultaneous_creators(source, monkeypatch):
    original_mkdir = Path.mkdir
    barrier = threading.Barrier(2)

    def race(path, *args, **kwargs):
        if path == source["proposal"] and not kwargs.get("exist_ok") and not kwargs.get("parents"):
            barrier.wait(timeout=30)
        return original_mkdir(path, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", race)
    fixtures = [Fixture(), Fixture()]

    def run(fixture):
        try:
            return prepare(source, fixture)
        except proposals.ProposalError as exc:
            assert exc.status == "blocked"
            return {"status": "blocked", "recovery": exc.recovery}

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run, fixtures))
    assert sum(fixture.preparations for fixture in fixtures) == 1
    assert sum(fixture.qualifications for fixture in fixtures) == 1
    assert any(result["status"] == "fixture_prepared" for result in results)


def test_interrupted_attempt_is_retained_and_never_automatically_regenerated(source):
    class InterruptedFixture(Fixture):
        def prepare(self, stage, request, supplied):
            self.preparations += 1
            raise KeyboardInterrupt("injected interruption")

    interrupted = InterruptedFixture()
    with pytest.raises(KeyboardInterrupt):
        prepare(source, interrupted)
    assert not (source["proposal"] / "receipt.json").exists()
    assert not (source["proposal"] / "source").exists()
    assert (source["proposal"] / "progress/candidate-started.json").is_file()
    retained = snapshot(source["proposal"])
    resumed = Fixture()
    with pytest.raises(proposals.ProposalError, match="interrupted") as error:
        prepare(source, resumed)
    assert error.value.recovery == {
        "state": "interrupted_or_incomplete", "automatic_retry": False, "evidence_preserved": True,
        "exportable": False, "staging_retained": False,
        "candidate_execution": "may_have_run", "next_step": "inspect retained evidence; do not rerun this directory",
    }
    assert snapshot(source["proposal"]) == retained
    assert resumed.preparations == resumed.qualifications == 0


def test_cli_reports_recovery_state_without_claiming_or_retrying_a_proposal(source, capsys):
    class InterruptedFixture(Fixture):
        def prepare(self, *args):
            raise KeyboardInterrupt("injected interruption")

    with pytest.raises(KeyboardInterrupt):
        prepare(source, InterruptedFixture())
    before = snapshot(source["proposal"])
    code = proposals.main([
        "status", str(source["proposal"]), "--repo", str(source["repo"]),
        "--base", source["base"], "--repository", source["repository"],
    ])
    result = json.loads(capsys.readouterr().out)
    assert code == 1 and result["status"] == "blocked"
    assert result["qualified"] is False and result["deployment_verified"] is False
    assert result["recovery"]["state"] == "interrupted_or_incomplete"
    assert result["recovery"]["automatic_retry"] is False
    assert result["recovery"]["exportable"] is False
    assert snapshot(source["proposal"]) == before


def test_process_death_releases_local_lock_but_never_restarts_generation(source):
    code = """
import os, sys
sys.path.insert(0, sys.argv[1])
import molter_capabilities as proposals
class Interrupted:
    identity = 'unit-tests-not-rapp-v1'
    def prepare(self, *args):
        os._exit(23)
proposals.prepare_proposal(
    sys.argv[2], repo=sys.argv[3], base=sys.argv[4], repository='fixture/molter',
    candidate_file=sys.argv[5], _fixture=Interrupted(),
)
"""
    completed = subprocess.run(
        [sys.executable, "-B", "-c", code, str(Path(proposals.__file__).parent), str(source["proposal"]),
         str(source["repo"]), source["base"], str(source["candidate"])],
        env=proposals.environment(), capture_output=True, timeout=30,
    )
    assert completed.returncode == 23, completed.stderr
    assert not proposals._attempt_active(source["proposal"])
    before = snapshot(source["proposal"])
    fixture = Fixture()
    with pytest.raises(proposals.ProposalError, match="interrupted") as error:
        prepare(source, fixture)
    assert error.value.recovery["candidate_execution"] == "may_have_run"
    assert error.value.recovery["staging_retained"] is True
    assert error.value.recovery["exportable"] is False
    assert fixture.preparations == fixture.qualifications == 0
    assert snapshot(source["proposal"]) == before


def test_artifact_write_publishes_complete_bytes_without_overwrite(tmp_path, monkeypatch):
    path = tmp_path / "artifact.json"
    link = proposals.os.link
    observed = []

    def publish(source, destination):
        assert not Path(destination).exists()
        observed.append(Path(source).read_bytes())
        link(source, destination)

    monkeypatch.setattr(proposals.os, "link", publish)
    proposals.write_new(path, b'{"complete":true}\n')
    assert observed == [b'{"complete":true}\n']
    assert path.read_bytes() == observed[0]
    monkeypatch.setattr(proposals.os, "link", link)
    with pytest.raises(FileExistsError):
        proposals.write_new(path, b"replacement")
    assert path.read_bytes() == observed[0]
    assert list(tmp_path.iterdir()) == [path]


def test_atomic_write_never_removes_a_preexisting_pending_file(tmp_path, monkeypatch):
    pending = tmp_path / ".pending-occupied"
    pending.write_bytes(b"preexisting evidence")
    monkeypatch.setattr(proposals.uuid, "uuid4", lambda: SimpleNamespace(hex="occupied"))
    with pytest.raises(FileExistsError):
        proposals.write_new(tmp_path / "new.json", b"new work")
    assert pending.read_bytes() == b"preexisting evidence"
    assert not (tmp_path / "new.json").exists()


def test_missing_proposal_does_not_claim_retained_evidence(source):
    with pytest.raises(proposals.ProposalError) as error:
        verify(source, Fixture())
    assert error.value.recovery["evidence_preserved"] is False
    assert not source["proposal"].exists()


@pytest.mark.parametrize("name", [
    "proposal.patch", "candidate.bundle", "candidate-result.json", "request.json",
    "receipt.json", "fixture-evidence.json", "qualification-context.json",
    "changes/apps/games/counter.html", "candidate-input.html",
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
        manifest_before = (stage / "apps/manifest.json").read_bytes()
        manifest = json.loads((stage / "apps/manifest.json").read_text())
        app = manifest["categories"]["games"]["apps"][0]
        app.update(generation=1, lastMolted="2026-09-06",
                   moltHistory=[{"gen": 1, "date": "2026-09-06", "size": len(IMPROVED.encode())}])
        result["changes"].update({
            "apps/manifest.json": json.dumps(manifest),
            "apps/archive/counter/v1.html": ORIGINAL,
            "apps/archive/counter/molt-log.json": '[{"status":"prepared"}]',
        })
        result["evidence"]["base_sha256"] = {
            request["app_path"]: result["input_sha256"],
            "apps/manifest.json": proposals.digest(manifest_before),
            "apps/archive/counter/v1.html": None,
            "apps/archive/counter/molt-log.json": None,
        }

    result = prepare(source, Fixture(mutate))
    assert result["status"] == "fixture_prepared", result
    receipt = json.loads((source["proposal"] / "receipt.json").read_text())
    assert len(receipt["changes"]) == 4


@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_archive_and_candidate_preserve_legacy_whitespace_and_line_endings(source, newline):
    original = (ORIGINAL.rstrip("\n") + "  \n\n").replace("\n", newline)
    improved = (IMPROVED.rstrip("\n") + "  \n\n").replace("\n", newline)
    (source["repo"] / "apps/games/counter.html").write_bytes(original.encode())
    source["candidate"].write_bytes(improved.encode())
    run_git(source["repo"], "add", "apps/games/counter.html")
    run_git(source["repo"], "commit", "-qm", "legacy exact-byte whitespace")
    source["base"] = run_git(source["repo"], "rev-parse", "HEAD")

    def mutate(result, stage, request):
        result["changes"]["apps/archive/counter/v1.html"] = original

    result = prepare(source, Fixture(mutate))
    assert result["status"] == "fixture_prepared", result
    assert (source["proposal"] / "changes/apps/archive/counter/v1.html").read_bytes() == original.encode()
    assert (source["proposal"] / "changes/apps/games/counter.html").read_bytes() == improved.encode()


@pytest.mark.parametrize("generation,fault", [
    (0, None), (2, None), (0, "wrong_date"), (0, "unrelated_metadata"), (0, "wrong_archive"),
])
def test_legacy_candidate_generation_size_and_manifest_refresh_conventions(source, generation, fault):
    manifest_path = source["repo"] / "apps/manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["categories"]["games"]["apps"][0]["generation"] = generation
    manifest["meta"] = {"lastUpdated": "2020-01-01", "preserved": "value"}
    manifest_path.write_text(json.dumps(manifest))
    run_git(source["repo"], "add", "apps/manifest.json")
    run_git(source["repo"], "commit", "-qm", "legacy generation fixture")
    source["base"] = run_git(source["repo"], "rev-parse", "HEAD")
    html = IMPROVED.replace("Add one", "Add one ✓")
    source["candidate"].write_text(html, encoding="utf-8")
    next_generation = generation + 1
    archive = f"apps/archive/counter/v{generation if fault == 'wrong_archive' else next_generation}.html"

    def mutate(result, stage, request):
        manifest_bytes = (stage / "apps/manifest.json").read_bytes()
        updated = json.loads(manifest_bytes)
        app = updated["categories"]["games"]["apps"][0]
        app.update(generation=next_generation, lastMolted="2026-09-06", moltHistory=[
            {"gen": next_generation, "date": "2026-09-06", "size": len(html)},
        ])
        updated["meta"]["lastUpdated"] = "2026-09-06" if fault != "wrong_date" else "2020-02-02"
        if fault == "unrelated_metadata":
            updated["meta"]["preserved"] = "unrelated mutation"
        result["changes"].update({
            "apps/manifest.json": json.dumps(updated),
            archive: ORIGINAL,
            "apps/archive/counter/molt-log.json": json.dumps([{"generation": next_generation}]),
        })
        result["evidence"].update(base_unchanged=True, base_sha256={
            request["app_path"]: result["input_sha256"], "apps/manifest.json": proposals.digest(manifest_bytes),
            archive: None, "apps/archive/counter/molt-log.json": None,
        })

    fixture = Fixture(mutate)
    result = prepare(source, fixture, target="counter.html")
    if fault is not None:
        assert result["status"] == "rejected", result
        assert fixture.qualifications == 0
    else:
        assert result["status"] == "fixture_prepared", result
        staged_manifest = json.loads((source["proposal"] / "changes/apps/manifest.json").read_text())
        history = staged_manifest["categories"]["games"]["apps"][0]["moltHistory"]
        assert history[-1]["size"] == len(html) != len(html.encode("utf-8"))
        assert (source["proposal"] / "changes" / archive).read_text() == ORIGINAL
        assert verify(source, fixture)["status"] == "fixture_prepared"


@pytest.mark.parametrize("omitted", [None, "manifest", "log", "archive", "refresh"])
def test_real_result_validation_requires_complete_history_deltas(source, omitted):
    target, app_path, manifest, category, app, original = proposals.select_app(source["repo"], source["base"], "counter.html")
    request = {"target": target, "app_path": app_path, "base_commit": source["base"],
               "objective": proposals.DEFAULT_OBJECTIVE, "candidate_sha256": proposals.digest(IMPROVED.encode()),
               "allow_model": False, "timeout_seconds": 180, "fixture": None}
    # Shape-only boundary data: this test does not run or assert RAPP qualification.
    result = Fixture().prepare(source["repo"], request, IMPROVED.encode())
    updated = json.loads(json.dumps(manifest))
    updated["categories"]["games"]["apps"][0].update(
        generation=1, lastMolted="2026-09-06",
        moltHistory=[{"gen": 1, "date": "2026-09-06", "size": len(IMPROVED)}],
    )
    if omitted != "refresh":
        updated["meta"] = {"lastUpdated": "2026-09-06"}
    result["changes"].update({
        "apps/manifest.json": json.dumps(updated),
        "apps/archive/counter/v1.html": ORIGINAL,
        "apps/archive/counter/molt-log.json": '[{"generation":1}]',
    })
    path = {"manifest": "apps/manifest.json", "archive": "apps/archive/counter/v1.html",
            "log": "apps/archive/counter/molt-log.json"}.get(omitted)
    if path:
        del result["changes"][path]
    if omitted is not None:
        with pytest.raises(proposals.ProposalError):
            proposals.validate_candidate(result, source["repo"], request, manifest, category, app, original)
    else:
        _, records = proposals.validate_candidate(result, source["repo"], request, manifest, category, app, original)
        assert len(records) == 4


@pytest.mark.parametrize("mismatch", ["missing_path", "wrong_hash", "wrong_absence", "extra_path", "wrong_type"])
def test_candidate_base_evidence_must_match_exact_committed_destinations(source, mismatch):
    def mutate(result, stage, request):
        expected = {request["app_path"]: result["input_sha256"]}
        if mismatch == "missing_path":
            expected = {}
        elif mismatch == "wrong_hash":
            expected[request["app_path"]] = "0" * 64
        elif mismatch == "wrong_absence":
            expected[request["app_path"]] = None
        elif mismatch == "extra_path":
            expected["apps/community.json"] = None
        else:
            expected = []
        result["evidence"]["base_sha256"] = expected

    fixture = Fixture(mutate)
    result = prepare(source, fixture)
    assert result["status"] == "rejected"
    assert "base expectations" in result["reason"]
    assert fixture.qualifications == 0


@pytest.mark.parametrize("archive_body", [ORIGINAL, "<html>Conflicting archive</html>", None])
def test_base_evidence_can_include_only_an_identical_unchanged_original_archive(source, archive_body):
    archive = "apps/archive/counter/v1.html"
    if archive_body is not None:
        (source["repo"] / archive).parent.mkdir(parents=True)
        (source["repo"] / archive).write_text(archive_body)
        run_git(source["repo"], "add", archive)
        run_git(source["repo"], "commit", "-qm", "legacy rollback archive residue")
        source["base"] = run_git(source["repo"], "rev-parse", "HEAD")

    def mutate(result, stage, request):
        result["evidence"].update(base_unchanged=True, base_sha256={
            request["app_path"]: result["input_sha256"],
            archive: proposals.digest(archive_body.encode()) if archive_body is not None else None,
        })

    fixture = Fixture(mutate)
    result = prepare(source, fixture)
    if archive_body == ORIGINAL:
        assert result["status"] == "fixture_prepared", result
        receipt = json.loads((source["proposal"] / "receipt.json").read_text())
        assert archive not in {item["path"] for item in receipt["changes"]}
        assert verify(source, fixture)["status"] == "fixture_prepared"
    else:
        assert result["status"] == "rejected"
        assert "unchanged archive evidence" in result["reason"]
        assert fixture.qualifications == 0


def test_explicitly_unstable_candidate_base_cannot_qualify(source):
    fixture = Fixture(lambda result, stage, request: result["evidence"].update(base_unchanged=False))
    result = prepare(source, fixture)
    assert result["status"] == "rejected" and fixture.qualifications == 0
    assert "base snapshot was not stable" in result["reason"]


def test_preparation_cannot_replace_an_operator_reviewed_candidate(source):
    def mutate(result, stage, request):
        altered = IMPROVED.replace("Add", "Subtract")
        result["changes"][request["app_path"]] = altered
        result["output_sha256"] = proposals.digest(altered.encode())

    fixture = Fixture(mutate)
    result = prepare(source, fixture)
    assert result["status"] == "rejected"
    assert "operator-supplied candidate" in result["reason"]
    assert fixture.qualifications == 0


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

    monkeypatch.setattr(proposals, "run_isolated", timeout)
    with pytest.raises(proposals.ProposalError, match="timed out"):
        proposals._worker("candidate", source["proposal"], source["proposal"] / "request.json", timeout=1)
    observation = json.loads((source["proposal"] / "diagnostics/candidate.json").read_text())
    assert observation["timed_out"] is True and observation["exit_code"] is None
    assert (source["proposal"] / observation["stderr"]["path"]).read_bytes() == b"failure evidence"
    assert not (source["proposal"] / "check-work").exists()


@pytest.mark.parametrize("action", ["preflight", "qualify"])
def test_capability_worker_uses_implementation_local_scratch(source, monkeypatch, action):
    (source["proposal"] / "capability").mkdir(parents=True)
    expected = str(source["proposal"] / "capability/check-work")

    def run(*args, **kwargs):
        assert all(kwargs["env"][key] == expected for key in ("TMPDIR", "TMP", "TEMP"))
        assert Path(expected).is_dir()
        return SimpleNamespace(returncode=0, stdout=b'{"test_fixture":true}', stderr=b"")

    monkeypatch.setattr(proposals, "run_isolated", run)
    assert proposals._worker(action, source["proposal"], source["proposal"] / "context.json") == {"test_fixture": True}
    assert not Path(expected).exists()


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
    monkeypatch.setattr(proposals, "PIN_SHA256", proposals.digest(files[proposals.PIN]))
    monkeypatch.setattr(proposals, "REGISTRY_SHA256", proposals.digest(files["scripts/capability_registry.py"]))
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


@pytest.mark.parametrize("changed", [proposals.PIN, "scripts/capability_registry.py"])
def test_package_reference_and_registry_pins_cannot_be_redefined(package_shape, changed):
    package_shape[changed] += b"\n"
    with pytest.raises(proposals.ProposalError, match="pin.*differs|implementation differs"):
        proposals._package_inputs(Path("."), "a" * 40, None)


@pytest.mark.parametrize("extra", ["__pycache__", "capability_registry.pyc", "selectors.py"])
def test_archived_import_guard_refuses_extra_modules_and_bytecode(package_shape, tmp_path, extra):
    root = tmp_path / "capability"
    for name, body in package_shape.items():
        proposals.write_new(root / name, body)
    proposals.verify_implementation_inputs(root)
    if extra == "__pycache__":
        (root / "scripts" / extra).mkdir()
    else:
        (root / "scripts" / extra).write_text("raise AssertionError('untrusted module')\n")
    with pytest.raises(proposals.ProposalError, match="undeclared implementation modules"):
        proposals.verify_implementation_inputs(root)


def test_worker_rejects_unpinned_code_before_import(package_shape, tmp_path):
    for name, body in package_shape.items():
        proposals.write_new(tmp_path / "capability" / name, body)
    (tmp_path / "capability/scripts/capability_registry.py").write_text(
        "raise AssertionError('must never be executed')\n"
    )
    with pytest.raises(proposals.ProposalError, match="pinned registry implementation differs"):
        capability_worker.capability(tmp_path, {}, "preflight")


@pytest.mark.parametrize("location", ["vendor/rapp-1", "reference"])
def test_worker_preflight_supports_bundled_and_legacy_reference_paths(tmp_path, monkeypatch, location):
    (tmp_path / "capability" / location).mkdir(parents=True)
    observed = []
    monkeypatch.setattr(sys, "path", list(sys.path))
    monkeypatch.setattr(proposals, "verify_implementation_inputs", lambda root: None)
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

"""Tests for Agent World's Fair release provenance verification."""

import copy
import io
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import agent_world_fair as fair
import organism_ledger
import verify_agent_fair_release_attestation as verifier


EXPECTED_BOOTSTRAP_PATHS = {
    ".github/CODEOWNERS",
    ".github/workflows/agent-fair-release-attestation.yml",
    ".github/workflows/agent-fair-release.yml",
    ".well-known/agent-protocol",
    ".well-known/feeddata-toc",
    ".well-known/mcp.json",
    ".well-known/rappterzoo-syndication",
    "apps/3d-immersive/agent-worlds-fair-sw.js",
    "apps/3d-immersive/agent-worlds-fair.html",
    "apps/agent-fair/agent-contract.json",
    "apps/agent-fair/district.json",
    "apps/agent-fair/events.jsonl",
    "apps/agent-fair/fair-state.json",
    "apps/agent-fair/release-candidate.json",
    "apps/feed.json",
    "apps/feed.xml",
    "apps/manifest.json",
    "docs/AGENT-WORLDS-FAIR.md",
    "scripts/agent_fair_gate.py",
    "scripts/agent_park_gate.py",
    "scripts/agent_world_fair.py",
    "scripts/build_syndication.py",
    "scripts/moonshot_gate.py",
    "scripts/rappterzoo_mcp.py",
    "scripts/rappterzoo_sync.py",
    "scripts/tests/test_agent_fair_gate.py",
    "scripts/tests/test_agent_park_gate.py",
    "scripts/tests/test_agent_world_fair.py",
    "scripts/tests/test_observatory_security.py",
    "scripts/tests/test_rappterzoo_mcp.py",
    "scripts/tests/test_syndication.py",
    "scripts/tests/test_verify_agent_fair_release_attestation.py",
    "scripts/verify_agent_fair_release_attestation.py",
    "skill.json",
    "skill.md",
}


def test_cross_origin_redirect_strips_authorization():
    request = urllib.request.Request(
        "https://api.github.com/repos/example/project/actions/artifacts/1/zip",
        headers={"Authorization": "Bearer secret"},
    )
    redirected = verifier._SafeRedirectHandler().redirect_request(
        request,
        None,
        302,
        "Found",
        {},
        "https://artifact.example.test/release.zip",
    )
    assert redirected is not None
    assert redirected.get_header("Authorization") is None


def test_same_origin_redirect_retains_authorization():
    request = urllib.request.Request(
        "https://api.github.com/repos/example/project/actions/artifacts/1/zip",
        headers={"Authorization": "Bearer secret"},
    )
    redirected = verifier._SafeRedirectHandler().redirect_request(
        request,
        None,
        302,
        "Found",
        {},
        "https://api.github.com/repositories/1/actions/artifacts/1/zip",
    )
    assert redirected is not None
    assert redirected.get_header("Authorization") == "Bearer secret"


def test_non_https_redirect_is_rejected():
    request = urllib.request.Request(
        "https://api.github.com/repos/example/project/actions/artifacts/1/zip",
        headers={"Authorization": "Bearer secret"},
    )
    with pytest.raises(verifier.AttestationError, match="not HTTPS"):
        verifier._SafeRedirectHandler().redirect_request(
            request,
            None,
            302,
            "Found",
            {},
            "http://artifact.example.test/release.zip",
        )


@pytest.fixture
def scratch_dir():
    path = ROOT / ".agent-fair-attestation-test-work"
    shutil.rmtree(path, ignore_errors=True)
    path.mkdir()
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def _run(root, *arguments):
    process = subprocess.run(
        list(arguments),
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
    )
    assert process.returncode == 0, process.stderr
    return process.stdout.strip()


def _copy_release_tree(root):
    for relative in (
        "apps/agent-park/park-state.json",
        "apps/agent-park/events.jsonl",
        "apps/organism-frames.jsonl",
        "apps/organism-frames.json",
        "apps/manifest.json",
        "apps/agent-fair/events.jsonl",
        "apps/agent-fair/fair-state.json",
        "apps/agent-fair/agent-contract.json",
        "apps/agent-fair/district.json",
        "apps/agent-fair/release-candidate.json",
    ):
        source = ROOT / relative
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def _release_utc(root):
    frames = organism_ledger.read_frames(
        root / "apps" / "organism-frames.jsonl"
    )
    return (
        datetime.strptime(
            frames[-1]["utc"],
            "%Y-%m-%dT%H:%M:%S.%fZ",
        ).replace(tzinfo=timezone.utc)
        + timedelta(minutes=1)
    ).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _approval_evidence():
    return {
        "actor": "customer-operator",
        "attestation_sha256": "a" * 64,
        "aud": fair.OIDC_AUDIENCE,
        "environment": fair.OIDC_ENVIRONMENT,
        "event_name": fair.OIDC_EVENT_NAME,
        "exp": 2_000_000_300,
        "iss": fair.OIDC_ISSUER,
        "nbf": 1_999_999_990,
        "ref": fair.OIDC_REF,
        "repository": fair.OIDC_REPOSITORY,
        "run_id": "123456789",
        "workflow_ref": fair.OIDC_WORKFLOW_REF,
    }


def _release_repo(scratch_dir):
    root = scratch_dir / "repo"
    _copy_release_tree(root)
    _run(root, "git", "init", "-q")
    _run(root, "git", "config", "user.name", "attestation-test")
    _run(root, "git", "config", "user.email", "attestation@example.invalid")
    _run(root, "git", "add", "apps")
    _run(root, "git", "commit", "-q", "-m", "base")
    base_sha = _run(root, "git", "rev-parse", "HEAD")

    candidate = fair._load_json(
        root / "apps" / "agent-fair" / "release-candidate.json"
    )
    payload = fair._render_release_frame_payload(
        candidate,
        _approval_evidence(),
    )
    frame = organism_ledger.append_frame(
        "zoo.observation",
        payload,
        utc=_release_utc(root),
        ledger_path=root / "apps" / "organism-frames.jsonl",
        projection_path=root / "apps" / "organism-frames.json",
    )
    _run(
        root,
        "git",
        "checkout",
        "-q",
        "-b",
        "release/agent-fair-123456789",
    )
    _run(
        root,
        "git",
        "add",
        "apps/organism-frames.jsonl",
        "apps/organism-frames.json",
    )
    _run(root, "git", "commit", "-q", "-m", "release")
    head_sha = _run(root, "git", "rev-parse", "HEAD")
    attestation = verifier.build_release_attestation(
        candidate,
        frame,
        base_sha,
        head_sha,
    )
    return {
        "attestation": attestation,
        "base_sha": base_sha,
        "candidate": candidate,
        "frame": frame,
        "head_sha": head_sha,
        "root": root,
    }


def _bootstrap_repo(scratch_dir):
    root = scratch_dir / "bootstrap-repo"
    _copy_release_tree(root)
    for relative in EXPECTED_BOOTSTRAP_PATHS:
        destination = root / relative
        if destination.is_file():
            destination.unlink()
    shutil.rmtree(root / "apps" / "agent-fair", ignore_errors=True)
    _run(root, "git", "init", "-q")
    _run(root, "git", "config", "user.name", "bootstrap-test")
    _run(root, "git", "config", "user.email", "bootstrap@example.invalid")
    _run(root, "git", "add", "apps")
    _run(root, "git", "commit", "-q", "-m", "base without verifier")
    base_sha = _run(root, "git", "rev-parse", "HEAD")
    _run(root, "git", "checkout", "-q", "-b", "feature/bootstrap-verifier")
    for relative in sorted(EXPECTED_BOOTSTRAP_PATHS):
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, destination)
    _run(root, "git", "add", ".")
    _run(root, "git", "commit", "-q", "-m", "install release verifier")
    return {
        "base_sha": base_sha,
        "head_sha": _run(root, "git", "rev-parse", "HEAD"),
        "root": root,
    }


def _run_bootstrap_workflow(case, head_ref):
    workflow = (
        ROOT
        / ".github"
        / "workflows"
        / "agent-fair-release-attestation.yml"
    ).read_text(encoding="utf-8")
    marker = (
        "      - name: Bootstrap verifier installation "
        "without release authority\n"
    )
    section = workflow.split(marker, 1)[1]
    script = section.split("        run: |\n", 1)[1]
    script = "\n".join(
        line[10:]
        for line in script.splitlines()
        if not line or line.startswith("          ")
    )
    environment = os.environ.copy()
    environment.update(
        {
            "BASE_SHA": case["base_sha"],
            "HEAD_REF": head_ref,
            "HEAD_SHA": case["head_sha"],
        }
    )
    return subprocess.run(
        ["bash", "-c", script],
        cwd=str(case["root"]),
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def _artifact_zip(value, extra=False):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            verifier.ATTESTATION_FILE,
            fair._pretty_bytes(value),
        )
        if extra:
            archive.writestr("unexpected.json", b"{}\n")
    return output.getvalue()


class FakeApi:
    def __init__(self, values, archive):
        self.values = copy.deepcopy(values)
        self.archive = archive
        self.calls = []

    def get_json(self, path):
        self.calls.append(("json", path))
        value = self.values[path]
        if isinstance(value, list):
            if len(value) > 1:
                return copy.deepcopy(value.pop(0))
            return copy.deepcopy(value[0])
        return copy.deepcopy(value)

    def get_bytes(self, path):
        self.calls.append(("bytes", path))
        return self.archive


def _api_values(case, branch="release/agent-fair-123456789"):
    repository = fair.OIDC_REPOSITORY
    run_id = branch.rsplit("-", 1)[-1]
    return {
        "/repos/{}/pulls/17".format(repository): {
            "base": {"ref": "main", "sha": case["base_sha"]},
            "head": {
                "ref": branch,
                "repo": {"full_name": repository},
                "sha": case["head_sha"],
            },
            "number": 17,
        },
        "/repos/{}/actions/runs/{}".format(repository, run_id): {
            "actor": {"login": "customer-operator"},
            "conclusion": "success",
            "event": fair.OIDC_EVENT_NAME,
            "head_branch": "main",
            "head_sha": case["base_sha"],
            "id": int(run_id),
            "path": ".github/workflows/agent-fair-release.yml",
            "repository": {"full_name": repository},
            "status": "completed",
        },
        (
            "/repos/{}/actions/runs/{}/artifacts?per_page=100"
        ).format(repository, run_id): {
            "artifacts": [
                {
                    "expired": False,
                    "id": 9001,
                    "name": verifier.ARTIFACT_PREFIX + run_id,
                }
            ],
        },
    }


def _verify(case, api):
    return verifier.verify_pull_request_release(
        case["root"],
        fair.OIDC_REPOSITORY,
        17,
        case["base_sha"],
        case["head_sha"],
        api=api,
        wait_seconds=10,
        poll_seconds=5,
        sleep_fn=lambda _seconds: None,
    )


def test_create_and_verify_attestation_roundtrip(scratch_dir):
    case = _release_repo(scratch_dir)
    output = scratch_dir / "agent-fair-release-attestation.json"
    created = verifier.create_release_attestation(
        case["root"],
        output,
        case["base_sha"],
        case["head_sha"],
    )
    assert created == case["attestation"]
    assert output.read_bytes() == fair._pretty_bytes(created)
    assert set(created) == verifier.ATTESTATION_KEYS
    assert created["approval_evidence"] == _approval_evidence()
    assert created["attestation_sha256"] == "a" * 64
    assert created["release_frame_hash"] == case["frame"]["frame_hash"]
    assert created["release_event_id"] == case["frame"]["payload"]["event_id"]
    verified = verifier.verify_ci_release_attestation(
        output,
        case["root"],
    )
    assert verified["status"] == "attestation-verified"
    assert verified["release_commit_sha"] == case["head_sha"]


def test_valid_pull_request_attestation_is_verified(scratch_dir):
    case = _release_repo(scratch_dir)
    api = FakeApi(
        _api_values(case),
        _artifact_zip(case["attestation"]),
    )
    result = _verify(case, api)
    assert result == {
        "artifact_name": "agent-fair-release-attestation-123456789",
        "branch": "release/agent-fair-123456789",
        "candidate_digest": fair._load_json(
            fair.RELEASE_CANDIDATE_PATH
        )["candidate_digest"],
        "release_commit_sha": case["head_sha"],
        "release_event_id": case["frame"]["payload"]["event_id"],
        "run_id": "123456789",
        "status": "verified",
        "valid": True,
    }


def test_non_release_pull_request_passes_without_github_api(scratch_dir):
    case = _release_repo(scratch_dir)
    root = case["root"]
    _run(root, "git", "checkout", "-q", case["base_sha"])
    (root / "unrelated.txt").write_text("unrelated\n", encoding="utf-8")
    _run(root, "git", "add", "unrelated.txt")
    _run(root, "git", "commit", "-q", "-m", "unrelated")
    head_sha = _run(root, "git", "rev-parse", "HEAD")

    class NoApi:
        def get_json(self, _path):
            raise AssertionError("GitHub API must not be called")

    result = verifier.verify_pull_request_release(
        root,
        fair.OIDC_REPOSITORY,
        18,
        case["base_sha"],
        head_sha,
        api=NoApi(),
    )
    assert result["status"] == "not-applicable"
    assert result["valid"] is True


@pytest.mark.parametrize(
    "relative",
    [
        "apps/agent-fair/release-candidate.json",
        "unrelated.txt",
    ],
)
def test_release_branch_requires_fair_frame(scratch_dir, relative):
    case = _release_repo(scratch_dir)
    root = case["root"]
    _run(root, "git", "checkout", "-q", case["base_sha"])
    _run(root, "git", "checkout", "-q", "-b", "release/agent-fair-999")
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("not a release frame\n", encoding="utf-8")
    _run(root, "git", "add", relative)
    _run(root, "git", "commit", "-q", "-m", "forged protected change")
    head_sha = _run(root, "git", "rev-parse", "HEAD")
    with pytest.raises(
        verifier.AttestationError,
        match="does not contain a fair release frame",
    ):
        verifier.verify_pull_request_release(
            root,
            fair.OIDC_REPOSITORY,
            19,
            case["base_sha"],
            head_sha,
            head_ref="release/agent-fair-999",
        )


@pytest.mark.parametrize(
    "mutation",
    [
        "wrong-branch",
        "reused-run",
        "missing-artifact",
        "expired-artifact",
        "wrong-workflow",
        "wrong-workflow-ref",
        "wrong-event",
        "wrong-repository",
        "wrong-actor",
        "wrong-run-id",
        "wrong-run-base",
        "wrong-pr-head",
        "forged-evidence",
        "wrong-schema",
        "extra-field",
        "missing-field",
        "wrong-environment",
        "edited-release-commit",
        "wrong-frame-hash",
        "wrong-candidate",
        "extra-archive-file",
    ],
)
def test_all_provenance_mutations_fail(scratch_dir, mutation):
    case = _release_repo(scratch_dir)
    branch = "release/agent-fair-123456789"
    values = _api_values(case, branch)
    artifact = copy.deepcopy(case["attestation"])
    extra = False
    repository = fair.OIDC_REPOSITORY
    run_path = "/repos/{}/actions/runs/123456789".format(repository)
    artifacts_path = (
        "/repos/{}/actions/runs/123456789/artifacts?per_page=100"
    ).format(repository)
    if mutation == "wrong-branch":
        values["/repos/{}/pulls/17".format(repository)]["head"][
            "ref"
        ] = "feature/not-authorized"
    elif mutation == "reused-run":
        values["/repos/{}/pulls/17".format(repository)]["head"][
            "ref"
        ] = "release/agent-fair-987654321"
        values["/repos/{}/actions/runs/987654321".format(repository)] = (
            copy.deepcopy(values.pop(run_path))
        )
        values["/repos/{}/actions/runs/987654321".format(repository)][
            "id"
        ] = 987654321
        values[
            "/repos/{}/actions/runs/987654321/artifacts?per_page=100".format(
                repository
            )
        ] = copy.deepcopy(values.pop(artifacts_path))
    elif mutation == "missing-artifact":
        values[artifacts_path]["artifacts"] = []
    elif mutation == "expired-artifact":
        values[artifacts_path]["artifacts"][0]["expired"] = True
    elif mutation == "wrong-workflow":
        values[run_path]["path"] = ".github/workflows/other.yml"
    elif mutation == "wrong-workflow-ref":
        artifact["workflow_ref"] = (
            fair.OIDC_REPOSITORY
            + "/.github/workflows/other.yml@refs/heads/main"
        )
    elif mutation == "wrong-event":
        values[run_path]["event"] = "push"
    elif mutation == "wrong-repository":
        values[run_path]["repository"]["full_name"] = "attacker/fork"
    elif mutation == "wrong-actor":
        values[run_path]["actor"]["login"] = "attacker"
    elif mutation == "wrong-run-id":
        values[run_path]["id"] = 42
    elif mutation == "wrong-run-base":
        values[run_path]["head_sha"] = "0" * 40
    elif mutation == "wrong-pr-head":
        values["/repos/{}/pulls/17".format(repository)]["head"][
            "sha"
        ] = case["base_sha"]
    elif mutation == "forged-evidence":
        artifact["approval_evidence"]["actor"] = "attacker"
    elif mutation == "wrong-schema":
        artifact["schema"] = "forged"
    elif mutation == "extra-field":
        artifact["jwt"] = "must-not-be-accepted"
    elif mutation == "missing-field":
        artifact.pop("release_event_id")
    elif mutation == "wrong-environment":
        artifact["environment"] = "unprotected"
    elif mutation == "edited-release-commit":
        artifact["release_commit_sha"] = case["base_sha"]
    elif mutation == "wrong-frame-hash":
        artifact["release_frame_hash"] = "0" * 64
    elif mutation == "wrong-candidate":
        artifact["candidate_digest"] = "0" * 64
    else:
        extra = True
    api = FakeApi(values, _artifact_zip(artifact, extra=extra))
    with pytest.raises(verifier.AttestationError):
        _verify(case, api)


def test_run_wait_is_bounded_and_requires_success(scratch_dir):
    case = _release_repo(scratch_dir)
    values = _api_values(case)
    run_path = "/repos/{}/actions/runs/123456789".format(
        fair.OIDC_REPOSITORY
    )
    pending = copy.deepcopy(values[run_path])
    pending["status"] = "in_progress"
    pending["conclusion"] = None
    values[run_path] = [pending, pending, values[run_path]]
    api = FakeApi(values, _artifact_zip(case["attestation"]))
    assert _verify(case, api)["status"] == "verified"
    assert sum(
        1
        for kind, path in api.calls
        if kind == "json" and path == run_path
    ) == 3

    values = _api_values(case)
    values[run_path] = [pending]
    api = FakeApi(values, _artifact_zip(case["attestation"]))
    with pytest.raises(verifier.AttestationError, match="timed out"):
        _verify(case, api)
    assert sum(
        1
        for kind, path in api.calls
        if kind == "json" and path == run_path
    ) == 3


def test_failed_release_workflow_is_rejected(scratch_dir):
    case = _release_repo(scratch_dir)
    values = _api_values(case)
    run_path = "/repos/{}/actions/runs/123456789".format(
        fair.OIDC_REPOSITORY
    )
    values[run_path]["conclusion"] = "failure"
    api = FakeApi(values, _artifact_zip(case["attestation"]))
    with pytest.raises(verifier.AttestationError, match="did not succeed"):
        _verify(case, api)


def test_release_commit_edited_after_artifact_is_rejected(scratch_dir):
    case = _release_repo(scratch_dir)
    root = case["root"]
    (root / "edited.txt").write_text("edited after release\n", encoding="utf-8")
    _run(root, "git", "add", "edited.txt")
    _run(root, "git", "commit", "-q", "-m", "edited release")
    edited_head = _run(root, "git", "rev-parse", "HEAD")
    with pytest.raises(
        verifier.AttestationError,
        match="direct child",
    ):
        verifier.verify_pull_request_release(
            root,
            fair.OIDC_REPOSITORY,
            17,
            case["base_sha"],
            edited_head,
            api=FakeApi(
                _api_values(case),
                _artifact_zip(case["attestation"]),
            ),
        )


def test_missing_base_verifier_allows_exact_nonrelease_bootstrap(scratch_dir):
    assert verifier.BOOTSTRAP_ALLOWED_PATHS == EXPECTED_BOOTSTRAP_PATHS
    case = _bootstrap_repo(scratch_dir)
    result = verifier.verify_bootstrap_install(
        case["root"],
        case["base_sha"],
        case["head_sha"],
        "feature/bootstrap-verifier",
    )
    assert result == {
        "changed_paths": sorted(EXPECTED_BOOTSTRAP_PATHS),
        "reason": "trusted base verifier is not installed yet",
        "status": "bootstrap-not-release",
        "valid": True,
    }
    workflow = _run_bootstrap_workflow(
        case,
        "feature/bootstrap-verifier",
    )
    assert workflow.returncode == 0, workflow.stderr
    assert '"status": "bootstrap-not-release"' in workflow.stdout


def test_missing_base_verifier_rejects_release_branch(scratch_dir):
    case = _bootstrap_repo(scratch_dir)
    with pytest.raises(
        verifier.AttestationError,
        match="cannot use a release branch",
    ):
        verifier.verify_bootstrap_install(
            case["root"],
            case["base_sha"],
            case["head_sha"],
            "release/agent-fair-123456789",
        )
    workflow = _run_bootstrap_workflow(
        case,
        "release/agent-fair-123456789",
    )
    assert workflow.returncode != 0
    assert "cannot use a release branch" in workflow.stderr


@pytest.mark.parametrize(
    ("relative", "contents"),
    (
        ("apps/organism-frames.json", '{"edited":true}\n'),
        ("apps/organism-frames.json.backup", "{}\n"),
        ("apps/syndication/bootstrap-forgery.json", "{}\n"),
    ),
)
def test_missing_base_verifier_rejects_generated_release_paths(
    scratch_dir,
    relative,
    contents,
):
    case = _bootstrap_repo(scratch_dir)
    target = case["root"] / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(contents, encoding="utf-8")
    _run(case["root"], "git", "add", relative)
    _run(case["root"], "git", "commit", "-q", "-m", "forged output")
    with pytest.raises(
        verifier.AttestationError,
        match="forbidden generated release paths",
    ):
        verifier.verify_bootstrap_install(
            case["root"],
            case["base_sha"],
            _run(case["root"], "git", "rev-parse", "HEAD"),
            "feature/bootstrap-verifier",
        )
    case["head_sha"] = _run(case["root"], "git", "rev-parse", "HEAD")
    workflow = _run_bootstrap_workflow(
        case,
        "feature/bootstrap-verifier",
    )
    assert workflow.returncode != 0
    assert "forbidden generated release paths" in workflow.stderr


def test_missing_base_verifier_rejects_fair_release_frame(scratch_dir):
    case = _bootstrap_repo(scratch_dir)
    root = case["root"]
    candidate = fair._load_json(
        root / "apps" / "agent-fair" / "release-candidate.json"
    )
    organism_ledger.append_frame(
        "zoo.observation",
        fair._render_release_frame_payload(
            candidate,
            _approval_evidence(),
        ),
        utc=_release_utc(root),
        ledger_path=root / "apps" / "organism-frames.jsonl",
        projection_path=root / "apps" / "organism-frames.json",
    )
    _run(
        root,
        "git",
        "add",
        "apps/organism-frames.json",
        "apps/organism-frames.jsonl",
    )
    _run(root, "git", "commit", "-q", "-m", "forged release")
    with pytest.raises(
        verifier.AttestationError,
        match="contains a fair release event",
    ):
        verifier.verify_bootstrap_install(
            root,
            case["base_sha"],
            _run(root, "git", "rev-parse", "HEAD"),
            "feature/bootstrap-verifier",
        )
    case["head_sha"] = _run(root, "git", "rev-parse", "HEAD")
    workflow = _run_bootstrap_workflow(
        case,
        "feature/bootstrap-verifier",
    )
    assert workflow.returncode != 0
    assert "contains a fair release event" in workflow.stderr


def test_missing_base_verifier_rejects_nonbootstrap_path(scratch_dir):
    case = _bootstrap_repo(scratch_dir)
    target = case["root"] / "README.md"
    target.write_text("unrelated change\n", encoding="utf-8")
    _run(case["root"], "git", "add", "README.md")
    _run(case["root"], "git", "commit", "-q", "-m", "unrelated")
    with pytest.raises(
        verifier.AttestationError,
        match="outside the one-time allowlist",
    ):
        verifier.verify_bootstrap_install(
            case["root"],
            case["base_sha"],
            _run(case["root"], "git", "rev-parse", "HEAD"),
            "feature/bootstrap-verifier",
        )
    case["head_sha"] = _run(case["root"], "git", "rev-parse", "HEAD")
    workflow = _run_bootstrap_workflow(
        case,
        "feature/bootstrap-verifier",
    )
    assert workflow.returncode != 0
    assert "outside one-time allowlist" in workflow.stderr


def test_workflows_and_codeowners_close_provenance_path():
    release = (
        ROOT / ".github" / "workflows" / "agent-fair-release.yml"
    ).read_text(encoding="utf-8")
    attestation = (
        ROOT
        / ".github"
        / "workflows"
        / "agent-fair-release-attestation.yml"
    ).read_text(encoding="utf-8")
    owners = (ROOT / ".github" / "CODEOWNERS").read_text(encoding="utf-8")
    assert "actions/upload-artifact@v4" in release
    assert "agent-fair-release-attestation-${{ github.run_id }}" in release
    assert release.index("Push release branch") < release.index(
        "Generate bounded release attestation"
    )
    assert release.index("Generate bounded release attestation") < (
        release.index("actions/upload-artifact@v4")
    )
    assert "AGENT_FAIR_RELEASE_ATTESTATION" not in release
    assert release.index("actions/upload-artifact@v4") < release.index(
        "gh pr create"
    )
    assert "Dispatch required release pull request checks" in release
    assert "gh workflow run moonshot-gate.yml" in release
    assert "gh workflow run agent-fair-release-attestation.yml" in release
    assert "actions: write" in release
    assert not re.search(
        r"git\s+push[^\n]*(?:HEAD:main|refs/heads/main|origin\s+main)",
        release,
        re.IGNORECASE,
    )
    assert "pull_request:" in attestation
    assert "workflow_dispatch:" in attestation
    for input_name in ("pr_number:", "base_sha:", "head_sha:", "head_ref:"):
        assert input_name in attestation
    assert 'test "$HEAD_SHA" = "$GITHUB_SHA"' in attestation
    assert 'test "$HEAD_REF" = "$GITHUB_REF_NAME"' in attestation
    assert "agent-fair-release-attestation:" in attestation
    assert "actions: read" in attestation
    assert "pull-requests: read" in attestation
    assert "contents: read" in attestation
    assert "--head-ref" in attestation
    assert (
        'git cat-file -e "${BASE_SHA}:scripts/'
        'verify_agent_fair_release_attestation.py"'
    ) in attestation
    assert (
        "if: steps.trusted.outputs.available == 'true'"
    ) in attestation
    assert (
        "if: steps.trusted.outputs.available == 'false'"
    ) in attestation
    assert "bootstrap-not-release" in attestation
    assert '"apps/organism-frames.jsonl"' in attestation
    assert '"apps/syndication/"' in attestation
    assert (
        '"scripts/verify_agent_fair_release_attestation.py"'
        in attestation
    )
    assert attestation.index("Detect trusted base verifier") < (
        attestation.index("Materialize trusted verifier")
    )
    assert (
        'git show "${BASE_SHA}:scripts/'
        'verify_agent_fair_release_attestation.py"'
    ) in attestation
    assert (
        '"${RUNNER_TEMP}/agent-fair-release-verifier/'
        'verify_agent_fair_release_attestation.py"'
    ) in attestation
    assert "verify-pr" in attestation
    for path in (
        "/apps/organism-frames.json ",
        "/apps/organism-frames.jsonl ",
        "/apps/syndication/ ",
        "/apps/agent-fair/ ",
        "/.github/workflows/agent-fair-release.yml ",
        "/.github/workflows/agent-fair-release-attestation.yml ",
    ):
        assert path + "@kody-w" in owners
    source = (
        ROOT / "scripts" / "verify_agent_fair_release_attestation.py"
    ).read_text(encoding="utf-8")
    assert "PROTECTED_RELEASE_PATHS" in source
    assert "PROTECTED_RELEASE_PREFIXES" in source
    assert "BOOTSTRAP_ALLOWED_PATHS" in source
    assert "BOOTSTRAP_FORBIDDEN_PATHS" in source
    assert "BOOTSTRAP_FORBIDDEN_PREFIXES" in source
    assert "def _changed_paths(" in source
    assert "def _protected_changed_paths(" in source
    assert "def verify_bootstrap_install(" in source


def test_attestation_contains_no_token_or_jwt_fields(scratch_dir):
    value = _release_repo(scratch_dir)["attestation"]

    def walk(item):
        if isinstance(item, dict):
            for key, child in item.items():
                assert key.lower() not in {"jwt", "jws", "token"}
                walk(child)
        elif isinstance(item, list):
            for child in item:
                walk(child)

    walk(value)

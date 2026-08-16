#!/usr/bin/env python3
"""Create and verify provenance for Agent World's Fair release pull requests."""

import argparse
import io
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import agent_world_fair as fair
import organism_ledger


ROOT = Path(__file__).resolve().parent.parent
LEDGER_RELATIVE = Path("apps/organism-frames.jsonl")
PROJECTION_RELATIVE = Path("apps/organism-frames.json")
CANDIDATE_RELATIVE = Path("apps/agent-fair/release-candidate.json")
ATTESTATION_SCHEMA = "rappterzoo-agent-fair-release-attestation/1"
ATTESTATION_FILE = "agent-fair-release-attestation.json"
ARTIFACT_PREFIX = "agent-fair-release-attestation-"
RELEASE_BRANCH_PREFIX = "release/agent-fair-"
RELEASE_EVENT_PREFIX = "agent-worlds-fair-release:"
GITHUB_API_URL = "https://api.github.com"
JSON_LIMIT = 1024 * 1024
ZIP_LIMIT = 10 * 1024 * 1024
ATTESTATION_LIMIT = 128 * 1024
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
HASH_RE = re.compile(r"^[0-9a-f]{64}$")
ATTESTATION_KEYS = {
    "actor",
    "approval_evidence",
    "attestation_sha256",
    "base_sha",
    "bundle_digest",
    "candidate_digest",
    "district_digest",
    "environment",
    "event_name",
    "release_commit_sha",
    "release_event_id",
    "release_frame_hash",
    "repository",
    "run_id",
    "schema",
    "workflow_ref",
}
PROTECTED_RELEASE_PATHS = {
    ".github/CODEOWNERS",
    ".github/workflows/agent-fair-release-attestation.yml",
    ".github/workflows/agent-fair-release.yml",
    "apps/agent-fair/release-candidate.json",
    "apps/organism-frames.json",
    "apps/organism-frames.jsonl",
    "scripts/agent_world_fair.py",
    "scripts/verify_agent_fair_release_attestation.py",
}
PROTECTED_RELEASE_PREFIXES = (
    "apps/agent-fair/",
    "apps/syndication/",
)


class AttestationError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AttestationError(message)


def _git_bytes(root: Path, arguments: Sequence[str]) -> bytes:
    process = subprocess.run(
        ["git", "-C", str(root)] + list(arguments),
        capture_output=True,
        check=False,
    )
    if process.returncode != 0:
        raise AttestationError(
            process.stderr.decode("utf-8", "replace").strip()
            or "git command failed"
        )
    return process.stdout


def _git_text(root: Path, arguments: Sequence[str]) -> str:
    try:
        return _git_bytes(root, arguments).decode("utf-8").strip()
    except UnicodeError as error:
        raise AttestationError("git returned invalid UTF-8") from error


def _validate_sha(value: str, label: str) -> str:
    if type(value) is not str or not SHA_RE.fullmatch(value):
        raise AttestationError("{} must be a lowercase commit SHA".format(label))
    return value


def _changed_paths(
    root: Path,
    base_sha: str,
    head_sha: str,
) -> List[str]:
    base = _validate_sha(base_sha, "base_sha")
    head = _validate_sha(head_sha, "head_sha")
    raw = _git_bytes(
        Path(root),
        ["diff", "--name-only", "-z", base, head],
    )
    try:
        paths = [
            value.decode("utf-8")
            for value in raw.split(b"\x00")
            if value
        ]
    except UnicodeError as error:
        raise AttestationError("git changed paths are invalid UTF-8") from error
    _require(
        all(
            path
            and not path.startswith("/")
            and ".." not in Path(path).parts
            for path in paths
        ),
        "git changed path is unsafe",
    )
    return sorted(set(paths))


def _protected_changed_paths(paths: Sequence[str]) -> List[str]:
    return [
        path
        for path in paths
        if (
            path in PROTECTED_RELEASE_PATHS
            or any(
                path.startswith(prefix)
                for prefix in PROTECTED_RELEASE_PREFIXES
            )
        )
    ]


def _release_lines(raw: bytes) -> List[bytes]:
    result = []
    for line in raw.splitlines():
        try:
            frame = json.loads(line.decode("utf-8"))
        except (UnicodeError, ValueError):
            continue
        if type(frame) is not dict:
            continue
        payload = frame.get("payload", {})
        if (
            type(payload) is dict
            and (
                payload.get("event") == "agent-worlds-fair-release"
                or str(payload.get("event_id", "")).startswith(
                    RELEASE_EVENT_PREFIX
                )
            )
        ):
            result.append(line)
    return result


def _read_verified_frames(raw: bytes) -> List[Dict[str, Any]]:
    try:
        frames = organism_ledger._read_frame_bytes(raw)
        organism_ledger.verify_frames(frames)
    except Exception as error:
        raise AttestationError(
            "organism frame history is invalid: {}".format(error)
        ) from error
    return frames


def _release_frames(
    frames: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    return [
        frame
        for frame in frames
        if (
            frame.get("payload", {}).get("event")
            == "agent-worlds-fair-release"
            or str(frame.get("payload", {}).get("event_id", "")).startswith(
                RELEASE_EVENT_PREFIX
            )
        )
    ]


def _direct_parent(root: Path, commit_sha: str) -> str:
    line = _git_text(
        root,
        ["rev-list", "--parents", "-n", "1", commit_sha],
    ).split()
    _require(
        len(line) == 2 and line[0] == commit_sha,
        "release commit must have exactly one parent",
    )
    return line[1]


def inspect_release_change(
    root: Path,
    base_sha: str,
    head_sha: str,
) -> Optional[Tuple[Dict[str, Any], Dict[str, Any]]]:
    repository = Path(root).resolve()
    base = _validate_sha(base_sha, "base_sha")
    head = _validate_sha(head_sha, "head_sha")
    current = _git_text(repository, ["rev-parse", "HEAD"])
    _require(current == head, "checked-out HEAD does not match pull request")
    base_raw = _git_bytes(
        repository,
        ["show", "{}:{}".format(base, LEDGER_RELATIVE.as_posix())],
    )
    head_raw = _git_bytes(
        repository,
        ["show", "{}:{}".format(head, LEDGER_RELATIVE.as_posix())],
    )
    if _release_lines(base_raw) == _release_lines(head_raw):
        return None
    base_frames = _read_verified_frames(base_raw)
    head_frames = _read_verified_frames(head_raw)
    _require(
        len(head_frames) == len(base_frames) + 1
        and head_frames[:len(base_frames)] == base_frames,
        "fair release must be one exact append",
    )
    base_releases = _release_frames(base_frames)
    head_releases = _release_frames(head_frames)
    _require(
        not base_releases and len(head_releases) == 1,
        "fair release frame must be introduced exactly once",
    )
    frame = head_frames[-1]
    _require(
        frame == head_releases[0]
        and frame.get("kind") == "zoo.observation"
        and frame.get("sig") is None,
        "appended frame is not the unsigned fair release",
    )
    try:
        organism_ledger.verify_projection(
            head_frames,
            repository / PROJECTION_RELATIVE,
        )
        verified = fair.verify_release_candidate_file(repository)
        candidate = fair._load_json(repository / CANDIDATE_RELATIVE)
        fair._verify_release_frame_payload(candidate, frame.get("payload"))
    except Exception as error:
        raise AttestationError(
            "release frame or candidate verification failed: {}".format(error)
        ) from error
    _require(
        verified.get("candidate_digest") == candidate.get("candidate_digest"),
        "verified candidate digest changed",
    )
    _require(
        _direct_parent(repository, head) == base,
        "release commit is not a direct child of workflow base",
    )
    return candidate, frame


def build_release_attestation(
    candidate: Dict[str, Any],
    frame: Dict[str, Any],
    base_sha: str,
    release_commit_sha: str,
) -> Dict[str, Any]:
    base = _validate_sha(base_sha, "base_sha")
    release_commit = _validate_sha(
        release_commit_sha,
        "release_commit_sha",
    )
    payload = frame.get("payload", {})
    evidence = payload.get("approval_evidence", {})
    try:
        fair._verify_release_frame_payload(candidate, payload)
    except Exception as error:
        raise AttestationError(
            "release payload does not match candidate: {}".format(error)
        ) from error
    return {
        "actor": evidence["actor"],
        "approval_evidence": evidence,
        "attestation_sha256": evidence["attestation_sha256"],
        "base_sha": base,
        "bundle_digest": candidate["bundle_digest"],
        "candidate_digest": candidate["candidate_digest"],
        "district_digest": candidate["district_digest"],
        "environment": evidence["environment"],
        "event_name": evidence["event_name"],
        "release_commit_sha": release_commit,
        "release_event_id": payload["event_id"],
        "release_frame_hash": frame["frame_hash"],
        "repository": evidence["repository"],
        "run_id": evidence["run_id"],
        "schema": ATTESTATION_SCHEMA,
        "workflow_ref": evidence["workflow_ref"],
    }


def verify_release_attestation(
    attestation: Dict[str, Any],
    candidate: Dict[str, Any],
    frame: Dict[str, Any],
    base_sha: str,
    head_sha: str,
) -> Dict[str, Any]:
    if type(attestation) is not dict or set(attestation) != ATTESTATION_KEYS:
        raise AttestationError("release attestation key set is invalid")
    expected = build_release_attestation(
        candidate,
        frame,
        base_sha,
        head_sha,
    )
    if attestation != expected:
        raise AttestationError(
            "release attestation does not match PR frame and lineage"
        )
    _require(
        attestation["schema"] == ATTESTATION_SCHEMA
        and attestation["repository"] == fair.OIDC_REPOSITORY
        and attestation["workflow_ref"] == fair.OIDC_WORKFLOW_REF
        and attestation["environment"] == fair.OIDC_ENVIRONMENT
        and attestation["event_name"] == fair.OIDC_EVENT_NAME,
        "release attestation authority fields changed",
    )
    _require(
        type(attestation["actor"]) is str
        and attestation["actor"]
        and attestation["actor"].strip() == attestation["actor"]
        and type(attestation["run_id"]) is str
        and attestation["run_id"].isdigit(),
        "release attestation actor/run_id is invalid",
    )
    _require(
        HASH_RE.fullmatch(attestation["attestation_sha256"]) is not None
        and attestation["attestation_sha256"] != "0" * 64
        and attestation["approval_evidence"]["attestation_sha256"]
        == attestation["attestation_sha256"],
        "release attestation digest is invalid",
    )
    return {
        "candidate_digest": attestation["candidate_digest"],
        "release_commit_sha": attestation["release_commit_sha"],
        "release_event_id": attestation["release_event_id"],
        "run_id": attestation["run_id"],
        "valid": True,
    }


def create_release_attestation(
    root: Path,
    output: Path,
    base_sha: str,
    release_commit_sha: str,
) -> Dict[str, Any]:
    repository = Path(root).resolve()
    context = inspect_release_change(
        repository,
        base_sha,
        release_commit_sha,
    )
    if context is None:
        raise AttestationError("release commit does not add a fair frame")
    candidate, frame = context
    value = build_release_attestation(
        candidate,
        frame,
        base_sha,
        release_commit_sha,
    )
    verify_release_attestation(
        value,
        candidate,
        frame,
        base_sha,
        release_commit_sha,
    )
    fair._atomic_bytes(Path(output), fair._pretty_bytes(value))
    return value


class GitHubApi:
    def __init__(self, repository: str, token: str):
        _require(
            repository == fair.OIDC_REPOSITORY,
            "GitHub repository is not the release authority",
        )
        _require(
            type(token) is str and token and token.strip() == token,
            "GITHUB_TOKEN is required",
        )
        self.repository = repository
        self.token = token

    def _request(self, path: str, limit: int) -> bytes:
        _require(
            type(path) is str and path.startswith("/"),
            "GitHub API path is invalid",
        )
        request = urllib.request.Request(
            GITHUB_API_URL + path,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": "Bearer " + self.token,
                "User-Agent": "rappterzoo-agent-fair-attestation/1",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                status = getattr(response, "status", None)
                if status is None:
                    status = response.getcode()
                _require(status == 200, "GitHub API returned HTTP {}".format(
                    status
                ))
                raw = response.read(limit + 1)
        except AttestationError:
            raise
        except (OSError, urllib.error.URLError) as error:
            raise AttestationError("GitHub API request failed") from error
        _require(len(raw) <= limit, "GitHub API response is too large")
        return raw

    def get_json(self, path: str) -> Dict[str, Any]:
        raw = self._request(path, JSON_LIMIT)
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeError, ValueError) as error:
            raise AttestationError("GitHub API returned invalid JSON") from error
        _require(type(value) is dict, "GitHub API returned a non-object")
        return value

    def get_bytes(self, path: str) -> bytes:
        return self._request(path, ZIP_LIMIT)


def _wait_for_run(
    api: Any,
    repository: str,
    run_id: str,
    wait_seconds: int,
    poll_seconds: int,
    sleep_fn: Callable[[float], None],
) -> Dict[str, Any]:
    _require(
        wait_seconds >= 0 and poll_seconds > 0,
        "run wait bounds are invalid",
    )
    attempts = max(1, wait_seconds // poll_seconds + 1)
    path = "/repos/{}/actions/runs/{}".format(repository, run_id)
    for attempt in range(attempts):
        run = api.get_json(path)
        _require(str(run.get("id")) == run_id, "GitHub run id mismatch")
        if run.get("status") == "completed":
            _require(
                run.get("conclusion") == "success",
                "GitHub release workflow did not succeed",
            )
            return run
        _require(
            run.get("status") in {
                "queued",
                "in_progress",
                "pending",
                "waiting",
            },
            "GitHub release workflow status is invalid",
        )
        if attempt + 1 < attempts:
            sleep_fn(poll_seconds)
    raise AttestationError("timed out waiting for GitHub release workflow")


def _attestation_from_bytes(raw: bytes) -> Dict[str, Any]:
    try:
        value = fair._strict_json_bytes(
            raw,
            "release attestation artifact",
        )
    except Exception as error:
        raise AttestationError(str(error)) from error
    _require(
        raw == fair._pretty_bytes(value),
        "release attestation artifact bytes are not deterministic",
    )
    return value


def _artifact_from_zip(raw: bytes) -> Dict[str, Any]:
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            files = [
                info
                for info in archive.infolist()
                if not info.is_dir()
            ]
            _require(
                len(files) == 1
                and files[0].filename == ATTESTATION_FILE
                and files[0].file_size <= ATTESTATION_LIMIT,
                "release artifact archive shape is invalid",
            )
            value_raw = archive.read(files[0])
    except AttestationError:
        raise
    except (OSError, ValueError, zipfile.BadZipFile) as error:
        raise AttestationError("release artifact is not a valid ZIP") from error
    return _attestation_from_bytes(value_raw)


def verify_ci_release_attestation(
    path: Path,
    root: Path = ROOT,
) -> Dict[str, Any]:
    """Verify a local CI attestation file without performing network access."""
    artifact_path = Path(path)
    try:
        raw = artifact_path.read_bytes()
    except OSError as error:
        raise AttestationError(
            "cannot read release attestation artifact"
        ) from error
    _require(
        len(raw) <= ATTESTATION_LIMIT,
        "release attestation artifact is too large",
    )
    value = _attestation_from_bytes(raw)
    base_sha = value.get("base_sha")
    head_sha = value.get("release_commit_sha")
    context = inspect_release_change(Path(root), base_sha, head_sha)
    _require(context is not None, "attestation does not describe a fair release")
    candidate, frame = context
    result = verify_release_attestation(
        value,
        candidate,
        frame,
        base_sha,
        head_sha,
    )
    return {
        **result,
        "artifact": str(artifact_path),
        "status": "attestation-verified",
    }


def verify_pull_request_release(
    root: Path,
    repository: str,
    pr_number: int,
    base_sha: str,
    head_sha: str,
    head_ref: Optional[str] = None,
    api: Optional[Any] = None,
    wait_seconds: int = 300,
    poll_seconds: int = 5,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> Dict[str, Any]:
    repository_root = Path(root).resolve()
    base = _validate_sha(base_sha, "base_sha")
    head = _validate_sha(head_sha, "head_sha")
    changed_paths = _changed_paths(repository_root, base, head)
    protected_changes = _protected_changed_paths(changed_paths)
    context = inspect_release_change(repository_root, base, head)
    if context is None:
        if (
            type(head_ref) is str
            and head_ref.startswith(RELEASE_BRANCH_PREFIX)
            and protected_changes
        ):
            raise AttestationError(
                "release branch changed protected paths without a fair frame"
            )
        return {
            "changed_paths": changed_paths,
            "protected_changes": protected_changes,
            "reason": "pull request does not add or change a fair release frame",
            "status": "not-applicable",
            "valid": True,
        }
    _require(
        repository == fair.OIDC_REPOSITORY,
        "pull request repository is not the release authority",
    )
    candidate, frame = context
    client = api
    if client is None:
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        client = GitHubApi(repository, token or "")
    pull = client.get_json(
        "/repos/{}/pulls/{}".format(repository, int(pr_number))
    )
    _require(
        pull.get("number") == int(pr_number)
        and pull.get("base", {}).get("ref") == "main"
        and pull.get("base", {}).get("sha") == base
        and pull.get("head", {}).get("sha") == head
        and pull.get("head", {}).get("repo", {}).get("full_name")
        == repository,
        "GitHub pull request head/base identity mismatch",
    )
    branch = pull.get("head", {}).get("ref")
    match = re.fullmatch(
        r"release/agent-fair-([1-9][0-9]*)",
        str(branch),
    )
    _require(match is not None, "release pull request branch is invalid")
    run_id = match.group(1)
    evidence = frame["payload"]["approval_evidence"]
    _require(
        evidence.get("run_id") == run_id,
        "release branch and approval run_id mismatch",
    )
    run = _wait_for_run(
        client,
        repository,
        run_id,
        wait_seconds,
        poll_seconds,
        sleep_fn,
    )
    _require(
        run.get("event") == fair.OIDC_EVENT_NAME
        and run.get("path") == ".github/workflows/agent-fair-release.yml"
        and run.get("head_branch") == "main"
        and run.get("head_sha") == base
        and run.get("repository", {}).get("full_name") == repository
        and run.get("actor", {}).get("login") == evidence.get("actor"),
        "GitHub release workflow provenance mismatch",
    )
    artifact_name = ARTIFACT_PREFIX + run_id
    listing = client.get_json(
        "/repos/{}/actions/runs/{}/artifacts?per_page=100".format(
            repository,
            run_id,
        )
    )
    artifacts = listing.get("artifacts")
    _require(type(artifacts) is list, "GitHub artifact listing is invalid")
    matches = [
        artifact
        for artifact in artifacts
        if (
            type(artifact) is dict
            and artifact.get("name") == artifact_name
            and artifact.get("expired") is False
        )
    ]
    _require(
        len(matches) == 1
        and type(matches[0].get("id")) is int,
        "exact release attestation artifact is missing",
    )
    archive = client.get_bytes(
        "/repos/{}/actions/artifacts/{}/zip".format(
            repository,
            matches[0]["id"],
        )
    )
    attestation = _artifact_from_zip(archive)
    result = verify_release_attestation(
        attestation,
        candidate,
        frame,
        base,
        head,
    )
    _require(
        attestation["run_id"] == run_id
        and attestation["actor"] == run["actor"]["login"]
        and attestation["environment"] == fair.OIDC_ENVIRONMENT,
        "artifact and GitHub workflow authority mismatch",
    )
    return {
        **result,
        "artifact_name": artifact_name,
        "branch": branch,
        "status": "verified",
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="verify-agent-fair-release-attestation"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create")
    create.add_argument("--root", type=Path, default=ROOT)
    create.add_argument("--output", type=Path, required=True)
    create.add_argument("--base-sha", required=True)
    create.add_argument("--release-commit-sha", required=True)
    local = commands.add_parser("verify-local")
    local.add_argument("--root", type=Path, default=ROOT)
    local.add_argument("--attestation", type=Path, required=True)
    verify = commands.add_parser("verify-pr")
    verify.add_argument("--root", type=Path, default=ROOT)
    verify.add_argument("--repository", required=True)
    verify.add_argument("--pr-number", type=int, required=True)
    verify.add_argument("--base-sha", required=True)
    verify.add_argument("--head-sha", required=True)
    verify.add_argument("--head-ref")
    verify.add_argument("--wait-seconds", type=int, default=300)
    arguments = parser.parse_args(argv)
    try:
        if arguments.command == "create":
            value = create_release_attestation(
                arguments.root,
                arguments.output,
                arguments.base_sha,
                arguments.release_commit_sha,
            )
            result = {
                "artifact": str(arguments.output),
                "candidate_digest": value["candidate_digest"],
                "release_commit_sha": value["release_commit_sha"],
                "run_id": value["run_id"],
                "valid": True,
            }
        elif arguments.command == "verify-local":
            result = verify_ci_release_attestation(
                arguments.attestation,
                arguments.root,
            )
        else:
            result = verify_pull_request_release(
                arguments.root,
                arguments.repository,
                arguments.pr_number,
                arguments.base_sha,
                arguments.head_sha,
                head_ref=arguments.head_ref,
                wait_seconds=arguments.wait_seconds,
            )
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (
        AttestationError,
        OSError,
        ValueError,
        fair.FairError,
        organism_ledger.LedgerError,
    ) as error:
        print(
            json.dumps({"error": str(error), "ok": False}),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

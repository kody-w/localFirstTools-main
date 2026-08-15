#!/usr/bin/env python3
"""Queue GitHub Actions repository writers with an atomic remote Git ref."""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional


LOCK_BRANCH = "rappterzoo-writer-lock"
LOCK_REF = "refs/heads/" + LOCK_BRANCH
STATE_FILE = Path(".git") / "rappterzoo-writer-lock.json"
MESSAGE_PREFIX = "rappterzoo-writer-lock/1 "


class LockError(RuntimeError):
    pass


def _run(
    command,
    *,
    check=False,
    input_text=None,
    env=None,
):
    result = subprocess.run(
        command,
        input=input_text,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    if check and result.returncode != 0:
        raise LockError(
            result.stderr.strip()
            or result.stdout.strip()
            or "command failed: {}".format(" ".join(command))
        )
    return result


def lock_payload(run_id: str, workflow: str, repository: str) -> Dict[str, str]:
    return {
        "repository": repository,
        "run_id": run_id,
        "workflow": workflow,
    }


def lock_message(payload: Dict[str, str]) -> str:
    return MESSAGE_PREFIX + json.dumps(
        payload,
        separators=(",", ":"),
        sort_keys=True,
    )


def parse_lock_message(message: str) -> Optional[Dict[str, str]]:
    first_line = message.splitlines()[0] if message else ""
    if not first_line.startswith(MESSAGE_PREFIX):
        return None
    try:
        value = json.loads(first_line[len(MESSAGE_PREFIX):])
    except ValueError:
        return None
    if (
        not isinstance(value, dict)
        or not isinstance(value.get("run_id"), str)
        or not isinstance(value.get("repository"), str)
    ):
        return None
    return value


def may_reap(
    *,
    run_status: Optional[str],
    age_seconds: int,
    stale_seconds: int,
) -> bool:
    if run_status == "completed":
        return True
    if run_status in {"queued", "in_progress", "waiting", "pending"}:
        return False
    return age_seconds >= stale_seconds


def remote_lock_sha() -> Optional[str]:
    result = _run(["git", "ls-remote", "origin", LOCK_REF])
    if result.returncode != 0 or not result.stdout.strip():
        return None
    return result.stdout.split()[0]


def inspect_remote_lock(
    sha: str,
    repository: str,
) -> Dict[str, Any]:
    _run(["git", "fetch", "--quiet", "origin", LOCK_REF], check=True)
    message = _run(
        ["git", "show", "-s", "--format=%B", sha],
        check=True,
    ).stdout
    timestamp_text = _run(
        ["git", "show", "-s", "--format=%ct", sha],
        check=True,
    ).stdout.strip()
    try:
        timestamp = int(timestamp_text)
    except ValueError:
        timestamp = 0
    payload = parse_lock_message(message)
    status = None
    if payload and payload.get("repository") == repository:
        result = _run([
            "gh",
            "run",
            "view",
            payload["run_id"],
            "--repo",
            repository,
            "--json",
            "status",
        ])
        if result.returncode == 0:
            try:
                status = json.loads(result.stdout).get("status")
            except ValueError:
                status = None
    return {
        "payload": payload,
        "status": status,
        "age_seconds": max(0, int(time.time()) - timestamp),
    }


def delete_remote_lock(expected_sha: str) -> bool:
    result = _run([
        "git",
        "push",
        "origin",
        "--force-with-lease={}:{}".format(LOCK_REF, expected_sha),
        ":{}".format(LOCK_REF),
    ])
    return result.returncode == 0


def create_lock_commit(payload: Dict[str, str]) -> str:
    tree = _run(
        ["git", "rev-parse", "HEAD^{tree}"],
        check=True,
    ).stdout.strip()
    head = _run(["git", "rev-parse", "HEAD"], check=True).stdout.strip()
    identity = {
        **os.environ,
        "GIT_AUTHOR_NAME": "rappterzoo-writer-lock",
        "GIT_AUTHOR_EMAIL": "rappterzoo-writer-lock@users.noreply.github.com",
        "GIT_COMMITTER_NAME": "rappterzoo-writer-lock",
        "GIT_COMMITTER_EMAIL": "rappterzoo-writer-lock@users.noreply.github.com",
    }
    return _run(
        ["git", "commit-tree", tree, "-p", head],
        check=True,
        input_text=lock_message(payload) + "\n",
        env=identity,
    ).stdout.strip()


def acquire(
    *,
    timeout_seconds: int,
    interval_seconds: int,
    stale_seconds: int,
) -> Dict[str, str]:
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    workflow = os.environ.get("GITHUB_WORKFLOW", "")
    if not repository or not run_id:
        raise LockError(
            "GITHUB_REPOSITORY and GITHUB_RUN_ID are required"
        )
    payload = lock_payload(run_id, workflow, repository)
    commit = create_lock_commit(payload)
    deadline = time.monotonic() + timeout_seconds

    while True:
        result = _run([
            "git",
            "push",
            "origin",
            "{}:{}".format(commit, LOCK_REF),
        ])
        if result.returncode == 0:
            state = {
                **payload,
                "commit": commit,
            }
            STATE_FILE.write_text(
                json.dumps(state, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            return state

        sha = remote_lock_sha()
        if sha:
            lock = inspect_remote_lock(sha, repository)
            if may_reap(
                run_status=lock["status"],
                age_seconds=lock["age_seconds"],
                stale_seconds=stale_seconds,
            ):
                delete_remote_lock(sha)
                continue

        if time.monotonic() >= deadline:
            raise LockError("timed out waiting for repository writer lock")
        time.sleep(interval_seconds)


def release() -> bool:
    if not STATE_FILE.exists():
        return False
    try:
        state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    expected = state.get("commit")
    if not isinstance(expected, str):
        return False
    current = remote_lock_sha()
    if current != expected:
        return False
    released = delete_remote_lock(expected)
    if released:
        STATE_FILE.unlink()
    return released


def main() -> int:
    parser = argparse.ArgumentParser(prog="repository-lock")
    subcommands = parser.add_subparsers(dest="command", required=True)
    acquire_parser = subcommands.add_parser("acquire")
    acquire_parser.add_argument("--timeout", type=int, default=3600)
    acquire_parser.add_argument("--interval", type=int, default=15)
    acquire_parser.add_argument("--stale", type=int, default=7200)
    subcommands.add_parser("release")
    arguments = parser.parse_args()
    try:
        if arguments.command == "acquire":
            value = acquire(
                timeout_seconds=arguments.timeout,
                interval_seconds=arguments.interval,
                stale_seconds=arguments.stale,
            )
            print("Acquired repository writer lock for run {}".format(
                value["run_id"]
            ))
        else:
            print(
                "Released repository writer lock"
                if release()
                else "No owned repository writer lock to release"
            )
        return 0
    except LockError as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

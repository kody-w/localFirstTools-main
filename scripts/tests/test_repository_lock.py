"""Tests for the non-dropping GitHub Actions repository-writer queue."""

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import repository_lock


def test_lock_message_round_trip():
    payload = repository_lock.lock_payload(
        "123",
        "Autonomous Frame",
        "owner/repo",
    )
    assert repository_lock.parse_lock_message(
        repository_lock.lock_message(payload)
    ) == payload


def test_invalid_lock_message_is_not_authoritative():
    assert repository_lock.parse_lock_message("ordinary commit") is None
    assert repository_lock.parse_lock_message(
        repository_lock.MESSAGE_PREFIX + "{}"
    ) is None


def test_live_or_pending_runs_are_never_reaped():
    for status in ("queued", "in_progress", "waiting", "pending"):
        assert not repository_lock.may_reap(
            run_status=status,
            age_seconds=100000,
            stale_seconds=1,
        )


def test_completed_or_abandoned_locks_can_be_reaped():
    assert repository_lock.may_reap(
        run_status="completed",
        age_seconds=1,
        stale_seconds=7200,
    )
    assert repository_lock.may_reap(
        run_status=None,
        age_seconds=7200,
        stale_seconds=7200,
    )
    assert not repository_lock.may_reap(
        run_status=None,
        age_seconds=7199,
        stale_seconds=7200,
    )

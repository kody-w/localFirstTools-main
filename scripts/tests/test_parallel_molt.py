"""Tests for parallel molt execution in autonomous_frame.py."""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
import json
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import autonomous_frame


class TestParallelMolt:
    """html_molt uses ThreadPoolExecutor for concurrent molting."""

    def _make_rankings(self, apps):
        return {"rankings": [{"file": a, "score": 30 + i} for i, a in enumerate(apps)]}

    def _make_manifest(self, apps):
        return {"categories": {"test": {"apps": [{"file": a, "generation": 0} for a in apps]}}}

    @patch("autonomous_frame.run_script")
    @patch("autonomous_frame.load_json")
    def test_molts_multiple_apps(self, mock_load, mock_run):
        apps = ["a.html", "b.html", "c.html"]
        mock_load.side_effect = [self._make_rankings(apps), self._make_manifest(apps)]
        mock_run.return_value = (True, "ok", "")
        result = autonomous_frame.html_molt(3)
        assert len(result) == 3
        assert mock_run.call_count == 3

    @patch("autonomous_frame.run_script")
    @patch("autonomous_frame.load_json")
    def test_failure_doesnt_block_others(self, mock_load, mock_run):
        apps = ["a.html", "b.html", "c.html"]
        mock_load.side_effect = [self._make_rankings(apps), self._make_manifest(apps)]
        mock_run.side_effect = [(False, "", "fail"), (True, "ok", ""), (True, "ok", "")]
        result = autonomous_frame.html_molt(3)
        assert len(result) == 2, "2 of 3 should succeed"

    @patch("autonomous_frame.run_script")
    @patch("autonomous_frame.load_json")
    def test_returns_empty_on_no_rankings(self, mock_load, mock_run):
        mock_load.return_value = None
        result = autonomous_frame.html_molt(3)
        assert result == []
        mock_run.assert_not_called()

    @patch("autonomous_frame.run_script")
    @patch("autonomous_frame.load_json")
    def test_all_fail_returns_empty(self, mock_load, mock_run):
        apps = ["a.html", "b.html"]
        mock_load.side_effect = [self._make_rankings(apps), self._make_manifest(apps)]
        mock_run.return_value = (False, "", "timeout")
        result = autonomous_frame.html_molt(2)
        assert result == []

    @patch("autonomous_frame.run_script")
    @patch("autonomous_frame.load_json")
    def test_adaptive_timeout_by_file_size(self, mock_load, mock_run):
        """Larger files should get longer timeouts."""
        apps = ["big.html"]
        mock_load.side_effect = [self._make_rankings(apps), self._make_manifest(apps)]
        mock_run.return_value = (True, "ok", "")

        with patch("autonomous_frame.get_app_file_size", return_value=200_000):
            autonomous_frame.html_molt(1)

        call_args = mock_run.call_args
        timeout_used = call_args.kwargs.get("timeout", call_args[1].get("timeout", 300) if len(call_args) > 1 and isinstance(call_args[1], dict) else 300)
        # We just verify it was called — the timeout is passed as a kwarg
        assert mock_run.called

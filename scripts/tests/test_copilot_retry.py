"""Tests for copilot_call_with_retry — retry logic, backoff, adaptive timeout."""
import time
from unittest.mock import patch, MagicMock
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from copilot_utils import (
    copilot_call_with_retry,
    adaptive_timeout,
)


class TestAdaptiveTimeout:
    """adaptive_timeout(prompt) returns seconds scaled to prompt size."""

    def test_small_prompt(self):
        t = adaptive_timeout("x" * 1000)  # 1KB
        assert t >= 120, "Min timeout is 120s"

    def test_medium_prompt(self):
        t = adaptive_timeout("x" * 50_000)  # 50KB
        assert t >= 160, "50KB should get ~168s"

    def test_large_prompt(self):
        t = adaptive_timeout("x" * 200_000)  # 200KB
        assert t >= 310, "200KB should get ~315s"

    def test_returns_int(self):
        t = adaptive_timeout("hello")
        assert isinstance(t, int)


class TestCopilotCallWithRetry:
    """copilot_call_with_retry retries on failure with exponential backoff."""

    @patch("copilot_utils.copilot_call")
    def test_success_first_try(self, mock_call):
        mock_call.return_value = "some response"
        result = copilot_call_with_retry("prompt")
        assert result == "some response"
        assert mock_call.call_count == 1

    @patch("copilot_utils.time.sleep")
    @patch("copilot_utils.copilot_call")
    def test_retries_on_none(self, mock_call, mock_sleep):
        mock_call.side_effect = [None, None, "third time"]
        result = copilot_call_with_retry("prompt", max_retries=3)
        assert result == "third time"
        assert mock_call.call_count == 3

    @patch("copilot_utils.time.sleep")
    @patch("copilot_utils.copilot_call")
    def test_retries_on_empty_string(self, mock_call, mock_sleep):
        mock_call.side_effect = ["", "", "got it"]
        result = copilot_call_with_retry("prompt", max_retries=3)
        assert result == "got it"
        assert mock_call.call_count == 3

    @patch("copilot_utils.time.sleep")
    @patch("copilot_utils.copilot_call")
    def test_returns_none_after_all_retries_exhausted(self, mock_call, mock_sleep):
        mock_call.return_value = None
        result = copilot_call_with_retry("prompt", max_retries=3)
        assert result is None
        assert mock_call.call_count == 3

    @patch("copilot_utils.time.sleep")
    @patch("copilot_utils.copilot_call")
    def test_exponential_backoff_delays(self, mock_call, mock_sleep):
        mock_call.side_effect = [None, None, "ok"]
        copilot_call_with_retry("prompt", max_retries=3)
        delays = [c.args[0] for c in mock_sleep.call_args_list]
        assert delays == [2, 4], "Backoff: 2s, 4s (no sleep before first try or after success)"

    @patch("copilot_utils.time.sleep")
    @patch("copilot_utils.copilot_call")
    def test_uses_adaptive_timeout(self, mock_call, mock_sleep):
        mock_call.return_value = "ok"
        big_prompt = "x" * 100_000
        copilot_call_with_retry(big_prompt)
        used_timeout = mock_call.call_args.kwargs.get("timeout") or mock_call.call_args[1]
        assert used_timeout >= 210, "100KB prompt should get adaptive timeout >= 210s"

    @patch("copilot_utils.time.sleep")
    @patch("copilot_utils.copilot_call")
    def test_explicit_timeout_overrides_adaptive(self, mock_call, mock_sleep):
        mock_call.return_value = "ok"
        copilot_call_with_retry("small prompt", timeout=500)
        used_timeout = mock_call.call_args.kwargs.get("timeout") or mock_call.call_args[1]
        assert used_timeout == 500

    @patch("copilot_utils.copilot_call")
    def test_default_max_retries_is_3(self, mock_call):
        mock_call.return_value = None
        copilot_call_with_retry("prompt")
        assert mock_call.call_count == 3

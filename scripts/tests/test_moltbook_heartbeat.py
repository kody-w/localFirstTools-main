"""Tests for moltbook_heartbeat.py — fully mocked, no network."""

import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure scripts dir is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import moltbook_heartbeat as hb


# ---------------------------------------------------------------------------
# Verification solver tests
# ---------------------------------------------------------------------------

class TestCleanChallengeText:
    def test_strips_special_chars(self):
        assert hb._clean_challenge_text("TwEnTy!!! ThReE???") == "twenty three"

    def test_collapses_whitespace(self):
        assert hb._clean_challenge_text("  one   adds    two  ") == "one adds two"

    def test_lowercases(self):
        assert hb._clean_challenge_text("THIRTY FIVE") == "thirty five"


class TestExtractNumbers:
    def test_simple_numbers(self):
        assert hb._extract_numbers("five adds three") == [5, 3]

    def test_compound_number(self):
        assert hb._extract_numbers("twenty three adds ten") == [23, 10]

    def test_compound_thirty_two(self):
        assert hb._extract_numbers("thirty two minus five") == [32, 5]

    def test_no_numbers(self):
        assert hb._extract_numbers("hello world") == []

    def test_single_number(self):
        assert hb._extract_numbers("just five here") == [5]

    def test_teens(self):
        assert hb._extract_numbers("thirteen plus seventeen") == [13, 17]

    def test_forty_nine(self):
        assert hb._extract_numbers("forty nine times two") == [49, 2]


class TestDetectOperation:
    def test_add_keywords(self):
        assert hb._detect_operation("five adds three") == "add"
        assert hb._detect_operation("one and two") == "add"
        assert hb._detect_operation("gains five") == "add"
        assert hb._detect_operation("plus two") == "add"

    def test_sub_keywords(self):
        assert hb._detect_operation("reduces by three") == "sub"
        assert hb._detect_operation("minus two") == "sub"
        assert hb._detect_operation("loses five") == "sub"
        assert hb._detect_operation("takes away three") == "sub"

    def test_mul_keywords(self):
        assert hb._detect_operation("multiplied by three") == "mul"
        assert hb._detect_operation("five times two") == "mul"

    def test_default_add(self):
        assert hb._detect_operation("five something three") == "add"


class TestSolveVerification:
    def test_addition(self):
        assert hb.solve_verification("TwEnTy adds FiVe") == "25.00"

    def test_subtraction(self):
        assert hb.solve_verification("Thirty minus Ten") == "20.00"

    def test_multiplication(self):
        assert hb.solve_verification("Five times Three") == "15.00"

    def test_compound_numbers(self):
        assert hb.solve_verification("twenty three adds eleven") == "34.00"

    def test_garbled_text(self):
        assert hb.solve_verification("!!TwO!! **adds** !!ThReE!!") == "5.00"

    def test_zero(self):
        assert hb.solve_verification("zero adds five") == "5.00"

    def test_insufficient_numbers(self):
        assert hb.solve_verification("just one number here") is None

    def test_empty_string(self):
        assert hb.solve_verification("") is None

    def test_no_numbers(self):
        assert hb.solve_verification("no numbers at all") is None

    def test_subtraction_negative(self):
        assert hb.solve_verification("three minus ten") == "-7.00"

    def test_multiply_by_zero(self):
        assert hb.solve_verification("five times zero") == "0.00"

    def test_forty_adds_nine(self):
        assert hb.solve_verification("forty adds nine") == "49.00"

    def test_compound_sub(self):
        assert hb.solve_verification("fifty reduces by twenty one") == "29.00"

    def test_takes_away(self):
        assert hb.solve_verification("twenty takes away five") == "15.00"


# ---------------------------------------------------------------------------
# State management tests
# ---------------------------------------------------------------------------

class TestStateManagement:
    def test_fresh_state(self, tmp_path):
        with patch.object(hb, "STATE_PATH", tmp_path / "nonexistent.json"):
            state = hb.load_state()
        assert state["last_post_time"] is None
        assert state["posts_made"] == 0
        assert state["engaged_post_ids"] == []
        assert state["runs"] == 0

    def test_load_existing_state(self, tmp_path):
        state_data = {"last_post_time": "2026-01-01T00:00:00+00:00", "posts_made": 5,
                      "runs": 10, "engaged_post_ids": ["1", "2"]}
        state_file = tmp_path / "state.json"
        state_file.write_text(json.dumps(state_data))
        with patch.object(hb, "STATE_PATH", state_file):
            state = hb.load_state()
        assert state["posts_made"] == 5
        assert state["runs"] == 10

    def test_can_post_fresh_state(self):
        state = {"last_post_time": None}
        assert hb.can_post(state) is True

    def test_can_post_too_soon(self):
        recent = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
        state = {"last_post_time": recent}
        assert hb.can_post(state) is False

    def test_can_post_enough_time(self):
        old = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
        state = {"last_post_time": old}
        assert hb.can_post(state) is True

    def test_can_comment_fresh_state(self):
        state = {"last_comment_time": None}
        assert hb.can_comment(state) is True

    def test_can_comment_too_soon(self):
        recent = (datetime.now(timezone.utc) - timedelta(seconds=10)).isoformat()
        state = {"last_comment_time": recent}
        assert hb.can_comment(state) is False

    def test_can_comment_enough_time(self):
        old = (datetime.now(timezone.utc) - timedelta(seconds=60)).isoformat()
        state = {"last_comment_time": old}
        assert hb.can_comment(state) is True

    def test_save_state_dry_run(self, tmp_path):
        state_file = tmp_path / "state.json"
        with patch.object(hb, "STATE_PATH", state_file):
            hb.save_state({"runs": 1}, dry_run=True)
        assert not state_file.exists()

    def test_save_state_writes(self, tmp_path):
        state_file = tmp_path / "state.json"
        with patch.object(hb, "STATE_PATH", state_file):
            hb.save_state({"runs": 1}, dry_run=False)
        assert state_file.exists()
        data = json.loads(state_file.read_text())
        assert data["runs"] == 1


# ---------------------------------------------------------------------------
# Context gathering tests
# ---------------------------------------------------------------------------

class TestContextGathering:
    def test_reads_manifest(self, tmp_path):
        manifest = {
            "categories": {
                "games_puzzles": {"apps": [{"title": "A"}, {"title": "B"}]},
                "audio_music": {"apps": [{"title": "C"}]},
            }
        }
        rankings = {"rankings": [
            {"name": "game1.html", "total": 90, "grade": "S"},
            {"name": "game2.html", "total": 50, "grade": "C"},
        ]}
        mstate = {"frame": 7, "history": [{"actions": {"molted": ["x.html"]},
                                            "highlights": {"focus": "test"}}]}

        m_path = tmp_path / "manifest.json"
        r_path = tmp_path / "rankings.json"
        s_path = tmp_path / "molter-state.json"
        m_path.write_text(json.dumps(manifest))
        r_path.write_text(json.dumps(rankings))
        s_path.write_text(json.dumps(mstate))

        with patch.object(hb, "MANIFEST_PATH", m_path), \
             patch.object(hb, "RANKINGS_PATH", r_path), \
             patch.object(hb, "MOLTER_STATE_PATH", s_path):
            ctx = hb.gather_rappterzoo_context()

        assert ctx["total_apps"] == 3
        assert ctx["avg_score"] == 70.0
        assert ctx["frame"] == 7
        assert ctx["top_games"][0]["name"] == "game1.html"
        assert ctx["recent_molts"] == ["x.html"]
        assert ctx["categories"]["games_puzzles"] == 2

    def test_handles_missing_files(self, tmp_path):
        with patch.object(hb, "MANIFEST_PATH", tmp_path / "nope.json"), \
             patch.object(hb, "RANKINGS_PATH", tmp_path / "nope2.json"), \
             patch.object(hb, "MOLTER_STATE_PATH", tmp_path / "nope3.json"):
            ctx = hb.gather_rappterzoo_context()
        assert ctx["total_apps"] == 0
        assert ctx["avg_score"] == 0


# ---------------------------------------------------------------------------
# HTTP transport tests
# ---------------------------------------------------------------------------

class TestMoltbookRequest:
    def test_get_request(self):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"posts": []}).encode()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp) as mock_open:
            result = hb._moltbook_request("GET", "/posts", api_key="test-key")
            assert result == {"posts": []}
            req = mock_open.call_args[0][0]
            assert req.get_header("Authorization") == "Bearer test-key"
            assert req.get_method() == "GET"

    def test_post_request(self):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"id": "123"}).encode()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = hb._moltbook_request("POST", "/posts", {"content": "hello"}, "key")
            assert result["id"] == "123"

    def test_http_error(self):
        err = hb.urllib.error.HTTPError(
            "http://x", 429, "Too Many", {}, None
        )
        err.read = MagicMock(return_value=b"rate limited")
        with patch("urllib.request.urlopen", side_effect=err):
            result = hb._moltbook_request("GET", "/posts")
            assert result["error"] is True
            assert result["status"] == 429

    def test_network_error(self):
        with patch("urllib.request.urlopen", side_effect=ConnectionError("offline")):
            result = hb._moltbook_request("GET", "/posts")
            assert result["error"] is True


# ---------------------------------------------------------------------------
# API key loading
# ---------------------------------------------------------------------------

class TestGetApiKey:
    def test_env_var(self):
        with patch.dict("os.environ", {"MOLTBOOK_API_KEY": "env-key"}):
            assert hb.get_api_key() == "env-key"

    def test_credentials_file(self, tmp_path):
        cred_dir = tmp_path / ".config" / "moltbook"
        cred_dir.mkdir(parents=True)
        (cred_dir / "credentials.json").write_text(json.dumps({"api_key": "file-key"}))
        with patch.dict("os.environ", {}, clear=True), \
             patch("pathlib.Path.home", return_value=tmp_path):
            # Need to clear MOLTBOOK_API_KEY specifically
            import os
            old = os.environ.pop("MOLTBOOK_API_KEY", None)
            try:
                assert hb.get_api_key() == "file-key"
            finally:
                if old:
                    os.environ["MOLTBOOK_API_KEY"] = old

    def test_no_key(self, tmp_path):
        with patch.dict("os.environ", {}, clear=True), \
             patch("pathlib.Path.home", return_value=tmp_path):
            import os
            old = os.environ.pop("MOLTBOOK_API_KEY", None)
            try:
                assert hb.get_api_key() is None
            finally:
                if old:
                    os.environ["MOLTBOOK_API_KEY"] = old


# ---------------------------------------------------------------------------
# Content generation tests
# ---------------------------------------------------------------------------

class TestGeneratePostContent:
    def test_template_fallback(self):
        with patch.object(hb, "detect_backend", return_value="unavailable"):
            ctx = {
                "total_apps": 642, "avg_score": 54.5, "frame": 13,
                "top_games": [{"name": "best.html", "score": 95, "grade": "S"}],
                "recent_molts": ["a.html", "b.html"],
            }
            content = hb._generate_post_content(ctx)
            assert "642" in content
            assert "54.5" in content
            assert "frame 13" in content
            assert "best.html" in content

    def test_template_no_molts(self):
        with patch.object(hb, "detect_backend", return_value="unavailable"):
            ctx = {
                "total_apps": 100, "avg_score": 50.0, "frame": 1,
                "top_games": [], "recent_molts": [],
            }
            content = hb._generate_post_content(ctx)
            assert "100" in content
            assert "molt" not in content.lower() or "molting engine" in content.lower()


class TestGenerateComment:
    def test_template_fallback(self):
        with patch.object(hb, "detect_backend", return_value="unavailable"):
            ctx = {"total_apps": 500}
            comment = hb._generate_comment("AI Agents", "Discussion about AI", ctx)
            assert "500" in comment
            assert len(comment) > 20


# ---------------------------------------------------------------------------
# Phase tests (integration-style, all mocked)
# ---------------------------------------------------------------------------

class TestPhasePost:
    def test_rate_limited(self):
        recent = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
        state = {"last_post_time": recent}
        result = hb.phase_post(state, "key", {}, verbose=False)
        assert result is False

    def test_dry_run(self, capsys):
        state = {"last_post_time": None}
        with patch.object(hb, "detect_backend", return_value="unavailable"):
            result = hb.phase_post(state, "key", {"total_apps": 10, "avg_score": 50,
                                                    "frame": 1, "top_games": [],
                                                    "recent_molts": []},
                                   dry_run=True)
        assert result is True
        captured = capsys.readouterr()
        assert "DRY RUN" in captured.out

    def test_successful_post(self):
        state = {"last_post_time": None, "posts_made": 0}
        mock_resp = {"id": "post-123"}
        with patch.object(hb, "detect_backend", return_value="unavailable"), \
             patch.object(hb, "_moltbook_request", return_value=mock_resp):
            result = hb.phase_post(state, "key",
                                   {"total_apps": 10, "avg_score": 50, "frame": 1,
                                    "top_games": [], "recent_molts": []})
        assert result is True
        assert state["posts_made"] == 1
        assert state["last_post_time"] is not None


class TestPhaseEngage:
    def test_dry_run(self, capsys):
        state = {"engaged_post_ids": [], "search_term_index": 0}
        result = hb.phase_engage(state, "key", {}, dry_run=True)
        assert result is True
        captured = capsys.readouterr()
        assert "DRY RUN" in captured.out

    def test_rotates_search_terms(self):
        state = {"engaged_post_ids": [], "search_term_index": 3}
        hb.phase_engage(state, "key", {}, dry_run=True)
        assert state["search_term_index"] == 4


class TestPhaseDms:
    def test_dry_run(self, capsys):
        state = {}
        result = hb.phase_dms(state, "key", dry_run=True)
        assert result is True
        captured = capsys.readouterr()
        assert "DRY RUN" in captured.out

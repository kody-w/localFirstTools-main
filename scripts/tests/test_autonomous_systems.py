"""
Tests for the autonomous platform systems:
  - activity_log.py
  - generate_feeds.py
  - subagent_swarm.py
  - rappterzoo_agent.py
  - process_agent_issues.py
  - automation-dashboard.html

All LLM/network calls are mocked — no network needed.
"""

import json
import os
import sys
from pathlib import Path
from unittest import mock

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS_DIR = str(ROOT / "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)


# ─── Helpers ──────────────────────────────────────────────────────────────────


SAMPLE_MANIFEST = {
    "categories": {
        "games_puzzles": {
            "title": "Games",
            "folder": "games-puzzles",
            "count": 2,
            "apps": [
                {
                    "title": "Test Game",
                    "file": "test-game.html",
                    "description": "A test",
                    "tags": ["canvas"],
                    "complexity": "simple",
                    "type": "game",
                    "featured": False,
                    "created": "2026-01-01",
                },
                {
                    "title": "Puzzle",
                    "file": "puzzle.html",
                    "description": "A puzzle",
                    "tags": ["logic"],
                    "complexity": "intermediate",
                    "type": "game",
                    "featured": True,
                    "created": "2026-01-15",
                },
            ],
        }
    }
}

SAMPLE_RANKINGS_NESTED = {
    "rankings": [{"file": "test-game.html", "score": 75}],
    "generated": "2026-01-01",
}

SAMPLE_RANKINGS_FLAT = [{"file": "test-game.html", "score": 75}]


# ─── TestActivityLog ─────────────────────────────────────────────────────────


class TestActivityLog:
    """Tests for scripts/activity_log.py."""

    def _import(self):
        import activity_log
        return activity_log

    def test_load_log_missing_file(self, tmp_path):
        """load_log returns empty structure when file does not exist."""
        mod = self._import()
        with mock.patch.object(mod, "LOG_PATH", tmp_path / "nope.json"):
            result = mod.load_log()
        assert result["entries"] == []
        assert result["stats"]["total_runs"] == 0

    def test_load_log_existing_file(self, tmp_path):
        """load_log reads from disk when file exists."""
        mod = self._import()
        log_file = tmp_path / "activity-log.json"
        data = {"entries": [{"id": "x"}], "stats": {"total_runs": 5,
                "total_apps_created": 0, "total_comments": 0, "total_molts": 0}}
        log_file.write_text(json.dumps(data))
        with mock.patch.object(mod, "LOG_PATH", log_file):
            result = mod.load_log()
        assert len(result["entries"]) == 1
        assert result["stats"]["total_runs"] == 5

    def test_log_activity_appends_entry(self, tmp_path):
        """log_activity creates an entry with the right fields."""
        mod = self._import()
        log_file = tmp_path / "activity-log.json"
        log_file.write_text(json.dumps({
            "entries": [],
            "stats": {"total_runs": 0, "total_apps_created": 0,
                      "total_comments": 0, "total_molts": 0},
        }))
        with mock.patch.object(mod, "LOG_PATH", log_file):
            entry = mod.log_activity("test-source", "did a thing",
                                     details={"apps_created": 3})
        assert entry["source"] == "test-source"
        assert entry["summary"] == "did a thing"
        assert "timestamp" in entry
        # Verify it wrote to disk
        saved = json.loads(log_file.read_text())
        assert len(saved["entries"]) == 1
        assert saved["stats"]["total_apps_created"] == 3

    def test_max_entries_trimming(self, tmp_path):
        """Entries beyond MAX_ENTRIES are trimmed (oldest dropped)."""
        mod = self._import()
        log_file = tmp_path / "activity-log.json"
        # Pre-populate with exactly MAX_ENTRIES entries
        existing = {"entries": [{"id": "old-{}".format(i)} for i in range(200)],
                    "stats": {"total_runs": 200, "total_apps_created": 0,
                              "total_comments": 0, "total_molts": 0}}
        log_file.write_text(json.dumps(existing))
        with mock.patch.object(mod, "LOG_PATH", log_file):
            mod.log_activity("trim-test", "one more entry")
        saved = json.loads(log_file.read_text())
        assert len(saved["entries"]) == 200
        # The oldest entry should have been dropped
        assert saved["entries"][0]["id"] != "old-0"
        assert saved["entries"][-1]["source"] == "trim-test"

    def test_stats_accumulation(self, tmp_path):
        """Stats accumulate across multiple log_activity calls."""
        mod = self._import()
        log_file = tmp_path / "activity-log.json"
        log_file.write_text(json.dumps({
            "entries": [],
            "stats": {"total_runs": 0, "total_apps_created": 0,
                      "total_comments": 0, "total_molts": 0},
        }))
        with mock.patch.object(mod, "LOG_PATH", log_file):
            mod.log_activity("s1", "run1", {"apps_created": 2, "comments": 1})
            mod.log_activity("s2", "run2", {"molts": 3, "comments": 5})
        saved = json.loads(log_file.read_text())
        assert saved["stats"]["total_runs"] == 2
        assert saved["stats"]["total_apps_created"] == 2
        assert saved["stats"]["total_comments"] == 6
        assert saved["stats"]["total_molts"] == 3

    def test_dry_run_skips_disk_write(self, tmp_path):
        """dry_run=True returns entry but does not write file."""
        mod = self._import()
        log_file = tmp_path / "activity-log.json"
        # File does not exist — dry_run should not create it
        with mock.patch.object(mod, "LOG_PATH", log_file):
            entry = mod.log_activity("dry", "test", dry_run=True)
        assert entry["source"] == "dry"
        assert not log_file.exists()


# ─── TestGenerateFeeds ───────────────────────────────────────────────────────


class TestGenerateFeeds:
    """Tests for scripts/generate_feeds.py."""

    def _import(self):
        import generate_feeds
        return generate_feeds

    def test_build_feed_json_schema(self):
        """build_feed_json produces valid Schema.org DataFeed structure."""
        mod = self._import()
        feed = mod.build_feed_json(SAMPLE_MANIFEST, SAMPLE_RANKINGS_FLAT)
        assert feed["@context"] == "https://schema.org"
        assert feed["@type"] == "DataFeed"
        assert "dataFeedElement" in feed
        assert isinstance(feed["dataFeedElement"], list)
        assert feed["publisher"]["name"] == "RappterZoo"

    def test_feed_json_item_count(self):
        """Number of DataFeedElement items matches total manifest apps."""
        mod = self._import()
        feed = mod.build_feed_json(SAMPLE_MANIFEST, [])
        total_apps = sum(
            len(c.get("apps", []))
            for c in SAMPLE_MANIFEST["categories"].values()
        )
        assert len(feed["dataFeedElement"]) == total_apps

    def test_feed_json_item_fields(self):
        """Each DataFeedElement item has required Schema.org fields."""
        mod = self._import()
        feed = mod.build_feed_json(SAMPLE_MANIFEST, SAMPLE_RANKINGS_FLAT)
        item = feed["dataFeedElement"][0]
        assert item["@type"] == "DataFeedItem"
        inner = item["item"]
        assert inner["@type"] == "VideoGame"  # type=game -> VideoGame
        assert "url" in inner
        assert inner["isAccessibleForFree"] is True

    def test_feed_json_rating_from_rankings(self):
        """Rankings scores appear as aggregateRating in feed items."""
        mod = self._import()
        feed = mod.build_feed_json(SAMPLE_MANIFEST, SAMPLE_RANKINGS_FLAT)
        # test-game.html has score=75
        game_item = [e for e in feed["dataFeedElement"]
                     if e["item"]["name"] == "Test Game"][0]
        assert game_item["item"]["aggregateRating"]["ratingValue"] == 75
        assert game_item["item"]["aggregateRating"]["bestRating"] == 100

    def test_build_feed_xml_valid_rss(self):
        """build_feed_xml produces valid RSS 2.0 structure."""
        mod = self._import()
        xml = mod.build_feed_xml(SAMPLE_MANIFEST, [])
        assert xml.startswith("<?xml version=")
        assert "<rss version=\"2.0\"" in xml
        assert "<channel>" in xml
        assert "<item>" in xml
        assert "</rss>" in xml

    def test_feed_xml_item_count(self):
        """RSS feed has correct number of <item> elements."""
        mod = self._import()
        xml = mod.build_feed_xml(SAMPLE_MANIFEST, [])
        item_count = xml.count("<item>")
        total_apps = sum(
            len(c.get("apps", []))
            for c in SAMPLE_MANIFEST["categories"].values()
        )
        assert item_count == total_apps

    def test_feed_xml_score_note(self):
        """RSS description includes score note when rankings provided."""
        mod = self._import()
        xml = mod.build_feed_xml(SAMPLE_MANIFEST, SAMPLE_RANKINGS_FLAT)
        assert "(score: 75/100)" in xml

    def test_load_rankings_nested_dict(self, tmp_path):
        """load_rankings extracts list from nested {'rankings': [...]}."""
        mod = self._import()
        f = tmp_path / "rankings.json"
        f.write_text(json.dumps(SAMPLE_RANKINGS_NESTED))
        result = mod.load_rankings(str(f))
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["file"] == "test-game.html"

    def test_load_rankings_flat_list(self, tmp_path):
        """load_rankings handles a plain list directly."""
        mod = self._import()
        f = tmp_path / "rankings.json"
        f.write_text(json.dumps(SAMPLE_RANKINGS_FLAT))
        result = mod.load_rankings(str(f))
        assert isinstance(result, list)
        assert len(result) == 1

    def test_load_rankings_unexpected_type(self, tmp_path):
        """load_rankings returns empty list for non-dict/non-list data."""
        mod = self._import()
        f = tmp_path / "rankings.json"
        f.write_text('"just a string"')
        result = mod.load_rankings(str(f))
        assert result == []

    def test_feed_json_empty_manifest(self):
        """build_feed_json handles manifest with no categories."""
        mod = self._import()
        feed = mod.build_feed_json({"categories": {}}, [])
        assert feed["dataFeedElement"] == []


# ─── TestSubagentSwarm ───────────────────────────────────────────────────────


class TestSubagentSwarm:
    """Tests for scripts/subagent_swarm.py."""

    def _import(self):
        # Patch subprocess and _has_copilot at import time to avoid side effects
        with mock.patch("subprocess.run"):
            import subagent_swarm
        return subagent_swarm

    def test_personas_count(self):
        """PERSONAS list has exactly 12 entries."""
        mod = self._import()
        assert len(mod.PERSONAS) == 12

    def test_personas_required_fields(self):
        """Every persona has id, name, bio, specialty, categories, experiences, style."""
        mod = self._import()
        required = {"id", "name", "bio", "specialty", "categories", "experiences", "style"}
        for p in mod.PERSONAS:
            missing = required - set(p.keys())
            assert not missing, "Persona '{}' missing: {}".format(p.get("id", "?"), missing)

    def test_persona_specialties_coverage(self):
        """Persona specialties cover create, comment, and molt."""
        mod = self._import()
        specialties = {p["specialty"] for p in mod.PERSONAS}
        assert "create" in specialties
        assert "comment" in specialties
        assert "molt" in specialties

    def test_persona_ids_unique(self):
        """All persona IDs are unique."""
        mod = self._import()
        ids = [p["id"] for p in mod.PERSONAS]
        assert len(ids) == len(set(ids))

    def test_parse_html_from_code_fence(self):
        """_parse_html extracts HTML from ```html code fence."""
        mod = self._import()
        raw = 'Here is the app:\n```html\n<!DOCTYPE html>\n<html><body>Hi</body></html>\n```\nDone!'
        result = mod._parse_html(raw)
        assert result is not None
        assert "<!DOCTYPE html>" in result

    def test_parse_html_raw_document(self):
        """_parse_html extracts raw <!DOCTYPE html>...</html>."""
        mod = self._import()
        raw = 'Some wrapper text\n<!DOCTYPE html>\n<html><body>Test</body></html>\nMore text'
        result = mod._parse_html(raw)
        assert result is not None
        assert result.startswith("<!DOCTYPE html>")

    def test_parse_html_strips_ansi(self):
        """_parse_html strips ANSI escape codes before parsing."""
        mod = self._import()
        raw = '\x1b[32m```html\n<!DOCTYPE html>\n<html><body>X</body></html>\n```\x1b[0m'
        result = mod._parse_html(raw)
        assert result is not None
        assert "\x1b" not in result

    def test_parse_html_returns_none_for_empty(self):
        """_parse_html returns None for empty/None input."""
        mod = self._import()
        assert mod._parse_html(None) is None
        assert mod._parse_html("") is None

    def test_parse_json_from_code_fence(self):
        """_parse_json extracts JSON from ```json code fence."""
        mod = self._import()
        raw = 'Result:\n```json\n{"key": "value"}\n```'
        result = mod._parse_json(raw)
        assert result == {"key": "value"}

    def test_parse_json_raw(self):
        """_parse_json parses raw JSON string."""
        mod = self._import()
        raw = '{"hello": "world"}'
        result = mod._parse_json(raw)
        assert result == {"hello": "world"}

    def test_parse_json_embedded_in_text(self):
        """_parse_json finds JSON object embedded in text."""
        mod = self._import()
        raw = 'Here is the result: {"status": "ok"} and more text'
        result = mod._parse_json(raw)
        assert result == {"status": "ok"}

    def test_parse_json_strips_ansi(self):
        """_parse_json strips ANSI codes before parsing."""
        mod = self._import()
        raw = '\x1b[36m{"a": 1}\x1b[0m'
        result = mod._parse_json(raw)
        assert result == {"a": 1}

    def test_parse_json_returns_none_for_empty(self):
        """_parse_json returns None for empty/None input."""
        mod = self._import()
        assert mod._parse_json(None) is None
        assert mod._parse_json("") is None

    def test_parse_json_returns_none_for_invalid(self):
        """_parse_json returns None for non-JSON text."""
        mod = self._import()
        assert mod._parse_json("just some words with no braces") is None

    def test_category_folders_match_expected(self):
        """CATEGORY_FOLDERS has all 11 categories."""
        mod = self._import()
        assert len(mod.CATEGORY_FOLDERS) == 11
        assert mod.CATEGORY_FOLDERS["games_puzzles"] == "games-puzzles"


# ─── TestAgentScript ─────────────────────────────────────────────────────────


class TestAgentScript:
    """Tests for scripts/rappterzoo_agent.py."""

    def _import(self):
        with mock.patch("subprocess.run"):
            import rappterzoo_agent
        return rappterzoo_agent

    def test_agent_id_set(self):
        """AGENT_ID is a non-empty string."""
        mod = self._import()
        assert isinstance(mod.AGENT_ID, str)
        assert len(mod.AGENT_ID) > 0

    def test_agent_version_set(self):
        """AGENT_VERSION follows semver-like pattern."""
        mod = self._import()
        assert isinstance(mod.AGENT_VERSION, str)
        parts = mod.AGENT_VERSION.split(".")
        assert len(parts) == 3

    def test_agent_name_set(self):
        """AGENT_NAME is set."""
        mod = self._import()
        assert isinstance(mod.AGENT_NAME, str)
        assert len(mod.AGENT_NAME) > 0

    def test_parse_html_from_code_fence(self):
        """_parse_html extracts HTML from code fences."""
        mod = self._import()
        raw = '```html\n<!DOCTYPE html>\n<html><head><title>T</title></head><body></body></html>\n```'
        result = mod._parse_html(raw)
        assert result is not None
        assert "<!DOCTYPE html>" in result

    def test_parse_html_raw_document(self):
        """_parse_html extracts raw HTML without code fences."""
        mod = self._import()
        raw = '<!DOCTYPE html>\n<html><head></head><body>Hello</body></html>'
        result = mod._parse_html(raw)
        assert result is not None
        assert result.startswith("<!DOCTYPE html>")

    def test_parse_html_none_input(self):
        """_parse_html returns None for None input."""
        mod = self._import()
        assert mod._parse_html(None) is None

    def test_parse_json_from_code_fence(self):
        """_parse_json extracts JSON from code fences."""
        mod = self._import()
        raw = '```json\n{"action": "create"}\n```'
        result = mod._parse_json(raw)
        assert result == {"action": "create"}

    def test_parse_json_raw(self):
        """_parse_json parses raw JSON."""
        mod = self._import()
        raw = '{"status": "ok"}'
        result = mod._parse_json(raw)
        assert result == {"status": "ok"}

    def test_parse_json_embedded_braces(self):
        """_parse_json extracts JSON from surrounding text."""
        mod = self._import()
        raw = 'Answer: {"found": true} end'
        result = mod._parse_json(raw)
        assert result == {"found": True}

    def test_parse_json_none_input(self):
        """_parse_json returns None for None input."""
        mod = self._import()
        assert mod._parse_json(None) is None

    def test_category_folders_present(self):
        """CATEGORY_FOLDERS is populated with 11 entries."""
        mod = self._import()
        assert len(mod.CATEGORY_FOLDERS) == 11

    def test_site_url_set(self):
        """SITE_URL points to GitHub Pages."""
        mod = self._import()
        assert "github.io" in mod.SITE_URL


# ─── TestIssueProcessor ─────────────────────────────────────────────────────


class TestIssueProcessor:
    """Tests for scripts/process_agent_issues.py."""

    def _import(self):
        import process_agent_issues
        return process_agent_issues

    def test_parse_issue_body_basic(self):
        """parse_issue_body splits ### headers into dict keys."""
        mod = self._import()
        body = "### App Title\n\nMy Cool App\n\n### Category\n\ngames_puzzles\n\n### Description\n\nA test app"
        result = mod.parse_issue_body(body)
        assert result["app_title"] == "My Cool App"
        assert result["category"] == "games_puzzles"
        assert result["description"] == "A test app"

    def test_parse_issue_body_multiline_value(self):
        """parse_issue_body handles multi-line values."""
        mod = self._import()
        body = "### Description\n\nLine one\nLine two\nLine three\n\n### Category\n\ngames_puzzles"
        result = mod.parse_issue_body(body)
        assert "Line one" in result["description"]
        assert "Line two" in result["description"]
        assert "Line three" in result["description"]
        assert result["category"] == "games_puzzles"

    def test_parse_issue_body_empty(self):
        """parse_issue_body returns empty dict for empty body."""
        mod = self._import()
        assert mod.parse_issue_body("") == {}
        assert mod.parse_issue_body(None) == {}

    def test_parse_issue_body_normalizes_keys(self):
        """parse_issue_body lowercases and underscores field names."""
        mod = self._import()
        body = "### Star Rating (Optional)\n\n5"
        result = mod.parse_issue_body(body)
        # The key should be normalized: "star_rating_(optional)" -> "rating"
        assert "rating" in result
        assert result["rating"] == "5"

    def test_parse_issue_body_app_filename_normalization(self):
        """parse_issue_body normalizes 'App Filename' to 'app_file'."""
        mod = self._import()
        body = "### App Filename\n\nmy-game.html"
        result = mod.parse_issue_body(body)
        assert "app_file" in result
        assert result["app_file"] == "my-game.html"

    def test_parse_issue_body_comment_text_normalization(self):
        """parse_issue_body normalizes 'Comment Text' to 'text'."""
        mod = self._import()
        body = "### Comment Text\n\nGreat game!"
        result = mod.parse_issue_body(body)
        assert "text" in result
        assert result["text"] == "Great game!"

    def test_category_folders_present(self):
        """Module has CATEGORY_FOLDERS dict."""
        mod = self._import()
        assert isinstance(mod.CATEGORY_FOLDERS, dict)
        assert "games_puzzles" in mod.CATEGORY_FOLDERS

    def test_claim_code_words_populated(self):
        """CLAIM_CODE_WORDS is a non-empty list of strings."""
        mod = self._import()
        assert len(mod.CLAIM_CODE_WORDS) > 10
        assert all(isinstance(w, str) for w in mod.CLAIM_CODE_WORDS)


# ─── TestDashboard ───────────────────────────────────────────────────────────


class TestDashboard:
    """Tests for apps/productivity/automation-dashboard.html."""

    DASHBOARD_PATH = ROOT / "apps" / "productivity" / "automation-dashboard.html"

    def test_file_exists(self):
        """Dashboard HTML file exists."""
        assert self.DASHBOARD_PATH.exists(), "automation-dashboard.html not found"

    def test_has_doctype(self):
        """Dashboard starts with <!DOCTYPE html>."""
        content = self.DASHBOARD_PATH.read_text()
        assert content.strip().startswith("<!DOCTYPE html>")

    def test_has_title(self):
        """Dashboard has a <title> tag."""
        content = self.DASHBOARD_PATH.read_text()
        assert "<title>" in content

    def test_has_viewport_meta(self):
        """Dashboard has viewport meta tag."""
        content = self.DASHBOARD_PATH.read_text()
        assert 'name="viewport"' in content

    def test_fetches_activity_log(self):
        """Dashboard fetches activity-log.json."""
        content = self.DASHBOARD_PATH.read_text()
        assert "activity-log.json" in content

    def test_has_rappterzoo_meta_tags(self):
        """Dashboard has required rappterzoo:* meta tags."""
        content = self.DASHBOARD_PATH.read_text()
        assert 'rappterzoo:author' in content
        assert 'rappterzoo:category' in content
        assert 'rappterzoo:type' in content

    def test_no_external_dependencies(self):
        """Dashboard does not reference external CDNs or .js/.css files."""
        content = self.DASHBOARD_PATH.read_text()
        # No external script src or link href (allow relative and data: URIs)
        import re
        ext_scripts = re.findall(r'<script[^>]+src=["\']https?://', content)
        ext_links = re.findall(r'<link[^>]+href=["\']https?://', content)
        assert not ext_scripts, "Found external script: {}".format(ext_scripts)
        assert not ext_links, "Found external stylesheet: {}".format(ext_links)

    def test_is_self_contained(self):
        """Dashboard has inline <style> and <script> blocks."""
        content = self.DASHBOARD_PATH.read_text()
        assert "<style>" in content
        assert "<script>" in content

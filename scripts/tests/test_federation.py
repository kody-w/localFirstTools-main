"""Tests for the Federation Agent.

All network calls mocked — no internet needed.
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


# ── Fixtures ──────────────────────────────────────────────────────

SAMPLE_FEDERATION = {
    "version": "1.0",
    "self": {"name": "RappterZoo", "url": "https://example.com", "total_apps": 100},
    "peers": [
        {
            "id": "test-peer",
            "name": "Test Peer",
            "url": "https://testpeer.example.com",
            "discovery_url": "https://testpeer.example.com/.well-known/feeddata-general",
            "status": "pending",
            "type": "test",
            "last_probed": None,
            "feeds_found": [],
            "content_themes": [],
            "apps_inspired": 0,
            "notes": "",
        },
        {
            "id": "active-peer",
            "name": "Active Peer",
            "url": "https://active.example.com",
            "discovery_url": "https://active.example.com/.well-known/feeddata-general",
            "status": "active",
            "type": "test",
            "last_probed": "2026-01-01T00:00:00Z",
            "feeds_found": [{"url": "https://active.example.com/feed.json", "type": "DataFeed", "name": "Feed", "items": 5}],
            "content_themes": ["travel", "planning", "maps"],
            "apps_inspired": 2,
            "notes": "",
        },
    ],
    "sync_history": [],
    "stats": {"total_probes": 0, "platforms_discovered": 1, "feeds_indexed": 0, "apps_inspired": 2, "last_sync": None},
}

SAMPLE_DATAFEED = json.dumps({
    "@context": "https://schema.org",
    "@type": "DataFeed",
    "name": "Test Feed",
    "dataFeedElement": [
        {
            "@type": "DataFeedItem",
            "item": {
                "@type": "WebApplication",
                "name": "Test App",
                "keywords": "travel, maps, planning",
                "applicationCategory": "Travel",
            },
        },
        {
            "@type": "DataFeedItem",
            "item": {
                "@type": "WebApplication",
                "name": "Another App",
                "keywords": "cooking, recipes",
                "applicationCategory": "Food",
            },
        },
    ],
})

SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
<title>Test RSS</title>
<item><title>Travel Guide</title><category>travel</category></item>
<item><title>Recipe Book</title><category>cooking</category></item>
</channel>
</rss>"""


# ── Import module under test ─────────────────────────────────────

# Mock _has_copilot before importing
with mock.patch.dict(os.environ, {}):
    import federation_agent


# ── TestRegistry ─────────────────────────────────────────────────

class TestRegistry:
    def test_load_federation_from_file(self, tmp_path):
        path = tmp_path / "fed.json"
        path.write_text(json.dumps(SAMPLE_FEDERATION))
        with mock.patch.object(federation_agent, "FEDERATION_PATH", path):
            data = federation_agent.load_federation()
        assert len(data["peers"]) == 2

    def test_load_federation_missing_file(self, tmp_path):
        path = tmp_path / "nope.json"
        with mock.patch.object(federation_agent, "FEDERATION_PATH", path):
            data = federation_agent.load_federation()
        assert data["peers"] == []
        assert "stats" in data

    def test_save_federation(self, tmp_path):
        path = tmp_path / "fed.json"
        with mock.patch.object(federation_agent, "FEDERATION_PATH", path):
            with mock.patch.object(federation_agent, "DRY_RUN", False):
                federation_agent.save_federation(SAMPLE_FEDERATION)
        assert path.exists()
        data = json.loads(path.read_text())
        assert len(data["peers"]) == 2

    def test_save_federation_dry_run(self, tmp_path):
        path = tmp_path / "fed.json"
        with mock.patch.object(federation_agent, "FEDERATION_PATH", path):
            with mock.patch.object(federation_agent, "DRY_RUN", True):
                federation_agent.save_federation(SAMPLE_FEDERATION)
        assert not path.exists()


# ── TestAddPeer ──────────────────────────────────────────────────

class TestAddPeer:
    def test_add_new_peer(self, tmp_path):
        path = tmp_path / "fed.json"
        path.write_text(json.dumps({"peers": [], "stats": {}, "sync_history": []}))
        with mock.patch.object(federation_agent, "FEDERATION_PATH", path):
            with mock.patch.object(federation_agent, "DRY_RUN", False):
                federation_agent.add_peer("https://new.example.com", name="New Site")
        data = json.loads(path.read_text())
        assert len(data["peers"]) == 1
        assert data["peers"][0]["name"] == "New Site"
        assert data["peers"][0]["url"] == "https://new.example.com"

    def test_add_duplicate_peer(self, tmp_path, capsys):
        path = tmp_path / "fed.json"
        path.write_text(json.dumps({"peers": [{"url": "https://dup.com", "name": "Dup"}],
                                     "stats": {}, "sync_history": []}))
        with mock.patch.object(federation_agent, "FEDERATION_PATH", path):
            federation_agent.add_peer("https://dup.com")
        out = capsys.readouterr().out
        assert "already registered" in out


# ── TestParsers ──────────────────────────────────────────────────

class TestParsers:
    def test_parse_html_from_code_fence(self):
        raw = "Here:\n```html\n<!DOCTYPE html><html><head><title>T</title></head><body></body></html>\n```"
        result = federation_agent._parse_html(raw)
        assert result is not None
        assert "<!DOCTYPE html>" in result

    def test_parse_html_none(self):
        assert federation_agent._parse_html(None) is None
        assert federation_agent._parse_html("") is None

    def test_parse_json_from_code_fence(self):
        raw = '```json\n{"key": "value"}\n```'
        result = federation_agent._parse_json_response(raw)
        assert result == {"key": "value"}

    def test_parse_json_raw(self):
        result = federation_agent._parse_json_response('{"a": 1}')
        assert result == {"a": 1}

    def test_parse_json_none(self):
        assert federation_agent._parse_json_response(None) is None


# ── TestDiscover ─────────────────────────────────────────────────

class TestDiscover:
    def test_discover_active_nlweb(self, tmp_path):
        path = tmp_path / "fed.json"
        path.write_text(json.dumps(SAMPLE_FEDERATION))
        with mock.patch.object(federation_agent, "FEDERATION_PATH", path):
            with mock.patch.object(federation_agent, "DRY_RUN", False):
                with mock.patch.object(federation_agent, "_fetch") as mock_fetch:
                    mock_fetch.return_value = SAMPLE_DATAFEED
                    fed = federation_agent.discover()
        # Both peers should be active since fetch returns data
        active = [p for p in fed["peers"] if p["status"] == "active"]
        assert len(active) == 2

    def test_discover_unreachable(self, tmp_path):
        path = tmp_path / "fed.json"
        fed_data = {"peers": [{"id": "dead", "name": "Dead", "url": "https://dead.example.com",
                                "discovery_url": "https://dead.example.com/.well-known/feeddata-general",
                                "status": "pending", "feeds_found": [], "content_themes": [],
                                "apps_inspired": 0, "last_probed": None, "type": "test", "notes": ""}],
                     "stats": {"total_probes": 0, "platforms_discovered": 0, "feeds_indexed": 0,
                               "apps_inspired": 0, "last_sync": None}, "sync_history": []}
        path.write_text(json.dumps(fed_data))
        with mock.patch.object(federation_agent, "FEDERATION_PATH", path):
            with mock.patch.object(federation_agent, "DRY_RUN", False):
                with mock.patch.object(federation_agent, "_fetch", return_value=None):
                    fed = federation_agent.discover()
        assert fed["peers"][0]["status"] == "unreachable"

    def test_discover_rss_fallback(self, tmp_path):
        path = tmp_path / "fed.json"
        fed_data = {"peers": [{"id": "rss", "name": "RSS Site", "url": "https://rss.example.com",
                                "discovery_url": "https://rss.example.com/.well-known/feeddata-general",
                                "status": "pending", "feeds_found": [], "content_themes": [],
                                "apps_inspired": 0, "last_probed": None, "type": "test", "notes": ""}],
                     "stats": {"total_probes": 0, "platforms_discovered": 0, "feeds_indexed": 0,
                               "apps_inspired": 0, "last_sync": None}, "sync_history": []}
        path.write_text(json.dumps(fed_data))

        def mock_fetch_fn(url, timeout=15):
            if ".well-known" in url:
                return None
            if "feed.xml" in url or url.endswith("/feed"):
                return SAMPLE_RSS
            return None

        with mock.patch.object(federation_agent, "FEDERATION_PATH", path):
            with mock.patch.object(federation_agent, "DRY_RUN", False):
                with mock.patch.object(federation_agent, "_fetch", side_effect=mock_fetch_fn):
                    fed = federation_agent.discover()
        assert fed["peers"][0]["status"] == "rss-only"


# ── TestScan ─────────────────────────────────────────────────────

class TestScan:
    def test_scan_extracts_themes(self, tmp_path):
        path = tmp_path / "fed.json"
        fed_data = {
            "peers": [{"id": "a", "name": "A", "url": "https://a.com", "status": "active",
                        "feeds_found": [{"url": "https://a.com/feed.json", "type": "DataFeed", "name": "Feed"}],
                        "content_themes": [], "apps_inspired": 0, "last_probed": None, "type": "t", "notes": ""}],
            "stats": {"total_probes": 0, "platforms_discovered": 1, "feeds_indexed": 0,
                      "apps_inspired": 0, "last_sync": None}, "sync_history": []}
        path.write_text(json.dumps(fed_data))
        with mock.patch.object(federation_agent, "FEDERATION_PATH", path):
            with mock.patch.object(federation_agent, "DRY_RUN", False):
                with mock.patch.object(federation_agent, "_fetch", return_value=SAMPLE_DATAFEED):
                    fed = federation_agent.scan(fed_data)
        themes = fed["peers"][0]["content_themes"]
        assert len(themes) > 0
        assert "travel" in themes or "Travel" in [t.title() for t in themes]


# ── TestInspire ──────────────────────────────────────────────────

class TestInspire:
    def test_inspire_dry_run(self, tmp_path):
        path = tmp_path / "fed.json"
        path.write_text(json.dumps(SAMPLE_FEDERATION))
        with mock.patch.object(federation_agent, "FEDERATION_PATH", path):
            with mock.patch.object(federation_agent, "DRY_RUN", True):
                results = federation_agent.inspire(count=2)
        assert len(results) == 2
        assert all(r.get("dry_run") for r in results)

    def test_inspire_uses_themes(self, tmp_path):
        path = tmp_path / "fed.json"
        path.write_text(json.dumps(SAMPLE_FEDERATION))
        with mock.patch.object(federation_agent, "FEDERATION_PATH", path):
            with mock.patch.object(federation_agent, "DRY_RUN", True):
                results = federation_agent.inspire(count=1)
        assert results[0]["themes"]
        assert results[0]["sources"]


# ── TestCategoryFolders ──────────────────────────────────────────

class TestCategoryFolders:
    def test_all_categories_mapped(self):
        expected = {"visual_art", "3d_immersive", "audio_music", "generative_art",
                    "games_puzzles", "particle_physics", "creative_tools",
                    "experimental_ai", "educational_tools", "data_tools", "productivity"}
        assert set(federation_agent.CATEGORY_FOLDERS.keys()) == expected


# ── TestDashboard ────────────────────────────────────────────────

class TestFederationHub:
    def test_file_exists(self):
        path = ROOT / "apps" / "productivity" / "federation-hub.html"
        assert path.exists()

    def test_has_doctype(self):
        html = (ROOT / "apps" / "productivity" / "federation-hub.html").read_text()
        assert "<!DOCTYPE html>" in html

    def test_fetches_federation_json(self):
        html = (ROOT / "apps" / "productivity" / "federation-hub.html").read_text()
        assert "federation.json" in html

    def test_has_canvas(self):
        html = (ROOT / "apps" / "productivity" / "federation-hub.html").read_text()
        assert "<canvas" in html

    def test_no_external_deps(self):
        html = (ROOT / "apps" / "productivity" / "federation-hub.html").read_text()
        assert "cdn" not in html.lower() or "cdn" in html.lower().split("<!--")[0] == False
        assert '<script src=' not in html
        assert '<link rel="stylesheet" href=' not in html

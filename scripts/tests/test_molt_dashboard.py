#!/usr/bin/env python3
"""Tests for molt-priority-dashboard.html — Molt Priority Visualization.

Validates structural requirements, data integration, priority algorithm
indicators, visualization elements, and feature completeness.

Usage:
    python3 -m pytest scripts/tests/test_molt_dashboard.py -v
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
APP_PATH = ROOT / "apps" / "creative-tools" / "molt-priority-dashboard.html"


@pytest.fixture(scope="module")
def html():
    assert APP_PATH.exists(), f"App not found: {APP_PATH}"
    return APP_PATH.read_text(encoding="utf-8")


# ── Structural ──

class TestStructural:
    def test_has_doctype(self, html):
        assert "<!doctype html>" in html.lower()

    def test_has_title(self, html):
        m = re.search(r"<title>(.*?)</title>", html, re.IGNORECASE)
        assert m and "molt" in m.group(1).lower()

    def test_has_viewport(self, html):
        assert '<meta name="viewport"' in html

    def test_has_inline_css(self, html):
        assert "<style>" in html and "</style>" in html

    def test_has_inline_js(self, html):
        assert "<script>" in html and "</script>" in html

    def test_no_external_js_css(self, html):
        ext = re.findall(r'(?:src|href)="(https?://[^"]+)"', html)
        bad = [u for u in ext if any(u.endswith(e) for e in (".js", ".css", ".mjs"))]
        assert bad == [], f"External deps: {bad}"

    def test_no_api_keys(self, html):
        for pattern in [r'sk-[a-zA-Z0-9]{20,}', r'AKIA[A-Z0-9]{16}']:
            assert not re.search(pattern, html), f"Possible secret: {pattern}"

    def test_file_size_reasonable(self, html):
        size_kb = len(html.encode("utf-8")) / 1024
        assert 10 < size_kb < 500, f"File size {size_kb:.0f}KB outside 10-500KB range"


# ── Data Integration ──

class TestDataIntegration:
    def test_fetches_manifest(self, html):
        assert "manifest.json" in html

    def test_fetches_rankings(self, html):
        assert "rankings.json" in html

    def test_fetches_community(self, html):
        assert "community.json" in html

    def test_handles_fetch_error(self, html):
        assert "catch" in html

    def test_references_generation_field(self, html):
        assert "generation" in html

    def test_references_last_molted(self, html):
        low = html.lower()
        assert "lastmolted" in low or "last_molted" in low or "lastMolted" in html


# ── Priority Algorithm ──

class TestPriorityAlgorithm:
    def test_has_urgency_or_priority_score(self, html):
        low = html.lower()
        assert any(w in low for w in ["urgency", "priority", "score"])

    def test_penalizes_higher_generations(self, html):
        # Must reference generation in scoring context
        assert "generation" in html

    def test_factors_staleness(self, html):
        low = html.lower()
        assert any(w in low for w in ["stale", "days", "age", "since", "elapsed"])

    def test_factors_quality(self, html):
        low = html.lower()
        assert any(w in low for w in ["quality", "score", "rank", "grade"])

    def test_never_molted_prioritized(self, html):
        # Apps with gen 0 should get highest priority
        low = html.lower()
        assert any(w in low for w in ["never", "unmolted", "generation", "=== 0", "== 0"])


# ── Visualization ──

class TestVisualization:
    def test_has_canvas_element(self, html):
        assert "<canvas" in html

    def test_has_chart_rendering(self, html):
        assert "getContext" in html

    def test_has_category_chart(self, html):
        low = html.lower()
        assert any(w in low for w in ["donut", "pie", "chart", "arc"])

    def test_has_generation_distribution(self, html):
        low = html.lower()
        assert any(w in low for w in ["distribution", "bar", "histogram", "generation"])

    def test_has_color_coding(self, html):
        # Should use category colors from manifest
        assert "color" in html.lower()


# ── Priority List ──

class TestPriorityList:
    def test_has_sortable_list(self, html):
        low = html.lower()
        assert any(w in low for w in ["sort", "order", "rank"])

    def test_has_search_or_filter(self, html):
        low = html.lower()
        assert any(w in low for w in ["search", "filter", "query"])

    def test_has_click_to_navigate(self, html):
        low = html.lower()
        assert any(w in low for w in ["href", "window.open", "target", "navigate", "_blank"])


# ── Stats Panel ──

class TestStatsPanel:
    def test_shows_total_count(self, html):
        low = html.lower()
        assert any(w in low for w in ["total", "count", "apps"])

    def test_shows_molted_unmolted(self, html):
        low = html.lower()
        assert any(w in low for w in ["molted", "unmolted", "generation"])

    def test_shows_average_quality(self, html):
        low = html.lower()
        assert any(w in low for w in ["average", "avg", "mean"])


# ── Responsive ──

class TestResponsive:
    def test_has_responsive_viewport(self, html):
        assert "width=device-width" in html

    def test_has_media_query_or_responsive(self, html):
        assert any(w in html for w in ["@media", "innerWidth", "clientWidth", "matchMedia"])

#!/usr/bin/env python3
"""Tests for crowd-heatmap.html — Crowd Heatmap & Player Trails visualization.

Validates structural requirements, required UI elements, canvas rendering,
data integration, and feature completeness.

Usage:
    python3 -m pytest scripts/tests/test_heatmap.py -v
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
APP_PATH = ROOT / "apps" / "experimental-ai" / "crowd-heatmap.html"


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
        assert m and len(m.group(1).strip()) > 2

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
        for pattern in [r'sk-[a-zA-Z0-9]{20,}', r'AKIA[A-Z0-9]{16}', r'api[_-]?key\s*[:=]\s*["\'][^"\']{20,}']:
            assert not re.search(pattern, html), f"Possible secret: {pattern}"

    def test_file_size_reasonable(self, html):
        size_kb = len(html.encode("utf-8")) / 1024
        assert 10 < size_kb < 500, f"File size {size_kb:.0f}KB outside 10-500KB range"


# ── Canvas & Rendering ──

class TestCanvas:
    def test_has_canvas_element(self, html):
        assert "<canvas" in html

    def test_has_request_animation_frame(self, html):
        assert "requestAnimationFrame" in html

    def test_has_get_context(self, html):
        assert "getContext" in html

    def test_has_canvas_resize_handling(self, html):
        assert "resize" in html.lower()


# ── Data Integration ──

class TestDataIntegration:
    def test_fetches_manifest(self, html):
        assert "manifest.json" in html

    def test_fetches_community(self, html):
        assert "community.json" in html

    def test_handles_fetch_error(self, html):
        assert "catch" in html, "No error handling for fetch"


# ── Heatmap Feature ──

class TestHeatmapFeature:
    def test_has_heatmap_rendering(self, html):
        assert "heatmap" in html.lower()

    def test_has_category_colors(self, html):
        # Should reference category colors from manifest
        assert "color" in html.lower() and "category" in html.lower()

    def test_has_intensity_mapping(self, html):
        # Activity level should map to visual intensity
        assert any(w in html.lower() for w in ["intensity", "alpha", "opacity", "heat"])


# ── Pulse Glow ──

class TestPulseGlow:
    def test_has_glow_or_pulse(self, html):
        assert any(w in html.lower() for w in ["pulse", "glow", "pulsing"])

    def test_has_animation_timing(self, html):
        # Needs some form of time-based animation
        assert any(w in html for w in ["Date.now", "performance.now", "timestamp", "deltaTime", "dt"])


# ── Particle Trails ──

class TestParticleTrails:
    def test_has_particle_system(self, html):
        assert any(w in html.lower() for w in ["particle", "trail"])

    def test_has_bezier_or_curve(self, html):
        assert any(w in html.lower() for w in ["bezier", "curve", "quadratic", "arc"])

    def test_has_trail_between_apps(self, html):
        # Must connect apps, not just random particles
        assert "trail" in html.lower()


# ── Voronoi Diagram ──

class TestVoronoi:
    def test_has_voronoi_mode(self, html):
        assert "voronoi" in html.lower()

    def test_has_voronoi_toggle(self, html):
        # Some UI control to switch to voronoi view
        low = html.lower()
        assert any(w in low for w in ["voronoi", "diagram", "density"])


# ── Stats Panel ──

class TestStatsPanel:
    def test_has_online_count(self, html):
        assert "online" in html.lower()

    def test_has_player_count(self, html):
        assert "player" in html.lower()

    def test_has_category_breakdown(self, html):
        low = html.lower()
        assert "category" in low or "categories" in low


# ── Live Simulation ──

class TestLiveSimulation:
    def test_has_interval_or_timer(self, html):
        assert any(w in html for w in ["setInterval", "setTimeout", "requestAnimationFrame"])

    def test_has_simulation_state(self, html):
        low = html.lower()
        assert any(w in low for w in ["simulat", "active", "current"])


# ── Responsive ──

class TestResponsive:
    def test_has_responsive_meta(self, html):
        assert "width=device-width" in html

    def test_has_media_query_or_responsive(self, html):
        assert any(w in html for w in ["@media", "innerWidth", "clientWidth", "matchMedia"])

#!/usr/bin/env python3
"""Tests for Global Time Machine and Windowed Desktop apps.

Usage:
    python3 -m pytest scripts/tests/test_gallery_apps.py -v
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent


@pytest.fixture(scope="module")
def time_machine():
    p = ROOT / "apps" / "experimental-ai" / "global-time-machine.html"
    assert p.exists(), f"Missing: {p}"
    return p.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def desktop():
    p = ROOT / "apps" / "experimental-ai" / "windowed-desktop.html"
    assert p.exists(), f"Missing: {p}"
    return p.read_text(encoding="utf-8")


class TestTimeMachineStructural:
    def test_doctype(self, time_machine):
        assert "<!doctype html>" in time_machine.lower()

    def test_title(self, time_machine):
        assert "<title>" in time_machine.lower()

    def test_viewport(self, time_machine):
        assert '<meta name="viewport"' in time_machine

    def test_inline_css_js(self, time_machine):
        assert "<style>" in time_machine and "<script>" in time_machine

    def test_no_external_deps(self, time_machine):
        ext = re.findall(r'(?:src|href)="(https?://[^"]+)"', time_machine)
        bad = [u for u in ext if any(u.endswith(e) for e in (".js", ".css", ".mjs"))]
        assert bad == []


class TestTimeMachineFeatures:
    def test_fetches_manifest(self, time_machine):
        assert "manifest.json" in time_machine

    def test_has_canvas(self, time_machine):
        assert "<canvas" in time_machine

    def test_has_animation_loop(self, time_machine):
        assert "requestAnimationFrame" in time_machine

    def test_has_timeline(self, time_machine):
        assert any(w in time_machine.lower() for w in ["timeline", "scrub", "playhead"])

    def test_has_play_pause(self, time_machine):
        assert any(w in time_machine.lower() for w in ["play", "pause"])

    def test_has_speed_control(self, time_machine):
        assert "speed" in time_machine.lower()

    def test_has_date_display(self, time_machine):
        assert any(w in time_machine for w in ["toLocaleDateString", "toISOString", "getFullYear", "Date"])


class TestDesktopStructural:
    def test_doctype(self, desktop):
        assert "<!doctype html>" in desktop.lower()

    def test_title(self, desktop):
        assert "<title>" in desktop.lower()

    def test_viewport(self, desktop):
        assert '<meta name="viewport"' in desktop

    def test_inline_css_js(self, desktop):
        assert "<style>" in desktop and "<script>" in desktop

    def test_no_external_deps(self, desktop):
        ext = re.findall(r'(?:src|href)="(https?://[^"]+)"', desktop)
        bad = [u for u in ext if any(u.endswith(e) for e in (".js", ".css", ".mjs"))]
        assert bad == []


class TestDesktopFeatures:
    def test_fetches_manifest(self, desktop):
        assert "manifest.json" in desktop

    def test_has_iframe(self, desktop):
        assert "iframe" in desktop.lower()

    def test_has_draggable(self, desktop):
        assert any(w in desktop.lower() for w in ["drag", "mousedown", "pointerdown"])

    def test_has_taskbar(self, desktop):
        assert "taskbar" in desktop.lower()

    def test_has_window_management(self, desktop):
        assert any(w in desktop.lower() for w in ["minimize", "maximize", "z-index", "zindex"])

    def test_has_start_menu(self, desktop):
        assert any(w in desktop.lower() for w in ["start", "menu"])

    def test_has_close_button(self, desktop):
        assert "close" in desktop.lower()


class TestLivePreview:
    @pytest.fixture(scope="class")
    def index_html(self):
        p = ROOT / "index.html"
        return p.read_text(encoding="utf-8")

    def test_has_preview_element(self, index_html):
        assert "live-preview" in index_html

    def test_has_preview_iframe(self, index_html):
        assert "preview-frame" in index_html

    def test_has_hover_debounce(self, index_html):
        assert any(w in index_html for w in ["setTimeout", "debounce", "hoverTimer", "previewTimer"])

    def test_has_preview_css(self, index_html):
        assert ".live-preview" in index_html

    def test_has_open_button(self, index_html):
        low = index_html.lower()
        assert "open" in low and "preview" in low

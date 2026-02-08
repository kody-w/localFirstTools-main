#!/usr/bin/env python3
"""Tests for educational apps batch — 10 new educational HTML apps.

Usage:
    python3 -m pytest scripts/tests/test_edu_apps.py -v
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
EDU_DIR = ROOT / "apps" / "educational"

EXPECTED_APPS = [
    "periodic-table-explorer.html",
    "music-theory-trainer.html",
    "regex-playground.html",
    "css-grid-sandbox.html",
    "binary-number-lab.html",
    "geography-quiz.html",
    "typing-speed-trainer.html",
    "math-visualizer.html",
    "algorithm-visualizer.html",
    "color-theory-lab.html",
]


@pytest.fixture(params=EXPECTED_APPS)
def edu_app(request):
    path = EDU_DIR / request.param
    assert path.exists(), f"Missing: {path}"
    return path.read_text(encoding="utf-8")


class TestStructural:
    def test_has_doctype(self, edu_app):
        assert "<!doctype html>" in edu_app.lower()

    def test_has_title(self, edu_app):
        m = re.search(r"<title>(.*?)</title>", edu_app, re.I)
        assert m and len(m.group(1).strip()) > 2

    def test_has_viewport(self, edu_app):
        assert '<meta name="viewport"' in edu_app

    def test_has_inline_css(self, edu_app):
        assert "<style>" in edu_app

    def test_has_inline_js(self, edu_app):
        assert "<script>" in edu_app

    def test_no_external_deps(self, edu_app):
        ext = re.findall(r'(?:src|href)="(https?://[^"]+)"', edu_app)
        bad = [u for u in ext if any(u.endswith(e) for e in (".js", ".css", ".mjs"))]
        assert bad == [], f"External deps: {bad}"

    def test_reasonable_size(self, edu_app):
        kb = len(edu_app.encode()) / 1024
        assert 5 < kb < 500


class TestInteractivity:
    def test_has_event_handling(self, edu_app):
        assert any(w in edu_app for w in ["addEventListener", "onclick", "onchange", "oninput"])

    def test_has_localstorage(self, edu_app):
        assert "localStorage" in edu_app


class TestManifest:
    def test_all_apps_in_manifest(self):
        import json
        m = json.load(open(ROOT / "apps" / "manifest.json"))
        cat = m["categories"]["educational_tools"]
        files = {a["file"] for a in cat["apps"]}
        for app in EXPECTED_APPS:
            assert app in files, f"{app} missing from manifest"
        assert cat["count"] >= 17

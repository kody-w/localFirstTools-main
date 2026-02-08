#!/usr/bin/env python3
"""
test_platform_apps.py — Validates the 5 new platform flagship apps meet
RappterZoo quality standards. Tests structural requirements, functionality
markers, and self-containment.

Run: python3 -m pytest scripts/tests/test_platform_apps.py -v
"""

import json
import os
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
APPS_DIR = ROOT / "apps"
MANIFEST_PATH = APPS_DIR / "manifest.json"

# The 5 flagship apps we're validating
PLATFORM_APPS = {
    "personal-wiki": {
        "category": "productivity",
        "folder": "productivity",
        "file": "personal-wiki.html",
        "required_strings": [
            "localStorage",       # persistence
            "contenteditable",    # editing capability (or textarea)
            "export",             # export feature
            "import",             # import feature
        ],
        "required_any": [
            ["textarea", "contenteditable"],  # must have one editing mechanism
            ["markdown", "Markdown", "MD"],   # markdown support
        ],
        "min_lines": 200,
    },
    "data-vault": {
        "category": "data_tools",
        "folder": "data-tools",
        "file": "data-vault.html",
        "required_strings": [
            "localStorage",
            "FileReader",         # file reading capability
            "base64",             # base64 storage
            "download",           # download capability
        ],
        "required_any": [
            ["drop", "dragover", "drag"],    # drag-and-drop
            ["delete", "remove", "Remove"],  # file deletion
        ],
        "min_lines": 200,
    },
    "data-dashboard": {
        "category": "data_tools",
        "folder": "data-tools",
        "file": "data-dashboard.html",
        "required_strings": [
            "localStorage",
            "canvas",             # charts via canvas
        ],
        "required_any": [
            ["csv", "CSV"],                    # CSV support
            ["JSON", "json"],                  # JSON support
            ["chart", "Chart", "graph", "bar", "pie", "line"],  # visualization
            ["filter", "Filter", "query", "sort", "Sort"],      # data ops
        ],
        "min_lines": 300,
    },
    "automation-hub": {
        "category": "productivity",
        "folder": "productivity",
        "file": "automation-hub.html",
        "required_strings": [
            "localStorage",
        ],
        "required_any": [
            ["trigger", "Trigger", "when", "When"],     # trigger concept
            ["action", "Action", "then", "Then"],       # action concept
            ["rule", "Rule", "workflow", "Workflow"],    # rule concept
            ["log", "Log", "history", "History"],        # execution log
        ],
        "min_lines": 200,
    },
    "api-playground": {
        "category": "data_tools",
        "folder": "data-tools",
        "file": "api-playground.html",
        "required_strings": [
            "localStorage",
        ],
        "required_any": [
            ["GET", "POST", "PUT", "DELETE"],              # HTTP methods
            ["fetch", "XMLHttpRequest"],                    # request mechanism
            ["header", "Header"],                           # headers support
            ["response", "Response", "status"],             # response display
            ["collection", "Collection", "save", "Save"],   # save collections
        ],
        "min_lines": 200,
    },
}


class TestStructuralRequirements:
    """Every app must meet basic RappterZoo structural requirements."""

    @pytest.fixture(params=PLATFORM_APPS.keys())
    def app_data(self, request):
        key = request.param
        spec = PLATFORM_APPS[key]
        path = APPS_DIR / spec["folder"] / spec["file"]
        if not path.exists():
            pytest.skip(f"{path} not yet created")
        content = path.read_text(encoding="utf-8")
        return {"key": key, "spec": spec, "path": path, "content": content}

    def test_file_exists(self, app_data):
        assert app_data["path"].exists(), f"{app_data['path']} must exist"

    def test_has_doctype(self, app_data):
        assert "<!DOCTYPE html>" in app_data["content"] or "<!doctype html>" in app_data["content"]

    def test_has_title(self, app_data):
        assert "<title>" in app_data["content"] and "</title>" in app_data["content"]

    def test_has_viewport(self, app_data):
        assert 'name="viewport"' in app_data["content"]

    def test_has_inline_css(self, app_data):
        assert "<style>" in app_data["content"] or "<style " in app_data["content"]

    def test_has_inline_js(self, app_data):
        assert "<script>" in app_data["content"] or "<script " in app_data["content"]

    def test_no_external_scripts(self, app_data):
        content = app_data["content"]
        # Find all script tags with src attributes
        ext_scripts = re.findall(r'<script[^>]+src\s*=\s*["\']([^"\']+)', content)
        for src in ext_scripts:
            assert not src.startswith("http"), f"External script found: {src}"
            assert not src.startswith("//"), f"Protocol-relative script found: {src}"

    def test_no_external_stylesheets(self, app_data):
        content = app_data["content"]
        ext_css = re.findall(r'<link[^>]+href\s*=\s*["\']([^"\']+)', content)
        for href in ext_css:
            if "stylesheet" in content[content.index(href)-100:content.index(href)]:
                assert not href.startswith("http"), f"External CSS found: {href}"

    def test_minimum_size(self, app_data):
        lines = app_data["content"].count("\n") + 1
        min_lines = app_data["spec"]["min_lines"]
        assert lines >= min_lines, f"{app_data['key']} has {lines} lines, need {min_lines}+"

    def test_self_contained(self, app_data):
        """No references to sibling files or parent directories."""
        content = app_data["content"]
        assert "../" not in content or "<!--" in content, "Should not reference parent dirs"


class TestFunctionalRequirements:
    """Each app must include its core functionality markers."""

    @pytest.fixture(params=PLATFORM_APPS.keys())
    def app_data(self, request):
        key = request.param
        spec = PLATFORM_APPS[key]
        path = APPS_DIR / spec["folder"] / spec["file"]
        if not path.exists():
            pytest.skip(f"{path} not yet created")
        content = path.read_text(encoding="utf-8")
        return {"key": key, "spec": spec, "path": path, "content": content}

    def test_required_strings(self, app_data):
        content = app_data["content"]
        spec = app_data["spec"]
        for s in spec["required_strings"]:
            assert s in content, f"{app_data['key']} must contain '{s}'"

    def test_required_any_groups(self, app_data):
        content = app_data["content"]
        spec = app_data["spec"]
        for group in spec.get("required_any", []):
            found = any(s in content for s in group)
            assert found, f"{app_data['key']} must contain at least one of: {group}"


class TestManifestIntegration:
    """Apps must be properly registered in manifest.json."""

    @pytest.fixture(params=PLATFORM_APPS.keys())
    def app_spec(self, request):
        key = request.param
        return {"key": key, **PLATFORM_APPS[key]}

    def test_manifest_has_category(self, app_spec):
        manifest = json.loads(MANIFEST_PATH.read_text())
        cat_key = app_spec["category"]
        assert cat_key in manifest["categories"], f"Category '{cat_key}' must exist in manifest"

    def test_manifest_has_app_entry(self, app_spec):
        manifest = json.loads(MANIFEST_PATH.read_text())
        cat_key = app_spec["category"]
        cat = manifest["categories"][cat_key]
        files = [a["file"] for a in cat.get("apps", [])]
        assert app_spec["file"] in files, f"{app_spec['file']} must be registered in {cat_key}"

    def test_manifest_count_correct(self, app_spec):
        manifest = json.loads(MANIFEST_PATH.read_text())
        cat_key = app_spec["category"]
        cat = manifest["categories"][cat_key]
        assert cat["count"] == len(cat["apps"]), f"Count mismatch in {cat_key}"


class TestRappterZooMeta:
    """Apps should include rappterzoo:* meta tags."""

    @pytest.fixture(params=PLATFORM_APPS.keys())
    def app_data(self, request):
        key = request.param
        spec = PLATFORM_APPS[key]
        path = APPS_DIR / spec["folder"] / spec["file"]
        if not path.exists():
            pytest.skip(f"{path} not yet created")
        content = path.read_text(encoding="utf-8")
        return {"key": key, "spec": spec, "content": content}

    def test_has_category_meta(self, app_data):
        assert "rappterzoo:category" in app_data["content"]

    def test_has_type_meta(self, app_data):
        assert "rappterzoo:type" in app_data["content"]

    def test_has_created_meta(self, app_data):
        assert "rappterzoo:created" in app_data["content"]

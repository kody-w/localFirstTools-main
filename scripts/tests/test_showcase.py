"""Validation tests for the 10 showcase apps."""
import os
import re
import json
import subprocess
import sys

REPO_ROOT = os.path.join(os.path.dirname(__file__), '..', '..')
MANIFEST_PATH = os.path.join(REPO_ROOT, 'apps', 'manifest.json')

# App definitions: (filename, category_folder, min_size_kb, required_strings)
APPS = [
    ('digital-petri-dish.html', 'generative-art', 15, ['canvas', 'genome', 'species']),
    ('infinite-shoreline.html', 'generative-art', 15, ['canvas', 'wave', 'scroll']),
    ('synesthesia-machine.html', 'audio-music', 15, ['AudioContext', 'canvas', 'keyboard']),
    ('one-bit-city.html', 'games-puzzles', 15, ['canvas', 'isometric', 'building']),
    ('infinite-zoom.html', 'generative-art', 15, ['canvas', 'zoom', 'fractal']),
    ('emotion-engine.html', 'experimental-ai', 15, ['canvas', 'emotion', 'sentiment']),
    ('gravity-sandbox.html', 'particle-physics', 15, ['canvas', 'gravity', 'mass']),
    ('probability-casino.html', 'educational', 15, ['canvas', 'probability']),
    ('voxel-terrarium.html', 'generative-art', 15, ['canvas', 'voxel', 'raycast']),
    ('git-circus.html', 'educational', 15, ['canvas', 'commit', 'branch']),
]


def read_file(path):
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        return f.read()


class TestAppExists:
    """Every app file must exist in the correct category folder."""

    def _path(self, filename, folder):
        return os.path.join(REPO_ROOT, 'apps', folder, filename)

    def test_digital_petri_dish(self):
        assert os.path.exists(self._path(*APPS[0][:2])), f"Missing {APPS[0][0]}"

    def test_infinite_shoreline(self):
        assert os.path.exists(self._path(*APPS[1][:2])), f"Missing {APPS[1][0]}"

    def test_synesthesia_machine(self):
        assert os.path.exists(self._path(*APPS[2][:2])), f"Missing {APPS[2][0]}"

    def test_one_bit_city(self):
        assert os.path.exists(self._path(*APPS[3][:2])), f"Missing {APPS[3][0]}"

    def test_infinite_zoom(self):
        assert os.path.exists(self._path(*APPS[4][:2])), f"Missing {APPS[4][0]}"

    def test_emotion_engine(self):
        assert os.path.exists(self._path(*APPS[5][:2])), f"Missing {APPS[5][0]}"

    def test_gravity_sandbox(self):
        assert os.path.exists(self._path(*APPS[6][:2])), f"Missing {APPS[6][0]}"

    def test_probability_casino(self):
        assert os.path.exists(self._path(*APPS[7][:2])), f"Missing {APPS[7][0]}"

    def test_voxel_terrarium(self):
        assert os.path.exists(self._path(*APPS[8][:2])), f"Missing {APPS[8][0]}"

    def test_git_circus(self):
        assert os.path.exists(self._path(*APPS[9][:2])), f"Missing {APPS[9][0]}"


class TestAppStructure:
    """Every app must be a valid self-contained HTML file."""

    def _check(self, idx):
        filename, folder, min_kb, keywords = APPS[idx]
        path = os.path.join(REPO_ROOT, 'apps', folder, filename)
        if not os.path.exists(path):
            return  # TestAppExists covers this
        html = read_file(path)
        size_kb = len(html.encode('utf-8')) / 1024

        # DOCTYPE
        assert html.strip()[:15].lower().startswith('<!doctype html'), \
            f"{filename}: missing DOCTYPE"

        # Title
        m = re.search(r'<title>([^<]+)</title>', html, re.IGNORECASE)
        assert m and len(m.group(1).strip()) > 0, f"{filename}: missing or empty <title>"

        # Viewport
        assert re.search(r'meta[^>]*viewport', html, re.IGNORECASE), \
            f"{filename}: missing viewport meta"

        # Self-contained: no external scripts or CSS
        ext_scripts = re.findall(
            r'<script\s+src=["\'](?!data:)(https?://[^"\']+)',
            html, re.IGNORECASE
        )
        assert len(ext_scripts) == 0, \
            f"{filename}: has external scripts: {ext_scripts}"

        ext_css = re.findall(
            r'<link\s+rel=["\']stylesheet["\']\s+href=["\'](?!data:)(https?://[^"\']+)',
            html, re.IGNORECASE
        )
        assert len(ext_css) == 0, \
            f"{filename}: has external CSS: {ext_css}"

        # Inline style and script
        assert '<style' in html.lower(), f"{filename}: no inline <style>"
        assert '<script>' in html.lower() or '<script ' in html.lower(), \
            f"{filename}: no inline <script>"

        # Minimum size
        assert size_kb >= min_kb, \
            f"{filename}: too small ({size_kb:.1f}KB < {min_kb}KB)"

        # Required content keywords (case-insensitive)
        html_lower = html.lower()
        for kw in keywords:
            assert kw.lower() in html_lower, \
                f"{filename}: missing required keyword '{kw}'"

    def test_digital_petri_dish(self): self._check(0)
    def test_infinite_shoreline(self): self._check(1)
    def test_synesthesia_machine(self): self._check(2)
    def test_one_bit_city(self): self._check(3)
    def test_infinite_zoom(self): self._check(4)
    def test_emotion_engine(self): self._check(5)
    def test_gravity_sandbox(self): self._check(6)
    def test_probability_casino(self): self._check(7)
    def test_voxel_terrarium(self): self._check(8)
    def test_git_circus(self): self._check(9)


class TestJSSyntax:
    """Every app's JavaScript must parse without syntax errors."""

    def _check_js(self, idx):
        filename, folder, _, _ = APPS[idx]
        path = os.path.join(REPO_ROOT, 'apps', folder, filename)
        if not os.path.exists(path):
            return
        html = read_file(path)
        # Extract all inline script blocks
        scripts = re.findall(r'<script[^>]*>(.*?)</script>', html, re.DOTALL | re.IGNORECASE)
        if not scripts:
            return
        combined = '\n'.join(scripts)
        # Check via Node.js
        r = subprocess.run(
            ['node', '-e', f'new Function({json.dumps(combined)})'],
            capture_output=True, text=True, timeout=10
        )
        assert r.returncode == 0, \
            f"{filename}: JS syntax error:\n{r.stderr[:500]}"

    def test_digital_petri_dish(self): self._check_js(0)
    def test_infinite_shoreline(self): self._check_js(1)
    def test_synesthesia_machine(self): self._check_js(2)
    def test_one_bit_city(self): self._check_js(3)
    def test_infinite_zoom(self): self._check_js(4)
    def test_emotion_engine(self): self._check_js(5)
    def test_gravity_sandbox(self): self._check_js(6)
    def test_probability_casino(self): self._check_js(7)
    def test_voxel_terrarium(self): self._check_js(8)
    def test_git_circus(self): self._check_js(9)


class TestManifestEntries:
    """Every app must have an entry in manifest.json."""

    def _check_manifest(self, idx):
        filename, folder, _, _ = APPS[idx]
        path = os.path.join(REPO_ROOT, 'apps', folder, filename)
        if not os.path.exists(path):
            return
        with open(MANIFEST_PATH) as f:
            data = json.load(f)
        found = False
        for k, cat in data['categories'].items():
            if cat.get('folder') == folder:
                for app in cat['apps']:
                    if app['file'] == filename:
                        found = True
                        assert app.get('title'), f"{filename}: missing title in manifest"
                        assert app.get('description'), f"{filename}: missing description"
                        assert app.get('tags'), f"{filename}: missing tags"
                        assert app.get('type'), f"{filename}: missing type"
                        assert app.get('complexity'), f"{filename}: missing complexity"
                        break
        assert found, f"{filename} not found in manifest under folder '{folder}'"

    def test_digital_petri_dish(self): self._check_manifest(0)
    def test_infinite_shoreline(self): self._check_manifest(1)
    def test_synesthesia_machine(self): self._check_manifest(2)
    def test_one_bit_city(self): self._check_manifest(3)
    def test_infinite_zoom(self): self._check_manifest(4)
    def test_emotion_engine(self): self._check_manifest(5)
    def test_gravity_sandbox(self): self._check_manifest(6)
    def test_probability_casino(self): self._check_manifest(7)
    def test_voxel_terrarium(self): self._check_manifest(8)
    def test_git_circus(self): self._check_manifest(9)

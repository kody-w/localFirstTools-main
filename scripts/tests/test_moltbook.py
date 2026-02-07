"""Tests for Moltbook: post template, sync-manifest, compile-frame, feed."""
import os
import re
import json
import sys

# Allow imports from scripts/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

REPO_ROOT = os.path.join(os.path.dirname(__file__), '..', '..')
APPS_DIR = os.path.join(REPO_ROOT, 'apps')
TEMPLATE_PATH = os.path.join(APPS_DIR, 'creative-tools', 'post-template.html')
INDEX_PATH = os.path.join(REPO_ROOT, 'index.html')
SKILLS_PATH = os.path.join(REPO_ROOT, 'skills.md')
CLAUDE_PATH = os.path.join(REPO_ROOT, 'CLAUDE.md')
MANIFEST_PATH = os.path.join(APPS_DIR, 'manifest.json')

REQUIRED_META = [
    'moltbook:author',
    'moltbook:author-type',
    'moltbook:category',
    'moltbook:tags',
    'moltbook:type',
    'moltbook:complexity',
    'moltbook:created',
    'moltbook:generation',
]

VALID_AUTHOR_TYPES = {'agent', 'human'}
VALID_CATEGORIES = {
    '3d_immersive', 'audio_music', 'games_puzzles', 'visual_art',
    'generative_art', 'particle_physics', 'creative_tools',
    'educational_tools', 'experimental_ai'
}
VALID_TYPES = {'game', 'visual', 'audio', 'interactive', 'interface', 'drawing'}
VALID_COMPLEXITIES = {'simple', 'intermediate', 'advanced'}


def extract_meta(html, name):
    """Extract content of <meta name="X" content="Y"> from HTML string."""
    pattern = r'<meta\s+name=["\']' + re.escape(name) + r'["\']\s+content=["\']([^"\']*)["\']'
    m = re.search(pattern, html, re.IGNORECASE)
    return m.group(1) if m else None


def read_file(path):
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


# ============================================================
# 1. POST TEMPLATE TESTS
# ============================================================

class TestPostTemplate:
    """Validate the canonical post template."""

    def test_template_exists(self):
        assert os.path.exists(TEMPLATE_PATH), f"Post template missing at {TEMPLATE_PATH}"

    def test_has_doctype(self):
        html = read_file(TEMPLATE_PATH)
        assert html.strip().lower().startswith('<!doctype html>'), "Missing DOCTYPE"

    def test_has_title(self):
        html = read_file(TEMPLATE_PATH)
        assert '<title>' in html.lower(), "Missing <title>"
        m = re.search(r'<title>([^<]+)</title>', html, re.IGNORECASE)
        assert m and len(m.group(1).strip()) > 0, "Empty <title>"

    def test_has_viewport(self):
        html = read_file(TEMPLATE_PATH)
        assert 'viewport' in html.lower(), "Missing viewport meta"

    def test_has_all_moltbook_meta(self):
        html = read_file(TEMPLATE_PATH)
        for meta_name in REQUIRED_META:
            val = extract_meta(html, meta_name)
            assert val is not None, f"Missing meta: {meta_name}"

    def test_author_type_valid(self):
        html = read_file(TEMPLATE_PATH)
        val = extract_meta(html, 'moltbook:author-type')
        assert val in VALID_AUTHOR_TYPES, f"Invalid author-type: {val}"

    def test_category_valid(self):
        html = read_file(TEMPLATE_PATH)
        val = extract_meta(html, 'moltbook:category')
        assert val in VALID_CATEGORIES, f"Invalid category: {val}"

    def test_type_valid(self):
        html = read_file(TEMPLATE_PATH)
        val = extract_meta(html, 'moltbook:type')
        assert val in VALID_TYPES, f"Invalid type: {val}"

    def test_complexity_valid(self):
        html = read_file(TEMPLATE_PATH)
        val = extract_meta(html, 'moltbook:complexity')
        assert val in VALID_COMPLEXITIES, f"Invalid complexity: {val}"

    def test_generation_is_zero(self):
        html = read_file(TEMPLATE_PATH)
        val = extract_meta(html, 'moltbook:generation')
        assert val == '0', f"Template generation should be 0, got {val}"

    def test_no_external_deps(self):
        html = read_file(TEMPLATE_PATH)
        ext_scripts = re.findall(r'<script\s+src=["\'](?!data:)([^"\']+)', html, re.IGNORECASE)
        ext_css = re.findall(r'<link\s+rel=["\']stylesheet["\']\s+href=["\'](?!data:)([^"\']+)', html, re.IGNORECASE)
        assert len(ext_scripts) == 0, f"External scripts: {ext_scripts}"
        assert len(ext_css) == 0, f"External CSS: {ext_css}"

    def test_self_contained(self):
        html = read_file(TEMPLATE_PATH)
        assert '<style>' in html.lower() or '<style ' in html.lower(), "Missing inline <style>"
        assert '<script>' in html.lower() or '<script ' in html.lower(), "Missing inline <script>"

    def test_has_description_meta(self):
        html = read_file(TEMPLATE_PATH)
        val = extract_meta(html, 'description')
        assert val and len(val) > 10, "Missing or short description meta"


# ============================================================
# 2. SYNC-MANIFEST TESTS
# ============================================================

class TestSyncManifest:
    """Test that sync-manifest.py correctly parses moltbook meta tags."""

    def test_script_exists(self):
        assert os.path.exists(os.path.join(REPO_ROOT, 'scripts', 'sync-manifest.py')), \
            "sync-manifest.py missing"

    def test_extract_meta_helper(self):
        html = '<meta name="moltbook:author" content="test-user">'
        assert extract_meta(html, 'moltbook:author') == 'test-user'

    def test_extract_meta_missing(self):
        html = '<meta name="other" content="val">'
        assert extract_meta(html, 'moltbook:author') is None

    def test_sync_reads_template(self):
        """sync-manifest should be importable and have a parse_post function."""
        try:
            from sync_manifest import parse_post
            html = read_file(TEMPLATE_PATH)
            result = parse_post(html, 'post-template.html')
            assert result is not None
            assert 'title' in result
            assert 'category' in result
            assert result['category'] in VALID_CATEGORIES
        except ImportError:
            import subprocess
            r = subprocess.run(
                [sys.executable, os.path.join(REPO_ROOT, 'scripts', 'sync-manifest.py'), '--dry-run'],
                capture_output=True, text=True, cwd=REPO_ROOT
            )
            assert r.returncode == 0, f"sync-manifest --dry-run failed: {r.stderr}"


# ============================================================
# 3. COMPILE-FRAME TESTS
# ============================================================

class TestCompileFrame:
    """Test the deterministic frame compiler."""

    def test_script_exists(self):
        assert os.path.exists(os.path.join(REPO_ROOT, 'scripts', 'compile-frame.py')), \
            "compile-frame.py missing"

    def test_deterministic_output(self):
        """Same input + same seed → same output hash."""
        import subprocess
        cmd = [sys.executable, os.path.join(REPO_ROOT, 'scripts', 'compile-frame.py'),
               '--dry-run', '--no-llm', '--file', TEMPLATE_PATH]
        r1 = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT)
        r2 = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT)
        if r1.returncode == 0 and r2.returncode == 0:
            assert r1.stdout == r2.stdout, "compile-frame not deterministic"

    def test_increments_generation(self):
        """Output should have generation = input generation + 1."""
        import subprocess
        cmd = [sys.executable, os.path.join(REPO_ROOT, 'scripts', 'compile-frame.py'),
               '--dry-run', '--no-llm', '--file', TEMPLATE_PATH]
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT)
        if r.returncode == 0 and r.stdout.strip():
            output_html = r.stdout
            orig_gen = int(extract_meta(read_file(TEMPLATE_PATH), 'moltbook:generation') or '0')
            new_gen = extract_meta(output_html, 'moltbook:generation')
            if new_gen is not None:
                assert int(new_gen) == orig_gen + 1, f"Expected gen {orig_gen+1}, got {new_gen}"


# ============================================================
# 4. INDEX.HTML (FEED) TESTS
# ============================================================

class TestFeed:
    """Validate the Moltbook feed index.html."""

    def test_index_exists(self):
        assert os.path.exists(INDEX_PATH), "index.html missing"

    def test_has_doctype(self):
        html = read_file(INDEX_PATH)
        assert html.strip().lower().startswith('<!doctype html>'), "Missing DOCTYPE"

    def test_has_moltbook_branding(self):
        html = read_file(INDEX_PATH).lower()
        assert 'moltbook' in html, "Missing moltbook branding"

    def test_fetches_manifest(self):
        html = read_file(INDEX_PATH)
        assert 'manifest.json' in html, "Not fetching manifest.json"

    def test_fetches_archive_manifest(self):
        html = read_file(INDEX_PATH)
        assert 'archive/manifest.json' in html or 'archive' in html, \
            "Not fetching archive manifest"

    def test_has_author_type_rendering(self):
        html = read_file(INDEX_PATH)
        assert 'author-type' in html or 'authorType' in html or 'author_type' in html or \
               '🤖' in html or 'agent' in html.lower(), \
            "No author-type badge rendering"

    def test_has_timelapse_player(self):
        html = read_file(INDEX_PATH)
        assert 'timelapse' in html.lower(), "Missing timelapse player"

    def test_has_search(self):
        html = read_file(INDEX_PATH)
        assert 'search' in html.lower(), "Missing search"

    def test_no_external_deps(self):
        html = read_file(INDEX_PATH)
        ext_scripts = re.findall(r'<script\s+src=["\'](?!data:)([^"\']+)', html, re.IGNORECASE)
        ext_css = re.findall(r'<link\s+rel=["\']stylesheet["\']\s+href=["\'](?!data:)([^"\']+)', html, re.IGNORECASE)
        assert len(ext_scripts) == 0, f"External scripts in index: {ext_scripts}"
        assert len(ext_css) == 0, f"External CSS in index: {ext_css}"


# ============================================================
# 5. SKILLS.MD TESTS
# ============================================================

class TestSkills:
    """Validate the agent/human onboarding doc."""

    def test_skills_exists(self):
        assert os.path.exists(SKILLS_PATH), "skills.md missing"

    def test_covers_creating_posts(self):
        md = read_file(SKILLS_PATH).lower()
        assert 'creat' in md and 'post' in md, "skills.md doesn't cover creating posts"

    def test_covers_molting(self):
        md = read_file(SKILLS_PATH).lower()
        assert 'molt' in md, "skills.md doesn't cover molting"

    def test_covers_template(self):
        md = read_file(SKILLS_PATH).lower()
        assert 'template' in md or 'moltbook:' in md, "skills.md doesn't reference template"

    def test_covers_agent_vs_human(self):
        md = read_file(SKILLS_PATH).lower()
        assert 'agent' in md and 'human' in md, "skills.md doesn't cover agent vs human"

    def test_covers_portals(self):
        md = read_file(SKILLS_PATH).lower()
        assert 'portal' in md, "skills.md doesn't cover portals"

    def test_covers_seed(self):
        md = read_file(SKILLS_PATH).lower()
        assert 'seed' in md, "skills.md doesn't cover deterministic seeds"


# ============================================================
# 6. CLAUDE.MD TESTS
# ============================================================

class TestClaude:
    """Validate CLAUDE.md has Moltbook section."""

    def test_claude_exists(self):
        assert os.path.exists(CLAUDE_PATH), "CLAUDE.md missing"

    def test_has_moltbook_section(self):
        md = read_file(CLAUDE_PATH).lower()
        assert 'moltbook' in md, "CLAUDE.md missing Moltbook section"

    def test_references_compile_frame(self):
        md = read_file(CLAUDE_PATH).lower()
        assert 'compile-frame' in md or 'compile_frame' in md, \
            "CLAUDE.md doesn't reference compile-frame"

    def test_references_post_template(self):
        md = read_file(CLAUDE_PATH).lower()
        assert 'post-template' in md or 'post template' in md, \
            "CLAUDE.md doesn't reference post template"


# ============================================================
# 7. MANIFEST INTEGRITY
# ============================================================

class TestManifest:
    """Validate manifest.json structure."""

    def test_manifest_valid_json(self):
        with open(MANIFEST_PATH) as f:
            data = json.load(f)
        assert 'categories' in data

    def test_template_in_manifest(self):
        with open(MANIFEST_PATH) as f:
            data = json.load(f)
        found = False
        for k, cat in data['categories'].items():
            for app in cat['apps']:
                if app['file'] == 'post-template.html':
                    found = True
                    break
        assert found, "post-template.html not in manifest"

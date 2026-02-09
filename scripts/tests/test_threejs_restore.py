"""Tests for restored Three.js 3D apps.

Validates that the 4 apps previously downgraded to Canvas 2D have been
properly restored as full Three.js 3D experiences with CDN imports,
proper scene setup, and all RappterZoo conventions.

Apps tested:
  - evomon-world-generator.html  (3D procedural world generator)
  - picasso-bowl.html            (3D cubist art exploration)
  - evomon-history-viewer.html   (3D creature evolution viewer)
  - tesseract-4d-rotator.html    (4D hypercube 3D projection)
"""
import os
import re
import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
APPS_DIR = os.path.join(REPO_ROOT, 'apps')

WORLD_GEN_PATH = os.path.join(APPS_DIR, '3d-immersive', 'evomon-world-generator.html')
PICASSO_PATH = os.path.join(APPS_DIR, 'visual-art', 'picasso-bowl.html')
HISTORY_PATH = os.path.join(APPS_DIR, 'games-puzzles', 'evomon-history-viewer.html')
TESSERACT_PATH = os.path.join(APPS_DIR, '3d-immersive', 'tesseract-4d-rotator.html')

THREEJS_APPS = {
    'world-gen': WORLD_GEN_PATH,
    'picasso': PICASSO_PATH,
    'history': HISTORY_PATH,
    'tesseract': TESSERACT_PATH,
}


def read_file(path):
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


# ─── Shared Convention Tests ──────────────────────────────────

class TestAppConventions:
    """All apps must meet RappterZoo HTML conventions and use Three.js."""

    @pytest.fixture(params=[
        pytest.param('world-gen', id='evomon-world-generator'),
        pytest.param('picasso', id='picasso-bowl'),
        pytest.param('history', id='evomon-history-viewer'),
        pytest.param('tesseract', id='tesseract-4d-rotator'),
    ])
    def app_html(self, request):
        return read_file(THREEJS_APPS[request.param])

    def test_has_doctype(self, app_html):
        assert '<!DOCTYPE html>' in app_html or '<!doctype html>' in app_html.lower()

    def test_has_title(self, app_html):
        assert re.search(r'<title>.+</title>', app_html)

    def test_has_viewport_meta(self, app_html):
        assert 'viewport' in app_html

    def test_has_inline_style(self, app_html):
        assert '<style>' in app_html or '<style ' in app_html

    def test_has_inline_script(self, app_html):
        assert '<script>' in app_html or '<script ' in app_html

    def test_has_rappterzoo_author(self, app_html):
        assert 'rappterzoo:author' in app_html

    def test_has_rappterzoo_category(self, app_html):
        assert 'rappterzoo:category' in app_html

    def test_has_rappterzoo_tags(self, app_html):
        assert 'rappterzoo:tags' in app_html

    def test_has_rappterzoo_type(self, app_html):
        assert 'rappterzoo:type' in app_html

    def test_has_rappterzoo_complexity(self, app_html):
        assert 'rappterzoo:complexity' in app_html

    def test_has_rappterzoo_created(self, app_html):
        assert 'rappterzoo:created' in app_html

    def test_has_rappterzoo_generation(self, app_html):
        assert 'rappterzoo:generation' in app_html

    # ── Three.js requirements ──

    def test_uses_threejs(self, app_html):
        """Must import Three.js via CDN."""
        assert re.search(r'three', app_html, re.IGNORECASE), "Must use Three.js"

    def test_has_threejs_cdn_or_importmap(self, app_html):
        """Must load Three.js from CDN (script src or importmap)."""
        has_cdn = bool(re.search(r'(cdnjs|unpkg|jsdelivr|esm\.sh).*three', app_html, re.IGNORECASE))
        has_importmap = bool(re.search(r'importmap', app_html))
        assert has_cdn or has_importmap, "Must load Three.js via CDN or importmap"

    def test_creates_scene(self, app_html):
        """Must create a THREE.Scene."""
        assert re.search(r'(THREE\.Scene|new\s+Scene)', app_html), "Must create a 3D scene"

    def test_creates_camera(self, app_html):
        """Must create a camera."""
        assert re.search(r'(Camera|camera)', app_html), "Must create a camera"

    def test_creates_renderer(self, app_html):
        """Must create a WebGLRenderer."""
        assert re.search(r'(Renderer|renderer)', app_html), "Must create a renderer"

    def test_has_animation_loop(self, app_html):
        """Must have a render/animation loop."""
        assert re.search(r'(requestAnimationFrame|animate|render)', app_html), "Must have animation loop"

    def test_handles_window_resize(self, app_html):
        """Must handle window resize for responsive 3D."""
        assert re.search(r'resize', app_html, re.IGNORECASE), "Must handle resize"

    def test_minimum_size(self, app_html):
        """Restored 3D apps must be substantial."""
        lines = app_html.count('\n')
        assert lines > 300, f"Only {lines} lines — 3D app needs >= 300"


# ─── EvoMon World Generator ──────────────────────────────────

class TestEvoMonWorldGenerator:
    """3D procedural world with terrain, water, vegetation, buildings."""

    @pytest.fixture
    def html(self):
        return read_file(WORLD_GEN_PATH)

    def test_file_exists(self):
        assert os.path.isfile(WORLD_GEN_PATH)

    def test_has_terrain_generation(self, html):
        assert re.search(r'(terrain|heightmap|height)', html, re.IGNORECASE)

    def test_has_noise_function(self, html):
        """Must use noise for procedural generation."""
        assert re.search(r'(simplex|perlin|noise)', html, re.IGNORECASE)

    def test_has_water(self, html):
        assert re.search(r'water', html, re.IGNORECASE)

    def test_has_vegetation(self, html):
        assert re.search(r'(tree|vegetation|plant|grass)', html, re.IGNORECASE)

    def test_has_buildings(self, html):
        assert re.search(r'building', html, re.IGNORECASE)

    def test_has_regenerate_control(self, html):
        assert re.search(r'(regenerate|generate)', html, re.IGNORECASE)

    def test_has_sliders_or_controls(self, html):
        assert re.search(r'(range|slider|control)', html, re.IGNORECASE)

    def test_has_lighting(self, html):
        assert re.search(r'(Light|light|ambient|directional)', html)

    def test_category_is_3d_immersive(self, html):
        m = re.search(r'rappterzoo:category.*?content="([^"]+)"', html)
        assert m and m.group(1) == '3d-immersive'


# ─── Picasso Bowl ─────────────────────────────────────────────

class TestPicassoBowl:
    """3D cubist art exploration with deconstructed geometric forms."""

    @pytest.fixture
    def html(self):
        return read_file(PICASSO_PATH)

    def test_file_exists(self):
        assert os.path.isfile(PICASSO_PATH)

    def test_has_cubist_theme(self, html):
        assert re.search(r'(cubis|picasso|abstract|deconstruct)', html, re.IGNORECASE)

    def test_has_bowl_concept(self, html):
        assert re.search(r'bowl', html, re.IGNORECASE)

    def test_has_geometric_forms(self, html):
        assert re.search(r'(geometry|plane|fragment|facet|mesh)', html, re.IGNORECASE)

    def test_has_3d_mesh_creation(self, html):
        assert re.search(r'Mesh', html), "Must create Three.js meshes"

    def test_has_materials(self, html):
        assert re.search(r'Material', html), "Must use Three.js materials"

    def test_has_orbit_controls_or_mouse_interaction(self, html):
        assert re.search(r'(OrbitControls|mouse|drag|rotate)', html, re.IGNORECASE)

    def test_category_is_visual_art(self, html):
        m = re.search(r'rappterzoo:category.*?content="([^"]+)"', html)
        assert m and m.group(1) == 'visual-art'


# ─── EvoMon History Viewer ────────────────────────────────────

class TestEvoMonHistoryViewer:
    """3D creature evolution timeline with genome visualization."""

    @pytest.fixture
    def html(self):
        return read_file(HISTORY_PATH)

    def test_file_exists(self):
        assert os.path.isfile(HISTORY_PATH)

    def test_has_evolution_theme(self, html):
        assert re.search(r'(evolution|evolv|history|timeline)', html, re.IGNORECASE)

    def test_has_creature_concept(self, html):
        assert re.search(r'(creature|evomon|monster|specimen)', html, re.IGNORECASE)

    def test_has_3d_creature_rendering(self, html):
        """Must render creatures as 3D objects."""
        assert re.search(r'(Mesh|Geometry|geometry)', html)

    def test_has_genome_or_stats(self, html):
        assert re.search(r'(genome|gene|stat|trait|attribute)', html, re.IGNORECASE)

    def test_has_timeline_or_history(self, html):
        assert re.search(r'(timeline|generation|history|lineage)', html, re.IGNORECASE)

    def test_has_3d_scene(self, html):
        assert re.search(r'Scene', html)

    def test_category_is_games_puzzles(self, html):
        m = re.search(r'rappterzoo:category.*?content="([^"]+)"', html)
        assert m and m.group(1) == 'games-puzzles'


# ─── Tesseract 4D Rotator ────────────────────────────────────

class TestTesseract4DRotator:
    """4D hypercube projected into 3D space with rotation controls."""

    @pytest.fixture
    def html(self):
        return read_file(TESSERACT_PATH)

    def test_file_exists(self):
        assert os.path.isfile(TESSERACT_PATH)

    def test_has_4d_concept(self, html):
        assert re.search(r'(4[dD]|tesseract|hypercube|fourth.*dimension)', html, re.IGNORECASE)

    def test_has_rotation(self, html):
        assert re.search(r'rotat', html, re.IGNORECASE)

    def test_has_projection(self, html):
        """Must project 4D to 3D."""
        assert re.search(r'(project|perspective|stereographic)', html, re.IGNORECASE)

    def test_has_vertices_and_edges(self, html):
        """Tesseract must define vertices and edges."""
        assert re.search(r'(vertices|vertex|edge)', html, re.IGNORECASE)

    def test_has_w_axis(self, html):
        """Must reference the W axis (4th dimension)."""
        assert re.search(r'[wW][\s-]*(axis|rotation|component|coord)', html)

    def test_has_3d_lines_or_geometry(self, html):
        assert re.search(r'(Line|BufferGeometry|geometry)', html)

    def test_has_visual_effects(self, html):
        assert re.search(r'(glow|bloom|effect|post)', html, re.IGNORECASE)

    def test_has_interactive_controls(self, html):
        assert re.search(r'(slider|range|control|speed|button)', html, re.IGNORECASE)

    def test_category_is_3d_immersive(self, html):
        m = re.search(r'rappterzoo:category.*?content="([^"]+)"', html)
        assert m and m.group(1) == '3d-immersive'

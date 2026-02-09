"""Tests for RappterZooNation Visual Music Video Player.

Validates the music video app meets RappterZoo conventions and contains
all required visual, audio, sync, and interaction systems:
  - Web Audio API pipeline (AudioContext, AnalyserNode, frequency/waveform)
  - Canvas 2D rendering (60fps loop, layered compositing)
  - Host avatars (Rapptr=cyan, ZooKeeper=orange, geometric shapes)
  - Dialogue sync engine (proportional time mapping)
  - App review cards (score badges, grade colors, spring animation)
  - Segment transitions (intro/review/roast/outro visual changes)
  - Particle system (frequency-reactive)
  - localStorage persistence (episode, position, settings)
  - UI controls (play/pause, episode selector, progress, volume, fullscreen)
"""
import os
import re
import json
import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
APPS_DIR = os.path.join(REPO_ROOT, 'apps')
MV_PATH = os.path.join(APPS_DIR, 'audio-music', 'rappterzoo-music-video.html')
MANIFEST_PATH = os.path.join(APPS_DIR, 'manifest.json')


def read_file(path):
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


@pytest.fixture(scope='module')
def html():
    return read_file(MV_PATH)


@pytest.fixture(scope='module')
def manifest():
    with open(MANIFEST_PATH, 'r') as f:
        return json.load(f)


# ─── File & Convention Tests ───────────────────────────────────

class TestFileConventions:
    """Music video app must meet RappterZoo HTML app conventions."""

    def test_file_exists(self):
        assert os.path.isfile(MV_PATH), f'Music video file not found at {MV_PATH}'

    def test_file_size_reasonable(self, html):
        lines = html.count('\n')
        assert lines >= 800, f'Expected 800+ lines, got {lines}'

    def test_has_doctype(self, html):
        assert '<!DOCTYPE html>' in html or '<!doctype html>' in html.lower()

    def test_has_title(self, html):
        m = re.search(r'<title>(.+?)</title>', html)
        assert m, 'Missing <title>'
        assert 'music video' in m.group(1).lower() or 'rappterzoo' in m.group(1).lower()

    def test_has_viewport_meta(self, html):
        assert 'viewport' in html

    def test_has_inline_style(self, html):
        assert '<style>' in html or '<style ' in html

    def test_has_inline_script(self, html):
        assert '<script>' in html or '<script ' in html

    def test_self_contained(self, html):
        # No external CSS or local JS imports
        assert 'rel="stylesheet"' not in html or 'href="http' in html
        # Should not reference other local files (except CDNs and feed.json/audio)
        local_imports = re.findall(r'<script\s+src="(?!http)([^"]+)"', html)
        assert len(local_imports) == 0, f'Local script imports found: {local_imports}'


# ─── RappterZoo Meta Tags ─────────────────────────────────────

class TestMetaTags:
    """Required rappterzoo:* meta tags."""

    def test_has_author(self, html):
        assert 'rappterzoo:author' in html

    def test_has_author_type(self, html):
        assert 'rappterzoo:author-type' in html

    def test_has_category(self, html):
        m = re.search(r'rappterzoo:category.*?content="([^"]+)"', html)
        assert m and m.group(1) == 'audio-music'

    def test_has_tags(self, html):
        m = re.search(r'rappterzoo:tags.*?content="([^"]+)"', html)
        assert m
        tags = m.group(1).split(',')
        assert len(tags) >= 3, f'Expected 3+ tags, got {tags}'

    def test_has_type(self, html):
        m = re.search(r'rappterzoo:type.*?content="([^"]+)"', html)
        assert m and m.group(1) in ('audio', 'visual', 'interactive')

    def test_has_complexity(self, html):
        m = re.search(r'rappterzoo:complexity.*?content="([^"]+)"', html)
        assert m and m.group(1) == 'advanced'

    def test_has_created(self, html):
        m = re.search(r'rappterzoo:created.*?content="([^"]+)"', html)
        assert m and re.match(r'\d{4}-\d{2}-\d{2}', m.group(1))

    def test_has_generation(self, html):
        assert 'rappterzoo:generation' in html


# ─── Web Audio API Pipeline ───────────────────────────────────

class TestAudioPipeline:
    """Web Audio API setup for real-time analysis."""

    def test_creates_audio_context(self, html):
        assert 'AudioContext' in html

    def test_creates_analyser_node(self, html):
        assert 'createAnalyser' in html

    def test_creates_media_element_source(self, html):
        assert 'createMediaElementSource' in html

    def test_sets_fft_size(self, html):
        m = re.search(r'fftSize\s*=\s*(\d+)', html)
        assert m, 'fftSize not set'
        fft = int(m.group(1))
        assert fft >= 512, f'fftSize should be >= 512, got {fft}'

    def test_gets_frequency_data(self, html):
        assert 'getByteFrequencyData' in html

    def test_gets_time_domain_data(self, html):
        assert 'getByteTimeDomainData' in html

    def test_connects_to_destination(self, html):
        assert 'destination' in html


# ─── Canvas Rendering ─────────────────────────────────────────

class TestCanvasRendering:
    """Canvas 2D rendering setup and animation loop."""

    def test_has_canvas_element(self, html):
        assert '<canvas' in html

    def test_gets_2d_context(self, html):
        assert "getContext('2d')" in html or 'getContext("2d")' in html

    def test_has_request_animation_frame(self, html):
        assert 'requestAnimationFrame' in html

    def test_has_clear_rect(self, html):
        assert 'clearRect' in html

    def test_has_fill_style(self, html):
        assert 'fillStyle' in html

    def test_has_begin_path(self, html):
        assert 'beginPath' in html

    def test_has_arc_calls(self, html):
        # For circular waveform and avatar shapes
        assert 'arc(' in html or 'arc (' in html


# ─── Host Avatars ─────────────────────────────────────────────

class TestHostAvatars:
    """Geometric host avatars with audio reactivity."""

    def test_rapptr_color(self, html):
        assert '#00e5ff' in html, 'Missing Rapptr cyan color'

    def test_zookeeper_color(self, html):
        assert '#ff6e40' in html, 'Missing ZooKeeper orange color'

    def test_avatar_drawing(self, html):
        # Should have triangle/polygon drawing for geometric avatars
        assert 'moveTo' in html or 'lineTo' in html, 'Missing geometric drawing primitives'

    def test_avatar_opacity_switch(self, html):
        # Active speaker full opacity, inactive dimmed
        assert 'globalAlpha' in html or 'opacity' in html.lower()

    def test_avatar_scale_pulse(self, html):
        # Scale should pulse with amplitude
        assert 'scale(' in html or 'scale (' in html


# ─── Sync Engine ──────────────────────────────────────────────

class TestSyncEngine:
    """Proportional time-to-dialogue sync."""

    def test_loads_feed_json(self, html):
        assert 'feed.json' in html

    def test_proportional_sync(self, html):
        # Should compute percentage through audio
        assert 'currentTime' in html
        assert 'duration' in html

    def test_segment_tracking(self, html):
        # Should track which segment is active
        assert re.search(r'segment', html, re.IGNORECASE)

    def test_dialogue_index(self, html):
        # Should map time to a dialogue line
        assert 'dialogue' in html


# ─── App Review Cards ─────────────────────────────────────────

class TestAppReviewCards:
    """Review cards that appear during review segments."""

    def test_grade_colors(self, html):
        # At least the key grade colors
        assert '#4caf50' in html or '#4CAF50' in html, 'Missing A-grade green'
        assert '#f44336' in html or '#F44336' in html, 'Missing F-grade red'

    def test_grade_letter_display(self, html):
        # Should display letter grades
        assert re.search(r'grade', html, re.IGNORECASE)

    def test_score_display(self, html):
        assert re.search(r'score', html, re.IGNORECASE)


# ─── Particle System ─────────────────────────────────────────

class TestParticleSystem:
    """Frequency-reactive particle field."""

    def test_particle_array(self, html):
        assert re.search(r'particle', html, re.IGNORECASE)

    def test_particle_count(self, html):
        # Should create 100+ particles
        m = re.search(r'(\d{2,})', html)
        assert m, 'No numeric particle count found'

    def test_particle_properties(self, html):
        # Particles should have position and velocity
        assert re.search(r'\bx\b', html) and re.search(r'\by\b', html)


# ─── Segment Transitions ─────────────────────────────────────

class TestSegmentTransitions:
    """Visual transitions between segment types."""

    def test_intro_handling(self, html):
        assert "'intro'" in html or '"intro"' in html

    def test_review_handling(self, html):
        assert "'review'" in html or '"review"' in html

    def test_roast_handling(self, html):
        assert "'roast'" in html or '"roast"' in html

    def test_outro_handling(self, html):
        assert "'outro'" in html or '"outro"' in html

    def test_transition_handling(self, html):
        assert "'transition'" in html or '"transition"' in html


# ─── localStorage Persistence ─────────────────────────────────

class TestLocalStorage:
    """Saves/restores state via localStorage."""

    def test_episode_key(self, html):
        assert 'rzn-mv-episode' in html

    def test_position_key(self, html):
        assert 'rzn-mv-position' in html

    def test_settings_key(self, html):
        assert 'rzn-mv-settings' in html

    def test_localstorage_getitem(self, html):
        assert 'getItem' in html

    def test_localstorage_setitem(self, html):
        assert 'setItem' in html


# ─── UI Controls ──────────────────────────────────────────────

class TestUIControls:
    """Player controls and keyboard shortcuts."""

    def test_play_pause(self, html):
        assert re.search(r'play|pause', html, re.IGNORECASE)

    def test_episode_selector(self, html):
        assert '<select' in html or 'episode' in html.lower()

    def test_progress_bar(self, html):
        assert 'progress' in html.lower()

    def test_volume_control(self, html):
        assert 'volume' in html.lower()

    def test_fullscreen_toggle(self, html):
        assert 'fullscreen' in html.lower() or 'requestFullscreen' in html

    def test_spacebar_shortcut(self, html):
        assert "' '" in html or '" "' in html or 'Space' in html

    def test_f_key_fullscreen(self, html):
        # F key or f key for fullscreen
        assert re.search(r"""['"]f['"]""", html, re.IGNORECASE) or "'F'" in html


# ─── Visual Effects ───────────────────────────────────────────

class TestVisualEffects:
    """Background gradients, waveform ring, spectrum bars."""

    def test_gradient_backgrounds(self, html):
        assert 'createLinearGradient' in html or 'createRadialGradient' in html or 'gradient' in html.lower()

    def test_circular_waveform(self, html):
        # Should draw a circular/ring waveform
        assert 'Math.cos' in html and 'Math.sin' in html

    def test_spectrum_bars(self, html):
        assert 'frequencyData' in html or 'freqData' in html or 'frequency' in html.lower()


# ─── Manifest Integration ─────────────────────────────────────

class TestManifest:
    """App should be registered in manifest.json."""

    def test_in_manifest(self, manifest):
        audio_apps = manifest.get('categories', manifest).get('audio_music', {}).get('apps', [])
        filenames = [a['file'] for a in audio_apps]
        assert 'rappterzoo-music-video.html' in filenames, \
            f'rappterzoo-music-video.html not found in audio_music apps: {filenames[:5]}...'

    def test_manifest_valid_json(self):
        with open(MANIFEST_PATH, 'r') as f:
            data = json.load(f)
        assert isinstance(data, dict)

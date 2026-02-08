"""Shared pytest configuration for RappterZoo quality gate tests."""

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
APPS_DIR = ROOT / "apps"
MANIFEST = APPS_DIR / "manifest.json"

CATEGORY_FOLDERS = {
    "visual_art": "visual-art",
    "3d_immersive": "3d-immersive",
    "audio_music": "audio-music",
    "generative_art": "generative-art",
    "games_puzzles": "games-puzzles",
    "particle_physics": "particle-physics",
    "creative_tools": "creative-tools",
    "experimental_ai": "experimental-ai",
    "educational_tools": "educational",
}


def pytest_addoption(parser):
    parser.addoption(
        "--new-files",
        action="store",
        default=None,
        help="Comma-separated list of HTML files to test (relative or absolute paths)",
    )
    parser.addoption(
        "--gate-threshold",
        action="store",
        default=60,
        type=int,
        help="Minimum quality score for non-game apps (default: 60)",
    )
    parser.addoption(
        "--game-threshold",
        action="store",
        default=65,
        type=int,
        help="Minimum quality score for game apps (default: 65)",
    )


def _resolve_path(p: str) -> Path:
    """Resolve a file path, trying relative to CWD and then ROOT."""
    path = Path(p)
    if path.is_absolute() and path.exists():
        return path
    rel = ROOT / p
    if rel.exists():
        return rel
    if path.exists():
        return path.resolve()
    return path


def _discover_all_apps() -> list:
    """Find all HTML files registered in manifest.json."""
    files = []
    if not MANIFEST.exists():
        return files
    manifest = json.loads(MANIFEST.read_text())
    for cat_key, cat_data in manifest.get("categories", {}).items():
        folder = cat_data.get("folder", CATEGORY_FOLDERS.get(cat_key, cat_key))
        for app in cat_data.get("apps", []):
            path = APPS_DIR / folder / app["file"]
            if path.exists():
                files.append(path)
    return files


def pytest_generate_tests(metafunc):
    """Parametrize tests with HTML file paths."""
    if "html_file" in metafunc.fixturenames:
        new_files = metafunc.config.getoption("--new-files")
        if new_files:
            files = [_resolve_path(f.strip()) for f in new_files.split(",")]
        else:
            files = _discover_all_apps()
        if files:
            ids = [str(f.relative_to(ROOT)) if str(f).startswith(str(ROOT)) else str(f) for f in files]
            metafunc.parametrize("html_file", files, ids=ids)
        else:
            metafunc.parametrize("html_file", [], ids=[])


@pytest.fixture
def html_content(html_file):
    """Read and return the content of an HTML file."""
    return html_file.read_text(encoding="utf-8", errors="replace")


@pytest.fixture
def gate_threshold(request):
    return request.config.getoption("--gate-threshold")


@pytest.fixture
def game_threshold(request):
    return request.config.getoption("--game-threshold")


@pytest.fixture
def is_game(html_file):
    """Determine if a file is in the games-puzzles category."""
    return "games-puzzles" in str(html_file)

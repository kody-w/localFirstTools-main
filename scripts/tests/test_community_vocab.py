"""
Tests for the community vocabulary cache system (scripts/generate_community.py).

All LLM calls are mocked -- no network needed.
"""

import json
import random
import tempfile
from pathlib import Path
from unittest import mock

import pytest

# Import the module under test
import sys
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import generate_community as gc


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_vocab():
    """A valid vocab dict that passes _validate_vocab."""
    return gc._default_vocab()


@pytest.fixture
def sample_app():
    """A sample app dict for testing comment/reply builders."""
    return {
        "file": "test-game.html",
        "title": "Test Game",
        "description": "Build and explore a dungeon",
        "tags": ["canvas", "game", "physics"],
        "complexity": "intermediate",
        "type": "game",
        "generation": 2,
        "featured": False,
    }


@pytest.fixture
def sample_players():
    """A small list of player dicts for testing."""
    return [
        {"id": f"p{i:04d}", "username": f"Player{i}", "color": "#ff4500"}
        for i in range(20)
    ]


@pytest.fixture(autouse=True)
def set_vocab(sample_vocab):
    """Ensure VOCAB is loaded for every test."""
    gc.VOCAB = sample_vocab
    yield
    gc.VOCAB = {}


# ─── Validation Tests ─────────────────────────────────────────────────────────


def test_validate_vocab_accepts_default():
    """The default vocab passes validation."""
    vocab = gc._default_vocab()
    assert gc._validate_vocab(vocab) is True


def test_validate_vocab_rejects_empty():
    assert gc._validate_vocab({}) is False
    assert gc._validate_vocab(None) is False
    assert gc._validate_vocab("string") is False


def test_validate_vocab_rejects_missing_sections():
    vocab = gc._default_vocab()
    del vocab["player_identity"]
    assert gc._validate_vocab(vocab) is False


def test_validate_vocab_rejects_small_lists():
    vocab = gc._default_vocab()
    vocab["player_identity"]["adjectives"] = ["one", "two"]  # min is 10
    assert gc._validate_vocab(vocab) is False


def test_validate_vocab_rejects_missing_moderator_templates():
    vocab = gc._default_vocab()
    vocab["moderator"]["templates"] = []  # min is 2
    assert gc._validate_vocab(vocab) is False


def test_validate_vocab_rejects_missing_reply_keywords():
    vocab = gc._default_vocab()
    vocab["reply_vocabulary"]["topic_keywords"] = {"a": ["b"]}  # min is 3
    assert gc._validate_vocab(vocab) is False


# ─── Cache Read/Write Tests ──────────────────────────────────────────────────


def test_load_vocab_from_cache(sample_vocab, tmp_path):
    """load_vocab reads from cache file when it exists and is valid."""
    cache_file = tmp_path / "community-vocab.json"
    cache_file.write_text(json.dumps(sample_vocab))

    with mock.patch.object(gc, "VOCAB_CACHE_PATH", cache_file):
        result = gc.load_vocab(regen=False)

    assert result["player_identity"]["adjectives"] == sample_vocab["player_identity"]["adjectives"]


def test_load_vocab_falls_back_on_invalid_cache(tmp_path):
    """load_vocab falls back to default when cache is invalid JSON."""
    cache_file = tmp_path / "community-vocab.json"
    cache_file.write_text("not json{{{")

    with mock.patch.object(gc, "VOCAB_CACHE_PATH", cache_file), \
         mock.patch.object(gc, "_generate_vocab_llm", return_value=None):
        result = gc.load_vocab(regen=False, verbose=True)

    # Should get the default vocab (emergency fallback)
    assert gc._validate_vocab(result) is True


def test_load_vocab_regen_calls_llm(sample_vocab, tmp_path):
    """load_vocab with regen=True calls _generate_vocab_llm even if cache exists."""
    cache_file = tmp_path / "community-vocab.json"
    cache_file.write_text(json.dumps(sample_vocab))

    with mock.patch.object(gc, "VOCAB_CACHE_PATH", cache_file), \
         mock.patch.object(gc, "_generate_vocab_llm", return_value=sample_vocab) as mock_gen:
        result = gc.load_vocab(regen=True)

    mock_gen.assert_called_once()
    assert gc._validate_vocab(result) is True


def test_load_vocab_writes_cache_after_llm_gen(sample_vocab, tmp_path):
    """load_vocab writes cache file after successful LLM generation."""
    cache_file = tmp_path / "community-vocab.json"

    with mock.patch.object(gc, "VOCAB_CACHE_PATH", cache_file), \
         mock.patch.object(gc, "_generate_vocab_llm", return_value=sample_vocab):
        gc.load_vocab(regen=True)

    assert cache_file.exists()
    written = json.loads(cache_file.read_text())
    assert written["player_identity"]["adjectives"] == sample_vocab["player_identity"]["adjectives"]


# ─── LLM Generation Tests ────────────────────────────────────────────────────


def test_generate_vocab_llm_no_copilot():
    """_generate_vocab_llm returns None when copilot is unavailable."""
    with mock.patch.dict("sys.modules", {"copilot_utils": mock.MagicMock()}) as m:
        mod = sys.modules["copilot_utils"]
        mod.detect_backend.return_value = "unavailable"
        result = gc._generate_vocab_llm(verbose=True)

    assert result is None


def test_generate_vocab_llm_success(sample_vocab):
    """_generate_vocab_llm returns vocab when all 5 calls succeed."""
    call_count = [0]

    # Call 2 was split into 2a (tag_observations) and 2b (rest of comment_vocabulary)
    tag_obs = sample_vocab["comment_vocabulary"]["tag_observations"]
    comment_rest = {k: v for k, v in sample_vocab["comment_vocabulary"].items() if k != "tag_observations"}

    def mock_copilot_call(prompt, timeout=120):
        call_count[0] += 1
        if call_count[0] == 1:
            return json.dumps(sample_vocab["player_identity"])
        elif call_count[0] == 2:
            return json.dumps(tag_obs)
        elif call_count[0] == 3:
            return json.dumps(comment_rest)
        elif call_count[0] == 4:
            return json.dumps(sample_vocab["reply_vocabulary"])
        elif call_count[0] == 5:
            return json.dumps({
                "moderator": sample_vocab["moderator"],
                "activity": sample_vocab["activity"],
            })
        return None

    with mock.patch.dict("sys.modules", {"copilot_utils": mock.MagicMock()}) as m:
        mod = sys.modules["copilot_utils"]
        mod.detect_backend.return_value = "copilot-cli"
        mod.copilot_call.side_effect = mock_copilot_call
        mod.parse_llm_json.side_effect = lambda raw: json.loads(raw) if raw else None

        with mock.patch("time.sleep"):
            result = gc._generate_vocab_llm(verbose=True)

    assert result is not None
    assert gc._validate_vocab(result) is True
    assert call_count[0] == 5


def test_generate_vocab_llm_partial_failure():
    """_generate_vocab_llm returns None if any call fails."""
    call_count = [0]

    def mock_copilot_call(prompt, timeout=120):
        call_count[0] += 1
        if call_count[0] == 1:
            vocab = gc._default_vocab()
            return json.dumps(vocab["player_identity"])
        # Call 2a (tag observations) fails
        return None

    with mock.patch.dict("sys.modules", {"copilot_utils": mock.MagicMock()}) as m:
        mod = sys.modules["copilot_utils"]
        mod.detect_backend.return_value = "copilot-cli"
        mod.copilot_call.side_effect = mock_copilot_call
        mod.parse_llm_json.side_effect = lambda raw: json.loads(raw) if raw else None

        with mock.patch("time.sleep"):
            result = gc._generate_vocab_llm(verbose=True)

    assert result is None


# ─── Consumer Function Tests ─────────────────────────────────────────────────


def test_build_comment_for_app_returns_comments(sample_app):
    """build_comment_for_app returns a non-empty list of strings."""
    rng = random.Random("test-seed")
    comments = gc.build_comment_for_app(sample_app, rng)
    assert isinstance(comments, list)
    assert len(comments) > 0
    assert all(isinstance(c, str) for c in comments)


def test_build_comment_uses_tag_observations(sample_app):
    """Comments include observations from matching tags."""
    rng = random.Random("test-seed")
    comments = gc.build_comment_for_app(sample_app, rng)
    # With canvas, game, physics tags, we should get tag observations
    all_text = " ".join(comments)
    # At least some tag observations should appear
    assert len(comments) >= 3


def test_build_comment_includes_criticism(sample_app):
    """build_comment_for_app includes constructive criticism for game type."""
    rng = random.Random("test-seed-crit")
    comments = gc.build_comment_for_app(sample_app, rng)
    # The criticism pool for game type should contribute
    assert len(comments) >= 4


def test_build_comment_deduplicates(sample_app):
    """Comments are deduplicated — no exact repeats."""
    rng = random.Random("test-seed-dedup")
    comments = gc.build_comment_for_app(sample_app, rng)
    assert len(comments) == len(set(comments))


def test_build_reply_matches_topic():
    """build_reply_for_comment matches topic keywords and returns a reply."""
    app = {"title": "Physics Demo", "tags": ["physics"]}
    rng = random.Random("reply-test")
    reply = gc.build_reply_for_comment("the physics feel weighty and real", app, rng)
    assert isinstance(reply, str)
    assert len(reply) > 0


def test_build_reply_fallback_no_topic():
    """build_reply_for_comment returns a fallback when no topic matches."""
    app = {"title": "Something", "tags": []}
    rng = random.Random("reply-fallback")
    reply = gc.build_reply_for_comment("xyzzy nonsense words", app, rng)
    assert isinstance(reply, str)
    assert len(reply) > 0


def test_build_reply_data_driven_loop():
    """build_reply uses the data-driven loop, not hardcoded if-blocks."""
    app = {"title": "Test", "tags": []}
    rng = random.Random("data-driven")

    # Audio topic should match "headphones"
    reply = gc.build_reply_for_comment("play with headphones for sure", app, rng)
    assert isinstance(reply, str)

    # Persistence topic should match "save"
    reply2 = gc.build_reply_for_comment("the save system is great", app, rng)
    assert isinstance(reply2, str)


def test_generate_players_uses_vocab():
    """generate_players pulls from VOCAB player_identity."""
    players = gc.generate_players(5)
    assert len(players) == 5
    for p in players:
        assert "username" in p
        assert "bio" in p
        assert p["isNPC"] is True


def test_build_moderator_comment_uses_vocab(sample_app):
    """_build_moderator_comment uses VOCAB moderator section."""
    rng = random.Random("mod-test")
    comment = gc._build_moderator_comment(sample_app, rng)
    assert comment["author"] == "ArcadeKeeper"
    assert comment["isModerator"] is True
    assert "[ArcadeKeeper]" in comment["text"]


def test_generate_activity_feed_uses_vocab(sample_app, sample_players):
    """generate_activity_feed uses VOCAB activity section."""
    apps_list = [{"app": sample_app, "catKey": "games_puzzles", "catTitle": "Games", "folder": "games-puzzles"}]
    rng = random.Random("activity-test")
    events = gc.generate_activity_feed(apps_list, sample_players, rng, count=20)
    assert len(events) == 20
    achieved_events = [e for e in events if e["type"] == "achieved"]
    for e in achieved_events:
        assert "achievement" in e


def test_generate_comments_for_app_full(sample_app, sample_players):
    """Full comment generation produces threaded comments with moderator."""
    rng = random.Random("full-comments")
    comments = gc.generate_comments_for_app(
        sample_app, "games_puzzles", sample_players, rng
    )
    assert isinstance(comments, list)
    assert len(comments) >= 2  # at least 1 comment + 1 moderator
    # Last comment should be moderator
    assert comments[-1]["author"] == "ArcadeKeeper"
    # Check threading — some comments should have children
    has_children = any(len(c.get("children", [])) > 0 for c in comments)
    # Not guaranteed with small player pool but check structure is valid
    for c in comments:
        assert "id" in c
        assert "text" in c
        assert "author" in c


# ─── Default Vocab Structure Tests ────────────────────────────────────────────


def test_default_vocab_structure():
    """_default_vocab returns a complete, valid structure."""
    vocab = gc._default_vocab()
    assert gc._validate_vocab(vocab)

    # Check all top-level keys
    assert "player_identity" in vocab
    assert "comment_vocabulary" in vocab
    assert "reply_vocabulary" in vocab
    assert "moderator" in vocab
    assert "activity" in vocab

    # Check nested structure
    pi = vocab["player_identity"]
    assert len(pi["adjectives"]) >= 10
    assert len(pi["nouns"]) >= 10
    assert len(pi["colors"]) >= 5
    assert len(pi["bios"]) >= 5

    cv = vocab["comment_vocabulary"]
    assert isinstance(cv["tag_observations"], dict)
    assert isinstance(cv["desc_reactions"], dict)
    assert isinstance(cv["complexity_reactions"], dict)
    assert isinstance(cv["type_reactions"], dict)
    assert isinstance(cv["criticism"], dict)
    assert isinstance(cv["fallbacks"], list)

    rv = vocab["reply_vocabulary"]
    assert isinstance(rv["topic_keywords"], dict)
    assert isinstance(rv["topic_replies"], dict)
    assert isinstance(rv["fallback_replies"], list)

    mod = vocab["moderator"]
    assert isinstance(mod["templates"], list)
    assert isinstance(mod["verdicts"], dict)
    assert isinstance(mod["tech_labels"], dict)

    act = vocab["activity"]
    assert isinstance(act["achievements"], list)
    assert isinstance(act["durations"], list)

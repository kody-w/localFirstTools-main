#!/usr/bin/env python3
"""Tests for the shared agent memory store."""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

# Patch MEMORY_DIR before importing memory module
_test_dir = None


@pytest.fixture(autouse=True)
def isolated_memory(tmp_path):
    """Each test gets its own temporary memory directory."""
    global _test_dir
    _test_dir = tmp_path
    import scripts.memory as mem
    mem.MEMORY_DIR = tmp_path
    mem.LEDGER_PATH = tmp_path / "ledger.json"
    yield tmp_path


class TestLoadSaveRoundtrip:
    def test_load_missing_agent_returns_empty(self, isolated_memory):
        from scripts.memory import load_agent_memory
        data = load_agent_memory("test-agent")
        assert data["agent"] == "test-agent"
        assert data["entries"] == []
        assert "lastUpdated" in data

    def test_save_and_load_roundtrip(self, isolated_memory):
        from scripts.memory import load_agent_memory, save_agent_memory
        data = {"agent": "test-agent", "lastUpdated": "", "entries": [
            {"id": "abc", "timestamp": "2026-01-01T00:00:00Z", "type": "note",
             "target": "apps/test.html", "data": {"notes": "hello"}}
        ]}
        save_agent_memory("test-agent", data)
        loaded = load_agent_memory("test-agent")
        assert len(loaded["entries"]) == 1
        assert loaded["entries"][0]["data"]["notes"] == "hello"
        assert loaded["agent"] == "test-agent"

    def test_save_updates_lastUpdated(self, isolated_memory):
        from scripts.memory import load_agent_memory, save_agent_memory
        data = {"agent": "x", "lastUpdated": "old", "entries": []}
        save_agent_memory("x", data)
        loaded = load_agent_memory("x")
        assert loaded["lastUpdated"] != "old"


class TestAppendEntry:
    def test_append_entry_adds_to_list(self, isolated_memory):
        from scripts.memory import append_memory_entry, load_agent_memory
        entry = append_memory_entry("test-agent", {
            "type": "created",
            "target": "apps/games-puzzles/test.html",
            "data": {"title": "Test Game"}
        })
        assert "id" in entry
        assert "timestamp" in entry
        mem = load_agent_memory("test-agent")
        assert len(mem["entries"]) == 1

    def test_append_multiple_entries(self, isolated_memory):
        from scripts.memory import append_memory_entry, load_agent_memory
        for i in range(5):
            append_memory_entry("test-agent", {
                "type": "note",
                "target": f"apps/test{i}.html",
                "data": {"notes": f"note {i}"}
            })
        mem = load_agent_memory("test-agent")
        assert len(mem["entries"]) == 5

    def test_append_invalid_type_raises(self, isolated_memory):
        from scripts.memory import append_memory_entry
        with pytest.raises(ValueError, match="Invalid entry type"):
            append_memory_entry("test-agent", {
                "type": "invalid_type",
                "target": "x",
                "data": {}
            })

    def test_preserves_existing_id_and_timestamp(self, isolated_memory):
        from scripts.memory import append_memory_entry
        entry = append_memory_entry("test-agent", {
            "id": "custom-id",
            "timestamp": "2026-01-01T00:00:00Z",
            "type": "scored",
            "target": "apps/test.html",
            "data": {"score": 75}
        })
        assert entry["id"] == "custom-id"
        assert entry["timestamp"] == "2026-01-01T00:00:00Z"


class TestLedger:
    def test_load_empty_ledger(self, isolated_memory):
        from scripts.memory import load_ledger
        ledger = load_ledger()
        assert ledger["relationships"] == []
        assert "consistencyHash" in ledger

    def test_append_relationship(self, isolated_memory):
        from scripts.memory import append_relationship, load_ledger
        rel = append_relationship({
            "source": "apps/games-puzzles/a.html",
            "target": "apps/games-puzzles/b.html",
            "relation": "improves",
            "agent": "molter-engine"
        })
        assert "id" in rel
        assert "timestamp" in rel
        ledger = load_ledger()
        assert len(ledger["relationships"]) == 1

    def test_append_invalid_relation_raises(self, isolated_memory):
        from scripts.memory import append_relationship
        with pytest.raises(ValueError, match="Invalid relation"):
            append_relationship({
                "source": "a", "target": "b",
                "relation": "destroys", "agent": "x"
            })

    def test_consistency_hash_updates(self, isolated_memory):
        from scripts.memory import append_relationship, load_ledger
        append_relationship({
            "source": "a", "target": "b",
            "relation": "teaches", "agent": "x"
        })
        h1 = load_ledger()["consistencyHash"]
        append_relationship({
            "source": "c", "target": "d",
            "relation": "duplicates", "agent": "y"
        })
        h2 = load_ledger()["consistencyHash"]
        assert h1 != h2

    def test_find_relationships_query(self, isolated_memory):
        from scripts.memory import append_relationship, find_relationships
        append_relationship({
            "source": "apps/a.html", "target": "apps/b.html",
            "relation": "relates_to", "agent": "x"
        })
        append_relationship({
            "source": "apps/c.html", "target": "apps/a.html",
            "relation": "derived_from", "agent": "y"
        })
        append_relationship({
            "source": "apps/d.html", "target": "apps/e.html",
            "relation": "competes_with", "agent": "z"
        })
        results = find_relationships("apps/a.html")
        assert len(results) == 2


class TestAtomicWrite:
    def test_atomic_write_creates_valid_json(self, isolated_memory):
        from scripts.memory import save_agent_memory, load_agent_memory
        save_agent_memory("atomic-test", {
            "agent": "atomic-test", "lastUpdated": "", "entries": []
        })
        path = isolated_memory / "atomic-test.json"
        assert path.exists()
        data = json.loads(path.read_text())
        assert data["agent"] == "atomic-test"

    def test_no_tmp_files_left(self, isolated_memory):
        from scripts.memory import save_agent_memory
        save_agent_memory("clean-test", {
            "agent": "clean-test", "lastUpdated": "", "entries": []
        })
        tmp_files = list(isolated_memory.glob("*.tmp"))
        assert len(tmp_files) == 0


class TestCrossAgentQuery:
    def test_get_all_entries_for_target(self, isolated_memory):
        from scripts.memory import append_memory_entry, get_all_entries_for_target
        append_memory_entry("agent-a", {
            "type": "created", "target": "apps/shared.html",
            "data": {"title": "Shared"}
        })
        append_memory_entry("agent-b", {
            "type": "scored", "target": "apps/shared.html",
            "data": {"score": 72}
        })
        append_memory_entry("agent-b", {
            "type": "scored", "target": "apps/other.html",
            "data": {"score": 50}
        })
        results = get_all_entries_for_target("apps/shared.html")
        assert len(results) == 2
        agents = {r["_agent"] for r in results}
        assert agents == {"agent-a", "agent-b"}

    def test_ignores_schema_and_ledger(self, isolated_memory):
        from scripts.memory import get_all_entries_for_target
        # Write schema.json with entries field (should be ignored)
        (isolated_memory / "schema.json").write_text(json.dumps({
            "entries": [{"target": "apps/x.html"}]
        }))
        results = get_all_entries_for_target("apps/x.html")
        assert len(results) == 0

#!/usr/bin/env python3
"""Shared agent memory store for RappterZoo.

Provides atomic read/write for per-agent memory files and a cross-agent
relationship ledger. All files live in .claude/memory/.

Usage:
    from scripts.memory import (
        load_agent_memory, save_agent_memory, append_memory_entry,
        load_ledger, append_relationship, find_relationships,
        get_all_entries_for_target
    )
"""

import hashlib
import json
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MEMORY_DIR = ROOT / ".claude" / "memory"
LEDGER_PATH = MEMORY_DIR / "ledger.json"

VALID_ENTRY_TYPES = {"created", "molted", "scored", "audited", "linked", "note"}
VALID_RELATIONS = {"teaches", "improves", "duplicates", "relates_to", "derived_from", "competes_with"}
KNOWN_AGENTS = {"molter-engine", "game-factory", "data-slosh", "task-delegator"}


def _atomic_write(path: Path, data: dict) -> None:
    """Write JSON atomically via tmp file + rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2)
            f.write("\n")
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def load_agent_memory(name: str) -> dict:
    """Load an agent's memory file. Returns empty structure if missing."""
    path = MEMORY_DIR / f"{name}.json"
    if path.exists():
        return json.loads(path.read_text())
    return {"agent": name, "lastUpdated": datetime.now(timezone.utc).isoformat(), "entries": []}


def save_agent_memory(name: str, data: dict) -> None:
    """Atomically save an agent's memory file."""
    data["lastUpdated"] = datetime.now(timezone.utc).isoformat()
    _atomic_write(MEMORY_DIR / f"{name}.json", data)


def append_memory_entry(name: str, entry: dict) -> dict:
    """Append an entry to an agent's memory. Returns the entry with id/timestamp filled."""
    if "id" not in entry:
        entry["id"] = str(uuid.uuid4())
    if "timestamp" not in entry:
        entry["timestamp"] = datetime.now(timezone.utc).isoformat()
    if entry.get("type") not in VALID_ENTRY_TYPES:
        raise ValueError(f"Invalid entry type: {entry.get('type')}. Must be one of {VALID_ENTRY_TYPES}")
    mem = load_agent_memory(name)
    mem["entries"].append(entry)
    save_agent_memory(name, mem)
    return entry


def _compute_consistency_hash(relationships: list) -> str:
    """MD5 hash of sorted relationship IDs for integrity checking."""
    ids = sorted(r["id"] for r in relationships)
    return hashlib.md5("|".join(ids).encode()).hexdigest()


def load_ledger() -> dict:
    """Load the cross-agent relationship ledger."""
    if LEDGER_PATH.exists():
        return json.loads(LEDGER_PATH.read_text())
    return {"relationships": [], "consistencyHash": hashlib.md5(b"").hexdigest()}


def append_relationship(rel: dict) -> dict:
    """Append a relationship to the ledger. Returns the relationship with id/timestamp filled."""
    if "id" not in rel:
        rel["id"] = str(uuid.uuid4())
    if "timestamp" not in rel:
        rel["timestamp"] = datetime.now(timezone.utc).isoformat()
    if rel.get("relation") not in VALID_RELATIONS:
        raise ValueError(f"Invalid relation: {rel.get('relation')}. Must be one of {VALID_RELATIONS}")
    ledger = load_ledger()
    ledger["relationships"].append(rel)
    ledger["consistencyHash"] = _compute_consistency_hash(ledger["relationships"])
    _atomic_write(LEDGER_PATH, ledger)
    return rel


def find_relationships(target: str) -> list:
    """Find all relationships involving a target (as source or target)."""
    ledger = load_ledger()
    return [r for r in ledger["relationships"] if r.get("source") == target or r.get("target") == target]


def get_all_entries_for_target(target: str) -> list:
    """Query all agent memories for entries referencing a target."""
    results = []
    for path in MEMORY_DIR.glob("*.json"):
        if path.name in ("schema.json", "ledger.json"):
            continue
        try:
            data = json.loads(path.read_text())
            for entry in data.get("entries", []):
                if entry.get("target") == target:
                    results.append({**entry, "_agent": data.get("agent", path.stem)})
        except (json.JSONDecodeError, KeyError):
            continue
    return sorted(results, key=lambda e: e.get("timestamp", ""))

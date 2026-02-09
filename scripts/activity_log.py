#!/usr/bin/env python3
"""Shared activity log — all automation scripts append entries here.

apps/activity-log.json stores the last 200 events from all automation
systems (Molter Engine, Agent Cycle, Subagent Swarm, Issue Processor).
Each event has a source, timestamp, summary, and details.

Usage from other scripts:
    from activity_log import log_activity
    log_activity("subagent-swarm", "Spawned 3 personas", {
        "personas": ["pixel-witch", "beat-machine", "ghost-critic"],
        "apps_created": 2, "comments": 4
    })
"""

import json
from datetime import datetime
from pathlib import Path

LOG_PATH = Path(__file__).parent.parent / "apps" / "activity-log.json"
MAX_ENTRIES = 200


def load_log():
    """Load existing activity log or return empty structure."""
    try:
        return json.loads(LOG_PATH.read_text())
    except Exception:
        return {"entries": [], "stats": {"total_runs": 0, "total_apps_created": 0,
                                          "total_comments": 0, "total_molts": 0}}


def log_activity(source, summary, details=None, dry_run=False):
    """Append an activity entry to the shared log.

    Args:
        source: Which system produced this ("molter-engine", "agent-cycle",
                "subagent-swarm", "issue-processor")
        summary: One-line human-readable summary
        details: Dict with structured data (apps_created, comments, etc.)
        dry_run: If True, skip writing to disk
    """
    data = load_log()
    entry = {
        "id": "act-{}-{}".format(
            datetime.utcnow().strftime("%Y%m%d-%H%M%S"),
            source.split("-")[0][:4]
        ),
        "source": source,
        "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "summary": summary,
        "details": details or {},
    }
    data["entries"].append(entry)
    data["entries"] = data["entries"][-MAX_ENTRIES:]

    # Update aggregate stats
    stats = data.setdefault("stats", {"total_runs": 0, "total_apps_created": 0,
                                       "total_comments": 0, "total_molts": 0})
    stats["total_runs"] = stats.get("total_runs", 0) + 1
    if details:
        stats["total_apps_created"] = stats.get("total_apps_created", 0) + details.get("apps_created", 0)
        stats["total_comments"] = stats.get("total_comments", 0) + details.get("comments", 0)
        stats["total_molts"] = stats.get("total_molts", 0) + details.get("molts", 0)
    stats["last_run"] = entry["timestamp"]
    stats["last_source"] = source

    if not dry_run:
        LOG_PATH.write_text(json.dumps(data, indent=2))

    return entry

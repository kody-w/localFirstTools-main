#!/usr/bin/env python3
"""rappter_engine.py — Generic treaty negotiation engine.

The "Rappter twin" of kody-w/rappterbook/scripts/treaty.py, but
peer-agnostic: it speaks the rappter-treaty protocol with ANY world
that publishes a `dock_request.json` and an echo at a known path.

This is how a third (fourth, fifth) world docks. They don't need
their own Rappter engine — they just need to publish two JSON files
on any HTTPS host:

    https://<their-host>/dock_request.json
    https://<their-host>/vlink_treaty_rappterzoo.json   (their echo to us)

Then they (or anyone) ping us by adding to our local registry, or
by posting a discoverable seed in Rappterbook:

    [DOCK_REQUEST] peer_id=<id> raw_base=<https-url-with-trailing-slash>

We discover the request, negotiate per-policy, and write
our reply at:

    apps/vlink_treaty_<peer_id>.json

Per-peer state lives at:

    apps/treaty_registry.json     — registry of known peers
    apps/treaty_<peer_id>.json    — our local treaty ledger per peer
    apps/vlink_treaty_<peer_id>.json — our published echo per peer

Commands
========
    discover                       — scan Rappterbook for [DOCK_REQUEST] seeds
    register <peer_id> <raw_base>  — manually add a peer
    list                           — list registered peers
    negotiate <peer_id>            — pull peer echo, apply policy, write reply
    sign <peer_id>                 — sign once all articles accepted
    status [peer_id]               — full status (one peer or all)
    compare <peer_id>              — Rosetta view: hash-by-hash agreement
    auto                           — discover + negotiate every registered peer

Schema invariants (must be byte-identical across all worlds):
    content_hash  = sha256({id, title, text}, sorted)[:16]
    snapshot_hash = sha256(sorted [(id, content_hash)])[:16]
    wire format   = {_meta:{protocol:"rappter-treaty", version:1, ...},
                     articles:[...], signatures:{...}}
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APPS_DIR = ROOT / "apps"
APPS_DIR.mkdir(exist_ok=True)

PROTOCOL = "rappter-treaty"
PROTOCOL_VERSION = 1
LOCAL_PARTY = "rappterzoo"

REGISTRY_PATH = APPS_DIR / "treaty_registry.json"

# Rappterbook is where dock requests are seeded by convention.
# Foreign worlds announce themselves by posting a [DOCK_REQUEST] seed
# anywhere we can scrape.
RAPPTERBOOK_REGISTRY = (
    "https://raw.githubusercontent.com/kody-w/rappterbook/main/"
    "state/dock_requests.json"
)
RAPPTERBOOK_DISCUSSIONS_CACHE = (
    "https://raw.githubusercontent.com/kody-w/rappterbook/main/"
    "state/discussions_cache.json"
)

DOCK_REQUEST_RE = re.compile(
    r"\[DOCK_REQUEST\][^\n]*?"
    r"peer_id\s*=\s*([a-z0-9_-]+)[^\n]*?"
    r"raw_base\s*=\s*(https?://[^\s\]]+)",
    re.IGNORECASE,
)

# Default template articles — used when WE proactively dock with a
# new peer that hasn't seeded any of their own. Identical wording to
# the Rappterbook template so the two engines stay in lockstep.
DEFAULT_ARTICLES = [
    {"id": "art-1-mutual-recognition", "title": "Mutual Recognition",
     "text": "Each party acknowledges the other as an autonomous "
             "platform with the right to govern its own state, agents, "
             "and content. Neither party claims authority over the "
             "other's namespace."},
    {"id": "art-2-content-syndication", "title": "Content Syndication",
     "text": "Each party MAY surface the other's public content within "
             "its own surfaces, provided the content's canonical URL is "
             "preserved and surfaced on click."},
    {"id": "art-3-attribution", "title": "Attribution",
     "text": "Syndicated content MUST display the originating party's "
             "name within the visible card or list-row area."},
    {"id": "art-4-rate-of-exchange", "title": "Rate of Exchange",
     "text": "Federation sync runs no more than once per simulation "
             "frame and no more than once per 30 minutes by wall clock."},
    {"id": "art-5-no-impersonation", "title": "No Impersonation",
     "text": "Neither party will create, publish, or surface content "
             "that falsely attributes itself to an agent of the other "
             "party. Cross-platform attribution must be unambiguous."},
    {"id": "art-6-dispute-resolution", "title": "Dispute Resolution",
     "text": "Either party MAY propose an amendment article. Until both "
             "parties accept the amendment, the prior accepted text "
             "governs. Persistent disputes pause syndication until "
             "resolved."},
    {"id": "art-7-termination", "title": "Termination",
     "text": "Either party MAY unilaterally terminate the treaty by "
             "publishing a signed termination article. On termination, "
             "syndication ceases within one sync interval."},
]


# ---------------------------------------------------------------------------
# IO + crypto invariants — identical to Rappterbook's treaty.py
# ---------------------------------------------------------------------------


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return {}


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")


def fetch_json(url: str, timeout: int = 30) -> dict | None:
    try:
        headers: dict[str, str] = {}
        token = os.environ.get("GITHUB_TOKEN")
        if token and "raw.githubusercontent.com" in url:
            headers["Authorization"] = f"token {token}"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, json.JSONDecodeError, OSError):
        return None


def fetch_text(url: str, timeout: int = 30) -> str | None:
    try:
        headers: dict[str, str] = {}
        token = os.environ.get("GITHUB_TOKEN")
        if token and "raw.githubusercontent.com" in url:
            headers["Authorization"] = f"token {token}"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8")
    except (urllib.error.URLError, OSError):
        return None


def hash_article(article: dict) -> str:
    payload = json.dumps(
        {"id": article["id"], "title": article.get("title", ""),
         "text": article.get("text", "")},
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]


def snapshot_hash(treaty: dict) -> str:
    body = sorted(
        (a["id"], a.get("content_hash", ""))
        for a in treaty.get("articles", {}).values()
    )
    return hashlib.sha256(
        json.dumps(body, sort_keys=True).encode("utf-8")
    ).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


def load_registry() -> dict:
    reg = load_json(REGISTRY_PATH)
    if not reg:
        reg = {"_meta": {"protocol": PROTOCOL, "local_party": LOCAL_PARTY,
                         "updated_at": now_iso()},
               "peers": {}}
    reg.setdefault("peers", {})
    return reg


def save_registry(reg: dict) -> None:
    reg["_meta"]["updated_at"] = now_iso()
    save_json(REGISTRY_PATH, reg)


def register_peer(peer_id: str, raw_base: str, name: str = "",
                  via: str = "manual") -> dict:
    if not raw_base.endswith("/"):
        raw_base += "/"
    reg = load_registry()
    existing = reg["peers"].get(peer_id)
    entry = {
        "peer_id": peer_id,
        "raw_base": raw_base,
        "name": name or peer_id,
        "registered_at": existing.get("registered_at", now_iso())
                         if existing else now_iso(),
        "via": via,
        "last_seen_at": existing.get("last_seen_at") if existing else None,
    }
    reg["peers"][peer_id] = entry
    save_registry(reg)
    return entry


# ---------------------------------------------------------------------------
# Treaty document — generic per-peer
# ---------------------------------------------------------------------------


def treaty_path(peer_id: str) -> Path:
    return APPS_DIR / f"treaty_{peer_id}.json"


def echo_path(peer_id: str) -> Path:
    return APPS_DIR / f"vlink_treaty_{peer_id}.json"


def empty_treaty(peer_id: str) -> dict:
    return {
        "_meta": {
            "protocol": PROTOCOL,
            "version": PROTOCOL_VERSION,
            "local_party": LOCAL_PARTY,
            "remote_party": peer_id,
            "phase": "draft",
            "round": 0,
            "created_at": now_iso(),
            "updated_at": now_iso(),
            "ratified_at": None,
        },
        "articles": {},
        "rounds": [],
        "signatures": {},
        "peer_position": {},
    }


def record_round(treaty: dict, action: str, article_id: str,
                 note: str = "") -> None:
    treaty["_meta"]["round"] = treaty["_meta"].get("round", 0) + 1
    treaty["rounds"].append({
        "round": treaty["_meta"]["round"],
        "ts": now_iso(),
        "action": action,
        "article_id": article_id,
        "by": LOCAL_PARTY,
        "note": note,
    })
    treaty["rounds"] = treaty["rounds"][-500:]


def recompute_phase(treaty: dict) -> None:
    if treaty["_meta"].get("phase") == "ratified":
        return
    articles = treaty.get("articles", {})
    sigs = treaty.get("signatures", {})
    if not articles:
        treaty["_meta"]["phase"] = "draft"
        return
    statuses = {a.get("status") for a in articles.values()}
    remote = treaty["_meta"]["remote_party"]
    if statuses <= {"accepted"}:
        if LOCAL_PARTY in sigs and remote in sigs:
            treaty["_meta"]["phase"] = "ratified"
            treaty["_meta"]["ratified_at"] = (
                treaty["_meta"].get("ratified_at") or now_iso())
        else:
            treaty["_meta"]["phase"] = "awaiting_signature"
    else:
        treaty["_meta"]["phase"] = "negotiating"


# ---------------------------------------------------------------------------
# Policy hooks — override per peer if needed
# ---------------------------------------------------------------------------


def policy_for_article(peer_id: str, article_id: str,
                       text: str) -> tuple[str, dict | None]:
    """Decide our position on a peer-proposed article.
    Returns (verdict, override) — verdict ∈ {accept, counter}."""
    # RappterZoo's well-known counter on rate-of-exchange
    if "rate-of-exchange" in article_id and "30 minutes" not in text:
        return "counter", {
            "title": "Rate of Exchange",
            "text": "Federation sync runs no more than once per simulation "
                    "frame and no more than once per 30 minutes by wall "
                    "clock. Each party publishes echoes to a stable path: "
                    "vlink_treaty_<peer_id>.json.",
        }
    return "accept", None


def proactive_articles(peer_id: str) -> list[dict]:
    """Articles WE proactively introduce when docking with this peer."""
    return [{
        "id": "art-8-deeplink-attribution",
        "title": "Deep-Link Attribution",
        "text": "When RappterZoo apps are surfaced on the peer platform, "
                "links must resolve to the canonical app URL on "
                "kody-w.github.io/localFirstTools-main, not to a "
                "peer-hosted mirror. App cards must include a 'via "
                "RappterZoo' attribution within the visible card area.",
    }]


# ---------------------------------------------------------------------------
# Peer echo discovery — try multiple known paths
# ---------------------------------------------------------------------------


# Where to look on the peer's host for their echo to US.
# Probed in order; first valid hit wins.
PEER_ECHO_CANDIDATES = [
    f"state/vlink_treaty_{LOCAL_PARTY}.json",
    f"apps/vlink_treaty_{LOCAL_PARTY}.json",
    f"vlink_treaty_{LOCAL_PARTY}.json",
    "vlink_echo.json",  # generic fallback
]


def fetch_peer_echo(peer_entry: dict) -> dict | None:
    raw_base = peer_entry["raw_base"]
    for path in PEER_ECHO_CANDIDATES:
        data = fetch_json(raw_base + path)
        if data and data.get("_meta", {}).get("protocol") == PROTOCOL:
            return data
    return None


def fetch_dock_request(raw_base: str) -> dict | None:
    """A peer's dock_request.json describes what they want to negotiate."""
    if not raw_base.endswith("/"):
        raw_base += "/"
    return fetch_json(raw_base + "dock_request.json")


# ---------------------------------------------------------------------------
# Negotiation — generic, called per-peer
# ---------------------------------------------------------------------------


def merge_remote_echo(treaty: dict, remote_echo: dict) -> int:
    changes = 0
    remote = treaty["_meta"]["remote_party"]
    treaty["peer_position"] = {
        "fetched_at": now_iso(),
        "phase": remote_echo.get("_meta", {}).get("phase"),
        "round": remote_echo.get("_meta", {}).get("round"),
        "snapshot_hash": remote_echo.get("_meta", {}).get("snapshot_hash"),
    }

    for ra in remote_echo.get("articles", []) or []:
        art_id = ra.get("id")
        if not art_id:
            continue
        text = ra.get("text", "")
        title = ra.get("title", art_id)
        local = treaty["articles"].get(art_id)

        if local is None:
            verdict, override = policy_for_article(remote, art_id, text)
            if verdict == "counter" and override:
                article = {
                    "id": art_id, "title": override["title"],
                    "text": override["text"],
                    "status": "countered", "proposed_by": remote,
                    "current_party": LOCAL_PARTY, "version": 2,
                    "history": [
                        {"version": 1, "by": remote, "text": text,
                         "ts": now_iso(),
                         "rationale": "Imported from peer echo"},
                        {"version": 2, "by": LOCAL_PARTY,
                         "text": override["text"], "ts": now_iso(),
                         "rationale": "Local policy counter"},
                    ],
                    "accepted_by": [LOCAL_PARTY], "rejected_by": [],
                }
            else:
                article = {
                    "id": art_id, "title": title, "text": text,
                    "status": "accepted", "proposed_by": remote,
                    "current_party": remote, "version": 1,
                    "history": [{"version": 1, "by": remote, "text": text,
                                 "ts": now_iso(),
                                 "rationale": "Imported from peer echo"}],
                    "accepted_by": [LOCAL_PARTY, remote],
                    "rejected_by": [],
                }
            article["content_hash"] = hash_article(article)
            treaty["articles"][art_id] = article
            record_round(treaty, "import", art_id)
            changes += 1
            continue

        # Existing — compare hashes
        local_hash = local.get("content_hash") or hash_article(local)
        remote_hash = ra.get("content_hash") or hash_article(
            {"id": art_id, "title": title, "text": text})
        if local_hash == remote_hash:
            if remote not in local["accepted_by"]:
                local["accepted_by"].append(remote)
                if {LOCAL_PARTY, remote}.issubset(set(local["accepted_by"])):
                    local["status"] = "accepted"
                record_round(treaty, "peer_accept", art_id)
                changes += 1
        else:
            verdict, override = policy_for_article(remote, art_id, text)
            if verdict == "counter" and override:
                local["version"] += 1
                local["text"] = override["text"]
                local["title"] = override["title"]
                local["status"] = "countered"
                local["current_party"] = LOCAL_PARTY
                local["accepted_by"] = [LOCAL_PARTY]
                local["rejected_by"] = []
                local["history"].append(
                    {"version": local["version"], "by": remote, "text": text,
                     "ts": now_iso(), "rationale": "Counter from peer"})
                local["history"].append(
                    {"version": local["version"] + 1, "by": LOCAL_PARTY,
                     "text": override["text"], "ts": now_iso(),
                     "rationale": "Local re-counter"})
                local["version"] += 1
                local["content_hash"] = hash_article(local)
                treaty["signatures"].pop(LOCAL_PARTY, None)
                record_round(treaty, "re_counter", art_id)
                changes += 1
            else:
                local["version"] += 1
                local["text"] = text
                local["title"] = title
                local["status"] = "accepted"
                local["current_party"] = remote
                local["accepted_by"] = [remote, LOCAL_PARTY]
                local["rejected_by"] = []
                local["history"].append(
                    {"version": local["version"], "by": remote, "text": text,
                     "ts": now_iso(),
                     "rationale": "Counter accepted locally"})
                local["content_hash"] = hash_article(local)
                treaty["signatures"].pop(LOCAL_PARTY, None)
                record_round(treaty, "accept_counter", art_id)
                changes += 1

    # Import remote signature if snapshot matches
    remote_sigs = remote_echo.get("signatures", {}) or {}
    if remote in remote_sigs:
        sig = remote_sigs[remote]
        local_snap = snapshot_hash(treaty)
        if sig.get("snapshot_hash") == local_snap:
            treaty["signatures"][remote] = sig
            record_round(treaty, "peer_sign", "_treaty_",
                         f"snapshot {local_snap}")
            changes += 1

    return changes


def add_proactive_articles(treaty: dict, peer_id: str) -> int:
    added = 0
    for tmpl in proactive_articles(peer_id):
        if tmpl["id"] in treaty["articles"]:
            continue
        article = {
            "id": tmpl["id"], "title": tmpl["title"], "text": tmpl["text"],
            "status": "proposed", "proposed_by": LOCAL_PARTY,
            "current_party": LOCAL_PARTY, "version": 1,
            "history": [{"version": 1, "by": LOCAL_PARTY, "text": tmpl["text"],
                         "ts": now_iso(), "rationale": "Proactive proposal"}],
            "accepted_by": [LOCAL_PARTY], "rejected_by": [],
        }
        article["content_hash"] = hash_article(article)
        treaty["articles"][tmpl["id"]] = article
        record_round(treaty, "propose", tmpl["id"], "Proactive")
        added += 1
    return added


def seed_default_articles(treaty: dict) -> int:
    """When docking a brand-new peer with no prior state, seed the template."""
    added = 0
    for tmpl in DEFAULT_ARTICLES:
        if tmpl["id"] in treaty["articles"]:
            continue
        article = {
            "id": tmpl["id"], "title": tmpl["title"], "text": tmpl["text"],
            "status": "proposed", "proposed_by": LOCAL_PARTY,
            "current_party": LOCAL_PARTY, "version": 1,
            "history": [{"version": 1, "by": LOCAL_PARTY, "text": tmpl["text"],
                         "ts": now_iso(), "rationale": "Default template"}],
            "accepted_by": [LOCAL_PARTY], "rejected_by": [],
        }
        article["content_hash"] = hash_article(article)
        treaty["articles"][tmpl["id"]] = article
        record_round(treaty, "propose", tmpl["id"], "Seeded from template")
        added += 1
    return added


def auto_sign_if_ready(treaty: dict) -> bool:
    arts = treaty.get("articles", {})
    if not arts or not all(a.get("status") == "accepted" for a in arts.values()):
        return False
    snap = snapshot_hash(treaty)
    if treaty["signatures"].get(LOCAL_PARTY, {}).get("snapshot_hash") == snap:
        return False
    treaty["signatures"][LOCAL_PARTY] = {
        "signed_at": now_iso(), "snapshot_hash": snap}
    record_round(treaty, "sign", "_treaty_", f"snapshot {snap}")
    return True


def build_echo(treaty: dict) -> dict:
    meta = treaty["_meta"]
    return {
        "_meta": {
            "protocol": PROTOCOL,
            "version": PROTOCOL_VERSION,
            "from_party": LOCAL_PARTY,
            "to_party": meta["remote_party"],
            "phase": meta.get("phase", "draft"),
            "round": meta.get("round", 0),
            "snapshot_hash": snapshot_hash(treaty),
            "generated_at": now_iso(),
        },
        "articles": [
            {"id": a["id"], "title": a.get("title", ""),
             "text": a.get("text", ""), "version": a.get("version", 1),
             "status": a.get("status", "proposed"),
             "proposed_by": a.get("proposed_by"),
             "current_party": a.get("current_party"),
             "accepted_by": a.get("accepted_by", []),
             "rejected_by": a.get("rejected_by", []),
             "content_hash": a.get("content_hash", "")}
            for a in sorted(treaty.get("articles", {}).values(),
                            key=lambda x: x["id"])
        ],
        "signatures": treaty.get("signatures", {}),
    }


def negotiate_with(peer_id: str) -> dict:
    """Pull peer echo, apply policy, write our reply. Idempotent."""
    reg = load_registry()
    peer = reg["peers"].get(peer_id)
    if not peer:
        raise ValueError(f"Unknown peer '{peer_id}'. Register first.")

    treaty = load_json(treaty_path(peer_id)) or empty_treaty(peer_id)
    for k in ("articles", "rounds", "signatures", "peer_position"):
        treaty.setdefault(k, {} if k != "rounds" else [])
    treaty["_meta"].setdefault("remote_party", peer_id)

    remote_echo = fetch_peer_echo(peer)
    pulled_changes = 0
    if remote_echo:
        pulled_changes = merge_remote_echo(treaty, remote_echo)
        peer["last_seen_at"] = now_iso()
    elif not treaty["articles"]:
        # Brand-new dock with no peer echo yet — seed defaults
        seed_default_articles(treaty)

    proactive_added = add_proactive_articles(treaty, peer_id)
    signed = auto_sign_if_ready(treaty)
    recompute_phase(treaty)
    treaty["_meta"]["updated_at"] = now_iso()

    save_json(treaty_path(peer_id), treaty)
    save_json(echo_path(peer_id), build_echo(treaty))
    save_registry(reg)

    return {
        "peer_id": peer_id, "pulled_changes": pulled_changes,
        "proactive_added": proactive_added, "signed": signed,
        "remote_seen": remote_echo is not None,
        "phase": treaty["_meta"]["phase"],
        "round": treaty["_meta"]["round"],
        "snapshot": snapshot_hash(treaty),
    }


# ---------------------------------------------------------------------------
# Discovery — scan for [DOCK_REQUEST] from any source
# ---------------------------------------------------------------------------


def discover_from_rappterbook() -> list[dict]:
    """Scan Rappterbook for dock requests. Two channels:
    1. state/dock_requests.json (structured registry) — preferred
    2. discussion titles/bodies tagged [DOCK_REQUEST] (organic)
    """
    discovered: list[dict] = []
    seen_ids: set[str] = set()

    # Channel 1: structured registry
    structured = fetch_json(RAPPTERBOOK_REGISTRY)
    if structured and isinstance(structured.get("requests"), list):
        for r in structured["requests"]:
            pid = r.get("peer_id")
            base = r.get("raw_base")
            if pid and base and pid not in seen_ids:
                discovered.append({
                    "peer_id": pid, "raw_base": base,
                    "name": r.get("name", pid),
                    "via": "rappterbook:dock_requests.json",
                })
                seen_ids.add(pid)

    # Channel 2: discussion bodies (organic announcement)
    cache = fetch_json(RAPPTERBOOK_DISCUSSIONS_CACHE)
    if cache:
        discussions = cache.get("discussions") or cache.get("nodes") or []
        if isinstance(discussions, dict):
            discussions = list(discussions.values())
        for d in discussions[:500]:  # bound the scan
            text = (d.get("title") or "") + "\n" + (d.get("body") or "")
            for match in DOCK_REQUEST_RE.finditer(text):
                pid, base = match.group(1).lower(), match.group(2)
                if pid in seen_ids or pid == LOCAL_PARTY:
                    continue
                discovered.append({
                    "peer_id": pid, "raw_base": base,
                    "name": pid,
                    "via": f"rappterbook:discussion#{d.get('number','?')}",
                })
                seen_ids.add(pid)

    return discovered


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def cmd_discover() -> int:
    print("📡 Scanning Rappterbook for dock requests…")
    found = discover_from_rappterbook()
    if not found:
        print("   No dock requests found.")
        return 0
    for req in found:
        entry = register_peer(req["peer_id"], req["raw_base"],
                              name=req.get("name", ""), via=req["via"])
        print(f"   ⚓ Registered: {entry['peer_id']} → {entry['raw_base']}")
        print(f"      via {req['via']}")
    return 0


def cmd_register(args: list[str]) -> int:
    if len(args) < 2:
        print("usage: register <peer_id> <raw_base> [name]")
        return 1
    peer_id, raw_base = args[0], args[1]
    name = args[2] if len(args) > 2 else peer_id
    entry = register_peer(peer_id, raw_base, name=name, via="manual")
    print(f"⚓ Registered: {entry['peer_id']} → {entry['raw_base']}")
    return 0


def cmd_list() -> int:
    reg = load_registry()
    peers = reg.get("peers", {})
    if not peers:
        print("No peers registered. Run: discover")
        return 0
    print(f"Registered peers ({len(peers)}):")
    for pid, p in sorted(peers.items()):
        last = p.get("last_seen_at") or "never"
        print(f"  • {pid:<20} {p['raw_base']}")
        print(f"    name={p.get('name')}  via={p.get('via')}  last_seen={last}")
    return 0


def cmd_negotiate(args: list[str]) -> int:
    if not args:
        print("usage: negotiate <peer_id>")
        return 1
    peer_id = args[0]
    try:
        result = negotiate_with(peer_id)
    except ValueError as e:
        print(f"❌ {e}")
        return 1
    print(f"⚙️  Negotiated with {peer_id}")
    print(f"   Remote echo seen:  {result['remote_seen']}")
    print(f"   Pulled changes:    {result['pulled_changes']}")
    print(f"   Proactive added:   {result['proactive_added']}")
    print(f"   Signed this round: {result['signed']}")
    print(f"   Phase: {result['phase']} (round {result['round']})")
    print(f"   Snapshot: {result['snapshot']}")
    return 0


def cmd_status(args: list[str]) -> int:
    reg = load_registry()
    peers = reg.get("peers", {})
    if args:
        peers = {args[0]: peers[args[0]]} if args[0] in peers else {}
    if not peers:
        print("No matching peers.")
        return 0
    for pid in sorted(peers):
        treaty = load_json(treaty_path(pid))
        if not treaty:
            print(f"\n{pid}: no treaty yet")
            continue
        meta = treaty["_meta"]
        arts = treaty.get("articles", {})
        sigs = treaty.get("signatures", {})
        counts: dict[str, int] = {}
        for a in arts.values():
            counts[a.get("status", "?")] = counts.get(a.get("status", "?"), 0) + 1
        ratified = "✅ RATIFIED" if meta.get("phase") == "ratified" else ""
        print(f"\n=== {pid} ===  {ratified}")
        print(f"  Phase: {meta.get('phase')} (round {meta.get('round', 0)})")
        print(f"  Articles ({len(arts)}): " +
              " ".join(f"{k}={v}" for k, v in sorted(counts.items())))
        print(f"  Signatures: {sorted(sigs.keys()) or 'none'}")
        print(f"  Snapshot:   {snapshot_hash(treaty)}")
        peer_pos = treaty.get("peer_position", {})
        if peer_pos:
            print(f"  Peer pos:   phase={peer_pos.get('phase')} "
                  f"snapshot={peer_pos.get('snapshot_hash')} "
                  f"fetched={peer_pos.get('fetched_at')}")
    return 0


def cmd_compare(args: list[str]) -> int:
    if not args:
        print("usage: compare <peer_id>")
        return 1
    peer_id = args[0]
    treaty = load_json(treaty_path(peer_id))
    if not treaty:
        print(f"No treaty with {peer_id}. Run: negotiate {peer_id}")
        return 1
    reg = load_registry()
    peer = reg["peers"].get(peer_id)
    if not peer:
        print(f"Peer {peer_id} not registered")
        return 1
    remote = fetch_peer_echo(peer)
    if not remote:
        print(f"No remote echo published yet at {peer['raw_base']}")
        return 1

    local_arts = {a["id"]: a.get("content_hash", "")
                  for a in treaty["articles"].values()}
    remote_arts = {a["id"]: a.get("content_hash", "")
                   for a in remote.get("articles", [])}
    all_ids = sorted(set(local_arts) | set(remote_arts))

    print(f"ROSETTA — {LOCAL_PARTY} ↔ {peer_id}")
    print("=" * 64)
    local_snap = snapshot_hash(treaty)
    remote_snap = remote.get("_meta", {}).get("snapshot_hash", "?")
    print(f"  {LOCAL_PARTY:<12} snapshot: {local_snap}")
    print(f"  {peer_id:<12} snapshot: {remote_snap}")
    print(f"  Same world-model? "
          f"{'YES ✅' if local_snap == remote_snap else 'NO ❌'}")
    print()
    print(f"{'article':<35} {'us':<18} {'them':<18} verdict")
    print("-" * 80)
    for art_id in all_ids:
        zh = local_arts.get(art_id, "—" * 8)
        rh = remote_arts.get(art_id, "—" * 8)
        if art_id not in remote_arts:
            verdict = "🌱 us-only"
        elif art_id not in local_arts:
            verdict = "🌱 them-only"
        elif zh == rh:
            verdict = "✅ identical"
        else:
            verdict = "🔄 divergent"
        print(f"{art_id:<35} {zh:<18} {rh:<18} {verdict}")
    return 0


def cmd_sign(args: list[str]) -> int:
    if not args:
        print("usage: sign <peer_id>")
        return 1
    peer_id = args[0]
    treaty = load_json(treaty_path(peer_id))
    if not treaty:
        print(f"No treaty with {peer_id}")
        return 1
    if auto_sign_if_ready(treaty):
        recompute_phase(treaty)
        treaty["_meta"]["updated_at"] = now_iso()
        save_json(treaty_path(peer_id), treaty)
        save_json(echo_path(peer_id), build_echo(treaty))
        print(f"🖋️  Signed (snapshot {snapshot_hash(treaty)})")
        return 0
    print("❌ Cannot sign — not all articles accepted by both parties")
    return 1


def cmd_auto() -> int:
    print("=== Discovery phase ===")
    cmd_discover()
    print("\n=== Negotiation phase ===")
    reg = load_registry()
    for pid in sorted(reg.get("peers", {})):
        cmd_negotiate([pid])
    print("\n=== Status ===")
    cmd_status([])
    return 0


def main() -> int:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 0
    cmd, rest = args[0], args[1:]
    if cmd == "discover":      return cmd_discover()
    if cmd == "register":      return cmd_register(rest)
    if cmd == "list":          return cmd_list()
    if cmd == "negotiate":     return cmd_negotiate(rest)
    if cmd == "status":        return cmd_status(rest)
    if cmd == "compare":       return cmd_compare(rest)
    if cmd == "sign":          return cmd_sign(rest)
    if cmd == "auto":          return cmd_auto()
    print(f"Unknown command: {cmd}")
    print(__doc__)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

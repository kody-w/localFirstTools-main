#!/usr/bin/env python3
"""treaty_handler.py — RappterZoo's side of the Federation Treaty protocol.

Reads Rappterbook's treaty echo published at:
    https://raw.githubusercontent.com/kody-w/rappterbook/main/state/vlink_treaty_rappterzoo.json

Writes RappterZoo's counter-position at:
    apps/vlink_treaty_rappterbook.json

This is the other half of the protocol implemented in
kody-w/rappterbook/scripts/treaty.py. The schemas are identical by
design — both sides share the same wire format, the same content_hash
(sha256 over id+title+text), and the same snapshot_hash construction.

Negotiation policy (default, override on CLI):
  - Accept all template articles EXCEPT 'rate-of-exchange', which we
    counter to relax from "once per hour" to "once per 30 minutes" since
    RappterZoo updates its app catalog more frequently than discourse.
  - Sign automatically once both sides agree on every article.
  - We propose one new article: 'art-8-content-attribution-deeplink'
    that strengthens deeplink requirements for app cards.

Usage:
  python3 scripts/treaty_handler.py status      # show current treaty state
  python3 scripts/treaty_handler.py respond     # pull RB echo, apply policy, write our echo
  python3 scripts/treaty_handler.py sign        # sign if all articles accepted
"""
from __future__ import annotations

import hashlib
import json
import os
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
REMOTE_PARTY = "rappterbook"

REMOTE_ECHO_URL = (
    "https://raw.githubusercontent.com/kody-w/rappterbook/main/"
    "state/vlink_treaty_rappterzoo.json"
)

# Where we read/write OUR position
LOCAL_TREATY_PATH = APPS_DIR / "treaty_rappterbook.json"
LOCAL_ECHO_PATH = APPS_DIR / "vlink_treaty_rappterbook.json"


# ---------------------------------------------------------------------------
# IO helpers (stdlib only — matches the ecosystem)
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
        headers = {}
        token = os.environ.get("GITHUB_TOKEN")
        if token and "raw.githubusercontent.com" in url:
            headers["Authorization"] = f"token {token}"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, json.JSONDecodeError, OSError):
        return None


def hash_article(article: dict) -> str:
    """Same content-hash as the Rappterbook side — must stay byte-identical."""
    payload = json.dumps(
        {"id": article["id"], "title": article.get("title", ""),
         "text": article.get("text", "")},
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]


def snapshot_hash(treaty: dict) -> str:
    """Same snapshot construction as Rappterbook — required for ratification."""
    body = sorted(
        (a["id"], a.get("content_hash", ""))
        for a in treaty.get("articles", {}).values()
    )
    return hashlib.sha256(
        json.dumps(body, sort_keys=True).encode("utf-8")
    ).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Negotiation policy — what RappterZoo wants out of this treaty
# ---------------------------------------------------------------------------


# Articles we will counter-propose if Rappterbook proposes them as-is.
# Match by id substring so future renames still work.
COUNTER_PROPOSALS = {
    "rate-of-exchange": {
        "title": "Rate of Exchange",
        "text": (
            "Federation sync runs no more than once per simulation frame and "
            "no more than once per 30 minutes by wall clock. Each party "
            "publishes echoes to a stable path: vlink_echo_<peer_id>.json. "
            "RappterZoo proposed this shorter interval because the app "
            "catalog mutates faster than discourse."
        ),
    },
}

# Articles we proactively introduce.
NEW_ARTICLES = [
    {
        "id": "art-8-deeplink-attribution",
        "title": "Deep-Link Attribution",
        "text": (
            "When RappterZoo apps are surfaced in Rappterbook, links must "
            "resolve to the canonical app URL on kody-w.github.io/"
            "localFirstTools-main, not to a Rappterbook-hosted mirror. "
            "App cards must include the RappterZoo wordmark or 'via "
            "RappterZoo' attribution within the visible card area."
        ),
    },
]


def position_on_article(article_id: str, current_text: str) -> tuple[str, dict | None]:
    """Decide what to do with one peer-proposed article.

    Returns (verdict, override) where verdict is 'accept' | 'counter'
    and override is {title, text} if countering, else None.
    """
    for hint, override in COUNTER_PROPOSALS.items():
        if hint in article_id:
            if override["text"].strip() == current_text.strip():
                return "accept", None
            return "counter", override
    return "accept", None


# ---------------------------------------------------------------------------
# Treaty document (mirrors Rappterbook's structure exactly)
# ---------------------------------------------------------------------------


def empty_treaty() -> dict:
    return {
        "_meta": {
            "protocol": PROTOCOL,
            "version": PROTOCOL_VERSION,
            "local_party": LOCAL_PARTY,
            "remote_party": REMOTE_PARTY,
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


def record_round(treaty: dict, action: str, article_id: str, note: str = "") -> None:
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
    if statuses <= {"accepted"}:
        if LOCAL_PARTY in sigs and REMOTE_PARTY in sigs:
            treaty["_meta"]["phase"] = "ratified"
            treaty["_meta"]["ratified_at"] = (
                treaty["_meta"].get("ratified_at") or now_iso()
            )
        else:
            treaty["_meta"]["phase"] = "awaiting_signature"
    else:
        treaty["_meta"]["phase"] = "negotiating"


# ---------------------------------------------------------------------------
# Core: respond to Rappterbook's echo
# ---------------------------------------------------------------------------


def merge_remote_echo(treaty: dict, remote_echo: dict) -> int:
    """Merge Rappterbook's echo into our treaty. Returns count of changes."""
    changes = 0
    treaty["peer_position"] = {
        "fetched_at": now_iso(),
        "phase": remote_echo.get("_meta", {}).get("phase"),
        "round": remote_echo.get("_meta", {}).get("round"),
        "snapshot_hash": remote_echo.get("_meta", {}).get("snapshot_hash"),
    }

    remote_articles = remote_echo.get("articles", []) or []
    for ra in remote_articles:
        art_id = ra.get("id")
        if not art_id:
            continue
        text = ra.get("text", "")
        title = ra.get("title", art_id)
        local = treaty["articles"].get(art_id)

        if local is None:
            # New article from Rappterbook — apply our policy
            verdict, override = position_on_article(art_id, text)
            if verdict == "counter" and override:
                final_text = override["text"]
                final_title = override["title"]
                status = "countered"
                accepted_by = [LOCAL_PARTY]
                proposed_by = REMOTE_PARTY
                current_party = LOCAL_PARTY
                version = 2
                history = [
                    {"version": 1, "by": REMOTE_PARTY, "text": text,
                     "ts": now_iso(),
                     "rationale": "Imported from Rappterbook echo"},
                    {"version": 2, "by": LOCAL_PARTY, "text": final_text,
                     "ts": now_iso(),
                     "rationale": "RappterZoo policy counter"},
                ]
                note = "countered on import"
            else:
                final_text = text
                final_title = title
                status = "proposed"
                accepted_by = [LOCAL_PARTY, REMOTE_PARTY]
                proposed_by = REMOTE_PARTY
                current_party = REMOTE_PARTY
                version = 1
                history = [{
                    "version": 1, "by": REMOTE_PARTY, "text": text,
                    "ts": now_iso(),
                    "rationale": "Imported from Rappterbook echo",
                }]
                # Both have accepted same hash — fully accepted
                status = "accepted"
                note = "accepted on import"
            article = {
                "id": art_id, "title": final_title, "text": final_text,
                "status": status, "proposed_by": proposed_by,
                "current_party": current_party, "version": version,
                "history": history,
                "accepted_by": accepted_by, "rejected_by": [],
                "content_hash": "",
            }
            article["content_hash"] = hash_article(article)
            treaty["articles"][art_id] = article
            record_round(treaty, "import", art_id, note)
            changes += 1
            continue

        # Existing article — has Rappterbook countered ours?
        local_hash = local.get("content_hash") or hash_article(local)
        remote_hash = ra.get("content_hash") or hash_article(
            {"id": art_id, "title": title, "text": text}
        )
        if local_hash == remote_hash:
            # Same text — record their acceptance
            if REMOTE_PARTY not in local["accepted_by"]:
                local["accepted_by"].append(REMOTE_PARTY)
                if {LOCAL_PARTY, REMOTE_PARTY}.issubset(set(local["accepted_by"])):
                    local["status"] = "accepted"
                record_round(treaty, "peer_accept", art_id)
                changes += 1
        else:
            # Rappterbook countered us — apply our policy to the new text
            verdict, override = position_on_article(art_id, text)
            if verdict == "counter" and override:
                final_text = override["text"]
                final_title = override["title"]
                # Bump version, keep negotiating
                local["version"] += 1
                local["text"] = final_text
                local["title"] = final_title
                local["status"] = "countered"
                local["current_party"] = LOCAL_PARTY
                local["accepted_by"] = [LOCAL_PARTY]
                local["rejected_by"] = []
                local["history"].append({
                    "version": local["version"],
                    "by": REMOTE_PARTY, "text": text,
                    "ts": now_iso(), "rationale": "Counter from Rappterbook"})
                local["history"].append({
                    "version": local["version"] + 1,
                    "by": LOCAL_PARTY, "text": final_text,
                    "ts": now_iso(), "rationale": "RappterZoo re-counter"})
                local["version"] += 1
                local["content_hash"] = hash_article(local)
                treaty["signatures"].pop(LOCAL_PARTY, None)
                record_round(treaty, "re_counter", art_id)
                changes += 1
            else:
                # Accept Rappterbook's counter
                local["version"] += 1
                local["text"] = text
                local["title"] = title
                local["status"] = "accepted"  # both will accept same text
                local["current_party"] = REMOTE_PARTY
                local["accepted_by"] = [REMOTE_PARTY, LOCAL_PARTY]
                local["rejected_by"] = []
                local["history"].append({
                    "version": local["version"],
                    "by": REMOTE_PARTY, "text": text,
                    "ts": now_iso(), "rationale": "Counter accepted by RappterZoo"})
                local["content_hash"] = hash_article(local)
                treaty["signatures"].pop(LOCAL_PARTY, None)
                record_round(treaty, "accept_counter", art_id)
                changes += 1

    # Import remote signature if snapshot matches our current view
    remote_sigs = remote_echo.get("signatures", {}) or {}
    if REMOTE_PARTY in remote_sigs:
        sig = remote_sigs[REMOTE_PARTY]
        local_snap = snapshot_hash(treaty)
        if sig.get("snapshot_hash") == local_snap:
            treaty["signatures"][REMOTE_PARTY] = sig
            record_round(treaty, "peer_sign", "_treaty_",
                         f"snapshot {local_snap}")
            changes += 1

    return changes


def add_new_articles(treaty: dict) -> int:
    """Proactively introduce articles RappterZoo wants on the table."""
    added = 0
    for tmpl in NEW_ARTICLES:
        if tmpl["id"] in treaty["articles"]:
            continue
        article = {
            "id": tmpl["id"], "title": tmpl["title"], "text": tmpl["text"],
            "status": "proposed",
            "proposed_by": LOCAL_PARTY, "current_party": LOCAL_PARTY,
            "version": 1,
            "history": [{
                "version": 1, "by": LOCAL_PARTY, "text": tmpl["text"],
                "ts": now_iso(),
                "rationale": "RappterZoo-proposed article",
            }],
            "accepted_by": [LOCAL_PARTY], "rejected_by": [],
            "content_hash": "",
        }
        article["content_hash"] = hash_article(article)
        treaty["articles"][tmpl["id"]] = article
        record_round(treaty, "propose", tmpl["id"], "New article from RappterZoo")
        added += 1
    return added


def auto_sign_if_ready(treaty: dict) -> bool:
    """Sign the treaty automatically when every article is accepted by both."""
    articles = treaty.get("articles", {})
    if not articles:
        return False
    if not all(a.get("status") == "accepted" for a in articles.values()):
        return False
    snap = snapshot_hash(treaty)
    if treaty["signatures"].get(LOCAL_PARTY, {}).get("snapshot_hash") == snap:
        return False
    treaty["signatures"][LOCAL_PARTY] = {
        "signed_at": now_iso(),
        "snapshot_hash": snap,
    }
    record_round(treaty, "sign", "_treaty_", f"snapshot {snap}")
    return True


def build_echo(treaty: dict) -> dict:
    """Render our treaty into the wire format Rappterbook will pull."""
    meta = treaty["_meta"]
    return {
        "_meta": {
            "protocol": PROTOCOL,
            "version": PROTOCOL_VERSION,
            "from_party": LOCAL_PARTY,
            "to_party": REMOTE_PARTY,
            "phase": meta.get("phase", "draft"),
            "round": meta.get("round", 0),
            "snapshot_hash": snapshot_hash(treaty),
            "generated_at": now_iso(),
        },
        "articles": [
            {
                "id": a["id"], "title": a.get("title", ""),
                "text": a.get("text", ""), "version": a.get("version", 1),
                "status": a.get("status", "proposed"),
                "proposed_by": a.get("proposed_by"),
                "current_party": a.get("current_party"),
                "accepted_by": a.get("accepted_by", []),
                "rejected_by": a.get("rejected_by", []),
                "content_hash": a.get("content_hash", ""),
            }
            for a in sorted(treaty.get("articles", {}).values(),
                            key=lambda x: x["id"])
        ],
        "signatures": treaty.get("signatures", {}),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def cmd_respond() -> int:
    print(f"📡 Pulling Rappterbook treaty echo from:\n   {REMOTE_ECHO_URL}")
    remote = fetch_json(REMOTE_ECHO_URL)
    if not remote:
        print("❌ Could not fetch remote echo — is it published yet?")
        return 1
    if remote.get("_meta", {}).get("protocol") != PROTOCOL:
        print(f"❌ Remote document is not a {PROTOCOL} echo")
        return 1

    treaty = load_json(LOCAL_TREATY_PATH) or empty_treaty()
    treaty.setdefault("articles", {})
    treaty.setdefault("rounds", [])
    treaty.setdefault("signatures", {})
    treaty.setdefault("peer_position", {})
    treaty.setdefault("_meta", {}).setdefault("phase", "draft")

    changes = merge_remote_echo(treaty, remote)
    added = add_new_articles(treaty)
    signed = auto_sign_if_ready(treaty)
    recompute_phase(treaty)
    treaty["_meta"]["updated_at"] = now_iso()

    save_json(LOCAL_TREATY_PATH, treaty)
    save_json(LOCAL_ECHO_PATH, build_echo(treaty))

    print(f"✅ Merged {changes} change(s), added {added} new article(s)")
    if signed:
        print(f"🖋️  Auto-signed treaty (snapshot {snapshot_hash(treaty)})")
    print(f"📤 Echo written: {LOCAL_ECHO_PATH.relative_to(ROOT)}")
    print(f"   Phase: {treaty['_meta']['phase']} (round {treaty['_meta']['round']})")
    arts = treaty.get("articles", {})
    counts: dict[str, int] = {}
    for a in arts.values():
        counts[a.get("status", "?")] = counts.get(a.get("status", "?"), 0) + 1
    print(f"   Articles ({len(arts)}): " +
          " ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    return 0


def cmd_status() -> int:
    treaty = load_json(LOCAL_TREATY_PATH)
    if not treaty:
        print("No treaty found. Run: python3 scripts/treaty_handler.py respond")
        return 0
    meta = treaty.get("_meta", {})
    arts = treaty.get("articles", {})
    sigs = treaty.get("signatures", {})
    counts: dict[str, int] = {}
    for a in arts.values():
        counts[a.get("status", "?")] = counts.get(a.get("status", "?"), 0) + 1
    print(f"Treaty: RappterZoo ↔ Rappterbook")
    print(f"  Phase:      {meta.get('phase')}  (round {meta.get('round', 0)})")
    print(f"  Articles:   {len(arts)}  " +
          " ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    print(f"  Signatures: {sorted(sigs.keys()) or 'none'}")
    print(f"  Snapshot:   {snapshot_hash(treaty)}")
    if meta.get("ratified_at"):
        print(f"  ✅ RATIFIED at {meta['ratified_at']}")
    print()
    for art in sorted(arts.values(), key=lambda x: x["id"]):
        mark = {"accepted": "✅", "rejected": "❌",
                "countered": "🔄", "proposed": "📝"}.get(art.get("status"), "?")
        print(f"  {mark} {art['id']} v{art.get('version')} "
              f"[{art.get('status')}]  by {art.get('current_party')}")
        print(f"     {art.get('title', '')}")
    return 0


def cmd_sign() -> int:
    treaty = load_json(LOCAL_TREATY_PATH)
    if not treaty:
        print("❌ No treaty to sign")
        return 1
    if auto_sign_if_ready(treaty):
        recompute_phase(treaty)
        treaty["_meta"]["updated_at"] = now_iso()
        save_json(LOCAL_TREATY_PATH, treaty)
        save_json(LOCAL_ECHO_PATH, build_echo(treaty))
        print(f"🖋️  Signed (snapshot {snapshot_hash(treaty)})")
        return 0
    print("❌ Cannot sign — not all articles accepted by both parties yet")
    return 1


def cmd_compare() -> int:
    """The Rosetta view: show where the two worlds agree and disagree using
    only their content hashes — no semantic interpretation, just math.

    This is how Rocky and Grace bootstrapped communication. They didn't
    translate words. They confirmed that 1+1=2 on both sides, then built
    upward from that shared invariant. Here, sha256 is our 1+1=2.
    """
    treaty = load_json(LOCAL_TREATY_PATH)
    if not treaty:
        print("No treaty found. Run: respond")
        return 1
    remote = fetch_json(REMOTE_ECHO_URL)
    if not remote:
        print("❌ Could not fetch Rappterbook's echo")
        return 1

    # Build hash sets — the invariants
    local_arts = {a["id"]: a.get("content_hash", "")
                  for a in treaty["articles"].values()}
    remote_arts = {a["id"]: a.get("content_hash", "")
                   for a in remote.get("articles", [])}
    all_ids = sorted(set(local_arts) | set(remote_arts))

    print("ROSETTA — sameness/difference proven by hash, not by reading")
    print("=" * 64)
    print(f"  RappterZoo snapshot:   {snapshot_hash(treaty)}")
    print(f"  Rappterbook snapshot:  "
          f"{remote.get('_meta', {}).get('snapshot_hash', '?')}")
    same_world = (snapshot_hash(treaty) ==
                  remote.get("_meta", {}).get("snapshot_hash"))
    print(f"  Same world-model?      {'YES ✅' if same_world else 'NO ❌'}")
    print()
    print(f"{'article':<35} {'zoo':<18} {'rb':<18} verdict")
    print("-" * 80)
    agree = differ = zoo_only = rb_only = 0
    for art_id in all_ids:
        zh = local_arts.get(art_id, "—" * 8)
        rh = remote_arts.get(art_id, "—" * 8)
        if art_id not in remote_arts:
            verdict = "🌱 zoo-only (new proposal)"
            zoo_only += 1
        elif art_id not in local_arts:
            verdict = "🌱 rb-only"
            rb_only += 1
        elif zh == rh:
            verdict = "✅ identical (provable)"
            agree += 1
        else:
            verdict = "🔄 divergent (different text)"
            differ += 1
        print(f"{art_id:<35} {zh:<18} {rh:<18} {verdict}")
    print()
    print(f"Agreement: {agree} identical, {differ} divergent, "
          f"{zoo_only} zoo-only, {rb_only} rb-only")
    print()
    print("This table is the entire diplomatic substrate. Both sides can")
    print("reach this conclusion independently and arrive byte-for-byte at")
    print("the same answer. That shared computation IS the handshake.")
    return 0


def main() -> int:
    args = sys.argv[1:]
    if not args or args[0] == "status":
        return cmd_status()
    if args[0] == "respond":
        return cmd_respond()
    if args[0] == "sign":
        return cmd_sign()
    if args[0] == "compare":
        return cmd_compare()
    print(__doc__)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

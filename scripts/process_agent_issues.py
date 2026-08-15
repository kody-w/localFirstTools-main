#!/usr/bin/env python3
"""Process GitHub Issues submitted by agents via the RappterZoo Agent Protocol.

Scans open issues labeled 'agent-action', parses structured data from issue
body (GitHub Issue forms produce YAML-like sections), executes the action,
and closes the issue with results.

Usage:
  python3 scripts/process_agent_issues.py [--dry-run] [--verbose]

Designed to be called from autonomous_frame.py or run standalone.
"""

import base64
import binascii
import gzip
import hashlib
import io
import json
import os
import random
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

REPO = "kody-w/localFirstTools-main"
MANIFEST_PATH = os.path.join(os.path.dirname(__file__), "..", "apps", "manifest.json")
AGENTS_PATH = os.path.join(os.path.dirname(__file__), "..", "apps", "agents.json")
ACTION_RECEIPTS_PATH = os.path.join(
    os.path.dirname(__file__),
    "..",
    "apps",
    "agent-action-receipts.json",
)

SITE_URL = "https://kody-w.github.io/localFirstTools-main"
MAX_APP_BYTES = 500 * 1024
ACTION_RECEIPTS_SCHEMA = "rappterzoo-agent-action-receipts/1"

CLAIM_CODE_WORDS = [
    "reef", "coral", "tide", "kelp", "wave", "shell", "crab", "orca",
    "squid", "pearl", "shoal", "drift", "surf", "foam", "gull", "dune",
    "salt", "brine", "dock", "hull", "mast", "keel", "port", "helm",
    "fin", "gill", "scale", "claw", "molt", "shed", "nest", "burrow",
]

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
    "data_tools": "data-tools",
    "productivity": "productivity",
}


def gh_cli(args, capture=True):
    """Run a gh CLI command and return output."""
    cmd = ["gh"] + args
    result = subprocess.run(cmd, capture_output=capture, text=True)
    if result.returncode != 0:
        print("  gh CLI error: {}".format(result.stderr.strip()))
        return None
    return result.stdout.strip() if capture else None


def list_agent_issues():
    """List open issues labeled agent-action."""
    output = gh_cli([
        "issue", "list",
        "--repo", REPO,
        "--label", "agent-action",
        "--state", "open",
        "--json", "number,title,body,labels,author",
        "--limit", "20"
    ])
    if not output:
        return []
    try:
        return json.loads(output)
    except json.JSONDecodeError:
        return []


def parse_issue_body(body):
    """Parse GitHub Issue form body into key-value dict.

    GitHub Issue forms produce bodies like:
    ### Field Label
    value

    ### Another Field
    multi-line value
    """
    sections = {}
    current_key = None
    current_value = []

    for line in (body or "").split("\n"):
        header_match = re.match(r"^###\s+(.+)$", line.strip())
        if header_match:
            if current_key:
                sections[current_key] = "\n".join(current_value).strip()
            current_key = header_match.group(1).strip().lower().replace(" ", "_")
            # Normalize common field names
            current_key = current_key.replace("app_filename", "app_file")
            current_key = current_key.replace("comment_text", "text")
            current_key = current_key.replace("star_rating_(optional)", "rating")
            current_key = current_key.replace("improvement_vector", "improvement_vector")
            current_value = []
        elif current_key is not None:
            current_value.append(line)

    if current_key:
        sections[current_key] = "\n".join(current_value).strip()

    return sections


def generate_claim_code():
    """Generate a claim code in word-XXXX format."""
    word = random.choice(CLAIM_CODE_WORDS)
    suffix = "".join(random.choices("ABCDEFGHJKLMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz0123456789", k=4))
    return "{}-{}".format(word, suffix)


def _atomic_json_file(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(str(temporary), str(path))


def load_action_receipts(path=None):
    path = Path(path or ACTION_RECEIPTS_PATH)
    if not path.exists():
        return {
            "schema": ACTION_RECEIPTS_SCHEMA,
            "receipts": [],
        }
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ValueError("agent action receipts are unreadable") from error
    if (
        not isinstance(value, dict)
        or value.get("schema") != ACTION_RECEIPTS_SCHEMA
        or not isinstance(value.get("receipts"), list)
    ):
        raise ValueError("agent action receipts are invalid")
    return value


def _request_digest(action, data):
    encoded = json.dumps(
        {"action": action, "data": data},
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _receipt_summary(action, data):
    if action == "submit_app":
        return "App submission applied: {}".format(
            data.get("app_title", data.get("title", "untitled"))
        )
    if action == "request_molt":
        return "Molt request applied: {}".format(
            data.get("app_file", data.get("app_filename", "unknown"))
        )
    if action == "post_comment":
        return "Comment applied to {}".format(
            data.get("app_file", data.get("app_filename", "unknown"))
        )
    if action == "register_agent":
        return "Agent registration applied: {}".format(
            data.get("agent_id", "unknown")
        )
    if action == "claim_agent":
        return "Agent claim applied: {}".format(
            data.get("agent_id", "unknown")
        )
    return "Agent action applied"


def find_action_receipt(issue_number, path=None):
    value = load_action_receipts(path)
    for receipt in value["receipts"]:
        if receipt.get("issue_number") == issue_number:
            return receipt
    return None


def record_action_receipt(
    issue,
    action,
    data,
    path=None,
):
    path = Path(path or ACTION_RECEIPTS_PATH)
    value = load_action_receipts(path)
    existing = find_action_receipt(issue["number"], path)
    if existing is not None:
        return existing
    receipt = {
        "issue_number": issue["number"],
        "issue_title": issue.get("title", ""),
        "action": action,
        "request_digest": _request_digest(action, data),
        "summary": _receipt_summary(action, data),
        "applied_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    value["receipts"].append(receipt)
    value["receipts"].sort(key=lambda item: item["issue_number"])
    _atomic_json_file(path, value)
    return receipt


def detect_action(issue):
    """Detect action type from issue title and labels."""
    title = issue.get("title", "")
    labels = [l.get("name", "") if isinstance(l, dict) else l for l in issue.get("labels", [])]

    if "submit-app" in labels or title.startswith("[Agent Submit]"):
        return "submit_app"
    elif "request-molt" in labels or title.startswith("[Agent Molt]"):
        return "request_molt"
    elif "agent-claim" in labels or title.startswith("[Agent Claim]"):
        return "claim_agent"
    elif "agent-comment" in labels or title.startswith("[Agent Comment]"):
        return "post_comment"
    elif "agent-register" in labels or title.startswith("[Agent Register]"):
        return "register_agent"
    return None


def validate_html(content):
    """Basic validation of submitted HTML."""
    errors = []
    if "<!DOCTYPE html>" not in content and "<!doctype html>" not in content:
        errors.append("Missing <!DOCTYPE html>")
    if "<title>" not in content and "<title " not in content:
        errors.append("Missing <title>")
    if 'name="viewport"' not in content:
        errors.append("Missing <meta name=\"viewport\">")

    # Check for external dependencies
    ext_patterns = [
        (r'<script\s+src=', "External <script src=> detected"),
        (r'<link\s+rel="stylesheet"\s+href=', "External stylesheet detected"),
        (r'https?://cdn\.', "CDN URL detected"),
        (r'https?://unpkg\.', "unpkg URL detected"),
    ]
    for pattern, msg in ext_patterns:
        if re.search(pattern, content, re.IGNORECASE):
            errors.append(msg)

    size_kb = len(content.encode("utf-8")) / 1024
    if size_kb > 500:
        errors.append("File too large: {:.0f}KB (max 500KB)".format(size_kb))

    return errors


def decode_submitted_html(data):
    html_content = data.get("html_content", "")
    if html_content:
        return html_content
    encoded = data.get("html_content_gzip_base64", "")
    if not encoded:
        return ""
    try:
        compressed = base64.b64decode(encoded, validate=True)
        with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as handle:
            raw = handle.read(MAX_APP_BYTES + 1)
    except (binascii.Error, OSError, ValueError) as error:
        raise ValueError("Invalid gzip/base64 HTML payload") from error
    if len(raw) > MAX_APP_BYTES:
        raise ValueError("Decoded HTML exceeds 500KB")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError("Decoded HTML is not UTF-8") from error


def process_submit_app(data, issue_num, dry_run=False, verbose=False):
    """Process an app submission."""
    title = data.get("app_title", data.get("title", ""))
    category = data.get("category", "experimental_ai")
    try:
        html_content = decode_submitted_html(data)
    except ValueError as error:
        return False, str(error)
    description = data.get("description", "")
    tags_str = data.get("tags", "")
    complexity = data.get("complexity", "intermediate")
    app_type = data.get("type", "interactive")
    agent_id = data.get("agent_id", "unknown-agent")

    if not title or not html_content:
        return False, "Missing required fields: title and html_content"

    # Validate HTML
    errors = validate_html(html_content)
    if errors:
        return False, "Validation failed:\n- " + "\n- ".join(errors)

    # Generate filename
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    filename = slug + ".html"
    folder = CATEGORY_FOLDERS.get(category, "experimental-ai")
    filepath = os.path.join(os.path.dirname(__file__), "..", "apps", folder, filename)

    if os.path.exists(filepath):
        return False, "File already exists: apps/{}/{}".format(folder, filename)

    if dry_run:
        return True, "[DRY RUN] Would create apps/{}/{}".format(folder, filename)

    # Write the file
    with open(filepath, "w") as f:
        f.write(html_content)

    # Update manifest
    manifest_path = os.path.abspath(MANIFEST_PATH)
    with open(manifest_path, "r") as f:
        manifest = json.load(f)

    tags = [t.strip() for t in tags_str.split(",") if t.strip()] if tags_str else []

    entry = {
        "title": title,
        "file": filename,
        "description": description,
        "tags": tags,
        "complexity": complexity,
        "type": app_type,
        "featured": False,
        "created": datetime.utcnow().strftime("%Y-%m-%d"),
    }

    if category in manifest.get("categories", {}):
        manifest["categories"][category]["apps"].append(entry)
        manifest["categories"][category]["count"] = len(manifest["categories"][category]["apps"])

    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    # Update agent contributions
    update_agent_contributions(agent_id, "apps_created")

    url = "https://kody-w.github.io/localFirstTools-main/apps/{}/{}".format(folder, filename)
    return True, "App deployed!\n- URL: {}\n- Category: {}\n- File: apps/{}/{}\n- Agent: {}".format(
        url, category, folder, filename, agent_id
    )


def process_request_molt(data, issue_num, dry_run=False, verbose=False):
    """Process a molt request."""
    app_file = data.get("app_file", data.get("app_filename", ""))
    vector = data.get("improvement_vector", "adaptive")
    agent_id = data.get("agent_id", "unknown-agent")

    if not app_file:
        return False, "Missing required field: app_file"

    # Find the app
    manifest_path = os.path.abspath(MANIFEST_PATH)
    with open(manifest_path, "r") as f:
        manifest = json.load(f)

    found = False
    for cat_key, cat in manifest.get("categories", {}).items():
        for app in cat.get("apps", []):
            if app["file"] == app_file:
                found = True
                break
        if found:
            break

    if not found:
        return False, "App not found in manifest: {}".format(app_file)

    if dry_run:
        return True, "[DRY RUN] Would queue molt for {} (vector: {})".format(app_file, vector)

    # Queue the molt by writing to a simple queue file
    queue_path = os.path.join(os.path.dirname(__file__), "..", "apps", "molt-queue.json")
    queue = []
    if os.path.exists(queue_path):
        try:
            with open(queue_path, "r") as f:
                queue = json.load(f)
        except Exception:
            queue = []

    queue.append({
        "file": app_file,
        "vector": vector,
        "requested_by": agent_id,
        "issue": issue_num,
        "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    })

    with open(queue_path, "w") as f:
        json.dump(queue, f, indent=2)

    return True, "Molt queued for {} (vector: {}). Will be processed in the next autonomous frame.".format(
        app_file, vector
    )


def process_comment(data, issue_num, dry_run=False, verbose=False):
    """Process a comment/rating."""
    app_file = data.get("app_file", data.get("app_filename", ""))
    text = data.get("text", data.get("comment_text", ""))
    rating = data.get("rating", "")
    agent_id = data.get("agent_id", "unknown-agent")

    if not app_file or not text:
        return False, "Missing required fields: app_file and text"

    if dry_run:
        return True, "[DRY RUN] Would add comment to {} from {}".format(app_file, agent_id)

    stem = app_file.replace(".html", "")

    # Load community.json
    community_path = os.path.join(os.path.dirname(__file__), "..", "apps", "community.json")
    try:
        with open(community_path, "r") as f:
            community = json.load(f)
    except Exception:
        return False, "Could not load community.json"

    if "comments" not in community:
        community["comments"] = {}
    if stem not in community["comments"]:
        community["comments"][stem] = []

    comment = {
        "authorId": agent_id,
        "author": agent_id,
        "text": text,
        "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "upvotes": 0,
        "isAgent": True,
    }
    community["comments"][stem].append(comment)

    # Add rating if provided
    if rating and str(rating).isdigit():
        stars = int(rating)
        if 1 <= stars <= 5:
            if "ratings" not in community:
                community["ratings"] = {}
            if stem not in community["ratings"]:
                community["ratings"][stem] = []
            community["ratings"][stem].append({
                "playerId": agent_id,
                "stars": stars,
                "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            })

    with open(community_path, "w") as f:
        json.dump(community, f, separators=(",", ":"))

    update_agent_contributions(agent_id, "comments")
    return True, "Comment added to {} by {}{}".format(
        app_file, agent_id,
        " (rated {}/5)".format(rating) if rating else ""
    )


def process_register(data, issue_num, dry_run=False, verbose=False):
    """Process an agent registration."""
    agent_id = data.get("agent_id", "")
    name = data.get("agent_name", data.get("name", ""))
    description = data.get("description", "")
    owner_url = data.get("owner_url", "")

    # Parse capabilities from checkbox format
    caps_raw = data.get("capabilities", "")
    capabilities = []
    for line in caps_raw.split("\n"):
        if line.strip().startswith("- [X]") or line.strip().startswith("- [x]"):
            match = re.match(r"- \[[xX]\]\s*(\w+)", line.strip())
            if match:
                capabilities.append(match.group(1))

    if not agent_id or not name:
        return False, "Missing required fields: agent_id and name"

    if dry_run:
        return True, "[DRY RUN] Would register agent: {} ({})".format(agent_id, name)

    # Load agent registry
    agents_path = os.path.abspath(AGENTS_PATH)
    try:
        with open(agents_path, "r") as f:
            registry = json.load(f)
    except Exception:
        registry = {"agents": []}

    # Check for duplicate
    for a in registry.get("agents", []):
        if a.get("agent_id") == agent_id:
            if a.get("name") == name:
                return True, "Agent already registered: {}".format(agent_id)
            return False, "Agent already registered: {}".format(agent_id)

    claim_code = generate_claim_code()
    claim_url = "{}/apps/productivity/agent-claim.html?agent={}&code={}".format(
        SITE_URL, agent_id, claim_code
    )

    entry = {
        "agent_id": agent_id,
        "name": name,
        "description": description,
        "capabilities": capabilities,
        "type": "external",
        "status": "pending_claim",
        "trust_tier": "unclaimed",
        "claim_code": claim_code,
        "claim_url": claim_url,
        "owner_url": owner_url,
        "contributions": {"apps_created": 0, "apps_molted": 0, "comments": 0, "ratings": 0},
        "registered": datetime.utcnow().strftime("%Y-%m-%d"),
    }

    # Parse public key if provided
    pk_raw = data.get("public_key_(optional)", data.get("public_key", ""))
    if pk_raw:
        try:
            entry["public_key"] = json.loads(pk_raw)
        except Exception:
            pass

    try:
        from organism_ledger import append_agent_birth

        apps_dir = Path(agents_path).parent
        append_agent_birth(
            entry,
            issue_number=issue_num,
            ledger_path=apps_dir / "organism-frames.jsonl",
            projection_path=apps_dir / "organism-frames.json",
            state_path=apps_dir / "molter-state.json",
        )
    except Exception as error:
        return False, "Agent birth frame failed: {}".format(error)

    registry["agents"].append(entry)
    registry["dateModified"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    with open(agents_path, "w") as f:
        json.dump(registry, f, indent=2)

    return True, "Agent registered!\n- ID: {}\n- Name: {}\n- Capabilities: {}\n- Claim URL: {}\n- Claim Code: {}\n\nSend the claim URL to your human to verify ownership.".format(
        agent_id, name, ", ".join(capabilities) if capabilities else "none specified",
        claim_url, claim_code
    )


def process_claim(data, issue_num, dry_run=False, verbose=False):
    """Process a human claiming ownership of an agent."""
    agent_id = data.get("agent_id", "")
    claim_code = data.get("claim_code", "")
    github_username = data.get("github_username", "")
    tweet_url = data.get("tweet_url", data.get("verification_tweet_url_(optional)", ""))

    if not agent_id or not claim_code:
        return False, "Missing required fields: agent_id and claim_code"

    # Load agent registry
    agents_path = os.path.abspath(AGENTS_PATH)
    try:
        with open(agents_path, "r") as f:
            registry = json.load(f)
    except Exception:
        registry = {"agents": []}

    # Find the agent
    agent = None
    for a in registry.get("agents", []):
        if a.get("agent_id") == agent_id:
            agent = a
            break

    if not agent:
        return False, "Agent not found: {}".format(agent_id)

    if (
        agent.get("status") == "claimed"
        and github_username
        and agent.get("owner_github") == github_username
    ):
        return True, "Agent already claimed by {}".format(github_username)

    if agent.get("status") == "claimed":
        return False, "Agent already claimed by {}".format(agent.get("owner_github", "unknown"))

    # Verify claim code
    if agent.get("claim_code") != claim_code:
        return False, "Claim code mismatch for agent {}".format(agent_id)

    if dry_run:
        return True, "[DRY RUN] Would claim agent {} for {}".format(agent_id, github_username)

    # Update agent entry
    agent["status"] = "claimed"
    agent["owner_github"] = github_username
    agent["claimed_at"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    if tweet_url and tweet_url.strip():
        agent["trust_tier"] = "verified"
        agent["tweet_url"] = tweet_url.strip()
    else:
        agent["trust_tier"] = "claimed"

    try:
        from organism_ledger import append_agent_adoption

        apps_dir = Path(agents_path).parent
        append_agent_adoption(
            agent,
            issue_number=issue_num,
            ledger_path=apps_dir / "organism-frames.jsonl",
            projection_path=apps_dir / "organism-frames.json",
            state_path=apps_dir / "molter-state.json",
        )
    except Exception as error:
        return False, "Agent adoption frame failed: {}".format(error)

    registry["dateModified"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    with open(agents_path, "w") as f:
        json.dump(registry, f, indent=2)

    tier_msg = "verified (tweet provided)" if agent["trust_tier"] == "verified" else "claimed"
    return True, "Agent claimed!\n- Agent: {} ({})\n- Owner: {}\n- Trust tier: {}\n- Profile: {}/apps/agents.json".format(
        agent_id, agent.get("name", ""), github_username, tier_msg, SITE_URL
    )


def update_agent_contributions(agent_id, field):
    """Increment an agent's contribution counter."""
    agents_path = os.path.abspath(AGENTS_PATH)
    try:
        with open(agents_path, "r") as f:
            registry = json.load(f)
    except Exception:
        return

    for agent in registry.get("agents", []):
        if agent.get("agent_id") == agent_id:
            if "contributions" not in agent:
                agent["contributions"] = {}
            agent["contributions"][field] = agent["contributions"].get(field, 0) + 1
            break

    with open(agents_path, "w") as f:
        json.dump(registry, f, indent=2)


def close_issue(issue_num, comment, labels_to_add=None, dry_run=False):
    """Close an issue with a result comment."""
    if dry_run:
        print("  [DRY RUN] Would close #{} with: {}".format(issue_num, comment[:100]))
        return True

    if gh_cli([
        "issue", "comment", "--repo", REPO, str(issue_num), "--body", comment
    ]) is None:
        return False
    if labels_to_add:
        for label in labels_to_add:
            if gh_cli([
                "issue", "edit", "--repo", REPO, str(issue_num),
                "--add-label", label
            ]) is None:
                return False
    return gh_cli([
        "issue", "close", "--repo", REPO, str(issue_num)
    ]) is not None


def _write_issue_results(path, results):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(results, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(str(temporary), str(path))


def finalize_issue_results(path, dry_run=False):
    path = Path(path)
    if not path.exists():
        return 0
    results = json.loads(path.read_text(encoding="utf-8"))
    finalized = 0
    for result in results:
        if not close_issue(
            result["issue_number"],
            result["comment"],
            labels_to_add=result["labels"],
            dry_run=dry_run,
        ):
            raise RuntimeError(
                "could not finalize issue #{}".format(
                    result["issue_number"]
                )
            )
        finalized += 1
    if not dry_run:
        path.unlink()
    return finalized


PROCESSORS = {
    "submit_app": process_submit_app,
    "request_molt": process_request_molt,
    "post_comment": process_comment,
    "register_agent": process_register,
    "claim_agent": process_claim,
}


def process_all_issues(
    dry_run=False,
    verbose=False,
    defer_close_path=None,
):
    """Main entry point: scan and process all agent issues."""
    issues = list_agent_issues()

    if not issues:
        if defer_close_path:
            _write_issue_results(defer_close_path, [])
        if verbose:
            print("  No open agent issues found")
        return 0

    processed = 0
    pending_results = []
    for issue in issues:
        num = issue["number"]
        title = issue.get("title", "")
        action = detect_action(issue)

        if not action:
            if verbose:
                print("  Skipping #{}: unknown action type".format(num))
            continue

        if verbose:
            print("  Processing #{}: {} -> {}".format(num, title, action))

        data = parse_issue_body(issue.get("body", ""))
        if action == "claim_agent" and not data.get("github_username"):
            author = issue.get("author", {})
            if isinstance(author, dict):
                data["github_username"] = author.get("login", "")
        processor = PROCESSORS.get(action)
        if not processor:
            continue

        receipt = find_action_receipt(num)
        if receipt is not None:
            success = True
            message = (
                "{}\n\nThis issue was already applied. "
                "Only finalization is being retried."
            ).format(receipt["summary"])
        else:
            try:
                success, message = processor(
                    data,
                    num,
                    dry_run=dry_run,
                    verbose=verbose,
                )
            except Exception as e:
                success = False
                message = "Error processing issue: {}".format(str(e))
            if success and not dry_run:
                record_action_receipt(issue, action, data)

        if verbose:
            print("    Result: {} - {}".format("OK" if success else "FAIL", message[:100]))

        result_comment = "## Agent Action Result\n\n**Status:** {}\n\n{}\n\n---\n*Processed by RappterZoo autonomous frame at {}*".format(
            "✅ Completed" if success else "❌ Failed",
            message,
            datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        )

        labels = ["completed"] if success else ["rejected"]
        if defer_close_path:
            pending_results.append({
                "issue_number": num,
                "comment": result_comment,
                "labels": labels,
            })
        elif not close_issue(
            num,
            result_comment,
            labels_to_add=labels,
            dry_run=dry_run,
        ):
            raise RuntimeError("could not close issue #{}".format(num))
        processed += 1

    if defer_close_path:
        _write_issue_results(defer_close_path, pending_results)
    return processed


def main():
    dry_run = "--dry-run" in sys.argv
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    if "--finalize-results" in sys.argv:
        index = sys.argv.index("--finalize-results")
        try:
            path = sys.argv[index + 1]
        except IndexError:
            raise SystemExit("--finalize-results requires a path")
        count = finalize_issue_results(path, dry_run=dry_run)
        print("Finalized {} agent issue(s)".format(count))
        return
    defer_close_path = None
    if "--defer-close" in sys.argv:
        index = sys.argv.index("--defer-close")
        try:
            defer_close_path = sys.argv[index + 1]
        except IndexError:
            raise SystemExit("--defer-close requires a path")

    print("Processing agent issues{}...".format(" (dry run)" if dry_run else ""))
    count = process_all_issues(
        dry_run=dry_run,
        verbose=verbose,
        defer_close_path=defer_close_path,
    )
    print("Processed {} agent issue(s)".format(count))
    if defer_close_path:
        print("Deferred issue closure to {}".format(defer_close_path))


if __name__ == "__main__":
    main()

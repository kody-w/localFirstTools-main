#!/usr/bin/env python3
"""Process GitHub Issues submitted by agents via the RappterZoo Agent Protocol.

Scans open issues labeled 'agent-action', parses structured data from issue
body (GitHub Issue forms produce YAML-like sections), executes the action,
and closes the issue with results.

Usage:
  python3 scripts/process_agent_issues.py [--dry-run] [--verbose]

Designed to be called from autonomous_frame.py or run standalone.
"""

import json
import os
import random
import re
import subprocess
import sys
from datetime import datetime

REPO = "kody-w/localFirstTools-main"
MANIFEST_PATH = os.path.join(os.path.dirname(__file__), "..", "apps", "manifest.json")
AGENTS_PATH = os.path.join(os.path.dirname(__file__), "..", "apps", "agents.json")

SITE_URL = "https://kody-w.github.io/localFirstTools-main"

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
        "--json", "number,title,body,labels",
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


def process_submit_app(data, issue_num, dry_run=False, verbose=False):
    """Process an app submission."""
    title = data.get("app_title", data.get("title", ""))
    category = data.get("category", "experimental_ai")
    html_content = data.get("html_content", "")
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
        return

    gh_cli(["issue", "comment", "--repo", REPO, str(issue_num), "--body", comment])
    if labels_to_add:
        for label in labels_to_add:
            gh_cli(["issue", "edit", "--repo", REPO, str(issue_num), "--add-label", label])
    gh_cli(["issue", "close", "--repo", REPO, str(issue_num)])


PROCESSORS = {
    "submit_app": process_submit_app,
    "request_molt": process_request_molt,
    "post_comment": process_comment,
    "register_agent": process_register,
    "claim_agent": process_claim,
}


def process_all_issues(dry_run=False, verbose=False):
    """Main entry point: scan and process all agent issues."""
    issues = list_agent_issues()

    if not issues:
        if verbose:
            print("  No open agent issues found")
        return 0

    processed = 0
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
        processor = PROCESSORS.get(action)
        if not processor:
            continue

        try:
            success, message = processor(data, num, dry_run=dry_run, verbose=verbose)
        except Exception as e:
            success = False
            message = "Error processing issue: {}".format(str(e))

        if verbose:
            print("    Result: {} - {}".format("OK" if success else "FAIL", message[:100]))

        result_comment = "## Agent Action Result\n\n**Status:** {}\n\n{}\n\n---\n*Processed by RappterZoo autonomous frame at {}*".format(
            "✅ Completed" if success else "❌ Failed",
            message,
            datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        )

        labels = ["completed"] if success else ["rejected"]
        close_issue(num, result_comment, labels_to_add=labels, dry_run=dry_run)
        processed += 1

    return processed


def main():
    dry_run = "--dry-run" in sys.argv
    verbose = "--verbose" in sys.argv or "-v" in sys.argv

    print("Processing agent issues{}...".format(" (dry run)" if dry_run else ""))
    count = process_all_issues(dry_run=dry_run, verbose=verbose)
    print("Processed {} agent issue(s)".format(count))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Check upstream mattpocock/skills and write claude/pocock-skills-workflow/sync-status.json.

Uses only the Python standard library so it runs cleanly in GitHub Actions and
local environments without extra installs.

Usage:
    python update_pocock_sync.py            # fetch and write sync-status.json
    python update_pocock_sync.py --dry-run  # print JSON to stdout instead
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT_PATH = ROOT / "claude" / "pocock-skills-workflow" / "sync-status.json"
UPSTREAM_REPO = "mattpocock/skills"

# The 27 core production skills mapped in claude/pocock-skills-workflow/index.html
MAPPED_CORE_SKILLS = sorted([
    # Engineering (20)
    "ask-matt",
    "code-review",
    "codebase-design",
    "diagnosing-bugs",
    "domain-modeling",
    "grill-with-docs",
    "implement",
    "implement-spec",
    "improve-codebase-architecture",
    "pr",
    "prototype",
    "research",
    "retro",
    "setup-matt-pocock-skills",
    "tdd",
    "to-spec",
    "to-tickets",
    "triage",
    "wayfinder",
    "wizard",
    # Productivity (7)
    "grill-me",
    "grilling",
    "handoff",
    "teach",
    "to-questionnaire",
    "wait-what",
    "writing-for-agents",
])


def github_get_json(url: str, token: str | None = None) -> dict:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "mastery-sites-pocock-sync",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def parse_skill_tree(tree_items: list[dict]) -> dict[str, list[str]]:
    """Extract sorted skill names grouped by category from a GitHub git tree payload."""
    buckets: dict[str, set[str]] = {
        "engineering": set(),
        "productivity": set(),
        "in-progress": set(),
        "misc": set(),
    }
    for item in tree_items:
        path = item.get("path", "")
        parts = path.split("/")
        # Expected shape: skills/<category>/<skill-name>/SKILL.md
        if len(parts) == 4 and parts[0] == "skills" and parts[3] == "SKILL.md":
            cat, name = parts[1], parts[2]
            if cat in buckets:
                buckets[cat].add(name)
    return {k: sorted(v) for k, v in buckets.items()}


def build_sync_payload(
    release: dict,
    tree_items: list[dict],
    checked_at: str | None = None,
    mapped_core: list[str] | None = None,
) -> dict:
    grouped = parse_skill_tree(tree_items)
    upstream_core = sorted(set(grouped["engineering"]) | set(grouped["productivity"]))
    mapped_set = set(mapped_core if mapped_core is not None else MAPPED_CORE_SKILLS)
    upstream_set = set(upstream_core)

    added_upstream = sorted(upstream_set - mapped_set)
    removed_upstream = sorted(mapped_set - upstream_set)

    return {
        "repo": UPSTREAM_REPO,
        "repo_url": f"https://github.com/{UPSTREAM_REPO}",
        "release_tag": release.get("tag_name") or release.get("name") or "unknown",
        "release_published": release.get("published_at") or "",
        "checked_at": checked_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "in_sync": not added_upstream and not removed_upstream,
        "mapped_count": len(mapped_set),
        "upstream_core_count": len(upstream_set),
        "added_upstream": added_upstream,
        "removed_upstream": removed_upstream,
        "categories": {
            "engineering": grouped["engineering"],
            "productivity": grouped["productivity"],
            "in_progress": grouped["in-progress"],
            "misc": grouped["misc"],
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="Print JSON to stdout without writing.")
    args = ap.parse_args()

    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    try:
        release = github_get_json(f"https://api.github.com/repos/{UPSTREAM_REPO}/releases/latest", token)
        tree = github_get_json(f"https://api.github.com/repos/{UPSTREAM_REPO}/git/trees/main?recursive=1", token)
    except urllib.error.URLError as exc:
        print(f"error fetching {UPSTREAM_REPO}: {exc}", file=sys.stderr)
        return 1

    payload = build_sync_payload(release, tree.get("tree", []))
    rendered = json.dumps(payload, indent=2) + "\n"

    if args.dry_run:
        sys.stdout.write(rendered)
        return 0

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(rendered, encoding="utf-8", newline="\n")
    status = "IN SYNC" if payload["in_sync"] else f"DRIFT (+{len(payload['added_upstream'])} / -{len(payload['removed_upstream'])})"
    print(f"Wrote {OUT_PATH.relative_to(ROOT)} ({payload['release_tag']} · {status})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

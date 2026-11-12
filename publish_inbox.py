#!/usr/bin/env python3
"""Publish every .html page in inbox/ as a site: import, test, push, verify, archive.

    python publish_inbox.py [--dry-run] [--yes] [--local]

For each inbox/*.html page the script picks a category, folder name,
description and tags, shows the plan, and waits for "y". Then it:
  1. runs import_site.py for each page (which regenerates the index),
  2. runs the full test suite and stops before committing if anything fails,
  3. commits only the new site folders and index.html, pulls, and pushes,
  4. waits for the Workers Builds check and fetches each live URL,
  5. moves each source into inbox/archive/ once its live page is verified.

Metadata comes from an LLM through OpenRouter (OPENROUTER_API_KEY, model
OPENROUTER_MODEL, default ~anthropic/claude-haiku-latest). Plans are saved in
inbox/.plans.json, so a real run reuses what the dry run showed. The page's title
and first few thousand characters of visible text are sent. With --local,
or for a file named category--slug.html, nothing is sent: the file name
gives the target and the page's meta description or <title> gives the
description.

inbox/ is gitignored and skipped by the generator, so drafts never deploy.
"""
import argparse
import html
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from generate_index import CATEGORY_DOTS
from import_site import SLUG_RE, TITLE_RE, existing_fingerprints, fingerprint

ROOT = Path(__file__).resolve().parent
INBOX = ROOT / "inbox"
PLANS_NAME = ".plans.json"  # in INBOX: page fingerprint -> plan, so the real run repeats the dry run
LIVE_BASE = "https://mastery-sites.stenguye.workers.dev"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "~anthropic/claude-haiku-latest"
CHECK_NAME = "Workers Builds: mastery-sites"
TEXT_LIMIT = 3000
DESC_LIMIT = 160
META_DESC_RE = re.compile(
    r'<meta\s+[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)["\']', re.IGNORECASE)
STRIP_RE = re.compile(r"<(script|style|head)\b.*?</\1>", re.IGNORECASE | re.DOTALL)
TAG_RE = re.compile(r"<[^>]+>")


def page_title(text: str) -> str:
    m = TITLE_RE.search(text)
    return html.unescape(re.sub(r"\s+", " ", m.group(1))).strip() if m else ""


def visible_text(text: str, limit: int = TEXT_LIMIT) -> str:
    body = TAG_RE.sub(" ", STRIP_RE.sub(" ", text))
    return re.sub(r"\s+", " ", html.unescape(body)).strip()[:limit]


def from_filename(name: str) -> tuple[str, str] | None:
    """category--slug.html -> (category, slug), else None."""
    stem = Path(name).stem
    if "--" not in stem:
        return None
    category, slug = stem.split("--", 1)
    return category, slug


def local_plan(src: Path, text: str) -> dict:
    target = from_filename(src.name)
    if not target:
        raise ValueError("--local needs a file named category--slug.html")
    m = META_DESC_RE.search(text)
    description = html.unescape(m.group(1)).strip() if m else page_title(text)
    return {"category": target[0], "slug": target[1], "description": description, "tags": []}


def llm_plan(text: str, categories: list[str], model: str, key: str) -> dict:
    prompt = (
        "You file standalone HTML reference pages into a site index.\n"
        f"Existing categories (pick exactly one): {', '.join(categories)}\n"
        "Return only a JSON object with keys:\n"
        '  "category": one of the existing categories,\n'
        '  "slug": lowercase-hyphenated folder name, 2-5 words, no category prefix,\n'
        f'  "description": one plain sentence under {DESC_LIMIT} characters for the index card,\n'
        '  "tags": 2-4 short lowercase tags.\n\n'
        f"Title: {page_title(text)}\n\n{visible_text(text)}"
    )
    body = {
        "model": model,
        "temperature": 0,  # same page, same plan: a dry run should predict the real run
        "response_format": {"type": "json_object"},
        "messages": [{"role": "user", "content": prompt}],
    }
    req = urllib.request.Request(
        OPENROUTER_URL, data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                 "X-Title": "mastery-sites publish_inbox"})
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            content = json.load(r)["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as exc:
        raise ValueError(f"OpenRouter returned HTTP {exc.code}: {exc.read()[:300]!r}")
    m = re.search(r"\{.*\}", content, re.DOTALL)  # tolerate code fences around the JSON
    if not m:
        raise ValueError(f"LLM reply was not JSON: {content[:200]!r}")
    return json.loads(m.group(0))


def validate(plan: dict, categories: list[str], taken: set[str]) -> dict:
    """Normalize an LLM or filename plan; raise ValueError naming the first problem."""
    category = str(plan.get("category", "")).strip().lower()
    slug = str(plan.get("slug", "")).strip().lower()
    description = re.sub(r"\s+", " ", str(plan.get("description", ""))).strip()
    raw_tags = plan.get("tags") or []
    if isinstance(raw_tags, str):
        raw_tags = raw_tags.split(",")
    tags = [re.sub(r"\s+", "-", str(t).strip().lower()) for t in raw_tags if str(t).strip()][:4]
    if category not in categories:
        raise ValueError(f"category {category!r} is not one of the existing categories; "
                         "add it to CATEGORY_DOTS and CATEGORY_BLURBS first, or rename the file")
    if not SLUG_RE.match(slug):
        raise ValueError(f"slug {slug!r} is not lowercase-hyphenated")
    if f"{category}/{slug}" in taken:
        raise ValueError(f"{category}/{slug} already exists")
    if not description:
        raise ValueError("description is empty")
    if len(description) > DESC_LIMIT:
        description = description[:DESC_LIMIT - 1].rstrip() + "…"
    return {"category": category, "slug": slug, "description": description, "tags": tags}


def load_plans(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def existing_targets(root: Path) -> set[str]:
    return {f"{p.parts[-3]}/{p.parts[-2]}" for p in root.glob("*/*/index.html")}


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=ROOT, check=True, **kw)


def git(*args: str) -> str:
    return run(["git", *args], capture_output=True, text=True).stdout.strip()


def run_tests() -> None:
    run([sys.executable, "-m", "unittest", "discover", "-s", "tests"])
    run(["node", "tests/test_index.cjs", "index.html"])


def wait_for_deploy(sha: str, timeout: int = 600) -> str:
    """Poll the Workers Builds check on sha; return its conclusion, or 'unknown'."""
    remote = git("remote", "get-url", "origin")
    m = re.search(r"github\.com[:/](.+?)(?:\.git)?$", remote)
    if not m:
        return "unknown"
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            out = subprocess.run(
                ["gh", "api", f"repos/{m.group(1)}/commits/{sha}/check-runs",
                 "--jq", f'.check_runs[] | select(.name == "{CHECK_NAME}") | "\\(.status) \\(.conclusion)"'],
                capture_output=True, text=True, check=True).stdout.split()
        except (OSError, subprocess.CalledProcessError):
            return "unknown"
        if out and out[0] == "completed":
            return out[1]
        time.sleep(10)
    return "timeout"


def live_ok(path: str, title: str) -> bool:
    try:
        # Cloudflare answers 403 to urllib's default User-Agent
        req = urllib.request.Request(f"{LIVE_BASE}/{path}/", headers={"User-Agent": "mastery-sites-publish/1.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status == 200 and title in html.unescape(r.read().decode("utf-8", "ignore"))
    except (urllib.error.URLError, TimeoutError):
        return False


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="Show the plan; import and push nothing.")
    ap.add_argument("--yes", action="store_true", help="Skip the confirmation prompt.")
    ap.add_argument("--local", action="store_true", help="Send nothing to OpenRouter; use category--slug.html names.")
    args = ap.parse_args()

    sources = sorted(INBOX.glob("*.html")) if INBOX.is_dir() else []
    if not sources:
        raise SystemExit(f"nothing to publish: no .html files in {INBOX.relative_to(ROOT)}/")
    if not args.dry_run:
        if git("status", "--porcelain"):
            raise SystemExit("working tree has uncommitted changes; commit or stash them first")
        git("pull", "--ff-only", "--quiet")

    categories = sorted(CATEGORY_DOTS)
    taken = existing_targets(ROOT)
    deployed = existing_fingerprints(ROOT)
    model = os.environ.get("OPENROUTER_MODEL", DEFAULT_MODEL)
    key = os.environ.get("OPENROUTER_API_KEY", "")
    plans_file = INBOX / PLANS_NAME  # resolved here so it always follows INBOX
    cache, kept = load_plans(plans_file), {}
    plans, skipped = [], []
    for src in sources:
        text = src.read_text(encoding="utf-8")
        dupe = deployed.get(fingerprint(text))
        if dupe:  # import_site.py would refuse it mid-run, after earlier pages were imported
            skipped.append((src, f"already published as {dupe.parent.relative_to(ROOT)}; delete it from inbox/"))
            continue
        fp = fingerprint(text)
        try:
            if fp in cache and not args.local:
                plan = cache[fp]
            elif args.local or from_filename(src.name):
                plan = local_plan(src, text)
            elif not key:
                raise ValueError("OPENROUTER_API_KEY is not set; use --local or a category--slug.html name")
            else:
                plan = llm_plan(text, categories, model, key)
            plan = validate(plan, categories, taken)
            kept[fp] = plan
        except ValueError as exc:
            skipped.append((src, str(exc)))
            continue
        taken.add(f"{plan['category']}/{plan['slug']}")
        plans.append((src, text, plan))

    plans_file.write_text(json.dumps(kept, indent=1), encoding="utf-8")
    for src, text, p in plans:
        print(f"\n{src.name}\n  -> {p['category']}/{p['slug']}\n  {p['description']}\n  tags: {', '.join(p['tags']) or '-'}")
    for src, reason in skipped:
        print(f"\nSKIP {src.name}: {reason}")
    if not plans:
        raise SystemExit("\nnothing to publish")
    if args.dry_run:
        print("\ndry run: nothing imported or pushed")
        return
    if not args.yes and input(f"\nPublish {len(plans)} site(s) to production? [y/N] ").strip().lower() != "y":
        raise SystemExit("cancelled; nothing changed")

    targets = []
    for src, text, p in plans:
        target = f"{p['category']}/{p['slug']}"
        run([sys.executable, "import_site.py", str(src), target,
             "--description", p["description"], "--tags", ", ".join(p["tags"])])
        targets.append((src, target, page_title(text)))

    try:
        run_tests()
    except subprocess.CalledProcessError:
        raise SystemExit("tests failed; new sites are imported but not committed. "
                         "Fix them, or remove the new folders and run python generate_index.py")

    run(["git", "add", "index.html", *[t for _, t, _ in targets]])
    names = ", ".join(t for _, t, _ in targets)
    run(["git", "commit", "-q", "-m", f"Add {names}" if len(targets) == 1 else f"Add {len(targets)} sites: {names}"])
    try:
        run(["git", "push", "-q", "origin", "main"])
    except subprocess.CalledProcessError:
        run(["git", "pull", "--rebase", "-q"])  # the daily bot may have pushed meanwhile
        run(["git", "push", "-q", "origin", "main"])
    sha = git("rev-parse", "HEAD")
    print(f"\npushed {sha[:7]}; waiting for {CHECK_NAME} ...")

    conclusion = wait_for_deploy(sha)
    print(f"deploy: {conclusion}")
    if conclusion != "success":
        raise SystemExit("deploy not confirmed; sources stay in inbox/. Check Cloudflare, then re-run "
                         "import_site.py SRC TARGET --archive for each verified page")
    for src, target, title in targets:
        if live_ok(target, title):
            run([sys.executable, "import_site.py", str(src), target, "--description", "-", "--archive"],
                capture_output=True)
            print(f"live  {LIVE_BASE}/{target}/  (source archived)")
        else:
            print(f"NOT VERIFIED  {LIVE_BASE}/{target}/  (source left in inbox/)")


if __name__ == "__main__":
    main()

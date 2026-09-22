#!/usr/bin/env python3
"""Import a standalone HTML page from the inbox into this repository as a site.

    python import_site.py SRC.html CATEGORY/SLUG --description "..." [--tags a,b] [--pinned] [--archive]

What it does, in order:
  1. Refuses if CATEGORY/SLUG/index.html already exists.
  2. Refuses if the page body is byte-identical (after front-matter and
     homebar are stripped and whitespace collapsed) to any deployed site,
     so a re-dropped file does not become a second copy.
  3. Copies the source, inserting the <!-- index: --> block after the
     doctype and the All-sites bar as the first child of <body>. Nothing
     else in the source is changed.
  4. Runs generate_index.py.
  5. With --archive, moves the source into the sibling archive/ folder next
     to it, never overwriting an existing archive file.

Only step 5 touches the inbox. Deploy verification stays manual: push,
check the live path, then archive (or run again with --archive later).
"""
import argparse
import hashlib
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
HOMEBAR = (
    '<nav id="ms-homebar" class="ms-homebar" aria-label="All sites">'
    '<a href="https://mastery-sites.stenguye.workers.dev/">All sites</a></nav>\n'
    '<style>#ms-homebar{position:sticky;top:0;z-index:2147483647;display:block;'
    'padding:8px 14px;background:#111827;font:600 13px/1.2 system-ui,-apple-system,'
    '"Segoe UI",sans-serif;border-bottom:1px solid #1f2937}#ms-homebar a{color:#93c5fd;'
    'text-decoration:none}#ms-homebar a:hover{text-decoration:underline;color:#bfdbfe}</style>'
)
FM_RE = re.compile(r"<!--\s*index:.*?-->\s*", re.DOTALL | re.IGNORECASE)
BAR_RE = re.compile(r'<nav id="ms-homebar".*?</nav>\s*<style>#ms-homebar.*?</style>\s*', re.DOTALL)
DOCTYPE_RE = re.compile(r"<!DOCTYPE html[^>]*>\s*", re.IGNORECASE)
BODY_RE = re.compile(r"<body[^>]*>", re.IGNORECASE)
TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def fingerprint(text: str) -> str:
    body = BAR_RE.sub("", FM_RE.sub("", text))
    body = re.sub(r"\s+", " ", body).strip()
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def existing_fingerprints(root: Path) -> dict[str, Path]:
    out = {}
    for page in root.glob("*/*/index.html"):
        if page.parts[-3].startswith(".") or page.parts[-3] in {"tests", "__pycache__"}:
            continue
        out[fingerprint(page.read_text(encoding="utf-8", errors="ignore"))] = page
    return out


def build_page(src_text: str, description: str, tags: str, pinned: bool, ingested: str) -> str:
    if not TITLE_RE.search(src_text):
        raise SystemExit("source has no <title>; add one before importing")
    if not BODY_RE.search(src_text):
        raise SystemExit("source has no <body> tag; cannot place the All-sites bar")
    if FM_RE.search(src_text[:8000]):
        raise SystemExit("source already carries an <!-- index: --> block; import by hand")
    lines = [f"description: {description}"]
    if tags:
        lines.append(f"tags: {tags}")
    if pinned:
        lines.append("pinned: true")
    lines.append(f"ingested: {ingested}")
    fm = "<!-- index:\n" + "\n".join(lines) + "\n-->\n"
    m = DOCTYPE_RE.match(src_text)
    text = (m.group(0) + fm + src_text[m.end():]) if m else (fm + src_text)
    text = BODY_RE.sub(lambda b: b.group(0) + HOMEBAR + "\n", text, count=1)
    return text


def archive(src: Path) -> Path:
    dest_dir = src.parent / "archive"
    dest_dir.mkdir(exist_ok=True)
    dest = dest_dir / src.name
    if dest.exists():
        raise SystemExit(f"not archiving: {dest} already exists")
    shutil.move(str(src), str(dest))
    return dest


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src", type=Path, help="Standalone .html file to import.")
    ap.add_argument("target", help="CATEGORY/SLUG destination folder, e.g. sharepoint/copilot-km-runbook")
    ap.add_argument("--description", required=True, help="One-line description for the index row.")
    ap.add_argument("--tags", default="", help="Comma-separated tags.")
    ap.add_argument("--pinned", action="store_true")
    ap.add_argument("--ingested", default=None, help="ISO timestamp with timezone; default now.")
    ap.add_argument("--archive", action="store_true", help="Move SRC into its sibling archive/ after import.")
    ap.add_argument("--force-duplicate", action="store_true", help="Import even if content matches a deployed site.")
    args = ap.parse_args()

    parts = args.target.strip("/").split("/")
    if len(parts) != 2 or not all(SLUG_RE.match(p) for p in parts):
        raise SystemExit("target must be category/slug, lowercase with hyphens")
    category, slug = parts
    dest = ROOT / category / slug / "index.html"
    if dest.exists():
        raise SystemExit(f"{dest.relative_to(ROOT)} already exists")
    if not args.src.is_file():
        raise SystemExit(f"no such file: {args.src}")

    src_text = args.src.read_text(encoding="utf-8")
    dupe = existing_fingerprints(ROOT).get(fingerprint(src_text))
    if dupe and not args.force_duplicate:
        raise SystemExit(f"content matches deployed {dupe.relative_to(ROOT)}; "
                         "leave the source in the inbox or pass --force-duplicate")

    ingested = args.ingested or datetime.now().astimezone().replace(microsecond=0).isoformat()
    page = build_page(src_text, args.description, args.tags, args.pinned, ingested)
    dest.parent.mkdir(parents=True)
    dest.write_text(page, encoding="utf-8")
    print(f"wrote {dest.relative_to(ROOT)}")

    subprocess.run([sys.executable, str(ROOT / "generate_index.py")], check=True, cwd=ROOT)

    if args.archive:
        print(f"archived to {archive(args.src)}")
    else:
        print("source left in place; verify the live path, then move it to archive/")


if __name__ == "__main__":
    main()

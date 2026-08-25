#!/usr/bin/env python3
"""
Scans the current directory for sites and generates a root index.html.

Supports two layouts:
  FLAT:     root/site-folder/index.html
  NESTED:   root/category/site-folder/index.html

A folder is treated as a CATEGORY if it contains no index.html but does
contain subfolders with index.html. Otherwise it's treated as a SITE.

Usage:
    python generate_index.py            # folder names as labels
    python generate_index.py --titles   # read <title> from each site's index.html
    python generate_index.py --root /path/to/sites
    python generate_index.py --dry-run
"""
import argparse
import re
import sys
from datetime import date
from html import escape
from pathlib import Path

SKIP_DIRS = {".git", ".github", "node_modules", "__pycache__", ".venv", "venv"}


def natural_sort_key(name: str):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", name)]


def read_title(html_path: Path) -> str | None:
    try:
        text = html_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None
    m = re.search(r"<title[^>]*>(.*?)</title>", text, re.IGNORECASE | re.DOTALL)
    return m.group(1).strip() if m else None


def prettify(name: str) -> str:
    return name.replace("_", " ").replace("-", " ").title()


def is_site(folder: Path) -> bool:
    return (folder / "index.html").exists()


def find_sites(root: Path, use_titles: bool):
    """Return list of (category, slug, label, href).
    category is None for flat sites, else the category folder name.
    slug is the site folder name. href is the path from root to index.html.
    """
    results = []
    for entry in sorted(root.iterdir()):
        if not entry.is_dir() or entry.name in SKIP_DIRS or entry.name.startswith("."):
            continue

        if is_site(entry):
            # flat site at root
            label = read_title(entry / "index.html") if use_titles else None
            if not label:
                label = prettify(entry.name)
            results.append((None, entry.name, label, f"{entry.name}/index.html"))
            continue

        # potential category: scan children
        children = []
        for child in sorted(entry.iterdir()):
            if not child.is_dir() or child.name in SKIP_DIRS or child.name.startswith("."):
                continue
            if is_site(child):
                label = read_title(child / "index.html") if use_titles else None
                if not label:
                    label = prettify(child.name)
                children.append((entry.name, child.name, label, f"{entry.name}/{child.name}/index.html"))

        if children:
            results.extend(children)
        # if no children and no index.html, it's just a non-site folder, skip it

    return results


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
    :root {{
      --bg: #0f1115;
      --card: #181b22;
      --text: #e6e6e6;
      --muted: #8a8f9a;
      --accent: #4f9cff;
      --border: #262a33;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.5;
    }}
    header {{
      padding: 3rem 2rem 2rem;
      text-align: center;
    }}
    header h1 {{ margin: 0 0 0.5rem; font-size: 1.75rem; }}
    header p {{ margin: 0; color: var(--muted); font-size: 0.95rem; }}
    main {{
      max-width: 880px;
      margin: 0 auto;
      padding: 1rem 2rem 4rem;
    }}
    .category {{ margin-bottom: 2.5rem; }}
    .category > h2 {{
      font-size: 1.1rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--muted);
      border-bottom: 1px solid var(--border);
      padding-bottom: 0.4rem;
      margin: 0 0 1rem;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
      gap: 0.75rem;
    }}
    a.card {{
      display: block;
      padding: 0.9rem 1rem;
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 8px;
      text-decoration: none;
      color: var(--text);
      transition: border-color 0.15s, transform 0.15s;
    }}
    a.card:hover {{
      border-color: var(--accent);
      transform: translateY(-1px);
    }}
    a.card .name {{ font-weight: 600; }}
    a.card .path {{ display: block; margin-top: 0.15rem; color: var(--muted); font-size: 0.8rem; font-family: ui-monospace, monospace; }}
    .empty {{ color: var(--muted); text-align: center; padding: 2rem; }}
    footer {{ text-align: center; color: var(--muted); font-size: 0.8rem; padding: 2rem; }}
  </style>
</head>
<body>
  <header>
    <h1>{heading}</h1>
    <p>{count} sites &middot; updated {today}</p>
  </header>
  <main>
{body}
  </main>
  <footer>Generated by generate_index.py</footer>
</body>
</html>
"""

CARD = '<a class="card" href="{href}"><span class="name">{label}</span><span class="path">/{path}/</span></a>'


def build_html(sites):
    """sites: list of (category, slug, label, href). category is None for flat."""
    today = date.today().isoformat()
    if not sites:
        body = '    <div class="empty">No sites found.</div>'
    else:
        from collections import OrderedDict
        grouped = OrderedDict()
        for category, slug, label, href in sites:
            key = category or "Sites"
            grouped.setdefault(key, []).append((slug, label, href))

        sections = []
        for cat, cards in grouped.items():
            card_lines = []
            for slug, label, href in cards:
                # display path includes category for nested, just slug for flat
                if cat == "Sites":
                    disp = slug
                else:
                    disp = f"{cat}/{slug}"
                card_lines.append(CARD.format(
                    path=escape(disp),
                    label=escape(label),
                    href=escape(href),
                ))
            sections.append(
                f'    <div class="category">\n'
                f'      <h2>{escape(cat)}</h2>\n'
                f'      <div class="grid">\n'
                f'{chr(10).join(card_lines)}\n'
                f'      </div>\n'
                f'    </div>'
            )
        body = "\n".join(sections)

    return HTML_TEMPLATE.format(
        title="Sites Index",
        heading="Sites",
        count=len(sites),
        today=today,
        body=body,
    )


def main():
    ap = argparse.ArgumentParser(description="Generate a directory index of static sites (flat or nested).")
    ap.add_argument("--root", default=".", help="Directory to scan (default: current).")
    ap.add_argument("--titles", action="store_true", help="Use each site's <title> as the label.")
    ap.add_argument("--dry-run", action="store_true", help="Print HTML to stdout instead of writing.")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    if not root.is_dir():
        sys.exit(f"Not a directory: {root}")

    sites = find_sites(root, use_titles=args.titles)
    sites.sort(key=lambda s: natural_sort_key(s[1]))

    html = build_html(sites)

    if args.dry_run:
        print(html)
        return

    out = root / "index.html"
    out.write_text(html, encoding="utf-8")
    print(f"Wrote {out} with {len(sites)} site{'s' if len(sites) != 1 else ''}.")


if __name__ == "__main__":
    main()

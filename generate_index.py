#!/usr/bin/env python3
"""
Scans the current directory for sites and generates a root index.html:
a left-rail + single-column list layout with client-side filtering.

The output is ONE self-contained static HTML file: inline <style>, one small
inline <script>, no build step, no dependencies, no network requests except
the Google Fonts stylesheet, and no localStorage / cookies / analytics.
All filter state lives in memory only.

Metadata: single source of truth
--------------------------------
Each page may carry an HTML comment block of front-matter near the top of
its own index.html:

    <!-- index:
    description: One-line description shown under the title.
    tags: runbook, mastery
    pinned: true
    -->

All three fields are optional. A missing block (or missing field) falls back
to description "", tags [], pinned false, and the layout degrades gracefully
(no description line, no tag chips, no TAGS rail section). Titles come from
each page's <title> element; the prettified folder name is the fallback.

Order
-----
Sites keep this generator's historical order (natural sort by folder name,
categories in first-appearance order). When PINNED_FIRST is true, pinned
sites additionally float to the top of the list (stable within each group).

Determinism: identical inputs on the same calendar day produce
byte-identical HTML.

Usage:
    python generate_index.py            # write index.html into --root
    python generate_index.py --root DIR
    python generate_index.py --dry-run  # print HTML instead of writing
    (--titles is accepted for backward compatibility; titles are always read.)
"""
import argparse
import html as html_mod
import json
import re
import sys
from collections import OrderedDict
from datetime import date
from pathlib import Path

SKIP_DIRS = {".git", ".github", "node_modules", "__pycache__", ".venv", "venv"}

# Flip to False to list sites in plain generator order (pinned not first).
PINNED_FIRST = True

PAGE_TITLE = "Reference Sites"

# Category dot colors; any unknown folder uses DOT_FALLBACK.
CATEGORY_DOTS = {
    "hermes": "#5b9dff",
    "shared": "#63c7a6",
    "claude": "#d98a5b",
    "codex": "#a78bfa",
    "sharepoint": "#dfae5c",
}
DOT_FALLBACK = "#6c737f"
DOT_ALL = "#6c737f"
DOT_PINNED = "#dfae5c"

# One-line blurb shown under the heading for each nav target. Unknown
# categories get "" and the blurb line is hidden.
ALL_SITES_BLURB = "All reference sites across every category, pinned first."
PINNED_BLURB = "The sites kept at the top of the list."
CATEGORY_BLURBS = {
    "hermes": "Hermes Agent runbooks and references: bot mode, handoffs, flightpath.",
    "shared": "Cross-tool references: rosters, vault circuits, working agreements.",
    "claude": "Claude Code references and control workflows.",
    "codex": "OpenAI Codex mastery guides and vault circuits.",
    "sharepoint": "SharePoint / Microsoft 365 builds: hubs, flows, briefings.",
}

FRONT_MATTER_RE = re.compile(r"<!--\s*index:\s*(.*?)-->", re.DOTALL | re.IGNORECASE)
FRONT_MATTER_WINDOW = 8000  # only look for front-matter in the first N chars
TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)

FONTS_URL = (
    "https://fonts.googleapis.com/css2?"
    "family=IBM+Plex+Mono:wght@400;500"
    "&family=IBM+Plex+Sans:wght@400;500;600"
    "&display=swap"
)


def esc(s: str) -> str:
    return html_mod.escape(str(s), quote=True)


def natural_sort_key(name: str):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", name)]


def prettify(name: str) -> str:
    return name.replace("_", " ").replace("-", " ").title()


def parse_front_matter(text: str) -> dict:
    """Parse the optional <!-- index: ... --> block. Degrades to defaults."""
    meta = {"description": "", "tags": [], "pinned": False}
    m = FRONT_MATTER_RE.search(text[:FRONT_MATTER_WINDOW])
    if not m:
        return meta
    for line in m.group(1).splitlines():
        line = line.strip()
        if line.startswith("description:"):
            meta["description"] = line.split(":", 1)[1].strip()
        elif line.startswith("tags:"):
            raw = line.split(":", 1)[1]
            meta["tags"] = [t.strip() for t in raw.split(",") if t.strip()]
        elif line.startswith("pinned:"):
            meta["pinned"] = line.split(":", 1)[1].strip().lower() in {
                "true", "yes", "1", "on",
            }
    return meta


def make_entry(category, slug: str, html_path: Path) -> dict:
    try:
        text = html_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        text = ""
    tm = TITLE_RE.search(text)
    title = html_mod.unescape(tm.group(1).strip()) if tm else prettify(slug)
    meta = parse_front_matter(text)
    if category:
        path_disp = f"/{category}/{slug}/"
        href = f"{category}/{slug}/index.html"
    else:
        path_disp = f"/{slug}/"
        href = f"{slug}/index.html"
    return {
        "category": category or "Sites",
        "title": title,
        "path": path_disp,
        "description": meta["description"],
        "tags": meta["tags"],
        "pinned": meta["pinned"],
        "slug": slug,
        "href": href,
    }


def collect(root: Path) -> list:
    """Scan root (flat sites and one level of category folders) and return
    entries in the generator's historical order: natural sort by slug."""
    entries = []
    for entry in sorted(root.iterdir()):
        if not entry.is_dir() or entry.name in SKIP_DIRS or entry.name.startswith("."):
            continue
        if (entry / "index.html").exists():
            entries.append(make_entry(None, entry.name, entry / "index.html"))
            continue
        children = []
        for child in sorted(entry.iterdir()):
            if not child.is_dir() or child.name in SKIP_DIRS or child.name.startswith("."):
                continue
            if (child / "index.html").exists():
                children.append(make_entry(entry.name, child.name, child / "index.html"))
        entries.extend(children)
    entries.sort(key=lambda e: natural_sort_key(e["slug"]))
    return entries


CSS = """\
:root{
  --bg:#0e1014;
  --surface:#15181e;
  --nav-active:#1a1e26;
  --pill-bg:#1e2430;
  --pill-border:#33405a;
  --hair-rail:#1c2028;
  --hair:#262a33;
  --text:#e8eaed;
  --text-2:#8b919c;
  --dim:#5b6270;
  --gold:#dfae5c;
  --pin-idle:#39404d;
  --link:#5b9dff;
  --link-hover:#8bbaff;
  --chip-bg:#181c23;
  --chip-text:#7d8492;
  --chip-border:#23272f;
  --sans:"IBM Plex Sans",-apple-system,"Segoe UI",system-ui,sans-serif;
  --mono:"IBM Plex Mono",ui-monospace,Consolas,monospace;
}
*{box-sizing:border-box}
html,body{margin:0;padding:0}
body{background:var(--bg);color:var(--text);font-family:var(--sans);font-size:14px;line-height:1.5}
a{color:var(--link);text-decoration:none}
a:hover{color:var(--link-hover)}
button{font:inherit;color:inherit;background:none;border:0;padding:0;cursor:pointer}
input::placeholder{color:#5b6270}
[hidden]{display:none!important}
:focus-visible{outline:2px solid var(--link);outline-offset:2px}

.wrap{display:grid;grid-template-columns:264px 1fr;min-height:100vh}

/* left rail */
.rail{position:sticky;top:0;height:100vh;overflow-y:auto;border-right:1px solid var(--hair-rail);padding:30px 20px;display:flex;flex-direction:column;gap:20px}
.brand-name{font-size:17px;font-weight:600;line-height:1.3}
.brand-sub{font-family:var(--mono);font-size:11px;color:var(--dim);margin-top:4px}
#q{width:100%;min-height:32px;background:var(--surface);border:1px solid var(--hair);border-radius:8px;padding:6px 11px;color:var(--text);font-family:var(--sans);font-size:13px}
#q:focus{outline:none;border-color:var(--link)}
.nav{display:flex;flex-direction:column;gap:2px}
.nav-row{display:flex;align-items:center;gap:9px;min-height:32px;width:100%;padding:5px 10px;border-radius:7px;border:1px solid transparent;color:var(--text-2);text-align:left}
.nav-row:hover{background:var(--surface);color:var(--text)}
.nav-row.active{background:var(--nav-active);color:var(--text)}
.dot{width:6px;height:6px;border-radius:50%;flex:none}
.nav-label{flex:1;font-size:13px;font-weight:500;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.count{font-family:var(--mono);font-size:11px;color:var(--dim)}
.tags{border-top:1px solid var(--hair-rail);padding-top:16px;display:flex;flex-direction:column;gap:10px;min-width:0}
.tags-head{font-family:var(--mono);font-size:10px;font-weight:500;letter-spacing:.14em;color:var(--dim)}
.tag-wrap{display:flex;flex-wrap:wrap;gap:6px}
.tag{display:inline-flex;align-items:center;gap:6px;min-height:32px;padding:5px 12px;border-radius:999px;border:1px solid var(--hair);color:var(--text-2);font-family:var(--mono);font-size:11px}
.tag:hover{background:var(--surface);color:var(--text)}
.tag.active{background:var(--pill-bg);border-color:var(--pill-border);color:var(--text)}
.tag .n{color:var(--dim)}
.rail-foot{margin-top:auto;font-family:var(--mono);font-size:10.5px;line-height:1.8;color:var(--dim)}

/* right column */
.list-col{padding:34px 44px 90px;max-width:940px;min-width:0}
.list-head{display:flex;align-items:baseline;gap:14px}
.list-head h1{margin:0;font-size:24px;font-weight:600;letter-spacing:-0.02em;line-height:1.2}
.meta{font-family:var(--mono);font-size:11.5px;color:var(--dim);white-space:nowrap}
.clear{margin-left:auto;display:inline-flex;align-items:center;min-height:32px;padding:4px 13px;border-radius:999px;border:1px solid var(--hair);color:var(--text-2);font-family:var(--mono);font-size:11px;white-space:nowrap}
.clear:hover{background:var(--surface);color:var(--text)}
.blurb{margin:8px 0 26px;font-size:13px;color:var(--text-2)}
.rows{display:flex;flex-direction:column;gap:2px}
.row{display:block;padding:14px 16px;border-radius:9px;border:1px solid transparent;color:var(--text)}
.row:hover{background:var(--surface);border-color:var(--hair);color:var(--text)}
.l1{display:flex}
.pin{flex:none;width:21px;color:var(--pin-idle)}
.pin.on{color:var(--gold)}
.ttl{font-size:15.5px;font-weight:500;line-height:1.35;text-wrap:pretty}
.l2{display:block;margin:5px 0 0 21px;max-width:62ch;font-size:13px;line-height:1.5;color:var(--text-2);text-wrap:pretty}
.l3{display:flex;flex-wrap:wrap;align-items:center;gap:6px;margin:8px 0 0 21px}
.pth{font-family:var(--mono);font-size:11.5px;color:var(--text-2)}
.chip{font-family:var(--mono);font-size:10px;color:var(--chip-text);background:var(--chip-bg);border:1px solid var(--chip-border);border-radius:4px;padding:2px 7px}
.empty{font-family:var(--mono);font-size:13px;color:var(--dim);padding:56px 0}

@media (max-width:860px){
  .wrap{grid-template-columns:1fr}
  .rail{position:static;height:auto;border-right:0;border-bottom:1px solid var(--hair-rail)}
  .nav{flex-direction:row;overflow-x:auto;gap:6px;padding-bottom:6px}
  .nav-row{flex:none;width:auto;white-space:nowrap;border:1px solid var(--hair);border-radius:999px;padding:5px 13px}
  .nav-label{overflow:visible}
  .list-col{padding:24px 20px 64px}
}"""


JS_CORE = """\
(function () {
  "use strict";
  var state = { cat: "all", tag: null, q: "" };
  var rows = Array.prototype.slice.call(document.querySelectorAll("#rows .row"));
  var qInput = document.getElementById("q");
  var h1 = document.getElementById("h1");
  var meta = document.getElementById("meta");
  var blurb = document.getElementById("blurb");
  var clearBtn = document.getElementById("clear");
  var emptyEl = document.getElementById("empty");
  var navBtns = Array.prototype.slice.call(document.querySelectorAll("#nav .nav-row"));
  var tagBtns = Array.prototype.slice.call(document.querySelectorAll("#tags .tag"));

  function matches(s) {
    if (state.cat === "pinned") {
      if (!s.pinned) return false;
    } else if (state.cat !== "all" && s.category !== state.cat) {
      return false;
    }
    if (state.tag !== null && s.tags.indexOf(state.tag) === -1) return false;
    var q = state.q.replace(/^\\s+|\\s+$/g, "");
    if (q) {
      var hay = (s.title + " " + s.description + " " + s.path + " " +
                 s.category + " " + s.tags.join(" ")).toLowerCase();
      var toks = q.toLowerCase().split(/\\s+/);
      for (var i = 0; i < toks.length; i++) {
        if (toks[i] !== "" && hay.indexOf(toks[i]) === -1) return false;
      }
    }
    return true;
  }

  function apply() {
    var visible = 0;
    for (var i = 0; i < rows.length; i++) {
      var show = matches(SITES[i]);
      rows[i].hidden = !show;
      if (show) visible++;
    }
    var name = state.cat === "all" ? "All sites"
             : (state.cat === "pinned" ? "\\u2605 Pinned" : state.cat);
    h1.textContent = name;
    var m = visible + (visible === 1 ? " page" : " pages");
    if (state.tag !== null) m += " \\u00b7 tag: " + state.tag;
    meta.textContent = m;
    var b = BLURBS[state.cat] || "";
    blurb.textContent = b;
    blurb.hidden = (b === "");
    clearBtn.hidden = !(state.q !== "" || state.tag !== null || state.cat !== "all");
    emptyEl.hidden = (visible !== 0);
    for (var j = 0; j < navBtns.length; j++) {
      navBtns[j].classList.toggle("active",
        navBtns[j].getAttribute("data-cat") === state.cat);
    }
    for (var k = 0; k < tagBtns.length; k++) {
      tagBtns[k].classList.toggle("active",
        tagBtns[k].getAttribute("data-tag") === state.tag);
    }
  }

  qInput.addEventListener("input", function () {
    state.q = qInput.value;
    apply();
  });

  document.getElementById("nav").addEventListener("click", function (e) {
    var btn = e.target.closest ? e.target.closest(".nav-row") : null;
    if (!btn) return;
    state.cat = btn.getAttribute("data-cat");
    apply();
  });

  var tagsEl = document.getElementById("tags");
  if (tagsEl) {
    tagsEl.addEventListener("click", function (e) {
      var btn = e.target.closest ? e.target.closest(".tag") : null;
      if (!btn) return;
      var t = btn.getAttribute("data-tag");
      state.tag = (state.tag === t) ? null : t;
      apply();
    });
  }

  clearBtn.addEventListener("click", function () {
    state.cat = "all";
    state.tag = null;
    state.q = "";
    qInput.value = "";
    apply();
  });

  apply();
})();"""


def nav_button(cat_id: str, label: str, color: str, count: int, active: bool = False) -> str:
    cls = "nav-row active" if active else "nav-row"
    return (
        f'<button type="button" class="{cls}" data-cat="{esc(cat_id)}">'
        f'<span class="dot" style="background:{color}"></span>'
        f'<span class="nav-label">{esc(label)}</span>'
        f'<span class="count">{count}</span>'
        f"</button>"
    )


def build_row(i: int, e: dict) -> str:
    pin_cls = "pin on" if e["pinned"] else "pin"
    glyph = "\u2605" if e["pinned"] else "\u00b7"
    parts = [
        f'<a class="row" href="{esc(e["href"])}" data-i="{i}">',
        f'<span class="l1"><span class="{pin_cls}">{glyph}</span>'
        f'<span class="ttl">{esc(e["title"])}</span></span>',
    ]
    if e["description"]:
        parts.append(f'<span class="l2">{esc(e["description"])}</span>')
    chips = "".join(f'<span class="chip">{esc(t)}</span>' for t in e["tags"])
    parts.append(
        f'<span class="l3"><span class="pth">{esc(e["path"])}</span>{chips}</span>'
    )
    parts.append("</a>")
    return "".join(parts)


def build_html(entries: list) -> str:
    today = date.today().isoformat()

    # Category order: first appearance in the historical (slug-sorted) order.
    grouped = OrderedDict()
    for e in entries:
        grouped.setdefault(e["category"], []).append(e)
    category_order = list(grouped.keys())
    counts = {c: len(v) for c, v in grouped.items()}

    if PINNED_FIRST:
        display = sorted(entries, key=lambda e: 0 if e["pinned"] else 1)
    else:
        display = list(entries)

    tag_counts = {}
    for e in entries:
        for t in e["tags"]:
            tag_counts[t] = tag_counts.get(t, 0) + 1
    tags_sorted = sorted(tag_counts, key=lambda t: (t.lower(), t))

    # --- left rail ---
    nav_lines = [nav_button("all", "All sites", DOT_ALL, len(entries), active=True)]
    pinned_count = sum(1 for e in entries if e["pinned"])
    nav_lines.append(nav_button("pinned", "\u2605 Pinned", DOT_PINNED, pinned_count))
    for cat in category_order:
        color = CATEGORY_DOTS.get(cat, DOT_FALLBACK)
        nav_lines.append(nav_button(cat, cat, color, counts[cat]))

    if tags_sorted:
        pill_lines = [
            f'<button type="button" class="tag" data-tag="{esc(t)}">'
            f'{esc(t)} <span class="n">{tag_counts[t]}</span></button>'
            for t in tags_sorted
        ]
        tags_block = (
            '<div class="tags" id="tags">\n'
            '<div class="tags-head">TAGS</div>\n'
            '<div class="tag-wrap">\n' + "\n".join(pill_lines) + "\n</div>\n</div>"
        )
    else:
        tags_block = ""

    # --- right column ---
    if display:
        rows_html = "\n".join(build_row(i, e) for i, e in enumerate(display))
    else:
        rows_html = '<div class="empty">No sites found.</div>'

    # Data for the client script (same order as the server-rendered rows).
    sites_payload = [
        {
            "category": e["category"],
            "title": e["title"],
            "path": e["path"],
            "description": e["description"],
            "tags": e["tags"],
            "pinned": e["pinned"],
        }
        for e in display
    ]
    sites_js = json.dumps(
        sites_payload, ensure_ascii=True, separators=(",", ":")
    ).replace("</", "<\\/")
    blurbs = {"all": ALL_SITES_BLURB, "pinned": PINNED_BLURB}
    for cat in category_order:
        blurbs[cat] = CATEGORY_BLURBS.get(cat, "")
    blurbs_js = json.dumps(blurbs, ensure_ascii=True, sort_keys=True, separators=(",", ":"))

    n = len(entries)
    return "\n".join([
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>{PAGE_TITLE}</title>",
        '<link rel="preconnect" href="https://fonts.googleapis.com">',
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>',
        f'<link href="{FONTS_URL}" rel="stylesheet">',
        "<style>",
        CSS,
        "</style>",
        "</head>",
        "<body>",
        '<div class="wrap">',
        '<aside class="rail">',
        '<div class="brand">',
        f'<div class="brand-name">{PAGE_TITLE}</div>',
        f'<div class="brand-sub">{n} pages \u00b7 {today}</div>',
        "</div>",
        '<input id="q" type="text" placeholder="Filter titles, tags, paths\u2026"'
        ' autocomplete="off" spellcheck="false">',
        '<nav class="nav" id="nav">',
        "\n".join(nav_lines),
        "</nav>",
        tags_block,
        '<div class="rail-foot">',
        "<div>generate_index.py</div>",
        "<div>static \u00b7 no tracking</div>",
        "</div>",
        "</aside>",
        '<main class="list-col">',
        '<div class="list-head">',
        '<h1 id="h1">All sites</h1>',
        f'<div class="meta" id="meta">{n} page{"s" if n != 1 else ""}</div>',
        '<button type="button" id="clear" class="clear" hidden>clear filters \u00d7</button>',
        "</div>",
        f'<p class="blurb" id="blurb">{esc(ALL_SITES_BLURB)}</p>',
        '<div class="rows" id="rows">',
        rows_html,
        "</div>",
        '<div class="empty" id="empty" hidden>nothing matches that filter</div>',
        "</main>",
        "</div>",
        "<script>",
        f"const SITES = {sites_js};",
        f"const BLURBS = {blurbs_js};",
        JS_CORE,
        "</script>",
        "</body>",
        "</html>",
        "",  # trailing newline
    ])


def main():
    ap = argparse.ArgumentParser(
        description="Generate the root index (left rail + list) for the static sites."
    )
    ap.add_argument("--root", default=".", help="Directory to scan (default: current).")
    ap.add_argument("--titles", action="store_true",
                    help="Deprecated no-op: page <title>s are always read.")
    ap.add_argument("--dry-run", action="store_true", help="Print HTML instead of writing.")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    if not root.is_dir():
        sys.exit(f"Not a directory: {root}")

    entries = collect(root)
    html = build_html(entries)

    if args.dry_run:
        print(html)
        return

    out = root / "index.html"
    out.write_text(html, encoding="utf-8")
    print(f"Wrote {out} with {len(entries)} site{'s' if len(entries) != 1 else ''}.")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Regenerates watchlist/repo-states/index.html from the GitHub API.

Fetches every repo owned by the authenticated user, then renders one
self-contained static page: a dark, filterable table sorted by last push
with staleness shading, plus the repo's standard All-sites bar and
index front-matter. No third-party imports; the page has no network
requests except the Google Fonts stylesheet, matching generate_index.py.

Auto-refresh: .github/workflows/update-repo-states.yml runs this daily
and commits the result, which triggers the Cloudflare Workers deploy.

The INGESTED constant records when the site first entered this repo and
must not change on later updates (README: keep the original ingestion
timestamp). The visible "Data refreshed" line and the generated meta
tag DO change every run; that keeps daily commits non-empty and the
page's freshness claim honest.

Usage:
    python update_repo_states.py            # fetch and write the page
    python update_repo_states.py --dry-run  # print HTML instead of writing

Token resolution: GH_TOKEN / GITHUB_TOKEN env var, else `gh auth token`.
"""
import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from html import escape as esc
from pathlib import Path

API_BASE = "https://api.github.com"
PAGE_PATH = Path("watchlist/repo-states/index.html")

# Fixed first-ingest timestamp; preserve on every update (README rule 4).
INGESTED = "2026-10-02T14:18:10-07:00"

FRESH_DAYS = 7       # pushed within N days -> green
ACTIVE_DAYS = 30      # within N days -> default text
DORMANT_DAYS = 90     # within N days -> amber; older -> dim/grey

FONTS_URL = (
    "https://fonts.googleapis.com/css2?"
    "family=IBM+Plex+Mono:wght@400;500"
    "&family=IBM+Plex+Sans:wght@400;500;600"
    "&display=swap"
)


def resolve_token() -> str:
    """Return a GitHub API token from env, falling back to gh auth token.

    REPO_STATES_TOKEN comes first: the Actions GITHUB_TOKEN is scoped to
    this repository only and gets HTTP 403 when listing the owner's
    other repos, so the workflow needs a token with metadata read on
    all of them (see README of this script).
    """
    for var in ("REPO_STATES_TOKEN", "GH_TOKEN", "GITHUB_TOKEN"):
        if os.environ.get(var):
            return os.environ[var]
    try:
        out = subprocess.run(
            ["gh", "auth", "token"],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
        return out.stdout.strip()
    except (subprocess.SubprocessError, OSError) as exc:
        raise RuntimeError("no token: set GH_TOKEN or run `gh auth login`") from exc


def fetch_repos(token: str) -> list[dict]:
    """Fetch all repos owned by the token's user, newest push first."""
    repos: list[dict] = []
    page = 1
    while True:
        url = (
            f"{API_BASE}/user/repos?affiliation=owner&sort=pushed"
            f"&per_page=100&page={page}"
        )
        req = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "User-Agent": "mastery-sites/repo-states",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                batch = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")[:500]
            try:
                message = json.loads(body).get("message", body)
            except json.JSONDecodeError:
                message = body
            raise RuntimeError(f"HTTP {exc.code} from {url}: {message}") from exc
        if not batch:
            break
        repos.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return repos


def age_days(pushed_at: str, now: dt.datetime) -> int:
    """Whole days between now and the repo's last push (UTC ISO strings)."""
    pushed = dt.datetime.fromisoformat(pushed_at.replace("Z", "+00:00"))
    return max(0, (now - pushed).days)


def staleness(days: int) -> str:
    """CSS class for a last-push age."""
    if days <= FRESH_DAYS:
        return "fresh"
    if days <= ACTIVE_DAYS:
        return "active"
    if days <= DORMANT_DAYS:
        return "aging"
    return "dormant"


def badges(repo: dict) -> str:
    """Visibility / archived / fork chips for a repo row."""
    chips = []
    if repo["archived"]:
        chips.append('<span class="chip chip-arch">archived</span>')
    elif repo["fork"]:
        chips.append('<span class="chip">fork</span>')
    if repo.get("visibility") == "private":
        chips.append('<span class="chip">private</span>')
    return " ".join(chips) if chips else '<span class="chip">public</span>'


def render_row(repo: dict, now: dt.datetime) -> str:
    """One table row for a repo."""
    days = age_days(repo["pushed_at"], now)
    pushed_date = repo["pushed_at"][:10]
    desc = esc(repo["description"] or "")
    lang = esc(repo["language"] or "—")
    issues = repo["open_issues_count"]
    return (
        f'<tr class="r" data-k="{esc(repo["name"].lower())} {desc.lower()}">'
        f'<td><a class="rn" href="{esc(repo["html_url"])}" target="_blank" rel="noopener">{esc(repo["name"])}</a></td>'
        f"<td class='d'>{desc}</td>"
        f"<td class='l'>{lang}</td>"
        f"<td class='b'>{badges(repo)}</td>"
        f"<td class='p'>{pushed_date}</td>"
        f"<td class='a {staleness(days)}'>{days}d</td>"
        f"<td class='i'>{issues}</td>"
        f"</tr>"
    )


def render_page(repos: list[dict], now: dt.datetime) -> str:
    """Render the full static page. Pure: same inputs -> same HTML."""
    repos = sorted(repos, key=lambda r: r["pushed_at"], reverse=True)
    rows = "".join(render_row(r, now) for r in repos)
    n_total = len(repos)
    ages = [age_days(r["pushed_at"], now) for r in repos]
    n_fresh = sum(1 for d in ages if d <= FRESH_DAYS)
    n_dormant = sum(1 for d in ages if d > DORMANT_DAYS)
    n_archived = sum(1 for r in repos if r["archived"])
    generated = now.strftime("%Y-%m-%d %H:%M UTC")
    return f"""<!doctype html><html lang="en"><head><!-- index:
description: All aerin00 GitHub repos with last-push recency, language, and state. Auto-refreshed daily by a scheduled job.
tags: github, repos, watchlist
pinned: true
ingested: {INGESTED}
--><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="dark">
<meta name="generated" content="{now.isoformat()}">
<title>GitHub Repo States</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="{FONTS_URL}" rel="stylesheet">
<style>
:root{{--bg:#0e1014;--surface:#15181e;--hair:#262a33;--text:#e8eaed;--dim:#5b6270;--link:#5b9dff;--link-hover:#8bbaff;
--fresh:#63c7a6;--aging:#dfae5c;--dormant:#5b6270;--sans:"IBM Plex Sans",-apple-system,"Segoe UI",system-ui,sans-serif;
--mono:"IBM Plex Mono",ui-monospace,Consolas,monospace}}
*{{box-sizing:border-box}}html,body{{margin:0;padding:0}}
body{{background:var(--bg);color:var(--text);font-family:var(--sans);font-size:14px;line-height:1.5}}
a{{color:var(--link);text-decoration:none}}a:hover{{color:var(--link-hover)}}
#ms-homebar{{position:sticky;top:0;z-index:2147483647;display:block;padding:8px 14px;background:#111827;
font:600 13px/1.2 system-ui,-apple-system,"Segoe UI",sans-serif;border-bottom:1px solid #1f2937}}
#ms-homebar a{{color:#93c5fd;text-decoration:none}}#ms-homebar a:hover{{text-decoration:underline;color:#bfdbfe}}
main{{max-width:1180px;margin:0 auto;padding:30px 20px 60px}}
h1{{margin:0 0 4px;font-size:24px;font-weight:600;letter-spacing:-.02em}}
.sub{{font-family:var(--mono);font-size:11.5px;color:var(--dim);margin-bottom:22px}}
#q{{width:100%;max-width:340px;min-height:32px;background:var(--surface);border:1px solid var(--hair);border-radius:8px;
padding:6px 11px;color:var(--text);font-family:var(--sans);font-size:13px;margin-bottom:18px}}
#q:focus{{outline:none;border-color:var(--link)}}
.stats{{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:20px}}
.stat{{font-family:var(--mono);font-size:11px;color:var(--dim);background:var(--surface);border:1px solid var(--hair);
border-radius:999px;padding:4px 12px}}
.stat b{{color:var(--text);font-weight:500}}
table{{border-collapse:collapse;width:100%}}
th{{text-align:left;font-family:var(--mono);font-size:10.5px;font-weight:500;letter-spacing:.14em;color:var(--dim);
padding:0 12px 10px;border-bottom:1px solid var(--hair)}}
td{{padding:10px 12px;border-bottom:1px solid var(--hair);vertical-align:top}}
tr:hover td{{background:var(--surface)}}
.rn{{font-weight:500}}
.d{{color:var(--text);max-width:340px}}.d,.l,.p,.i{{color:#8b919c}}
.b{{white-space:nowrap}}.p{{font-family:var(--mono);font-size:12px;white-space:nowrap}}
.a{{font-family:var(--mono);font-size:12px;text-align:right;white-space:nowrap}}
.a.fresh{{color:var(--fresh)}}.a.active{{color:#8b919c}}.a.aging{{color:var(--aging)}}.a.dormant{{color:var(--dormant)}}
.i{{font-family:var(--mono);font-size:12px;text-align:right}}
.chip{{display:inline-block;font-family:var(--mono);font-size:10px;color:#7d8492;background:#181c23;
border:1px solid #23272f;border-radius:999px;padding:1px 8px;margin-right:4px}}
.chip-arch{{color:var(--aging);border-color:#3a3324;background:#221d12}}
.foot{{margin-top:26px;font-family:var(--mono);font-size:11px;color:var(--dim)}}
@media(max-width:720px){{.d{{display:none}}th.h-d{{display:none}}}}
</style></head><body><nav id="ms-homebar" class="ms-homebar" aria-label="All sites"><a href="https://mastery-sites.stenguye.workers.dev/">All sites</a></nav>
<main>
<h1>GitHub Repo States</h1>
<div class="sub">every repo owned by aerin00, sorted by last push · refreshes daily at 07:00 Pacific</div>
<input id="q" type="search" placeholder="Filter repos…" autocomplete="off">
<div class="stats">
<span class="stat"><b>{n_total}</b> repos</span>
<span class="stat"><b>{n_fresh}</b> pushed ≤ {FRESH_DAYS}d ago</span>
<span class="stat"><b>{n_dormant}</b> dormant &gt; {DORMANT_DAYS}d</span>
<span class="stat"><b>{n_archived}</b> archived</span>
</div>
<table>
<thead><tr><th>Repo</th><th class="h-d">What</th><th>Lang</th><th>State</th><th>Last push</th><th style="text-align:right">Age</th><th style="text-align:right">Issues/PRs</th></tr></thead>
<tbody>{rows}</tbody>
</table>
<div class="foot">Data refreshed {generated} · source: api.github.com · issues column counts open issues and PRs</div>
</main>
<script>
const q=document.getElementById('q');
q.addEventListener('input',()=>{{
  const s=q.value.trim().toLowerCase();
  for(const tr of document.querySelectorAll('tr.r')){{
    tr.hidden=s!==''&&!tr.dataset.k.includes(s);
  }}
}});
</script>
</body></html>"""


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Regenerate watchlist/repo-states/index.html from the GitHub API."
    )
    parser.add_argument("--dry-run", action="store_true", help="print HTML instead of writing")
    args = parser.parse_args(argv)

    now = dt.datetime.now(dt.timezone.utc)
    try:
        repos = fetch_repos(resolve_token())
    except (urllib.error.URLError, RuntimeError, OSError) as exc:
        print(f"error: fetch failed: {exc}", file=sys.stderr)
        return 1

    if not repos:
        print("error: API returned zero repos; refusing to overwrite page", file=sys.stderr)
        return 1

    html = render_page(repos, now)
    if args.dry_run:
        sys.stdout.write(html)
        return 0
    PAGE_PATH.parent.mkdir(parents=True, exist_ok=True)
    PAGE_PATH.write_text(html, encoding="utf-8")
    print(f"repo-states: {len(repos)} repos -> {PAGE_PATH} (refreshed {now:%Y-%m-%d %H:%M UTC})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

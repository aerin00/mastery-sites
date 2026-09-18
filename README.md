# Mastery Sites

A monorepo of standalone static HTML sites, organized by category and deployed through Cloudflare Workers Builds. Each site folder contains an `index.html`. The generated root `index.html` links to all sites through a left rail and responsive paginated grid with in-memory filtering.

## Layout

```
00_Mastery_Sites/
├── index.html              ← generated homepage and current site inventory
├── generate_index.py       ← regenerates index.html
├── README.md               ← conventions and workflow
└── <category>/
    └── <site-slug>/
        ├── index.html
        └── <local assets, if needed>
```

Use the [generated homepage](index.html) for the current inventory. Do not maintain a second per-site list here.

## Category convention

Categories are folders at the root level that contain site folders inside them. The generator auto-detects them:

- **Folder with `index.html` directly inside** = a **site**. It shows up as a row.
- **Folder with no `index.html`, but subfolders that each have `index.html`** = a **category**. Its children show up grouped under a nav entry named after the folder.

You can nest one level deep. Deeper nesting is not supported and not needed.

### Naming

- **Categories**: lowercase, no spaces. One word if possible (`hermes`, `codex`, `claude`, `shared`, `sharepoint`).
- **Sites**: lowercase, hyphens, descriptive (`bot-mode-handoff`, `codex-mastery`). Avoid generic names like `site1`.

### Which category?

| If the site is about...                         | Put it in  |
|-------------------------------------------------|------------|
| Hermes Agent (setup, modes, bot fleet, flightpath) | `hermes/`  |
| OpenAI Codex (agent, mastery, vault)             | `codex/`   |
| Claude Code (control stack, workflows)           | `claude/`  |
| SharePoint / Microsoft 365 (hubs, flows, Copilot, briefings) | `sharepoint/` |
| Cross-tool, shared infrastructure, general tools | `shared/`  |
| Grok Bots and coordination                      | `grok/`    |
| Trading indicators and TradingView field guides | `trading/` |
| Natal and financial astrology                   | `astrology/` |
| Oracle practice                                | `oracle/`  |
| Something new that doesn't fit any of the above  | make a new category folder |

When in doubt, start a new category folder. A sparse category is better than a wrong one.

## Adding a new site

1. Pick a category (or create one):
   ```bash
   mkdir -p sharepoint/new-site-name
   ```

2. Add your `index.html` with a `<title>`, the `<!-- index: ... -->` block, and the All-sites bar as the first thing in `<body>` (see below).

3. Set a descriptive `<title>` in that `index.html`. The generator always reads it as the row label (the prettified folder name is the fallback).

4. Add the ingestion timestamp to the front-matter block (see below). Description, tags, and pinning are optional. Keep the original ingestion timestamp when updating or moving an existing site. Every site page also needs the All-sites bar so a reader can return to https://mastery-sites.stenguye.workers.dev/ .

5. Regenerate the homepage:
   ```bash
   python generate_index.py
   ```

6. Verify the pages and index locally, then commit and push to `origin/main` with approval. Cloudflare Workers Builds deploys automatically.

For inbox imports, preserve source HTML and add metadata only to the deployed copy. After the live deployment is verified, move only successfully imported sources into the sibling `00_Mastery_Sites_Inbox/archive/` folder. Leave unprocessed files in the inbox and never overwrite an existing archive file.

## Site front-matter (optional)

Each page may carry an HTML comment block near the top of its own `index.html` (the generator only looks in the first 8000 chars):

```html
<!-- index:
description: One-line description shown under the title.
tags: runbook, mastery
pinned: true
ingested: 2026-09-10T16:27:00-07:00
-->
```

Missing description, tags, or pinning fall back to no description, no tags, and not pinned. `pinned: true` floats the site to the top outside Recent Sites (the generator's `PINNED_FIRST` flag controls this globally). Tags also appear as a TAGS filter section in the rail once any site has tags.

`ingested` records when the site first entered this repository, not its latest edit. Use an ISO timestamp including seconds and timezone, as in the example; `YYYY-MM-DD` is also accepted when only a date is known (sorted as midnight UTC). Missing dates display **Unknown** and sort last; malformed dates stop generation instead of silently inventing a date. New imports should always include this field.

**Recent Sites**, directly below **All Sites**, shows a site/date-ingested list ordered newest first. It retains search, tag filters, and pagination without giving pins priority. Timestamps sort by UTC instant, while the date column preserves the source timestamp's calendar date. Identical timestamps use site path as a deterministic tie-breaker.

Historical dates were backfilled from the first Git commit adding each current site's `index.html`. These are repository-entry proxies, not claims about when the source document was originally created. Metadata is persisted with each page so rebuilding or cloning the repository cannot reset its ingestion date; generation does not need Git.

## Regenerating the index

```bash
python generate_index.py              # write index.html into --root
python generate_index.py --root DIR   # scan a different directory
python generate_index.py --dry-run    # print HTML instead of writing
```

`--titles` is still accepted for backward compatibility but is a no-op: titles are always read.

The output is one static HTML file with inline style and script: a left rail with category navigation, search, and tag filters, plus a responsive grid paginated at 10 sites per page. There is no frontend compilation or tracking; Google Fonts loads externally. Run the generator any time you change a site's title or index metadata, or add, remove, rename, or move a site. The generated `index.html` overwrites the previous one. Identical inputs on the same calendar day produce byte-identical HTML.

Category dot colors and per-category blurbs live in `generate_index.py` (`CATEGORY_DOTS`, `CATEGORY_BLURBS`). Unknown categories get a fallback dot and no blurb.

### Tests

```bash
python -m unittest discover -s tests -v
python generate_index.py
node tests/test_index.cjs index.html
```

The Python tests cover ingestion metadata and date validation. The Node harness executes the generated inline JavaScript against a small DOM stub, checking ordering, filters, pagination, unknown dates, and the empty index. No package installation is required; these checks do not replace visual browser inspection.

## Deploy

The production site is deployed by **Cloudflare Workers Builds** from `origin/main`. Every site folder becomes a path:

- https://mastery-sites.stenguye.workers.dev/ → the generated homepage
- https://mastery-sites.stenguye.workers.dev/hermes/bot-mode-mastery/ → that site
- https://mastery-sites.stenguye.workers.dev/sharepoint/ipc-scoped-flow/ → that site

Regenerate and commit the root index before pushing. Check the GitHub commit's `Workers Builds: mastery-sites` result and verify the live homepage and changed site paths before considering deployment complete. Build settings are managed outside this repository; this workflow does not change them.

## Rules

1. Every site is a folder with an `index.html`. No exceptions.
2. Max one level of nesting: `category/site/index.html`. Not `category/subcategory/site/index.html`.
3. Always set a `<title>` in each site's `index.html`.
4. Always include the `<!-- index: ... -->` block (description, tags, ingested date, pinned) and the All-sites bar (`#ms-homebar`) as the first child of `<body>`.
5. Always run `python generate_index.py` after structural changes.
6. The generator is the source of truth for the root `index.html`; regenerate and commit its output rather than hand-editing it.
7. Keep repository tooling at the root and site assets beside their page. The generator discovers only folders containing `index.html`, directly or one category level down; it skips dot-directories and known noise (`.git`, `node_modules`, `__pycache__`).

# Mastery Sites

A monorepo of standalone static HTML sites, organized by category and deployed as a single project to Cloudflare Pages. Each subfolder with an `index.html` is one site. A generated root `index.html` links to all of them.

## Layout

```
00_Mastery_Sites/
├── index.html              ← generated homepage, links to every site
├── generate_index.py      ← regenerates index.html
├── README.md               ← this file
│
├── hermes/                 ← category: Hermes Agent
│   ├── bot-mode-handoff/
│   ├── bot-mode-mastery/
│   ├── hermes-bot-mode/
│   ├── hermes-bot-mode-by-hermes/
│   └── hermes-flightpath/
│
├── codex/                  ← category: OpenAI Codex
│   ├── codex-agent-mastery/
│   ├── codex-mastery/
│   └── codex-vault-circuit/
│
├── claude/                 ← category: Claude Code
│   └── claude-code-control-stack/
│
├── sharepoint/             ← category: SharePoint / Microsoft 365
│   ├── bc-hydro-copilot-operating-model/
│   ├── copilot-field-guide/
│   ├── copilot-power-platform-hub/
│   ├── ddm-future-state/
│   ├── ipc-forecast-briefing/
│   ├── ipc-scoped-flow/
│   ├── master-hub-blueprint/
│   ├── onedrive-working-memory-playbook/
│   └── pic-sharepoint-hub-reference/
│
└── shared/                 ← category: cross-tool / general
    ├── bot-roster/
    ├── obsidian-vault-circuit/
    ├── steven-os/
    └── working-with-steven/
```

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
| Something new that doesn't fit any of the above  | make a new category folder |

When in doubt, start a new category folder. A sparse category is better than a wrong one.

## Adding a new site

1. Pick a category (or create one):
   ```bash
   mkdir -p sharepoint/new-site-name
   ```

2. Add your `index.html`:
   ```bash
   echo "<!DOCTYPE html><html><head><title>New Site Name</title></head><body><h1>Hello</h1></body></html>" > sharepoint/new-site-name/index.html
   ```

3. Set a descriptive `<title>` in that `index.html`. The generator always reads it as the row label (the prettified folder name is the fallback).

4. Optionally add a front-matter block (see below) for a description line, tag chips, and pinning.

5. Regenerate the homepage:
   ```bash
   python generate_index.py
   ```

6. Commit and push. Cloudflare Pages deploys automatically.

## Site front-matter (optional)

Each page may carry an HTML comment block near the top of its own `index.html` (the generator only looks in the first 8000 chars):

```html
<!-- index:
description: One-line description shown under the title.
tags: runbook, mastery
pinned: true
-->
```

All three fields are optional. Missing block or field falls back to no description, no tags, not pinned. `pinned: true` floats the site to the top of the list (the generator's `PINNED_FIRST` flag controls this globally). Tags also appear as a TAGS filter section in the rail once any site has tags.

## Regenerating the index

```bash
python generate_index.py              # write index.html into --root
python generate_index.py --root DIR   # scan a different directory
python generate_index.py --dry-run    # print HTML instead of writing
```

`--titles` is still accepted for backward compatibility but is a no-op: titles are always read.

The output is one self-contained static HTML file: left rail with category nav, search box, and tag filters, plus a single-column list. Inline style and script, no build step, no tracking; the only network request besides the sites themselves is the Google Fonts stylesheet. Run it any time you add, remove, rename, or move a site. The generated `index.html` overwrites the previous one. Safe to run repeatedly; identical inputs on the same calendar day produce byte-identical HTML.

Category dot colors and per-category blurbs live in `generate_index.py` (`CATEGORY_DOTS`, `CATEGORY_BLURBS`). Unknown categories get a fallback dot and no blurb.

## Deploy

This repo is designed for **Cloudflare Pages** as a single project. Every folder becomes a path:

- `https://your-domain.com/` → the generated homepage
- `https://your-domain.com/hermes/bot-mode-mastery/` → that site
- `https://your-domain.com/sharepoint/ipc-scoped-flow/` → that site

No build step needed. Set the build command to empty and the output directory to the repo root.

## Rules

1. Every site is a folder with an `index.html`. No exceptions.
2. Max one level of nesting: `category/site/index.html`. Not `category/subcategory/site/index.html`.
3. Always set a `<title>` in each site's `index.html`.
4. Always run `python generate_index.py` after structural changes.
5. Don't commit the `index.html` at the root if you're also auto-generating it in CI, pick one source of truth. Manual is fine for now.
6. Don't put non-site files at the root (scripts, configs) inside category folders. The generator skips dotfiles and known noise (`.git`, `node_modules`, `__pycache__`), but anything else looks like a site to it.

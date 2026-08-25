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
└── shared/                 ← category: cross-tool / general
    ├── bot-roster/
    └── obsidian-vault-circuit/
```

## Category convention

Categories are folders at the root level that contain site folders inside them. The generator auto-detects them:

- **Folder with `index.html` directly inside** = a **site**. It shows up as a card.
- **Folder with no `index.html`, but subfolders that each have `index.html`** = a **category**. Its children show up grouped under a header named after the folder.

You can nest one level deep. Deeper nesting is not supported and not needed.

### Naming

- **Categories**: lowercase, no spaces. One word if possible (`hermes`, `codex`, `claude`, `shared`).
- **Sites**: lowercase, hyphens, descriptive (`bot-mode-handoff`, `codex-mastery`). Avoid generic names like `site1`.

### Which category?

| If the site is about...                         | Put it in  |
|-------------------------------------------------|------------|
| Hermes Agent (setup, modes, bot fleet, flightpath) | `hermes/`  |
| OpenAI Codex (agent, mastery, vault)             | `codex/`   |
| Claude Code (control stack, workflows)           | `claude/`  |
| Cross-tool, shared infrastructure, general tools | `shared/`  |
| Something new that doesn't fit any of the above  | make a new category folder |

When in doubt, start a new category folder. A sparse category is better than a wrong one.

## Adding a new site

1. Pick a category (or create one):
   ```bash
   mkdir -p codex/new-site-name
   ```

2. Add your `index.html`:
   ```bash
   echo "<!DOCTYPE html><html><head><title>New Site Name</title></head><body><h1>Hello</h1></body></html>" > codex/new-site-name/index.html
   ```

3. Set a descriptive `<title>` in that `index.html` — the generator uses it as the card label when you pass `--titles`.

4. Regenerate the homepage:
   ```bash
   python generate_index.py --titles
   ```

5. Commit and push. Cloudflare Pages deploys automatically.

## Regenerating the index

```bash
python generate_index.py --titles      # use each site's <title> as the label
python generate_index.py               # use folder names as labels
python generate_index.py --dry-run     # preview without writing
python generate_index.py --root /path  # scan a different directory
```

Run this any time you add, remove, rename, or move a site. The generated `index.html` overwrites the previous one. Safe to run repeatedly.

## Deploy

This repo is designed for **Cloudflare Pages** as a single project. Every folder becomes a path:

- `https://your-domain.com/` → the generated homepage
- `https://your-domain.com/hermes/bot-mode-mastery/` → that site
- `https://your-domain.com/codex/codex-mastery/` → that site

No build step needed. Set the build command to empty and the output directory to the repo root.

## Rules

1. Every site is a folder with an `index.html`. No exceptions.
2. Max one level of nesting: `category/site/index.html`. Not `category/subcategory/site/index.html`.
3. Always set a `<title>` in each site's `index.html`.
4. Always run `python generate_index.py --titles` after structural changes.
5. Don't commit the `index.html` at the root if you're also auto-generating it in CI — pick one source of truth. Manual is fine for now.
6. Don't put non-site files at the root (scripts, configs) inside category folders. The generator skips dotfiles and known noise (`.git`, `node_modules`, `__pycache__`), but anything else looks like a site to it.

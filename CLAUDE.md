# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A monorepo of standalone static HTML sites (`category/site-slug/index.html`) deployed by Cloudflare Workers Builds from `origin/main`. There is no build step and no dependencies: Python 3 stdlib and Node (tests only). [README.md](README.md) documents conventions, front-matter fields and deploy workflow in detail; read it before adding or moving sites.

## Commands

```bash
python generate_index.py                  # regenerate root index.html (always commit the output)
python generate_index.py --strict         # make lint warnings fatal
python import_site.py SRC.html category/slug --description "..." [--tags a,b] [--pinned] [--archive]
python update_repo_states.py --dry-run    # preview watchlist/repo-states (needs a GitHub token)

# Full test suite (same as CI)
python -m unittest discover -s tests -v
node tests/test_index.cjs index.html      # run after regenerating; executes the index's inline JS against a DOM stub

# Single test
python -m unittest tests.test_generate_index.<Class>.<test_name> -v
```

## Architecture

- **`generate_index.py` is the source of truth for the root `index.html`.** It scans for folders containing `index.html` (a site) or whose children do (a category), max one level deep, and emits one self-contained page with inline CSS/JS. Never hand-edit the root `index.html`. Per-category colors and blurbs live in `CATEGORY_DOTS` / `CATEGORY_BLURBS`; a new category needs entries in both or lint warns.
- **Site metadata lives in each site's own `index.html`**: the `<title>` and an `<!-- index: ... -->` comment (description, tags, pinned, `ingested`) in the first 8000 chars, plus the `#ms-homebar` All-sites bar as the first child of `<body>`. The `ingested` timestamp is the first-entry date: preserve it when editing or moving a site. Malformed dates abort generation.
- **`import_site.py`** copies an inbox page into place, injects the front-matter and homebar without touching anything else, refuses duplicates by content fingerprint, and runs the generator.
- **`watchlist/repo-states/index.html` is generated** by `update_repo_states.py` and refreshed daily by `.github/workflows/update-repo-states.yml`, which regenerates, tests, and pushes a `chore: refresh watchlist/repo-states` commit as a bot. Never hand-edit the page, never change its `INGESTED` constant, and expect to pull before pushing. The workflow needs the `REPO_STATES_TOKEN` secret.
- **`.assetsignore`** (gitignore syntax) keeps repo-only files off the public site, since the whole repo root is published. Add any new root-level tooling file to it.

## Working rules

- Committing and pushing to `origin/main` triggers a production deploy; do it only with the user's approval, then check the `Workers Builds: mastery-sites` result and the live path.
- Preserve source HTML on imports: add metadata only to the deployed copy, and archive inbox sources only after the live deploy is verified.
- Site folder names are lowercase-hyphenated; category names are lowercase single words.

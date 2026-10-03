# AGENTS.md

## What this is
Mastery Sites is a monorepo of standalone static HTML reference sites, one per folder at category/slug/index.html, plus a generated root index.html.
Cloudflare Workers Builds deploys GitHub origin/main (aerin00/mastery-sites) to https://mastery-sites.stenguye.workers.dev/. No clone deploys directly; every push to main is a production deploy.
README.md is the full convention reference. Read it before adding, moving, or renaming a site.

## Run and test
- Regenerate the index after any title, metadata, or structural change: python generate_index.py (use --strict before committing, --dry-run to preview).
- Import an inbox page: python import_site.py SRC.html category/slug --description "..." --tags "a, b". Archive the inbox source only after the live path is verified.
- Tests use only the standard library and Node, with nothing to install: python -m unittest discover -s tests -v, then node tests/test_index.cjs index.html.
- The GitHub Action runs the same tests on every refresh, so keep them green.

## Conventions
- Every site needs a <title>, an <!-- index: --> block within the first 8000 characters carrying description and ingested (ISO timestamp with timezone), and the #ms-homebar All-sites bar as the first child of <body>. import_site.py inserts both.
- ingested is the date the site first entered the repo. Keep the original value when editing or moving a site.
- One level of nesting only. Slugs are lowercase and hyphenated.
- A new category also needs a CATEGORY_DOTS entry in generate_index.py, or --strict fails.
- Site assets sit beside their page. Repo tooling sits at the root and must be listed in .assetsignore, because Workers publishes the whole repo root.
- Keep LF line endings. The Windows clone tends to rewrite files as CRLF, which shows up as whole-file diffs.
- Commit messages are a plain summary that names the site path.

## Clones and git
Two clones push to the same remote: ~/projects/mastery-sites (WSL, used by Hermes crons) and C:\Users\Steven\_Steven OS\07_Dev\00_Mastery_Sites (Windows). Scheduled jobs push too.
Start every session with git pull --rebase origin main.
Commit locally as needed. Push only after Steven says yes. After a push, check the commit's "Workers Builds: mastery-sites" result and load the live homepage and every changed path.

## Never touch by hand
- index.html: it is generated, so regenerate it instead of editing it.
- Cron-owned pages: change their generators, never their output, and leave uncommitted changes in them for the cron to commit.
  - astrology/merriman-market-watch: WSL merriman cron (~/.hermes/scripts/merriman_watch_page.py)
  - watchlist/amex-points: Windows Hermes cron 5210af1e5768
  - hermes/field-notes: Field Notes publisher job
  - watchlist/repo-states: GitHub Action update-repo-states.yml
- Cloudflare build settings live outside this repo. Leave them alone.
- Secrets never enter the repo. REPO_STATES_TOKEN lives in GitHub Actions secrets.

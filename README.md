# Dash Improve My LLMs — the AI and crawler surface for Dash apps

<p align="center">
  <img src="https://cdn.2plot.ai/github_assets/dark_mode_2plot.png" alt="2plot" width="640">
</p>

> The documentation site for [`dash-improve-my-llms`](https://pypi.org/project/dash-improve-my-llms/) — the crawler, agent and SEO companion every Dash app mounts in one line. By [Pip Install Python](https://2plot.dev).

**Live:** [llms.2plot.dev](https://llms.2plot.dev)

[![Dash](https://img.shields.io/badge/Dash-4.4.1-blue.svg)](https://dash.plotly.com/)
[![DMC](https://img.shields.io/badge/DMC-2.7.0-teal.svg)](https://www.dash-mantine-components.com/)
[![Backends](https://img.shields.io/badge/Backends-Flask%20%7C%20FastAPI%20%7C%20Quart-orange.svg)](https://dash.plotly.com/)
[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## What this repository is

Two things at once, and the second is the reason it exists separately from
the package:

1. **The documentation site** for `dash-improve-my-llms` — organised by who
   is asking (MCP clients, web crawlers, paste-to-chat), with a full
   reference section and three live showcases that run the package's own pure
   handlers in-process rather than describing what they would do.

2. **The 2plot network's owner-control bench.** The package is a zero-dependency
   floor that enforces policy and, by decision, never writes it. This site is
   the writable layer above it: an admin-gated control board that mutates a
   store on disk, which reaches the package through its **callable seams** —
   read per request by every worker, so a change lands on the next request
   with no restart and no redeploy.

It is forked from
[dash-documentation-boilerplate](https://github.com/pip-install-python/dash-documentation-boilerplate)
1.6.7 and keeps its machinery — the markdown loader, the access model, the
network directory, the CI baseline. It does **not** keep its documentation:
the template's tutorial pages were deleted rather than hidden, because hiding
them from the sidebar still left them in `sitemap.xml` and `/llms.txt`, which
would have published the boilerplate's docs as this site's own.

---

## Quick start

```bash
git clone <this repo> && cd llms-2plot-dev
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# markdown2dash pins gunicorn<22 against this project's CVE-driven
# gunicorn>=23 floor, so it installs without its dependency graph.
pip install --no-deps markdown2dash==0.1.2

./scripts/dev.sh          # or: python run.py
```

Then open <http://localhost:8559>.

Run it on another backend with one environment variable:

```bash
DASH_BACKEND=fastapi python run.py    # needs uvicorn
DASH_BACKEND=quart   python run.py    # needs hypercorn
```

---

## Layout

```
docs/                       every page on the site, one directory each
  getting_started/          install + the one-line integration
  reference_config/         LLMSConfig, RobotsConfig, configure_seo
  reference_access/         tiers, verdicts, the 402 seam, the rate contract
  reference_geo/            configure_geo — and it inlines lib/policy_store.py
  reference_panel/          the read-only operator panel
  mcp_clients/              audience page + a live registry demo
  crawler_view/             audience page + SHOWCASE A
  paste_to_chat/            audience page
  robots_sandbox/           SHOWCASE B — throwaway RobotsConfig builder
  policy_panel/             SHOWCASE C — live policy + geo choropleth

lib/
  policy_store.py           THE WRITABLE LAYER — flock-guarded JSON,
                            read per request through the 2.7.0 seams
  page_visibility.py        the inherited board's own store
  access.py, page_tiers.py  the tier model
  network_directory.py      the cross-host peer list

pages/
  home.py / home.md         the front door; home.md IS /llms.txt's prose
  markdown.py               the docs/ loader
  control_board.py          /admin/control-board — page visibility + geo

run.py                      the whole integration, top to bottom
BUGS-2.7.0.md               the pre-release soak report
PHASE1-REPORT.md            what is built, deferred, and blocked
```

### Writing a page

Drop a markdown file in a new `docs/<name>/` directory with frontmatter:

```markdown
---
name: My Page
description: One sentence. Becomes the meta description and the llms.txt line.
endpoint: /reference/my-page
category: Reference
icon: tabler:book
lastmod: 2026-08-22
---

.. llms_copy::My Page

.. toc::

### Content
```

It registers automatically. Add it to a cluster in `components/navbar.py`, or
it appears under "More".

**Interactive examples** live beside the markdown as `.. exec::` modules. Two
rules, both enforced by `tests/test_showcase.py` because both fail silently:

- **globally unique id prefixes** — ids share one namespace across every exec
  module, and a collision wires the wrong callback rather than erroring;
- **no import-time `dash.page_registry` walk** — these modules are imported
  from inside the loader's glob loop, so the registry is incomplete; use a
  placeholder `component` and populate by callback.

Directory names must be valid Python identifiers (`docs/mcp_clients`, not
`docs/mcp-clients`) because `.. exec::` resolves a module path.

---

## Testing

```bash
pytest                          # Flask
DASH_BACKEND=fastapi pytest     # FastAPI
python scripts/audit_links.py   # every internal link and anchor
python scripts/network_smoke.py # the post-deploy battery, in-process
```

The suite boots `run.py` itself rather than a test app, secretless — the
zero-secret boot is the first invariant, and every fail-closed assertion
depends on it.

Every test runs unconditionally. The `requires_dimll_27` skip marker was
removed with the floor bump: once `requirements.txt` guarantees the feature,
a skipif that can never fire is a suite quietly overstating its own
coverage.

---

## Configuration

Everything is environment variables; nothing is required for local
development.

```bash
APP_BASE_URL=https://llms.2plot.dev   # canonical tags, sitemap, llms.txt
DASH_BACKEND=flask                    # flask | fastapi | quart
SATELLITE_APP_KEY=llms                # the hub row this app reports under

# The writable layer — both want the mounted disk in production
POLICY_STORE_FILE=/var/data/policy_overrides.json
PAGE_VISIBILITY_FILE=/var/data/page_visibility.json

# The package's own knobs
DIMLL_PANEL_TOKEN=                    # unset ⇒ the operator panel 404s
LLMS_RATE_LIMIT_PER_MINUTE=           # unset ⇒ no rate limiting
GEO_POLICY_URL=                       # RFC 7725 Link on a 451

# Admin gate (the control board fails CLOSED without these)
CLERK_SECRET_KEY= CLERK_PUBLISHABLE_KEY= CLERK_SIGN_IN_URL=
ADMIN_EMAILS=
ALLOW_UNGATED_ADMIN=1                 # local development only
```

Boot prints a `[policy]` or `[visibility]` warning when either store would not
survive a redeploy. **The absence of those warnings in a deploy log is the
acceptance check.**

See `.env.example` for the annotated full list.

---

## The control board

`/admin/control-board`, admin-gated, fails closed without Clerk.

- **Page visibility** — flip any page between public / auth / admin / hidden,
  and toggle whether its `llms.txt` is served to anonymous and AI traffic.
- **The country guardrail** — click a country on the world map, confirm, and
  the next request carrying that `CF-IPCountry` gets `451` on every surface.

A map click *selects*; the button *commits*. Blocking a country acts against
every human and every bot in a geography, and a misclick on a world map is
easy.

Every write callback re-checks `is_admin_user()` **server-side**. The layout
gate only hides the UI — a callback stays callable by anyone who can POST a
reconstructed component id.

---

## Status

`dash-improve-my-llms` **2.7.1** is on PyPI and `requirements.txt` floors
there. The `LLMS_HAS_27` capability block that let this app boot on either
release is gone — collapsed to a plain import, which was its stated design
promise.

**Not deployed yet.** There is no Render service, so the live half of
`cd.yml` — the build-match wait and both live batteries — is dormant, gated
on an unset `SITE_URL` repository variable. Setting that variable to the
service's `.onrender.com` URL brings it up at B3; changing it to
`https://llms.2plot.dev` at cutover is the only other edit. See the header of
`.github/workflows/cd.yml`.

| Document | What it carries |
|---|---|
| [BUGS-2.7.0.md](BUGS-2.7.0.md) | the pre-release soak's findings — **gates the v2.7.0 tag** |
| [PHASE1-REPORT.md](PHASE1-REPORT.md) | what is built, deferred, and blocked |
| [DEVELOPMENT-LOG.md](DEVELOPMENT-LOG.md) | how it went, every issue found, and who owns each fix |

---

## License

MIT — see [LICENSE](LICENSE).

## Community

- **GitHub**: [@pip-install-python](https://github.com/pip-install-python)
- **YouTube**: [2plot.ai](https://www.youtube.com/@2plotai?sub_confirmation=1)
- **The network**: [2plot.dev](https://2plot.dev)

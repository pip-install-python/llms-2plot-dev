# llms.2plot.dev — the dash-improve-my-llms documentation site

## Project Overview

This repo serves <https://llms.2plot.dev>: the documentation site for the
`dash-improve-my-llms` package, and the 2plot network's owner-control bench
for it. **It documents a package it does not contain** — the package lives in
its own repo and installs from PyPI. Read `README.md` for the two-things-at-
once framing, `requirements.txt` for the stack, `CHANGELOG.md` for what
changed and when. Versions are deliberately not restated here; they go stale.

Forked from `dash-documentation-boilerplate` 1.6.7 and kept in sync from its
`sync/SYNC-*.md` specs. The deliberate differences are in `DIVERGENCES.md`.

---

## Custom Directives

| Directive | Syntax | Purpose |
|-----------|--------|---------|
| `toc` | `.. toc::` | Generate table of contents |
| `exec` | `.. exec::module.path` | Render Python component |
| `source` | `.. source::file/path.py` | Display source code |
| `kwargs` | `.. kwargs::ComponentName` | Show component props |
| `llms-copy` | `.. llms-copy::` | The paste-into-a-chat copy button |

`.. source::` expansion into `/<page>/llms.txt` is **fence-aware**
(`pages/markdown.py`): a directive shown INSIDE a fenced block is
documentation, not a directive, and expanding it would close the fence early.

---

## Configuration

### Customization Points

| File | Purpose |
|------|---------|
| `lib/constants.py` | Site identity — `SITE_BRAND`, `BASE_URL`, OG image |
| `lib/policy_store.py` | The writable policy store behind the package's callable seams (geo denylist, vendor policy) |
| `lib/page_visibility.py` | The control board's override store (`PAGE_VISIBILITY_FILE`); overrides beat frontmatter in `lib/access.py` |
| `lib/page_tiers.py` | The declared tier ledger — the second half of the same one declared value |
| `lib/health.py` / `lib/asgi_routes.py` | `/healthz` — one payload builder, three backends |
| `pages/control_board.py` | `/admin/control-board` — live tier, llms.txt and policy toggles (admin-gated, fails closed) |
| `lib/auth_demos.py` | Live-demo teasers rendered inside the sign-in gate cards |
| `assets/main.css` | Custom CSS |
| `templates/index.html` | HTML template (meta tags, SEO) |
| `components/navbar.py` | Navigation ordering |

---

## Development Notes

### Adding a documentation page
1. Create a folder in `docs/` (e.g. `docs/my_topic/`).
2. Write the markdown with frontmatter — `name`, `description`, `endpoint`,
   and optionally `tier`, `llms_public`, `schema_type`, `lastmod`.
3. Reference Python examples with `.. exec::docs.my_topic.example` (the module
   exposes a module-level `component`).
4. The page auto-registers on both lanes: the browser page AND the machine
   twin at `/<endpoint>/llms.txt`.

### The two lanes
The browser lane and the machine lane are **different documents**. A page
renders through `markdown2dash`; its twin is the directive-expanded markdown
handed to `register_page_metadata(llms_doc=...)`. A fix proven on one is
unproven on the other — the fence bug was invisible on the browser lane for
exactly this reason.

### Running the suite
`pytest tests -q` runs against Flask. `DASH_BACKEND=fastapi` and
`DASH_BACKEND=quart` run the same suite against the other two backends; CI
runs all three. The suite is **secretless by design** — `tests/conftest.py`
pins every Clerk and hub secret empty, because the fail-closed behaviour is
only provable when nothing is configured.

---

## Resources

- [dash-improve-my-llms](https://pypi.org/project/dash-improve-my-llms/) — the package this site documents
- [Live site](https://llms.2plot.dev) · [the hub](https://2plot.ai)
- [dash-documentation-boilerplate](https://github.com/pip-install-python/dash-documentation-boilerplate) — the template
- [Dash Documentation](https://dash.plotly.com/) · [Dash Mantine Components](https://www.dash-mantine-components.com/)

---

## Network role & the behavioral contract

This repo is a member of the 2plot network — either the template
itself (dash-documentation-boilerplate) or a fork of it serving one
component's documentation. **Identity derives from the repo, never
from this file**: the app key comes from `SATELLITE_APP_KEY` and
run.py's fork point, the host from `lib/constants.py`'s `BASE_URL`,
the deliberate differences from the template from `DIVERGENCES.md`
at the repo root. If those disagree with anything written here,
they win.

### The contract — every session, every prompt

1. **Check the prompt against this tree before executing.** Prompts
   are written from the template's perspective and your fork may
   legitimately differ — floors, backends, payload shapes, page
   sets. A prompt step that doesn't fit this repo is a finding to
   return, not an instruction to force.
2. **Corrections are your job, not scope creep.** If a prompt's
   reference list doesn't match its steps, if its assumed state is
   wrong, or if executing it as written would produce a
   green-but-vacuous result, say so and propose the corrected
   version before running it.
3. **Verify your own deploy on the wire before reporting.** A push
   is not a result. Run `/wire-verify` (or its manual equivalent)
   against production and paste what came back. If your sandbox
   cannot reach your own domain, say exactly that — an unverified
   claim marked as unverified is honest; the same claim unmarked is
   not.
4. **Report observed versus expected, with evidence.** Paste the
   JSON, the status code, the test count. "Should work" and summary
   claims without artifacts are not reports.
5. **Divergence is legitimate when written down.** Before syncing
   template changes, read `DIVERGENCES.md`; never let a sync
   "restore" a recorded deliberate difference. When you deliberately
   diverge, record it there in the same commit — an unrecorded
   divergence is indistinguishable from drift and will be treated
   as drift.
6. **Never touch**: environment variable VALUES, hosting dashboards,
   secrets, other repos' trees, or anything the prompt didn't put in
   scope. Enumerate what you cannot do (closing PRs, dashboard
   steps) for the owner instead of claiming it done.

### Verification traps (fleet-learned, keep them)

- A `>=` floor can never pull a new release through a Docker cache
  hit — the requirements line changing IS the cache bust, and floors
  live in several encodings (requirements, run.py's boot floor,
  tests, CI): grep the number, move every one.
- `/healthz` build == HEAD is the deploy proof; a missing geo block
  on dimll ≥2.7 means the cache trap fired (unless DIVERGENCES.md
  says this host's healthz is deliberately minimal).
- Probe with GET, not HEAD — HEAD responses omit the Link headers.
- Run-watchers keyed on a commit sha can match Dependabot's runs on
  the same sha — key on the workflow path (cd.yml) instead.
- The browser lane and the machine lane are different documents;
  a fix proven on one is unproven on the other.
- A bot-merged PR — any GITHUB_TOKEN merge — lands with ZERO
  workflow runs on the merge sha (anti-recursion) yet still reaches
  production: the deploy hook builds branch HEAD, so an in-flight
  CD run ships the merge while its own build-match wait holds out
  for the superseded release sha. Observed live on 4a1d430
  (2026-08-25). Since 1.6.25 the wait fails FAST on this (live
  build a descendant of the wanted sha, via the compare API)
  instead of going red at timeout, and the remedy is policy —
  actions PRs: human merge when green; never a bot actor on main.
- Anonymous api.github.com is 60 requests/hour. With no `gh` and no
  token, read a run ONCE after CI's own jobs report complete — a
  blind 20 s poll loop spends the whole budget reading rate-limit
  bodies as "not done yet" (modelviewer, 2026-08-26).
- A GitHub API JSON body WITHOUT the field you asked for
  (`workflow_runs` absent, not empty) is a rate-limit error body,
  never an empty result — check the field exists before trusting
  the answer.
- `git fetch` before any audit: the fan-out pushes to these repos
  now, and a checkout current yesterday is 2–3 merges behind
  origin/main today (three pilot sessions, same day, 2026-08-26).

# Divergences from the template

Every DELIBERATE difference between this repo and
dash-documentation-boilerplate, with its reason. This file is the
boundary between design and drift:

- Template syncs read this file FIRST and must not "restore" anything
  recorded here.
- A difference not recorded here is treated as drift and will be
  synced away.
- Record the divergence in the SAME commit that creates it — one
  line: what differs, why, and what the template would otherwise do.
- An empty list is a statement too: it means this repo intends to
  match the template exactly.

Retirements are MARKED, not deleted — a record that overclaims
teaches the next sync to defend a line nobody is attacking.

## This repo's divergences

**1. This host documents a package it does not contain.** `docs/` is
wholly this site's own — the template's tutorial pages were DELETED at
fork time, not hidden, because hiding a page from the sidebar still
leaves it in `sitemap.xml` and `/llms.txt` and would have published
the boilerplate's docs as this site's. A sync must never restore
`docs/`; the template's page set is not this site's page set, and
every path-shaped constant that follows from it (`network_smoke.py`'s
probe paths and `HIDDEN_DOC_PATHS`, `SITE_H1`, the navbar order) is
this fork's.

**2. `lib/policy_store.py` and the board's policy half are fork-only.**
This site is the network's owner-control bench for the package it
documents: a JSON store on the mounted disk, read per request through
the package's CALLABLE seams (`configure_geo(deny_countries=...)`,
`RobotsConfig(vendor_policy=...)`), so a toggle lands on the next
request in every worker with no restart. `pages/control_board.py`
therefore carries a "Country guardrail" section the template's board
has no equivalent of, and `run.py` passes callables where the
template passes static values. The template has no such layer by
design — the package is the floor that enforces policy and never
writes it.

**3. The home page's published identity is set in `run.py`, not in
`lib/page_visibility.published_name`.** Same contract as
SYNC-1.6.10-1.6.16 item 8 — whatever name the package injects is the
name the llms preamble uses, `SITE_BRAND` at `/` — in a different
shape: this fork's home is a hand-written `pages/home.py`, so there is
no `pages/markdown.py` call site to route a `published_name` helper
through. `run.py`'s `register_page_metadata(path="/", name=SITE_BRAND)`
IS the mechanism. Do not add the helper here to "restore" it; the
every-page single-h1 sweep covers `/` and holds the contract.

**4. `cd.yml`'s live half is gated on the `SITE_URL` repo variable
with no fallback.** The template hard-codes its own host, so a fork
that inherits it verbatim polls SOMEBODY ELSE'S `/healthz` for
fifteen minutes and reports red on day one. An empty `SITE_URL` is
this fork's signal that no live target is configured yet; the
build-match wait and the whole verify job skip with a notice. The
guard stays. (Live status, 2026-08-26: the variable is still unset
while the site is live — a repo-settings change for the owner, not a
code divergence.) Since the 1.6.35 promote round the same guard is a
SECOND conjunct on `verify`'s `if`, after the item's required
`needs.deploy.result == 'success'`; `tests/test_cd_promotes_release.py`
is therefore PORTED, not byte-copied — it asserts that deploy-success is
required and that no `needs.deploy.result !=` chain creeps back, rather
than the template's exact `if:` string.

**5. The package-behaviour suites are additions, not replacements.**
`tests/test_geo_guardrail.py`, `test_operator_panel.py`,
`test_vendor_policy.py`, `test_toll_gate.py`, `test_control_board_geo.py`,
`test_showcase.py`, `test_prerender_seo.py` and
`test_prerender_idempotency.py` pin the documented package's contract
from the app's side — the thing a documentation site can prove that
the package's own suite cannot. Nothing inherited was dropped for
them; a sync adding template tests does not collide with these.

**6. Three fork-only root documents.** `BUGS-2.7.0.md` (the package
soak that gated the 2.7.0 tag), `PHASE1-REPORT.md` (this fork's build
report) and `DEVELOPMENT-LOG.md` (its running log). They are records,
not machinery — a sync should neither restore nor remove them.

## Byte-owned paths

Paths this fork owns byte-for-byte. The F3b fan-out never overwrites
a path listed here; everything else in the spec's `sync-verbatim`
block is the template's to update mechanically. Prose above explains
divergences; this block is the machine answer.

Repo-relative paths, one per line, `#` comments, no `..`; exactly one
block. An EMPTY block means "the template owns every sync-verbatim
path here" — present so the absence is a statement. When the block
exists it is authoritative; a fork without it gets the conservative
mention heuristic (over-flags, never restores).

Audited 2026-08-26 against every `sync-verbatim` path in
SYNC-1.6.10-1.6.16, SYNC-1.6.17-1.6.21 and SYNC-1.6.22-1.6.29 (the
three kit skills, `tests/test_claude_kit.py`, `.github/dependabot.yml`,
`tests/test_auth_demos.py`): this fork makes no byte-level claim on
any of them, and none of the divergences above touch one. The block
is EMPTY on purpose — drift is never fenced, because the fan-out is
how drift gets fixed.

```yaml byte-owned
```

## Posture

What this host ANSWERS, as measured — never as intended. The hub's F4
battery seeded these per-host postures from its own table, which is a
copy of a measurement somebody took once; this block homes them in the
repo that can keep them true, and the hub reads it instead.

All keys optional. An EMPTY block means "the template defaults" —
present, so the absence is a statement. `tests/test_claude_kit.py`
validates the shape (and holds `runtime:` against render.yaml, where the
repo declares one); nothing validates the numbers but a probe, so
re-measure when you change what this host serves:

    ai_bots   the status an AI-crawler UA receives per path, measured
              with a real vendor UA (ClaudeBot, GPTBot — NOT a UA-less
              curl, which is classified separately). A blocked vendor
              gets 403 on the browser document while the agent surfaces
              stay open — that asymmetry is the posture, and it is
              invisible from a browser.
    healthz   `full` (the fleet payload: app, backend, build, geo,
              python, …) or `minimal` (a deliberately reduced body).
    runtime   `docker` or `python` — the Render service runtime, which
              decides whether PYTHON_VERSION is required or forbidden
              (sync spec item 5).
    deploy    `release-branch` — Render deploys `release`, which only
              CD writes after a green matrix (1.6.35, sync item 13);
              `build` on /healthz is HEAD of `release`, and `main`
              ahead of it is an uncertified push pending, never drift
              and never a hand deploy. ABSENT reads as `main`.

Measured on llms.2plot.dev, 2026-08-29, build ae1dce6 — GPTBot UA for
the `ai_bots` row, a browser UA for the `/healthz` body:

```yaml posture
ai_bots: {"/": 403, "/llms.txt": 200, "/healthz": 403}
healthz: full
runtime: python
deploy: release-branch
```

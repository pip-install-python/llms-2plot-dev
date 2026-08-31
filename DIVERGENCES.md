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
guard stays. (Live status CORRECTED 2026-08-29: the variable IS
now set — run 33266359801's "Say plainly that the live half is dormant"
step SKIPPED, which is `env.SITE_URL != ''` measured from inside the
workflow. The 2026-08-26 note that it was still unset is retired.) Since the 1.6.35 promote round the same guard is a
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

**7. RETIRED 2026-08-29, same day — the first-promote observation, kept
because the timing will recur on any fork adopting item 13.** When the
promote round landed, `5c73a53` reached `main` at 17:43:00Z and was
fast-forwarded onto a newly created `release` at 17:45:24Z, and at
18:22:44Z `/healthz` still served `ae1dce6` — where the PREVIOUS deploy
had been live within six minutes of its push. CD run 33266359801 went
red on its build-match wait for exactly that, its promote step already
green. From this session's vantage the cause was NOT decidable — the
dashboard is not readable from here — and an earlier version of this
entry inferred autoDeploy was off. That inference was wrong: the ops
seat reports the owner switched the service's Branch to `release` at
~18:00Z, and the very next run (33281935425, `0081f65`) went fully green
in five minutes — promote, build-match wait, and verify including its
`/healthz build == github.sha` step. Nothing in this repo's code was at
fault and nothing needs changing.

The keepable lesson: on a fork whose Render service is not
Blueprint-managed, `render.yaml`'s `branch:` is documentation and the
dashboard Branch field is the switch — item 13 says so in its notes, and
this host is a worked example. Expect the FIRST promoted run after
adoption to go red on the wait until the dashboard is switched, and read
that red as the owner step outstanding, not as a defect in cd.yml.

**8. RETIRED 2026-08-31 — both seams closed template-side at 1.6.41.**
At 1.6.38 this fork reported that two of the eleven navigation files
could not be byte-identical, and that both seams were the template's
rather than ours: `components/header.py` hardcoded its own logo
filename, and `tests/test_nav_contract.py` named `/backend-comparison`,
a tutorial page this fork deleted at fork time. 1.6.41 closed both —
`LOGO_ASSET` / `LOGO_STYLE` / `WORDMARK_COLOR` / `WORDMARK_VISIBLE_FROM`
moved to `lib/constants.py`, and the aside pin now derives its paths
from the registry. Re-measured against 4ac02e0: this fork's
`components/header.py` and `tests/test_nav_contract.py` are byte-copies
of the template's, and the byte-identity evidence recorded against
519d496 is superseded. Kept as a retirement rather than deleted, per
this file's own rule: the record that a fork's report closed a template
seam is worth more than the absence of it.

**9. `SAME_AS` carries the PyPI distribution as well as the repo.** The
template's 1.6.38 constant is `SAME_AS = [GITHUB_URL]`. This site
documents a published package, so its JSON-LD identity claims both the
repo and `https://pypi.org/project/dash-improve-my-llms/` — the
docs-home ↔ package loop this site exists to close. `GITHUB_URL` itself
points at the PACKAGE's repo, not this site's, for the same reason.

**10. `.. exec::` expands into the machine lane; the template's does
not YET — measured there too, and held for the owner.** Item 18's amended highlight 7 names the fourth mechanism
for a silent surface: a markdown2dash directive that renders Dash
components puts its output only in the React tree, while the machine
lane, the prerender and the crawler HTML are built from the markdown
SOURCE with the directive line stripped. Measured here 2026-08-31 and
present: `/showcase/robots-sandbox/llms.txt` read "Move the switches.
The document on the right is generated by..." followed by a blank line,
on four pages whose prose actively refers to the missing component.

`pages/markdown.py` now expands `.. exec::module` into the module's
SOURCE through the SAME fence-aware pass `.. source::` uses — one parse,
two consumers. The component cannot be serialised into markdown and a
screenshot would be worse than nothing to an agent; its source is what
produces the demo, and it keeps both lanes describing one artifact.
`tests/test_exec_lane_parity.py` pins row CONTENT (real code lines from
each module, never a heading), derives its cases from the docs tree, and
MUTATION-CHECKS itself — the expansion was disabled and all four content
pins plus the vacuity guard were confirmed to go red before being
restored.

Recorded as a divergence because the template ships no `.. exec::`
expansion: this fork is ahead of it here, not behind. Offered upstream
and CONFIRMED there 2026-08-31 — the template has the same class on four
documents in its raw-directive variant, worse than this fork's: the line
is served LITERALLY, so an agent reads `.. exec::docs.…` as prose and
gets neither the component nor the code, with nothing to signal that
anything is missing. The template seat is holding the fix for the owner
rather than landing it, because it changes what every machine document on
that site contains. modelviewer answers the same class by PAIRING every
`.. exec::` with a `.. source::`, which costs no parser change and is the
better road where the pairs already exist; it cannot cover unpaired
offenders, which is what both this fork and the template had.

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

              MEASURED on this host, not merely consistent-with, and by
              the negative control rather than the happy path. Item 13's
              notes say a first promoted run cannot tell
              autoDeploy-from-main from autoDeploy-from-release, because
              both branches then hold the same sha. A RED push separates
              them, and this host had one. Run 33337712632: `ee75b5b`
              reached `main` at 21:55:01Z and the matrix went red at
              21:57:01Z on `ci / lint`, so the `deploy` job SKIPPED and
              `release` never moved — it went `bdd8e77` → `625c91c` and
              never held `ee75b5b` (this session's own readings). The ops
              seat's sampler, which this session did not run, shows the
              wire holding `bdd8e77` across the whole window
              21:54:34–22:01:29. On a host whose promote→wire time is
              about 90 seconds, a Render watching `main` would have built
              the red sha inside that window. It did not. The two halves
              together are the proof; neither is sufficient alone.
              Corroborating, from the seat's timing of the next run:
              `release` 22:01:29Z → wire 22:02:56Z, promote-first.

`ai_bots` is CURRENT: round 3.4 (owner decision, 2026-08-30) retired
this host's training wall in `run.py` (`block_ai_training=False`), the
flip deployed in run 33337897170, and the values below are the wire's own
answer afterwards. History, so the next reading can be compared against
something:

  - 2026-08-29, build ae1dce6, wall UP: `/` 403 · `/llms.txt` 200 ·
    `/healthz` 403, identically for ClaudeBot and GPTBot.
  - 2026-08-30 14:09Z, still ae1dce6/0081f65 on the wire, wall UP:
    the same triple, both UAs, and IN-PROCESS at the same commit the
    same triple again. Edge and app AGREE, which means every 403
    measured on this host is the APP's wall. No separate Cloudflare
    wall has been observed here; whether a zone rule exists at all is
    an open question for the owner, not something this fence can answer.
  - 2026-08-30 22:05Z, build 625c91c, wall DOWN — the reading below:
    `/` 200 (14,133 B crawler document) · `/llms.txt` 200 (13,801 B) ·
    `/healthz` 200, identically for both UAs, and `/robots.txt` carrying
    `Allow: /` for ClaudeBot, GPTBot and CCBot (this fork renders the
    explicit allow rather than no stanza, because it passes the callable
    `vendor_policy` seam — see divergence 2). NO edge wall appeared when
    the app's came down, which settles the question above: every 403 this
    host ever served was its own, and the owner has since confirmed no
    Cloudflare rule exists on the zone at all.

Measured on llms.2plot.dev, 2026-08-30 22:05Z, build 625c91c, with the
real ClaudeBot and GPTBot UAs for the `ai_bots` row and a browser UA for
the `/healthz` body:

```yaml posture
ai_bots: {"/": 200, "/llms.txt": 200, "/healthz": 200}
healthz: full
runtime: python
deploy: release-branch
```

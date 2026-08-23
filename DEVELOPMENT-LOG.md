# DEVELOPMENT-LOG.md — llms-2plot-dev, phase 1

**Written:** 2026-08-22 · **Re-soak appended:** 2026-08-23 · **Repo:**
`llms-2plot-dev` · **Branch:** `main`, origin unset · origin unset.

Companions: **[BUGS-2.7.0.md](BUGS-2.7.0.md)** (the package findings — read
that first if you are deciding whether to ship 2.7.0) and
**[PHASE1-REPORT.md](PHASE1-REPORT.md)** (what is built, deferred, blocked).

This document is the narrative the other two do not carry: how the work
went, everything that turned out to be wrong, and who owns each fix.

---

## 1. What this project is

Two jobs in one repository.

**The documentation site** for `dash-improve-my-llms` — the package that
mounts `/llms.txt`, `/robots.txt`, `/sitemap.xml`, a crawler prerender and
an MCP bridge into a Dash app in one call.

**The network's owner-control bench.** The package enforces policy and, by
decision, never writes it: its config is per-process module state, so a
control plane inside it would change one gunicorn worker and lie on the
next refresh. This site is the writable layer above — an admin-gated board
that mutates a store on disk, which the package reads back through
*callable seams* on every request. A change lands on the next request, in
every worker, with no restart.

Phase 1 had a second mandate: **soak-test the unreleased 2.7.0 package**
from the application side, before its tag ships.

---

## 2. How it went

### Step 0 — the fork and a baseline worth trusting

Cloned the boilerplate at 1.6.7 with full history (91 commits), removed
`origin`. Ran the inherited suite green on the pinned 2.6.1 — **322
passed** — then force-installed the local 2.7.0 wheel and ran it again.
Identical.

The soak came *before* the build on purpose: a green baseline established
after changing things proves nothing.

### B1 + B7/1 — identity, and the seam wired live

Brand, origin, favicons from the hook mark, the `SATELLITE_APP_KEY` fork
point. Then `lib/policy_store.py` wired through
`configure_geo(deny_countries=…)` and `RobotsConfig(vendor_policy=…)`.

The suite then ran **with the guardrail live, the panel registered and the
vendor seam attached**, against an empty store. Still 322 — byte-identical
-when-unset in a stronger form than the brief asked for.

### The soak — seven charter items, two defects

Geo across ten surface classes plus the SPA navigation POST; the panel's
gate and anti-drift guarantee; per-vendor policy; the prerender idempotency
fix; the rate contract, the dark 402 seam, the hub ceiling.

Two real defects, both contradicting documented guarantees, both pinned as
`xfail(strict=True)` so they fail loudly the day they are fixed.

### B2 + B7 — content, showcases, control board

Three audience pages at byte-for-byte preserved URLs. Three showcases
running the package's own pure handlers in-process. The inherited board
grew a country guardrail.

### The correction — "this still looks like the boilerplate"

Owner review caught what the tests could not. Covered in §3.

### B7 fix — opening the board in a browser

Two bugs in the geo map, both found in the first minute of clicking.

---

## 3. Issues found

Grouped by who owns the fix. The self-inflicted group is the largest,
which is the honest result.

### 3a. In the package — `dash-improve-my-llms` 2.7.0

These gate the tag. Full repro in [BUGS-2.7.0.md](BUGS-2.7.0.md).

| # | Sev | Issue | Where |
|---|---|---|---|
| 1 | **HIGH** | A `deny_countries` callable returning an **unhashable element** (dict/list/set) raises `TypeError` out of the middleware — **every request on every surface 500s**. GEO.md promises "it can never take down the request path". 2.8's bot × country matrix arrives through this same seam. | `geo.py:221` |
| 2 | **HIGH** | A per-vendor **block on a traditional crawler is enforced but never published** — the middleware 403s Googlebot while `robots.txt` still says `Allow: /`. Contradicts W2's "one fold drives robots.txt AND the middleware". Silent and SEO-severe. | `robots_generator.py:150, :196` |
| 3 | docs | GEO.md says a malformed *entry* voids the whole denylist; the code skips the entry and keeps the valid ones. The code is right; the doc should move. | `docs/GEO.md` |
| 4 | docs | GEO.md says a raising `resolver=` resolves "unknown"; it falls back to header resolution — and a resolver returning *garbage* does not fall back. | `docs/GEO.md` |

### 3b. Inherited from the template

**Each fires on every fork, not just this one.** Worth pushing upstream to
`dash-documentation-boilerplate`.

| Issue | Where | Status |
|---|---|---|
| **`excluded_links` hides from the sidebar only.** Pages stay in `sitemap.xml`, `/llms.txt`, `/llms-full.txt`, the MCP set and the prerender. A fork that "hides" the tutorial pages still publishes them — duplicate content competing with the template's own site. | `components/navbar.py` | fixed here |
| **The header wordmark was a hardcoded string** — "Dash Docs", beside the template's logo, which every fork then serves as its own identity. | `components/header.py` | fixed here |
| **A guard test that stops guarding on any fork.** The foreign-canonical check spelled the template's hostname literally, so on a renamed fork it rewrote nothing and passed as a no-op. | `tests/test_smoke_live.py` | fixed here |
| **The control-board stores were not gitignored.** With their env unset both fall back to the app directory, so running the board locally writes a real policy file into the checkout. The template gitignores its analytics ledger for exactly this reason. | `.gitignore` | fixed here |
| Hardcoded `host='0.0.0.0'` and a **string** port — a platform injecting `$PORT` needs a code change, and the dev server publishes to the whole network. | `run.py` | fixed here |

### 3c. Self-inflicted — written, then caught

| Issue | Caught by | Pinned by |
|---|---|---|
| **The site was renamed, not rebuilt.** B1 changed identity strings while eleven byte-identical template pages stayed published. Hiding them from the sidebar felt like a fix and was not one. | owner review | pages deleted; sitemap/llms.txt assert 11 own pages |
| **The map could only *un*-deny a country.** Plotly emits `clickData` only for locations present in the trace, and only the denied countries were plotted — so the map was clickable exactly where a block already existed. Click-a-country-to-deny never worked. | browser | `test_the_map_is_clickable_for_a_country_that_is_not_denied` |
| **An empty denylist painted Antarctica red.** A single-value `z` makes Plotly autoscale to the top of the colorscale, so "nothing denied" rendered as a blocked continent. | browser | `zmin`/`zmax` pinned + a test |
| **The showcases broke the app on its own pinned floor.** All three imported the 2.7.0 vendor registry at *layout* time, so the app would not boot on the `>=2.6.1` `requirements.txt` still pins — and PHASE1-REPORT.md claimed the opposite. | verifying a claim | suite runs on both releases (401 passed on 2.6.1) |
| The policy store accepted vendor **display names**, which the package ignores with a log line — an override that silently does nothing. | writing the seam test | registry validation at the write |
| Reference prose wrote a literal `<div class="dv-banner">`, which is exactly what the chrome-leak detector matches. | the inherited test | the test it tripped, kept |
| Showcase A assumed every vendor publishes a robots token. `anthropic-legacy` is UA-only with an empty tuple — it crashed the app at boot. | first run | falls back to UA tokens |
| The prerender subprocess harness was Flask-shaped and failed on FastAPI, which needs the ASGI lifespan. | second backend | backend-aware; 9 passed on both |

**The pattern worth naming:** four of these were invisible to a suite that
had 540 passing tests at the time. Tests asserted the store and the 451 —
the *state* — and never the affordance that drives it. Two were found by
opening a browser for sixty seconds.

### 3d. Environment

- **No network in the sandbox.** `pip install -r requirements.txt` cannot
  reach PyPI, so the 2.6.1 baseline was mirrored from the boilerplate's own
  resolved venv rather than re-resolved. Nothing about what was *tested*
  changes; the resolution step was not re-proved and should be run once on
  a networked machine before staging.
- **One socket, non-reclaimable.** The sandbox permitted the first dev
  server to bind, then refused every later bind and every attempt to kill
  the first. The running board therefore predates the map fix.

---

## 4. Decisions on the record

| Decision | Rationale | Cost |
|---|---|---|
| **Delete the template docs** (owner) | A site that publishes another site's documentation is not its own site. | Overrides the kickoff's "NEVER deleted — wave-sync purity". Template syncs touching `docs/` now need manual resolution. |
| **Capability probe, not version compare** | `LLMS_HAS_27` asks whether the symbol exists, so a partial backport or a yanked release cannot make the guard lie. | A block of degrade code until the floor moves. |
| **No throttle on the store read** | The seam's promise is "the next request". A throttle downgrades that to "probably, within a second". A visibility toggle can land late; a compliance block cannot. | One `os.stat` per request. |
| **Select, then commit** on the map | Blocking a country acts against every human and bot in a geography, and a misclick on a world map is trivially easy. | One extra click. |

---

## 5. Where it stands

### Done and verified

- **Identity** on every surface. No served surface carries the template's.
- **Eleven pages**, all this site's own: 3 audience, 5 reference,
  3 showcase (+ home).
- **The writable layer** — `lib/policy_store.py` + a control board that
  toggles a country and has it enforced on the next request, demonstrated
  live by editing the store from outside the running app.
- **The soak** — all seven charter items on both backends.
- **567 / 564 tests** (Flask / FastAPI), 8 strict xfails, 0 broken
  internal links, green on both 2.6.1 and 2.7.0.

### Blocked on the package publishing

`requirements.txt` floors at `>=2.6.1` deliberately. When 2.7.0 ships:
move the floor, raise `LLMS_PKG_FLOOR`, delete the capability block, and
run a clean install on a networked machine.

### Deferred to B3+

- GitHub repo, Render service, env groups, the 1 GB disk, staging, cutover.
- **The social card does not exist.** `OG_IMAGE_URL` points at a CDN object
  never uploaded, so every share currently unfurls without an image.
- A live browser pass of all three showcases as human *and* crawler UA.
  Only the control board has been seen in a real browser.
- The bot × country matrix (first 2.8 item). The board's UI and the
  store's forward-compatible key handling are already shaped for it.

---

## 6. Next

1. Owner reads `BUGS-2.7.0.md`, rules on the two high-severity defects.
2. Package session fixes, rebuilds the wheel, re-soaks here — the eight
   strict xfails become failures the moment the fixes land. That is the
   signal.
3. Tag and publish → 4. floor moves here → 5. B3 staging.

Before any of that: **restart the dev server and click the map.** The
running instance predates the fix, and the two bugs it exposed in a minute
were invisible to the suite.

---

## 7. Re-soak — 2026-08-23

The hook repo shipped the pre-tag fix batch. Installed
`dash_improve_my_llms-2.7.0-py3-none-any.whl`
`sha256:b91411257750aa1b4f2717ff41eff88717f50d6682c49ae009f8ce5c5e286d56`.

**The signal fired.** All eight strict xfails flipped to `XPASS(strict)` and
failed the run — which is what those markers exist to do. #1 and #2 are
genuinely fixed; #3 and #4 were doc/code disagreements and GEO.md moved to
match the code, which was the recommendation.

Markers removed and assertions inverted, with two strengthened past what the
originals checked:

- **#1** now asserts the *documented contract* rather than merely "not a
  500": an unhashable element yields an **empty denylist**, so a denied
  country is served normally. It also pins the deliberate asymmetry the
  corrected GEO.md spells out — one nested object voids the whole list, while
  a malformed *string* entry is skipped and the valid entries keep blocking.
- **#2** now asserts three halves: the effective verdict, the vendor's **own**
  `User-agent:` group, and the served 403. The middle one matters — the bug
  was inheritance from `User-agent: *`, so a check that only resolves the
  effective verdict would start passing again for the wrong reason the day
  the `*` group flipped to Disallow.

### New finding — #5, and the tag stays held

The batch's H1 dedup landed on `prerender.py` and not on
`html_generator.py`. This package serves **two documents**: a browser-like
UA gets the app shell with the prerender injected; a declared crawler gets a
separate static document. The fix covers the first. Every page of the second
— the one Googlebot, ClaudeBot and GPTBot actually receive — still ships two
identical `<h1>`s. 11/11 pages, both backends.

Pre-existing on 2.6.1, so **not a regression**. But it is the same defect the
fix's own comment describes ("confirmed on every host"), left on the half
that matters more for search. Per the re-soak charter, that holds the tag;
whether to ship anyway is the owner's call and #5 carries what is needed to
make it.

Writing those pins forced a distinction the first draft got wrong: a test
that fetches with `CRAWLER_UA` and looks for the prerender block finds
nothing at all. Both lanes are covered now, with a control test so #5 cannot
silently change shape.

**Also fixed on this side:** `templates/index.html` shipped an `<h1>` in its
`<noscript>` block — a crawler runs no JS and parses noscript, so every page
had a second site-wide h1 competing with its own. Demoted to `<h2>`. Same
defect class as #5, one layer out, and worth a line in the boilerplate
alongside §3b.

### Totals after the re-soak

| | Flask | FastAPI |
|---|---|---|
| Full suite | 585 passed, 1 skipped, 1 xfailed | 582 passed, 4 skipped, 1 xfailed |

The single remaining xfail is #5. It will fail the moment #5 is fixed, which
is the signal for the next re-soak.

---

## 8. Final re-soak — 2026-08-23 — TAG READY

`sha256:05180075dd43ddb083af555e3cc7bf5345fe84c6554e5b8f17fb9bc807ade1a0`,
verified against the file **before** installing.

**#5 fixed at 93a02d6.** `html_generator.py` now carries the identical
leading-h1 guard `prerender.py` has, and its xfail flipped as designed.
Marker removed, behaviour asserted positively.

All three prose shapes are pinned at the generator, not just the one this
site happens to produce: prose that opens with its own h1 (the header
contributes only the description), prose starting mid-thought, and a page
with no prose at all (the header's h1 is the only one and stays). A dedup
that simply *deleted* the header h1 would have passed the end-to-end test and
left doc-less pages with no heading.

The test worth keeping is `test_exactly_one_h1_on_both_lanes_for_every_page`
— browser and crawler counts compared per page, in one place. **That is the
test that would have caught #5 originally**: the package serves two
documents, the first fix covered one, and no single assertion compared them.
A companion test requires both modules to carry the guard, so the lanes
cannot drift apart again.

Measured: **1 h1 on both lanes, all 11 pages, both backends, zero drift.**

### Two link fixes the audit surfaced

- `pages/home.md` still linked `/networks`, a page this fork deleted — it
  resolved through a 301 rather than pointing at its destination. Repointed
  at the policy panel, where the live network directory actually renders.
- `scripts/audit_links.py` now skips pages the package deliberately hides.
  `mark_hidden()` makes a page's `llms.txt` 404 *by design*, and
  `network_smoke.py` asserts it does — an audit that reports designed
  behaviour as a broken link is an audit people learn to ignore.

### Final totals

| | Flask | FastAPI |
|---|---|---|
| Full suite | **597 passed, 1 skipped, 0 xfailed** | **594 passed, 4 skipped, 0 xfailed** |

`audit_links`: 0 broken internal, 0 broken anchors. **No strict xfails remain
anywhere in the suite.**

The soak is closed. Five findings, all fixed and verified from the
application side, on the seam a package suite structurally cannot reach.

---

## 9. Phase B — to production, part 1 (2026-08-23)

dimll shipped, so the migration's production half opened: floor bump →
workflow audit → inaugural push. Stops at the owner gate; no service
creation, no cutover.

### The floor is 2.7.1, not 2.7.0

Checked PyPI at execution time as instructed. The first check showed 2.7.0
(uploaded 17:48:38Z) and **no 2.7.1**. The clean install minutes later
resolved **2.7.1** — the fast-follow landed at 18:24:03Z, *between* the check
and the install. Re-verified and floored on the later one, per the rule that
the fleet's floor round happens once.

2.7.0 is what this app cannot **start** without (it calls `configure_geo`,
the panel, per-vendor policy and the rate ceiling unconditionally). 2.7.1 is
additive: `rel="describedby"` discovery relations on both document lanes plus
`Link` headers, a `text/plain` Accept ramp, and a source digest that makes
representation parity provable. Nothing here needed changing for it.

Moved by **grepping the number**, not from memory — which turned up a third
encoding nobody had touched: `ci.yml` still asserted `>=2.3.4`, inherited
from the template.

### The capability block is gone

That was its design promise, not a convenience. Collapsed to a plain import,
and every guarded call site with it — including `requires_dimll_27` and the
`pytestmark` in six modules. That marker could no longer fire once the floor
guaranteed the feature, and **a skipif that can never trigger is a suite
quietly overstating its own coverage**.

### The resolution re-proof

Phase 1 mirrored the boilerplate's venv because the sandbox had no network,
and said so. This is the real thing: fresh venv on **Python 3.12** (CI's
primary, not phase 1's 3.11), full resolve from PyPI. It pulled genuinely
newer transitives than the mirror — DMC 2.8.0, plotly 6.9.0, pandas 3.0.5,
numpy 2.5.2, gunicorn 26.1.0 — and the suite is green on all of it.

*Environment note:* pip ≥24.2 verifies TLS through the macOS keychain, which
this sandbox denies (`OSStatus -26276`), while plain OpenSSL + certifi
through the same proxy works. pip falls back to certifi when
`pip._vendor.truststore` cannot be imported, so the install ran through a
three-line wrapper that blocks that import. Nothing in the repo changed —
only how pip verifies.

### The workflow audit, before the push

The excalidraw lesson. `cd.yml` carried
`SITE_URL: https://boilerplate.2plot.dev` **hard-coded**. Unguarded, the
inaugural push would have polled another site's `/healthz` for fifteen
minutes waiting for a commit it will never serve, failed, then run both live
batteries against it — a fork failing CD on day one over a host it does not
own. `ci.yml` still tagged its image `dash-docs-boilerplate:ci` and described
this repo as the template.

Everything touching a running host is now gated on the repository variable
`SITE_URL`, **with no hard-coded fallback** — an empty value *is* the signal
that no service exists, and a default would silently re-point the workflow at
someone else's host. Unguarding takes no workflow edit, twice: B3 sets the
variable to the `.onrender.com` URL, B5 changes it to the domain.

### The inaugural push, and its three failures

The first run in this repo's history went red in three places, all mine, none
catchable locally because **neither lint nor the older-Dash matrix leg had
ever run here**:

- **flake8, 8 findings** — seven unused imports and a blank-line count,
  almost all orphaned by edits earlier in this same phase.
- **dash 4.4.0, both backends** — `test_the_nonce_mask_is_sound`, the control
  for every byte-identical assertion in the geo file, asserted that two
  identical requests DIFFER. True on 4.4.1 (which stamps a per-request
  `end_id` nonce), false on 4.4.0. **A control test coupled to a Dash version
  fact.** Rewritten to assert the two properties that actually matter and
  hold on either version: the mask is sound (identical requests compare
  equal) and not over-broad (it must not equalise two *different* pages).

The CD guard worked on that same run: `deploy to render` and `verify the live
site` both skipped. Nothing was battered against a host this repo does not
own — which was the entire point of auditing before pushing rather than
after.

Verified on both Dash versions this time: **597 / 594 passed** on 4.4.0 and
4.4.1 alike, flake8 clean.

---

## 10. Production verification (2026-08-23)

llms.2plot.dev's service was repointed to this repo; the deploy replaced the
old flagship in place, so hub-row continuity is automatic.

### Confirmed

| Check | Result |
|---|---|
| Deploy fingerprint | `/healthz` `build` == HEAD, `app: llms` |
| dimll in production | **2.7.1** (read from installed metadata, not prose) |
| Clerk / auth wiring | both halves — `POST /api/auth/session` → `401 {"authenticated":false}`, **not** the 405 that signals `register()` without `configure_app()` |
| Store persistence | "Not persistent" banner **gone**; store resolves to `/var/data/policy_overrides.json` |
| Both batteries vs the domain | network_smoke 9/9; smoke_live 89/90 — the single warning is a PEER host serving HTML at its llms.txt, scoped by the script as "not this deployment" |
| Showcases, human + crawler | all three: 200, exactly one `<h1>`, real prose, no stub, on both lanes |
| Map click → write | Antarctica clicked → `AQ` → toggled → painted red, badge, store written |
| Un-deny → recovery | `AQ is allowed again`; denylist back to the owner's six |
| Hub row | `llms.2plot.dev — 55 bot hits · 12 unique crawlers/day · reported 10m ago`, alongside peers at 2–27m. **No gap**, reporter ACTIVE |

### The geo investigation — a false alarm, and what it cost to prove

Every request to a denied country returned **200**, on the domain *and* on the
Render origin. That looked like the guardrail failing in production while the
board and the public showcase both showed countries denied.

It was not. **Render fronts `*.onrender.com` with Cloudflare too** (`server:
cloudflare`, `cf-ray` on the origin), so on *both* hostnames Cloudflare
overwrites a client-supplied `CF-IPCountry` with the true client country. My
spoof never reached the app. Every 200 was the correct answer for a US
visitor against a denylist that does not contain US.

That is the documented trust model holding — and holding *better* than
documented: GEO.md warns that a client reaching the origin directly can
spoof, and on this platform there is no direct-to-origin path to reach.

**What made it diagnosable was making it observable.** Ruling this out from
outside took: the public showcase (store readable), ClaudeBot → 403
(middleware running), the `text/plain` ramp (headers arriving), and a local
replay of the exact production store on the exact deployed commit (451). None
of those is the actual question, which is *"what country does this request
resolve to?"* — the check GEO.md calls mandatory and points at the
token-gated operator panel for. On a host where nobody has that token, the
mandatory check is unavailable.

So `/healthz` now carries it: `geo: {configured, denied, resolved}`. Counts
and a resolution trace, never the country codes.

### Two inherited defects found while adding that

1. **The health payload was a snapshot.** `register_health_route` computed it
   once at registration and closed over the dict. Harmless while every field
   was static — and the route is registered ~150 lines before `configure_geo`
   runs, so the first version of this diagnostic reported the guardrail
   UNCONFIGURED on a host where it is configured. The diagnostic lying in
   exactly the situation it exists for. Now built per request.

2. **FastAPI had its own payload.** `lib/asgi_routes.py` constructed
   `HealthResponse` independently and never called `health_payload`, so a
   FastAPI deployment silently lacked `build` — and `cd.yml`'s build-match
   wait polls for precisely that field. It would have fallen into the
   "predates the build field" path forever, verifying whichever release
   happened to be serving: the muicharts defect that wait exists to prevent,
   reintroduced per-backend. Both backends now render from one function.

### Still unproven, and why

The 451 itself has **not** been observed on production. Proving it requires a
request that Cloudflare labels with a denied country — which, since spoofing
is impossible here, means denying the country the tester is actually in. That
is a deliberate brief outage for real visitors and is the owner's call, not
a verification pass's.

Everything either side of it is proven: the store writes, the config reads it
(`denied: 6`), the resolution works (`US (via cf-ipcountry)`), and the exact
production store on the exact deployed commit answers 451 locally across all
ten surface classes.

### Dependabot

Five floor-raise PRs closed with reasons, none rebased or merged — the change
itself was the problem, not its base. `.github/dependabot.yml` now restricts
pip **version**-updates to `dash*`/`plotly*`/`markdown2dash`, mirroring
dash-documentation-boilerplate `ab22fd7` (a commit this fork's first push
prompted). Security updates are unaffected — separate channel. PRs #1 (base
image 3.11.8 → 3.14.7) and #2 (actions group) are different ecosystems, are
real decisions, and stay open.

---

## 11. Template sync — fence-aware source expansion (2026-08-23)

Ported from `dash-documentation-boilerplate` 1.6.11 (`30075d0`): the
fence-aware `_expand_source_directives` in `pages/markdown.py`, the
every-page single-h1 / deduped-footer pin, and the fence unit test.

**The upstream bug.** `_expand_source_directives` was a plain regex `sub`
over the whole document, so a `.. source::` written *inside* a fenced block
to TEACH the directive was expanded like a real one. The expansion injects
its own ```` ```python ```` fence, which closes the already-open fence early
— everything after it renders as markdown, and every `# comment` line in the
inlined file becomes an `<h1>`. Five h1s on the template's tutorial page,
machine lane only: markdown2dash parses fences properly, so the browser lane
was always correct and nothing looked wrong to a human. The expander is now
a line walker that tracks the open fence marker (``` and ~~~ both) and
expands only at fence depth zero.

**Prevention here, not a fix.** This fork has exactly one `.. source::` —
`docs/reference_geo/geo.md:117`, inlining `lib/policy_store.py`, at top
level. No page here teaches the directive inside a fence today. The port is
for the day one does; the pin is what would catch it.

**The sweep found no drift.** It ran over all 11 non-admin pages — every one
serves exactly one `<h1>` to a generic client and a footer whose llms.txt
links are distinct, with `/` carrying the root link once. The same sweep
caught real content drift on two other forks (leaflet, muicharts), so the
clean result here is a measurement, not an assumption.

One adaptation: the template's pin skips `/admin/*` inline. This repo's
`pages` fixture already drops it — the control board fails closed to
anonymous renders and `tests/test_control_board.py` owns its assertions — so
the guard would be dead code, and the docstring says where the exclusion
actually lives.

Also refreshed the prerender-lane test's floor wording: it still named 2.6.1
as "the floor", which has been >=2.7.1 since Phase B.

**602 passed / 1 skipped (flask), 599 passed / 4 skipped (fastapi)**,
flake8 clean.

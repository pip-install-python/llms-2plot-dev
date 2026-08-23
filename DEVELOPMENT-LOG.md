# DEVELOPMENT-LOG.md — llms-2plot-dev, phase 1

**Written:** 2026-08-22 · **Repo:** `llms-2plot-dev` · **Branch:** `main`,
origin unset · **17 commits** on top of the fork · 94 files changed.

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

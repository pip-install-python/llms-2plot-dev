# PHASE1-REPORT.md — llms-2plot-dev, phase 1

**Date:** 2026-08-22 · **Repo:** `/Users/pip/PycharmProjects/llms-2plot-dev`
· **Branch:** `main`, 11 commits on top of the fork · **Origin:** unset,
deliberately · **Posture:** development only — nothing pushed, nothing
deployed, no hub reporting, no PyPI floor change.

Companion document: **[BUGS-2.7.0.md](BUGS-2.7.0.md)** — the soak's findings,
which gate the `v2.7.0` tag push. Read that one first if you are deciding
whether to ship the package.

---

## Hard rules — compliance

| Rule | Status |
|---|---|
| No `git push` | **Held.** `git remote -v` is empty; `origin` was removed immediately after cloning |
| No deploys | **Held.** Nothing left this machine |
| No hub reporting | **Held.** No `CROSS_APP_*` secrets set; every boot prints `[satellite-traffic] disabled` |
| No PyPI floor change for 2.7.0 | **Held.** `requirements.txt` still pins `>=2.6.1`; the 2.7.0 code paths are capability-guarded so the app still boots on the pin |
| Commit locally as you go | **Held.** 11 commits, full boilerplate history preserved (102 total) |

The fork was created with `git clone` from the local boilerplate, so all 91
upstream commits came with it — wave syncs remain a fast-forward. `origin`
was then removed rather than left pointing anywhere.

---

## STEP 0 — the baseline, and the gate it produced

| Stage | Flask | FastAPI |
|---|---|---|
| Inherited suite on **2.6.1** | 322 passed | 319 passed, 3 skipped |
| Same suite on **2.7.0**, zero knobs | 322 passed | 319 passed, 3 skipped |
| Same suite on **2.7.0**, seam fully live | 322 passed | 319 passed, 3 skipped |

The third row is the strong form of the byte-identical-when-unset claim, and
it is stronger than the charter asked for: this host calls `configure_geo()`
unconditionally with a callable denylist, registers the operator panel, and
attaches a callable `vendor_policy` — all against an empty store — and 322
inherited assertions do not move.

**One environment deviation, stated plainly.** The sandbox this session runs
in has no network, so `pip install -r requirements.txt` could not reach PyPI.
The 2.6.1 baseline environment was mirrored from the boilerplate's own
resolved venv (Python 3.11.8, `dash-improve-my-llms` 2.6.1, `dash` 4.4.1,
the vendored `dash-clerk-auth` 1.0.5 — the exact set `requirements.txt`
resolves to) rather than re-resolved from the index. The 2.7.0 wheel was then
force-installed over it exactly as specified. This changes nothing about what
was tested; it means the *resolution* step was not re-proved here, and a
clean `pip install -r requirements.txt` should be run once on a networked
machine before B3 staging.

---

## The soak — charter coverage

Every finding reproduced on **both** backends. Full detail in BUGS-2.7.0.md.

| # | Item | Result |
|---|---|---|
| 1 | Byte-identical when unset | PASS |
| 2 | Geo: surfaces, exemptions, unknown, the seam | PASS · **1 defect** |
| 3 | Panel: gate, headers, anti-drift, resolution line | PASS · clean |
| 4 | W2 vendor policy: published vs served | **FAIL on one class** |
| 5 | Idempotency hardening | PASS — the fix works |
| 6 | W4 / W5 / W6 | PASS · clean |
| 7 | The site's own guards on 2.7.0 | PASS |

### The two defects

**#1 (HIGH).** A `deny_countries` callable returning a sequence with an
unhashable element — a dict, list or set — makes **every request on every
surface 500**. `geo.py:221` hashes the raw tuple outside the `try/except`
that catches callable failures. GEO.md promises the exact opposite: *"it can
never take down the request path."* Four-line fix suggested. This matters
beyond the immediate: 2.8's bot × country matrix arrives through this same
seam, and a newer worker writing a matrix-shaped value during a rolling
deploy is precisely this shape.

**#2 (HIGH).** A per-vendor `block` on a **traditional** crawler (googlebot,
bingbot, slurp, duckduckbot) is enforced by the middleware but never
published in `robots.txt` — `User-agent: *  Allow: /` keeps inviting a
crawler the origin 403s. `robots_generator.py:150` excludes the traditional
class from the blocked section and `:196` renders it only under
`allow_traditional=False`. Contradicts W2's "one fold drives robots.txt AND
the middleware". The failure is silent and SEO-severe, and per-vendor
overrides are exactly what a control board writes — including this site's.

Both are pinned as `xfail(strict=True)`, so they fail loudly the day the
package fixes them and the markers have to come out. Two smaller GEO.md
statements the code contradicts are recorded as #3 and #4; in both cases the
code is the better behaviour and the doc should move.

---

## What is built

### B1 — identity (complete)

`SITE_BRAND` / `SITE_DESCRIPTION` / `SITE_SHORT_NAME`, `DEFAULT_BASE_URL` →
`https://llms.2plot.dev`, the social-card object, `SAME_AS` as the
docs↔GitHub↔PyPI triangle, `APP_VERSION` reset to 1.0.0. The fork point in
`run.py` (`setdefault("SATELLITE_APP_KEY", "llms")`) — the hub-row key the
runbook's continuity invariant is written against. `templates/index.html`:
brand ×6, origin ×9, keywords, installed-app title, the JSON-LD block, and a
noscript feature list describing this package. `pages/home.md` rewritten (it
is `/llms.txt`'s opening prose). Favicons regenerated from the hook mark via
the inherited `scripts/make_favicons.py`; `site.webmanifest` edited by hand
as that script instructs. `llms.2plot.dev` was already in
`network_directory.PEERS` — **verified, not added**.

One inherited test was silently broken by the rename and is now fixed at the
source: `test_smoke_live`'s foreign-canonical check spelled
`boilerplate.2plot.dev` literally, so on any fork it rewrote nothing and
passed as a no-op. It reads `BASE_URL` from constants now.

### B1a — the identity rebuild (owner-directed, 2026-08-22)

B1 changed the identity *strings*; a review found the site was still the
template underneath. Three problems, in increasing order of consequence:

- the header served `ddb.png` beside the literal wordmark **"Dash Docs"** and
  linked to the boilerplate's GitHub repo — the most visible surface on the
  site;
- the home page's hero was `intro_img.jpg`, the boilerplate's own screenshot;
- **eleven doc pages were byte-identical to the boilerplate's**, and
  `excluded_links` hid them only from the sidebar. They remained in
  `sitemap.xml`, `/llms.txt`, `/llms-full.txt`, the MCP resource set and the
  prerender — so llms.2plot.dev would have published
  dash-documentation-boilerplate's tutorials as its own documentation, on
  eleven URLs, competing with the site it was forked from.

**Owner decision: delete them, not hide them.** This overrides the migration
kickoff's `NEVER deleted (wave-sync purity)` rule, which is recorded here
because it has a running cost: template wave syncs touching `docs/` now
require manual resolution rather than fast-forwarding. That cost was accepted
in exchange for a site that stands on its own.

Deleted: `ai-integration`, `authentication`, `backend-comparison`, `backends`,
`data-visualization`, `directives`, `example`, `fastapi-showcase`,
`interactive-components`, `network-standard`, `networks`. `lib/directives/` —
the directive *implementations* — stays; only the pages teaching them went.

Rebranded: header logo → the hook mark, wordmark → `SITE_SHORT_NAME` (the
template hardcoded a string every fork then served), GitHub link →
`dash-improve-my-llms`, home hero → a rendered `assets/hero.png`, JSON-LD
organisation logo, and the social-card script's default artwork. Deleted
`ddb.png`, `dash_documentation_boilerplate.png`, `intro_img.*` and
`logo.svg`. README rewritten from 849 lines of the template's manual to this
repo's own. CHANGELOG gains this fork's 1.0.0 entry above the inherited
history.

**Verified:** no served surface — `/`, the reference pages, `/llms.txt`,
`/llms-full.txt`, `/robots.txt`, `/sitemap.xml`, or the crawler document —
carries "boilerplate", "Dash Docs", `ddb.png` or `intro_img`. The two
remaining mentions of `boilerplate.2plot.dev` are correct: it is a peer in
the cross-host network directory. `sitemap.xml` and `/llms.txt` list 11
pages, all this site's own.

### B2a — the Reference section (the gap the deletion exposed)

The site documented a package and had **no reference documentation for it** —
nothing on installing, `LLMSConfig`, `RobotsConfig`, `configure_seo`, access,
geo or the panel. Five pages now:

| Page | Covers |
|---|---|
| `/getting-started` | install, the one-line integration, where prose comes from, the checks to run |
| `/reference/configuration` | every `LLMSConfig` / `RobotsConfig` / `configure_seo` option |
| `/reference/access` | the four verdicts, the two axes, the 402 seam, the rate contract |
| `/reference/geo` | `configure_geo`, the trust model, and `lib/policy_store.py` inlined via `.. source::` |
| `/reference/panel` | the token gate, what it shows, and why it never writes |

Written against the installed 2.7.0 signatures rather than from memory, and
stating the consequences that are not obvious from a parameter name:
`block_ai_training=False` silently *allows* training rather than balancing it;
`rate_limit_per_minute` is per worker; `vendor_policy` keys are registry keys,
so a typo is a policy that does nothing.

Sixteen `301` redirects now — the deleted template paths point at their
nearest replacement rather than 404ing.

### B2 — pages, showcases, redirects (complete)

Three audience pages at their **byte-for-byte preserved** URLs:
`/audiences/mcp-clients`, `/audiences/web-crawlers`, `/audiences/llm-context`.

Three showcases, all exec-module hybrids driven by the package's own pure
functions rather than descriptions of them:

- **A — "What the crawler sees"** (`/audiences/web-crawlers`): page × UA
  dropdowns built from the vendor registry, then classification, vendor,
  class, effective policy, the prerendered document in an iframe and in
  view-source, and the headers — with the 403 shown for a blocked crawler
  before the document is ever built.
- **B — bot-policy sandbox** (`/showcase/robots-sandbox`): coarse flags plus
  a per-vendor override feeding `generate_robots_txt(config=...)` on a
  **throwaway** config. The no-mutation invariant has both a static test (no
  attribute named `_robots_config` is ever assigned) and a behavioural one
  (rendering the page does not change what `/robots.txt` serves).
- **C — policy panel** (`/showcase/policy-panel`): live tiers, vendor
  verdicts, and — real, because 2.7.0 is installed — a plotly choropleth of
  the denylist read from `lib/policy_store`, plus a simulator that walks a
  hypothetical request through the actual layer order.

Seven **301** redirects for retired URLs in `run.py`'s custom-routes slot,
mounted before `add_llms_routes` and registered per backend (verified on
both). Navigation grew "This package" and "Showcase" clusters ahead of the
inherited docs; the boilerplate's tutorial pages are hidden via
`excluded_links` and **never deleted** — they stay registered, crawlable and
reachable, which keeps every future wave sync a fast-forward.

### B7 — the writable control board (prototype complete)

`lib/policy_store.py` — flock-guarded JSON, validated on write, atomic via
`os.replace`, fail-open on every read failure, and re-stat'd on **every**
call rather than the template store's 1s throttle: the seam's promise is
"the next request", and a throttle downgrades that to "probably, within a
second". A page-visibility toggle can land a second late; a compliance block
cannot.

The inherited board is **extended**, not replaced — per the fleet addendum,
which superseded the migration doc's "port the leaflet pattern" (that pattern
was upstreamed into the template as 1.6.0 and hardened past leaflet's copy).
Same page, same gate, one more store. Click a country on the world map, press
the button, and the next request carrying that `CF-IPCountry` gets 451 on
every surface, in every worker, with no restart.

Deliberate calls worth carrying forward: a map click **selects**, the button
**commits** (a misclick on a world map is easy, and the action is taken
against every human and bot in a geography); every write callback re-checks
`is_admin_user()` server-side, with a test that invokes it directly as a
non-admin; invalid codes are refused **with a message** rather than dropped,
because the package reads anything that is not two ASCII letters as
"unknown" — a stored `XX` would look active and never match; and the store's
unrecognised keys survive a write, so 2.8's `deny_matrix` written by a newer
worker is not erased by an older one's toggle.

---

## Tests

| Suite | Tests |
|---|---|
| Inherited (retargeted at this site's pages) | ~300 |
| `test_geo_guardrail.py` | 77 + 4 xfail |
| `test_showcase.py` | 60 |
| `test_vendor_policy.py` | 29 + 4 xfail |
| `test_toll_gate.py` | 27 |
| `test_operator_panel.py` | 22 + 1 skip |
| `test_control_board_geo.py` | 21 |
| `test_prerender_idempotency.py` | 9 |
| **Total** | **563 passed / 1 skipped / 8 xfailed** (Flask) · **560 / 4 / 8** (FastAPI) |

The total fell from 587 after the template's docs were deleted — several
inherited suites are parametrized per markdown file. The suites that keyed on
specific template pages were **remapped individually**, not sed'd:
`/reference/configuration` for the heavily-formatted page,
`/reference/geo` for the `.. source::` expansion test, `/reference/panel` for
content negotiation. The `dv-banner` test survives because
`/reference/configuration` now documents the viewer's class names — and it
immediately caught that page writing the literal opening tag, which is the
exact confusion the test exists to prevent.

`scripts/audit_links.py`: **0 broken internal links** (was 3). The two
remaining flags are one inherited network peer unreachable from this
sandbox.

Two harness changes worth knowing about, both additive and both candidates
for upstreaming: `tests/conftest.py`'s client grew `headers=` and `post()` —
the guardrail reads `CF-IPCountry` and the panel reads `X-LLMS-Panel-Token`,
and neither fits the inherited two-argument client; and `pytest.ini`
registers a `slow` marker for the one test that boots the app in a
subprocess.

---

## Deferred, and why

**B3+ per the kickoff's own phasing** — not attempted, not started:

- GitHub repo creation, Render service, env groups A/B/C, the 1 GB disk.
- Staging on `.onrender.com`, `network_smoke` / `smoke_live` against a live
  host, the hub-row cutover.
- **The live browser pass of all three showcases as human and as crawler UA.**
  Partially compensated: every showcase callback is invoked directly by
  `test_showcase.py`, so a raising callback cannot hide behind a 200 — but
  nothing here has rendered in a real browser.
- The social card. `OG_IMAGE_URL` points at
  `cdn.2plot.ai/github_assets/llms.2plot.dev.png`, which **does not exist
  yet**. `scripts/make_social_card.py` renders it and the upload to the
  Cloudflare bucket is manual. Until that object is there, every share of
  this site unfurls without an image.
- `render.yaml` still carries the template's service name and no
  `POLICY_STORE_FILE` disk entry — deliberately, since the service does not
  exist and inventing its shape now would be guessing.

**Genuinely blocked on the package publishing:**

- The `requirements.txt` floor stays `>=2.6.1`. Every 2.7.0 call site is
  behind a `LLMS_HAS_27` **capability** probe (not a version compare, so a
  partial backport or a yanked release cannot make the guard lie), and
  `_llms_config_27()` filters kwargs against the real signature. When 2.7.0
  publishes, move the floor, raise `LLMS_PKG_FLOOR`, and the whole block
  collapses to a plain import.

  **This degrade is proved, not assumed.** An earlier draft of this report
  claimed the app still booted on the pinned floor; installing 2.6.1 and
  trying it showed otherwise — the three showcase modules imported the 2.7.0
  `vendors` registry at LAYOUT time, so the ImportError took down the whole
  app at boot rather than degrading one page. Fixed, and the claim is now
  backed by a run:

  | Installed | Flask | FastAPI |
  |---|---|---|
  | 2.6.1 (the pinned floor) | 401 passed, 195 skipped | 398 passed, 198 skipped |
  | 2.7.0 (the pre-release wheel) | 587 passed, 1 skipped, 8 xfailed | 584 passed, 4 skipped, 8 xfailed |

  On 2.6.1 the app boots, every page serves, and the two `[llms] WARNING`
  lines say exactly which features are not wired. The 2.7.0-only test modules
  carry `pytestmark = requires_dimll_27` — a capability probe matching
  run.py's — so they SKIP on the floor instead of failing. A red suite on the
  pinned floor would train everyone to ignore it.

**Deliberately not built:**

- The bot × country matrix. Recorded by the addendum as the first 2.8 item.
  The board's UI is shaped for it — the coarse country axis lives here now
  and the same map gains a per-vendor selector when `deny_matrix` lands —
  and the store already preserves keys it does not understand so a mixed-
  version rolling deploy cannot lose one.
- Any resurrection of the visitor dashboard. B1 retires `admin.py`,
  `analytics.py` and `ADMIN_DASH_TOKEN` with the old service; `/admin` and
  `/analytics` 301 to the control board and Showcase C respectively. The
  archived `KICKOFF-llms.md` addendum is superseded — recorded here so no
  later session rebuilds it.

---

## Recommended next steps

1. **Owner reads BUGS-2.7.0.md** and decides on #1 and #2.
2. Hook session fixes, rebuilds the wheel, and re-soaks here:
   `pip install --no-deps --force-reinstall <wheel>`, then `pytest` and
   `DASH_BACKEND=fastapi pytest`. The eight strict xfails turn into
   XPASS-failures the moment the fixes land — that is the signal — after
   which the markers come out and the tests stay.
3. `git push origin main v2.7.0` → PyPI.
4. Here: floor to `>=2.7.0`, raise `LLMS_PKG_FLOOR`, collapse the capability
   block, and run a clean `pip install -r requirements.txt` on a networked
   machine.
5. Then B3: GitHub repo, Render service (Starter, 1 GB disk, groups B/C +
   identity vars, **group A unlinked** — the `[satellite-traffic] disabled`
   boot line is the staging-posture proof), social card rendered and
   uploaded, and the live browser pass.
6. B5 cutover per the amended runbook: suspend/unlink the old service first,
   then link group A on the new one, then move the domain. The presence
   beacon makes the hub row's continuity visible within ~100s.

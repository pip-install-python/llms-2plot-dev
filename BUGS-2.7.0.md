# BUGS-2.7.0.md — the pre-release soak report

**Soaked:** 2026-08-22 · **Package:** `dash_improve_my_llms-2.7.0-py3-none-any.whl`
(local pre-release artifact, tag `v2.7.0` unpushed) · **Host:**
`llms-2plot-dev` (fork of `dash-documentation-boilerplate` 1.6.7, the future
llms.2plot.dev) · **Backends:** Flask and FastAPI, every finding reproduced on
both.

**This file gates the `v2.7.0` tag push.** Two findings are real defects and
one of them is an availability bug; two more are documentation statements the
implementation contradicts. Nothing here blocks the release architecturally —
the seam works, the panel works, the guardrail covers every surface — but #1
should not ship as it stands.

## What the soak was

The package's own 600-test suite proves 2.7.0 against itself. This soak proves
the thing that suite structurally cannot: the **callable seam driven by a real
control board on a real boilerplate app**, across both backends, with the whole
inherited site suite asserting nothing regressed.

Method: fork the boilerplate, install its pinned `dash-improve-my-llms` 2.6.1
from the existing fleet environment, run the inherited suite GREEN as a
baseline, then force-install the local 2.7.0 wheel over it and re-run.
Afterwards, wire the 2.7.0 surface the way a production satellite actually
would — `configure_geo(deny_countries=<callable>)`, `panel=True`,
`RobotsConfig(vendor_policy=<callable>)` — and attack it.

### Charter coverage

| # | Item | Verdict |
|---|---|---|
| 1 | Byte-identical when unset | **PASS** — see below |
| 2 | Geo: every surface class, exemptions, unknown, the seam | **PASS**, 1 defect (#1) |
| 3 | Panel: gate, headers, anti-drift, resolution line | **PASS**, no defects |
| 4 | W2 vendor policy: published vs served | **FAIL** on one class (#2) |
| 5 | Idempotency hardening | **PASS** — the fix works |
| 6 | W4 / W5 / W6 | **PASS**, no defects |
| 7 | The site's own guards on 2.7.0 | **PASS** |

### Charter #1 — byte-identical when unset, in its strongest form

| Stage | Flask | FastAPI |
|---|---|---|
| Inherited suite on 2.6.1 (baseline) | 322 passed | 319 passed, 3 skipped |
| Same suite on 2.7.0, zero knobs configured | 322 passed | 319 passed, 3 skipped |
| Same suite on 2.7.0 **with the seam live** | 322 passed | 319 passed, 3 skipped |

The third row is the one worth having. This host calls `configure_geo()`
unconditionally with a callable denylist, registers the panel, and attaches a
callable `vendor_policy` — against an empty store. 322 inherited assertions,
including the generic-UA prerender test and the llms.txt/tier surfaces, are
unmoved. An empty denylist really is a strict no-op.

Final suite after the soak's own tests were added: **486 passed / 1 skipped /
8 xfailed** (Flask), **483 passed / 4 skipped / 8 xfailed** (FastAPI). The
eight xfails are #1 and #2 below, pinned `strict=True` so they fail loudly the
day the package fixes them and the markers have to come out.

---

## #1 — HIGH — a `deny_countries` callable returning an unhashable entry 500s every request

**Contradicts a documented guarantee.** `docs/GEO.md`: *"a raising callable or
a malformed entry is logged once and treated as an empty denylist
(fail-open); **it can never take down the request path**."* It can.

### Location

`dash_improve_my_llms/geo.py:221`, in `_deny_set()`:

```python
def _deny_set() -> Tuple[str, ...]:
    if _config.deny_callable is None:
        return _config.deny_static
    try:
        raw = tuple(_config.deny_callable())
    except Exception:
        _warn_once("deny_countries callable raised; treating denylist as empty (fail-open)")
        logger.debug("geo denylist callable failure", exc_info=True)
        return ()
    cached = _callable_cache.get(raw)      # <-- line 221, OUTSIDE the try
    ...
```

`tuple(...)` succeeds for a list containing a dict, so the `except` never
fires. `_callable_cache.get(raw)` then hashes the tuple, raises
`TypeError: unhashable type: 'dict'`, and that escapes `_deny_set()` →
`gate()` → `handle_bot_request()` → the adapter's `before_request` hook.

### Repro

```python
from dash_improve_my_llms import configure_geo

# Any nested object in the returned sequence. A dict, a list, or a set.
configure_geo(deny_countries=lambda: [{"code": "RU"}])
```

Then fetch anything at all:

```
GET /                     -> 500
GET /llms.txt             -> 500
GET /robots.txt           -> 500
GET /assets/main.css      -> 500
GET /healthz              -> 200   (exempt paths return before _deny_set)
```

**Expected:** every one of those answers exactly as if the denylist were
empty — the callable is malformed, so nobody is blocked, and one warning is
logged.
**Actual:** `TypeError: unhashable type: 'dict'` out of the middleware; the
whole site 500s for every visitor in every country, not just for the denied
one. Confirmed identically on Flask and FastAPI.

Shapes that trigger it: `[{"code": "RU"}]`, `[["RU"]]`, `[{"RU"}]`, and
`["RU", {"x": 1}]` — note the last: a *valid* entry plus one nested object is
still a total outage.

### Why it is reachable

The store behind this seam is JSON on a mounted disk, written by a control
board. Three ordinary paths produce a nested object in that list:

1. a hand-edit during an incident (`{"geo_deny": [{"code": "RU"}]}` is the
   shape someone reaches for when they want to add a note);
2. a schema change in a site's own store;
3. **2.8's bot × country matrix.** The addendum records `deny_matrix` arriving
   through this same seam. A newer worker writing a matrix-shaped value that
   an older worker's `geo_deny()` returns verbatim is exactly this bug, and it
   would land during a rolling deploy.

This satellite's `lib/policy_store.py` sanitizes before persisting, so the
site itself is not exposed — but the package's contract is that it does not
have to.

### Suggested fix

Move the cache lookup inside the `try`, or normalize before caching. The
minimal change:

```python
    try:
        raw = tuple(_config.deny_callable())
        cached = _callable_cache.get(raw)
        if cached is None:
            cached = _normalize_codes(raw, strict=False)
            _callable_cache.clear()
            _callable_cache[raw] = cached
        return cached
    except Exception:
        _warn_once("deny_countries callable raised; treating denylist as empty (fail-open)")
        logger.debug("geo denylist callable failure", exc_info=True)
        return ()
```

`_normalize_codes` already does `str(entry)`, so it copes with nested objects
once it is reached; only the hash on the way to it is fatal.

### Pinned by

`tests/test_geo_guardrail.py::test_an_unhashable_entry_fails_open`
(4 parametrized cases, `xfail(strict=True)`).

---

## #2 — HIGH — a per-vendor block on a *traditional* crawler is enforced but never published

**Contradicts the W2 contract.** CHANGELOG [2.7.0]: *"One fold
(`vendors.effective_policies`) drives robots.txt AND the middleware"* — so
what a site says and what it does *"holds by construction"*. For the
traditional class, under the default config, it does not.

### Location

`dash_improve_my_llms/robots_generator.py`:

```python
150:  blocked = [v for v in VENDORS if policies[v.key] == "block" and v.cls != "traditional"]
...
196:  if config.allow_traditional:
          # comment-only block: "# Googlebot, Bingbot, etc. - covered by *"
      else:
          # emits real Disallow groups, correctly consulting `policies`
```

Line 150 excludes traditional vendors from the AI-blocked section. Line 196
renders the traditional class **only** in the `allow_traditional=False`
branch. So with the default `allow_traditional=True` — this app's config, and
the fleet's — a per-vendor override on a traditional vendor is never rendered
at all, and `User-agent: *  Allow: /` continues to govern it.

### Repro

```python
app._robots_config = RobotsConfig(vendor_policy={"googlebot": "block"})
```

| Check | Result |
|---|---|
| `effective_policies(config)["googlebot"]` | `"block"` |
| `GET /` as Googlebot | **403** |
| `/robots.txt` group for `Googlebot` | **none emitted** |
| What `/robots.txt` therefore tells Googlebot | `Allow: /` (via `*`) |

Affects all four traditional vendors: **googlebot, bingbot, slurp,
duckduckbot**. Reproduced on Flask and FastAPI, and directly against
`generate_robots_txt()` with no app at all.

### It is specifically the per-vendor path

The coarse flag is fine, which is what isolates this:

```python
generate_robots_txt(..., config=RobotsConfig(allow_traditional=False))
# -> emits Disallow groups for Googlebot, Bingbot, Slurp, DuckDuckBot  (P4 works)

generate_robots_txt(..., config=RobotsConfig(vendor_policy={"googlebot": "block"}))
# -> emits no Googlebot group at all
```

The `else` branch even honours overrides correctly: with
`allow_traditional=False, vendor_policy={"googlebot": "allow"}` Googlebot
gets no Disallow while the other three do. Only the `if` branch ignores
`policies`.

### Why it matters

Per-vendor overrides are precisely what a control board writes — this
satellite's B7 board offers exactly this control. An operator blocking a
misbehaving traditional crawler gets a host that 403s Googlebot while its own
`robots.txt` says `Allow: /`. Googlebot keeps crawling because it was invited,
collects 403s on every page, and Search Console fills with errors — with the
site's published promise insisting nothing is wrong. The failure is
SEO-severe, silent, and points the operator at the wrong layer.

It is also the one drift the panel cannot reveal: the panel reads the fold,
so it agrees with the middleware and disagrees with the served bytes.

### Suggested fix

Have the `allow_traditional=True` branch consult `policies` the way the
`else` branch already does — emit `Disallow: /` for any traditional vendor
whose effective policy is `block`, and leave `allow`/`meter` covered by `*`.
Equivalently, drop the `v.cls != "traditional"` filter at line 150 and let
the blocked section carry them.

### A parsing note for whoever writes the upstream test

A robots.txt comparison that iterates `User-agent:` groups **cannot see this
bug**: the vendor has no group, so it is skipped. The check has to resolve
each vendor's verdict through the `*` fallback — a vendor with no group of
its own is not unregulated, it is governed by `*`. That is how this soak
found it, after a first version of the same test missed it.

### Pinned by

`tests/test_vendor_policy.py::test_a_traditional_vendor_block_is_published_as_well_as_enforced`
(4 parametrized cases, `xfail(strict=True)`), with
`test_the_traditional_block_really_is_enforced` and
`test_the_coarse_flag_path_publishes_traditional_blocks` holding the two
halves of the diagnosis in place.

---

## #3 — LOW (docs) — a malformed *entry* does not void the denylist

`docs/GEO.md`, "the reloadable seam":

> Callable failures degrade the safe way: a raising callable **or a malformed
> entry** is logged **once** and treated as an empty denylist (fail-open)

The implementation treats those two cases differently, and only the first
matches the sentence. `_normalize_codes(raw, strict=False)` (geo.py:85) skips
the bad entry with a warn-once and **keeps the valid ones**:

```python
configure_geo(deny_countries=lambda: ["RU", "XX", "nonsense"])
# GEO.md predicts: empty denylist, nobody blocked
# actual:          RU is blocked; XX and "nonsense" are skipped with a warning
```

The code's behaviour is the better one — voiding a whole compliance denylist
because one entry is stale would be a worse failure than honouring the valid
part. So **the doc is the half that should move**, not the code. Worth fixing
before the tag because it is a compliance surface: an operator reading GEO.md
and finding a stale entry in the store will predict that nobody is blocked,
and be wrong.

Pinned by `tests/test_geo_guardrail.py::test_a_malformed_entry_does_not_void_the_whole_list`
(asserting the code's behaviour, with the disagreement in the docstring).

## #4 — LOW (docs) — a raising `resolver=` falls back to headers, it does not go "unknown"

`docs/GEO.md`, "Resolution order":

> 1. Your `resolver(headers)`, if configured (exceptions → unknown, warned once).

`resolve_country` (geo.py:~250) sets `code = None` on the exception and then
falls through to the header loop — its own warning says so: *"resolver raised;
falling back to header resolution"*. So with a broken resolver and a real
`CF-IPCountry` present, the country still resolves and a denied country is
still blocked.

There is also an asymmetry worth a sentence in the docs: a resolver that
**raises** falls back to headers, while a resolver that **returns an invalid
value** returns `None` immediately and does *not* fall back.

Both behaviours are defensible; neither is what the doc says. Pinned by
`test_a_raising_resolver_falls_back_to_headers` and
`test_a_resolver_returning_garbage_does_not_fall_back`.

---

## What was hammered and found clean

Recorded so the next session does not re-derive it.

**Geo — every surface class 451s** for a denied country, with
`Cache-Control: no-store`: `/`, a docs page, `/assets/*`, `/llms.txt`,
`/llms-small.txt`, `/llms-full.txt`, per-page `llms.txt`, `/robots.txt`,
`/sitemap.xml`, `/favicon.ico`, **`POST /_dash-update-component`** (the SPA
navigation route), `/llms-policy`, `/admin/control-board`, `/_dash-layout`,
`/_dash-dependencies`, and unknown paths. Humans and bots alike.

**No bypass found.** Exempt paths match exactly and case-sensitively:
`/healthz` passes; `/healthz/`, `/healthz-evil`, `/healthz/anything`,
`/HEALTHZ`, `/Healthz`, `//healthz`, `/./healthz`, `/a/../healthz` and
`/healthz%20` all 451. `/healthz?x=1` passes and serves only the health JSON —
the query string is not part of the matched path, which is correct and leaks
no content.

**Geo resolution:** all five documented edge headers resolve; `CF-IPCountry`
wins the priority order; matching is case-insensitive on the value;
`XX`, `T1`, empty, `ZZZ`, `de-DE` and `??` are all "unknown"; the default
allows unknown and `unknown="deny"` blocks it while exempt paths still answer.

**The seam works.** A store write is picked up by the *next* request in the
same process with no restart, un-toggling recovers, and configuring *before*
the store is populated still works — so the denylist is genuinely read per
request rather than snapshotted at `configure_geo()` time. A raising callable
fails open and warns once across five requests. A corrupt store fails open
rather than locking the site to its last known denylist.

**Panel:** unset token → 404 for everyone; wrong token → 404 whose body names
neither the panel nor the package; empty token → 404; the token is genuinely
read per request (rotation kills the old value on the next fetch, deletion
revokes); `X-Robots-Tag: noindex, nofollow` and `Cache-Control: private,
no-store` on success; absent from robots.txt, sitemap.xml, the llms index and
`page_registry`; POST refused; a render mutates nothing. Geo runs *before* the
token gate, so a denied country gets 451 rather than a 404 that would leak the
ordering. The vendor table agrees with this host's served `robots.txt` in both
directions on the default config. `"this request resolved to: DE (via
cf-ipcountry)"` renders correctly end to end — the per-host check GEO.md
mandates works.

**Prerender idempotency (the fix):** planting `data-dimll-prerender` inside a
comment in this repo's real `templates/index.html`, booting `run.py` in a
fresh subprocess and fetching `/` still produces the prerender block — the
exact trap that silently disabled email and flows. Also verified with the
marker in a `<meta>` tag and a `<script>` body. A genuine second injection is
still a no-op, so the probe was not loosened into uselessness. The plant was
removed and a test asserts the file came back clean.

**W2 default posture:** ClaudeBot and GPTBot 403 on pages while `/llms.txt`,
`/llms-small.txt`, `/llms-full.txt` and per-page `llms.txt` all answer 200
with non-empty bodies — the flagged behaviour change, with its docs-open half
confirmed from the app side. Policy surfaces open to everyone; assets never
vendor-gated; AI-search and traditional crawlers untouched; `meter` renders
Allow and behaves as allow.

**W4:** unset never limits; over-ceiling bots get 429 with a numeric
`Retry-After` and `Cache-Control: no-store`; the body names the conduct rule;
humans and policy routes are never limited; buckets key on the edge-header
client IP so one noisy agent cannot lock out another; `0` and `None` both mean
off; and a limiter monkeypatched to raise fails open for ten consecutive
corpus fetches.

**W5:** genuinely dark. `metering_enabled()` is `False`, a `priced` verdict
resolves to `gated`, no surface answers 402. Guarded against passing for the
wrong reason: `PRICED` is absent from `_VERDICTS` (if it were added, the
degrade at `access.py:179` would become dead code and the seam would go live
silently), and turning metering on *does* make `PRICED` survive.

**W6:** the hub can tighten a vendor but cannot loosen one — not past a coarse
flag, not past a local per-vendor override — and can lower the rate ceiling or
impose one where none existed but cannot raise it. A bulletin that raises
changes nothing. Five address-shaped payloads (`pay_to`, `payto`, `pay-to`,
`wallet`, `recipient`, including one nested three levels deep) are each
refused whole, with a control proving ordinary bulletins carrying prices as
strings are still accepted.

**One design shape confirmed rather than reported as drift:** `Omgili` is one
vendor publishing two robots tokens (`Omgilibot`, `Omgili`) matched by the
single UA substring `omgili`. A naive one-row-per-`User-agent` comparison
reads that as panel/robots drift. `get_bot_vendor()` classifies every token
robots.txt publishes, so it is correct — but it is worth knowing before
someone "fixes" it.

---

## Recommendation

1. Fix **#1** — it is a total-outage path that contradicts an explicit
   guarantee, the change is four lines, and 2.8's matrix makes it more likely
   to be hit, not less.
2. Fix **#2** — the per-vendor path is what control boards write, and the
   failure is silent and SEO-severe. If it slips, it must be documented in
   `docs/` as a known limitation of `vendor_policy` on the traditional class,
   because the current CHANGELOG language promises the opposite.
3. Fix **#3** and **#4** in `docs/GEO.md` — one sentence each, and both are on
   the compliance surface where operators reason from the doc rather than the
   code.
4. Re-soak: rebuild the wheel, `pip install --no-deps --force-reinstall` it
   here, and run `pytest` plus `DASH_BACKEND=fastapi pytest`. The eight strict
   xfails become XPASS-failures the moment #1 and #2 are fixed, which is the
   signal the fixes landed; then delete the markers and keep the tests.

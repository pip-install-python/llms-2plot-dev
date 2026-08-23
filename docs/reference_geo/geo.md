---
name: Geo guardrail
description: configure_geo — opt-in 451 on every surface for whole geographies, the header trust model, the fail-open postures, and the callable seam a control board writes through.
endpoint: /reference/geo
package: geo
category: Reference
icon: tabler:world-cancel
lastmod: 2026-08-22
schema_type: TechArticle
---

.. llms_copy::Geo guardrail

.. toc::

### What it is

Opt-in denial of whole geographies. Every listed country receives **HTTP 451
Unavailable For Legal Reasons on every surface** — pages, client-side
navigation, assets, the `llms.txt` family, `sitemap.xml`, `robots.txt`, root
icon redirects — humans and bots alike. The application does not exist for
that geography.

Unconfigured is a **strict no-op**: with no `configure_geo()` call, or an
empty denylist, every response is byte-identical to a build without the
feature.

### And what it honestly is not

**A compliance guardrail and a uniform-response layer. Not a security
boundary.**

The country of a request comes from an edge header, and an edge header is
exactly as trustworthy as the edge in front of your origin. Behind
Cloudflare, `CF-IPCountry` is set by Cloudflare and client-supplied copies
are stripped — the header is reliable. A client that reaches your **origin
directly** — no proxy, or a leaked origin hostname — can spoof or omit any
header.

There is no trusted-proxy validation here, deliberately: half of one would
imply a promise the header model cannot keep.

If the block matters adversarially, enforce it **at the edge as well** (a
Cloudflare country WAF rule) and treat this as the layer that makes the
origin's answer uniform across every surface — which an edge rule alone
cannot do, because it does not know that `/_dash-update-component` carries
page navigation or that `/llms-full.txt` is the corpus.

### Verify your host before trusting it

Geo requires the host to be **edge-proxied** (or an app-side `resolver=`). A
DNS-only host with no proxy in front resolves every request "unknown" and,
under the default `unknown="allow"`, the feature ships **inert** —
configured, tested, and blocking nobody.

The live check is the [operator panel](/reference/panel)'s line:

> this request resolved to: `DE` (via `cf-ipcountry`)

If that says "unknown" for a request you *know* came through your edge, the
header is not being forwarded. Fix that before trusting a denylist.

### Usage

```python
from dash_improve_my_llms import configure_geo

configure_geo(deny_countries=["RU", "CN", "IR"])
```

Full signature:

```python
configure_geo(
    deny_countries=["RU"],   # or a zero-argument callable
    unknown="allow",         # "allow" (default) | "deny"
    resolver=None,           # (headers) -> "US" | None
    exempt_paths=("/healthz", "/health", "/livez", "/readyz"),
    body=None,               # override the one-line 451 body
    policy_url="",           # emitted as Link: rel="blocked-by" (RFC 7725)
)
```

### `deny_countries` — the reloadable seam

A **static sequence** is validated at config time — `ValueError` on anything
that is not an ISO 3166-1 alpha-2 code.

A **zero-argument callable** is evaluated on **every request**. This is the
seam a writable control board wires a persisted store through:

```python
# lib/policy_store.py
import json, pathlib

_STORE = pathlib.Path("/var/data/policy_overrides.json")

def geo_deny():
    try:
        return json.loads(_STORE.read_text()).get("geo_deny", [])
    except FileNotFoundError:
        return []

# run.py
configure_geo(deny_countries=geo_deny)
```

A store edit takes effect on the **next request in every worker** — no
restart, no redeploy. That is what dissolves the multi-worker problem: mutate
module state and you change one worker; mutate a file every worker re-reads
and you change all of them.

This site's [control board](/admin/control-board) does exactly this. Here is
the whole store it writes through — flock-guarded, validated on write, atomic
on replace, and fail-open on every read failure:

.. source::lib/policy_store.py

Two details in there are worth lifting out. It re-stats the file on **every**
call rather than throttling: the seam's promise is "the next request", and a
throttle downgrades that to "probably, within a second" — fine for a page
toggle, not for a compliance block. And it preserves keys it does not
understand, so a newer worker writing a shape an older one cannot read does
not lose that policy on the older worker's next write.

Callable failures degrade the safe way: a raising callable is logged **once**
and treated as an empty denylist (fail-open). It can never take down the
request path.

### `unknown` — the posture for unresolvable countries

`"allow"` is the default and deliberately fail-open. It keeps three real
traffic classes working on a geo-enabled host: platform health checks
(origin-internal, no country header), internal monitoring sweeps, and
direct-to-origin fetches.

`"deny"` is for operators whose edge guarantees the header on every real
request. Under it, health checks survive **only** via `exempt_paths` — so
confirm your platform's actual health path first.

There are **no User-Agent exemptions**, and there will not be. A UA is
trivially spoofable, so an "allow our monitoring bot" rule would be a hole,
not a feature.

### Resolution order

1. Your `resolver(headers)`, if configured. For apps with their own geo-IP
   database. **Never do network I/O in it** — this runs inside every request.
2. `CF-IPCountry` (Cloudflare)
3. `CloudFront-Viewer-Country` (AWS, when the distribution forwards it)
4. `X-Vercel-IP-Country` (Vercel)
5. `Fastly-Geo-Country`, then `X-Country-Code`

`XX` (Cloudflare's unknown), `T1` (Tor), empty, and anything that is not two
ASCII letters all mean **unknown**, not a country.

Network lookups are not supported and will not be. An IP-geolocation call in
the request path is a third-party dependency between your visitor and your
page.

### Exempt paths match EXACTLY

`/healthz` is exempt. `/healthz-evil`, `/healthz/`, `/healthz/anything` and
`/HEALTHZ` are **not** — a prefix match would be a bypass anyone could spell.

Without the exemption, a geo-enabled host would 451 its own platform health
check and be reported down.

### The 451 response

One line of `text/plain`, status 451, `Cache-Control: no-store`, plus
`Link: <policy_url>; rel="blocked-by"` when a policy URL is configured.

**`no-store` is load-bearing.** The response varies by country and **no
`Vary` token exists for edge geo headers** — a shared cache storing one
country's 451 would serve it to the world.

The corollary for *allowed* responses: origin `Vary` cannot express country
either, so if you cache at a CDN, cache-key on country there.

### Two accepted consequences

- **The discovery floor bends here, once.** `robots.txt`, `sitemap.xml` and
  the root `llms.txt` are otherwise public everywhere, always. Geo denial is
  a deliberate exception: compliance, not monetization. Do not cite it as
  precedent for gating those surfaces anywhere else.
- **A session established before the block 451s on its next navigation.** The
  pages-router POST is covered — that is the point. Total block means total.

### Watch it work

The **[policy panel](/showcase/policy-panel)** shows the live denylist as a
world map and simulates a request from any country against the real logic.

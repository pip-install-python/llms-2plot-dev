---
name: Access & tiers
description: Gate a page and its machine twin independently — the four verdicts, the two axes, the callable seam, and why the gate document is served instead of a 403.
endpoint: /reference/access
package: access
category: Reference
icon: tabler:lock-access
lastmod: 2026-08-22
schema_type: TechArticle
---

.. llms_copy::Access & tiers

.. toc::

### Two axes, not one

Gating documentation has a shape most auth systems get wrong. There are
**two** questions, and they have different answers:

1. **Who may read the interactive page?** — a browser question.
2. **Who may read its machine twin** (`/<page>/llms.txt`, the crawler
   document, the prerender)? — an agent question.

Collapse them into one and you get a site that either leaks gated content to
every crawler, or hides its documentation from the search engines that would
have sent it customers. The package keeps them separate.

### The four verdicts

`configure_access(check)` takes a callable that receives a path and returns
one of:

| Verdict | Meaning | What the machine surfaces get |
|---|---|---|
| `allow` | public | the prose |
| `gated` | needs an account | the **gate document** — a real page saying what is behind the gate and how to get in |
| `deny` | not for this reader | 404, unrevealing |
| `priced` | payable | with metering **off**, degrades to `gated` |

```python
from dash_improve_my_llms import configure_access

def check(path: str) -> str:
    if path.startswith("/internal/"):
        return "deny"
    if path.startswith("/premium/"):
        return "gated"
    return "allow"

configure_access(check)
```

The callable runs **per request**, so it can consult a session, a header, or
a store. It must not raise: an exception is caught, logged once per path, and
degrades to `gated` — the page's prose is withheld rather than published,
which is the safe direction for a broken auth callback.

### Why `gated` serves a document instead of a 403

A 403 to an agent is a dead end. It cannot sign in, and the person who can is
usually the one who pasted the URL. So a gated page's `llms.txt` serves a
**gate document** — the page's title and description, a statement that it is
gated, and the sign-in URL — rather than nothing.

```python
configure_access(
    check,
    gate_doc=lambda path: f"# {path}\n\nSign in at https://example.com/login\n",
    link_suffix=lambda: "?key=" + current_agent_key(),
)
```

`link_suffix` is the person→agent handoff: it appends a portable key to the
`llms.txt` URLs the site publishes, so a signed-in reader who copies a URL
into a chat window does not lose their entitlements at the boundary.

That behaviour is deliberate and worth stating plainly: **the gate document
publishes the existence and shape of a page, never its content.**

### `deny` versus `hidden`

```python
from dash_improve_my_llms import mark_hidden

mark_hidden("/admin/control-board")
```

`mark_hidden` is the static version and it **wins over everything** — an
application check cannot un-hide a page. It removes the path from
`sitemap.xml`, 404s its `llms.txt`, skips the MCP resource, and 404s crawler
requests on the page URL.

It is deliberately **absent from `robots.txt`**. A `Disallow: /admin` line
tells every crawler exactly where your admin surface is; the lesson is old
and keeps being relearned.

### Viewer identity

```python
from dash_improve_my_llms import configure_viewer_identity

configure_viewer_identity(lambda: {"name": "Ada", "signed_in": True})
```

A zero-argument callable returning the current viewer, used by the rendered
`llms.txt` viewer to show who is signed in. Returns `None` for anonymous.

### The 402 seam, and why it ships dark

`LLMSConfig(metering=False)` is the default, and with it a `priced` verdict
resolves to `gated`. Nothing is published and nothing is charged.

That is the whole safety property. A billing bug in a site's own `check()`
cannot accidentally publish an offer document or bill anyone, because the
priced lane does not exist until an operator turns it on deliberately:

```python
add_llms_routes(app, LLMSConfig(metering=True))
configure_access(check, offer_doc=..., payment_headers=...)
```

With metering **on**, a priced page serves an offer document at `402` across
every surface, stays listed in the index, and serves the offer at `200` with
`noindex` to the crawler column — so a crawler is never shown different
content than a payer would get, which is the anti-cloaking rule.

**The package never computes a price and never holds a pay-to address.** Both
belong to the application. A network bulletin carrying anything shaped like a
payment address is refused whole rather than sanitized: a fetched address is
a payment-redirection target.

### The rate contract

```python
add_llms_routes(app, LLMSConfig(rate_limit_per_minute=30))
```

Bot traffic over the ceiling on the **corpus routes** gets `429` with
`Retry-After`, keyed on the client IP from the edge headers.

Three exemptions, each for a reason:

- **Humans are never limited.** The stampede this exists for is an agent
  failure mode.
- **`/robots.txt` and `/sitemap.xml` are never limited.** RFC 9309 reads an
  unreadable `robots.txt` as "no rules at all", so limiting it deletes the
  very rules it announces.
- **It fails open on any error.** Refusing to serve documentation is strictly
  worse than serving too much of it — this is the one place the package's
  fail-closed instinct is wrong.

Per process: N gunicorn workers means N × the ceiling in aggregate. There is
no shared counter, because a limiter that needed Redis would be a dependency
in the request path.

### Tiers from the network

If you run a family of sites behind a hub, the hub's bulletin can tighten a
page's tier network-wide. It can only ever **tighten** — a hub can close a
page a site left open, never open one a site chose to close.

### See it resolve

The **[policy panel](/showcase/policy-panel)** has a simulator: pick a page,
an audience and a country, and it walks the request through the real layer
order in-process — geo, then assets, then vendor policy, then the rate
contract, then the tier.

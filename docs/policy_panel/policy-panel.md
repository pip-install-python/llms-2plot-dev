---
name: Policy Panel
description: This host's live effective policy — tiers, vendor verdicts, the hub ceiling, and the country guardrail as a world map — plus a simulator that resolves a hypothetical request through the real in-process logic.
endpoint: /showcase/policy-panel
package: policy-panel
category: Showcase
icon: tabler:shield-lock
lastmod: 2026-08-22
schema_type: TechArticle
---

.. llms_copy::Policy Panel

.. toc::

### Showcase C — the policy panel

Every layer this package adds makes a decision about a request. Individually
each is simple; stacked, "why did that visitor get a 451 rather than a
sign-in card?" becomes a question nobody can answer from the code.

This panel answers it for **this host, right now**.

.. exec::docs.policy_panel.policy_panel

### The order the layers run in

The simulator above walks them in the order the middleware does, and the
order is load-bearing:

1. **Geo.** First, before everything — before the asset short-circuit (which
   would wave through `/assets/*` and the `POST /_dash-update-component` that
   carries client-side navigation) and before the bot gate (which would exempt
   humans). "451 on all surfaces" is one enforcement point with nothing to
   drift.
2. **Assets.** Static files are not policy-gated.
3. **Vendor policy.** Bots only. Humans are never subject to it.
4. **Rate contract.** Bot traffic on the corpus routes, over the ceiling.
5. **Page tier.** `public` / `auth` / `admin` / `hidden`, with the control
   board's override winning over frontmatter, and the hub's ceiling applying
   on top of both.

### The map is read-only. The board is not.

The choropleth reflects `lib/policy_store.geo_deny()` — the **same callable**
`configure_geo()` reads on every request:

```python
# run.py
configure_geo(deny_countries=policy_store.geo_deny)
```

That is the 2.7.0 seam, and it is the whole reason this site can have a
control board at all. The package's own operator panel (`/llms-policy`, token-gated and 404 to
everyone without the token) is read-only by decision: package config is per-process module state, so under
N gunicorn workers a *mutating* panel would change one worker and lie on the
next refresh. Routing every write through a file the workers re-read per
request dissolves that problem — and that is what
[the control board](/admin/control-board) does.

### What "451 on every surface" means

For a denied country, all of these answer `451` with `Cache-Control:
no-store`:

`/` · any docs page · `/assets/*` · `POST /_dash-update-component` ·
`/llms.txt` · `/llms-small.txt` · `/llms-full.txt` · `/<page>/llms.txt` ·
`/robots.txt` · `/sitemap.xml` · `/favicon.ico` · the operator panel itself.

`no-store` is not decoration. The response varies by country and **no `Vary`
token exists for edge geo headers**, so a shared cache holding one country's
451 would serve it to the world.

Exempt paths — `/healthz`, `/health`, `/livez`, `/readyz` — match **exactly**.
`/healthz-evil` is blocked. Without the exemption, a geo-enabled host would
fail the hub's hourly health sweep and be reported down.

### It is a compliance guardrail, not a security boundary

The country comes from an edge header. Behind Cloudflare, `CF-IPCountry` is
set by Cloudflare and client-supplied copies are stripped, so it is
trustworthy. A client reaching the origin **directly** can say anything.

If a block matters adversarially, add the edge WAF rule as well and treat this
as the layer that makes the origin's answer *uniform* across every surface —
which an edge rule alone cannot do, because it does not know that
`/_dash-update-component` carries page navigation or that `/llms-full.txt` is
the corpus.

On a DNS-only host with no proxy in front, every request resolves "unknown",
and under the default `unknown="allow"` the feature ships **inert**. The live
per-host check is the operator panel's line — *"this request resolved to: DE
(via cf-ipcountry)"*. Verify it before trusting a denylist.

### The hub may only tighten

The network bulletin can make this host **more** restrictive — block a vendor,
lower the rate ceiling, tighten a page tier. It can never loosen one. A
compromised or misconfigured hub can refuse traffic; it cannot open a site
that chose to close.

A bulletin carrying anything shaped like a payment address is refused
**whole**, not sanitized: a fetched pay-to address is a payment-redirection
target, and a partially-accepted payload is the exploitable shape.

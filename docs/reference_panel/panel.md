---
name: Operator panel
description: A read-only, token-gated page showing the live effective policy of every surface the package governs — and why it displays but never writes.
endpoint: /reference/panel
package: panel
category: Reference
order: 5
icon: tabler:dashboard
lastmod: 2026-08-22
schema_type: TechArticle
---

.. llms_copy::Operator panel

.. toc::

### What it is

One token-gated route — default `/llms-policy` — rendering the **live
effective policy** of every surface the package governs. Opt-in:

```python
add_llms_routes(app, LLMSConfig(panel=True))
```

Token via `LLMSConfig(panel_token=...)` or the `DIMLL_PANEL_TOKEN`
environment variable. `panel=False` is the default and registers nothing —
the path falls through to your app exactly as before.

### What it shows

| Section | Source | The point |
|---|---|---|
| Identity | package version, base URL, page count | which build answered |
| Vendor policy | the **same fold** `robots.txt` renders from | it cannot drift from `robots.txt` |
| Bot policy flags | the attached `RobotsConfig`, or the defaults | says == does, even unconfigured |
| Tier documents | `LLMSConfig` | corpus posture |
| Access control | callback **qualnames only** | who gates, without running the gate |
| Geo guardrail | the policy **plus** "this request resolved to `DE` via `cf-ipcountry`" | the live per-host check |
| Rate limiting | `rate_limit_per_minute` | the ceiling in force |
| Network | directory, bulletin state, hub tightenings | what the hub has tightened |

Every section ends with the copy-paste call that would change it.

Two details worth knowing. The vendor table renders from
`vendors.effective_policies` — the identical function `robots.txt` renders
from — so the panel and your published policy are one statement rather than
two things to keep in sync. And the access section shows callback
**qualnames** and never invokes them: a request-scoped check must not run
outside a request.

### The gate

- Token compared with `hmac.compare_digest`.
- Transported via the **`X-LLMS-Panel-Token`** header (preferred) or
  `?token=` (convenient in a browser; **it lands in access logs**).
- The env var is read **per request** — rotate it and the old token dies on
  the next request, no redeploy.
- **Unset token ⇒ 404, unconditionally.** Production fails closed.
- **Wrong token ⇒ 404 with an unrevealing body.** The panel never advertises
  its own existence.
- Deliberately absent from `robots.txt` (a `Disallow` line publishes the
  path — the `/admin` lesson), from the sitemap, and from the llms index.
- Success carries `X-Robots-Tag: noindex, nofollow` and `Cache-Control:
  private, no-store`.
- The [geo guardrail](/reference/geo) 451s the panel too. Intended: "451 on
  everything" includes the operator standing in a denied country.

```bash
curl -s -H 'X-LLMS-Panel-Token: <token>' https://your-site.example/llms-policy
```

### Read-only, and why that is not timidity

Package configuration is **per-process module state**. Under gunicorn's N
workers, a panel that *mutated* config would change one worker and lie on the
next refresh — a nondeterministically lying control plane, which is worse
than no control plane. And a write-capable endpoint behind a single shared
token is a remote policy override.

So this panel displays and never writes.

The footer shows the serving worker's **pid and boot time**. Values that flip
between refreshes mean different workers booted with different code or env —
a deployment diagnostic, not a panel bug.

### The writable layer above it

Your site's own control board, wired through the **callable seams** the
panel's hints show:

```python
configure_geo(deny_countries=store.geo_deny)
RobotsConfig(vendor_policy=store.vendor_policy)
```

Both are read per request by every worker — which is exactly what dissolves
the multi-worker problem the read-only decision guards against. Mutate module
state and you change one worker; mutate a file every worker re-reads and you
change all of them.

This site runs that pattern: a flock-guarded JSON store on a mounted disk,
written by an admin-gated control board whose every
write callback re-checks the gate server-side, and read back through the
seams on every request.

The **[policy panel showcase](/showcase/policy-panel)** is the public,
read-only view of the same state — no token required, because it shows only
what this site already publishes about itself.

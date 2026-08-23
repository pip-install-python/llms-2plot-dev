---
name: Getting Started
description: Install dash-improve-my-llms and mount the whole machine-facing surface of your Dash app in one line — llms.txt, robots.txt, sitemap.xml, a crawler prerender and an MCP bridge.
endpoint: /getting-started
package: getting-started
category: Reference
icon: tabler:rocket
lastmod: 2026-08-22
schema_type: TechArticle
---

.. llms_copy::Getting Started

.. toc::

### Install

Pick the extra that matches your Dash backend:

```bash
pip install "dash-improve-my-llms[flask]"      # the default Dash server
pip install "dash-improve-my-llms[fastapi]"    # Dash 4.4+ FastAPI backend
pip install "dash-improve-my-llms[quart]"      # Dash 4.4+ Quart backend
pip install "dash-improve-my-llms[all]"        # all three
```

The package itself has **zero required dependencies** beyond the standard
library — the extras only pull in the web framework you already run. That is
deliberate: this sits in the request path of every page you serve, so it
brings nothing with it that could break.

Requires **Dash 4.1+**. MCP resource registration needs **Dash 4.3+**.

### The one line

```python
import dash
from dash_improve_my_llms import add_llms_routes, LLMSConfig

app = dash.Dash(__name__, use_pages=True)

# ... register your pages ...

add_llms_routes(app, LLMSConfig(warn_missing_llms_doc=True))
```

That single call mounts every machine-facing surface:

| Route | What it serves |
|---|---|
| `/llms.txt` | the index — every page, with descriptions and links |
| `/llms-small.txt` | a compact briefing for a limited context window |
| `/llms-full.txt` | the whole corpus in one fetch |
| `/<page>/llms.txt` | one page's prose, content-negotiated |
| `/robots.txt` | generated from the vendor registry |
| `/sitemap.xml` | with priority inferred from your page tree |
| `/favicon.ico` | claimed, so Dash's catch-all stops answering it with the app shell |

…plus the **prerender** — the fix for the empty `<div>` — and one **MCP
resource** per page.

`warn_missing_llms_doc=True` is worth keeping on: it prints a line at boot
for every page with no prose registered, which is the only way you find out
before a crawler does.

### Where prose comes from

Three ways, in the order you will reach for them.

**1. A module-level `LLMS_DOC` string.** The package finds it automatically.

```python
# pages/pricing.py
import dash

dash.register_page(__name__, path="/pricing")

LLMS_DOC = """
# Pricing

Three tiers. The free tier has no time limit and no card.
"""

layout = ...
```

No layout walking, no extraction heuristics, no second copy of your docs to
keep in sync with the first.

**2. `register_page_metadata()`** for anything that is not a Dash page — the
home page, a document assembled at boot, a pseudo-path:

```python
from dash_improve_my_llms import register_page_metadata

register_page_metadata(
    path="/",
    name="My Site — what it is",
    description="One sentence, used as the site tagline.",
    llms_doc=open("pages/home.md").read(),
    schema_type="SoftwareApplication",
)
```

**3. A markdown loader.** If your pages come from `.md` files, feed the
expanded body in at registration time — that is what this site does, which is
why `/<page>/llms.txt` here serves the *rendered* prose rather than the
source with directives still in it.

### Set your public origin

```python
app._base_url = "https://your-site.example"
```

This drives `<link rel="canonical">` on every page, the absolute URLs in
`sitemap.xml`, and the "this app" entry in `/llms.txt`. It is the single
highest-consequence value in the integration: leave it pointing at someone
else's host and you are telling Google your entire site is a duplicate of
theirs.

### Identity for the crawler document

Browsers get whatever your `index.html` declares. Crawlers get the
prerendered document — and until you say otherwise, that document has your
content signals and none of your identity. One call fixes every crawler
surface at once:

```python
from dash_improve_my_llms import configure_seo

configure_seo(
    icons=["/assets/favicon/favicon.ico", "/assets/favicon/favicon-32x32.png"],
    social_image="https://cdn.example/card.png",
    social_image_alt="My Site",
    publisher="My Company",
    same_as=["https://github.com/me/my-package",
             "https://pypi.org/project/my-package/"],
)
```

See [Configuration](/reference/configuration) for the full signature.

### Check it worked

```bash
# the index
curl -s https://your-site.example/llms.txt | head

# one page, as an agent sees it
curl -s https://your-site.example/pricing/llms.txt

# the same URL as a browser sees it
curl -s -H 'Accept: text/html' https://your-site.example/pricing/llms.txt | head -3

# and the thing that actually matters — is your prose in the initial HTML?
curl -s -A 'Googlebot/2.1' https://your-site.example/ | grep -c '<main>'
```

That last command returning `0` means a crawler is still getting a loading
spinner. Everything else in this documentation is downstream of it.

### Where to go next

- **[Configuration](/reference/configuration)** — every option on
  `LLMSConfig`, `RobotsConfig` and `configure_seo`.
- **[Access & tiers](/reference/access)** — gating pages and their machine
  twins.
- **[The geo guardrail](/reference/geo)** — 451 for whole geographies.
- **[The operator panel](/reference/panel)** — read-only live policy.
- **[What the crawler sees](/audiences/web-crawlers)** — run the handlers
  against a real page and watch the output change.

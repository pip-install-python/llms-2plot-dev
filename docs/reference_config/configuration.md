---
name: Configuration
description: Every option on LLMSConfig, RobotsConfig and configure_seo — what each one does, what it defaults to, and the ones with consequences that are not obvious from the name.
endpoint: /reference/configuration
package: configuration
category: Reference
icon: tabler:settings-code
lastmod: 2026-08-22
schema_type: TechArticle
---

.. llms_copy::Configuration

.. toc::

### `LLMSConfig` — the routes and the documents

Passed to `add_llms_routes(app, config)`. Every option is optional; the
defaults are what this site runs.

```python
LLMSConfig(
    enabled=True,
    warn_missing_llms_doc=True,
    register_mcp_resources=True,
    prerender=True,
    llms_nav=True,
    llms_viewer=True,
    llms_tiers=True,
    llms_full_max_bytes=4_000_000,
    rate_limit_per_minute=None,
    metering=False,
    panel=False,
    panel_path="/llms-policy",
    panel_token=None,
)
```

| Option | Default | What it does |
|---|---|---|
| `enabled` | `True` | Master switch. `False` registers nothing |
| `warn_missing_llms_doc` | `True` | Boot warning per page with no prose. Keep it on |
| `register_mcp_resources` | `True` | One MCP resource per page (Dash 4.3+) |
| `prerender` | `True` | The static-HTML injection. **The documented one-argument rollback** |
| `llms_nav` | `True` | Sibling-page links in the corpus documents |
| `llms_viewer` | `True` | The rendered view browsers get at an `llms.txt` URL |
| `llms_tiers` | `True` | Serve `/llms-small.txt` and `/llms-full.txt` |
| `llms_full_max_bytes` | `4000000` | Cap on the full corpus |
| `rate_limit_per_minute` | `None` | W4's ceiling. `None` = no limiting |
| `metering` | `False` | The 402 seam. Off, a `priced` verdict degrades to `gated` |
| `panel` | `False` | Register the operator panel |
| `panel_path` | `/llms-policy` | Where it lives |
| `panel_token` | `None` | Beats the `DIMLL_PANEL_TOKEN` env var |

#### The rendered viewer

`llms_viewer=True` is what makes an `llms.txt` URL useful to a **person**. An
agent asking for that URL gets Markdown; a browser gets the same document
rendered, behind a small header carrying the site's brand chip and the
network wordmark.

If you style it, the header's outer element carries the class `dv-banner`
and the wordmark carries `mk-wordmark`. Both are stable.

Note what a bare class name is *not*: the string `dv-banner` appearing in a
document is prose, not chrome — this paragraph is the proof. Anything
checking whether viewer chrome leaked into an agent's copy has to key on the
rendered element, not on the name, or documenting the viewer becomes
impossible. (Which is why this page states the names in words and never
writes the opening tag: doing so would make this very document read as
chrome to a naive check.)

The rendered view is `noindex` by design, so it never competes with the real
page in search results, and both variants send `Vary: Accept` so a CDN cannot
hand cached HTML to the next agent that asks.

#### Three with non-obvious consequences

**`prerender=False`** is the rollback if the injection ever fights your
template. It is also the switch that stops per-page `<title>` rewriting — so
your `index.html` must keep Dash's `{%title%}` placeholder, or every page
reverts to one identical title and nothing looks broken.

**`rate_limit_per_minute` is per process.** Under gunicorn with N workers the
effective ceiling is N × this number. There is no shared counter, deliberately
— a limiter that needed Redis would be a dependency in the request path.

**`panel=True` with no token is safe.** The panel 404s for everyone until a
token exists, and the token is read *per request*, so it can be rotated or
revoked live. Registering it only when a token happens to be set at boot
would mean turning it on costs a redeploy — which is when nobody does it.

### `RobotsConfig` — who may crawl

Assigned to `app._robots_config`, and read by both `robots.txt` **and** the
middleware.

```python
RobotsConfig(
    block_ai_training=True,
    allow_ai_search=True,
    allow_traditional=True,
    crawl_delay=None,
    custom_rules=None,
    disallowed_paths=None,
    block_ai_training_docs=False,
    vendor_policy=None,
    default_unknown_ai="allow",
)
```

| Option | Default | What it does |
|---|---|---|
| `block_ai_training` | `True` | GPTBot, ClaudeBot, CCBot, Google-Extended, … |
| `allow_ai_search` | `True` | Claude-User, ChatGPT-User, PerplexityBot, OAI-SearchBot |
| `allow_traditional` | `True` | Googlebot, Bingbot, Slurp, DuckDuckBot |
| `crawl_delay` | `None` | Seconds, rendered inside the `User-agent: *` group |
| `custom_rules` | `None` | Raw lines appended verbatim |
| `disallowed_paths` | `None` | Paths inside the `*` group |
| `block_ai_training_docs` | `False` | Close the corpus to blocked training crawlers |
| `vendor_policy` | `None` | Per vendor: `allow` / `block` / `meter`. Map **or callable** |
| `default_unknown_ai` | `"allow"` | Posture for an AI crawler not in the registry |

#### `block_ai_training=False` does not mean "balanced"

With it `False` the training bucket is **not emitted at all**, which silently
*allows* every training crawler. If you want a permissive posture, say so per
vendor rather than by deleting the group.

#### `block_ai_training_docs` is the one most people want to leave alone

Off by default, and that default is load-bearing: your documentation exists to
get the package used, and blocking a training crawler on your *pages* while
leaving `/llms.txt` open is a coherent bargain. Turning this on closes the
corpus too.

#### `vendor_policy` takes a callable

```python
app._robots_config = RobotsConfig(
    vendor_policy={"perplexitybot": "block", "gptbot": "meter"},
)
```

Keys are **registry keys** (lowercase — `gptbot`, `claudebot`, `googlebot`),
not display names. An unrecognised key is logged and ignored, so a typo is a
policy that silently does nothing.

Pass a **zero-argument callable** instead of a dict and it is evaluated on
every request — that is the seam a writable control board wires a persisted
store through:

```python
app._robots_config = RobotsConfig(vendor_policy=my_store.vendor_policy)
```

`meter` renders as `Allow` in `robots.txt` and behaves as allow until the
rate limiter consumes it — a `Disallow` would kill the funnel the meter
exists for.

Try every combination on the **[bot policy sandbox](/showcase/robots-sandbox)**.

### `configure_seo` — identity on the crawler document

```python
configure_seo(
    icons=None,
    social_image="",
    social_image_alt="",
    social_image_width="",
    social_image_height="",
    twitter_site="",
    twitter_card="summary_large_image",
    publisher="",
    logo="",
    same_as=None,
    root_icons=True,
)
```

`icons` accepts plain paths or dicts with `href` / `sizes` / `rel`:

```python
configure_seo(icons=[
    "/assets/favicon/favicon.ico",
    {"href": "/assets/favicon/favicon-32x32.png", "sizes": "32x32"},
    {"href": "/assets/favicon/apple-touch-icon.png",
     "rel": "apple-touch-icon", "sizes": "180x180"},
])
```

`root_icons=True` also claims `/favicon.ico` — Google's fallback — which
Dash's page catch-all would otherwise answer with the app shell.

`same_as` becomes JSON-LD `sameAs`. For a package's documentation site, list
the GitHub repo and the PyPI project: three properties pointing at each other
is the strongest available statement of which URL is a package's canonical
docs home.

**Declared image dimensions must match the file.** A size that disagrees is
worse than declaring none, because the platform reserves that box and crops
into it.

### Page-level helpers

```python
from dash_improve_my_llms import mark_hidden, mark_important, register_page_metadata

mark_hidden("/admin/control-board")
```

`mark_hidden` removes a path from `sitemap.xml`, 404s its `llms.txt`, skips
the MCP resource, and returns 404 to crawler requests on the page URL. It is
deliberately **not** added to `robots.txt`: a `Disallow` line publishes the
path it is trying to protect.

```python
register_page_metadata(
    path="/pricing",
    name="Pricing",
    description="Three tiers.",
    llms_doc="# Pricing\n\n...",
    title="My Site | Pricing",
    image_url="https://cdn.example/card.png",
    schema_type="TechArticle",
    lastmod="2026-08-22",
)
```

`lastmod` is emitted **verbatim** into the sitemap, and omitted entirely when
absent. Set it when the content genuinely changes; never script it from file
mtimes, which reset on every container build and re-invent the daily-lie
sitemap.

### The network directory

```python
from dash_improve_my_llms import register_network

register_network(
    name="My Network",
    hub_url="https://hub.example",
    peers=[{"name": "sibling", "url": "https://sibling.example"}],
)
```

Emits `<link rel="related">` tags, a `## Network` section in `/llms.txt`, and
followed links in the prerendered body — so an agent that lands on one site
can enumerate the rest.

### Everything else

- **[Access & tiers](/reference/access)** — `configure_access`,
  `configure_viewer_identity`, the four verdicts.
- **[The geo guardrail](/reference/geo)** — `configure_geo`.
- **[The operator panel](/reference/panel)** — the token gate and what it shows.

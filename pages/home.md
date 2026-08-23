# Dash Improve My LLMs — the AI and crawler surface for Dash apps

> **`dash-improve-my-llms` — the crawler, agent and SEO companion every Dash app mounts in one line.** By [Pip Install Python](https://2plot.dev).

A Dash app is a JavaScript shell. A crawler that fetches it gets an empty
`<div>`; an agent that reads it learns nothing; a search engine indexes a
loading spinner. This package closes that gap without asking you to change
how you write Dash.

---

## What it does

One call — `add_llms_routes(app)` — mounts the whole machine-facing surface:

| Surface | Who reads it |
|---|---|
| `/llms.txt`, `/llms-small.txt`, `/llms-full.txt` | agents pasted a URL, and the crawlers that follow it |
| `/<page>/llms.txt` | one page's prose, content-negotiated: Markdown for agents, rendered for browsers |
| `/robots.txt` | every crawler, generated from one vendor registry |
| `/sitemap.xml` | search engines, with priority inferred from your page tree |
| a static-HTML prerender | crawlers that do not run JavaScript — the actual fix for the empty `<div>` |
| an MCP resource per page | Claude, ChatGPT and any other MCP client, natively |

Installed here: **{{VERSION:dash-improve-my-llms}}** — this site reads the
number from the package that is actually serving it, never from prose.

---

## The three audiences

This site is organised the way the package is: by who is asking.

- **[MCP clients](/audiences/mcp-clients)** — an assistant that speaks MCP
  mounts your docs as a resource and reads them natively. No copying, no
  scraping, no context window spent on HTML.
- **[Web crawlers](/audiences/web-crawlers)** — Googlebot, ClaudeBot,
  GPTBot, PerplexityBot. Each gets a document rendered for it, under a
  policy you declare once and serve everywhere.
- **[Paste-to-chat](/audiences/llm-context)** — a person pastes your URL
  into a chat window. The assistant fetches prose, not a bundle.

---

## Control, not just discovery

Discovery is the floor. Since 2.7 the package is also the layer that decides
**who gets served at all**:

- **Per-vendor policy** — allow, block or meter each crawler by name. One
  fold drives `robots.txt` and the middleware, so what you publish and what
  you enforce cannot drift apart.
- **The country guardrail** — `configure_geo(deny_countries=[...])` answers
  451 on *every* surface for a listed country: pages, assets, the corpus,
  `robots.txt`, even the favicon. Compliance, uniformly applied.
- **The rate contract** — a stated ceiling on the corpus routes, enforced,
  failing open on any limiter error.
- **The operator panel** — a read-only, token-gated page showing the live
  effective policy of every surface, including which header resolved this
  request's country.

Each of those takes a **callable** as well as a static value, and the
callable is read per request. That is the seam this site's
[control board](/admin/control-board) writes through: flip a country on the
map, and the next request from it gets 451 — in every worker, with no
restart and no redeploy.

---

## Install

```bash
pip install dash-improve-my-llms[flask]      # or [fastapi], [quart], [all]
```

```python
import dash
from dash_improve_my_llms import add_llms_routes, LLMSConfig

app = dash.Dash(__name__, use_pages=True)

add_llms_routes(app, LLMSConfig(warn_missing_llms_doc=True))
```

That is the whole integration. Every page that defines a module-level
`LLMS_DOC` string is served verbatim at its own `llms.txt`; every page
without one is still indexed, still prerendered, still in the sitemap.

### Writing a page's prose

```python
# pages/pricing.py
LLMS_DOC = """
# Pricing

Three tiers. The free tier has no time limit.
"""
```

No layout walking, no extraction heuristics, no second copy of your docs to
keep in sync.

---

## Backends

Dash 4.1 made the server pluggable, and the package follows it: the same
surface under **Flask**, **FastAPI** and **Quart**, auto-detected. Nothing
in the list above is backend-specific, and the package's suite runs against
all three.

---

## Resources

- **PyPI**: [dash-improve-my-llms](https://pypi.org/project/dash-improve-my-llms/)
- **GitHub**: [pip-install-python/dash-improve-my-llms](https://github.com/pip-install-python/dash-improve-my-llms)
- **The network**: [2plot.dev](https://2plot.dev) indexes every component
  site that runs this package — including this one.
- **The live directory**: every peer site, and this host's own policy, on the [policy panel](/showcase/policy-panel)

### Community

- **GitHub**: [@pip-install-python](https://github.com/pip-install-python) ![GitHub](https://img.shields.io/github/followers/pip-install-python?style=social)
- **YouTube**: [2plot.ai](https://www.youtube.com/@2plotai?sub_confirmation=1) — build-alongs and component walkthroughs

---

## License

MIT License — see [LICENSE](https://github.com/pip-install-python/dash-improve-my-llms/blob/main/LICENSE) for details.

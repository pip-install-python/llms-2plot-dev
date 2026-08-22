---
name: MCP Clients
description: How an MCP-speaking assistant mounts this site's documentation as a resource and reads it natively — no scraping, no copying, no context window spent on HTML.
endpoint: /audiences/mcp-clients
package: mcp-clients
category: This package
icon: tabler:plug-connected
lastmod: 2026-08-22
schema_type: TechArticle
---

.. llms_copy::MCP Clients

.. toc::

### The audience

An **MCP client** is an assistant that speaks the Model Context Protocol —
Claude Desktop, an IDE extension, an agent framework. It does not browse. It
asks a server for *resources* and reads what comes back.

A Dash app has nothing to offer such a client by default. The HTML is a
loading shell, and the content only exists after React has run. So the client
either gets nothing, or burns a large fraction of its context window on
markup that carries none of your meaning.

`dash-improve-my-llms` closes that in one line. On Dash 4.3+, every page that
registers prose becomes an MCP resource automatically:

```python
add_llms_routes(app, LLMSConfig(register_mcp_resources=True))  # the default
```

### What a client sees

Pick a page and read exactly what this site hands an MCP client for it. The
list is this app's own live page registry — not a fixture.

.. exec::docs.mcp_clients.mcp_registry

### The three ways to give a page prose

**1. A module-level `LLMS_DOC` string.** The package picks it up
automatically. No layout walking, no extraction heuristics.

```python
# pages/pricing.py
LLMS_DOC = """
# Pricing

Three tiers. The free tier has no time limit.
"""
```

**2. Markdown-driven pages.** This site's docs are markdown files; the loader
expands the directives and registers the result, so `/<page>/llms.txt` serves
the *expanded* prose rather than the source.

**3. `register_page_metadata(...)`** for anything that is not a page — the
home page, a pseudo-path, a document assembled at boot.

### Content negotiation, and why `Vary` matters

`/<page>/llms.txt` serves the same URL two ways:

| Client | Sends | Gets |
|---|---|---|
| agent / MCP client | no `Accept: text/html` | the Markdown, byte for byte |
| browser | `Accept: text/html,…` | the rendered viewer |

`?raw=1` and `?format=html` force either side. Both variants send
**`Vary: Accept`**, which is what stops a CDN handing an agent the HTML it
cached for the last human.

### The tiered corpus

One page at a time is often not what an agent wants. Three documents cover
the other shapes:

| Document | For |
|---|---|
| `/llms.txt` | the index — every page, plus the cross-host network directory |
| `/llms-small.txt` | a compact briefing, when the full corpus is too much |
| `/llms-full.txt` | everything, in one fetch |

**Prefer one `/llms-full.txt` fetch over N per-page fetches.** That is not
politeness — since 2.7.0 it is the published rate contract, and the origin
answers `429` with a `Retry-After` when an agent ignores it.

### Verifying it works

```bash
# what an agent gets
curl -s https://llms.2plot.dev/audiences/mcp-clients/llms.txt | head

# what a browser gets from the same URL
curl -s -H 'Accept: text/html' https://llms.2plot.dev/audiences/mcp-clients/llms.txt | head
```

If the first command returns HTML, the negotiation is broken — that is the
one check worth putting in your deploy pipeline.

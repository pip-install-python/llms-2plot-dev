---
name: Web Crawlers
description: What Googlebot, ClaudeBot, GPTBot and PerplexityBot actually receive from this site — the policy verdict, the crawler document, and the headers, run in-process against the real page registry.
endpoint: /audiences/web-crawlers
package: crawler-view
category: This package
order: 2
icon: tabler:robot
lastmod: 2026-08-22
schema_type: TechArticle
---

.. llms_copy::Web Crawlers

.. toc::

### The problem, stated once

A Dash app ships an empty `<div>`. Everything a reader sees is assembled by
JavaScript afterwards. Google runs JavaScript — eventually, on a second pass,
budget permitting. **Most crawlers do not run it at all**, and neither do the
AI fetchers that decide whether your package gets cited.

So the document a crawler stores for your page is a loading spinner, and
nothing anywhere reports this. The page looks perfect to you.

### Showcase A — what the crawler sees

Pick a page and a User-Agent. The verdict, the document and the headers below
are produced by running the package's **own** pure handlers in this process
against this site's real page registry — not by a mock, and not by a
description of what they would do.

.. exec::docs.crawler_view.crawler_view

Three things worth trying:

- switch between **Chrome** and **ClaudeBot** on any page — the verdict flips
  to `block` and the crawler gets a 403 before the document is ever built;
- switch to **Googlebot** and open **View source** — that is the prerendered
  document, with real prose and real links, in the *initial* HTML;
- switch to **PerplexityBot** — allowed, because AI *search* citations are how
  people find a package, while AI *training* is a different bargain.

### The policy behind the verdict

One vendor registry drives both halves, so the site cannot say one thing and
do another:

| Class | Default | Why |
|---|---|---|
| AI training (GPTBot, ClaudeBot, CCBot, …) | **block** | robots.txt was the published promise; 2.7.0 made the middleware keep it |
| AI search (Claude-User, ChatGPT-User, PerplexityBot, …) | **allow** | citations send readers; that is the point of docs |
| Traditional (Googlebot, Bingbot, …) | **allow** | ordinary search |

```python
app._robots_config = RobotsConfig(
    block_ai_training=True,
    allow_ai_search=True,
    allow_traditional=True,
    crawl_delay=10,
)
```

Since 2.7.0 the coarse flags have a finer companion — `vendor_policy`, per
vendor, `allow` / `block` / `meter` — and it takes a **callable**, read on
every request. That is what the control board writes
through.

### The documentation surfaces stay open

Note what did *not* 403 above: `/llms.txt`, `/llms-small.txt`,
`/llms-full.txt` and every `/<page>/llms.txt` answer a blocked training
crawler with `200`. That is deliberate. The corpus exists to get the package
used, and an upgrade must not silently start refusing it.

`RobotsConfig(block_ai_training_docs=True)` closes that half if you want it
closed. It is opt-in on purpose.

### Live policy

This site's `robots.txt` and `sitemap.xml` are generated, never hand-written,
and are always open to everyone — including crawlers the site blocks
elsewhere. A crawler that cannot read the rules is a crawler that has no
rules:

- [`/robots.txt`](/robots.txt) — generated from the vendor registry
- [`/sitemap.xml`](/sitemap.xml) — with priority inferred from the page tree
- [`/llms.txt`](/llms.txt) — the index, plus the cross-host network directory

### Hidden pages

`mark_hidden("/admin/control-board")` removes a path from the sitemap, 404s
its `llms.txt`, skips the MCP resource, and returns 404 to crawler requests on
the page URL. It is **not** in `robots.txt` — a `Disallow` line publishes the
path it is trying to protect.

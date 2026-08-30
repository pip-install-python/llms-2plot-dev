---
name: Paste-to-Chat
description: What happens when a person pastes this site's URL into ChatGPT or Claude — and how to make sure the assistant fetches your prose instead of a JavaScript bundle.
endpoint: /audiences/llm-context
package: paste-to-chat
category: This package
order: 3
icon: tabler:message-2-code
lastmod: 2026-08-22
schema_type: TechArticle
---

.. llms_copy::Paste-to-Chat

.. toc::

### The audience

Not a crawler. Not an MCP client. **A person**, mid-conversation, who pastes
your documentation URL into a chat window and expects the assistant to read
it.

This is the most common way an AI system encounters a package's docs, and the
least designed-for. The assistant sends a fetcher — `ChatGPT-User`,
`Claude-User`, `Perplexity-User` — which is a *user-triggered* fetch, not a
crawl. It usually gets one request, it does not run JavaScript, and whatever
comes back is what your package's reputation is built from in that
conversation.

For a stock Dash app, what comes back is an empty `<div>`.

### The fix, in the order it applies

1. **The prerender.** The initial HTML carries the page's real prose and real
   links, so a single non-JS fetch is already useful.
2. **`/<page>/llms.txt`.** The same content as clean Markdown, at a URL a
   person can paste deliberately.
3. **The tiered corpus.** `/llms-full.txt` for "read all of it", one fetch.
4. **Vendor policy.** User-triggered fetchers are `search`-class and
   **allowed** by default, even on a site that blocks AI training. Blocking
   them would mean nobody could ask an assistant about your package.

### Try it

Copy any of these into a chat window:

```text
https://llms.2plot.dev/llms.txt
https://llms.2plot.dev/audiences/mcp-clients/llms.txt
https://llms.2plot.dev/llms-full.txt
```

Every documentation page on this site also has a **copy button** — the
`.. llms_copy::` directive at the top of each page — which puts that page's
Markdown on the clipboard directly. Sometimes the fastest path is not a URL at
all.

### Why the `?key=` suffix exists

A page can be gated. When it is, the interactive site asks for a sign-in — but
an assistant cannot sign in, and the person who *can* is right there in the
chat.

`/api/agent-key` turns a browser session into a portable `?key=` that a copied
`llms.txt` URL carries with it, so the handoff from person to agent does not
lose the person's entitlements. Until Clerk and the hub are configured the
route answers `204` and the whole mechanism is inert — public docs need none
of it.

### What an assistant should do, and what this site asks for

Since 2.7.0 the corpus documents carry an **"Access policy"** section stating
the terms in the document body, where an agent reading the corpus will
actually see them — the identity convention, the coordination point, and the
rate rule:

> Prefer **one** `/llms-full.txt` fetch over N per-page fetches.

That is enforced, not merely requested: over the ceiling the origin answers
`429` with `Retry-After`. Humans are never rate-limited, and neither are
`/robots.txt` and `/sitemap.xml` — a crawler that cannot read the rules is a
crawler with no rules.

### Checking your own site

```bash
# what an assistant's fetcher gets
curl -s -A 'ChatGPT-User/1.0' https://your-site.example/ | grep -c '<main>'

# 0 means your prose is not in the initial HTML
```

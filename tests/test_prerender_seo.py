"""The 2.7.0 pre-tag SEO batch — H1 dedup and the home-footer llms.txt link.

Two fixes from the 2026-08-23 SEO audit, pinned here because both are
invisible from inside the application: they change only the bytes a machine
receives, and the browser view is identical either way.

**Know which document you are asserting about.** This package serves two,
and the H1 fix landed on one of them:

* a **browser-like UA** gets the app shell with the universal prerender
  injected into `#react-entry-point` — `prerender.py`;
* a **declared crawler or any non-browser UA** gets a separate static
  document — `html_generator.generate_static_page_html`.

A test that fetches with `CRAWLER_UA` and looks for the prerender block finds
nothing, and a test that only checks the prerender misses what Googlebot
actually receives. Both lanes are covered below, and the crawler lane is
where BUGS-2.7.0.md #5 lives.
"""
from __future__ import annotations

import html as _html
import re

import pytest

from conftest import BROWSER_UA, CRAWLER_UA

PRERENDER_OPEN = '<div id="dimll-prerender"'

# This site's OWN corpus pointer, in either form the prerender may emit.
# Deliberately not a substring match on "llms.txt": the same block carries
# ~17 PEER links from the cross-host directory, which would drown the signal.
SELF_LLMS_HREF = re.compile(
    r'href="(?:/llms\.txt|https://llms\.2plot\.dev/llms\.txt)"'
)


def _prerender(html: str) -> str:
    start = html.find(PRERENDER_OPEN)
    return html[start:] if start >= 0 else ""


def _h1s(markup: str) -> list[str]:
    return [
        _html.unescape(re.sub(r"<[^>]+>", "", raw)).strip()
        for raw in re.findall(r"<h1[^>]*>(.*?)</h1>", markup, re.S)
    ]


# ---------------------------------------------------------------------------
# 1. The prerender lane — the fix that shipped
# ---------------------------------------------------------------------------

def test_every_page_prerenders_exactly_one_h1(client, page_paths):
    """The batch's H1 dedup, across the whole site at once.

    The duplicate was structural — the injected header's h1 repeating the
    prose's own opening markdown H1 — so it appeared on every page
    simultaneously and has to be checked that way.
    """
    offenders = []
    for path in page_paths:
        block = _prerender(client.get(path, user_agent=BROWSER_UA).text)
        if not block:
            offenders.append(f"{path}: no prerender block at all")
            continue
        found = _h1s(block)
        if len(found) != 1:
            offenders.append(f"{path}: {len(found)} h1(s) -> {found}")

    assert offenders == [], (
        "every prerendered page must carry exactly one <h1>; two identical "
        f"ones split the topical signal a crawler reads: {offenders}"
    )


def test_the_single_prerendered_h1_names_the_page(client, pages):
    """One h1 is necessary, not sufficient — it has to be the right one.

    A dedup that kept the SITE brand on every page and dropped the page's own
    title would satisfy the count and destroy the signal.
    """
    from lib.constants import SITE_BRAND

    mismatches = []
    for path, name, _entry in pages:
        found = _h1s(_prerender(client.get(path, user_agent=BROWSER_UA).text))
        if not found:
            continue
        expected = SITE_BRAND if path == "/" else name
        if found[0] != _html.unescape(expected):
            mismatches.append(f"{path}: h1={found[0]!r} expected {expected!r}")

    assert mismatches == [], f"the surviving h1 does not name its page: {mismatches}"


def test_the_prerendered_h1_sits_inside_main(client):
    """Position matters as much as count: an h1 outside <main> is chrome."""
    block = _prerender(client.get("/getting-started", user_agent=BROWSER_UA).text)
    main = re.search(r"<main[^>]*>(.*?)</main>", block, re.S)
    assert main, "the prerender block carries no <main>"
    assert len(_h1s(main.group(1))) == 1


def test_the_whole_browser_document_has_exactly_one_h1(client, page_paths):
    """Stronger than the prerender-only pin, and the one that matches reality.

    A crawler runs no JS, so it parses the <noscript> fallback too. An h1
    there — which templates/index.html shipped — gives every page a second,
    site-wide h1 competing with the page's own. Site-side defect, same class
    as the package's, one layer out.
    """
    offenders = []
    for path in page_paths:
        found = _h1s(client.get(path, user_agent=BROWSER_UA).text)
        if len(found) != 1:
            offenders.append(f"{path}: {len(found)} -> {found}")
    assert offenders == [], f"documents with != 1 h1: {offenders}"


# ---------------------------------------------------------------------------
# 2. The crawler lane — BUGS-2.7.0.md #5
# ---------------------------------------------------------------------------

@pytest.mark.xfail(strict=True, reason=(
    "BUGS-2.7.0.md #5 — the H1 dedup landed on prerender.py:204 but NOT on "
    "html_generator.py:328, which emits <header><h1>{title}</h1> "
    "unconditionally before a <main> whose body_html opens with the prose's "
    "own <h1>. Every page of the CRAWLER document — the one Googlebot, "
    "ClaudeBot and GPTBot actually receive — carries two identical h1s. "
    "Pre-existing on 2.6.1, so not a regression, but it is the same defect "
    "the batch set out to fix, left on the path that matters most for SEO. "
    "Remove this marker when the package fixes it."
))
def test_the_crawler_document_has_exactly_one_h1(client, page_paths):
    offenders = []
    for path in page_paths:
        found = _h1s(client.get(path, user_agent=CRAWLER_UA).text)
        if len(found) != 1:
            offenders.append(f"{path}: {len(found)} -> {found[:2]}")
    assert offenders == [], (
        f"crawler documents with != 1 h1 ({len(offenders)}/{len(page_paths)} "
        f"pages): {offenders[:3]}"
    )


def test_the_crawler_document_is_still_the_one_crawlers_get(client):
    """The control for the test above — if this ever stops holding, #5 has
    changed shape rather than being fixed."""
    crawler = client.get("/getting-started", user_agent=CRAWLER_UA).text
    browser = client.get("/getting-started", user_agent=BROWSER_UA).text
    assert PRERENDER_OPEN not in crawler, "the crawler now gets the app shell"
    assert PRERENDER_OPEN in browser, "the browser lost the prerender"


# ---------------------------------------------------------------------------
# 3. One self-referential /llms.txt link in the home footer
# ---------------------------------------------------------------------------

def test_the_home_footer_links_its_own_llms_txt_exactly_once(client):
    """The corpus pointer is one canonical statement, not two."""
    block = _prerender(client.get("/", user_agent=BROWSER_UA).text)
    assert block, "the home page carries no prerender block"

    found = SELF_LLMS_HREF.findall(block)
    assert len(found) == 1, (
        "expected exactly one self-referential /llms.txt link in the home "
        f"prerender, found {len(found)}"
    )


def test_the_peer_directory_survived_the_dedup(client):
    """The control: the dedup must not have eaten the network directory,
    which is how an agent walks from this satellite to the rest."""
    block = _prerender(client.get("/", user_agent=BROWSER_UA).text)
    peers = re.findall(r'href="https://(?!llms\.2plot\.dev)[^"]+/llms\.txt"', block)
    assert len(peers) > 10, f"only {len(peers)} peer llms.txt links survive"


def test_every_page_points_at_its_own_machine_readable_twin(client, page_paths):
    """Each page's footer names ITS corpus URL, not the home page's."""
    missing = []
    for path in page_paths:
        block = _prerender(client.get(path, user_agent=BROWSER_UA).text)
        expected = "/llms.txt" if path == "/" else f"{path.rstrip('/')}/llms.txt"
        if f'href="{expected}"' not in block:
            missing.append(f"{path} -> expected {expected}")
    assert missing == [], f"pages not pointing at their own twin: {missing}"


# ---------------------------------------------------------------------------
# 4. The bytes moved; the prose must not have
# ---------------------------------------------------------------------------

def test_the_prerendered_prose_survived_the_h1_fix(client, page_paths):
    from conftest import STUB_MARKER

    thin = []
    for path in page_paths:
        block = _prerender(client.get(path, user_agent=BROWSER_UA).text)
        main = re.search(r"<main[^>]*>(.*?)</main>", block, re.S)
        body = main.group(1) if main else ""
        assert STUB_MARKER not in body, f"{path} serves the package's stub"
        if len(re.sub(r"<[^>]+>", "", body).strip()) < 2000:
            thin.append(path)
    assert thin == [], f"thin crawler prose after the H1 fix: {thin}"


def test_the_description_survived_the_header_rewrite(client, pages):
    """The fix removes the h1 from the header and keeps the description.
    Losing both would also produce one h1 per page — and a worse document."""
    for path, _name, entry in pages:
        block = _prerender(client.get(path, user_agent=BROWSER_UA).text)
        header = re.search(r"<header[^>]*>(.*?)</header>", block, re.S)
        assert header, f"{path}: the prerender header is gone entirely"
        assert re.sub(r"<[^>]+>", "", header.group(1)).strip(), (
            f"{path}: the prerender header is empty — the h1 dedup took the "
            "description with it"
        )

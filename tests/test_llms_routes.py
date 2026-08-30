"""The AI/LLM and SEO surfaces: llms.txt, sitemap.xml, robots.txt, canonicals."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from urllib.parse import urlparse

import pytest

from conftest import BROWSER_ACCEPT, CRAWLER_UA
from lib import network_directory as nd
from lib.constants import BASE_URL

SITEMAP_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}


def test_root_llms_txt_is_an_index(client):
    body = client.get("/llms.txt").text
    assert "# " in body, "llms.txt should open with a heading"
    assert "## Network" in body, "the cross-host directory is missing from llms.txt"


def test_every_page_has_its_own_llms_txt(client, page_paths):
    failures = []
    for path in page_paths:
        url = "/llms.txt" if path == "/" else f"{path.rstrip('/')}/llms.txt"
        response = client.get(url)
        if not response.ok or len(response.text) < 200:
            failures.append((url, response.status, len(response.text)))
    assert failures == [], f"per-page llms.txt missing or empty: {failures}"


def test_page_llms_txt_carries_the_page_prose(client):
    body = client.get("/reference/configuration/llms.txt").text
    assert "Configuration" in body
    assert "rate_limit_per_minute" in body, "page prose did not reach /<page>/llms.txt"


def test_source_directives_are_expanded_in_llms_txt(client):
    """`.. source::` must inline the referenced file, not name it.

    The audience for /<page>/llms.txt is someone pasting it into a chat
    window; a directive reference is useless to them.
    """
    body = client.get("/reference/geo/llms.txt").text
    assert ".. source::" not in body, "an unexpanded directive leaked into the prose"
    assert "def geo_deny()" in body, "the referenced source file was not inlined"


def test_robots_txt(client):
    body = client.get("/robots.txt").text
    assert "User-agent:" in body
    assert f"Sitemap: {BASE_URL}/sitemap.xml" in body, "robots.txt must point at this host's sitemap"


def test_robots_artifact_fingerprint(client):
    """The robots.txt crawler split is the network's proof-of-artifact.

    pip metadata is invisible from outside, so these exact robots.txt pairs
    are how a live host is fingerprinted as running the intended
    dash-improve-my-llms — the post-deploy check on every host in the
    rollout. If this fails locally, the installed package regressed.

    The signature, by release that introduced it:

    - 2.3.2: `OAI-SearchBot -> Allow` (ChatGPT search's crawler; pre-fix
      builds disallowed it).
    - 2.3.3: `Claude-User` and `Claude-SearchBot` — the user-triggered and
      search fetchers — are allowed, distinct from ClaudeBot.

    ClaudeBot's own line is NO LONGER a package fingerprint. It read
    `Disallow: /` only because this host set `block_ai_training=True`;
    since the round-3.4 posture flip (2026-08-30) the wall is retired, so
    that line is POLICY, not artifact, and it is asserted as posture below
    instead — the one shape-independent claim being that it is not a
    `Disallow`. The vendor SPLIT is what fingerprints the package, and the
    three lines above still carry it.
    """
    lines = client.get("/robots.txt").text.splitlines()

    def rule(agent):
        idx = lines.index(f"User-agent: {agent}")
        return lines[idx + 1]

    assert rule("OAI-SearchBot") == "Allow: /", "pre-2.3.2 artifact"
    assert rule("Claude-User") == "Allow: /", "pre-2.3.3 artifact"
    assert rule("Claude-SearchBot") == "Allow: /", "pre-2.3.3 artifact"



def test_training_crawlers_are_not_disallowed_in_robots(client):
    """Round 3.4 (2026-08-30): the training wall is retired, so robots.txt
    must not carry `Disallow: /` for the training vendors.

    Asserted as an ABSENCE, deliberately, because the allow SHAPE is
    fork-dependent: with `vendor_policy=None` (the template) the package
    emits no stanza for these vendors at all, while this fork passes the
    CALLABLE `vendor_policy` seam (DIVERGENCES.md 2) and gets an explicit
    `Allow: /`. Measured both ways on dimll 2.8.0. Both mean allowed; only
    "not disallowed" is true of both, so that is what this pins.
    """
    lines = [ln.strip() for ln in client.get("/robots.txt").text.splitlines()]

    for agent in ("ClaudeBot", "GPTBot", "CCBot"):
        marker = f"User-agent: {agent}"
        if marker not in lines:
            continue  # no stanza at all is the template's allow shape
        assert lines[lines.index(marker) + 1] != "Disallow: /", (
            f"{agent} is disallowed again — the round-3.4 flip has been "
            "reverted, or block_ai_training is back to True"
        )

def test_sitemap_lists_every_page_on_this_host(client, page_paths):
    body = client.get("/sitemap.xml").text
    root = ET.fromstring(body)
    locs = [el.text for el in root.findall(".//sm:url/sm:loc", SITEMAP_NS)]
    assert locs, "sitemap.xml contains no <url> entries"

    foreign = [loc for loc in locs if urlparse(loc).netloc != urlparse(BASE_URL).netloc]
    assert foreign == [], f"sitemap.xml lists URLs on another host: {foreign}"

    listed = {urlparse(loc).path.rstrip("/") or "/" for loc in locs}
    missing = {p.rstrip("/") or "/" for p in page_paths} - listed
    assert not missing, f"pages absent from sitemap.xml: {sorted(missing)}"


def test_canonical_points_at_this_host_and_path(client, page_paths):
    """The failure mode that deindexed a satellite for months.

    A canonical on the wrong host tells Google the page is a duplicate of
    somewhere else. Checked per page, because a template-level canonical is
    right on the home page and wrong everywhere else.
    """
    wrong = []
    for path in page_paths:
        html = client.get(path, user_agent=CRAWLER_UA).text
        found = re.findall(r'rel="canonical"\s+href="([^"]*)"', html)
        expected = f"{BASE_URL}{path}"
        if found != [expected]:
            wrong.append((path, found))
    assert wrong == [], f"bad canonical tags (expected exactly one, this host): {wrong}"


def test_exactly_one_canonical_tag_for_browsers(client):
    """A hard-coded canonical in index.html doesn't replace the injected one.

    It joins it, and two conflicting canonicals are read as no signal at all.

    Counts ELEMENTS, not the bare substring `rel="canonical"`. The template
    both explains itself in comments and now ships a script whose selector
    names the attribute (`link[rel="canonical"]`, the SPA URL sync) — neither
    is a canonical tag, and a substring count read both as one. Same lesson as
    the `dv-banner` chrome check below: match the markup, not the words, so a
    file may legitimately discuss what it is being checked for.
    """
    html = re.sub(r"<!--.*?-->", "", client.get("/reference/configuration").text, flags=re.S)
    tags = re.findall(r'<link[^>]+rel="canonical"[^>]*>', html)
    assert len(tags) == 1, f"expected exactly one canonical element, got {tags}"


def test_healthz(client):
    """The 2plot.ai hub probes this hourly on every backend."""
    response = client.get("/healthz")
    assert response.ok
    assert "ok" in response.text.lower()


# ---------------------------------------------------------------------------
# Content negotiation on /<page>/llms.txt (dash-improve-my-llms 2.2.0)
#
# One URL, two audiences. Agents must get Markdown byte for byte; people who
# paste the URL into a browser get it rendered. The failure mode this guards
# against is subtle in both directions: viewer chrome leaking into the
# Markdown makes every agent in the network pay tokens for decoration and
# shows up in no dashboard, and a CDN that ignores `Vary` can hand a cached
# HTML response to the next agent that asks.
# ---------------------------------------------------------------------------

# Deliberately not /reference/configuration/llms.txt: that page *documents* the viewer, so its
# prose contains the words "dv-banner" and "mk-wordmark" legitimately.
PAGE_DOC = "/reference/panel/llms.txt"

# Chrome is detected as rendered markup rather than as a bare class name. A
# Markdown document may legitimately discuss `dv-banner`; it can never contain
# `<div class="dv-banner">`. Keying on the token instead makes any page that
# writes about the viewer fail, which teaches people to stop writing about it.
CHROME = re.compile(r'<[a-z]+ class="dv-banner')


def test_agents_get_markdown(client):
    response = client.get(PAGE_DOC)
    assert response.ok
    assert "text/markdown" in response.content_type, response.content_type
    assert not CHROME.search(response.text), "viewer chrome leaked into the agent's copy"
    assert "<!DOCTYPE html>" not in response.text


def test_browsers_get_the_rendered_view(client):
    response = client.get(PAGE_DOC, accept=BROWSER_ACCEPT)
    assert response.ok
    assert "text/html" in response.content_type, response.content_type
    assert CHROME.search(response.text), "the viewer header is missing"
    assert "mk-wordmark" in response.text, "the network wordmark is missing"


def test_the_banner_renders_its_panels_without_a_bulletin(client):
    """Tips and What's new appear with the package's built-in defaults.

    `configure_bulletin()` is deliberately unwired here — 2plot.dev doesn't
    serve the endpoint yet — and this pins the fact that the header is fully
    formed regardless. Without it, "the banner looks wrong" could mean either
    a missing bulletin or a broken viewer, and those have very different
    fixes.
    """
    html = client.get(PAGE_DOC, accept=BROWSER_ACCEPT).text
    assert "Tips for getting started" in html
    assert "Append /llms.txt to any page URL" in html, "the default tip is missing"
    assert "What's new" in html
    assert "No announcements." in html, "the empty-state text is missing"


def test_the_banner_carries_this_app_and_network_identity(client):
    """The banner must name *this* site, not the package's demo app."""
    html = client.get(PAGE_DOC, accept=BROWSER_ACCEPT).text
    assert nd.NETWORK_NAME in html, "the banner does not name the network"
    assert nd.HUB_URL in html, "the banner does not link the hub"


def test_a_page_may_document_the_viewer_without_tripping_the_check(client):
    """/networks documents the viewer, so its prose names `dv-banner`.

    That is content, not chrome. This pins the distinction so the check
    can't be "fixed" later by making it substring-based again.
    """
    response = client.get("/reference/configuration/llms.txt")
    assert "text/markdown" in response.content_type
    assert "dv-banner" in response.text, "expected the page to discuss the class name"
    assert not CHROME.search(response.text), "that mention must not read as chrome"


def test_crawlers_get_markdown_not_the_viewer(client):
    """Googlebot asks for HTML by habit. It still gets the document.

    The rendered view is `noindex` precisely so it never competes with the
    real page, so serving it to a crawler would waste the fetch.
    """
    response = client.get(PAGE_DOC, user_agent=CRAWLER_UA)
    assert "text/markdown" in response.content_type, response.content_type


def test_both_variants_send_vary_accept(client):
    """Without `Vary: Accept`, a shared cache serves whichever variant it saw
    first to everyone — including HTML to an agent."""
    for accept in (None, BROWSER_ACCEPT):
        response = client.get(PAGE_DOC, accept=accept)
        assert "accept" in response.header("Vary").lower(), (
            f"Vary is {response.header('Vary')!r} for Accept={accept!r}"
        )


def test_query_overrides_beat_the_accept_header(client):
    """`?raw=1` for a person debugging in a browser, `?format=html` for a
    person sharing a link from a terminal."""
    raw = client.get(f"{PAGE_DOC}?raw=1", accept=BROWSER_ACCEPT)
    assert "text/markdown" in raw.content_type, raw.content_type

    rendered = client.get(f"{PAGE_DOC}?format=html")
    assert "text/html" in rendered.content_type, rendered.content_type


def test_the_rendered_view_is_noindex(client):
    """It is the same content as the page it documents. Indexed, it would
    compete with it."""
    response = client.get(PAGE_DOC, accept=BROWSER_ACCEPT)
    assert re.search(r'<meta[^>]+name="robots"[^>]+noindex', response.text), (
        "the viewer must not be indexable"
    )


# ---------------------------------------------------------------------------
# The navigation block (2.2.0)
#
# A page's llms.txt is usually read in isolation — pasted into a chat, handed
# to an agent. Before 2.2.0 it was a dead end: it described one page and gave
# an agent nothing to follow.
# ---------------------------------------------------------------------------


def test_page_documents_are_not_dead_ends(client):
    body = client.get(PAGE_DOC).text
    assert f"{BASE_URL}/llms.txt" in body, "no route back to this site's index"
    assert f"{BASE_URL}/sitemap.xml" in body, "no sitemap link"


def test_nav_block_points_one_level_up_the_hub_chain(client):
    """A subdomain names its section hub, not the network root.

    Each llms.txt then has exactly one "up" link and an agent walks the chain.
    This app is a `*.2plot.dev` subdomain, so its hub is 2plot.dev.
    """
    body = client.get(PAGE_DOC).text
    assert f"{nd.HUB_URL}/llms.txt" in body, f"expected the hub chain to reach {nd.HUB_URL}"


def test_nav_block_is_absent_from_the_root_index(client):
    """The root document *is* the site index; pointing it at itself is noise."""
    body = client.get("/llms.txt").text
    assert "## Pages" in body, "the root document should be an index"
    assert not CHROME.search(body), "viewer chrome leaked into the root index"


# ---------------------------------------------------------------------------
# /healthz is a LIVE report, not a snapshot
# ---------------------------------------------------------------------------

def test_healthz_reports_which_app_answered(client):
    """`build` says which commit; `app` says which satellite.

    On a fleet where several hosts share a template and a hostname can be
    repointed between services, those are different questions.
    """
    import json

    payload = json.loads(client.get("/healthz").text)
    assert payload["app"], "no app identity on /healthz"
    assert payload["ok"] is True


def test_healthz_reports_the_live_geo_state(app_module, client):
    """The regression pin for a snapshot payload.

    `register_health_route` used to compute the payload ONCE at registration
    and close over it. Harmless while every field was static — and silently
    wrong the moment one is not. The route is registered ~150 lines before
    `configure_geo` runs, so a snapshot reported the guardrail unconfigured
    on a host where it is configured: the diagnostic lying in exactly the
    situation it exists for.
    """
    import json

    from lib import policy_store

    before = json.loads(client.get("/healthz").text)["geo"]
    assert before["configured"] is True, (
        "this app calls configure_geo unconditionally, so /healthz must "
        "report it configured"
    )

    try:
        app_module.configure_geo(deny_countries=["RU", "CN"])
        after = json.loads(client.get("/healthz").text)["geo"]
        assert after["denied"] == 2, (
            f"/healthz did not follow a live config change ({after}) — it is "
            "a snapshot again"
        )
    finally:
        app_module.configure_geo(
            deny_countries=policy_store.geo_deny,
            unknown=policy_store.geo_unknown(),
            exempt_paths=("/healthz", "/health", "/livez", "/readyz"),
        )


def test_healthz_never_publishes_the_country_codes(app_module, client):
    """Counts and flags only. The codes are already public on the policy
    showcase, but a health endpoint is not where anyone should learn policy.
    """
    import json

    from lib import policy_store

    try:
        app_module.configure_geo(deny_countries=["RU", "CN"])
        body = client.get("/healthz").text
        assert "RU" not in body and "CN" not in body, body
        assert json.loads(body)["geo"]["denied"] == 2
    finally:
        app_module.configure_geo(
            deny_countries=policy_store.geo_deny,
            unknown=policy_store.geo_unknown(),
            exempt_paths=("/healthz", "/health", "/livez", "/readyz"),
        )


def test_healthz_resolves_the_country_from_this_requests_headers(client):
    """`resolved` must read THIS request's headers — on EVERY backend.

    The first version of the geo block called Flask's request context
    directly, so the FastAPI and Quart lanes answered "no request context"
    forever: a diagnostic that silently stops diagnosing on two of three
    backends, and specifically on the one field GEO.md calls the mandatory
    per-host check. The template caught it on pannellum's production
    healthz (FastAPI) and fixed it in 1.6.12 by having each route hand its
    own framework's headers to `health_payload`; this fork ported it before
    its own non-Flask lane shipped.

    One test, not two: `client` is whichever backend DASH_BACKEND names, so
    CI's flask/fastapi/quart legs each run this against a real request of
    their own framework's type. `/healthz` is an exempt path, so the
    spoofed header resolves without being enforced.
    """
    import json

    geo = json.loads(client.get("/healthz", headers={"CF-IPCountry": "FR"}).text)["geo"]
    assert "FR" in geo["resolved"], (
        f"/healthz did not resolve this request's country ({geo}) — the "
        "route is not passing its own headers through"
    )


def test_resolved_country_reads_explicit_headers_without_a_request():
    """The context-free pin — the only one that can actually fail.

    The in-request pins above pass even if a Flask route drops its
    `headers=`: inside a request the context fallback reads the same
    headers, and the lanes that genuinely break (Starlette/Quart) are
    unreachable from a Flask-pinned suite. Calling _resolved_country
    with a plain dict OUTSIDE any request context has no fallback to
    hide behind (dash-flows' finding, 2026-08-23).
    """
    from lib.health import _resolved_country

    result = _resolved_country({"CF-IPCountry": "DE"})
    if result.startswith("unavailable (pre-2.7.0"):
        pytest.skip("geo shipped in dash-improve-my-llms 2.7.0")
    assert "DE" in result, result

"""The country guardrail (dash-improve-my-llms 2.7.0) — from the app side.

The package's own suite proves the guardrail against fixtures. This file
proves it against THIS app: a real page tree, a real robots.txt, a real
asset folder, a real Dash update route, on whichever backend
``DASH_BACKEND`` selects. That is the gap a package suite cannot close —
"451 on every surface" is a claim about an application, not about a module.

The denylist here is driven through ``lib.policy_store``, the callable seam,
because that is how this site actually configures it. Where a behaviour is
about the STATIC form the test reconfigures explicitly and restores.

Read docs/GEO.md for the trust model. Short version: the country comes from
an edge header, so this is a compliance guardrail and not a security
boundary, and every test below spoofs the header exactly the way a
direct-to-origin client could.
"""
from __future__ import annotations

import json
import re

import pytest

from conftest import requires_dimll_27

# Every assertion in this module is about the 2.7.0 surface. On the
# pinned 2.6.1 floor the whole file skips rather than fails.
pytestmark = requires_dimll_27

from conftest import BROWSER_ACCEPT, BROWSER_UA, CRAWLER_UA

DENIED = "RU"
ALLOWED = "US"

# One representative of every surface class the guardrail claims to cover.
# Grouped rather than flat so a failure names the CLASS that regressed —
# "the corpus is open to a denied country" is the sentence that matters,
# not which of three corpus URLs was sampled.
SURFACES = {
    "app page": "/",
    "docs page": "/examples/ai-integration",
    "asset": "/assets/main.css",
    "llms index": "/llms.txt",
    "llms small tier": "/llms-small.txt",
    "llms full tier": "/llms-full.txt",
    "page llms.txt": "/examples/ai-integration/llms.txt",
    "robots.txt": "/robots.txt",
    "sitemap.xml": "/sitemap.xml",
    "favicon": "/favicon.ico",
}


@pytest.fixture(autouse=True)
def restore_geo(app_module):
    """Every test leaves the app in its booted production posture.

    Package config is process-global module state, and this suite shares one
    booted app across every test in the session. A test that reconfigures geo
    and does not put it back does not fail — it silently changes what every
    later test is asserting about.
    """
    from lib import policy_store

    yield

    _write_store({})
    policy_store.reset_for_tests()
    app_module.configure_geo(
        deny_countries=policy_store.geo_deny,
        unknown=policy_store.geo_unknown(),
        exempt_paths=("/healthz", "/health", "/livez", "/readyz"),
        policy_url="",
    )


def _write_store(doc: dict) -> None:
    """Write the store the way another worker would, then drop our cache."""
    import os

    from lib import policy_store

    path = policy_store.path()
    path.write_text(json.dumps(doc), encoding="utf-8")
    # The store keys its cache on (mtime_ns, size); two writes inside one
    # filesystem timestamp tick with the same length would not be noticed.
    # Tests write faster than production ever does, so bump the stamp
    # explicitly rather than sleeping.
    os.utime(path, ns=(0, os.stat(path).st_mtime_ns + 1_000_000))
    policy_store.reset_for_tests()


def _deny(app_module, countries=(DENIED,), **kwargs):
    """Configure the guardrail with a STATIC list."""
    app_module.configure_geo(deny_countries=list(countries), **kwargs)


# Dash regenerates `end_id` (a per-request CSRF nonce) on every HTML render,
# so two IDENTICAL requests are not byte-identical either. Masking it is what
# makes "byte-identical" mean "nothing the guardrail did", and
# test_the_nonce_mask_is_sound below proves the mask cannot hide a real change.
_NONCE = re.compile(r'"end_id":"[^"]*"')


def _stable(body: str) -> str:
    return _NONCE.sub('"end_id":"<masked>"', body)


def _get(client, path, country=None, **kwargs):
    headers = {"CF-IPCountry": country} if country else {}
    headers.update(kwargs.pop("headers", {}))
    return client.get(path, headers=headers, **kwargs)


# ---------------------------------------------------------------------------
# 1. Unconfigured is a strict no-op
# ---------------------------------------------------------------------------

def test_the_nonce_mask_is_sound(client):
    """The control for every byte-identical assertion in this file.

    If masking `end_id` were hiding something, two identical requests would
    still differ after the mask — and every "byte-identical" test below would
    be vacuous.
    """
    a, b = client.get("/"), client.get("/")
    assert a.text != b.text, (
        "two identical requests are byte-identical — the nonce mask is now "
        "unnecessary and should be deleted rather than left hiding changes"
    )
    assert _stable(a.text) == _stable(b.text)


@pytest.mark.parametrize("label,path", SURFACES.items(), ids=list(SURFACES))
def test_empty_denylist_is_byte_identical(client, label, path):
    """The claim the whole feature rests on.

    This app calls `configure_geo` UNCONDITIONALLY (run.py), so if an empty
    denylist were not a perfect no-op the guardrail would be a permanent tax
    on every response this site serves.
    """
    plain = client.get(path)
    with_country = _get(client, path, DENIED)

    assert with_country.status == plain.status, f"{label}: status moved"
    assert _stable(with_country.text) == _stable(plain.text), f"{label}: body moved"


# ---------------------------------------------------------------------------
# 2. A denied country gets 451 on EVERY surface class
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("label,path", SURFACES.items(), ids=list(SURFACES))
def test_denied_country_gets_451_everywhere(app_module, client, label, path):
    _deny(app_module)
    r = _get(client, path, DENIED)

    assert r.status == 451, f"{label} ({path}) served {r.status} to a denied country"
    assert r.header("Cache-Control") == "no-store", (
        f"{label}: Cache-Control={r.header('Cache-Control')!r}. no-store is "
        "load-bearing — the response varies by country and no Vary token "
        "exists for edge geo headers, so a shared cache storing one country's "
        "451 would serve it to the world."
    )


def test_the_pages_router_post_is_covered(app_module, client):
    """The surface a GET-only guardrail forgets.

    A Dash SPA changes pages through POST /_dash-update-component. Cover only
    GET and a session established before the block simply keeps browsing.
    """
    _deny(app_module)
    r = client.post(
        "/_dash-update-component",
        json={"output": "..", "outputs": [], "inputs": [], "changedPropIds": []},
        headers={"CF-IPCountry": DENIED},
    )
    assert r.status == 451, f"the pages router POST served {r.status}"
    assert r.header("Cache-Control") == "no-store"


@pytest.mark.parametrize("label,path", SURFACES.items(), ids=list(SURFACES))
def test_allowed_country_is_unchanged(app_module, client, label, path):
    """An allowed country's statuses equal an unconfigured build's."""
    baseline = client.get(path)
    _deny(app_module)
    r = _get(client, path, ALLOWED)

    assert r.status == baseline.status, f"{label}: allowed country got {r.status}"
    assert _stable(r.text) == _stable(baseline.text), (
        f"{label}: allowed country's body moved"
    )


def test_bots_are_denied_too(app_module, client):
    """Humans and bots alike — the application does not exist for that geo."""
    _deny(app_module)
    for ua in (BROWSER_UA, CRAWLER_UA, "ClaudeBot/1.0", "GPTBot/1.1"):
        r = _get(client, "/llms.txt", DENIED, user_agent=ua)
        assert r.status == 451, f"{ua} got {r.status} from a denied country"


# ---------------------------------------------------------------------------
# 3. The 451 response's shape
# ---------------------------------------------------------------------------

def test_451_body_is_one_plain_line(app_module, client):
    _deny(app_module)
    r = _get(client, "/", DENIED)
    assert "text/plain" in r.content_type, f"content-type {r.content_type!r}"
    assert r.text.strip(), "the 451 body is empty"
    assert len(r.text.splitlines()) == 1, f"expected one line, got {r.text!r}"


def test_policy_url_emits_the_rfc7725_link(app_module, client):
    """RFC 7725: a 451 SHOULD name the authority that demanded the block."""
    url = "https://llms.2plot.dev/legal/geo"
    _deny(app_module, policy_url=url)
    r = _get(client, "/", DENIED)

    link = r.header("Link")
    assert link, "no Link header with policy_url set"
    assert url in link, f"Link={link!r} does not carry the policy URL"
    assert 'rel="blocked-by"' in link, f"Link={link!r} lacks rel=blocked-by"


def test_no_link_header_without_a_policy_url(app_module, client):
    _deny(app_module)
    r = _get(client, "/", DENIED)
    assert "blocked-by" not in r.header("Link"), (
        "a blocked-by Link appeared with no policy_url configured"
    )


def test_custom_body_is_served(app_module, client):
    _deny(app_module, body="Unavailable in your region.")
    r = _get(client, "/", DENIED)
    assert r.text.strip() == "Unavailable in your region."


# ---------------------------------------------------------------------------
# 4. Exempt paths are EXACT matches
# ---------------------------------------------------------------------------

def test_healthz_survives_a_denied_country(app_module, client):
    """The platform's health check has no country and must never 451.

    Without this the hub's hourly sweep would report a geo-enabled host down.
    """
    _deny(app_module)
    r = _get(client, "/healthz", DENIED)
    assert r.status == 200, f"/healthz answered {r.status} to a denied country"


def test_exempt_paths_do_not_match_by_prefix(app_module, client):
    """A prefix match here would be a bypass: /healthz-evil, /healthz/../."""
    _deny(app_module)
    for path in ("/healthz-evil", "/healthzz", "/healthz/anything"):
        r = _get(client, path, DENIED)
        assert r.status == 451, (
            f"{path} answered {r.status} — exempt paths must match EXACTLY or "
            "the health exemption becomes a denylist bypass anyone can spell."
        )


def test_exempt_paths_are_configurable(app_module, client):
    _deny(app_module, exempt_paths=("/custom-health",))
    assert _get(client, "/custom-health", DENIED).status != 451
    assert _get(client, "/healthz", DENIED).status == 451, (
        "the default exempt list survived an explicit exempt_paths="
    )


# ---------------------------------------------------------------------------
# 5. Unknown countries
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("header", [None, "", "XX", "T1", "ZZZ", "1", "de-DE", "??"])
def test_unknown_country_is_allowed_by_default(app_module, client, header):
    """Fail-open is the documented default, and it is load-bearing.

    It is what keeps platform health checks, monitoring sweeps and
    direct-to-origin fetches working on a geo-enabled host.
    """
    _deny(app_module)
    headers = {} if header is None else {"CF-IPCountry": header}
    r = client.get("/", headers=headers)
    assert r.status != 451, f"CF-IPCountry={header!r} was treated as a country"


@pytest.mark.parametrize("header", ["XX", "T1", "", "ZZZ"])
def test_unknown_deny_posture_blocks(app_module, client, header):
    _deny(app_module, unknown="deny")
    r = client.get("/", headers={"CF-IPCountry": header})
    assert r.status == 451, f"unknown='deny' let CF-IPCountry={header!r} through"


def test_unknown_deny_still_exempts_health(app_module, client):
    """Under `deny`, health checks survive ONLY via exempt_paths."""
    _deny(app_module, unknown="deny")
    assert client.get("/healthz").status == 200


def test_country_matching_is_case_insensitive(app_module, client):
    _deny(app_module)
    for spelling in ("ru", "Ru", "rU", "RU"):
        r = client.get("/", headers={"CF-IPCountry": spelling})
        assert r.status == 451, f"CF-IPCountry={spelling!r} was not matched"


# ---------------------------------------------------------------------------
# 6. Header resolution order
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("header", [
    "CF-IPCountry", "CloudFront-Viewer-Country", "X-Vercel-IP-Country",
    "Fastly-Geo-Country", "X-Country-Code",
])
def test_every_documented_edge_header_resolves(app_module, client, header):
    _deny(app_module)
    r = client.get("/", headers={header: DENIED})
    assert r.status == 451, f"{header} did not resolve a country"


def test_cloudflare_wins_the_resolution_order(app_module, client):
    """CF-IPCountry is the fleet's edge and is documented as taking priority."""
    _deny(app_module)
    r = client.get("/", headers={"CF-IPCountry": ALLOWED,
                                 "X-Vercel-IP-Country": DENIED})
    assert r.status != 451, "a lower-priority header overrode CF-IPCountry"


def test_a_custom_resolver_takes_priority(app_module, client):
    _deny(app_module, resolver=lambda headers: DENIED)
    r = client.get("/")  # no country header at all
    assert r.status == 451, "the configured resolver was not consulted"


def test_a_raising_resolver_does_not_deny(app_module, client):
    """A broken geo-ip lookup must never black-hole the site.

    With NO country header present there is nothing to fall back to, so this
    isolates the resolver's own failure posture from header resolution.
    """
    def boom(headers):
        raise RuntimeError("geo-ip database unavailable")

    _deny(app_module, resolver=boom)
    assert client.get("/").status != 451


def test_a_raising_resolver_falls_back_to_headers(app_module, client):
    """Documented behaviour differs from GEO.md — see BUGS-2.7.0.md #4.

    GEO.md's resolution order says "exceptions -> unknown, warned once",
    which reads as "the request is unknown". The implementation logs
    "falling back to header resolution" and does exactly that, so an edge
    header still resolves. This test pins what the CODE does, because that
    is what an operator's traffic will meet; the doc is the half that should
    move.
    """
    def boom(headers):
        raise RuntimeError("geo-ip database unavailable")

    _deny(app_module, resolver=boom)
    assert client.get("/", headers={"CF-IPCountry": DENIED}).status == 451


def test_a_resolver_returning_garbage_does_not_fall_back(app_module, client):
    """The asymmetry worth knowing about: raising falls back to headers,
    returning an invalid value does not."""
    _deny(app_module, resolver=lambda headers: "NOPE")
    assert client.get("/", headers={"CF-IPCountry": DENIED}).status != 451


# ---------------------------------------------------------------------------
# 7. THE SEAM — the whole point of the release
# ---------------------------------------------------------------------------

def test_a_store_toggle_lands_on_the_next_request(app_module, client):
    """The seam's entire promise, end to end, with no restart.

    Write the store the way the control board's callback does, and the very
    next request answers 451. This is the acceptance criterion the migration
    kickoff writes for B7, exercised in-process.
    """
    from lib import policy_store

    app_module.configure_geo(deny_countries=policy_store.geo_deny)

    assert client.get("/", headers={"CF-IPCountry": DENIED}).status != 451

    _write_store({"geo_deny": [DENIED]})

    r = client.get("/", headers={"CF-IPCountry": DENIED})
    assert r.status == 451, (
        "the store toggle did NOT reach the next request — the callable seam "
        "is the reason 2.7.0 exists, and without this the control board needs "
        "a redeploy to block a country."
    )

    _write_store({"geo_deny": []})
    assert client.get("/", headers={"CF-IPCountry": DENIED}).status != 451, (
        "un-toggling did not recover"
    )


def test_the_seam_is_read_per_request_not_cached_at_config_time(app_module, client):
    """A denylist snapshotted at configure_geo() time would pass the test
    above by accident if the store already had the value. Configure FIRST
    with an empty store, then fill it."""
    from lib import policy_store

    _write_store({})
    app_module.configure_geo(deny_countries=policy_store.geo_deny)
    _write_store({"geo_deny": ["FR"]})

    assert client.get("/", headers={"CF-IPCountry": "FR"}).status == 451


def test_a_raising_callable_fails_open(app_module, client, caplog):
    calls = []

    def broken():
        calls.append(1)
        raise RuntimeError("store on fire")

    app_module.configure_geo(deny_countries=broken)
    for _ in range(3):
        r = client.get("/", headers={"CF-IPCountry": DENIED})
        assert r.status != 451, (
            "a raising denylist callable must fail OPEN — it runs inside every "
            "request and can never be allowed to take down the request path."
        )
    assert calls, "the callable was never consulted"


@pytest.mark.parametrize("junk", [None, 42, object(), "RU"], ids=[
    "None", "int", "object", "bare-string"])
def test_a_non_sequence_callable_fails_open(app_module, client, junk):
    """Not iterable (or iterable into nonsense) -> empty denylist.

    `"RU"` is in here on purpose: returning a bare STRING instead of a list
    is the likeliest operator slip, and it iterates to 'R','U' — two invalid
    one-character codes — so it blocks nobody. Safe, but silently so.
    """
    app_module.configure_geo(deny_countries=lambda: junk)
    assert client.get("/", headers={"CF-IPCountry": DENIED}).status != 451


def test_a_malformed_entry_does_not_void_the_whole_list(app_module, client):
    """Pins the CODE's behaviour, which GEO.md contradicts — BUGS-2.7.0.md #3.

    The doc says "a raising callable OR A MALFORMED ENTRY is ... treated as
    an empty denylist (fail-open)". The implementation skips the bad entry
    with a warn-once and keeps the valid ones, which is the more useful
    behaviour — but an operator who reads the doc and finds `["RU", "XX"]`
    in the store will predict that nobody is blocked, and RU is.
    """
    app_module.configure_geo(deny_countries=lambda: ["RU", "XX", "nonsense"])
    assert client.get("/", headers={"CF-IPCountry": "RU"}).status == 451


@pytest.mark.xfail(strict=True, reason=(
    "BUGS-2.7.0.md #1 — geo.py:221 `_callable_cache.get(raw)` sits OUTSIDE "
    "the try/except that catches callable failures, so an unhashable element "
    "in the returned sequence raises TypeError out of gate() and every "
    "request on every surface 500s. Contradicts GEO.md's 'it can never take "
    "down the request path'. Remove this marker when the package fixes it."
))
@pytest.mark.parametrize("junk", [
    [{"code": "RU"}], [["RU"]], [{"RU"}], ["RU", {"x": 1}],
], ids=["list-of-dicts", "list-of-lists", "list-of-sets", "valid-plus-dict"])
def test_an_unhashable_entry_fails_open(app_module, client, junk):
    """The store is JSON. A hand-edit, a schema change, or 2.8's bot x
    country matrix written by a newer worker all produce nested objects
    here — and the contract says the worst that may happen is no blocking.
    """
    app_module.configure_geo(deny_countries=lambda: junk)
    r = client.get("/", headers={"CF-IPCountry": DENIED})
    assert r.status != 500, (
        f"deny_countries returning {junk!r} took the whole site down with a "
        "500 — every surface, every visitor, every country."
    )


def test_a_malformed_store_fails_open(app_module, client):
    """The store's own degrade path, through the seam."""
    from lib import policy_store

    app_module.configure_geo(deny_countries=policy_store.geo_deny)
    _write_store({"geo_deny": [DENIED]})
    assert client.get("/", headers={"CF-IPCountry": DENIED}).status == 451

    policy_store.path().write_text("{ this is not json")
    policy_store.reset_for_tests()

    assert client.get("/", headers={"CF-IPCountry": DENIED}).status != 451, (
        "a corrupt store must fail open, not lock the site to its last "
        "known denylist"
    )


def test_the_callable_warns_only_once(app_module, client, caplog):
    """A per-request warning turns a degradation into a log outage."""
    import logging

    def broken():
        raise RuntimeError("store on fire")

    app_module.configure_geo(deny_countries=broken)
    with caplog.at_level(logging.WARNING):
        for _ in range(5):
            client.get("/", headers={"CF-IPCountry": DENIED})

    hits = [r for r in caplog.records if "store on fire" in str(r.getMessage())
            or "deny" in str(r.getMessage()).lower()]
    assert len(hits) <= 1, (
        f"{len(hits)} warnings for one broken callable — this runs per "
        f"request, so a repeated warning fills the disk: {[h.getMessage() for h in hits][:3]}"
    )


# ---------------------------------------------------------------------------
# 8. Static-list validation
# ---------------------------------------------------------------------------

def test_a_static_list_validates_at_config_time(app_module):
    """The static path CAN raise, so it should — the callable path cannot."""
    for bad in (["RUS"], ["R"], ["12"], [""], ["ru!"]):
        with pytest.raises(ValueError):
            app_module.configure_geo(deny_countries=bad)


def test_effective_policy_reports_the_callable_source(app_module):
    from lib import policy_store

    app_module.configure_geo(deny_countries=policy_store.geo_deny)
    policy = app_module._geo.effective_policy()
    assert policy["configured"] is True
    assert policy["denylist_source"] != "static", (
        "effective_policy() must distinguish a live callable from a frozen "
        "list — the panel shows this so an operator knows whether the board "
        "can change it."
    )


def test_explain_resolution_names_the_header(app_module):
    """The live per-host deployment check GEO.md mandates before trusting a
    denylist."""
    # Lowercase keys on purpose: the adapters hand this function the output
    # of _headers.normalize_headers(), which lowercases. Passing mixed case
    # here would silently resolve "unknown" and pass nothing useful.
    explained = app_module._geo.explain_resolution({"cf-ipcountry": "DE"})
    text = json.dumps(explained) if not isinstance(explained, str) else explained
    assert "DE" in text
    assert "cf-ipcountry" in text.lower(), (
        f"explain_resolution did not name the header that resolved: {text!r}"
    )

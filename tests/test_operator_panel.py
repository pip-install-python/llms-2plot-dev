"""The operator policy panel (dash-improve-my-llms 2.7.0) — from the app side.

`run.py` registers the panel unconditionally (`LLMSConfig(panel=True)`) and
leaves the token to `DIMLL_PANEL_TOKEN`, read per request. That combination
is the one PANEL.md documents as safe: no token means 404 for everyone, and
an operator can rotate or revoke the secret live.

The test that earns its keep here is `test_the_vendor_table_cannot_drift_from
_robots_txt`. The package pins panel-vs-fold agreement in its own suite; this
pins panel-vs-THIS-APP'S-SERVED-BYTES, which is the claim an operator
actually relies on when they read the panel to decide what the site is doing.
"""
from __future__ import annotations

import os
import re

import pytest

from conftest import requires_dimll_27

# Every assertion in this module is about the 2.7.0 surface. On the
# pinned 2.6.1 floor the whole file skips rather than fails.
pytestmark = requires_dimll_27

TOKEN = "soak-panel-token-8f2c"
PANEL = "/llms-policy"


@pytest.fixture
def token(monkeypatch):
    """A live token for one test. Read per request, so no reboot needed."""
    monkeypatch.setenv("DIMLL_PANEL_TOKEN", TOKEN)
    return TOKEN


@pytest.fixture
def no_token(monkeypatch):
    monkeypatch.delenv("DIMLL_PANEL_TOKEN", raising=False)


_UNSET = object()


def _panel(client, token_value=_UNSET, **headers):
    """GET the panel. Sends TOKEN unless a different value is passed.

    The default is the VALID token because most tests here are about what an
    authorised operator sees; the gate tests pass their own value.
    """
    hdrs = dict(headers)
    hdrs["X-LLMS-Panel-Token"] = TOKEN if token_value is _UNSET else token_value
    return client.get(PANEL, headers=hdrs)


def _panel_text(client, token_value=_UNSET, **headers):
    """The panel with its markup stripped, for prose assertions."""
    return _text(_panel(client, token_value, **headers).text)


def _text(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html)


# ---------------------------------------------------------------------------
# The gate
# ---------------------------------------------------------------------------

def test_no_token_configured_is_404_for_everyone(client, no_token):
    """Production fails closed. This is the DEFAULT state of every fork."""
    assert _panel(client).status == 404
    assert _panel(client, "anything").status == 404
    assert client.get(f"{PANEL}?token=anything").status == 404


def test_wrong_token_is_404_and_unrevealing(client, token):
    r = _panel(client, "wrong-token")
    assert r.status == 404, f"a wrong token got {r.status} — that confirms the path exists"

    body = r.text.lower()
    for leak in ("panel", "token", "unauthor", "forbidden", "policy panel",
                 "dash-improve-my-llms"):
        assert leak not in body, (
            f"the 404 body names {leak!r} — a wrong-token response must not "
            f"advertise that this path is anything special: {r.text[:200]!r}"
        )


def test_an_empty_token_header_is_404(client, token):
    assert _panel(client, "").status == 404


def test_the_right_token_renders_real_state(client, token):
    r = _panel(client)
    assert r.status == 200, f"a correct token got {r.status}"
    body = r.text
    for section in ("Identity", "Vendor policy", "Bot policy flags",
                    "Tier documents", "Access control", "Geo guardrail",
                    "Rate limiting", "Network"):
        assert section in body, f"the panel is missing its {section!r} section"


def test_the_query_parameter_also_works(client, token):
    """Documented browser convenience — and documented as log-leaking."""
    assert client.get(f"{PANEL}?token={TOKEN}").status == 200
    assert client.get(f"{PANEL}?token=nope").status == 404


def test_the_token_is_read_per_request_not_at_boot(client, monkeypatch):
    """PANEL.md's rotation promise: the old token dies on the next request.

    If the token were captured at boot this would need a redeploy, which is
    exactly when a leaked operator secret does not get rotated.
    """
    monkeypatch.setenv("DIMLL_PANEL_TOKEN", "first-secret")
    assert _panel(client, "first-secret").status == 200

    monkeypatch.setenv("DIMLL_PANEL_TOKEN", "second-secret")
    assert _panel(client, "first-secret").status == 404, "the rotated-out token still works"
    assert _panel(client, "second-secret").status == 200, "the new token does not work"

    monkeypatch.delenv("DIMLL_PANEL_TOKEN")
    assert _panel(client, "second-secret").status == 404, "revocation did not take"


def test_explicit_config_token_beats_the_env_var(app_module, client, monkeypatch):
    config = getattr(app_module.app, "_llms_config", None)
    if config is None or getattr(config, "panel_token", None) is None:
        pytest.skip("this app configures the token by env, not by LLMSConfig")


# ---------------------------------------------------------------------------
# Response posture
# ---------------------------------------------------------------------------

def test_success_is_noindex_and_private(client, token):
    r = _panel(client)
    assert r.header("X-Robots-Tag") == "noindex, nofollow"
    assert r.header("Cache-Control") == "private, no-store", (
        "the panel names live policy and the serving worker; a shared cache "
        "must never hold it"
    )


# ---------------------------------------------------------------------------
# The panel never advertises itself
# ---------------------------------------------------------------------------

def test_the_panel_path_is_absent_from_robots_txt(client, token):
    """A Disallow line PUBLISHES the path — the /admin lesson."""
    body = client.get("/robots.txt").text
    assert PANEL not in body, (
        "robots.txt names the panel path, which tells every crawler exactly "
        "where the operator surface lives"
    )


def test_the_panel_path_is_absent_from_the_sitemap(client, token):
    assert PANEL not in client.get("/sitemap.xml").text


def test_the_panel_path_is_absent_from_the_llms_index(client, token):
    assert PANEL not in client.get("/llms.txt").text


def test_the_panel_is_not_a_registered_page(app_module, token):
    import dash

    assert PANEL not in {e["path"] for e in dash.page_registry.values()}


# ---------------------------------------------------------------------------
# THE ANTI-DRIFT TEST — the panel's whole reason to be trusted
# ---------------------------------------------------------------------------

def _panel_vendor_policies(html: str) -> dict:
    """{vendor: effective policy} from the panel's vendor table."""
    section = html[html.index("Vendor policy"):html.index("Bot policy flags")]
    out = {}
    for row in re.findall(r"<tr>(.*?)</tr>", section, re.S):
        cells = [re.sub(r"<[^>]+>", "", c).strip()
                 for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.S)]
        if len(cells) >= 4 and cells[0] != "vendor":
            out[cells[0]] = cells[3]
    return out


def _robots_verdicts(robots: str) -> dict:
    """{user-agent: 'allow'|'block'} from the SERVED robots.txt bytes."""
    out = {}
    current = []
    for line in robots.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, _, value = line.partition(":")
        key, value = key.strip().lower(), value.strip()
        if key == "user-agent":
            current.append(value)
        elif key in ("allow", "disallow"):
            verdict = "block" if (key == "disallow" and value == "/") else "allow"
            for agent in current:
                out[agent] = verdict
            current = []
        else:
            current = []
    return out


def test_the_vendor_table_cannot_drift_from_robots_txt(client, token):
    """Panel says == robots.txt does, on a REAL app rather than a fixture.

    The package pins the panel against the `effective_policies` fold. This
    pins it against the bytes this host actually serves, which is the thing
    an operator reads the panel to learn. A regression that reintroduced a
    second policy path would pass the package's test and fail this one.
    """
    panel = _panel_vendor_policies(_unescape(_panel(client).text))
    robots = _robots_verdicts(client.get("/robots.txt").text)

    assert panel, "no vendor rows parsed out of the panel"
    assert robots, "no user-agent groups parsed out of robots.txt"

    disagreements = []
    for vendor, panel_policy in panel.items():
        if vendor not in robots:
            continue
        served = robots[vendor]
        # `meter` renders Allow and behaves as allow until the limiter
        # consumes it — documented in the 2.7.0 W2 notes.
        expected = "allow" if panel_policy == "meter" else panel_policy
        if expected != served:
            disagreements.append(f"{vendor}: panel={panel_policy} robots.txt={served}")

    assert not disagreements, (
        "the panel and this app's own robots.txt disagree — the panel exists "
        f"precisely because it cannot: {disagreements}"
    )


def test_every_robots_token_maps_back_to_a_panel_row(client, token):
    """The other direction, via the registry — no rule is invisible policy.

    Not a one-row-per-User-agent-group comparison: a vendor may publish
    SEVERAL robots tokens under one identity (Omgili ships `Omgilibot` and
    `Omgili`, both emitted since 1.x, both substring-matched by the single UA
    token `omgili`). The panel renders one row per VENDOR, so the honest
    check walks the registry's token lists and asserts every served group
    resolves to a vendor the panel shows — and that its verdict agrees.
    """
    from dash_improve_my_llms.vendors import VENDORS

    panel = _panel_vendor_policies(_unescape(_panel(client).text))
    robots = _robots_verdicts(client.get("/robots.txt").text)

    token_to_vendor = {}
    for vendor in VENDORS:
        for robots_token in getattr(vendor, "robots_tokens", ()):
            token_to_vendor[robots_token] = vendor.display

    unknown, disagreements = [], []
    for agent, served in robots.items():
        if agent == "*":
            continue
        display = token_to_vendor.get(agent)
        if display is None:
            unknown.append(agent)
            continue
        if display not in panel:
            unknown.append(f"{agent} -> {display} (vendor absent from panel)")
            continue
        expected = "allow" if panel[display] == "meter" else panel[display]
        if expected != served:
            disagreements.append(
                f"{agent} (vendor {display}): panel={panel[display]} "
                f"robots.txt={served}")

    assert not unknown, (
        f"robots.txt publishes User-agent groups with no registry vendor "
        f"behind them: {unknown}. The middleware classifies from the "
        "registry, so a token only robots.txt knows about is a promise "
        "nothing enforces."
    )
    assert not disagreements, (
        f"a served rule disagrees with the panel: {disagreements}")


def test_a_multi_token_vendor_is_enforced_under_every_token_it_publishes(client):
    """The Omgili shape, checked rather than assumed.

    robots.txt publishes `Omgilibot` AND `Omgili`; the registry carries one
    UA token, `omgili`, and relies on substring matching to cover both. If
    that ever stopped holding, robots.txt would keep promising a block the
    middleware no longer delivers — the exact drift W1 exists to prevent.
    """
    from dash_improve_my_llms.bot_detection import get_bot_vendor

    # get_bot_vendor returns the registry KEY, not the Vendor object.
    for ua in ("Omgilibot/0.1", "Omgili/0.1", "omgilibot",
               "Mozilla/5.0 (compatible; Omgilibot/0.1; +http://webz.io/bot.html)"):
        assert get_bot_vendor(ua) == "omgili", (
            f"{ua!r} classified as {get_bot_vendor(ua)!r} — robots.txt "
            "publishes a Disallow for this token, so a miss here is a "
            "published promise nothing enforces"
        )


def _unescape(html: str) -> str:
    import html as _h

    return _h.unescape(html)


# ---------------------------------------------------------------------------
# The live per-host geo check PANEL.md mandates
# ---------------------------------------------------------------------------

def test_the_panel_names_the_header_that_resolved_the_country(client, token):
    """GEO.md makes this the check to run BEFORE trusting a denylist."""
    body = _panel_text(client, **{"CF-IPCountry": "DE"})
    assert "DE (via cf-ipcountry)" in body, (
        "the panel did not report the resolved country and its header — this "
        "line is the live per-host check that says whether geo works here "
        f"at all. Got: {body[body.find('Geo guardrail'):][:400]!r}"
    )


def test_the_panel_says_unknown_when_no_edge_header_is_present(client, token):
    """A DNS-only host: geo ships inert and the panel must say so."""
    body = _panel_text(client)
    geo = body[body.index("Geo guardrail"):]
    assert "unknown" in geo.lower()


def test_the_panel_reports_the_callable_denylist_source(client, token):
    """An operator must be able to tell a live seam from a frozen list."""
    body = _panel_text(client)
    geo = body[body.index("Geo guardrail"):body.index("Rate limiting")]
    assert "geo_deny" in geo, (
        "the panel does not name the callable backing the denylist, so it "
        f"cannot say whether the control board can change it: {geo[:300]!r}"
    )


# ---------------------------------------------------------------------------
# Geo beats the panel — "451 on everything" includes the operator
# ---------------------------------------------------------------------------

def test_a_denied_country_gets_451_even_with_the_right_token(app_module, client, token):
    from lib import policy_store

    try:
        app_module.configure_geo(deny_countries=["RU"])
        r = _panel(client, TOKEN, **{"CF-IPCountry": "RU"})
        assert r.status == 451, (
            f"the panel answered {r.status} to a denied country — '451 on "
            "everything' includes the operator standing in one"
        )
        assert r.header("Cache-Control") == "no-store"
    finally:
        app_module.configure_geo(
            deny_countries=policy_store.geo_deny,
            unknown=policy_store.geo_unknown(),
            exempt_paths=("/healthz", "/health", "/livez", "/readyz"),
        )


def test_geo_denies_the_panel_before_the_token_is_even_checked(app_module, client,
                                                              no_token):
    """Ordering matters: a 404 here would leak that geo runs after the gate."""
    from lib import policy_store

    try:
        app_module.configure_geo(deny_countries=["RU"])
        r = _panel(client, "wrong", **{"CF-IPCountry": "RU"})
        assert r.status == 451, f"expected 451 before the token gate, got {r.status}"
    finally:
        app_module.configure_geo(
            deny_countries=policy_store.geo_deny,
            unknown=policy_store.geo_unknown(),
            exempt_paths=("/healthz", "/health", "/livez", "/readyz"),
        )


# ---------------------------------------------------------------------------
# Read-only, and the app is unchanged by a panel render
# ---------------------------------------------------------------------------

def test_rendering_the_panel_changes_nothing(app_module, client, token):
    """The read-only decision, checked rather than trusted."""
    before = app_module._geo.effective_policy()
    robots_before = client.get("/robots.txt").text

    _panel(client)

    assert app_module._geo.effective_policy() == before
    assert client.get("/robots.txt").text == robots_before


def test_the_panel_is_get_only(client, token):
    r = client.post(PANEL, json={}, headers={"X-LLMS-Panel-Token": TOKEN})
    assert r.status != 200, (
        "the panel answered a POST — it is documented read-only, and a "
        "write-capable endpoint behind one token is a remote policy override"
    )


def test_the_footer_names_the_serving_worker(client, token):
    """pid + boot time: values that flip between refreshes mean workers
    booted with different code or env."""
    body = _panel_text(client)
    assert str(os.getpid()) in body, "the panel does not name the serving pid"

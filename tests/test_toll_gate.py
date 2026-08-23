"""W4, W5 and W6 of 2.7.0 — the rate contract, the dark 402 seam, the hub.

What an application can actually reach of the agent toll gate:

* **W4** — `rate_limit_per_minute`: 429 + `Retry-After` for bot traffic over
  the ceiling on the CORPUS routes only, keyed on the edge-header client IP,
  and failing open on absolutely anything.
* **W5** — the 402 seam shipped DARK. With `metering=False` (the default) a
  `priced` verdict degrades to `gated`: nothing is published, nothing is
  charged. That degrade is the whole safety property, so it is what gets
  tested here rather than the priced path.
* **W6** — bulletin policy keys, where the hub may only ever TIGHTEN, and a
  payload carrying anything shaped like a pay-to address is refused whole.

The ceiling is read from `app._llms_config` per request, so these tests set
it on the live config and put it back — no reboot, and it exercises the same
attribute the middleware reads.
"""
from __future__ import annotations

import pytest

from conftest import requires_dimll_27

# Every assertion in this module is about the 2.7.0 surface. On the
# pinned 2.6.1 floor the whole file skips rather than fails.
pytestmark = requires_dimll_27

from conftest import BROWSER_UA, CRAWLER_UA

BOT_UA = "PerplexityBot/1.0"
CORPUS = ("/llms.txt", "/llms-small.txt", "/llms-full.txt")
POLICY = ("/robots.txt", "/sitemap.xml")


@pytest.fixture
def ceiling(app_module):
    """Set `rate_limit_per_minute` for one test and restore it after."""
    config = app_module.app._llms_config
    original = getattr(config, "rate_limit_per_minute", None)

    def _apply(value):
        config.rate_limit_per_minute = value
        _reset_buckets()
        return value

    yield _apply
    config.rate_limit_per_minute = original
    _reset_buckets()


def _reset_buckets():
    from dash_improve_my_llms import _rate_limit

    for name in ("reset", "_reset"):
        fn = getattr(_rate_limit, name, None)
        if callable(fn):
            fn()
            return
    for name in ("_buckets", "_windows", "_hits"):
        store = getattr(_rate_limit, name, None)
        if isinstance(store, dict):
            store.clear()


def _fetch(client, path, ip, ua=BOT_UA):
    return client.get(path, user_agent=ua, headers={"CF-Connecting-IP": ip})


# ---------------------------------------------------------------------------
# W4 — the rate contract
# ---------------------------------------------------------------------------

def test_unset_ceiling_never_limits(client):
    """The default. An un-opted host is byte-identical."""
    for _ in range(40):
        assert _fetch(client, "/llms.txt", "203.0.113.9").status == 200


def test_a_bot_over_the_ceiling_gets_429_with_retry_after(client, ceiling):
    ceiling(3)
    ip = "203.0.113.10"
    statuses = [_fetch(client, "/llms.txt", ip).status for _ in range(8)]

    assert 429 in statuses, f"the ceiling never engaged: {statuses}"
    assert statuses[0] == 200, "the very first request was limited"

    limited = _fetch(client, "/llms.txt", ip)
    assert limited.status == 429
    assert limited.header("Retry-After"), "429 with no Retry-After"
    assert limited.header("Retry-After").isdigit(), (
        f"Retry-After={limited.header('Retry-After')!r} is not a delta-seconds value"
    )
    assert limited.header("Cache-Control") == "no-store", (
        "a cached 429 would keep serving after the window closed"
    )


def test_the_429_body_states_the_conduct_rule(client, ceiling):
    """W3's rule, machine-readably: one full fetch beats N per-page fetches."""
    ceiling(2)
    ip = "203.0.113.11"
    for _ in range(6):
        r = _fetch(client, "/llms.txt", ip)
    assert r.status == 429
    assert "llms-full.txt" in r.text, (
        f"the 429 does not tell the agent what to do instead: {r.text!r}"
    )
    assert "Retry-After" in r.text or "back off" in r.text


def test_humans_are_never_limited(client, ceiling):
    """The stampede is an agent failure mode."""
    ceiling(2)
    ip = "203.0.113.12"
    for _ in range(15):
        assert _fetch(client, "/llms.txt", ip, ua=BROWSER_UA).status == 200


@pytest.mark.parametrize("path", POLICY)
def test_policy_routes_are_never_limited(client, ceiling, path):
    """RFC 9309 reads an unreadable robots.txt as 'no rules at all' — a
    limited policy route would delete the very rules it announces."""
    ceiling(2)
    ip = "203.0.113.13"
    for _ in range(15):
        assert _fetch(client, path, ip).status == 200, f"{path} was rate-limited"


def test_the_limiter_keys_on_the_client_ip(client, ceiling):
    """One noisy agent must not lock out everybody else."""
    ceiling(3)
    for _ in range(8):
        _fetch(client, "/llms.txt", "203.0.113.20")
    assert _fetch(client, "/llms.txt", "203.0.113.20").status == 429

    assert _fetch(client, "/llms.txt", "203.0.113.21").status == 200, (
        "a different client IP inherited another client's bucket"
    )


def test_the_limiter_fails_open_when_it_raises(client, ceiling, monkeypatch):
    """The one place the package's fail-closed instinct is wrong."""
    from dash_improve_my_llms import _rate_limit

    ceiling(1)

    def explode(*args, **kwargs):
        raise RuntimeError("bucket table corrupt")

    monkeypatch.setattr(_rate_limit, "check", explode)
    for _ in range(10):
        r = _fetch(client, "/llms.txt", "203.0.113.30")
        assert r.status == 200, (
            "a limiter exception black-holed the corpus — refusing to serve "
            "documents is strictly worse than serving too many"
        )


def test_a_zero_or_negative_ceiling_does_not_limit(client, ceiling):
    """run.py maps <=0 to None; check the package agrees rather than
    treating 0 as 'nothing allowed'."""
    for value in (0, None):
        ceiling(value)
        for _ in range(6):
            assert _fetch(client, "/llms.txt", "203.0.113.40").status == 200


def test_pages_are_not_corpus_routes(client, ceiling):
    """The ceiling is scoped to the corpus; ordinary pages are untouched."""
    ceiling(2)
    ip = "203.0.113.50"
    for _ in range(10):
        assert _fetch(client, "/", ip, ua=CRAWLER_UA).status == 200


# ---------------------------------------------------------------------------
# W5 — the 402 seam, DARK
# ---------------------------------------------------------------------------

def test_metering_is_off_by_default(app_module):
    from dash_improve_my_llms import access

    assert access.metering_enabled() is False, (
        "metering is ON — a billing bug could now publish an offer or charge"
    )


def test_a_priced_verdict_degrades_to_gated_with_metering_off(monkeypatch):
    """The safety property: off, `priced` can neither publish nor charge."""
    from dash_improve_my_llms import access

    monkeypatch.setattr(access._config, "check", lambda path: access.PRICED)
    assert access.metering_enabled() is False

    resolved = access.resolve("/anything")
    assert resolved != access.PRICED, (
        "a priced verdict survived with metering off — that is the seam "
        "being live when it is documented dark"
    )
    assert resolved == access.GATED


def test_the_degrade_is_real_and_not_a_verdict_that_never_arrives(monkeypatch):
    """Guards the test above against passing for the wrong reason.

    `resolve` returns early for any verdict in `_VERDICTS`, and the priced
    degrade sits AFTER that check — so if PRICED were ever added to
    `_VERDICTS` the degrade would become dead code and the seam would
    silently go live. Turning metering on must make PRICED survive.
    """
    from dash_improve_my_llms import access

    assert access.PRICED not in access._VERDICTS, (
        "PRICED joined _VERDICTS — resolve() now returns it before reaching "
        "the metering check, so the 402 seam is live regardless of the flag"
    )

    monkeypatch.setattr(access._config, "check", lambda path: access.PRICED)
    try:
        access.set_metering(True)
        assert access.resolve("/anything") == access.PRICED, (
            "with metering ON a priced verdict still degraded — the flag "
            "does nothing and the degrade above proves nothing"
        )
    finally:
        access.set_metering(False)

    assert access.metering_enabled() is False


def test_no_surface_answers_402_with_metering_off(client):
    paths = ("/", "/reference/access", *CORPUS, *POLICY,
             "/reference/access/llms.txt")
    for path in paths:
        for ua in (BROWSER_UA, CRAWLER_UA, BOT_UA):
            status = client.get(path, user_agent=ua).status
            assert status != 402, f"{path} answered 402 to {ua} with metering off"


def test_the_package_holds_no_pay_to_address(app_module):
    """The package never computes a price and never holds an address."""
    from dash_improve_my_llms import access

    for name in dir(access):
        assert "pay_to" not in name.lower(), f"access.{name} looks like an address"


# ---------------------------------------------------------------------------
# W6 — the hub may only tighten
# ---------------------------------------------------------------------------

def _policies_with_bulletin(monkeypatch, payload, config):
    from dash_improve_my_llms import bulletin, vendors

    monkeypatch.setattr(bulletin, "get_bulletin", lambda: payload)
    return vendors.effective_policies(config)


def test_the_hub_can_tighten_a_vendor(monkeypatch, app_module):
    from dash_improve_my_llms import RobotsConfig

    config = RobotsConfig()  # throwaway; never assigned to the app
    before = _policies_with_bulletin(monkeypatch, None, config)
    assert before["perplexitybot"] == "allow"

    after = _policies_with_bulletin(
        monkeypatch,
        {"network": {"crawler_policy": [{"vendor": "perplexitybot", "policy": "block"}]}},
        config,
    )
    assert after["perplexitybot"] == "block", "the hub could not tighten"


def test_the_hub_cannot_loosen_a_vendor(monkeypatch):
    """A compromised or misconfigured hub may refuse traffic, never open a
    host that chose to block."""
    from dash_improve_my_llms import RobotsConfig

    config = RobotsConfig(block_ai_training=True)
    after = _policies_with_bulletin(
        monkeypatch,
        {"network": {"crawler_policy": [{"vendor": "claudebot", "policy": "allow"}]}},
        config,
    )
    assert after["claudebot"] == "block", (
        "the hub LOOSENED a local block — a hub compromise would open every "
        "site in the network"
    )


def test_the_hub_cannot_loosen_a_local_vendor_override(monkeypatch):
    from dash_improve_my_llms import RobotsConfig

    config = RobotsConfig(vendor_policy={"googlebot": "block"})
    after = _policies_with_bulletin(
        monkeypatch,
        {"network": {"crawler_policy": [{"vendor": "googlebot", "policy": "allow"}]}},
        config,
    )
    assert after["googlebot"] == "block"


def test_a_broken_bulletin_changes_nothing(monkeypatch):
    from dash_improve_my_llms import RobotsConfig, bulletin, vendors

    config = RobotsConfig()
    baseline = vendors.effective_policies(config)

    def explode():
        raise RuntimeError("hub unreachable")

    monkeypatch.setattr(bulletin, "get_bulletin", explode)
    assert vendors.effective_policies(config) == baseline, (
        "a bulletin failure changed local policy — it is optional plumbing"
    )


@pytest.mark.parametrize("payload", [
    {"network": {"pay_to": "bc1qexample"}},
    {"network": {"prices": [{"path": "/", "price": "1", "wallet": "0xdead"}]}},
    {"network": {"payto": "acct:1234"}},
    {"recipient": "someone@example.com"},
    {"network": {"nested": {"deep": {"pay-to": "x"}}}},
])
def test_a_bulletin_carrying_an_address_is_refused_whole(payload):
    """Not sanitized — refused. A fetched address is a payment-redirection
    target, and a partially-accepted payload is the exploitable shape."""
    from dash_improve_my_llms.bulletin import PayToAddressRefused, _refuse_addresses

    with pytest.raises(PayToAddressRefused):
        _refuse_addresses(payload)


def test_an_ordinary_bulletin_is_accepted():
    """The control — the refusal must not reject everything."""
    from dash_improve_my_llms.bulletin import _refuse_addresses

    _refuse_addresses({
        "network": {
            "crawler_policy": [{"vendor": "gptbot", "policy": "block"}],
            "rate_limit": 30,
            "prices": [{"path": "/llms-full.txt", "price": "0.01 USD"}],
        }
    })


def test_the_hub_rate_limit_only_tightens(client, ceiling, monkeypatch):
    """min() on the ceiling, and a ceiling where none existed is tighter."""
    from dash_improve_my_llms import bulletin

    ceiling(100)
    monkeypatch.setattr(
        bulletin, "get_bulletin",
        lambda: {"network": {"rate_limit": 2}},
    )
    _reset_buckets()
    ip = "203.0.113.60"
    statuses = [_fetch(client, "/llms.txt", ip).status for _ in range(8)]
    assert 429 in statuses, (
        f"the hub's tighter ceiling was ignored (local=100, hub=2): {statuses}"
    )


def test_the_hub_cannot_raise_the_local_rate_ceiling(client, ceiling, monkeypatch):
    from dash_improve_my_llms import bulletin

    ceiling(2)
    monkeypatch.setattr(
        bulletin, "get_bulletin",
        lambda: {"network": {"rate_limit": 10_000}},
    )
    _reset_buckets()
    ip = "203.0.113.61"
    statuses = [_fetch(client, "/llms.txt", ip).status for _ in range(10)]
    assert 429 in statuses, (
        f"the hub RAISED this host's ceiling — it may only tighten: {statuses}"
    )

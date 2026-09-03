"""The network's internal-traffic contract — the analytics point of truth.

The rule (https://2plot.ai/docs/satellite-analytics, "Internal traffic"): a
request whose User-Agent contains `2plot-internal` is 2plot machinery talking
to itself — the hub's hourly health sweep, CI smoke batteries, the 4x-daily
heartbeat, cross-app calls — and is counted NOWHERE. Dropped at write time,
before device detection and before bot classification. `/healthz` is never a
visit either.

Both halves are tested here, because a contract kept on only one side is not
kept at all:

*inbound*   token-carrying requests never reach the ledger, and therefore
            never reach `human_hits` / `bot_hits` in the hourly rollup this
            app POSTs to 2plot.ai;
*outbound*  every call this host makes to another network host sends
            `INTERNAL_UA`, so the far side can apply the same rule. That half
            was missing: the ad client fetched a campaign from 2plot.dev on
            every single docs page view, arriving as `python-requests/2.x`,
            and the hub counted this satellite's readers as its own bots.
"""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from conftest import BROWSER_UA, CRAWLER_UA
from lib.analytics_tracker import analytics_path, tracker
from lib.constants import INTERNAL_UA, INTERNAL_UA_TOKEN, internal_ua

# A real page. `lib/traffic_rollup` drops infrastructure paths (`/llms.txt`,
# `/robots.txt`, `/healthz`, ...) at read time, so a rollup assertion made
# against one of those would pass no matter what the tracker did.
PAGE = "/reference/configuration"

# The READ table is written only for corpus documents the package serves
# (`on_document_read`), never for a browser page — so the reads-side pins
# below must ask for a machine surface, not PAGE.
LLMS_DOC_PATH = "/llms.txt"

# A real vendor, NOT carrying the internal token: the positive control for
# the reads pins. In-process only — never send this at a live host, which
# would write an unverified vendor row into a real ledger.
VENDOR_UA = ("Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; "
             "GPTBot/1.2; +https://openai.com/gptbot)")


def _ledger_visits():
    """Every hit on disk, flushing the write buffer first."""
    tracker.flush()
    try:
        with open(analytics_path()) as f:
            return json.load(f).get("visits", [])
    except FileNotFoundError:
        return []


def _ledger_reads():
    """Every READ row on disk, flushing first — the second table (1.6.34)."""
    tracker.flush()
    try:
        with open(analytics_path()) as f:
            return json.load(f).get("reads", [])
    except FileNotFoundError:
        return []


def _rollup():
    """Today's rollup as the hub would receive it, or an all-zero stand-in."""
    from lib.traffic_rollup import daily_rollup

    tracker.flush()
    return daily_rollup("boilerplate", datetime.now().date()) or {
        "human_hits": 0, "bot_hits": 0,
    }


# --------------------------------------------------------------- the token --


def test_token_is_the_network_wide_string():
    """The contract only works if every host agrees on the byte sequence."""
    assert INTERNAL_UA_TOKEN == "2plot-internal"
    assert INTERNAL_UA_TOKEN in INTERNAL_UA
    assert INTERNAL_UA.startswith(INTERNAL_UA_TOKEN)


def test_caller_suffix_never_breaks_the_token():
    ua = internal_ua("traffic-reporter")
    assert INTERNAL_UA_TOKEN in ua
    assert ua.endswith("traffic-reporter")
    assert internal_ua() == INTERNAL_UA
    assert internal_ua("  ") == INTERNAL_UA


# ------------------------------------------------------------------ inbound --


def test_the_tests_can_see_the_ledger_at_all(client, tmp_state_dir):
    """Guard for every delta assertion below.

    If the ledger path were wrong (or the suite were writing into the repo's
    own visitor_analytics.json), every "count did not change" test would pass
    vacuously. Prove a write lands first.
    """
    assert str(analytics_path()).startswith(tmp_state_dir), analytics_path()
    before = len(_ledger_visits())
    client.get(PAGE, user_agent=BROWSER_UA)
    assert len(_ledger_visits()) == before + 1


def test_internal_ua_is_counted_nowhere(client):
    before = len(_ledger_visits())
    client.get(PAGE, user_agent=internal_ua("network-smoke"))
    client.get("/", user_agent=INTERNAL_UA)
    assert len(_ledger_visits()) == before


def test_a_crawler_shaped_probe_carrying_the_token_stays_internal(client):
    """The battery's crawler probe exercises the bot path deliberately.

    It must still not be counted. This is precisely why the drop happens
    before `detect_device_type` — classification would file it under `bot`.
    """
    before = len(_ledger_visits())
    client.get(PAGE, user_agent=f"{CRAWLER_UA} {INTERNAL_UA}")
    assert len(_ledger_visits()) == before


def test_internal_ua_is_counted_nowhere_in_the_READ_table(client):
    """"Counted nowhere" includes the read table (1.6.43 item 1, note 83a).

    `track_visit` has dropped the token since this contract existed;
    `record_read` — the `on_document_read` hook the 2.8.0 floor added —
    did not, so the hub's health sweep, every satellite's link audit and
    every post-deploy battery were landing in `reads`. Measured on this
    host before the fix: one token-carrying probe wrote one row,
    vendor_key None, crawler lane, which made the network's own probes
    the busiest unidentified vendor on this board.

    BOTH DIRECTIONS IN ONE TEST, deliberately: a drop that dropped
    everything would pass the first assertion alone, and this round has
    learned not to trust a bare negative. The counts are in the failure
    messages for the same reason.
    """
    before = len(_ledger_reads())
    client.get(LLMS_DOC_PATH, user_agent=internal_ua("network-smoke"))
    client.get(LLMS_DOC_PATH, user_agent=f"{CRAWLER_UA} {INTERNAL_UA}")
    after = len(_ledger_reads())
    assert after == before, (
        f"internal traffic reached the read table: {before} -> {after}"
    )

    # ... and the table is still reachable, so the assertion above is not
    # passing because nothing can ever be written.
    client.get(LLMS_DOC_PATH, user_agent=VENDOR_UA)
    real = len(_ledger_reads())
    assert real == after + 1, (
        f"a real crawler wrote {real - after} read rows, expected 1 — the "
        "drop is dropping everything and the pin above is vacuous"
    )


def test_the_read_drop_keys_on_the_packages_own_field_name(client):
    """`EVENT_FIELDS` calls it `ua`; the visits row calls it `user_agent`.

    Keying the drop on the wrong name is silently a no-op — item 1's own
    failure mode. Verified against the wheels this host can run: `ua` is
    in EVENT_FIELDS at 2.8.0 (local), 2.9.0 (production) and 2.9.4 (what
    CI resolves from the >=2.8.0 floor), and `user_agent` is in none of
    them.
    """
    from dash_improve_my_llms._ledger import EVENT_FIELDS

    assert "ua" in EVENT_FIELDS
    assert "user_agent" not in EVENT_FIELDS


def test_the_token_is_matched_case_insensitively(client):
    before = len(_ledger_visits())
    client.get(PAGE, user_agent="2PLOT-INTERNAL/1.0 Health-Sweep")
    assert len(_ledger_visits()) == before


def test_healthz_is_never_a_visit(client):
    before = len(_ledger_visits())
    client.get("/healthz", user_agent="Render/1.0 health-check")
    client.get("/healthz", user_agent=BROWSER_UA)
    assert len(_ledger_visits()) == before


# ----------------------------------------------- the reported numbers -------
#
# The exclusion that actually matters. Everything above is about the ledger;
# this is about what 2plot.ai charts.


def test_internal_traffic_is_absent_from_human_hits_and_bot_hits(client):
    before = _rollup()

    # Four calls that are all machinery, in the two shapes the network sends:
    # a plain internal UA, and a crawler-shaped probe carrying the token.
    for _ in range(2):
        client.get(PAGE, user_agent=internal_ua("network-smoke"))
        client.get(PAGE, user_agent=f"{CRAWLER_UA} {INTERNAL_UA}")

    after = _rollup()
    assert after["human_hits"] == before["human_hits"], (
        "internal traffic reached human_hits — the hub would chart the health "
        "sweep as readers of these docs"
    )
    assert after["bot_hits"] == before["bot_hits"], (
        "internal traffic reached bot_hits — the hub would chart CI as crawler "
        "interest"
    )


def test_real_traffic_is_still_counted(client):
    """The exclusions must not have lobotomised the tracker.

    A rule that drops everything also satisfies every assertion above, so the
    positive case is load-bearing: one browser hit is one human, one Googlebot
    hit is one bot.
    """
    before = _rollup()
    client.get(PAGE, user_agent=BROWSER_UA)
    client.get(PAGE, user_agent=CRAWLER_UA)
    after = _rollup()

    assert after["human_hits"] == before["human_hits"] + 1
    assert after["bot_hits"] == before["bot_hits"] + 1


# ----------------------------------------------------------------- outbound --


class _Captured(Exception):
    """Abort the request once the headers have been seen."""


def _capture_headers(monkeypatch, module, attr="post"):
    """Record the headers of the next outbound call, then abort it."""
    seen = {}

    def fake(*args, **kwargs):
        seen.update(kwargs.get("headers") or {})
        raise _Captured

    monkeypatch.setattr(module, attr, fake)
    return seen


def test_the_traffic_rollup_post_sends_the_token(monkeypatch):
    import requests

    from lib import satellite_reporter

    seen = _capture_headers(monkeypatch, requests, "post")
    ok, _detail = satellite_reporter.post_rollup(
        {"app": "boilerplate", "date": "2026-07-31"}, secret="test-secret"
    )
    assert ok is False  # the fake raised; we only wanted the headers
    assert INTERNAL_UA_TOKEN in seen.get("User-Agent", "")


def test_hub_client_calls_send_the_token(monkeypatch):
    import requests

    from lib import hub_client

    monkeypatch.setenv("CROSS_APP_WEBHOOK_SECRET", "test-secret")
    seen = _capture_headers(monkeypatch, requests, "post")
    assert hub_client._post("/api/agent-key/verify", {"key": "x"}, 1.0) is None
    assert INTERNAL_UA_TOKEN in seen.get("User-Agent", "")


def test_the_ad_fetch_sends_the_token(monkeypatch):
    """One call per docs page view — the loudest of the three."""
    from lib import ad_client

    seen = _capture_headers(monkeypatch, ad_client._session, "get")
    monkeypatch.setattr(ad_client, "_last_failure", 0.0)
    assert ad_client.fetch_ad("/reference/configuration") is None
    assert INTERNAL_UA_TOKEN in seen.get("User-Agent", "")


@pytest.mark.parametrize("script", ["smoke_live", "audit_links", "network_smoke"])
def test_every_battery_script_sends_the_token(script):
    """A post-deploy battery sweeps every peer; it must not register anywhere."""
    import importlib.util

    from conftest import REPO_ROOT

    spec = importlib.util.spec_from_file_location(
        f"_ua_{script}", REPO_ROOT / "scripts" / f"{script}.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    agents = [
        value
        for name, value in vars(module).items()
        if (name == "UA" or name.endswith("_UA")) and isinstance(value, str)
    ]
    assert agents, f"scripts/{script}.py declares no User-Agent constant"
    missing = [ua for ua in agents if INTERNAL_UA_TOKEN not in ua]
    assert missing == [], f"scripts/{script}.py sends untokened UAs: {missing}"

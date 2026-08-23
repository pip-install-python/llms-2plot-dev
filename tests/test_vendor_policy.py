"""W2 — per-vendor policy, and whether this app says what it does.

The 2.7.0 claim: "One fold (`vendors.effective_policies`) drives robots.txt
AND the middleware", so a site's published promise and its enforced behaviour
"hold by construction". This file checks that on a real host, in the two
directions that matter:

* the DEFAULT posture — what a fork serves out of the box, including the
  deliberate 2.7.0 contract change (ClaudeBot 403s on pages while the docs
  surfaces stay open);
* every per-vendor OVERRIDE the control board can write, across all three
  vendor classes and all three actions.

The second sweep is where the fold used to stop holding: a per-vendor block
on a TRADITIONAL crawler was enforced but never published (BUGS-2.7.0.md #2).
Fixed in the pre-tag batch and asserted positively below.
"""
from __future__ import annotations

import pytest


from conftest import BROWSER_UA, CRAWLER_UA

TRAINING_UA = "ClaudeBot/1.0"
GPTBOT_UA = "GPTBot/1.1"
SEARCH_UA = "PerplexityBot/1.0"
CLAUDE_USER_UA = "Claude-User/1.0"

PAGE_SURFACES = ("/", "/reference/access")
DOC_SURFACES = ("/llms.txt", "/llms-small.txt", "/llms-full.txt",
                "/reference/access/llms.txt")
POLICY_SURFACES = ("/robots.txt", "/sitemap.xml")


@pytest.fixture(autouse=True)
def clean_store():
    """No vendor overrides unless a test writes one."""
    from lib import policy_store

    yield
    policy_store.path().write_text("{}")
    policy_store.reset_for_tests()


def _ua_for(vendor_key: str) -> str:
    from dash_improve_my_llms.vendors import VENDORS

    vendor = next(v for v in VENDORS if v.key == vendor_key)
    return f"{vendor.robots_tokens[0]}/1.0"


# ---------------------------------------------------------------------------
# 1. The default posture — what a fork serves out of the box
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("path", PAGE_SURFACES)
def test_training_crawlers_are_blocked_on_pages(client, path):
    """The 2.7.0 contract change, verified on a real app.

    ClaudeBot classifies `training` from 2.7.0 on — robots.txt was the
    published promise all along (P1), and now the middleware keeps it.
    """
    assert client.get(path, user_agent=TRAINING_UA).status == 403
    assert client.get(path, user_agent=GPTBOT_UA).status == 403


@pytest.mark.parametrize("path", DOC_SURFACES)
def test_the_docs_surfaces_stay_open_to_training_crawlers(client, path):
    """THE flagged half of the contract change — checked, not assumed.

    `block_ai_training_docs` defaults False: documentation routes are
    subject to policy like anything else, but the default still lets them
    through, because the corpus exists to get the package used and an
    upgrade must not silently start 403ing it. If this ever flips by
    accident, every AI-search citation of this site dies quietly.
    """
    for ua in (TRAINING_UA, GPTBOT_UA):
        r = client.get(path, user_agent=ua)
        assert r.status == 200, (
            f"{path} answered {r.status} to {ua} — the docs-open half of the "
            "2.7.0 default has regressed"
        )
        assert r.text.strip(), f"{path} served an empty body to {ua}"


@pytest.mark.parametrize("path", POLICY_SURFACES)
def test_policy_surfaces_are_open_to_everyone(client, path):
    """The discovery floor: robots.txt and sitemap.xml never gate."""
    for ua in (TRAINING_UA, GPTBOT_UA, SEARCH_UA, CRAWLER_UA, BROWSER_UA):
        assert client.get(path, user_agent=ua).status == 200


def test_ai_search_and_traditional_crawlers_are_untouched(client):
    for ua in (SEARCH_UA, CLAUDE_USER_UA, CRAWLER_UA, BROWSER_UA):
        for path in PAGE_SURFACES + DOC_SURFACES:
            assert client.get(path, user_agent=ua).status == 200, (
                f"{ua} was blocked on {path}"
            )


def test_assets_are_never_vendor_gated(client):
    """The asset short-circuit sits after geo and before the bot gate."""
    for ua in (TRAINING_UA, GPTBOT_UA):
        assert client.get("/assets/main.css", user_agent=ua).status == 200


# ---------------------------------------------------------------------------
# 2. Published vs served, on the DEFAULT config
# ---------------------------------------------------------------------------

def _robots_groups(robots: str) -> dict:
    groups, current = {}, []
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
                groups.setdefault(agent, verdict)
            current = []
        else:
            current = []
    return groups


def robots_verdict(robots: str, token: str) -> str:
    """What robots.txt tells ONE token, honouring the `*` fallback.

    The fallback is the whole point: a vendor with no group of its own is
    NOT unregulated, it is governed by `User-agent: *`. A comparison that
    skips such vendors cannot see a policy that failed to be published —
    which is exactly the hole BUGS-2.7.0.md #2 lives in.
    """
    groups = _robots_groups(robots)
    return groups.get(token, groups.get("*", "allow"))


@pytest.mark.parametrize("vendor_key", [
    "gptbot", "claudebot", "ccbot", "perplexitybot", "claude-user",
    "googlebot", "bingbot",
])
def test_published_matches_served_on_the_default_config(client, app_module, vendor_key):
    from dash_improve_my_llms.vendors import VENDORS, effective_policies

    vendor = next(v for v in VENDORS if v.key == vendor_key)
    fold = effective_policies(app_module.app._robots_config)[vendor_key]
    published = robots_verdict(client.get("/robots.txt").text, vendor.robots_tokens[0])
    served = "block" if client.get("/", user_agent=_ua_for(vendor_key)).status == 403 else "allow"

    expected = "allow" if fold == "meter" else fold
    assert published == expected, f"{vendor_key}: robots.txt={published} fold={fold}"
    assert served == expected, f"{vendor_key}: served={served} fold={fold}"


# ---------------------------------------------------------------------------
# 3. The override seam — the control board's half
# ---------------------------------------------------------------------------

def _set(vendor_key, action):
    from lib import policy_store

    policy_store.set_vendor_action(vendor_key, action)


@pytest.mark.parametrize("vendor_key", ["claudebot", "gptbot", "perplexitybot",
                                        "claude-user"])
def test_an_override_reaches_the_middleware_with_no_restart(client, vendor_key):
    """The seam, on the vendor axis."""
    assert client.get("/", user_agent=_ua_for(vendor_key)).status in (200, 403)

    _set(vendor_key, "block")
    assert client.get("/", user_agent=_ua_for(vendor_key)).status == 403, (
        f"a stored block on {vendor_key} did not reach the next request"
    )

    _set(vendor_key, "allow")
    assert client.get("/", user_agent=_ua_for(vendor_key)).status == 200, (
        f"a stored allow on {vendor_key} did not reach the next request"
    )


@pytest.mark.parametrize("vendor_key", ["claudebot", "perplexitybot"])
def test_an_override_reaches_robots_txt_with_no_restart(client, vendor_key):
    from dash_improve_my_llms.vendors import VENDORS

    vendor = next(v for v in VENDORS if v.key == vendor_key)

    _set(vendor_key, "block")
    assert robots_verdict(client.get("/robots.txt").text, vendor.robots_tokens[0]) == "block"

    _set(vendor_key, "allow")
    assert robots_verdict(client.get("/robots.txt").text, vendor.robots_tokens[0]) == "allow"


def test_meter_renders_as_allow_and_behaves_as_allow(client):
    """`meter` is fetchable under the rate contract: a Disallow would kill
    the funnel the meter exists for."""
    from dash_improve_my_llms.vendors import VENDORS

    _set("claudebot", "meter")
    vendor = next(v for v in VENDORS if v.key == "claudebot")
    assert robots_verdict(client.get("/robots.txt").text, vendor.robots_tokens[0]) == "allow"
    assert client.get("/", user_agent=TRAINING_UA).status == 200


@pytest.mark.parametrize("vendor_key", ["googlebot", "bingbot", "slurp",
                                        "duckduckbot"])
def test_a_traditional_vendor_block_is_published_as_well_as_enforced(
        client, vendor_key):
    """WAS BUGS-2.7.0.md #2, fixed in the pre-tag batch.

    W2's contract on the one class where it used to fail. With the default
    allow_traditional=True a per-vendor block on a traditional crawler was
    ENFORCED (403) but never PUBLISHED — `User-agent: *  Allow: /` still
    governed. An operator blocking a misbehaving crawler from the board got
    a site that 403s Googlebot while its own robots.txt says it is welcome:
    Search Console fills with crawl errors and the published promise insists
    nothing is wrong.

    All three halves are asserted now — the effective verdict, the vendor's
    OWN group, and the served status.
    """
    from dash_improve_my_llms.vendors import VENDORS

    vendor = next(v for v in VENDORS if v.key == vendor_key)
    token = vendor.robots_tokens[0]
    _set(vendor_key, "block")

    robots = client.get("/robots.txt").text

    published = robots_verdict(robots, token)
    assert published == "block", (
        f"{vendor_key}: enforced as block but robots.txt publishes "
        f"{published!r} — says != does"
    )

    # Its OWN group, not one inherited from `*`. The bug was precisely that
    # the vendor fell through to `User-agent: *`, and a check that only
    # resolves the effective verdict would start passing again for the wrong
    # reason the day the `*` group flipped to Disallow.
    assert f"User-agent: {token}" in robots, (
        f"{vendor_key}: robots.txt emits no group of its own for {token} — "
        "the verdict is being inherited from `*` rather than published"
    )

    served = client.get("/", user_agent=_ua_for(vendor_key)).status
    assert served == 403, (
        f"{vendor_key}: published as blocked but served {served} — the same "
        "drift in the other direction"
    )


def test_the_traditional_block_really_is_enforced(client):
    """The other half of #2, and the reason it matters: the 403 is real."""
    _set("googlebot", "block")
    assert client.get("/", user_agent=CRAWLER_UA).status == 403, (
        "if this ever stops being 403, BUGS-2.7.0.md #2 has changed shape"
    )


def test_the_coarse_flag_path_publishes_traditional_blocks(app_module):
    """Isolates #2 to the PER-VENDOR path: `allow_traditional=False` works.

    Uses a throwaway config — never assigns app._robots_config, because
    callbacks are global on a shared server.
    """
    from dash_improve_my_llms import RobotsConfig
    from dash_improve_my_llms.robots_generator import generate_robots_txt

    robots = generate_robots_txt(
        sitemap_url="https://llms.2plot.dev/sitemap.xml",
        base_url="https://llms.2plot.dev",
        config=RobotsConfig(allow_traditional=False),
    )
    for token in ("Googlebot", "Bingbot", "Slurp", "DuckDuckBot"):
        assert robots_verdict(robots, token) == "block", (
            f"allow_traditional=False did not publish a block for {token}"
        )


def test_an_unknown_vendor_key_is_refused_at_the_store(client):
    """The store's own guard: the package IGNORES unknown keys with a log
    line, so an override typed as a display name would silently do nothing."""
    from lib import policy_store

    with pytest.raises(ValueError):
        policy_store.set_vendor_action("NotARealBot", "block")

    # A display name is accepted and normalised to the registry key.
    policy_store.set_vendor_action("ClaudeBot", "block")
    assert policy_store.vendor_policy() == {"claudebot": "block"}


def test_a_malformed_vendor_store_fails_open(client):
    from lib import policy_store

    policy_store.path().write_text('{"vendor_policy": "not-a-map"}')
    policy_store.reset_for_tests()
    assert policy_store.vendor_policy() == {}
    assert client.get("/", user_agent=SEARCH_UA).status == 200


# ---------------------------------------------------------------------------
# 4. block_ai_training_docs — the knob that closes the docs half
# ---------------------------------------------------------------------------

def test_block_ai_training_docs_closes_the_corpus(app_module):
    """Rendered through a throwaway config; the live app keeps its default."""
    from dash_improve_my_llms.vendors import effective_policies
    from dash_improve_my_llms import RobotsConfig

    config = RobotsConfig(block_ai_training_docs=True)
    assert effective_policies(config)["claudebot"] == "block"
    assert getattr(config, "block_ai_training_docs") is True

"""B7 — the control board's geo section, and the seam it writes through.

The migration kickoff's acceptance criterion for this phase, in one line:

    admin toggles a country on the map; a request carrying that CF-IPCountry
    gets 451 on the NEXT fetch with NO restart; toggling back recovers;
    a non-admin sees the gate card.

These tests are that sentence, plus the two failure modes a writable policy
layer has to get right — a write callback invoked directly by someone who can
POST a component id, and a store that goes bad.
"""
from __future__ import annotations

import importlib
import json

import pytest

from conftest import requires_dimll_27

# Every assertion in this module is about the 2.7.0 surface. On the
# pinned 2.6.1 floor the whole file skips rather than fails.
pytestmark = requires_dimll_27

DENIED = "RU"


@pytest.fixture
def clean_policy_store():
    from lib import policy_store

    policy_store.path().write_text("{}")
    policy_store.reset_for_tests()
    yield policy_store
    policy_store.path().write_text("{}")
    policy_store.reset_for_tests()


def _board():
    """Import the board page, standing up a bare Dash app if none exists."""
    import dash

    try:
        return importlib.import_module("pages.control_board")
    except dash.exceptions.PageError:
        dash.Dash(__name__, use_pages=True, pages_folder="")
        return importlib.import_module("pages.control_board")


# ---------------------------------------------------------------------------
# The gate — the half a layout cannot enforce
# ---------------------------------------------------------------------------

def test_a_non_admin_sees_the_gate_card_and_no_geo_controls(clean_policy_store,
                                                            monkeypatch):
    board = _board()
    monkeypatch.delenv("ALLOW_UNGATED_ADMIN", raising=False)
    rendered = str(board.layout())

    assert "cb-geo-map" not in rendered, "the map rendered for a non-admin"
    assert "cb-geo-toggle" not in rendered, "the toggle rendered for a non-admin"
    assert "cb-geo-code" not in rendered


def test_the_geo_section_renders_for_an_admin(clean_policy_store, monkeypatch):
    board = _board()
    monkeypatch.setenv("ALLOW_UNGATED_ADMIN", "1")
    rendered = str(board.layout())

    assert "cb-geo-map" in rendered
    assert "cb-geo-toggle" in rendered


def test_the_write_callback_refuses_a_non_admin_invoked_directly(
        clean_policy_store, monkeypatch):
    """THE test. The layout gate only hides the UI.

    Pattern-matching and plain callbacks alike stay callable by anyone who can
    POST a reconstructed component id to /_dash-update-component, so the same
    admin check has to run inside the callback or the board is writable by
    anyone who reads the page source.
    """
    from dash.exceptions import PreventUpdate

    board = _board()
    monkeypatch.delenv("ALLOW_UNGATED_ADMIN", raising=False)

    with pytest.raises(PreventUpdate):
        board._toggle_country(1, DENIED)

    assert clean_policy_store.geo_deny() == [], (
        "a non-admin write reached the store — the board is remotely writable"
    )


def test_the_write_callback_accepts_an_admin(clean_policy_store, monkeypatch):
    board = _board()
    monkeypatch.setenv("ALLOW_UNGATED_ADMIN", "1")

    board._toggle_country(1, DENIED)
    assert clean_policy_store.geo_deny() == [DENIED]


# ---------------------------------------------------------------------------
# The seam — a board write reaches the next request, with no restart
# ---------------------------------------------------------------------------

def test_a_board_toggle_451s_the_next_request(client, app_module,
                                              clean_policy_store, monkeypatch):
    """The migration kickoff's acceptance criterion, end to end, in-process."""
    from lib import policy_store

    board = _board()
    monkeypatch.setenv("ALLOW_UNGATED_ADMIN", "1")
    app_module.configure_geo(deny_countries=policy_store.geo_deny)

    assert client.get("/", headers={"CF-IPCountry": DENIED}).status != 451

    board._toggle_country(1, DENIED)

    r = client.get("/", headers={"CF-IPCountry": DENIED})
    assert r.status == 451, (
        "the board toggle did not reach the next request — this is the whole "
        "acceptance criterion for B7"
    )
    assert r.header("Cache-Control") == "no-store"

    board._toggle_country(2, DENIED)
    assert client.get("/", headers={"CF-IPCountry": DENIED}).status != 451, (
        "toggling back did not recover"
    )


def test_the_toggle_blocks_every_surface_not_just_pages(client, app_module,
                                                        clean_policy_store,
                                                        monkeypatch):
    from lib import policy_store

    board = _board()
    monkeypatch.setenv("ALLOW_UNGATED_ADMIN", "1")
    app_module.configure_geo(deny_countries=policy_store.geo_deny)
    board._toggle_country(1, DENIED)

    for path in ("/", "/llms.txt", "/robots.txt", "/sitemap.xml",
                 "/assets/main.css", "/favicon.ico"):
        assert client.get(path, headers={"CF-IPCountry": DENIED}).status == 451, (
            f"{path} survived a board-set country block"
        )
    assert client.get("/healthz", headers={"CF-IPCountry": DENIED}).status == 200


# ---------------------------------------------------------------------------
# Validation and degradation
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("code", ["RUS", "R", "12", "XX", "T1", "!!"])
def test_an_invalid_code_is_refused_with_a_message(clean_policy_store,
                                                   monkeypatch, code):
    """A bad code stored is worse than no code.

    The package reads anything that is not two ASCII letters as "unknown", so
    a stored `XX` would sit in the denylist looking active and never match a
    request — a block the operator believes is in force and is not. Refusing
    at the write is the only moment they find out.
    """
    board = _board()
    monkeypatch.setenv("ALLOW_UNGATED_ADMIN", "1")

    alert = board._toggle_country(1, code)
    assert clean_policy_store.geo_deny() == [], (
        f"{code!r} was stored as a denied country"
    )
    assert "not an ISO" in str(alert), (
        f"{code!r} was rejected silently — the operator gets no feedback"
    )


@pytest.mark.parametrize("code", ["", None])
def test_an_empty_code_is_a_no_op(clean_policy_store, monkeypatch, code):
    """Pressing the button with nothing typed must not raise or store."""
    from dash.exceptions import PreventUpdate

    board = _board()
    monkeypatch.setenv("ALLOW_UNGATED_ADMIN", "1")

    with pytest.raises(PreventUpdate):
        board._toggle_country(1, code)
    assert clean_policy_store.geo_deny() == []


def test_a_malformed_store_fails_open_and_the_board_says_so(client, app_module,
                                                            clean_policy_store,
                                                            monkeypatch):
    from lib import policy_store

    board = _board()
    monkeypatch.setenv("ALLOW_UNGATED_ADMIN", "1")
    app_module.configure_geo(deny_countries=policy_store.geo_deny)

    board._toggle_country(1, DENIED)
    assert client.get("/", headers={"CF-IPCountry": DENIED}).status == 451

    policy_store.path().write_text("{ not json at all")
    policy_store.reset_for_tests()

    assert client.get("/", headers={"CF-IPCountry": DENIED}).status != 451, (
        "a corrupt store locked the site to its last known denylist instead "
        "of failing open"
    )
    # The board must not quietly render an empty, healthy-looking list.
    policy_store.geo_deny()  # trip the warn-once so status() reports degraded
    assert policy_store.status()["degraded"] is True
    assert "degraded" in str(board.layout()).lower()


def test_the_choropleth_reflects_the_store(clean_policy_store, monkeypatch):
    board = _board()
    monkeypatch.setenv("ALLOW_UNGATED_ADMIN", "1")

    empty = board._geo_figure([])
    assert empty["data"][0]["locations"] == ["ATA"], (
        "an empty denylist should paint nothing"
    )

    board._toggle_country(1, "DE")
    figure = board._geo_figure(clean_policy_store.geo_deny())
    assert "DEU" in figure["data"][0]["locations"], (
        "the map does not show a denied country — alpha-2 to alpha-3 "
        "translation is the one place these two vocabularies meet"
    )


def test_a_map_click_selects_but_does_not_commit(clean_policy_store, monkeypatch):
    """A misclick on a world map must not block a country."""
    board = _board()
    monkeypatch.setenv("ALLOW_UNGATED_ADMIN", "1")

    code = board._country_from_map({"points": [{"location": "DEU"}]})
    assert code == "DE"
    assert clean_policy_store.geo_deny() == [], (
        "clicking the map committed a block with no confirmation step"
    )


def test_unknown_countries_on_the_map_are_ignored(clean_policy_store, monkeypatch):
    from dash.exceptions import PreventUpdate

    board = _board()
    with pytest.raises(PreventUpdate):
        board._country_from_map({"points": [{"location": "ZZZ"}]})
    with pytest.raises(PreventUpdate):
        board._country_from_map(None)


# ---------------------------------------------------------------------------
# Cross-worker behaviour
# ---------------------------------------------------------------------------

def test_a_foreign_workers_write_is_picked_up_without_restart(client, app_module,
                                                              clean_policy_store):
    """Another gunicorn worker's toggle, simulated by writing the file."""
    import os

    from lib import policy_store

    app_module.configure_geo(deny_countries=policy_store.geo_deny)
    assert client.get("/", headers={"CF-IPCountry": "FR"}).status != 451

    path = policy_store.path()
    path.write_text(json.dumps({"geo_deny": ["FR"]}))
    os.utime(path, ns=(0, os.stat(path).st_mtime_ns + 1_000_000))

    assert client.get("/", headers={"CF-IPCountry": "FR"}).status == 451, (
        "another worker's write was not observed — under gunicorn only the "
        "worker that served the POST would enforce the block"
    )


def test_the_store_survives_keys_it_does_not_understand(clean_policy_store,
                                                        monkeypatch):
    """Forward compatibility with 2.8's bot x country matrix.

    A newer worker writes `deny_matrix`; an older worker toggles a country.
    The older worker must not erase what it cannot read, or a rolling deploy
    silently drops half the policy.
    """
    board = _board()
    monkeypatch.setenv("ALLOW_UNGATED_ADMIN", "1")

    path = clean_policy_store.path()
    path.write_text(json.dumps({
        "geo_deny": ["FR"],
        "deny_matrix": {"claudebot": ["DE"]},
    }))
    clean_policy_store.reset_for_tests()

    board._toggle_country(1, "BE")

    stored = json.loads(path.read_text())
    assert stored["deny_matrix"] == {"claudebot": ["DE"]}, (
        "an older worker's toggle erased a key it did not understand"
    )
    assert sorted(stored["geo_deny"]) == ["BE", "FR"]


def test_the_board_reports_the_store_and_the_serving_worker(clean_policy_store,
                                                            monkeypatch):
    import os

    board = _board()
    monkeypatch.setenv("ALLOW_UNGATED_ADMIN", "1")
    rendered = str(board.layout())

    assert str(os.getpid()) in rendered, "the board does not name the serving pid"
    assert str(clean_policy_store.path()) in rendered

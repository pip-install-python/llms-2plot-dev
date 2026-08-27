"""run.py must wire BOTH halves of dash-clerk-auth — the flexlayout class.

dash-clerk-auth splits its setup either side of ``Dash(...)``:
``register()`` loads the UI half (components, ClerkJS, appearance) and
``configure_app(app)`` registers the server half (``/api/auth/session``,
``/api/auth/signout``, the per-request identity population).

flexlayout shipped its batch-2 pass (2026-08-22) with the first call and
WITHOUT the second: every component rendered and ClerkJS reported
signed-in, while every server render read signed-out — the control board
served the owner the sign-in card forever, ``POST /api/auth/session``
answered 405 (the path fell through to Dash's GET-only page catch-all),
and sign-out never revoked. No suite could see it: Clerk is off in test
environments, and ``configure_app`` no-ops without keys, so the missing
call was indistinguishable from the deliberate no-op.

This pin is therefore STRUCTURAL — the wiring calls must exist in run.py
regardless of environment. The runtime half of the guard lives in
``scripts/smoke_live.py`` ("Auth wiring"), which proves the routes
actually answer on the deployed host.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

REQUIRED_CALLS = ("register", "configure_app")


def _module_aliases(tree: ast.Module) -> set[str]:
    """Names that ``lib.auth`` is bound to in run.py (e.g. ``_auth``)."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "lib":
            for alias in node.names:
                if alias.name == "auth":
                    names.add(alias.asname or alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "lib.auth":
                    names.add((alias.asname or alias.name).split(".")[0])
    return names


def test_run_py_calls_both_auth_wiring_halves():
    tree = ast.parse((ROOT / "run.py").read_text(encoding="utf-8"))
    aliases = _module_aliases(tree)
    assert aliases, (
        "run.py never imports lib.auth as a module — the auth stack is "
        "entirely unwired"
    )

    called: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            base = node.func.value
            if isinstance(base, ast.Name) and base.id in aliases:
                called.add(node.func.attr)

    for required in REQUIRED_CALLS:
        assert required in called, (
            f"run.py never calls {sorted(aliases)[0]}.{required}() — "
            "components without the server half (or vice versa): the site "
            "LOOKS signed in while every server render reads signed-out, "
            "auth POSTs answer 405 via the page catch-all, and sign-out "
            "never revokes. Both calls are required; see this file's "
            "docstring for the incident."
        )


def test_smoke_live_post_passes_the_ssl_context():
    """Source pin: post()'s urlopen must carry context=SSL_CONTEXT like
    fetch()'s. It shipped without it, so on any Python missing OS
    trust-store integration (macOS — the fleet's whole local-dev half)
    every auth POST died in the TLS handshake, returned 0, and the check
    accused the app of the exact configure_app regression it exists to
    detect. CI never saw it (Linux verifies fine) and no wired test can
    (they monkeypatch post) — a SOURCE pin is the only net with a mesh
    this fine. Found by flexlayout, F1 kit adoption 2026-08-24.
    """
    import re
    from pathlib import Path

    source = (
        Path(__file__).resolve().parent.parent / "scripts" / "smoke_live.py"
    ).read_text()
    calls = re.findall(r"urlopen\((?:[^)]|\n)*?\)", source)
    assert calls, "no urlopen calls found in smoke_live.py — probe rewritten?"
    naked = [c for c in calls if "context=SSL_CONTEXT" not in c]
    assert not naked, (
        f"urlopen without context=SSL_CONTEXT in smoke_live.py: {naked} — "
        "on macOS this dies in the handshake and reads as missing auth wiring"
    )


# ---------------------------------------------------------------------------
# The CONFIGURED branch — SYNC-1.6.22-1.6.29 item 7, ported to this fork's
# shape. Every fleet battery boots zero-secret, and tests/conftest.py pins
# every CLERK_* variable empty before anything imports run.py, so until these
# two tests existed NOTHING in this suite had ever executed the branch that
# runs in production. The lock card, the ClerkJS bootstrap and satellite mode
# were certified by nothing. Found end-to-end on clerkhook (2026-08-26), where
# the unrendered branch's first live run produced 220 false leaks and a
# verdict on a partial body; the CLASS is fleet-wide.
#
# The marker is the kwargs handed to dash_clerk_auth.register_clerk_auth —
# emitted ONLY by the configured branch, so neither assertion can pass
# vacuously. register_clerk_auth is recorded rather than called: it installs
# global @dash.hooks callbacks, and a suite that really invoked it would
# poison the session-scoped app fixture for every later test.
# ---------------------------------------------------------------------------


def _fake_clerk(monkeypatch, **env):
    """Arm a FAKE, non-empty Clerk config and record the registration call.

    Three things are recorded rather than executed, and each for the same
    reason — they are GLOBAL and would outlive the test:
    `register_clerk_auth` installs `@dash.hooks` callbacks, and both
    delegation installers register `@dash.hooks.index()` hooks that inject a
    <script> into every index render for the rest of the session. Recording
    keeps every assertion below non-vacuous (they read what the configured
    branch emitted) while leaving the session-scoped `app` fixture exactly as
    the other tests found it.
    """
    import sys
    import types

    from lib import auth as _auth

    calls = []
    stub = types.ModuleType("dash_clerk_auth")
    stub.register_clerk_auth = lambda **kwargs: calls.append(kwargs)
    monkeypatch.setitem(sys.modules, "dash_clerk_auth", stub)

    installed = []
    monkeypatch.setattr(_auth, "_install_satellite_signin_delegation",
                        lambda: installed.append("signin"))
    monkeypatch.setattr(_auth, "_install_signout_delegation",
                        lambda: installed.append("signout"))
    _fake_clerk.installed = installed

    defaults = {
        "CLERK_SECRET_KEY": "sk_test_not_a_real_key",
        "CLERK_PUBLISHABLE_KEY": "pk_test_not_a_real_key",
        "CLERK_SIGN_IN_URL": "https://accounts.example.test/sign-in",
        "SESSION_SECRET": "test-only-session-secret",
    }
    defaults.update(env)
    for key, value in defaults.items():
        monkeypatch.setenv(key, value)
    return calls


def test_register_runs_the_configured_branch_with_keys_present(monkeypatch):
    """With keys set, register() must actually wire Clerk — and say so."""
    from lib import auth

    calls = _fake_clerk(monkeypatch)
    assert auth.register() is True, (
        "register() reported auth disabled with a full config present — the "
        "production branch never runs"
    )
    assert len(calls) == 1, "register_clerk_auth was not called exactly once"
    assert calls[0]["clerk_publishable_key"] == "pk_test_not_a_real_key"
    assert calls[0]["clerk_sign_in_url"] == "https://accounts.example.test/sign-in"
    assert calls[0]["headless"] is True
    # The sign-out delegate is what makes Sign Out revoke the SERVER's
    # identity cookie, not just ClerkJS's — a configured build without it
    # renders every gated page to a signed-out browser for a week.
    assert "signout" in _fake_clerk.installed


def test_a_live_key_on_a_satellite_domain_boots_in_satellite_mode(monkeypatch):
    """The branch NOTHING could see: production runs a pk_live key, and
    ClerkJS throws "a satellite application needs to specify a domain"
    unless init carries isSatellite + domain. register() auto-enables it
    from the key prefix and the derived host even when CLERK_IS_SATELLITE
    was missed in the deploy env — so the one configuration that can only
    exist in production is exactly the one no zero-secret suite reaches.
    """
    from lib import auth

    calls = _fake_clerk(
        monkeypatch,
        CLERK_PUBLISHABLE_KEY="pk_live_not_a_real_key",
        CLERK_SATELLITE_DOMAIN="2plot.dev",
    )
    assert auth.register() is True
    assert calls[0]["is_satellite"] is True, (
        "a pk_live key on a configured satellite domain must init ClerkJS in "
        "satellite mode — primary mode fails sign-in on every *.2plot.dev host"
    )
    assert calls[0]["satellite_domain"] == "2plot.dev"
    assert "signin" in _fake_clerk.installed, (
        "satellite mode without the sign-in delegation: any sign-in button "
        "Dash renders after DOMContentLoaded gets no listener at all"
    )

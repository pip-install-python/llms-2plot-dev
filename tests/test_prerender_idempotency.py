"""The idempotency-probe trap (2.7.0 "Fixed") — proved on a real index.html.

Through 2.6.x the "already injected" check was `_MARKER in document`, a bare
substring probe on the marker's NAME. The name appearing anywhere in the
served document — including an innocent HTML COMMENT — made the injector
believe it had already run and return the document untouched. Two production
hosts in this fleet (email, flows) shipped exactly that and lost their entire
universal prerender: every crawler on every page got the empty Dash shell,
and nothing in any suite noticed, because the pages still rendered perfectly
for humans.

2.7.0 narrows the probe to the injected node's opening tag,
`<div id="dimll-prerender"`. This file proves it two ways:

* directly, against `inject_prerender` — the unit the fix lives in;
* end to end, by PLANTING the marker in this repo's real
  templates/index.html, booting run.py in a subprocess, and fetching a page.
  The plant is removed in a `finally` and a guard test verifies the file came
  back clean.

The authoring rule stands regardless — never spell the marker in served text
— but the package no longer hands out the footgun, and this is where that
stops being a claim.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from conftest import requires_dimll_27

# Every assertion in this module is about the 2.7.0 surface. On the
# pinned 2.6.1 floor the whole file skips rather than fails.
pytestmark = requires_dimll_27

REPO_ROOT = Path(__file__).resolve().parent.parent
INDEX_HTML = REPO_ROOT / "templates" / "index.html"
MARKER = "data-dimll-prerender"
PROBE = '<div id="dimll-prerender"'

# The exact shape that disabled the two hosts: a comment MENTIONING the
# marker, written by someone documenting the very feature they broke.
PLANTED_COMMENT = (
    "\n    <!-- Injected by dash-improve-my-llms; the block is tagged\n"
    f"         {MARKER}=\"1\" so it is easy to find in view-source. -->\n"
)


# ---------------------------------------------------------------------------
# 1. The unit
# ---------------------------------------------------------------------------

def _minimal_dash_document(extra_head: str = "") -> str:
    return (
        "<!DOCTYPE html><html><head><title>t</title>"
        f"{extra_head}</head><body>"
        '<div id="react-entry-point"><div class="_dash-loading">Loading...</div></div>'
        "</body></html>"
    )


def _inject(document: str) -> str:
    """`inject_prerender` with the context shape handlers.py builds."""
    from dash_improve_my_llms import prerender

    meta = {
        "name": "Soak",
        "title": "Soak",
        "description": "probe test",
        "llms_doc": "# Soak\n\nProse for the probe test.\n",
    }
    return prerender.inject_prerender(
        document,
        {
            "page_path": "/soak",
            "page_metadata": meta,
            "app_config": {"name": "Soak App", "base_url": "https://llms.2plot.dev"},
            # A LIST of page dicts: build_body_fragment iterates it and
            # subscripts each item, so a mapping yields bare keys and raises.
            "all_pages": [
                {"path": "/soak", "name": "Soak"},
                {"path": "/other", "name": "Other"},
            ],
        },
    )


def test_a_clean_document_gets_the_prerender():
    """The control. Without this, every assertion below could pass vacuously."""
    out = _inject(_minimal_dash_document())
    assert PROBE in out, "the control document was not injected into at all"


def test_the_marker_name_in_a_comment_does_not_block_injection():
    """THE regression. This exact document shape cost two hosts their prerender."""
    out = _inject(_minimal_dash_document(PLANTED_COMMENT))
    assert PROBE in out, (
        "the marker's NAME inside an HTML comment suppressed the entire "
        "prerender — this is the 2.6.x bug the 2.7.0 probe change fixes"
    )


@pytest.mark.parametrize("where", [
    f"<!-- {MARKER} -->",
    f'<meta name="note" content="{MARKER}">',
    f"<script>var m = '{MARKER}';</script>",
    f"<!-- see docs for {MARKER}=\"1\" -->",
])
def test_the_marker_name_anywhere_in_the_head_does_not_block_injection(where):
    assert PROBE in _inject(_minimal_dash_document(where)), (
        f"the marker name in {where!r} suppressed the prerender"
    )


def test_a_real_second_injection_is_still_a_no_op():
    """The probe must not have been loosened into uselessness.

    A genuinely already-injected document has to stay untouched, or a second
    middleware pass duplicates the prose — which reads as keyword stuffing.
    """
    once = _inject(_minimal_dash_document())
    twice = _inject(once)
    assert twice == once, "a second injection changed the document"
    assert once.count(PROBE) == 1, "the prerender block was duplicated"


# ---------------------------------------------------------------------------
# 2. End to end, on this repo's real template
# ---------------------------------------------------------------------------

_SUBPROCESS = textwrap.dedent(
    """
    import importlib.util, io, json, os, sys, contextlib, logging
    sys.path.insert(0, {root!r})
    sys.path.insert(0, os.path.join({root!r}, "tests"))
    os.environ["APP_ENV"] = "test"
    os.environ["ANALYTICS_GEO_LOOKUP"] = "0"
    os.environ["TRAFFIC_ANALYTICS_FILE"] = os.path.join({state!r}, "va.json")
    os.environ["PAGE_VISIBILITY_FILE"] = os.path.join({state!r}, "pv.json")
    os.environ["POLICY_STORE_FILE"] = os.path.join({state!r}, "ps.json")
    for key in ("CLERK_SECRET_KEY", "CLERK_PUBLISHABLE_KEY", "CROSS_APP_WEBHOOK_SECRET",
                "NETWORK_BULLETIN_URL", "DIMLL_PANEL_TOKEN"):
        os.environ[key] = ""
    logging.disable(logging.INFO)
    os.chdir({root!r})
    spec = importlib.util.spec_from_file_location("runmod", os.path.join({root!r}, "run.py"))
    m = importlib.util.module_from_spec(spec)
    sys.modules["runmod"] = m
    with contextlib.redirect_stdout(io.StringIO()):
        spec.loader.exec_module(m)
    # The subprocess inherits DASH_BACKEND, so it must reconcile the three
    # clients the same way tests/conftest.py does. FastAPI and Quart need the
    # ASGI lifespan to have run: Dash registers its page catch-all from the
    # startup event, so a client used outside the lifespan 404s every URL.
    from lib.backend import resolve_backend
    kind = resolve_backend()
    headers = {{"User-Agent": {ua!r}}}
    if kind == "fastapi":
        from starlette.testclient import TestClient
        with TestClient(m.app.server) as raw:
            body = raw.get("/", headers=headers).text
    elif kind == "quart":
        import asyncio
        async def _fetch():
            client = m.app.server.test_client()
            r = await client.get("/", headers=headers)
            return (await r.get_data()).decode()
        body = asyncio.new_event_loop().run_until_complete(_fetch())
    else:
        body = m.app.server.test_client().get("/", headers=headers).get_data().decode()
    print(json.dumps({{
        "has_probe": {probe!r} in body,
        "has_main": "<main>" in body,
        "length": len(body),
    }}))
    """
)


def _boot_and_probe(tmp_path, user_agent) -> dict:
    """Boot run.py in a FRESH process and report what a fetch of / contains.

    A subprocess because templates/index.html is read once at import time —
    the planted comment cannot be observed by the already-booted session app.
    """
    script = _SUBPROCESS.format(
        root=str(REPO_ROOT), state=str(tmp_path), ua=user_agent, probe=PROBE
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True, text=True, cwd=str(REPO_ROOT), timeout=300,
    )
    assert result.returncode == 0, (
        f"the app failed to boot in a subprocess:\n{result.stderr[-3000:]}"
    )
    return json.loads(result.stdout.strip().splitlines()[-1])


BROWSER = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
           "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")


@pytest.mark.slow
def test_the_real_index_html_still_prerenders_with_the_marker_planted(tmp_path):
    """The charter's own repro, on this repo's actual template.

    Plants the marker in a comment, boots run.py fresh, fetches `/`, and
    requires the prerender to be there. The plant is removed in `finally`;
    test_the_plant_was_removed below is the belt-and-braces.
    """
    original = INDEX_HTML.read_text()
    assert MARKER not in original, (
        "templates/index.html already spells the marker — the authoring rule "
        "says it must not, and this test cannot distinguish plant from prior "
        "contamination"
    )

    baseline = _boot_and_probe(tmp_path, BROWSER)
    assert baseline["has_probe"], (
        "the UNPLANTED template does not prerender either — something else "
        "is wrong and this test would otherwise report a false pass"
    )

    try:
        planted = original.replace("</head>", PLANTED_COMMENT + "</head>", 1)
        assert planted != original, "could not find </head> to plant before"
        INDEX_HTML.write_text(planted)

        result = _boot_and_probe(tmp_path, BROWSER)
        assert result["has_probe"], (
            "PLANTING THE MARKER IN A COMMENT DISABLED THE PRERENDER on the "
            "real template. This is the exact defect that silently cost two "
            "production hosts every prerendered page."
        )
        assert result["has_main"], "the prerender block carries no <main> prose"
    finally:
        INDEX_HTML.write_text(original)


def test_the_plant_was_removed():
    """Runs after the test above (alphabetical within the module is not
    guaranteed, so this checks the invariant rather than the ordering)."""
    assert MARKER not in INDEX_HTML.read_text(), (
        "templates/index.html still carries the planted marker — remove it "
        "before committing; it disables the prerender on 2.6.x consumers"
    )

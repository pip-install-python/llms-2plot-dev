"""Teaser demos for the authentication gate cards.

Each auth-gated docs page can register ONE live example that renders inside
the sign-in card (lib.gate_layouts.sign_in_layout) — an interactive taste of
what's behind the gate, with no code and no surrounding docs.

The modules referenced here are the same ``.. exec::`` example modules the
docs pages use (they expose a module-level ``component``), so they're already
imported — and their callbacks already registered — when pages/markdown.py
parses the docs at startup. Only one layout (gate card OR full docs) renders
per request, so sharing the component instances never duplicates IDs.

The table ships with ONE working entry in the template — the pattern, live —
and each satellite swaps in its own hero example (one entry is plenty; this
is a funnel, not a gallery). An empty table is legitimate too: cards render
without the demo block. Either way tests/test_auth_demos.py holds the line —
every entry that IS here must resolve on THIS site, because build_demo below
degrades silently by design.

Entries:
    endpoint -> {
        "module":     dotted path of the example module,
        "caption":    short label shown next to the "Live demo" badge,
        "max_height": px cap for the demo viewport inside the card,
        "height":     optional explicit px height — needed by components that
                      size to their container,
    }
"""
from __future__ import annotations

import importlib
import logging

logger = logging.getLogger(__name__)

DEMOS: dict[str, dict] = {
    # THIS SITE's hero example, replacing the template's inherited
    # /examples/visualization entry — a page that does not exist here, whose
    # module does not exist here, and whose card therefore rendered demo-less
    # and SILENT from fork time (build_demo swallows the ImportError by
    # design, and its warning only fires when that endpoint's card renders,
    # which never happens when the endpoint is not a page). Found fleet-wide
    # by excalidraw, 2026-08-25; tests/test_auth_demos.py is the loud surface.
    #
    # The robots sandbox is the right teaser for this funnel: it runs the
    # documented package's OWN pure handlers in-process, so a visitor types a
    # User-Agent and watches the real verdict — no account, no secrets, no
    # paid model behind it, and every render builds a throwaway config that
    # cannot touch what the site serves.
    "/showcase/robots-sandbox": {
        "module": "docs.robots_sandbox.robots_sandbox",
        "caption": "Live robots.txt sandbox",
        "max_height": 420,
    },
}


def build_demo(path: str):
    """Return the teaser demo block for ``path``, or None.

    Import/attribute failures degrade to the plain (demo-less) card — a broken
    example must never take down the sign-in funnel.
    """
    spec = DEMOS.get(path)
    if spec is None:
        return None
    try:
        module = importlib.import_module(spec["module"])
        component = getattr(module, "component")
    except Exception as e:
        logger.warning("Auth-gate demo %s failed to load (%s) — card renders "
                       "without it", spec.get("module"), e)
        return None

    import dash_mantine_components as dmc
    from dash_iconify import DashIconify

    return dmc.Box(
        [
            dmc.Group(
                [
                    dmc.Badge(
                        "Live demo — try it",
                        variant="light",
                        color="teal",
                        leftSection=DashIconify(icon="tabler:hand-click", width=13),
                    ),
                    dmc.Text(spec.get("caption", ""), size="sm", c="dimmed"),
                ],
                justify="space-between",
                px="md",
                pt="md",
            ),
            dmc.Box(
                component,
                p="md",
                className="auth-gate-demo",
                style={
                    "maxHeight": f"{spec.get('max_height', 420)}px",
                    "overflowY": "auto",
                    "overflowX": "hidden",
                    **({"height": f"{spec['height']}px"} if "height" in spec else {}),
                },
            ),
        ]
    )

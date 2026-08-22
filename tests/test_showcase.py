"""The three showcases, and the two exec-module rules that keep them safe.

Both rules exist because breaking them fails SILENTLY:

1. **Globally-unique id prefixes.** Dash ids share one namespace across every
   exec module on the site. A collision does not raise — it wires the wrong
   callback to the wrong component, and the page merely behaves oddly.
2. **No import-time registry walk.** These modules are imported from inside
   `pages/markdown.py`'s glob loop, so `dash.page_registry` is INCOMPLETE.
   A module that reads it at import time gets a short list, silently, and the
   dropdown is simply missing pages nobody notices are absent.

Plus Showcase B's own invariant: it must never assign `app._robots_config`.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

SHOWCASE_MODULES = {
    "docs/mcp_clients/mcp_registry.py": "mcpx",
    "docs/crawler_view/crawler_view.py": "crwv",
    "docs/robots_sandbox/robots_sandbox.py": "rbsx",
    "docs/policy_panel/policy_panel.py": "plcy",
}

SHOWCASE_ENDPOINTS = {
    "/audiences/mcp-clients",
    "/audiences/web-crawlers",
    "/audiences/llm-context",
    "/showcase/robots-sandbox",
    "/showcase/policy-panel",
}


def _source(rel_path: str) -> str:
    return (REPO_ROOT / rel_path).read_text()


# ---------------------------------------------------------------------------
# The pages exist and are reachable
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("endpoint", sorted(SHOWCASE_ENDPOINTS))
def test_every_showcase_endpoint_is_registered(app_module, endpoint):
    import dash

    paths = {entry["path"] for entry in dash.page_registry.values()}
    assert endpoint in paths, f"{endpoint} is not a registered page"


@pytest.mark.parametrize("endpoint", sorted(SHOWCASE_ENDPOINTS))
def test_every_showcase_endpoint_serves(client, endpoint):
    assert client.get(endpoint).status == 200


@pytest.mark.parametrize("endpoint", sorted(SHOWCASE_ENDPOINTS))
def test_every_showcase_page_has_machine_prose(client, endpoint):
    """A page with an interactive demo and no prose is invisible to agents."""
    from conftest import STUB_MARKER

    body = client.get(f"{endpoint.rstrip('/')}/llms.txt").text
    assert STUB_MARKER not in body, f"{endpoint} serves the package's stub"
    assert len(body) > 800, f"{endpoint}/llms.txt is only {len(body)} bytes"


def test_the_audience_urls_are_preserved_byte_for_byte(client):
    """The migration's one non-negotiable: these URLs move hosts, not paths."""
    for endpoint in ("/audiences/mcp-clients", "/audiences/web-crawlers",
                     "/audiences/llm-context"):
        assert client.get(endpoint).status == 200, f"{endpoint} moved"


# ---------------------------------------------------------------------------
# Rule 1 — globally unique id prefixes
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("rel_path,prefix", sorted(SHOWCASE_MODULES.items()))
def test_every_id_carries_the_modules_prefix(rel_path, prefix):
    source = _source(rel_path)
    ids = set(re.findall(r'id=f?"([a-z][a-z0-9-]*)"', source))
    ids |= set(re.findall(r'Output\(f?"([a-z][a-z0-9-]*)"', source))
    ids |= set(re.findall(r'Input\(f?"([a-z][a-z0-9-]*)"', source))

    # f-string ids are written f"{ID}-thing", so the literal captured is the
    # part after the brace — anything captured whole is a HARDCODED id.
    hardcoded = {i for i in ids if not i.startswith(prefix)}
    assert not hardcoded, (
        f"{rel_path} hardcodes id(s) {sorted(hardcoded)} outside its "
        f"{prefix!r} namespace. Ids are global across ~45 exec modules and a "
        "collision silently wires the wrong callback."
    )


def test_no_two_showcase_modules_share_a_prefix():
    prefixes = list(SHOWCASE_MODULES.values())
    assert len(prefixes) == len(set(prefixes)), f"duplicate prefixes: {prefixes}"


def test_every_showcase_module_declares_its_prefix_once():
    for rel_path, prefix in SHOWCASE_MODULES.items():
        source = _source(rel_path)
        assert f'ID = "{prefix}"' in source, (
            f"{rel_path} does not declare ID = {prefix!r}, so the prefix lives "
            "in every id string instead of one place"
        )


# ---------------------------------------------------------------------------
# Rule 2 — no import-time registry walk
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("rel_path", sorted(SHOWCASE_MODULES))
def test_no_module_reads_the_page_registry_at_import_time(rel_path):
    """`dash.page_registry` may only be touched inside a function body.

    Walks the AST rather than grepping: the point is WHERE the read happens,
    and a string search cannot tell module scope from a callback body.
    """
    tree = ast.parse(_source(rel_path))

    offenders = []
    for node in tree.body:  # module scope only — function bodies are fine
        for sub in ast.walk(node):
            if isinstance(sub, ast.Attribute) and sub.attr == "page_registry":
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                                         ast.ClassDef)):
                    offenders.append(getattr(node, "lineno", "?"))

    assert not offenders, (
        f"{rel_path} reads dash.page_registry at module scope (line(s) "
        f"{offenders}). These modules are imported from inside "
        "pages/markdown.py's glob loop, so the registry is incomplete and the "
        "result is a silently short list."
    )


@pytest.mark.parametrize("rel_path", sorted(SHOWCASE_MODULES))
def test_the_module_level_component_is_a_placeholder(rel_path):
    """`component` must exist at module scope — the directive imports it."""
    tree = ast.parse(_source(rel_path))
    assigned = {
        target.id
        for node in tree.body if isinstance(node, ast.Assign)
        for target in node.targets if isinstance(target, ast.Name)
    }
    assert "component" in assigned, f"{rel_path} defines no module-level `component`"


# ---------------------------------------------------------------------------
# Showcase B's invariant
# ---------------------------------------------------------------------------

def test_the_sandbox_never_assigns_the_live_robots_config():
    """THE invariant. Callbacks are global on a shared server.

    A sandbox that assigned `app._robots_config` would let any visitor
    rewrite the policy every other visitor — and every crawler — is served.
    """
    source = _source("docs/robots_sandbox/robots_sandbox.py")
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Attribute):
                    assert target.attr != "_robots_config", (
                        "the sandbox assigns _robots_config — every visitor "
                        "would be rewriting the live policy"
                    )
    assert "_robots_config =" not in source


def test_the_sandbox_builds_a_throwaway_config():
    source = _source("docs/robots_sandbox/robots_sandbox.py")
    assert "generate_robots_txt(" in source
    assert "config=config" in source, (
        "the sandbox does not pass its throwaway config, so it is either "
        "rendering the live one or not rendering at all"
    )


def test_the_sandbox_does_not_change_what_the_site_serves(client):
    """The behavioural half: render the page, then re-read robots.txt."""
    before = client.get("/robots.txt").text
    assert client.get("/showcase/robots-sandbox").status == 200
    assert client.get("/robots.txt").text == before


# ---------------------------------------------------------------------------
# Showcase C reads the real seam
# ---------------------------------------------------------------------------

def test_the_policy_panel_reads_the_live_policy_store():
    source = _source("docs/policy_panel/policy_panel.py")
    assert "policy_store" in source, (
        "Showcase C does not read lib.policy_store, so its map is decoration "
        "rather than the live denylist"
    )
    assert "geo_deny" in source


def test_the_policy_panel_is_read_only():
    """It displays. The control board writes."""
    source = _source("docs/policy_panel/policy_panel.py")
    for writer in ("set_geo_deny", "toggle_country", "set_vendor_action",
                   "clear_vendor_action", "set_visibility"):
        assert writer not in source, (
            f"Showcase C calls {writer}() — it is a public, ungated page and "
            "must never write policy"
        )

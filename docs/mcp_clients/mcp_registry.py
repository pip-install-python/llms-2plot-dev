"""Showcase exec module: what an MCP client actually mounts from this site.

Two exec-module rules apply here and are load-bearing enough to restate:

1. **Globally-unique id prefix.** Every id in this module starts `mcpx-`.
   Dash ids share one namespace across ~45 exec modules on this site; a
   collision does not error, it silently wires the wrong callback.
2. **No import-time registry walk.** `dash.page_registry` is INCOMPLETE while
   `pages/markdown.py` is still globbing — this module is imported from
   inside that loop. So `component` below is a placeholder and the table is
   populated by a callback, which runs long after registration finishes.
"""
from dash import Input, Output, callback, dcc, html, no_update
import dash_mantine_components as dmc
from dash_iconify import DashIconify

ID = "mcpx"

component = html.Div(
    [
        dmc.Group(
            [
                dmc.Select(
                    id=f"{ID}-page",
                    label="Page",
                    description="Every page this site registers is an MCP resource.",
                    placeholder="Loading the registry…",
                    searchable=True,
                    w=340,
                ),
                dmc.Switch(
                    id=f"{ID}-raw",
                    label="Show the raw resource body",
                    checked=False,
                    mt=28,
                ),
            ],
            gap="lg",
            align="flex-start",
        ),
        dmc.Space(h="md"),
        dmc.Paper(
            dmc.Stack(
                [
                    dmc.Group(
                        [
                            DashIconify(icon="tabler:plug-connected", width=18),
                            dmc.Text("Resource URI", size="sm", fw=600),
                        ],
                        gap="xs",
                    ),
                    dmc.Code(id=f"{ID}-uri", block=True),
                    dmc.Text(id=f"{ID}-hint", size="xs", c="dimmed"),
                ],
                gap="xs",
            ),
            withBorder=True,
            radius="md",
            p="md",
        ),
        dmc.Space(h="md"),
        html.Div(id=f"{ID}-body"),
        dcc.Interval(id=f"{ID}-boot", interval=200, max_intervals=1),
    ]
)


@callback(
    Output(f"{ID}-page", "data"),
    Output(f"{ID}-page", "value"),
    Input(f"{ID}-boot", "n_intervals"),
)
def _populate(_tick):
    """Read the registry HERE, not at import time.

    A one-shot Interval rather than a layout-time walk: by the time this
    fires, every page in docs/ has registered and the list is complete.
    """
    import dash

    options = sorted(
        (
            {"value": entry["path"], "label": entry.get("name") or entry["path"]}
            for entry in dash.page_registry.values()
            if not entry["path"].startswith("/admin/")
        ),
        key=lambda option: option["label"],
    )
    if not options:
        return no_update, no_update
    return options, options[0]["value"]


@callback(
    Output(f"{ID}-uri", "children"),
    Output(f"{ID}-hint", "children"),
    Output(f"{ID}-body", "children"),
    Input(f"{ID}-page", "value"),
    Input(f"{ID}-raw", "checked"),
)
def _describe(path, raw):
    if not path:
        return "—", "Pick a page.", None

    from lib.constants import BASE_URL

    doc = _llms_doc_for(path)
    suffix = "llms.txt" if path == "/" else f"{path.strip('/')}/llms.txt"
    uri = f"{BASE_URL}/{suffix}"

    hint = (
        "An MCP client mounts this as a resource and reads it directly. "
        "A browser opening the same URL gets it rendered instead — the route "
        "content-negotiates on Accept, and sends Vary: Accept so a CDN cannot "
        "hand cached HTML to the next agent."
    )

    if not doc:
        body = dmc.Alert(
            "This page registers no LLMS_DOC, so the resource carries its "
            "generated summary rather than hand-written prose.",
            color="yellow",
            variant="light",
            icon=DashIconify(icon="tabler:info-circle"),
        )
    elif raw:
        body = dmc.Paper(
            dmc.Code(doc[:4000] + ("\n…" if len(doc) > 4000 else ""), block=True),
            withBorder=True, radius="md", p="sm",
        )
    else:
        body = dmc.Paper(dcc.Markdown(doc[:4000]), withBorder=True, radius="md", p="md")

    return uri, hint, body


def _llms_doc_for(path):
    """The prose dash-improve-my-llms would serve for `path`.

    Read through the package's own registry so this demo cannot drift from
    what the route actually returns.
    """
    try:
        import dash_improve_my_llms as dimll

        store = getattr(getattr(dimll, "_state", None), "page_metadata", None) or {}
        return (store.get(path) or {}).get("llms_doc") or ""
    except Exception:
        # Private state, read defensively: if the package moves it, this demo
        # degrades to "no prose registered" rather than breaking the page.
        return ""

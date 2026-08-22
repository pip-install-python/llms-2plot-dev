"""Showcase A — what a crawler actually receives from this site.

Runs the package's own PURE handlers in-process for a chosen page and User-
Agent, and shows the three things that are normally invisible: the policy
verdict, the crawler document's markup, and the headers that came with it —
next to what a browser gets for the same URL.

Exec-module rules (both tested elsewhere in this repo):

1. **Globally-unique id prefix** — everything here starts `crwv-`. Ids share
   one namespace across every exec module on the site.
2. **No import-time registry walk** — this module is imported from inside
   `pages/markdown.py`'s glob loop, so `dash.page_registry` is incomplete.
   `component` is a placeholder; the page list arrives by callback.
"""
import html as _html

from dash import Input, Output, State, callback, dcc, html, no_update
import dash_mantine_components as dmc
from dash_iconify import DashIconify

ID = "crwv"

BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

_VERDICT_COLOR = {"allow": "teal", "block": "red", "meter": "yellow"}
_CLASS_COLOR = {"training": "red", "search": "teal", "traditional": "blue"}


def _ua_options():
    """Real UA tokens from the package registry, grouped by class.

    Built at layout time from `bot_detection`, so a vendor added to the
    registry appears here without this file changing.
    """
    from dash_improve_my_llms.vendors import VENDORS

    groups = {"training": [], "search": [], "traditional": []}
    for vendor in VENDORS:
        # Not every vendor publishes a robots token: `anthropic-legacy` is a
        # UA-only identity (anthropic-ai, claude-web) with an empty
        # robots_tokens tuple, so fall back to what the middleware matches on.
        token = (vendor.robots_tokens or vendor.ua_tokens or (vendor.key,))[0]
        groups.setdefault(vendor.cls, []).append(
            {"value": f"{token}/1.0", "label": f"{vendor.display} — {vendor.operator}"}
        )

    data = [{"group": "A human's browser",
             "items": [{"value": BROWSER_UA, "label": "Chrome 120 (a person)"}]}]
    for cls, label in (("training", "AI training crawlers"),
                       ("search", "AI search & citation"),
                       ("traditional", "Traditional search engines")):
        if groups.get(cls):
            data.append({"group": label, "items": sorted(groups[cls],
                                                         key=lambda o: o["label"])})
    return data


component = html.Div(
    [
        dmc.Group(
            [
                dmc.Select(
                    id=f"{ID}-page",
                    label="Page",
                    placeholder="Loading the registry…",
                    searchable=True,
                    w=320,
                ),
                dmc.Select(
                    id=f"{ID}-ua",
                    label="User-Agent",
                    data=_ua_options(),
                    value=BROWSER_UA,
                    searchable=True,
                    w=380,
                ),
            ],
            gap="lg",
            align="flex-start",
        ),
        dmc.Space(h="md"),
        html.Div(id=f"{ID}-verdict"),
        dmc.Space(h="md"),
        dmc.Tabs(
            [
                dmc.TabsList(
                    [
                        dmc.TabsTab("Rendered", value="rendered",
                                    leftSection=DashIconify(icon="tabler:eye", width=15)),
                        dmc.TabsTab("View source", value="source",
                                    leftSection=DashIconify(icon="tabler:code", width=15)),
                        dmc.TabsTab("Headers", value="headers",
                                    leftSection=DashIconify(icon="tabler:list-details", width=15)),
                    ]
                ),
                dmc.TabsPanel(html.Div(id=f"{ID}-rendered"), value="rendered", pt="md"),
                dmc.TabsPanel(html.Div(id=f"{ID}-source"), value="source", pt="md"),
                dmc.TabsPanel(html.Div(id=f"{ID}-headers"), value="headers", pt="md"),
            ],
            value="rendered",
            id=f"{ID}-tabs",
        ),
        dcc.Interval(id=f"{ID}-boot", interval=200, max_intervals=1),
    ]
)


@callback(
    Output(f"{ID}-page", "data"),
    Output(f"{ID}-page", "value"),
    Input(f"{ID}-boot", "n_intervals"),
)
def _pages(_tick):
    import dash

    options = sorted(
        ({"value": e["path"], "label": e.get("name") or e["path"]}
         for e in dash.page_registry.values()
         if not e["path"].startswith("/admin/")),
        key=lambda o: o["label"],
    )
    if not options:
        return no_update, no_update
    return options, "/"


@callback(
    Output(f"{ID}-verdict", "children"),
    Output(f"{ID}-rendered", "children"),
    Output(f"{ID}-source", "children"),
    Output(f"{ID}-headers", "children"),
    Input(f"{ID}-page", "value"),
    Input(f"{ID}-ua", "value"),
)
def _show(path, user_agent):
    if not path or not user_agent:
        return None, None, None, None

    from dash_improve_my_llms.bot_detection import get_bot_type, get_bot_vendor, is_any_bot
    from dash_improve_my_llms.vendors import VENDORS, effective_policies

    import dash

    is_bot = is_any_bot(user_agent)
    vendor_key = get_bot_vendor(user_agent)
    vendor = next((v for v in VENDORS if v.key == vendor_key), None)
    bot_class = get_bot_type(user_agent) if is_bot else "human"

    policy = "allow"
    if vendor is not None:
        try:
            policy = effective_policies(getattr(dash.get_app(), "_robots_config", None))[
                vendor.key
            ]
        except Exception:
            policy = "allow"

    verdict = _verdict_card(is_bot, vendor, bot_class, policy)

    if is_bot and policy == "block":
        blocked = dmc.Alert(
            [
                dmc.Text("403 Forbidden", fw=700, size="lg"),
                dmc.Text(
                    "This crawler is blocked on ordinary pages by the site's "
                    "vendor policy, so it never reaches the document below. "
                    "The documentation surfaces (/llms.txt and the tier "
                    "documents) stay open to it — that is deliberate, and it "
                    "is what `block_ai_training_docs` would close.",
                    size="sm",
                ),
            ],
            color="red",
            variant="light",
            icon=DashIconify(icon="tabler:ban"),
        )
        return verdict, blocked, blocked, _headers_table(
            {"Status": "403 Forbidden", "Cache-Control": "no-store"}
        )

    document = _crawler_document(path)
    if not document:
        empty = dmc.Alert(
            "No prerendered document is available for this page in-process.",
            color="yellow", variant="light",
        )
        return verdict, empty, empty, None

    rendered = html.Iframe(
        srcDoc=document,
        style={"width": "100%", "height": "480px", "border": "1px solid var(--mantine-color-default-border)",
               "borderRadius": "8px", "background": "white"},
    )
    source = dmc.Paper(
        dmc.Code(_truncate(document), block=True,
                 style={"maxHeight": "480px", "overflow": "auto", "display": "block"}),
        withBorder=True, radius="md", p="sm",
    )
    headers = _headers_table({
        "Status": "200 OK",
        "Content-Type": "text/html; charset=utf-8",
        "X-Robots-Tag": "(none — this page is indexable)",
        "Vary": "Accept  (on /<page>/llms.txt)",
    })
    return verdict, rendered, source, headers


def _verdict_card(is_bot, vendor, bot_class, policy):
    rows = [
        ("Classified as", "bot" if is_bot else "human (untouched by policy)"),
        ("Vendor", f"{vendor.display} — {vendor.operator}" if vendor else "—"),
        ("Class", bot_class),
        ("Effective policy", policy if is_bot else "n/a"),
    ]
    return dmc.Paper(
        dmc.Group(
            [
                dmc.Stack(
                    [
                        dmc.Text(label, size="xs", c="dimmed", tt="uppercase"),
                        dmc.Badge(
                            str(value),
                            color=_VERDICT_COLOR.get(value, _CLASS_COLOR.get(value, "gray")),
                            variant="light",
                            size="lg",
                        ) if label in ("Class", "Effective policy")
                        else dmc.Text(str(value), size="sm", fw=600),
                    ],
                    gap=4,
                )
                for label, value in rows
            ],
            gap="xl",
        ),
        withBorder=True, radius="md", p="md",
    )


def _headers_table(headers):
    return dmc.Table(
        [
            dmc.TableThead(dmc.TableTr([dmc.TableTh("Header"), dmc.TableTh("Value")])),
            dmc.TableTbody([
                dmc.TableTr([dmc.TableTd(dmc.Code(k)), dmc.TableTd(v)])
                for k, v in headers.items()
            ]),
        ],
        striped=True, withTableBorder=True,
    )


def _crawler_document(path):
    """The crawler HTML for `path`, built by the package's own generator.

    Calls the pure function rather than re-implementing it, so this showcase
    cannot claim something the real route would not serve.
    """
    try:
        import dash
        import dash_improve_my_llms as dimll
        from dash_improve_my_llms.html_generator import generate_static_page_html

        store = getattr(getattr(dimll, "_state", None), "page_metadata", None) or {}
        meta = store.get(path)
        if not meta:
            return ""

        all_pages = [
            {"path": p, "name": (m or {}).get("name") or p}
            for p, m in store.items()
        ]
        app = dash.get_app()
        app_config = {
            "name": getattr(app, "title", "") or "",
            "base_url": getattr(app, "_base_url", "") or "",
        }
        return generate_static_page_html(path, meta, all_pages, app_config)
    except Exception as exc:  # the showcase degrades, it never breaks the page
        return (
            "<!doctype html><meta charset='utf-8'>"
            f"<p>Crawler document unavailable in-process: {_html.escape(str(exc))}</p>"
        )


def _truncate(text, limit=12000):
    return text if len(text) <= limit else text[:limit] + "\n… truncated …"

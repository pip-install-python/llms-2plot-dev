"""Showcase B — build a RobotsConfig, see the robots.txt it would generate.

THE INVARIANT, and it has a test (tests/test_showcase.py): this module never
assigns `app._robots_config`. Dash callbacks are global on a shared server, so
a sandbox that mutated the live config would let any visitor rewrite what
every other visitor — and every crawler — is served. Every render here builds
a THROWAWAY config and passes it to `generate_robots_txt(config=...)`.

Exec-module rules: ids all start `rbsx-`; no import-time registry walk.
"""
from dash import Input, Output, callback, html
import dash_mantine_components as dmc
from dash_iconify import DashIconify

ID = "rbsx"

SITEMAP = "https://llms.2plot.dev/sitemap.xml"
BASE_URL = "https://llms.2plot.dev"

_POLICY_COLOR = {"allow": "teal", "block": "red", "meter": "yellow"}


def _vendor_rows():
    """(key, display, operator, class) for every vendor in the registry."""
    from dash_improve_my_llms.vendors import VENDORS

    return [(v.key, v.display, v.operator, v.cls) for v in VENDORS]


component = html.Div(
    [
        dmc.Alert(
            "This sandbox builds a throwaway config on every render. It never "
            "touches what this site actually serves — open /robots.txt in "
            "another tab and it will not change.",
            title="Nothing here is live",
            color="blue",
            variant="light",
            icon=DashIconify(icon="tabler:shield-check"),
        ),
        dmc.Space(h="md"),
        dmc.Grid(
            [
                dmc.GridCol(
                    dmc.Stack(
                        [
                            dmc.Text("Coarse flags", fw=600, size="sm"),
                            dmc.Switch(id=f"{ID}-training", checked=True,
                                       label="block_ai_training"),
                            dmc.Switch(id=f"{ID}-search", checked=True,
                                       label="allow_ai_search"),
                            dmc.Switch(id=f"{ID}-traditional", checked=True,
                                       label="allow_traditional"),
                            dmc.Switch(id=f"{ID}-docs", checked=False,
                                       label="block_ai_training_docs"),
                            dmc.NumberInput(id=f"{ID}-delay", label="crawl_delay",
                                            value=10, min=0, max=120, w=140),
                            dmc.Space(h="xs"),
                            dmc.Text("Per-vendor override (W2)", fw=600, size="sm"),
                            dmc.Select(
                                id=f"{ID}-vendor",
                                label="Vendor",
                                data=[{"value": key, "label": f"{display} ({cls})"}
                                      for key, display, _op, cls in _vendor_rows()],
                                searchable=True,
                                clearable=True,
                                placeholder="none",
                            ),
                            dmc.SegmentedControl(
                                id=f"{ID}-action",
                                data=[{"value": "allow", "label": "allow"},
                                      {"value": "meter", "label": "meter"},
                                      {"value": "block", "label": "block"}],
                                value="block",
                                fullWidth=True,
                            ),
                        ],
                        gap="sm",
                    ),
                    span={"base": 12, "md": 4},
                ),
                dmc.GridCol(
                    dmc.Tabs(
                        [
                            dmc.TabsList([
                                dmc.TabsTab("Generated robots.txt", value="robots"),
                                dmc.TabsTab("Per-vendor verdicts", value="verdicts"),
                            ]),
                            dmc.TabsPanel(html.Div(id=f"{ID}-robots"), value="robots", pt="sm"),
                            dmc.TabsPanel(html.Div(id=f"{ID}-verdicts"), value="verdicts", pt="sm"),
                        ],
                        value="robots",
                    ),
                    span={"base": 12, "md": 8},
                ),
            ],
            gutter="lg",
        ),
    ]
)


@callback(
    Output(f"{ID}-robots", "children"),
    Output(f"{ID}-verdicts", "children"),
    Input(f"{ID}-training", "checked"),
    Input(f"{ID}-search", "checked"),
    Input(f"{ID}-traditional", "checked"),
    Input(f"{ID}-docs", "checked"),
    Input(f"{ID}-delay", "value"),
    Input(f"{ID}-vendor", "value"),
    Input(f"{ID}-action", "value"),
)
def _render(training, search, traditional, docs, delay, vendor, action):
    from dash_improve_my_llms import RobotsConfig
    from dash_improve_my_llms.robots_generator import generate_robots_txt

    # THROWAWAY. Never assigned to the app — see this module's docstring.
    from dash_improve_my_llms.vendors import effective_policies

    config = RobotsConfig(
        block_ai_training=bool(training),
        allow_ai_search=bool(search),
        allow_traditional=bool(traditional),
        block_ai_training_docs=bool(docs),
        crawl_delay=int(delay) if delay else None,
        vendor_policy={vendor: action} if vendor else None,
    )
    robots = generate_robots_txt(sitemap_url=SITEMAP, base_url=BASE_URL, config=config)
    policies = effective_policies(config)

    robots_panel = dmc.Paper(
        dmc.Code(robots, block=True,
                 style={"maxHeight": "560px", "overflow": "auto", "display": "block"}),
        withBorder=True, radius="md", p="sm",
    )

    verdicts = dmc.Table(
        [
            dmc.TableThead(dmc.TableTr([
                dmc.TableTh("Vendor"), dmc.TableTh("Operator"),
                dmc.TableTh("Class"), dmc.TableTh("Effective policy"),
            ])),
            dmc.TableTbody([
                dmc.TableTr([
                    dmc.TableTd(display),
                    dmc.TableTd(dmc.Text(operator, size="xs", c="dimmed")),
                    dmc.TableTd(dmc.Text(cls, size="xs")),
                    dmc.TableTd(dmc.Badge(policies.get(key, "?"),
                                          color=_POLICY_COLOR.get(policies.get(key), "gray"),
                                          variant="light")),
                ])
                for key, display, operator, cls in _vendor_rows()
            ]),
        ],
        striped=True, highlightOnHover=True, withTableBorder=True,
    )
    return robots_panel, verdicts

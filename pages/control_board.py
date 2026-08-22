"""/admin/control-board — the writable owner control board.

Two panes, two stores, one gate.

**Page visibility** (inherited from the template): flip a page between
public / auth / admin / hidden and toggle whether its ``llms.txt`` is served
to anonymous and AI traffic. Persists to ``PAGE_VISIBILITY_FILE``; applies on
the next page render.

**The country guardrail** (this fork's B7 extension): click a country on the
world map to deny it. Persists to ``POLICY_STORE_FILE`` and reaches
``dash-improve-my-llms`` through the 2.7.0 CALLABLE seam —
``configure_geo(deny_countries=policy_store.geo_deny)`` in run.py — which the
package evaluates on **every request**. So the next request from that country
gets 451 on every surface, in every worker, with no restart and no redeploy.
That is the whole reason the seam exists, and this board is what it exists
for.

The package's own operator panel (``/llms-policy``) is the read-only floor
below this: it displays live policy and never writes, because package config
is per-process module state and a mutating panel would change one gunicorn
worker and lie on the next refresh. Routing writes through a file every
worker re-reads per request is what dissolves that — which is why the
writable layer belongs here and not in the package.

Access: the ``ADMIN_EMAILS`` / ``ADMIN_USER_IDS`` allowlist plus the owner
email (see ``lib.auth.is_admin_user``).

**This page fails CLOSED.** Everything else degrades to public when Clerk is
unavailable — docs must stay readable — but this board can hide any page on
the site, so without Clerk it returns a 404-style response instead. That is
the DEFAULT state: ``dash-clerk-auth`` is vendored, not resolved from PyPI,
and is not a dependency here, so a stock deploy has no Clerk. Set
``ALLOW_UNGATED_ADMIN=1`` to work on it locally.
"""
from datetime import datetime

import dash
import dash_mantine_components as dmc
from dash import ALL, Input, Output, State, callback, ctx, dcc, html, no_update
from dash.exceptions import PreventUpdate
from dash_iconify import DashIconify

from lib import policy_store
from lib.auth import admin_access_open, clerk_enabled, current_user, is_admin_user
from lib.constants import OG_IMAGE_URL, PAGE_TITLE_PREFIX
from lib.gate_layouts import forbidden_layout, hidden_layout, sign_in_layout
from lib.page_visibility import (
    TIERS,
    controllable_pages,
    set_llms_public,
    set_visibility,
)

BOARD_PATH = "/admin/control-board"

# Deliberately NOT registered in lib.page_tiers. Registering it `hidden`
# would flip `access.gating_configured()` on for EVERY fork — including
# all-public sites — and the template's contract is that the per-request
# machine check stays off until a real tier says otherwise
# (tests/test_access.py pins it). The board needs no ledger entry to be
# safe: its layout() below fails CLOSED on every render, the write callback
# re-checks the admin gate server-side, and the package-level mark below
# keeps every machine surface silent about it.
try:
    # Sitemap exclusion, llms.txt 404, no MCP resource, no prerender, and a
    # crawler 404 — dash-improve-my-llms' own hidden set works even on forks
    # whose pages are all public (where lib.access's check is deliberately
    # not wired at all).
    from dash_improve_my_llms import mark_hidden

    mark_hidden("/admin/control-board")
except Exception:  # pragma: no cover — the optional-SEO degrade
    pass

dash.register_page(
    __name__,
    path=BOARD_PATH,
    name="Control Board",
    title=PAGE_TITLE_PREFIX + "Control Board",
    description="Admin control board for page visibility and llms.txt exposure.",
    # Not for sharing — this page is hidden and Disallowed — but Dash emits
    # an empty og:image without it, and "every page" should mean every page.
    image_url=OG_IMAGE_URL,
)

_TIER_COLORS = {"public": "teal", "auth": "blue", "admin": "grape", "hidden": "gray"}

_TIER_HELP = [
    ("public", "teal", "Anyone — no account needed. The template's default."),
    ("auth", "blue", "Any signed-in user. The sign-in card on these pages "
                     "shows a live demo teaser and drives account creation."),
    ("admin", "grape", "Only allowlisted accounts. llms.txt for these pages "
                       "is never served anonymously."),
    ("hidden", "gray", "Nobody — the page and its llms.txt return a "
                       "404-style response."),
]


def _stat_card(label, value, color):
    return dmc.Paper(
        dmc.Stack(
            [
                dmc.Text(str(value), size="28px", fw=700, c=color),
                dmc.Text(label, size="xs", c="dimmed", tt="uppercase"),
            ],
            gap=2,
            align="center",
        ),
        withBorder=True,
        radius="md",
        p="md",
        style={"minWidth": "120px"},
    )


def _page_row(path, settings):
    return dmc.TableTr(
        [
            dmc.TableTd(
                dmc.Stack(
                    [
                        dmc.Anchor(settings["name"], href=path, size="sm", fw=600),
                        dmc.Text(path, size="xs", c="dimmed", ff="monospace"),
                    ],
                    gap=0,
                )
            ),
            dmc.TableTd(
                dmc.SegmentedControl(
                    id={"type": "cb-vis", "path": path},
                    value=settings["visibility"],
                    data=[{"value": t, "label": t.capitalize()} for t in TIERS],
                    size="xs",
                    color=_TIER_COLORS.get(settings["visibility"], "blue"),
                )
            ),
            dmc.TableTd(
                dmc.Switch(
                    id={"type": "cb-llms", "path": path},
                    checked=bool(settings["llms_public"]),
                    onLabel="ON",
                    offLabel="OFF",
                    size="md",
                    color="teal",
                ),
                style={"textAlign": "center"},
            ),
            dmc.TableTd(
                dmc.Anchor(
                    DashIconify(icon="tabler:external-link", width=16),
                    href=f"{path.rstrip('/')}/llms.txt",
                    target="_blank",
                ),
                style={"textAlign": "center"},
            ),
        ]
    )


def _build_board():
    pages = controllable_pages()
    counts = {t: 0 for t in TIERS}
    for s in pages.values():
        counts[s["visibility"]] = counts.get(s["visibility"], 0) + 1

    dev_banner = None
    if not clerk_enabled():
        dev_banner = dmc.Alert(
            "Clerk keys are not configured — every tier currently falls open "
            "to public and this board is ungated. Set CLERK_SECRET_KEY / "
            "CLERK_PUBLISHABLE_KEY / CLERK_SIGN_IN_URL / ADMIN_EMAILS in "
            "production.",
            title="Dev mode — auth disabled",
            color="yellow",
            icon=DashIconify(icon="tabler:alert-triangle"),
        )

    return dmc.Container(
        dmc.Stack(
            [
                dmc.Group(
                    [
                        DashIconify(
                            icon="tabler:adjustments-bolt",
                            width=34,
                            color="var(--mantine-color-green-5)",
                        ),
                        dmc.Stack(
                            [
                                dmc.Title("Page Control Board", order=2),
                                dmc.Text(
                                    "Toggle who can see each documentation "
                                    "page and whether its llms.txt is served "
                                    "to anonymous / AI traffic. Changes apply "
                                    "immediately; sitemap entries refresh on "
                                    "restart.",
                                    c="dimmed",
                                    size="sm",
                                ),
                            ],
                            gap=2,
                        ),
                    ],
                    gap="md",
                ),
                dev_banner,
                dmc.Group(
                    [
                        _stat_card(t.capitalize(), counts.get(t, 0), c)
                        for t, c, _ in _TIER_HELP
                    ]
                    + [_stat_card("Total", len(pages), "green")],
                    gap="sm",
                ),
                dmc.Accordion(
                    dmc.AccordionItem(
                        [
                            dmc.AccordionControl("What do the tiers mean?"),
                            dmc.AccordionPanel(
                                dmc.Stack(
                                    [
                                        dmc.Group(
                                            [
                                                dmc.Badge(t.capitalize(),
                                                          color=c,
                                                          variant="light"),
                                                dmc.Text(desc, size="sm",
                                                         c="dimmed"),
                                            ],
                                            gap="sm",
                                        )
                                        for t, c, desc in _TIER_HELP
                                    ],
                                    gap="xs",
                                )
                            ),
                        ],
                        value="tiers",
                    ),
                    variant="contained",
                ),
                dmc.Paper(
                    dmc.Table(
                        [
                            dmc.TableThead(
                                dmc.TableTr(
                                    [
                                        dmc.TableTh("Page"),
                                        dmc.TableTh("Visibility"),
                                        dmc.TableTh("llms.txt public",
                                                    style={"textAlign": "center"}),
                                        dmc.TableTh("llms.txt",
                                                    style={"textAlign": "center"}),
                                    ]
                                )
                            ),
                            dmc.TableTbody(
                                [_page_row(path, settings)
                                 for path, settings in pages.items()]
                            ),
                        ],
                        striped=True,
                        highlightOnHover=True,
                        verticalSpacing="sm",
                    ),
                    withBorder=True,
                    radius="md",
                    p="md",
                ),
                html.Div(id="cb-feedback"),

                # B7: the country guardrail, below the page table. Same gate,
                # same page, different store — one place the owner controls
                # who may read what, and who may reach the origin at all.
                dmc.Divider(mt="lg", mb="sm"),
                _geo_section(),
            ],
            gap="lg",
        ),
        size="lg",
        py="xl",
    )


def layout(**kwargs):
    """Admin-gated at render time; ``**kwargs`` absorbs Clerk handshake params."""
    if clerk_enabled():
        user = current_user()
        if user is None:
            return sign_in_layout("Control Board")
        if not is_admin_user(user):
            return forbidden_layout("Control Board")
    elif not admin_access_open():
        # Fail CLOSED. Everything else in this app degrades to public without
        # Clerk, because docs must stay readable — but this board can hide any
        # page on the site, so an ungated deploy would hand that to anyone who
        # guesses the URL. ALLOW_UNGATED_ADMIN=1 to work on the board locally.
        return hidden_layout()
    return _build_board()


@callback(
    Output("cb-feedback", "children"),
    Input({"type": "cb-vis", "path": ALL}, "value"),
    Input({"type": "cb-llms", "path": ALL}, "checked"),
    prevent_initial_call=True,
)
def save_visibility_change(_vis_values, _llms_values):
    """Persist whichever toggle fired to the override store."""
    trig = ctx.triggered_id
    if not isinstance(trig, dict):
        raise PreventUpdate
    # Server-side re-check, and the half that actually matters: a 404 layout
    # only hides the UI. Pattern-matching callbacks stay callable by anyone
    # who can POST to /_dash-update-component with a reconstructed component
    # id, so the same gate has to run here or the board is still writable.
    if clerk_enabled():
        if not is_admin_user():
            raise PreventUpdate
    elif not admin_access_open():
        raise PreventUpdate

    path = trig["path"]
    new_value = ctx.triggered[0]["value"]
    if trig["type"] == "cb-vis":
        set_visibility(path, new_value)
        message = f"{path} → visibility: {new_value}"
    else:
        set_llms_public(path, bool(new_value))
        message = f"{path} → llms.txt public: {'on' if new_value else 'off'}"

    return dmc.Alert(
        f"Saved {message}  ·  {datetime.now().strftime('%H:%M:%S')}",
        color="teal",
        variant="light",
        icon=DashIconify(icon="tabler:device-floppy"),
        withCloseButton=True,
    )


# ===========================================================================
# B7 — the country guardrail section
# ===========================================================================
# Designed for 2.8's bot x country MATRIX from day one, per the fleet
# addendum: the coarse country axis lives here now, and when `deny_matrix`
# lands the same map gains a per-vendor selector rather than a new page.

# ISO 3166-1 alpha-2 -> alpha-3. Plotly's choropleth wants alpha-3, the edge
# headers and the package both speak alpha-2, and the store holds alpha-2 —
# so exactly one translation table exists, here, at the display edge.
_ALPHA2_TO_ALPHA3 = {
    "AF": "AFG", "AL": "ALB", "AR": "ARG", "AT": "AUT", "AU": "AUS", "BD": "BGD",
    "BE": "BEL", "BG": "BGR", "BR": "BRA", "BY": "BLR", "CA": "CAN", "CH": "CHE",
    "CL": "CHL", "CN": "CHN", "CO": "COL", "CU": "CUB", "CZ": "CZE", "DE": "DEU",
    "DK": "DNK", "EE": "EST", "EG": "EGY", "ES": "ESP", "FI": "FIN", "FR": "FRA",
    "GB": "GBR", "GR": "GRC", "HK": "HKG", "HR": "HRV", "HU": "HUN", "ID": "IDN",
    "IE": "IRL", "IL": "ISR", "IN": "IND", "IQ": "IRQ", "IR": "IRN", "IS": "ISL",
    "IT": "ITA", "JP": "JPN", "KE": "KEN", "KP": "PRK", "KR": "KOR", "KZ": "KAZ",
    "LT": "LTU", "LV": "LVA", "MA": "MAR", "MX": "MEX", "MY": "MYS", "NG": "NGA",
    "NL": "NLD", "NO": "NOR", "NZ": "NZL", "PE": "PER", "PH": "PHL", "PK": "PAK",
    "PL": "POL", "PT": "PRT", "RO": "ROU", "RS": "SRB", "RU": "RUS", "SA": "SAU",
    "SD": "SDN", "SE": "SWE", "SG": "SGP", "SK": "SVK", "SY": "SYR", "TH": "THA",
    "TR": "TUR", "TW": "TWN", "UA": "UKR", "US": "USA", "VE": "VEN", "VN": "VNM",
    "ZA": "ZAF",
}
_ALPHA3_TO_ALPHA2 = {v: k for k, v in _ALPHA2_TO_ALPHA3.items()}


def _geo_figure(denied):
    """The denylist as a choropleth figure.

    Separate from the Graph wrapper because the toggle callback returns a
    FIGURE, not a component — patching `figure` in place is what keeps the
    map's zoom and the click handler alive across an update.
    """
    codes = [_ALPHA2_TO_ALPHA3[c] for c in denied if c in _ALPHA2_TO_ALPHA3]
    figure = {
        "data": [
            {
                "type": "choropleth",
                "locationmode": "ISO-3",
                "locations": codes or ["ATA"],
                "z": [1] * len(codes) if codes else [0],
                "colorscale": [[0, "rgba(0,0,0,0)"], [1, "#e03131"]],
                "showscale": False,
                "marker": {"line": {"color": "rgba(128,128,128,0.35)", "width": 0.4}},
                "hovertemplate": "%{location} — denied<extra></extra>",
            }
        ],
        "layout": {
            "margin": {"r": 0, "t": 0, "l": 0, "b": 0},
            "paper_bgcolor": "rgba(0,0,0,0)",
            "geo": {
                "bgcolor": "rgba(0,0,0,0)",
                "showframe": False,
                "showcoastlines": True,
                "coastlinecolor": "rgba(128,128,128,0.35)",
                "showland": True,
                "landcolor": "rgba(128,128,128,0.12)",
                "projection": {"type": "natural earth"},
            },
        },
    }
    return figure


def _geo_map(denied):
    """The map itself. A click SELECTS a country; it does not commit.

    Deliberate: blocking a country is a compliance action taken against every
    human and every bot in a geography, and a misclick on a world map is very
    easy. The click fills the code field and the operator presses the button.
    """
    return dcc.Graph(
        id="cb-geo-map",
        figure=_geo_figure(denied),
        config={"displayModeBar": False},
        style={"height": "380px"},
    )


def _geo_section():
    denied = policy_store.geo_deny()
    status = policy_store.status()

    warnings = []
    if not status["persistent"]:
        warnings.append(
            dmc.Alert(
                "POLICY_STORE_FILE is not on a mounted disk, so every block "
                "set here vanishes on the next deploy. Attach the render.yaml "
                "disk before relying on this.",
                title="Not persistent",
                color="orange",
                variant="light",
                icon=DashIconify(icon="tabler:database-off"),
            )
        )
    if status["degraded"]:
        warnings.append(
            dmc.Alert(
                "The policy store could not be read and is being treated as "
                "empty (fail-open) — nobody is currently blocked. Check the "
                "file before assuming a block is in force.",
                title="Store degraded",
                color="red",
                variant="light",
                icon=DashIconify(icon="tabler:alert-triangle"),
            )
        )

    return dmc.Stack(
        [
            dmc.Group(
                [
                    DashIconify(icon="tabler:world-cancel", width=26,
                                color="var(--mantine-color-red-5)"),
                    dmc.Stack(
                        [
                            dmc.Title("Country guardrail", order=3),
                            dmc.Text(
                                "A denied country receives 451 on EVERY "
                                "surface — pages, assets, the corpus, "
                                "robots.txt, sitemap.xml, even the favicon — "
                                "humans and bots alike. Applies on the next "
                                "request, in every worker, with no restart.",
                                c="dimmed", size="sm",
                            ),
                        ],
                        gap=2,
                    ),
                ],
                gap="md",
            ),
            *warnings,
            dmc.Alert(
                "This is a compliance guardrail, not a security boundary. The "
                "country comes from an edge header: behind Cloudflare it is "
                "trustworthy, but a client reaching the origin directly can "
                "spoof it. Where a block matters adversarially, add the edge "
                "WAF rule too.",
                color="blue", variant="light",
                icon=DashIconify(icon="tabler:info-circle"),
            ),
            _geo_map(denied),
            dmc.Group(
                [
                    dmc.TextInput(
                        id="cb-geo-code",
                        label="Country code",
                        description="ISO 3166-1 alpha-2, e.g. RU",
                        placeholder="click the map, or type a code",
                        w=220,
                    ),
                    dmc.Button(
                        "Toggle this country",
                        id="cb-geo-toggle",
                        color="red",
                        variant="light",
                        mt=32,
                        leftSection=DashIconify(icon="tabler:hand-stop"),
                    ),
                ],
                gap="md",
                align="flex-start",
            ),
            html.Div(id="cb-geo-current", children=_geo_badges(denied)),
            html.Div(id="cb-geo-feedback"),
            dmc.Text(
                f"Store: {status['path']} · last written {status['mtime_text']} "
                f"· served by pid {status['pid']}",
                size="xs", c="dimmed", ff="monospace",
            ),
            dmc.Text(
                "Two values that flip between refreshes mean different "
                "workers answered — a deployment diagnostic, not a bug.",
                size="xs", c="dimmed",
            ),
        ],
        gap="sm",
    )


def _geo_badges(denied):
    if not denied:
        return dmc.Text(
            "No countries denied. The guardrail is wired and live; an empty "
            "denylist is a strict no-op.",
            size="sm", c="dimmed",
        )
    return dmc.Group(
        [dmc.Badge(code, color="red", variant="filled", size="lg") for code in denied],
        gap="xs",
    )


@callback(
    Output("cb-geo-code", "value"),
    Input("cb-geo-map", "clickData"),
    prevent_initial_call=True,
)
def _country_from_map(click_data):
    """A map click fills the field. It does NOT commit — see _geo_map."""
    if not click_data:
        raise PreventUpdate
    location = (click_data.get("points") or [{}])[0].get("location")
    code = _ALPHA3_TO_ALPHA2.get(location)
    if not code:
        raise PreventUpdate
    return code


@callback(
    Output("cb-geo-feedback", "children"),
    Output("cb-geo-current", "children"),
    Output("cb-geo-map", "figure"),
    Input("cb-geo-toggle", "n_clicks"),
    State("cb-geo-code", "value"),
    prevent_initial_call=True,
)
def _toggle_country(_clicks, code):
    """Commit one country. Re-checks the admin gate SERVER-SIDE.

    The layout gate only hides the UI. A pattern-matching or plain callback
    stays callable by anyone who can POST a reconstructed component id to
    /_dash-update-component, so the same gate has to run here or the board is
    still writable by anyone who reads the page source.
    """
    if clerk_enabled():
        if not is_admin_user():
            raise PreventUpdate
    elif not admin_access_open():
        raise PreventUpdate

    if not code:
        raise PreventUpdate

    try:
        denied, now_denied = policy_store.toggle_country(code)
    except ValueError as exc:
        return (
            dmc.Alert(str(exc), color="red", variant="light",
                      icon=DashIconify(icon="tabler:alert-triangle"),
                      withCloseButton=True),
            no_update,
            no_update,
        )

    message = (
        f"{code.upper()} is now DENIED — the next request from it gets 451 "
        "on every surface."
        if now_denied else
        f"{code.upper()} is allowed again — the next request from it is "
        "served normally."
    )
    return (
        dmc.Alert(
            f"{message}  ·  {datetime.now().strftime('%H:%M:%S')}",
            color="red" if now_denied else "teal",
            variant="light",
            icon=DashIconify(icon="tabler:world-cancel" if now_denied
                             else "tabler:world-check"),
            withCloseButton=True,
        ),
        _geo_badges(denied),
        _geo_figure(denied),
    )

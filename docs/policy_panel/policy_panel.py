"""Showcase C — this host's live effective policy, read-only, plus geo.

Read-only in the same sense the package's operator panel is: it displays and
never writes. The WRITABLE layer is /admin/control-board, which is admin-gated
and re-checks the gate server-side in every write callback.

The geo section is real — 2.7.0 is installed, so the choropleth reflects the
live denylist through `lib.policy_store`, the same callable `configure_geo`
reads on every request.

Exec-module rules: ids all start `plcy-`; no import-time registry walk.
"""
from dash import Input, Output, callback, dcc, html, no_update
import dash_mantine_components as dmc
from dash_iconify import DashIconify
import plotly.graph_objects as go

ID = "plcy"

# ISO 3166-1 alpha-2 -> alpha-3, for the plotly choropleth's `locations`.
# Only the countries a fleet operator is plausibly going to name; anything
# else falls back to a plain list so the map is never the only readout.
ALPHA2_TO_ALPHA3 = {
    "AF": "AFG", "AR": "ARG", "AU": "AUS", "AT": "AUT", "BE": "BEL", "BR": "BRA",
    "BY": "BLR", "CA": "CAN", "CH": "CHE", "CL": "CHL", "CN": "CHN", "CO": "COL",
    "CU": "CUB", "CZ": "CZE", "DE": "DEU", "DK": "DNK", "EG": "EGY", "ES": "ESP",
    "FI": "FIN", "FR": "FRA", "GB": "GBR", "GR": "GRC", "HK": "HKG", "HU": "HUN",
    "ID": "IDN", "IE": "IRL", "IL": "ISR", "IN": "IND", "IQ": "IRQ", "IR": "IRN",
    "IT": "ITA", "JP": "JPN", "KE": "KEN", "KP": "PRK", "KR": "KOR", "MX": "MEX",
    "MY": "MYS", "NG": "NGA", "NL": "NLD", "NO": "NOR", "NZ": "NZL", "PE": "PER",
    "PH": "PHL", "PK": "PAK", "PL": "POL", "PT": "PRT", "RO": "ROU", "RU": "RUS",
    "SA": "SAU", "SE": "SWE", "SG": "SGP", "SY": "SYR", "TH": "THA", "TR": "TUR",
    "TW": "TWN", "UA": "UKR", "US": "USA", "VE": "VEN", "VN": "VNM", "ZA": "ZAF",
}

component = html.Div(
    [
        dmc.Group(
            [
                DashIconify(icon="tabler:shield-lock", width=22),
                dmc.Text("Live effective policy for this host", fw=600),
                dmc.Badge("read-only", color="gray", variant="light"),
            ],
            gap="sm",
        ),
        dmc.Space(h="sm"),
        html.Div(id=f"{ID}-summary"),
        dmc.Space(h="lg"),
        dmc.Text("Country guardrail", fw=600, size="sm"),
        dmc.Text(
            "Denied countries receive 451 on every surface — pages, assets, "
            "the corpus, robots.txt, even the favicon. The list is read from "
            "the policy store on every request, so the control board changes "
            "it with no restart.",
            size="xs", c="dimmed",
        ),
        dmc.Space(h="sm"),
        dcc.Graph(id=f"{ID}-map", config={"displayModeBar": False},
                  style={"height": "420px"}),
        html.Div(id=f"{ID}-geo-detail"),
        dmc.Space(h="lg"),
        dmc.Text("Simulate a request", fw=600, size="sm"),
        dmc.Group(
            [
                dmc.Select(id=f"{ID}-sim-page", label="Page", searchable=True, w=280,
                           placeholder="Loading…"),
                dmc.Select(
                    id=f"{ID}-sim-audience", label="Audience", w=240,
                    data=[
                        {"value": "human", "label": "A person in a browser"},
                        {"value": "search", "label": "AI search fetcher"},
                        {"value": "training", "label": "AI training crawler"},
                        {"value": "traditional", "label": "Googlebot"},
                    ],
                    value="human",
                ),
                dmc.TextInput(id=f"{ID}-sim-country", label="CF-IPCountry",
                              placeholder="e.g. DE (blank = unknown)", w=180),
            ],
            gap="md", align="flex-start",
        ),
        dmc.Space(h="sm"),
        html.Div(id=f"{ID}-sim-verdict"),
        dcc.Interval(id=f"{ID}-boot", interval=250, max_intervals=1),
        dcc.Interval(id=f"{ID}-poll", interval=5000),
    ]
)


@callback(
    Output(f"{ID}-sim-page", "data"),
    Output(f"{ID}-sim-page", "value"),
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
    return (options, "/") if options else (no_update, no_update)


@callback(
    Output(f"{ID}-summary", "children"),
    Output(f"{ID}-map", "figure"),
    Output(f"{ID}-geo-detail", "children"),
    Input(f"{ID}-poll", "n_intervals"),
)
def _policy(_tick):
    """Re-read on a poll so a board toggle shows up here without a refresh."""
    from lib import policy_store

    denied = policy_store.geo_deny()
    summary = _summary_cards(denied)
    return summary, _choropleth(denied), _geo_detail(denied)


def _summary_cards(denied):
    import dash
    from dash_improve_my_llms import __version__ as pkg_version

    from dash_improve_my_llms.vendors import effective_policies

    try:
        policies = effective_policies(getattr(dash.get_app(), "_robots_config", None))
    except Exception:
        # The fold reads a live config object; a public showcase degrades to
        # zeroes rather than throwing an error toast at a reader.
        policies = {}
    blocked = sum(1 for value in policies.values() if value == "block")
    metered = sum(1 for value in policies.values() if value == "meter")

    cards = [
        ("Package", pkg_version, "blue"),
        ("Vendors blocked", blocked, "red"),
        ("Vendors metered", metered, "yellow"),
        ("Countries denied", len(denied), "grape"),
    ]
    return dmc.Group(
        [
            dmc.Paper(
                dmc.Stack(
                    [
                        dmc.Text(str(value), size="24px", fw=700, c=color),
                        dmc.Text(label, size="xs", c="dimmed", tt="uppercase"),
                    ],
                    gap=2, align="center",
                ),
                withBorder=True, radius="md", p="md", style={"minWidth": "140px"},
            )
            for label, value, color in cards
        ],
        gap="sm",
    )


def _choropleth(denied):
    """Allow / deny, as a world map. Read-only — the board owns the toggles."""
    codes = [ALPHA2_TO_ALPHA3.get(code) for code in denied]
    codes = [code for code in codes if code]

    figure = go.Figure(
        go.Choropleth(
            locations=codes or ["ATA"],
            z=[1] * len(codes) if codes else [0],
            locationmode="ISO-3",
            colorscale=[[0, "rgba(0,0,0,0)"], [1, "#e03131"]],
            showscale=False,
            marker_line_color="rgba(128,128,128,0.35)",
            marker_line_width=0.4,
            hovertemplate="%{location} — denied (451)<extra></extra>",
        )
    )
    figure.update_geos(
        showcoastlines=True, coastlinecolor="rgba(128,128,128,0.35)",
        showland=True, landcolor="rgba(128,128,128,0.12)",
        showframe=False, projection_type="natural earth",
        bgcolor="rgba(0,0,0,0)",
    )
    figure.update_layout(
        margin={"r": 0, "t": 0, "l": 0, "b": 0},
        paper_bgcolor="rgba(0,0,0,0)",
        geo_bgcolor="rgba(0,0,0,0)",
    )
    return figure


def _geo_detail(denied):
    if not denied:
        return dmc.Alert(
            "No countries are denied. The guardrail is wired and configured — "
            "an empty denylist is a strict no-op, so every response is "
            "byte-identical to a build without it.",
            color="teal", variant="light",
            icon=DashIconify(icon="tabler:world-check"),
        )
    return dmc.Group(
        [dmc.Badge(code, color="red", variant="filled") for code in denied]
        + [dmc.Text("→ 451 on every surface", size="xs", c="dimmed")],
        gap="xs",
    )


@callback(
    Output(f"{ID}-sim-verdict", "children"),
    Input(f"{ID}-sim-page", "value"),
    Input(f"{ID}-sim-audience", "value"),
    Input(f"{ID}-sim-country", "value"),
)
def _simulate(path, audience, country):
    """Resolve a hypothetical request through the real in-process logic."""
    if not path:
        return None

    from lib import access as site_access
    from lib import policy_store

    steps = []

    denied = policy_store.geo_deny()
    resolved = (country or "").strip().upper()
    known = len(resolved) == 2 and resolved.isalpha() and resolved not in ("XX", "T1")
    if not known:
        steps.append(("Country", "unknown → allowed (the fail-open default)", "teal"))
    elif resolved in denied:
        steps.append(("Country", f"{resolved} is denied → 451, and nothing else runs", "red"))
        return _verdict_list(steps, "451 Unavailable For Legal Reasons", "red")
    else:
        steps.append(("Country", f"{resolved} is not denied → continue", "teal"))

    ua_class = audience or "human"
    if ua_class == "human":
        steps.append(("Vendor policy", "humans are never subject to bot policy", "teal"))
    else:
        policy = _policy_for_class(ua_class)
        colour = {"allow": "teal", "block": "red", "meter": "yellow"}[policy]
        steps.append(("Vendor policy", f"{ua_class} class → {policy}", colour))
        if policy == "block" and not path.endswith("llms.txt"):
            return _verdict_list(steps, "403 Forbidden", "red")

    try:
        tier = site_access.local_tier(path)
    except Exception:
        tier = "public"
    steps.append(("Page tier", f"{tier}", "teal" if tier == "public" else "blue"))

    if tier == "public":
        return _verdict_list(steps, "200 OK — the page is served", "teal")
    return _verdict_list(steps, f"gated ({tier}) — the sign-in card is served", "blue")


def _policy_for_class(ua_class):
    import dash

    try:
        from dash_improve_my_llms.vendors import VENDORS, effective_policies

        policies = effective_policies(getattr(dash.get_app(), "_robots_config", None))
    except Exception:
        return "allow"
    for vendor in VENDORS:
        if vendor.cls == ua_class:
            return policies.get(vendor.key, "allow")
    return "allow"


def _verdict_list(steps, outcome, colour):
    return dmc.Stack(
        [
            dmc.Timeline(
                [
                    dmc.TimelineItem(
                        title=label,
                        children=dmc.Text(detail, size="xs", c="dimmed"),
                    )
                    for label, detail, _c in steps
                ],
                active=len(steps),
                bulletSize=14,
                lineWidth=2,
            ),
            dmc.Alert(outcome, color=colour, variant="light",
                      icon=DashIconify(icon="tabler:flag-check")),
        ],
        gap="sm",
    )

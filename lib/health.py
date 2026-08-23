"""
``/healthz`` liveness probe for the Flask and Quart backends.

The 2plot.ai hub sweeps every satellite's ``/healthz`` once an hour and records
up/down + latency — that's the "Satellite health & reach" panel on ``/traffic``
(the traffic rollup this app POSTs supplies the other half). The FastAPI build
already declares a typed ``/healthz`` in ``lib/asgi_routes`` so it shows up in
Swagger; this module gives the other two backends the same endpoint, so the
probe result doesn't depend on which backend a deployment happens to run.

Keep it cheap: the hub measures the round trip, so any work done here is
reported back as this app being slow.
"""
from __future__ import annotations

import os

import dash


def _resolved_country(headers=None) -> str:
    """`geo.explain_resolution` over THIS request's headers, or a reason.

    Reads the request headers directly rather than anything the package
    threads through, so it answers "did the header reach this app at all?"
    independently of how the enforcement seam is wired.

    Each route passes its own framework's headers explicitly. The first
    version read Flask's request context, which made the FastAPI and Quart
    lanes answer "no request context" forever — a diagnostic that silently
    stops diagnosing on two of three backends. pannellum's production
    healthz (FastAPI) was the host that showed it; ported here from
    template 1.6.12 before this fork's own FastAPI lane could ship it.
    `normalize_headers` accepts Flask/Starlette/Quart/dict and never
    raises. The Flask-context fallback stays for callers that pass nothing.
    """
    try:
        from dash_improve_my_llms import geo
        from dash_improve_my_llms._headers import normalize_headers
    except Exception:
        return "unavailable (pre-2.7.0 package)"

    try:
        if headers is not None:
            return geo.explain_resolution(normalize_headers(headers))

        from flask import has_request_context, request

        if not has_request_context():
            return "no request context"
        return geo.explain_resolution(normalize_headers(request.headers))
    except Exception:
        return "unavailable"


def health_payload(backend: str, headers=None) -> dict:
    payload = {"ok": True, "backend": backend, "dash_version": dash.__version__}
    # Which commit the RUNNING instance was built from. This is what lets CD
    # verify the artifact it shipped rather than whichever build happens to
    # be serving: a Render service with a disk restarts with a blip instead
    # of overlapping instances, so a bare 200 proves nothing about WHICH
    # build answered (the muicharts finding, 2026-08-21 — its battery had
    # been verifying the previous release on every run, invisibly, until a
    # new surface made the race lose). Optional on purpose: omitted where
    # the platform variable does not exist, so the fleet's probe contract
    # is unchanged.
    build = os.environ.get("RENDER_GIT_COMMIT")
    if build:
        payload["build"] = build

    # WHICH satellite answered. `build` says which commit, this says which
    # app — and on a fleet where several hosts share a template and a
    # hostname can be repointed, "is this the site I think it is?" is a
    # different question from "is this the build I shipped?". Cheap, and the
    # hub's sweep gets it for free.
    payload["app"] = os.environ.get("SATELLITE_APP_KEY") or "unknown"

    # The geo guardrail's LIVE state. Added 2026-08-23 after a production
    # verification could not answer "is the denylist actually in force?"
    # from outside: the control board and the public policy showcase both
    # showed countries denied while every request was served 200, and the
    # only surfaces that could have settled it (the boot log, the operator
    # panel) need credentials this check does not have.
    #
    # Counts and flags only — never the country codes. The codes are already
    # public on /showcase/policy-panel, but a health endpoint should not be
    # the place anyone learns policy.
    try:
        from dash_improve_my_llms import geo

        payload["geo"] = {
            "configured": bool(geo.is_configured()),
            "denied": len(geo.effective_policy().get("deny_countries") or []),
            # THE per-host check docs/GEO.md mandates before trusting a
            # denylist: "this request resolved to DE (via cf-ipcountry)".
            # GEO.md points at the operator panel for it, which is
            # token-gated — so on a host where nobody has the token, the one
            # check the docs call mandatory is unavailable. It costs nothing
            # here and reveals only the caller's own country back to them,
            # which Cloudflare's /cdn-cgi/trace already does.
            #
            # It also localises a failure: geo can be configured with a full
            # denylist and still never match, if the country header is not
            # reaching the app. "configured: true, denied: 7, resolved:
            # unknown" says that in one line.
            "resolved": _resolved_country(headers),
        }
    except Exception:  # never let a diagnostic break the health probe
        payload["geo"] = {"configured": False, "denied": 0, "error": True}

    return payload


def register_health_route(app, backend: str) -> None:
    """Mount ``/healthz`` on Flask/Quart. No-op on FastAPI (already typed)."""
    if backend == "fastapi":
        return

    server = app.server

    # Built PER REQUEST, not once at registration. It used to be a snapshot
    # closed over by the route — harmless while every field was static
    # (ok/backend/dash_version/build never change for a running process), and
    # silently wrong the moment one is not. This route is registered at
    # run.py:566 and `configure_geo` runs ~150 lines later, so a snapshot
    # reported the guardrail as unconfigured on a host where it is configured
    # — the diagnostic lying in exactly the situation it exists for.
    #
    # The request's own headers go with it, per backend: geo's `resolved`
    # reads the country header from THIS request, and the Flask-context
    # fallback below can only ever see a Flask request.
    if backend == "quart":
        from quart import jsonify, request

        @server.get("/healthz")
        async def _healthz():  # pragma: no cover — quart runtime
            return jsonify(health_payload(backend, headers=request.headers))
    else:
        from flask import jsonify, request

        @server.get("/healthz")
        def _healthz():
            return jsonify(health_payload(backend, headers=request.headers))

    print(f"[boilerplate] /healthz registered ({backend}) — "
          "the 2plot.ai hourly health sweep probes this path.")

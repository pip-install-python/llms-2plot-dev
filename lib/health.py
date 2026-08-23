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


def health_payload(backend: str) -> dict:
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
    if backend == "quart":
        from quart import jsonify

        @server.get("/healthz")
        async def _healthz():  # pragma: no cover — quart runtime
            return jsonify(health_payload(backend))
    else:
        from flask import jsonify

        @server.get("/healthz")
        def _healthz():
            return jsonify(health_payload(backend))

    print(f"[boilerplate] /healthz registered ({backend}) — "
          "the 2plot.ai hourly health sweep probes this path.")

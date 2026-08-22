"""The writable policy store — this site's half of the 2.7.0 callable seam.

`dash-improve-my-llms` 2.7.0 accepts a **zero-argument callable** wherever it
accepts a static policy value, and evaluates it on **every request**:

    configure_geo(deny_countries=policy_store.geo_deny)
    RobotsConfig(vendor_policy=policy_store.vendor_policy)

That callable is the entire integration surface. The package stays zero-dep
and never learns what a disk is; this module owns persistence, validation and
concurrency, and hands back a plain list or dict. Flip a country on the
control board and the next request in every worker answers 451 — no restart,
no redeploy, no signal, no shared cache server.

Why a separate store from :mod:`lib.page_visibility`
----------------------------------------------------
The inherited board's store answers "who may READ this page" and is consulted
by :mod:`lib.access` at render time. This one answers "who may reach this
ORIGIN at all" and is consulted by the package's middleware before routing.
Different blast radius, different validation rules, different failure
posture — and one corrupt JSON file should not take out both. They share a
directory and nothing else.

The three hard-won behaviours, inherited from the template's store and kept
deliberately:

* **Cross-worker reconciliation, on the request itself.** gunicorn runs N
  workers; a board POST mutates one. Every read re-stats the file and
  re-parses only when ``(mtime_ns, size)`` moved. That is one ``os.stat`` per
  request — deliberately NOT the template's 1s throttle, because the geo
  seam's whole promise is "the NEXT request", and a throttle makes that
  "the next request, probably, within a second". A page-visibility toggle
  can afford to land a second late; a compliance block cannot.

* **Both persistence guards.** Boot warns when ``POLICY_STORE_FILE`` is
  unset, and when it points under ``/var/`` at a directory that is not
  actually a mount (a bare ``mkdir`` behaves identically until the next
  deploy wipes it).

* **Fail-open reads, validated writes.** A missing, unreadable, malformed or
  wrong-shaped store yields the empty policy and logs once — matching the
  contract docs/GEO.md states for a raising callable, because from the
  package's side that is exactly what this is. Writes validate first and
  refuse to persist garbage, so the fail-open path stays a bug-tolerance
  measure rather than a routine one.

Concurrency: writes take an exclusive ``flock`` for the whole
read-modify-write and land via ``os.replace``, so a reader never sees a torn
file and two workers toggling different countries cannot lose one another's
edit.
"""
from __future__ import annotations

import errno
import fcntl
import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_STORE_PATH = Path(os.environ.get("POLICY_STORE_FILE") or "policy_overrides.json")

# The shape this module persists. Anything else in the file is preserved on
# write but ignored on read, so a future key (2.8's bot x country matrix)
# added by a newer worker survives an older worker's toggle.
_GEO_DENY = "geo_deny"
_GEO_UNKNOWN = "geo_unknown"
_VENDOR_POLICY = "vendor_policy"

VENDOR_ACTIONS = ("allow", "block", "meter")
UNKNOWN_POSTURES = ("allow", "deny")

_lock = threading.Lock()
_cache: dict[str, Any] = {}
_cache_stamp: tuple[int, int] | None = None
_warned: set[str] = set()


def path() -> Path:
    """Where this process reads and writes policy."""
    return _STORE_PATH


def _warn_once(key: str, message: str, *args) -> None:
    """One line per distinct failure, however many requests hit it.

    The seam runs inside every request. A store that goes unreadable would
    otherwise write a log line per request forever, which is how a
    degradation becomes an outage of its own.
    """
    if key in _warned:
        return
    _warned.add(key)
    logger.warning(message, *args)


# ---------------------------------------------------------------------------
# Validation — the same ISO rules the package applies to a static list
# ---------------------------------------------------------------------------

def normalize_country(code: Any) -> str | None:
    """``"de"`` -> ``"DE"``; anything that is not two ASCII letters -> None.

    Mirrors the package's own ``_normalize_codes``. Validating here as well is
    not redundant: the package's static path raises ``ValueError`` at config
    time, but a CALLABLE that returns junk is treated as an empty denylist and
    fails OPEN. An invalid code that reaches the store would therefore not
    block anything and not say why. Refusing it at the write is the only place
    the operator finds out.
    """
    if not isinstance(code, str):
        return None
    code = code.strip().upper()
    if len(code) != 2 or not code.isascii() or not code.isalpha():
        return None
    # The package treats these as "unknown", never as a country; storing one
    # would create a denylist entry that can never match.
    if code in ("XX", "T1"):
        return None
    return code


def _clean_deny(raw: Any) -> list[str]:
    if not isinstance(raw, (list, tuple)):
        return []
    seen: list[str] = []
    for item in raw:
        code = normalize_country(item)
        if code and code not in seen:
            seen.append(code)
    return sorted(seen)


def known_vendors() -> dict[str, str]:
    """``{registry key: display name}`` from the package, or ``{}``.

    Best-effort by design: the registry is a 2.7.0 surface, and this module
    has to keep importing on the 2.6.1 floor requirements.txt still pins.
    """
    try:
        from dash_improve_my_llms.vendors import VENDORS

        return {v.key: v.display for v in VENDORS}
    except Exception:
        return {}


def normalize_vendor(name: Any) -> str | None:
    """``"ClaudeBot"`` / ``"claudebot"`` -> the registry KEY, or None.

    The package's ``vendor_policy`` map is keyed on the registry key, and an
    unrecognised key is logged and IGNORED — so a board that stored the
    display name would show an override that quietly does nothing. Same
    reasoning as :func:`normalize_country`: refuse at the write, because the
    write is the only place the operator finds out.
    """
    if not isinstance(name, str) or not name.strip():
        return None
    candidate = name.strip().lower()
    registry = known_vendors()
    if not registry:
        return candidate  # pre-2.7.0: nothing to validate against
    if candidate in registry:
        return candidate
    # Accept a display name too — it is what the board's table shows.
    for key, display in registry.items():
        if display.lower() == candidate:
            return key
    return None


def _clean_vendor_policy(raw: Any) -> dict[str, str]:
    if not isinstance(raw, dict):
        return {}
    out: dict[str, str] = {}
    for name, action in raw.items():
        key = normalize_vendor(name)
        if key is None:
            continue
        if not isinstance(action, str) or action.lower() not in VENDOR_ACTIONS:
            continue
        out[key] = action.lower()
    return out


# ---------------------------------------------------------------------------
# Reading — per request, cheap, and never raising
# ---------------------------------------------------------------------------

def _read() -> dict[str, Any]:
    """The current store contents, re-parsed only when the file moved.

    Never raises. Every failure path returns the empty policy, because this
    runs inside the request path of a package that promises to fail open.
    """
    global _cache, _cache_stamp
    try:
        st = _STORE_PATH.stat()
    except OSError as exc:
        if exc.errno != errno.ENOENT:
            _warn_once("stat", "policy store %s unreadable (%s) — empty policy",
                       _STORE_PATH, exc)
        # No file is the normal unconfigured state, not a failure: an app that
        # has never opened the board has no store, and must behave exactly
        # like an app with no board at all.
        if _cache_stamp is not None:
            with _lock:
                _cache, _cache_stamp = {}, None
        return {}

    stamp = (st.st_mtime_ns, st.st_size)
    if stamp == _cache_stamp:
        return _cache

    with _lock:
        if stamp == _cache_stamp:  # another thread just reloaded
            return _cache
        try:
            with _STORE_PATH.open("r", encoding="utf-8") as fh:
                fcntl.flock(fh.fileno(), fcntl.LOCK_SH)
                try:
                    loaded = json.load(fh)
                finally:
                    fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
            if not isinstance(loaded, dict):
                raise ValueError(f"top level is {type(loaded).__name__}, not an object")
            _cache = loaded
            _warned.discard("parse")
        except Exception as exc:
            _warn_once("parse", "policy store %s malformed (%s) — empty policy",
                       _STORE_PATH, exc)
            _cache = {}
        _cache_stamp = stamp
        return _cache


# ---------------------------------------------------------------------------
# THE SEAM — the callables handed to the package
# ---------------------------------------------------------------------------

def geo_deny() -> list[str]:
    """``configure_geo(deny_countries=policy_store.geo_deny)``.

    Zero-argument, called by the package on every request, and contractually
    forbidden from raising or doing I/O beyond this one local stat+read.
    """
    return _clean_deny(_read().get(_GEO_DENY))


def geo_unknown() -> str:
    """Posture for requests whose country will not resolve.

    NOT a callable seam — ``configure_geo(unknown=...)`` takes a plain string
    read once at config time. The board writes it, and run.py reads it at boot
    only, so the UI says so.
    """
    value = _read().get(_GEO_UNKNOWN)
    return value if value in UNKNOWN_POSTURES else "allow"


def vendor_policy() -> dict[str, str]:
    """``RobotsConfig(vendor_policy=policy_store.vendor_policy)``.

    Read per request by the middleware AND per render by robots.txt, which is
    what keeps the published promise and the enforced behaviour identical.
    """
    return _clean_vendor_policy(_read().get(_VENDOR_POLICY))


# ---------------------------------------------------------------------------
# Writing — validated, flocked, atomic
# ---------------------------------------------------------------------------

def _write(mutate) -> dict[str, Any]:
    """Read-modify-write under an exclusive lock, landing atomically.

    ``mutate`` receives the current document and edits it in place. The lock
    is held across the whole cycle so two workers toggling different countries
    cannot lose one another's edit; ``os.replace`` is what stops a concurrent
    READER seeing half a file.
    """
    global _cache, _cache_stamp
    _STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    lock_path = _STORE_PATH.with_suffix(_STORE_PATH.suffix + ".lock")

    with _lock:
        with lock_path.open("a+") as lock_fh:
            fcntl.flock(lock_fh.fileno(), fcntl.LOCK_EX)
            try:
                try:
                    doc = json.loads(_STORE_PATH.read_text(encoding="utf-8"))
                    if not isinstance(doc, dict):
                        doc = {}
                except (OSError, ValueError):
                    doc = {}

                mutate(doc)

                tmp = _STORE_PATH.with_suffix(_STORE_PATH.suffix + ".tmp")
                tmp.write_text(json.dumps(doc, indent=2, sort_keys=True),
                               encoding="utf-8")
                os.replace(tmp, _STORE_PATH)
            finally:
                fcntl.flock(lock_fh.fileno(), fcntl.LOCK_UN)

        # Invalidate rather than adopt: the file we just wrote is the truth,
        # and re-reading it through the normal path keeps exactly one parser.
        _cache, _cache_stamp = {}, None
        _warned.discard("parse")
    return _read()


def set_geo_deny(codes) -> list[str]:
    """Replace the denylist. Returns what was actually stored."""
    cleaned = _clean_deny(codes)

    def mutate(doc):
        doc[_GEO_DENY] = cleaned

    _write(mutate)
    return cleaned


def toggle_country(code: str) -> tuple[list[str], bool]:
    """Flip one country. Returns ``(denylist, now_denied)``.

    Invalid codes are refused rather than silently dropped — see
    :func:`normalize_country` for why a bad code is worse than no code.
    """
    normalized = normalize_country(code)
    if normalized is None:
        raise ValueError(
            f"{code!r} is not an ISO 3166-1 alpha-2 country code. "
            "The package treats anything else as 'unknown', so this entry "
            "would never match a request and the block would silently do "
            "nothing."
        )

    state = {}

    def mutate(doc):
        current = _clean_deny(doc.get(_GEO_DENY))
        if normalized in current:
            current.remove(normalized)
            state["denied"] = False
        else:
            current.append(normalized)
            state["denied"] = True
        doc[_GEO_DENY] = sorted(current)

    _write(mutate)
    return geo_deny(), state["denied"]


def set_geo_unknown(posture: str) -> str:
    if posture not in UNKNOWN_POSTURES:
        raise ValueError(f"unknown posture must be one of {UNKNOWN_POSTURES}")

    def mutate(doc):
        doc[_GEO_UNKNOWN] = posture

    _write(mutate)
    return posture


def set_vendor_action(vendor: str, action: str) -> dict[str, str]:
    """Set one vendor's policy. ``action='allow'`` removes the override."""
    key = normalize_vendor(vendor)
    if key is None:
        raise ValueError(
            f"{vendor!r} is not a known bot vendor. The package keys "
            "vendor_policy on its registry key and IGNORES anything else "
            "with a log line, so this override would silently do nothing. "
            f"Known: {', '.join(sorted(known_vendors())) or '(registry unavailable)'}"
        )
    if action not in VENDOR_ACTIONS:
        raise ValueError(f"action must be one of {VENDOR_ACTIONS}")

    def mutate(doc):
        current = _clean_vendor_policy(doc.get(_VENDOR_POLICY))
        current[key] = action
        doc[_VENDOR_POLICY] = current

    _write(mutate)
    return vendor_policy()


def clear_vendor_action(vendor: str) -> dict[str, str]:
    key = normalize_vendor(vendor)

    def mutate(doc):
        current = _clean_vendor_policy(doc.get(_VENDOR_POLICY))
        current.pop(key or (vendor or "").strip(), None)
        doc[_VENDOR_POLICY] = current

    _write(mutate)
    return vendor_policy()


# ---------------------------------------------------------------------------
# What the board shows about itself
# ---------------------------------------------------------------------------

def status() -> dict[str, Any]:
    """Store health for the board's footer.

    ``pid`` and ``mtime`` together are the cross-worker diagnostic: refresh
    twice, and a pid that changes while mtime holds steady proves every worker
    is reading the same store.
    """
    try:
        st = _STORE_PATH.stat()
        exists, mtime, size = True, st.st_mtime, st.st_size
    except OSError:
        exists, mtime, size = False, None, 0

    return {
        "path": str(_STORE_PATH),
        "exists": exists,
        "mtime": mtime,
        "mtime_text": (time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(mtime))
                       if mtime else "never written"),
        "size": size,
        "pid": os.getpid(),
        "degraded": "parse" in _warned or "stat" in _warned,
        "persistent": _persistent(),
    }


def _persistent() -> bool:
    configured = os.environ.get("POLICY_STORE_FILE")
    if not configured:
        return False
    p = Path(configured)
    if str(p).startswith("/var/") and len(p.parts) > 2:
        return os.path.ismount(str(Path("/") / p.parts[1] / p.parts[2]))
    return True


def persistence_warning() -> None:
    """Loud at boot when board writes would not survive a redeploy.

    Same two shapes lib/page_visibility.py guards, and for the same reason:
    both were observed live on the pilot host. A geo denylist that silently
    resets on deploy is worse than a page-visibility toggle that does, because
    nothing on the site looks different afterwards — the block simply stops.
    """
    configured = os.environ.get("POLICY_STORE_FILE")
    if not configured:
        print(
            "[policy] WARNING: POLICY_STORE_FILE unset — geo and vendor "
            "policy are writing to the app directory and will NOT survive a "
            "redeploy. Set POLICY_STORE_FILE=/var/data/policy_overrides.json "
            "on the service (render.yaml declares it, but only a Blueprint "
            "sync or a dashboard add makes the disk live)."
        )
        return
    if not _persistent():
        anchor = Path(configured)
        anchor = Path("/") / anchor.parts[1] / anchor.parts[2] \
            if len(anchor.parts) > 2 else anchor.parent
        print(
            f"[policy] WARNING: {anchor} is not a mounted disk on this "
            "instance — the geo denylist will vanish on the next deploy. "
            "Attach the render.yaml disk (Blueprint sync, or add it in the "
            "dashboard)."
        )


def reset_for_tests() -> None:
    """Drop the in-process cache and the warn-once ledger."""
    global _cache, _cache_stamp
    with _lock:
        _cache, _cache_stamp = {}, None
    _warned.clear()

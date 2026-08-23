"""Stylesheet hygiene: never style Mantine's private hashed classes.

Mantine stamps every component part with a build-generated class like
``m_b8a05bbd`` alongside the stable ``mantine-<Component>-<part>`` class.
The hashes are private internals, version-coupled by construction: a rule
targeting one either stops matching after a dependency bump (fails
silently) or starts matching a different component (applies geometry to
the wrong thing). Three forks have now paid for this class of rule —
leaflet's drawer floated because of a legacy ``.m_b8a05bbd`` margin,
emojimart's drawer was pinned at 63vh through Mantine's Drawer content
hash, and excalidraw inherited two dead-or-harmful hashed rules from this
very template. The fossils were removed from ``assets/main.css`` in 1.6.5;
this test keeps them out, fleet-wide, because forks copy this file.

Style the static classes (``aside.mantine-AppShell-aside``) or use the
DMC Styles API instead.
"""

from __future__ import annotations

import re
from pathlib import Path

ASSETS = Path(__file__).resolve().parent.parent / "assets"

# Mantine build hashes: m_ followed by 6-8 hex chars. The selector form
# (leading dot) is what a stylesheet rule would use.
HASHED_SELECTOR = re.compile(r"\.m_[0-9a-f]{6,8}\b")


def _strip_comments(css: str) -> str:
    # Tombstone comments are allowed to NAME retired hashes; only live
    # selectors are defects.
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def test_no_mantine_hashed_selectors_in_assets():
    offenders: list[str] = []
    for sheet in sorted(ASSETS.glob("*.css")):
        text = _strip_comments(sheet.read_text(encoding="utf-8"))
        for match in HASHED_SELECTOR.finditer(text):
            offenders.append(f"{sheet.name}: {match.group(0)}")
    assert offenders == [], (
        "Hashed Mantine selectors found — these are private, version-coupled "
        "internals that break silently on every DMC bump. Use the static "
        "mantine-<Component>-<part> classes or the Styles API instead: "
        f"{offenders}"
    )


# ---------------------------------------------------------------------------
# Rules keyed on CONTENT rather than structure
# ---------------------------------------------------------------------------
# Same family as the hashed-class rules above: a selector coupled to
# something that is not structural, which therefore stops matching for a
# reason nobody connects to layout.
#
# This template shipped `img[alt=logo] { width: 100% }`, and the home page's
# hero happened to be captioned "logo". Renaming that alt during this fork's
# identity rebuild — a pure copy edit, reviewed as prose — dropped the
# constraint and let a 1200px image overflow every phone. Nothing about an
# image's caption should decide whether it fits the screen.

CONTENT_KEYED_SELECTOR = re.compile(r"\[\s*(alt|title|placeholder)\s*[~^$*|]?=")


def test_no_rule_is_keyed_on_content_attributes():
    offenders: list[str] = []
    for sheet in sorted(ASSETS.glob("*.css")):
        text = _strip_comments(sheet.read_text(encoding="utf-8"))
        for line_no, line in enumerate(text.splitlines(), 1):
            if CONTENT_KEYED_SELECTOR.search(line):
                offenders.append(f"{sheet.name}:{line_no}: {line.strip()[:80]}")

    assert offenders == [], (
        "stylesheet rules keyed on alt/title/placeholder text: an editorial "
        f"change to the copy silently changes the layout. {offenders}"
    )

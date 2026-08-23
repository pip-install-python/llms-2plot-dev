from pathlib import Path

import frontmatter
import dash_mantine_components as dmc
from dash import dcc, register_page

from lib.constants import (
    OG_IMAGE_URL,
    PAGE_TITLE_PREFIX,
    SITE_BRAND,
    SITE_DESCRIPTION,
)
from lib.versions import substitute_versions

register_page(
    __name__,
    "/",
    title=PAGE_TITLE_PREFIX + "Home",
    # Dash emits `description`, `og:description` and `twitter:description` for
    # every page from this argument, and emits them EMPTY when it is missing —
    # which is what the home page, the most-linked page on the site, was doing.
    description=SITE_DESCRIPTION,
    # The most-shared page on the site. See lib.constants.OG_IMAGE_URL for why
    # this is explicit rather than inferred from assets/.
    image_url=OG_IMAGE_URL,
)

directory = "docs"

# read the home page markdown
md_file = Path("pages") / "home.md"

post = frontmatter.loads(md_file.read_text())
metadata, content = post.metadata, post.content

# Same {{VERSION:<distribution>}} substitution pages/markdown.py applies to
# the docs: home.md says "Powered by dash-improve-my-llms <version>" on the
# most-read surface in the network (/llms.txt), so the number must come from
# the installed package, never from prose — "Powered by 2.3.4" shipped for
# months while a newer package was actually serving the site.
content = substitute_versions(content, source=str(md_file))

# Module-level LLMS_DOC — dash-improve-my-llms picks this up automatically
# and serves it as the opening prose of /llms.txt. No layout walking, no
# extraction.
LLMS_DOC = content

# The hero is a COMPONENT, not a markdown image, for two reasons.
#
# Presentation: `dcc.Markdown` renders `![alt](src)` as a bare <img> with no
# constraint, so a 1200px card overflows every phone. The template papered
# over that with `img[alt=logo] { width: 100% }` in main.css — CSS keyed on
# ALT TEXT — so renaming the alt during the identity rebuild silently broke
# the layout on xs/sm. dmc.Image carries its own responsive root styles and
# cannot be detached from them by an editorial change.
#
# Corpus: home.md IS this site's /llms.txt prose. A decorative hero belongs
# in the layout, not in the document an agent reads.
#
# `src` is OG_IMAGE_URL — the same constant the social card, the crawler
# document and the JSON-LD already use, so the card and the hero cannot
# drift apart. `fallbackSrc` is the locally rendered copy: the CDN is a
# third party, and a hero that vanishes when someone else's bucket is
# unreachable is a worse failure than one that renders slightly differently.
hero = dmc.Image(
    src=OG_IMAGE_URL,
    alt=SITE_BRAND,
    radius="md",
    # `contain`, not the default `cover`: the box below is the card's own
    # 1200x630, so contain fits it exactly and can never crop the wordmark.
    fit="contain",
    fallbackSrc="/assets/hero.png",
    # Reserves the box before the image loads, which is what the DMC docs
    # recommend a fixed `h` for — but as a RATIO, so it stays correct at
    # every width instead of letterboxing on wide screens.
    style={"aspectRatio": "1200 / 630", "width": "100%", "height": "auto"},
    mb="xl",
)

layout = dmc.Container(
    # Page-unique id: keeps React's keyed reconciliation of page swaps atomic
    # (see the wrapper comment in pages/markdown.py).
    id="m2d-page-home",
    size="lg",
    py="xl",
    children=[
        hero,
        dcc.Markdown(
            content,
            style={
                "maxWidth": "none",  # Allow Container to control width
            }
        )
    ]
)

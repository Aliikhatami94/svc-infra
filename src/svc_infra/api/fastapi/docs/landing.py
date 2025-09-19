from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional

FAVICON_DATA_URI = (
    "data:image/svg+xml,"
    "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E"
    "%3Cpath fill='%230b0f14' d='M0 0h64v64H0z'/%3E"
    "%3Cpath fill='%23e6edf3' d='M21 16c-6 4-9 8-9 16s3 12 9 16l3-4c-4-3-6-6-6-12s2-9 6-12l-3-4zm22 0-3 4c4 3 6 6 6 12s-2 9-6 12l3 4c6-4 9-8 9-16s-3-12-9-16z'/%3E"
    "%3C/svg%3E"
)

# Get the directory containing this file
_DOCS_DIR = Path(__file__).parent
_TEMPLATES_DIR = _DOCS_DIR / "templates"
_STATIC_DIR = _DOCS_DIR / "static"


@dataclass(frozen=True)
class DocTargets:
    swagger: Optional[str] = None
    redoc: Optional[str] = None
    openapi_json: Optional[str] = None


@dataclass(frozen=True)
class CardSpec:
    tag: str
    docs: DocTargets


def _load_template(template_name: str) -> str:
    """Load an HTML template from the templates directory."""
    template_path = _TEMPLATES_DIR / template_name
    try:
        return template_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise FileNotFoundError(f"Template file not found: {template_path}")


def _btn(label: str, href: str) -> str:
    return f'<a class="btn" href="{href}">{label}</a>'


def _card(spec: CardSpec) -> str:
    tag = "/" if spec.tag.strip("/") == "" else f"/{spec.tag.strip('/')}"
    links: List[str] = []
    if spec.docs.swagger:
        links.append(_btn("Swagger", spec.docs.swagger))
    if spec.docs.redoc:
        links.append(_btn("ReDoc", spec.docs.redoc))
    if spec.docs.openapi_json:
        links.append(_btn("OpenAPI JSON", spec.docs.openapi_json))
    actions = "\n".join(links) if links else "<div class='muted'>No docs exposed</div>"

    # Load and render card template
    card_template = _load_template("card.html")
    return card_template.replace("{{tag}}", tag).replace("{{actions}}", actions)


def render_index_html(
    *,
    service_name: str,
    release: str,
    cards: Iterable[CardSpec],
    css_path: str = "styles.css",
) -> str:
    """Render the index HTML page using templates."""
    grid = "\n".join(_card(c) for c in cards)

    # Load main template
    main_template = _load_template("index.html")

    # Replace template variables
    html = main_template.replace("{{service_name}}", service_name)
    html = html.replace("{{release}}", release)
    html = html.replace("{{favicon_data_uri}}", FAVICON_DATA_URI)
    html = html.replace("{{css_path}}", css_path)
    html = html.replace("{{grid}}", grid)

    return html

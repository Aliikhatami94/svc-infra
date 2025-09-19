from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional


@dataclass(frozen=True)
class DocTargets:
    swagger: Optional[str] = None  # e.g. "/docs" or "/v0/docs"
    redoc: Optional[str] = None  # e.g. "/redoc" or "/v0/redoc"
    openapi_json: Optional[str] = None  # e.g. "/openapi.json" or "/v0/openapi.json"


@dataclass(frozen=True)
class CardSpec:
    tag: str  # "/", "v0", "v1" (no leading slash required)
    docs: DocTargets  # which endpoints to show


def _btn(label: str, href: str, *, kind: str = "solid") -> str:
    # kind: "solid" | "outline"
    base = "btn"
    cls = f"{base} {'btn-outline' if kind == 'outline' else ''}"
    return f'<a class="{cls}" href="{href}">{label}</a>'


def _card(spec: CardSpec) -> str:
    tag = "/" if spec.tag.strip("/") == "" else f"/{spec.tag.strip('/')}"
    links: List[str] = []
    if spec.docs.swagger:
        links.append(_btn("Swagger", spec.docs.swagger, kind="solid"))
    if spec.docs.redoc:
        links.append(_btn("ReDoc", spec.docs.redoc, kind="outline"))
    if spec.docs.openapi_json:
        links.append(_btn("OpenAPI JSON", spec.docs.openapi_json, kind="outline"))
    actions = "\n".join(links)

    return f"""
    <div class="card">
      <div class="card__body">
        <div class="chip">{tag}</div>
        <div class="actions">{actions}</div>
      </div>
    </div>
    """.strip()


def render_index_html(
    *,
    service_name: str,
    release: str,
    cards: Iterable[CardSpec],
) -> str:
    # Build card grid (Root first, then versions in caller order)
    grid = "\n".join(_card(c) for c in cards)

    # Minimal, shadcn-ish design tokens
    return f"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>{service_name} • {release}</title>
  <style>
    :root {{
      /* dark */
      --bg: #0b0f14;
      --fg: #e6edf3;
      --muted: #9aa7b3;
      --panel: #0f141b;
      --panel-2: #0d1218;
      --border: #1f2631;
      --border-strong: #2b3546;
      --brand: #4ea1ff;
      --brand-ink: #0b0f14;

      --radius: 12px;
      --shadow: 0 1px 0 rgba(0,0,0,.2), 0 8px 24px rgba(0,0,0,.24);
    }}
    @media (prefers-color-scheme: light) {{
      :root {{
        --bg: #f7f9fc;
        --fg: #0b0f14;
        --muted: #556171;
        --panel: #ffffff;
        --panel-2: #fafbfc;
        --border: #e6ebf2;
        --border-strong: #d7dfeb;
        --brand: #2563eb;
        --brand-ink: #ffffff;
      }}
    }}

    * {{ box-sizing: border-box; }}
    html, body {{ height: 100%; }}
    body {{
      margin: 0;
      padding: 28px;
      background: var(--bg);
      color: var(--fg);
      font: 500 15px/1.5 system-ui, -apple-system, Segoe UI, Roboto, Inter, "Helvetica Neue", Arial, "Noto Sans";
    }}

    .container {{ max-width: 1100px; margin: 0 auto; }}

    .header {{
      display: flex;
      align-items: baseline;
      gap: 12px;
      margin-bottom: 18px;
    }}
    .title {{ margin: 0; font-size: 24px; letter-spacing: .2px; }}
    .sub {{ color: var(--muted); font-size: 14px; }}

    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
      gap: 14px;
    }}

    .card {{
      background: linear-gradient(180deg, var(--panel), var(--panel-2));
      border: 1px solid var(--border);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
      transition: border-color .12s ease, transform .08s ease;
    }}
    .card:hover {{ border-color: var(--border-strong); transform: translateY(-1px); }}
    .card__body {{ padding: 16px; display: grid; gap: 12px; }}

    .chip {{
      display: inline-block;
      font-size: 12.5px;
      color: var(--muted);
      background: transparent;
      border: 1px solid var(--border);
      border-radius: 999px;
      padding: 6px 10px;
    }}

    .actions {{ display: flex; gap: 10px; flex-wrap: wrap; }}

    .btn {{
      display: inline-block;
      font-weight: 600;
      text-decoration: none;
      border-radius: 10px;
      padding: 8px 12px;
      border: 1px solid var(--border);
      background: var(--panel);
      color: var(--fg);
      transition: transform .06s ease, border-color .12s ease, background .12s ease;
    }}
    .btn:hover {{ transform: translateY(-1px); border-color: var(--border-strong); }}
    .btn.btn-outline {{ background: transparent; }}

    /* “solid” look */
    .btn:not(.btn-outline) {{
      background: var(--brand);
      color: var(--brand-ink);
      border-color: transparent;
    }}
    .btn:not(.btn-outline):hover {{
      filter: brightness(1.03);
    }}

    footer {{ margin-top: 22px; color: var(--muted); font-size: 13px; }}
  </style>
</head>
<body>
  <div class="container">
    <header class="header">
      <h1 class="title">{service_name}</h1>
      <div class="sub">release {release}</div>
    </header>

    <section class="grid">
      {grid}
    </section>

    <footer>
      Tip: each card exposes Swagger, ReDoc, and OpenAPI JSON when available.
    </footer>
  </div>
</body>
</html>
    """.strip()

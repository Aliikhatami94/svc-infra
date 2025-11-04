from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional

FAVICON_DATA_URI = (
    "data:image/svg+xml,"
    "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E"
    "%3Cpath fill='%230b0f14' d='M0 0h64v64H0z'/%3E"
    "%3Cpath fill='%23e6edf3' d='M21 16c-6 4-9 8-9 16s3 12 9 16l3-4c-4-3-6-6-6-12s2-9 6-12l-3-4zm22 0-3 4c4 3 6 6 6 12s-2 9-6 12l3 4c6-4 9-8 9-16s-3-12-9-16z'/%3E"
    "%3C/svg%3E"
)


@dataclass(frozen=True)
class DocTargets:
    swagger: Optional[str] = None
    redoc: Optional[str] = None
    openapi_json: Optional[str] = None


@dataclass(frozen=True)
class CardSpec:
    tag: str
    docs: DocTargets


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

    return f"""
    <div class="card">
      <div class="card__body">
        <div class="chip">{tag}</div>
        <div class="actions">{actions}</div>
      </div>
    </div>
    """.strip()


def render_index_html(*, service_name: str, release: str, cards: Iterable[CardSpec]) -> str:
    grid = "\n".join(_card(c) for c in cards)
    return f"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>{service_name} • {release}</title>
  <link rel="icon" href="{FAVICON_DATA_URI}">
  <style>
    :root {{
      --bg:#0b0f14; --fg:#e6edf3; --muted:#9aa7b3; --panel:#0f141b; --panel-2:#0d1218;
      --border:#1f2631; --border-strong:#2b3546; --btn-bg:#121a24; --btn-fg:#d7e2ee;
      --btn-border:#223044; --btn-hover-bg:#162130; --btn-hover-border:#2a3b54; --radius:12px;
    }}
    @media (prefers-color-scheme: light) {{
      :root {{
        --bg:#f7f9fc; --fg:#0b0f14; --muted:#556171; --panel:#ffffff; --panel-2:#fafbfc;
        --border:#e6ebf2; --border-strong:#d7dfeb; --btn-bg:#f6f8fc; --btn-fg:#0b1220;
        --btn-border:#dce5f2; --btn-hover-bg:#eef3fb; --btn-hover-border:#cfdbee;
      }}
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0; padding: 28px; background: var(--bg); color: var(--fg);
      font: 500 15px/1.5 system-ui, -apple-system, Segoe UI, Inter, Roboto, Helvetica, Arial;
    }}
    .container {{ max-width: 1100px; margin: 0 auto; }}
    .header {{ display:flex; align-items:baseline; gap:12px; margin-bottom:18px; }}
    .title {{ margin:0; font-size:24px; letter-spacing:.2px; }}
    .sub {{ color:var(--muted); font-size:14px; }}
    .grid {{ display:grid; grid-template-columns:repeat(auto-fill, minmax(240px,1fr)); gap:14px; }}
    .card {{
      background: linear-gradient(180deg, var(--panel), var(--panel-2));
      border: 1px solid var(--border); border-radius: var(--radius);
      transition: border-color .12s ease, transform .08s ease;
    }}
    .card:hover {{ border-color: var(--border-strong); transform: translateY(-1px); }}
    .card__body {{ padding: 16px; display:grid; gap:12px; }}
    .chip {{
      display:inline-block; font-size:15px; font-weight:600; color:var(--fg);
      background:#1c2736; border:1px solid var(--border-strong);
      border-radius: 999px; padding:6px 14px; width:fit-content; letter-spacing:.3px;
    }}
    .actions {{ display:flex; gap:8px; flex-wrap:wrap; align-items:center; }}
    .btn {{
      display:inline-block; text-decoration:none; font-weight:500; border-radius:8px;
      padding:6px 10px; font-size:13px; border:1px solid var(--btn-border);
      background:var(--btn-bg); color:var(--btn-fg);
      transition: transform .06s ease, border-color .12s ease, background .12s ease;
    }}
    .btn:hover {{ transform: translateY(-1px); background: var(--btn-hover-bg); border-color: var(--btn-hover-border); }}
    footer {{ margin-top:22px; color:var(--muted); font-size:13px; }}
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
    <footer>Tip: each card exposes Swagger, ReDoc, and a JSON view.</footer>
  </div>
</body>
</html>
    """.strip()

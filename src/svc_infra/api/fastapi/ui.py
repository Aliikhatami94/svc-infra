# svc_infra/api/fastapi/ui.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class VersionLink:
    tag: str  # e.g. "v0"
    docs_url: str  # e.g. "/v0/docs"
    redoc_url: str | None  # e.g. "/v0/redoc" (if enabled)
    openapi_url: str | None  # e.g. "/v0/openapi.json" (if enabled)


def _card(v: VersionLink) -> str:
    tag = v.tag.strip("/")
    # We do NOT repeat the service name here — just the version tag.
    # Primary CTA is Swagger; auxiliary links are tucked under the tag.
    redoc = f'<a class="pill" href="{v.redoc_url}">ReDoc</a>' if v.redoc_url else ""
    openapi = f'<a class="pill" href="{v.openapi_url}">OpenAPI JSON</a>' if v.openapi_url else ""
    return f"""
    <div class="card">
      <div class="card-body">
        <div class="tag">/{tag}</div>
        <div class="actions">
          <a class="cta" href="{v.docs_url}" aria-label="Open Swagger docs for {tag}">Swagger</a>
          {redoc}
          {openapi}
        </div>
      </div>
    </div>
    """.strip()


def render_index_html(
    *,
    service_name: str,
    release: str,
    versions: Iterable[VersionLink],
    root_docs_url: str | None,
    root_redoc_url: str | None,
    root_openapi_url: str | None,
) -> str:
    """
    Nice landing page:
      - Hero: service name + release + root docs buttons (if enabled)
      - Grid of version cards: one card per version (no repeated service name)
    """
    # Root docs buttons (only if exposed)
    root_btns = []
    if root_docs_url:
        root_btns.append(f'<a class="cta" href="{root_docs_url}">Root Swagger</a>')
    if root_redoc_url:
        root_btns.append(f'<a class="pill" href="{root_redoc_url}">Root ReDoc</a>')
    if root_openapi_url:
        root_btns.append(f'<a class="pill" href="{root_openapi_url}">Root OpenAPI JSON</a>')
    root_buttons = " ".join(root_btns) if root_btns else ""

    cards = "\n".join(_card(v) for v in versions)

    return f"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>{service_name} • {release}</title>
  <style>
    :root {{
      --bg:#0b0f14; --fg:#dbe3ec; --muted:#93a1b3; --card:#121821; --card2:#0f141c;
      --accent:#4ea1ff; --border:#1e2633; --border2:#2b3a52;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin:0; padding:28px; background:var(--bg); color:var(--fg);
      font:500 16px/1.45 system-ui,-apple-system,Segoe UI,Roboto,"Helvetica Neue",Arial,"Noto Sans","Apple Color Emoji","Segoe UI Emoji";
    }}
    .hero {{
      display:flex; gap:18px; align-items:center; flex-wrap:wrap; margin-bottom:20px;
    }}
    h1 {{ margin:0; font-size:24px; letter-spacing:.2px; }}
    .sub {{ color:var(--muted); }}
    .hero .actions {{ display:flex; gap:10px; flex-wrap:wrap; }}
    .cta {{
      display:inline-block; padding:8px 14px; border-radius:10px; text-decoration:none; color:#0b0f14;
      background:var(--accent); font-weight:600; transition:transform .06s ease;
    }}
    .cta:hover {{ transform:translateY(-1px); }}
    .pill {{
      display:inline-block; padding:6px 10px; border-radius:999px; text-decoration:none; color:#cfe3ff;
      background:#142033; border:1px solid #20304a; font-size:13px;
    }}
    .grid {{
      display:grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap:16px;
      margin-top:14px;
    }}
    .card {{
      border:1px solid var(--border); border-radius:12px;
      background:linear-gradient(180deg, var(--card), var(--card2));
      transition: border-color .12s ease, transform .08s ease;
    }}
    .card:hover {{ border-color:var(--border2); transform: translateY(-1px); }}
    .card-body {{ padding:16px; display:flex; flex-direction:column; gap:12px; }}
    .tag {{
      display:inline-block; font-size:13px; color:#b9c6d8; background:#1a2432; border:1px solid #223145;
      padding:3px 10px; border-radius:999px;
    }}
    .actions {{ display:flex; gap:10px; flex-wrap:wrap; align-items:center; }}
    footer {{
      margin-top:28px; color:var(--muted); font-size:13px;
    }}
    @media (prefers-color-scheme: light) {{
      :root {{
        --bg:#f7f9fc; --fg:#0b0f14; --muted:#516172; --card:#ffffff; --card2:#fbfbfb;
        --border:#e1e7ef; --border2:#cfd8e4; --accent:#2563eb;
      }}
      .pill {{ color:#1b2b44; background:#eef2f9; border-color:#d9e3f2; }}
    }}
  </style>
</head>
<body>
  <header class="hero">
    <div>
      <h1>{service_name}</h1>
      <div class="sub">release {release}</div>
    </div>
    <div class="actions">{root_buttons}</div>
  </header>

  <section class="grid">
    {cards}
  </section>

  <footer>
    Tip: each version card links to Swagger; ReDoc and raw OpenAPI are available as pills.
  </footer>
</body>
</html>
    """.strip()

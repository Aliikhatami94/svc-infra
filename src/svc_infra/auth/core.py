from __future__ import annotations

from pathlib import Path
from string import Template
from typing import Dict, Any

import importlib.resources as pkg

TEMPLATES_PKG = "svc_infra.auth.templates"  # package containing .tmpl files


def _render(name: str, ctx: dict[str, str]) -> str:
    txt = pkg.files(TEMPLATES_PKG).joinpath(name).read_text(encoding="utf-8")
    return Template(txt).substitute(**ctx)


def _write(dest: Path, content: str, overwrite: bool) -> Dict[str, Any]:
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and not overwrite:
        return {"path": str(dest), "action": "skipped", "reason": "exists"}
    dest.write_text(content, encoding="utf-8")
    return {"path": str(dest), "action": "wrote"}


# ---------------- Core (tool-callable) APIs ---------------- #

def scaffold_auth_core(
        *,
        models_dir: Path,
        schemas_dir: Path,
        overwrite: bool,
) -> Dict[str, Any]:
    """Create models.py and schemas.py for auth from templates."""
    models_res = _write(Path(models_dir) / "models.py", _render("models.py.tmpl", {}), overwrite)
    schemas_res = _write(Path(schemas_dir) / "schemas.py", _render("schemas.py.tmpl", {}), overwrite)
    return {
        "status": "ok",
        "results": {
            "models": models_res,
            "schemas": schemas_res,
        },
    }


def scaffold_auth_models_core(
        *,
        dest_dir: Path,
        overwrite: bool,
) -> Dict[str, Any]:
    """Create models.py for auth from template."""
    res = _write(Path(dest_dir) / "models.py", _render("models.py.tmpl", {}), overwrite)
    return {"status": "ok", "result": res}


def scaffold_auth_schemas_core(
        *,
        dest_dir: Path,
        overwrite: bool,
) -> Dict[str, Any]:
    """Create schemas.py for auth from template."""
    res = _write(Path(dest_dir) / "schemas.py", _render("schemas.py.tmpl", {}), overwrite)
    return {"status": "ok", "result": res}
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Literal, Optional

from svc_infra.db.utils import normalize_dir, pascal, plural_snake, snake
from svc_infra.utils import ensure_init_py, render_template, write

_INIT_CONTENT_PAIRED = 'from . import documents, schemas\n\n__all__ = ["documents", "schemas"]\n'
_INIT_CONTENT_MINIMAL = "# package marker; add explicit exports here if desired\n"


def _ensure_init_py(dir_path: Path, overwrite: bool, paired: bool) -> Dict[str, Any]:
    content = _INIT_CONTENT_PAIRED if paired else _INIT_CONTENT_MINIMAL
    return ensure_init_py(dir_path, overwrite, paired, content)


# -------------- public API -------------------

Kind = Literal["entity"]


def scaffold_core(
    *,
    documents_dir: Path | str,
    schemas_dir: Path | str,
    entity_name: str = "Item",
    overwrite: bool = False,
    same_dir: bool = False,
    documents_filename: Optional[str] = None,
    schemas_filename: Optional[str] = None,
) -> Dict[str, Any]:
    """Create starter Mongo document model + CRUD schemas."""

    documents_dir = normalize_dir(documents_dir)
    schemas_dir = normalize_dir(documents_dir if same_dir else schemas_dir)

    ent = pascal(entity_name)
    coll = plural_snake(ent)

    documents_txt = render_template(
        tmpl_dir="svc_infra.db.nosql.mongo.templates",
        name="documents.py.tmpl",
        subs={"Entity": ent, "collection_name": coll},
    )
    schemas_txt = render_template(
        tmpl_dir="svc_infra.db.nosql.mongo.templates",
        name="schemas.py.tmpl",
        subs={"Entity": ent},  # (only if your schemas.tmpl doesn't need collection_name)
    )

    if same_dir:
        doc_path = documents_dir / "documents.py"
        sch_path = schemas_dir / "schemas.py"
    else:
        base = snake(entity_name)
        doc_path = documents_dir / (documents_filename or f"{base}.py")
        sch_path = schemas_dir / (schemas_filename or f"{base}.py")

    res_doc = write(doc_path, documents_txt, overwrite)
    res_sch = write(sch_path, schemas_txt, overwrite)

    init_results = []
    init_results.append(_ensure_init_py(documents_dir, overwrite, paired=same_dir))
    if schemas_dir != documents_dir:
        init_results.append(_ensure_init_py(schemas_dir, overwrite, paired=False))

    return {
        "status": "ok",
        "results": {"documents": res_doc, "schemas": res_sch, "inits": init_results},
    }


def scaffold_documents_core(
    *,
    dest_dir: Path | str,
    entity_name: str = "Item",
    overwrite: bool = False,
    documents_filename: Optional[str] = None,
) -> Dict[str, Any]:
    dest = normalize_dir(dest_dir)
    ent = pascal(entity_name)
    coll = plural_snake(ent)

    txt = render_template(
        tmpl_dir="svc_infra.db.nosql.mongo.templates",
        name="documents.py.tmpl",
        subs={"Entity": ent, "collection_name": coll},
    )
    filename = documents_filename or f"{snake(entity_name)}.py"
    res = write(dest / filename, txt, overwrite)
    _ensure_init_py(dest, overwrite, paired=False)
    return {"status": "ok", "result": res}


def scaffold_schemas_core(
    *,
    dest_dir: Path | str,
    entity_name: str = "Item",
    overwrite: bool = False,
    schemas_filename: Optional[str] = None,
) -> Dict[str, Any]:
    dest = normalize_dir(dest_dir)
    ent = pascal(entity_name)
    txt = render_template(
        tmpl_dir="svc_infra.db.nosql.mongo.templates", name="schemas.py.tmpl", subs={"Entity": ent}
    )
    filename = schemas_filename or f"{snake(entity_name)}.py"
    res = write(dest / filename, txt, overwrite)
    _ensure_init_py(dest, overwrite, paired=False)
    return {"status": "ok", "result": res}


def scaffold_resources_core(
    *,
    dest_dir: Path | str,
    entity_name: str = "Item",
    filename: Optional[str] = None,  # defaults to "resources.py"
    overwrite: bool = False,
) -> Dict[str, Any]:
    """
    Create a starter resources.py with:
      - empty RESOURCES list
      - empty index_builders() mapping
    Uses templates/scaffold/resources.py.tmpl (no hardcoded content).
    """
    # normalize
    dest = Path(dest_dir)
    if not dest.is_absolute():
        dest = (Path.cwd() / dest).resolve()
    dest.mkdir(parents=True, exist_ok=True)

    ent = pascal(entity_name)
    coll = plural_snake(ent)

    # render from file template
    txt = render_template(
        tmpl_dir="svc_infra.db.nosql.mongo.templates",
        name="resources.py.tmpl",
        subs={
            "Entity": ent,
            "collection_name": coll,
        },
    )

    # write file
    out_path = dest / (filename or "resources.py")
    res = write(out_path, txt, overwrite)

    # ensure __init__.py
    _ensure_init_py(dest, overwrite, paired=False)

    return {"status": "ok", "result": res}

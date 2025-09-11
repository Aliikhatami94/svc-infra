from __future__ import annotations

from pathlib import Path
from string import Template
from typing import Any, Dict, Literal, Optional


def _normalize_dir(p: Path | str) -> Path:
    p = Path(p)
    return p if p.is_absolute() else (Path.cwd() / p).resolve()


def _write(dest: Path, content: str, overwrite: bool) -> Dict[str, Any]:
    dest = dest.resolve()
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and not overwrite:
        return {"path": str(dest), "action": "skipped", "reason": "exists"}
    dest.write_text(content, encoding="utf-8")
    return {"path": str(dest), "action": "wrote"}


_INIT_CONTENT_PAIRED = 'from . import documents, schemas\n\n__all__ = ["documents", "schemas"]\n'
_INIT_CONTENT_MINIMAL = "# package marker; add explicit exports here if desired\n"


def _ensure_init_py(dir_path: Path, overwrite: bool, paired: bool) -> Dict[str, Any]:
    content = _INIT_CONTENT_PAIRED if paired else _INIT_CONTENT_MINIMAL
    return _write(dir_path / "__init__.py", content, overwrite)


def _snake(name: str) -> str:
    import re

    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    s2 = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1)
    return re.sub(r"[^a-zA-Z0-9_]+", "_", s2).lower().strip("_")


def _pascal(name: str) -> str:
    return "".join(p.capitalize() for p in _snake(name).split("_") if p) or "Item"


# ----------------- templates -----------------

_DOC_TPL = Template(
    """from __future__ import annotations

from datetime import datetime
from typing import Optional, Any, Dict

from pydantic import BaseModel, Field
from svc_infra.db.nosql.types import PyObjectId


class ${Entity}Doc(BaseModel):
    \"\"\"Mongo document model for the ${Entity} collection.\"\"\"
    _id: Optional[PyObjectId] = Field(default=None, alias="_id")
    name: str
    is_active: bool = True
    tenant_id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "from_attributes": True,
        "json_encoders": {PyObjectId: str},
    }
"""
)

_SCHEMA_TPL = Template(
    """from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel
from svc_infra.db.nosql.types import PyObjectId


class ${Entity}Read(BaseModel):
    _id: Optional[PyObjectId] = None
    name: Optional[str] = None
    is_active: Optional[bool] = None
    tenant_id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ${Entity}Create(BaseModel):
    name: str
    tenant_id: Optional[str] = None
    is_active: Optional[bool] = True


class ${Entity}Update(BaseModel):
    name: Optional[str] = None
    tenant_id: Optional[str] = None
    is_active: Optional[bool] = None
"""
)

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

    documents_dir = _normalize_dir(documents_dir)
    schemas_dir = _normalize_dir(documents_dir if same_dir else schemas_dir)

    ent = _pascal(entity_name)

    documents_txt = _DOC_TPL.substitute({"Entity": ent})
    schemas_txt = _SCHEMA_TPL.substitute({"Entity": ent})

    if same_dir:
        doc_path = documents_dir / "documents.py"
        sch_path = schemas_dir / "schemas.py"
    else:
        base = _snake(entity_name)
        doc_path = documents_dir / (documents_filename or f"{base}.py")
        sch_path = schemas_dir / (schemas_filename or f"{base}.py")

    res_doc = _write(doc_path, documents_txt, overwrite)
    res_sch = _write(sch_path, schemas_txt, overwrite)

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
    dest = _normalize_dir(dest_dir)
    ent = _pascal(entity_name)
    txt = _DOC_TPL.substitute({"Entity": ent})
    filename = documents_filename or f"{_snake(entity_name)}.py"
    res = _write(dest / filename, txt, overwrite)
    _ensure_init_py(dest, overwrite, paired=False)
    return {"status": "ok", "result": res}


def scaffold_schemas_core(
    *,
    dest_dir: Path | str,
    entity_name: str = "Item",
    overwrite: bool = False,
    schemas_filename: Optional[str] = None,
) -> Dict[str, Any]:
    dest = _normalize_dir(dest_dir)
    ent = _pascal(entity_name)
    txt = _SCHEMA_TPL.substitute({"Entity": ent})
    filename = schemas_filename or f"{_snake(entity_name)}.py"
    res = _write(dest / filename, txt, overwrite)
    _ensure_init_py(dest, overwrite, paired=False)
    return {"status": "ok", "result": res}

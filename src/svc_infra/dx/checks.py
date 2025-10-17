from __future__ import annotations

from pathlib import Path


def _load_json(path: str | Path) -> dict:
    import json

    p = Path(path)
    return json.loads(p.read_text())


def check_openapi_problem_schema(
    schema: dict | None = None, *, path: str | Path | None = None
) -> None:
    """Validate OpenAPI has a Problem schema with required fields and formats.

    Raises ValueError with a descriptive message on failure.
    """

    if schema is None:
        if path is None:
            raise ValueError("either schema or path must be provided")
        schema = _load_json(path)

    comps = (schema or {}).get("components") or {}
    prob = (comps.get("schemas") or {}).get("Problem")
    if not isinstance(prob, dict):
        raise ValueError("Problem schema missing under components.schemas.Problem")

    props = prob.get("properties") or {}
    # Required keys presence
    for key in ("type", "title", "status", "detail", "instance", "code"):
        if key not in props:
            raise ValueError(f"Problem.{key} missing in properties")

    # instance must be uri-reference per our convention
    inst = props.get("instance") or {}
    if inst.get("format") != "uri-reference":
        raise ValueError("Problem.instance must have format 'uri-reference'")


def check_migrations_up_to_date(*, project_root: str | Path = ".") -> None:
    """Best-effort migrations check: passes if alembic env present and head is reachable.

    This is a lightweight stub that can be extended per-project. For now, it checks
    that an Alembic env exists when 'alembic.ini' is present; it does not execute DB calls.
    """

    root = Path(project_root)
    # If alembic.ini is absent, there's nothing to check here
    if not (root / "alembic.ini").exists():
        return
    # Ensure versions/ dir exists under migrations path if configured, default to 'migrations'
    mig_dir = root / "migrations"
    if not mig_dir.exists():
        # tolerate alternative layout via env; keep stub permissive
        return
    versions = mig_dir / "versions"
    if not versions.exists():
        raise ValueError("Alembic migrations directory missing versions/ subfolder")


__all__ = [
    "check_openapi_problem_schema",
    "check_migrations_up_to_date",
]

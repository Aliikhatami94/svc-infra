from __future__ import annotations
from pathlib import Path
from typing import Optional
import typer

app = typer.Typer(help="Scaffold user-management boilerplate: models/schemas/routers.")

# --- Simple templates (minimal but useful) -----------------------------------

USER_MODEL_TEMPLATE = """\
from __future__ import annotations
import uuid
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Boolean
from svc_infra.db.base import Base, UUIDMixin, TimestampMixin, SoftDeleteMixin

class User(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "users"
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    provider: Mapped[str] = mapped_column(String(32), default="password", nullable=False)  # google, github, apple, password
    provider_id: Mapped[str | None] = mapped_column(String(128), nullable=True)           # sub/id from the IdP
    hashed_password: Mapped[str | None] = mapped_column(String(255), nullable=True)       # null for pure OAuth accounts
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
"""

USER_SCHEMAS_TEMPLATE = """\
from __future__ import annotations
import uuid
from pydantic import BaseModel, EmailStr, Field

class UserBase(BaseModel):
    email: EmailStr
    name: str | None = None

class UserCreate(UserBase):
    password: str | None = Field(default=None, min_length=8)
    provider: str = "password"
    provider_id: str | None = None

class UserRead(UserBase):
    id: uuid.UUID
    is_active: bool
    provider: str
    provider_id: str | None = None

class UserUpdate(BaseModel):
    name: str | None = None
    is_active: bool | None = None
"""

USER_ROUTER_TEMPLATE = """\
from __future__ import annotations
from fastapi import APIRouter, HTTPException, status
from typing import Sequence
from svc_infra.db.integration.fastapi import SessionDep  # provides AsyncSession via DI
from svc_infra.db.repository.base import Repository, paginate
from .schemas import UserCreate, UserRead, UserUpdate   # adjust import to your layout
from .models import User                                # adjust import to your layout

ROUTER_TAG = "users"
ROUTER_PREFIX = "/_db/users"
INCLUDE_ROUTER_IN_SCHEMA = False  # set to True to expose in OpenAPI docs
router = APIRouter()

@router.get("/", response_model=Sequence[UserRead])
async def list_users(session: SessionDep, limit: int = 50, offset: int = 0):
    repo = Repository[User](session, User)
    stmt = repo._base_select()  # includes soft-delete filtering if mixin present
    page = await paginate(session, stmt, limit=limit, offset=offset)
    return [UserRead.model_validate(x.__dict__) for x in page.items]

@router.post("/", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(payload: UserCreate, session: SessionDep):
    repo = Repository[User](session, User)
    # hashing omitted for brevity — plug your auth layer here
    obj = await repo.create(
        email=str(payload.email),
        name=payload.name,
        provider=payload.provider,
        provider_id=payload.provider_id,
        hashed_password=None if payload.password is None else payload.password,
    )
    return UserRead.model_validate(obj.__dict__)

@router.get("/{user_id}", response_model=UserRead)
async def get_user(user_id: str, session: SessionDep):
    repo = Repository[User](session, User)
    obj = await repo.get(user_id)
    if not obj:
        raise HTTPException(status_code=404, detail="User not found")
    return UserRead.model_validate(obj.__dict__)

@router.patch("/{user_id}", response_model=UserRead)
async def update_user(user_id: str, payload: UserUpdate, session: SessionDep):
    repo = Repository[User](session, User)
    obj = await repo.update(user_id, **{k: v for k, v in payload.model_dump(exclude_unset=True).items()})
    if not obj:
        raise HTTPException(status_code=404, detail="User not found")
    return UserRead.model_validate(obj.__dict__)

@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: str, session: SessionDep):
    repo = Repository[User](session, User)
    deleted = await repo.delete(user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="User not found")
    return None
"""

# --- helpers -----------------------------------------------------------------

def _ensure_pkg_init(dir_path: Path) -> None:
    """Ensure the directory is a Python package by creating __init__.py if missing."""
    dir_path.mkdir(parents=True, exist_ok=True)
    init_file = dir_path / "__init__.py"
    if not init_file.exists():
        init_file.write_text("", encoding="utf-8")
        typer.echo(f"✔ Created {init_file}")


def _write_file(path: str, content: str, overwrite: bool):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    # Ensure the target directory is a package
    _ensure_pkg_init(p.parent)
    if p.exists() and not overwrite:
        typer.echo(f"✖ File exists (use --overwrite to replace): {p}")
        raise typer.Exit(code=1)
    p.write_text(content, encoding="utf-8")
    typer.echo(f"✔ Wrote {p}")


def _guess_import_note(path: str, kind: str):
    # Quick tip to show how to include the file after writing
    if kind == "routers":
        return "Remember to include the router in your FastAPI app: `app.include_router(router)`."
    return None

# --- subcommands: each independent ------------------------------------------

@app.command("models")
def scaffold_models(
        path: str = typer.Option(..., "--path", help="Where to write the User model file."),
        overwrite: bool = typer.Option(False, "--overwrite", help="Overwrite if file exists"),
):
    _write_file(path, USER_MODEL_TEMPLATE, overwrite)
    note = _guess_import_note(path, "models")
    if note:
        typer.echo(note)


@app.command("schemas")
def scaffold_schemas(
        path: str = typer.Option(..., "--path", help="Where to write the Pydantic schemas."),
        overwrite: bool = typer.Option(False, "--overwrite", help="Overwrite if file exists"),
):
    _write_file(path, USER_SCHEMAS_TEMPLATE, overwrite)
    note = _guess_import_note(path, "schemas")
    if note:
        typer.echo(note)


@app.command("routers")
def scaffold_routers(
        path: str = typer.Option(..., "--path", help="Where to write the FastAPI router."),
        overwrite: bool = typer.Option(False, "--overwrite", help="Overwrite if file exists"),
):
    _write_file(path, USER_ROUTER_TEMPLATE, overwrite)
    note = _guess_import_note(path, "routers")
    if note:
        typer.echo(note)

# --- umbrella command: any subset -------------------------------------------

@app.command("combo")
def scaffold_any(
        models_path: Optional[str] = typer.Option(None, "--models-path", help="Output path for models.py"),
        schemas_path: Optional[str] = typer.Option(None, "--schemas-path", help="Output path for schemas.py"),
        routers_path: Optional[str] = typer.Option(None, "--routers-path", help="Output path for routers.py"),
        overwrite: bool = typer.Option(False, "--overwrite", help="Overwrite if a target file exists"),
):
    if not any([models_path, schemas_path, routers_path]):
        typer.echo("Nothing to do. Provide at least one of --models-path / --schemas-path / --routers-path.")
        raise typer.Exit(code=1)
    if models_path:
        _write_file(models_path, USER_MODEL_TEMPLATE, overwrite)
    if schemas_path:
        _write_file(schemas_path, USER_SCHEMAS_TEMPLATE, overwrite)
    if routers_path:
        _write_file(routers_path, USER_ROUTER_TEMPLATE, overwrite)


def run():
    app()


if __name__ == "__main__":
    run()
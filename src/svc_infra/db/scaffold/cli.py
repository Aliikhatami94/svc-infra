from __future__ import annotations

from pathlib import Path
import typer

app = typer.Typer(no_args_is_help=True, add_completion=False)

def _write(path: Path, content: str, *, overwrite: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not overwrite:
        typer.echo(f"SKIP {path} (exists). Use --overwrite to replace.")
        return
    path.write_text(content.strip() + "\n", encoding="utf-8")
    typer.echo(f"WRITE {path}")

def _slug(name: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in name).lower()

# -------- templates (minimal but solid) --------

MODEL_USER = """\
from __future__ import annotations
import uuid
import datetime as dt
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, DateTime, Boolean, ForeignKey, UniqueConstraint
from svc_infra.db.base import Base, UUIDMixin, TimestampMixin, SoftDeleteMixin

class User(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "users"
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str | None] = mapped_column(String(255), nullable=True)  # nullable for oauth-only
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    oauth_accounts: Mapped[list["OAuthAccount"]] = relationship(back_populates="user", cascade="all, delete-orphan")

class OAuthAccount(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "oauth_accounts"
    provider: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    provider_account_id: Mapped[str] = mapped_column(String(255), nullable=False)
    access_token: Mapped[str | None] = mapped_column(String(4096))
    refresh_token: Mapped[str | None] = mapped_column(String(4096))
    expires_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    user: Mapped["User"] = relationship(back_populates="oauth_accounts")
    __table_args__ = (UniqueConstraint("provider", "provider_account_id", name="uq_provider_account"),)
"""

SCHEMAS_USER = """\
from __future__ import annotations
import uuid
import datetime as dt
from pydantic import BaseModel, EmailStr, Field

class UserCreate(BaseModel):
    email: EmailStr
    password: str | None = None  # optional for oauth-only

class UserRead(BaseModel):
    id: uuid.UUID
    email: EmailStr
    is_active: bool
    class Config:
        from_attributes = True

class UserUpdate(BaseModel):
    email: EmailStr | None = None
    password: str | None = None
    is_active: bool | None = None

class OAuthAccountRead(BaseModel):
    id: uuid.UUID
    provider: str
    provider_account_id: str
    expires_at: dt.datetime | None = None
    class Config:
        from_attributes = True
"""

ROUTER_USER = """\
from __future__ import annotations
import uuid
from typing import Annotated, Sequence
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from svc_infra.db.integration.fastapi import SessionDep, UoWDep
from svc_infra.db.repository.base import Repository
from .schemas import UserCreate, UserRead, UserUpdate
from .models import User, OAuthAccount

router = APIRouter(prefix="/users", tags=["users"])

# NOTE: replace with your real hashing/JWT
def _hash(pw: str) -> str: return "hashed:" + pw

@router.post("", response_model=UserRead, status_code=201)
async def create_user(payload: UserCreate, uow: UoWDep):
    repo = uow.repo(User)
    # very basic uniqueness check
    existing = await repo.list(where={"email": str(payload.email)}, limit=1)
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")
    data = {"email": str(payload.email), "hashed_password": _hash(payload.password) if payload.password else None}
    user = await repo.create(**data)
    return user

@router.get("", response_model=list[UserRead])
async def list_users(limit: int = 50, offset: int = 0, uow: UoWDep = Depends()):
    repo = uow.repo(User)
    return await repo.list(limit=limit, offset=offset)

@router.get("/{user_id}", response_model=UserRead)
async def get_user(user_id: uuid.UUID, uow: UoWDep = Depends()):
    repo = uow.repo(User)
    user = await repo.get(user_id)
    if not user:
        raise HTTPException(status_code=404)
    return user

@router.patch("/{user_id}", response_model=UserRead)
async def update_user(user_id: uuid.UUID, payload: UserUpdate, uow: UoWDep = Depends()):
    repo = uow.repo(User)
    data = payload.model_dump(exclude_unset=True)
    if "password" in data:
        data["hashed_password"] = _hash(data.pop("password")) if data["hashed_password"] is not None else None
    user = await repo.update(user_id, **data)
    if not user:
        raise HTTPException(status_code=404)
    return user

@router.delete("/{user_id}", status_code=204)
async def delete_user(user_id: uuid.UUID, uow: UoWDep = Depends()):
    repo = uow.repo(User)
    deleted = await repo.delete(user_id)
    if deleted == 0:
        raise HTTPException(status_code=404)
    return

# --- OAuth (skeleton) ---
@router.post("/oauth/{provider}/start", status_code=202)
async def oauth_start(provider: str):
    # return redirect URL for provider (plug your OAuth lib here)
    return {"provider": provider, "message": "Implement start: return provider auth URL"}

@router.get("/oauth/{provider}/callback", response_model=UserRead)
async def oauth_callback(provider: str, code: str, uow: UoWDep = Depends()):
    # exchange code, fetch profile -> provider_account_id, email
    # create or link user + OAuthAccount; this is a stub
    repo = uow.repo(User)
    users = await repo.list(where={"email": "stub@example.com"}, limit=1)
    user = users[0] if users else await repo.create(email="stub@example.com", hashed_password=None, is_active=True)
    return user
"""

README_SNIPPET = """\
Scaffolded auth boilerplate:
- SQLAlchemy models: User, OAuthAccount
- Pydantic schemas: UserCreate, UserRead, UserUpdate, OAuthAccountRead
- FastAPI router with CRUD + OAuth stubs
Wire it up:
    from svc_infra.db.integration.fastapi import attach_db
    from myapp.api.users.router import router as users_router
    app = FastAPI()
    attach_db(app)
    app.include_router(users_router)
"""

# -------- command: scaffold auth --------

@app.command("scaffold-auth")
def scaffold_auth(
        models_path: str = typer.Option(..., help="Where to put SQLAlchemy models file"),
        schemas_path: str = typer.Option(..., help="Where to put Pydantic schemas file"),
        routers_path: str = typer.Option(..., help="Where to put FastAPI router file"),
        package_name: str = typer.Option("users", help="logical package name (used only in router import lines you may tweak)"),
        overwrite: bool = typer.Option(False, help="Overwrite files if present"),
):
    models_file = Path(models_path)
    schemas_file = Path(schemas_path)
    routers_file = Path(routers_path)

    # write files
    _write(models_file, MODEL_USER, overwrite=overwrite)
    _write(schemas_file, SCHEMAS_USER, overwrite=overwrite)

    # router needs relative imports that match user’s layout.
    # We keep them local ('.models', '.schemas') and rely on user placing them under same pkg.
    # If they’re separate dirs, they can adjust the import lines quickly.
    # To help, we emit the file as-is, and add a short README tip.
    _write(routers_file, ROUTER_USER, overwrite=overwrite)

    # readme next to router for quick wiring reminder
    _write(routers_file.parent / "README_AUTH_SCAFFOLD.txt", README_SNIPPET, overwrite=overwrite)

    typer.echo("Done. Review import lines if models/schemas live in different packages.")

def run():
    app()

if __name__ == "__main__":
    run()
from sqlalchemy.orm import DeclarativeBase


class ModelBase(DeclarativeBase):
    """Primary declarative base for models that should be discovered/migrated."""

    pass


class _DeprecatedModelBase(DeclarativeBase):
    """Optional base for models you want to keep in code but exclude from migrations."""

    pass

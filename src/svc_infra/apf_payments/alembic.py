from __future__ import annotations


def discover_packages() -> list[str]:
    """
    Packages Alembic should import so our models are registered with ModelBase.
    Keep this stable so apps can reference it.
    """
    return [
        "svc_infra.apf_payments.models",  # SQLAlchemy models
    ]

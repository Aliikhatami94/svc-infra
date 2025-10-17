from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from svc_infra.data.add import add_data_lifecycle


def test_add_data_lifecycle_invokes_fixture_loader(monkeypatch):
    app = FastAPI()
    called = {"fixtures": 0}

    # Avoid executing real migrations in unit test; stub out cmd_setup_and_migrate
    import svc_infra.data.add as data_add

    def fake_setup_and_migrate(**kwargs):  # noqa: D401, ANN001
        return None

    monkeypatch.setattr(data_add, "cmd_setup_and_migrate", fake_setup_and_migrate)

    def _fixtures():  # noqa: D401, ANN201
        called["fixtures"] += 1

    add_data_lifecycle(app, auto_migrate=True, on_load_fixtures=_fixtures)

    with TestClient(app):
        pass

    assert called["fixtures"] == 1

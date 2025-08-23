from fastapi.routing import APIRoute

from svc_infra.api.fastapi import _build_child_api


def test_db_health_route_is_registered():
    app = _build_child_api(app_config=None, api_config=None)
    paths = {r.path for r in app.routes if isinstance(r, APIRoute)}
    assert "/_db/health" in paths


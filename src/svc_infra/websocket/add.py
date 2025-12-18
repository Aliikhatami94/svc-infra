"""
FastAPI integration for WebSocket infrastructure.

Provides:
- add_websocket_manager: Add a connection manager to a FastAPI app
- get_ws_manager: Dependency to retrieve the manager

Example:
    from fastapi import FastAPI, WebSocket, Depends
    from svc_infra.websocket import add_websocket_manager, get_ws_manager, ConnectionManager

    app = FastAPI()
    add_websocket_manager(app)

    @app.websocket("/ws/{user_id}")
    async def ws_endpoint(websocket: WebSocket, user_id: str):
        manager = get_ws_manager(app)
        await manager.connect(user_id, websocket)
        try:
            async for msg in websocket.iter_json():
                await manager.broadcast(msg)
        finally:
            await manager.disconnect(user_id, websocket)

    @app.get("/ws/stats")
    async def ws_stats(manager: ConnectionManager = Depends(get_ws_manager)):
        return {"connections": manager.connection_count}
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from .manager import ConnectionManager

if TYPE_CHECKING:
    from fastapi import FastAPI, Request

_WS_MANAGER_ATTR = "_svc_infra_ws_manager"


def add_websocket_manager(
    app: FastAPI,
    manager: ConnectionManager | None = None,
) -> ConnectionManager:
    """
    Add a WebSocket connection manager to a FastAPI app.

    The manager is stored on app.state and can be retrieved via get_ws_manager().

    Args:
        app: FastAPI application instance
        manager: Optional pre-configured ConnectionManager.
                If not provided, a new one is created.

    Returns:
        The ConnectionManager instance (created or provided)

    Example:
        app = FastAPI()
        manager = add_websocket_manager(app)

        @app.websocket("/ws/{user_id}")
        async def ws_endpoint(websocket: WebSocket, user_id: str):
            await manager.connect(user_id, websocket)
            try:
                async for msg in websocket.iter_json():
                    await manager.broadcast(msg)
            finally:
                await manager.disconnect(user_id, websocket)
    """
    if manager is None:
        manager = ConnectionManager()

    setattr(app.state, _WS_MANAGER_ATTR, manager)
    return manager


def get_ws_manager(app_or_request: FastAPI | Request) -> ConnectionManager:
    """
    Get the WebSocket manager from a FastAPI app or request.

    Can be used as a FastAPI dependency or called directly.

    Args:
        app_or_request: Either a FastAPI app instance or a Request object

    Returns:
        The ConnectionManager instance

    Raises:
        RuntimeError: If no manager has been added to the app

    Example (as dependency):
        @app.get("/ws/stats")
        async def ws_stats(manager: ConnectionManager = Depends(get_ws_manager)):
            return {
                "connections": manager.connection_count,
                "users": manager.active_users,
            }

    Example (direct call):
        @app.websocket("/ws/{user_id}")
        async def ws_endpoint(websocket: WebSocket, user_id: str):
            manager = get_ws_manager(websocket.app)
            await manager.connect(user_id, websocket)
    """
    # Handle both FastAPI app and Request objects
    if hasattr(app_or_request, "app"):
        # It's a Request object
        app = app_or_request.app
    else:
        # It's a FastAPI app
        app = app_or_request

    manager = getattr(app.state, _WS_MANAGER_ATTR, None)
    if manager is None:
        raise RuntimeError(
            "WebSocket manager not found. Did you forget to call add_websocket_manager(app)?"
        )
    return cast("ConnectionManager", manager)


def get_ws_manager_dependency(request: Request) -> ConnectionManager:
    """
    FastAPI dependency to get the WebSocket manager.

    This is an alternative to get_ws_manager that works directly as a Depends().

    Example:
        from fastapi import Depends

        @app.get("/ws/stats")
        async def ws_stats(
            manager: ConnectionManager = Depends(get_ws_manager_dependency)
        ):
            return {"connections": manager.connection_count}
    """
    return get_ws_manager(request)

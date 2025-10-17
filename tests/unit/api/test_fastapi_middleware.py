"""
Tests for FastAPI middleware functionality.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from httpx import ASGITransport, AsyncClient

from svc_infra.api.fastapi.middleware.errors.catchall import CatchAllExceptionMiddleware
from svc_infra.api.fastapi.middleware.idempotency import IdempotencyMiddleware
from svc_infra.api.fastapi.middleware.optimistic_lock import check_version_or_409, require_if_match


class TestCatchAllExceptionMiddleware:
    """Test CatchAllExceptionMiddleware functionality."""

    @pytest.mark.asyncio
    async def test_middleware_handles_exception(self):
        """Test middleware handles exceptions properly."""
        app = FastAPI()

        @app.get("/test")
        async def test_endpoint():
            raise ValueError("Test exception")

        app.add_middleware(CatchAllExceptionMiddleware)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get("/test")

            # Verify exception was handled with 500 status
            assert response.status_code == 500
            assert "Internal Server Error" in response.text

    @pytest.mark.asyncio
    async def test_middleware_passes_through_normal_requests(self):
        """Test middleware passes through normal requests."""
        app = FastAPI()

        @app.get("/test")
        async def test_endpoint():
            return {"message": "success"}

        app.add_middleware(CatchAllExceptionMiddleware)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get("/test")

            # Verify normal request passes through
            assert response.status_code == 200
            assert response.json() == {"message": "success"}

    @pytest.mark.asyncio
    async def test_middleware_handles_different_exception_types(self):
        """Test middleware handles different exception types."""
        app = FastAPI()

        @app.get("/test")
        async def test_endpoint():
            raise RuntimeError("Runtime error")

        app.add_middleware(CatchAllExceptionMiddleware)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get("/test")

            # Verify exception was handled with 500 status
            assert response.status_code == 500
            assert "Internal Server Error" in response.text


@pytest.mark.concurrency
class TestIdempotencyMiddleware:
    """Test IdempotencyMiddleware functionality."""

    @pytest.mark.asyncio
    async def test_middleware_handles_idempotency_key(self):
        """Test middleware handles idempotency key."""
        app = FastAPI()

        @app.post("/test")
        async def test_endpoint():
            return {"message": "success"}

        app.add_middleware(IdempotencyMiddleware)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.post(
                "/test", json={"data": "test"}, headers={"Idempotency-Key": "test-key-123"}
            )

            # Verify request is processed normally
            assert response.status_code == 200
            assert response.json() == {"message": "success"}

    @pytest.mark.asyncio
    async def test_middleware_ignores_get_requests(self):
        """Test middleware ignores GET requests."""
        app = FastAPI()

        @app.get("/test")
        async def test_endpoint():
            return {"message": "success"}

        app.add_middleware(IdempotencyMiddleware)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get("/test")

            # Verify GET request is processed normally
            assert response.status_code == 200
            assert response.json() == {"message": "success"}

    @pytest.mark.asyncio
    async def test_middleware_handles_duplicate_requests(self):
        """Test middleware handles duplicate requests."""
        app = FastAPI()

        @app.post("/test")
        async def test_endpoint():
            return {"message": "success", "timestamp": "2023-01-01T00:00:00Z"}

        app.add_middleware(IdempotencyMiddleware)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            # First request
            response1 = await client.post(
                "/test", json={"data": "test"}, headers={"Idempotency-Key": "duplicate-key-123"}
            )

            # Second request with same idempotency key
            response2 = await client.post(
                "/test", json={"data": "test"}, headers={"Idempotency-Key": "duplicate-key-123"}
            )

            # Both should return the same response
            assert response1.status_code == 200
            assert response2.status_code == 200
            assert response1.json() == response2.json()

    @pytest.mark.asyncio
    async def test_middleware_conflict_on_mismatched_payload(self):
        """Re-using same Idempotency-Key with different body should 409."""
        app = FastAPI()

        @app.post("/test")
        async def test_endpoint():
            return {"message": "ok"}

        app.add_middleware(IdempotencyMiddleware)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            # First request
            r1 = await client.post(
                "/test",
                json={"a": 1},
                headers={"Idempotency-Key": "same-key"},
            )
            assert r1.status_code == 200
            # Second request same key, different body
            r2 = await client.post(
                "/test",
                json={"a": 2},
                headers={"Idempotency-Key": "same-key"},
            )
            assert r2.status_code == 409


@pytest.mark.concurrency
class TestOptimisticLocking:
    @pytest.mark.asyncio
    async def test_missing_if_match(self):
        app = FastAPI()

        @app.patch("/resource")
        async def update(_: str = Depends(require_if_match)):
            return {"ok": True}

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            res = await client.patch("/resource", json={})
            assert res.status_code == 428

    @pytest.mark.asyncio
    async def test_bad_if_match_format(self):
        # current version is int=3
        def _cur():
            return 3

        with pytest.raises(HTTPException) as ctx:
            check_version_or_409(_cur, "abc")
        assert ctx.value.status_code == 400

    @pytest.mark.asyncio
    async def test_version_mismatch_conflict(self):
        def _cur():
            return 5

        with pytest.raises(HTTPException) as ctx:
            check_version_or_409(_cur, "4")
        assert ctx.value.status_code == 409

    @pytest.mark.asyncio
    async def test_version_match_success(self):
        def _cur():
            return 7

        # should not raise
        check_version_or_409(_cur, "7")

    @pytest.mark.asyncio
    async def test_middleware_without_idempotency_key(self):
        """Test middleware without idempotency key."""
        app = FastAPI()

        @app.post("/test")
        async def test_endpoint():
            return {"message": "success"}

        app.add_middleware(IdempotencyMiddleware)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.post("/test", json={"data": "test"})

            # Verify request is processed normally without idempotency key
            assert response.status_code == 200
            assert response.json() == {"message": "success"}


class TestCORSMiddleware:
    """Test CORS middleware functionality."""

    @pytest.mark.asyncio
    async def test_cors_preflight_request(self):
        """Test CORS preflight request handling."""
        from fastapi.middleware.cors import CORSMiddleware

        app = FastAPI()

        @app.get("/test")
        async def test_endpoint():
            return {"message": "success"}

        app.add_middleware(
            CORSMiddleware,
            allow_origins=["http://localhost:3000"],
            allow_methods=["GET", "POST"],
            allow_headers=["*"],
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.options(
                "/test",
                headers={
                    "Origin": "http://localhost:3000",
                    "Access-Control-Request-Method": "GET",
                    "Access-Control-Request-Headers": "Content-Type",
                },
            )

            # Verify CORS preflight response
            assert response.status_code == 200
            assert "access-control-allow-origin" in response.headers

    @pytest.mark.asyncio
    async def test_cors_actual_request(self):
        """Test CORS actual request handling."""
        from fastapi.middleware.cors import CORSMiddleware

        app = FastAPI()

        @app.get("/test")
        async def test_endpoint():
            return {"message": "success"}

        app.add_middleware(
            CORSMiddleware,
            allow_origins=["http://localhost:3000"],
            allow_methods=["GET", "POST"],
            allow_headers=["*"],
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get("/test", headers={"Origin": "http://localhost:3000"})

            # Verify CORS headers are present
            assert response.status_code == 200
            assert "access-control-allow-origin" in response.headers
            assert response.json() == {"message": "success"}

    @pytest.mark.asyncio
    async def test_cors_unauthorized_origin(self):
        """Test CORS with unauthorized origin."""
        from fastapi.middleware.cors import CORSMiddleware

        app = FastAPI()

        @app.get("/test")
        async def test_endpoint():
            return {"message": "success"}

        app.add_middleware(
            CORSMiddleware,
            allow_origins=["http://localhost:3000"],
            allow_methods=["GET", "POST"],
            allow_headers=["*"],
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get("/test", headers={"Origin": "http://unauthorized.com"})

            # Verify request is processed but CORS headers may be restricted
            assert response.status_code == 200
            assert response.json() == {"message": "success"}


class TestSecurityMiddleware:
    """Test security middleware functionality."""

    @pytest.mark.asyncio
    async def test_trusted_host_middleware_allowed_host(self):
        """Test trusted host middleware with allowed host."""
        from fastapi.middleware.trustedhost import TrustedHostMiddleware

        app = FastAPI()

        @app.get("/test")
        async def test_endpoint():
            return {"message": "success"}

        app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1"])

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get("/test", headers={"Host": "localhost"})

            # Verify request is processed normally
            assert response.status_code == 200
            assert response.json() == {"message": "success"}

    @pytest.mark.asyncio
    async def test_trusted_host_middleware_disallowed_host(self):
        """Test trusted host middleware with disallowed host."""
        from fastapi.middleware.trustedhost import TrustedHostMiddleware

        app = FastAPI()

        @app.get("/test")
        async def test_endpoint():
            return {"message": "success"}

        app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1"])

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get("/test", headers={"Host": "evil.com"})

            # Verify request is rejected
            assert response.status_code == 400


class TestCustomMiddleware:
    """Test custom middleware functionality."""

    @pytest.mark.asyncio
    async def test_custom_middleware_applies_header(self):
        """Test custom middleware applies header."""
        from starlette.middleware.base import BaseHTTPMiddleware

        class CustomHeaderMiddleware(BaseHTTPMiddleware):
            async def dispatch(self, request, call_next):
                response = await call_next(request)
                response.headers["X-Custom-Header"] = "test-value"
                return response

        app = FastAPI()

        @app.get("/test")
        async def test_endpoint():
            return {"message": "success"}

        app.add_middleware(CustomHeaderMiddleware)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get("/test")

            # Verify custom header is applied
            assert response.status_code == 200
            assert response.headers["x-custom-header"] == "test-value"
            assert response.json() == {"message": "success"}

    @pytest.mark.asyncio
    async def test_multiple_custom_middlewares(self):
        """Test multiple custom middlewares."""
        from starlette.middleware.base import BaseHTTPMiddleware

        class HeaderMiddleware1(BaseHTTPMiddleware):
            async def dispatch(self, request, call_next):
                response = await call_next(request)
                response.headers["X-Header-1"] = "value-1"
                return response

        class HeaderMiddleware2(BaseHTTPMiddleware):
            async def dispatch(self, request, call_next):
                response = await call_next(request)
                response.headers["X-Header-2"] = "value-2"
                return response

        app = FastAPI()

        @app.get("/test")
        async def test_endpoint():
            return {"message": "success"}

        app.add_middleware(HeaderMiddleware1)
        app.add_middleware(HeaderMiddleware2)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get("/test")

            # Verify both headers are applied
            assert response.status_code == 200
            assert response.headers["x-header-1"] == "value-1"
            assert response.headers["x-header-2"] == "value-2"
            assert response.json() == {"message": "success"}


class TestMiddlewareOrder:
    """Test middleware execution order."""

    @pytest.mark.asyncio
    async def test_middleware_execution_order(self):
        """Test middleware execution order."""
        from starlette.middleware.base import BaseHTTPMiddleware

        execution_order = []

        class OrderMiddleware1(BaseHTTPMiddleware):
            async def dispatch(self, request, call_next):
                execution_order.append("middleware-1-before")
                response = await call_next(request)
                execution_order.append("middleware-1-after")
                return response

        class OrderMiddleware2(BaseHTTPMiddleware):
            async def dispatch(self, request, call_next):
                execution_order.append("middleware-2-before")
                response = await call_next(request)
                execution_order.append("middleware-2-after")
                return response

        app = FastAPI()

        @app.get("/test")
        async def test_endpoint():
            execution_order.append("endpoint")
            return {"message": "success"}

        app.add_middleware(OrderMiddleware1)
        app.add_middleware(OrderMiddleware2)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get("/test")

            # Verify execution order (middleware is executed in reverse order of addition)
            assert response.status_code == 200
            assert execution_order == [
                "middleware-2-before",
                "middleware-1-before",
                "endpoint",
                "middleware-1-after",
                "middleware-2-after",
            ]

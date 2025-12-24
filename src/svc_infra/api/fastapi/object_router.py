"""Object Router — Convert any Python object's methods to FastAPI endpoints.

This module provides a generic utility to automatically generate FastAPI router
endpoints from any Python object's methods. It handles:

- Method discovery and filtering
- HTTP verb inference from method names
- URL path generation
- Request/response model generation
- Exception mapping to HTTP status codes
- Authentication via svc-infra dual routers

Example:
    >>> from fastapi import FastAPI
    >>> from svc_infra.api.fastapi import router_from_object
    >>>
    >>> class Calculator:
    ...     def add(self, a: float, b: float) -> float:
    ...         '''Add two numbers together.'''
    ...         return a + b
    ...
    ...     def get_history(self) -> list[str]:
    ...         '''Get calculation history.'''
    ...         return ["1 + 2 = 3"]
    >>>
    >>> app = FastAPI()
    >>> router = router_from_object(Calculator(), prefix="/calc")
    >>> app.include_router(router)
    >>>
    >>> # POST /calc/add     -> {"a": 1, "b": 2} -> 3.0
    >>> # GET  /calc/history -> [] -> ["1 + 2 = 3"]

    For authentication-required endpoints:
    >>> router = router_from_object(MyService(), prefix="/api", auth_required=True)

    For custom HTTP verbs:
    >>> router = router_from_object(service, methods={"process": "GET"})

Note:
    This module uses svc-infra dual routers (not generic APIRouter) following
    the mandatory integration standards from svc-infra AGENTS.md.

    We intentionally do NOT use `from __future__ import annotations` here
    because FastAPI needs actual type objects (not string annotations) for
    Pydantic model parameter resolution in endpoint handlers.
"""

import functools
import inspect
import logging
import re
from collections.abc import Callable
from typing import Any, TypeVar, get_type_hints

from pydantic import BaseModel, create_model

logger = logging.getLogger(__name__)


__all__ = [
    # Main functions
    "router_from_object",
    "router_from_object_with_websocket",
    # Decorators
    "endpoint",
    "endpoint_exclude",
    "websocket_endpoint",
    # Exception handling
    "map_exception_to_http",
    "DEFAULT_EXCEPTION_MAP",
    "STATUS_TITLES",
]


# Marker for endpoint exclusion
_ENDPOINT_EXCLUDE_ATTR = "_svc_infra_endpoint_exclude"
_ENDPOINT_CONFIG_ATTR = "_svc_infra_endpoint_config"


F = TypeVar("F", bound=Callable[..., Any])


# =============================================================================
# Decorators
# =============================================================================


def endpoint(
    *,
    method: str | None = None,
    path: str | None = None,
    summary: str | None = None,
    description: str | None = None,
    response_model: type | None = None,
    status_code: int | None = None,
) -> Callable[[F], F]:
    """Mark a method with custom endpoint configuration.

    Use this decorator to override the automatic inference for HTTP verb,
    path, summary, or response model.

    Args:
        method: HTTP verb ("GET", "POST", "PUT", "PATCH", "DELETE").
        path: Custom URL path (overrides auto-generation).
        summary: OpenAPI summary (overrides docstring first line).
        description: OpenAPI description (overrides docstring).
        response_model: Override response model.
        status_code: Override success status code.

    Returns:
        Decorator function.

    Example:
        >>> class Service:
        ...     @endpoint(method="GET", path="/custom", summary="Custom action")
        ...     def my_action(self, value: int) -> str:
        ...         return f"value: {value}"
    """

    def decorator(func: F) -> F:
        config = {
            "method": method,
            "path": path,
            "summary": summary,
            "description": description,
            "response_model": response_model,
            "status_code": status_code,
        }
        # Remove None values
        config = {k: v for k, v in config.items() if v is not None}
        setattr(func, _ENDPOINT_CONFIG_ATTR, config)
        return func

    return decorator


def endpoint_exclude(func: F) -> F:
    """Mark a method to be excluded from router generation.

    Use this decorator to explicitly exclude a method that would otherwise
    be included in the generated router.

    Args:
        func: The method to exclude.

    Returns:
        The method unchanged, but marked for exclusion.

    Example:
        >>> class Service:
        ...     @endpoint_exclude
        ...     def internal_helper(self) -> str:
        ...         return "internal"
    """
    setattr(func, _ENDPOINT_EXCLUDE_ATTR, True)
    return func


# Marker for WebSocket endpoints
_WEBSOCKET_ENDPOINT_ATTR = "_svc_infra_websocket_endpoint"


def websocket_endpoint(
    *,
    path: str | None = None,
) -> Callable[[F], F]:
    """Mark a method as a WebSocket endpoint.

    Use this decorator to indicate a method should be exposed as a WebSocket
    endpoint instead of a regular HTTP endpoint. The method should be an
    async generator or return an async iterator.

    Args:
        path: Custom URL path (overrides auto-generation).

    Returns:
        Decorator function.

    Example:
        >>> class Service:
        ...     @websocket_endpoint(path="/stream")
        ...     async def stream_data(self, interval: float = 1.0):
        ...         while True:
        ...             yield {"timestamp": time.time()}
        ...             await asyncio.sleep(interval)
    """

    def decorator(func: F) -> F:
        config = {"path": path}
        config = {k: v for k, v in config.items() if v is not None}
        setattr(func, _WEBSOCKET_ENDPOINT_ATTR, config)
        return func

    return decorator


# =============================================================================
# HTTP Verb Inference
# =============================================================================

# Prefix patterns for HTTP verb inference
_VERB_PATTERNS: list[tuple[list[str], str]] = [
    (["get_", "list_", "read_", "fetch_", "find_", "search_"], "GET"),
    (["create_", "add_", "insert_", "new_"], "POST"),
    (["update_", "modify_", "edit_", "set_"], "PUT"),
    (["patch_"], "PATCH"),
    (["delete_", "remove_", "destroy_", "drop_"], "DELETE"),
]


def _infer_http_verb(method_name: str) -> str:
    """Infer HTTP verb from method name prefix.

    Args:
        method_name: The method name to analyze.

    Returns:
        HTTP verb string ("GET", "POST", "PUT", "PATCH", "DELETE").
        Defaults to "POST" if no pattern matches.
    """
    lower_name = method_name.lower()
    for prefixes, verb in _VERB_PATTERNS:
        if any(lower_name.startswith(p) for p in prefixes):
            return verb
    return "POST"  # Default for actions


def _strip_verb_prefix(method_name: str) -> str:
    """Remove HTTP verb prefix from method name.

    Args:
        method_name: The method name to strip.

    Returns:
        Method name without verb prefix.
    """
    lower_name = method_name.lower()
    for prefixes, _ in _VERB_PATTERNS:
        for prefix in prefixes:
            if lower_name.startswith(prefix):
                return method_name[len(prefix) :]
    return method_name


# =============================================================================
# Path Generation
# =============================================================================


def _to_kebab_case(name: str) -> str:
    """Convert snake_case or camelCase to kebab-case.

    Args:
        name: The name to convert.

    Returns:
        Name in kebab-case.

    Examples:
        >>> _to_kebab_case("process_payment")
        'process-payment'
        >>> _to_kebab_case("processPayment")
        'process-payment'
        >>> _to_kebab_case("HTTPClient")
        'http-client'
    """
    # Handle camelCase and PascalCase
    name = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1-\2", name)
    name = re.sub(r"([a-z\d])([A-Z])", r"\1-\2", name)
    # Handle snake_case
    name = name.replace("_", "-")
    return name.lower()


def _generate_path(method_name: str) -> str:
    """Generate URL path from method name.

    Args:
        method_name: The method name to convert.

    Returns:
        URL path string (without leading slash).

    Examples:
        >>> _generate_path("get_user")
        'user'
        >>> _generate_path("create_order")
        'order'
        >>> _generate_path("process_payment")
        'process-payment'
    """
    stripped = _strip_verb_prefix(method_name)
    if not stripped:
        stripped = method_name
    return _to_kebab_case(stripped)


def _generate_path_with_params(
    method_name: str,
    method: Callable,
    path_params: list[str] | None = None,
) -> tuple[str, list[str]]:
    """Generate URL path with path parameters from method signature.

    Detects path parameters from method arguments. Arguments ending with
    '_id' or named 'id' are treated as path parameters.

    Args:
        method_name: The method name to convert.
        method: The method to inspect for parameters.
        path_params: Explicit list of parameter names to include in path.

    Returns:
        Tuple of (path_string, list_of_path_param_names).

    Examples:
        >>> def get_user(self, user_id: str) -> User: ...
        >>> _generate_path_with_params("get_user", get_user)
        ('user/{user_id}', ['user_id'])

        >>> def get_order_item(self, order_id: str, item_id: str) -> Item: ...
        >>> _generate_path_with_params("get_order_item", get_order_item)
        ('order-item/{order_id}/{item_id}', ['order_id', 'item_id'])
    """
    base_path = _generate_path(method_name)

    # Get method parameters
    try:
        sig = inspect.signature(method)
    except (ValueError, TypeError):
        return base_path, []

    # Detect path parameters
    detected_params: list[str] = []
    for param_name, param in sig.parameters.items():
        if param_name == "self":
            continue

        # Check if explicitly marked as path param
        if path_params and param_name in path_params:
            detected_params.append(param_name)
            continue

        # Auto-detect: parameters ending with _id or named 'id'
        if path_params is None:  # Only auto-detect if not explicitly provided
            if param_name == "id" or param_name.endswith("_id"):
                detected_params.append(param_name)

    if not detected_params:
        return base_path, []

    # Build path with parameters
    path_suffix = "/".join(f"{{{p}}}" for p in detected_params)
    full_path = f"{base_path}/{path_suffix}"

    return full_path, detected_params


# =============================================================================
# Method Discovery
# =============================================================================


def _get_method_candidates(obj: Any) -> list[tuple[str, Callable]]:
    """Get all callable methods from an object.

    Excludes dunder methods (__*__).

    Args:
        obj: The object to inspect.

    Returns:
        List of (name, method) tuples.
    """
    candidates = []
    for name in dir(obj):
        # Skip dunder methods
        if name.startswith("__") and name.endswith("__"):
            continue

        try:
            attr = getattr(obj, name)
        except AttributeError:
            continue

        if callable(attr) and not isinstance(attr, type):
            candidates.append((name, attr))

    return candidates


def _filter_methods(
    candidates: list[tuple[str, Callable]],
    *,
    methods: dict[str, str] | None = None,
    exclude: list[str] | None = None,
    include_private: bool = False,
) -> list[tuple[str, Callable]]:
    """Filter method candidates.

    Args:
        candidates: List of (name, method) tuples.
        methods: If provided, only include methods with keys in this dict.
        exclude: Methods to exclude.
        include_private: Include _underscore methods.

    Returns:
        Filtered list of (name, method) tuples.
    """
    exclude = exclude or []
    result = []

    for name, method in candidates:
        # Check @endpoint_exclude decorator
        if getattr(method, _ENDPOINT_EXCLUDE_ATTR, False):
            continue

        # Skip private methods (unless include_private)
        if name.startswith("_") and not include_private:
            continue

        # If methods dict provided, only include those
        if methods is not None and name not in methods:
            continue

        # Check exclude list
        if name in exclude:
            continue

        result.append((name, method))

    return result


# =============================================================================
# Request/Response Model Generation
# =============================================================================


def _create_request_model(
    method: Callable,
    method_name: str,
    class_name: str,
) -> type[BaseModel] | None:
    """Create a Pydantic request model from method signature.

    Args:
        method: The method to analyze.
        method_name: Name of the method.
        class_name: Name of the class (for model naming).

    Returns:
        A Pydantic model class, or None if no parameters.
    """
    try:
        sig = inspect.signature(method)
        hints = get_type_hints(method)
    except (ValueError, TypeError):
        return None

    fields: dict[str, Any] = {}
    for param_name, param in sig.parameters.items():
        # Skip 'self'
        if param_name == "self":
            continue

        # Get type hint or default to Any
        param_type = hints.get(param_name, Any)

        # Handle default value
        if param.default is not inspect.Parameter.empty:
            fields[param_name] = (param_type, param.default)
        else:
            fields[param_name] = (param_type, ...)

    if not fields:
        return None

    # Create a descriptive model name
    model_name = f"{class_name}_{method_name.title().replace('_', '')}Request"

    return create_model(model_name, **fields)  # type: ignore[call-overload]


def _get_response_type(method: Callable) -> type | None:
    """Get the return type of a method.

    Args:
        method: The method to analyze.

    Returns:
        The return type, or None if not annotated.
    """
    try:
        hints = get_type_hints(method)
        return hints.get("return")
    except (ValueError, TypeError):
        return None


# =============================================================================
# Exception Handling
# =============================================================================

# Default exception to HTTP status mapping (public for customization)
DEFAULT_EXCEPTION_MAP: dict[type[Exception], int] = {
    ValueError: 400,
    TypeError: 400,
    KeyError: 404,
    LookupError: 404,
    PermissionError: 403,
    TimeoutError: 504,
    NotImplementedError: 501,
    ConnectionError: 503,
    OSError: 500,
}

# Keep private alias for backwards compatibility
_DEFAULT_EXCEPTION_MAP = DEFAULT_EXCEPTION_MAP

# Status code to title mapping (public for customization)
STATUS_TITLES: dict[int, str] = {
    400: "Validation Error",
    401: "Unauthorized",
    403: "Forbidden",
    404: "Not Found",
    405: "Method Not Allowed",
    409: "Conflict",
    422: "Unprocessable Entity",
    429: "Too Many Requests",
    500: "Internal Error",
    501: "Not Implemented",
    502: "Bad Gateway",
    503: "Service Unavailable",
    504: "Gateway Timeout",
}


def map_exception_to_http(
    exc: Exception,
    custom_handlers: dict[type[Exception], int] | None = None,
) -> tuple[int, str, str]:
    """Map an exception to HTTP status code, title, and detail.

    This is a public utility for mapping exceptions to HTTP responses.
    Can be used standalone outside of router_from_object.

    Args:
        exc: The exception to map.
        custom_handlers: Custom exception to HTTP status mapping.

    Returns:
        Tuple of (status_code, title, detail).

    Example:
        >>> status, title, detail = map_exception_to_http(ValueError("bad input"))
        >>> print(status, title)
        400 Validation Error
    """
    handlers = {**DEFAULT_EXCEPTION_MAP, **(custom_handlers or {})}

    # Check for exact type match
    exc_type = type(exc)
    if exc_type in handlers:
        status = handlers[exc_type]
    else:
        # Check for subclass match
        status = 500
        for exc_class, exc_status in handlers.items():
            if isinstance(exc, exc_class):
                status = exc_status
                break

    title = STATUS_TITLES.get(status, "Error")
    detail = str(exc)

    return status, title, detail


def _create_exception_handler(
    custom_handlers: dict[type[Exception], int] | None = None,
) -> Callable[[Exception], None]:
    """Create an exception handler function.

    Args:
        custom_handlers: Custom exception to HTTP status mapping.

    Returns:
        A function that raises FastApiException for exceptions.
    """

    def handle_exception(exc: Exception) -> None:
        """Map exception to FastApiException and raise it."""
        status, title, detail = map_exception_to_http(exc, custom_handlers)

        try:
            from svc_infra.exceptions import FastApiException

            raise FastApiException(
                title=title,
                detail=detail,
                status_code=status,
                code=type(exc).__name__.upper(),
            ) from exc
        except ImportError:
            from fastapi import HTTPException

            raise HTTPException(status_code=status, detail=detail) from exc

    return handle_exception


# =============================================================================
# Endpoint Creation
# =============================================================================


def _create_endpoint(
    method: Callable,
    method_name: str,
    class_name: str,
    http_verb: str,
    path: str,
    request_model: type[BaseModel] | None,
    response_type: type | None,
    exception_handler: Callable[[Exception], None],
    summary: str | None = None,
    description: str | None = None,
) -> tuple[Callable, dict[str, Any]]:
    """Create a FastAPI endpoint function.

    Args:
        method: The original method.
        method_name: Name of the method.
        class_name: Name of the class.
        http_verb: HTTP verb for the endpoint.
        path: URL path for the endpoint.
        request_model: Pydantic model for request body.
        response_type: Return type for response.
        exception_handler: Function to handle exceptions.
        summary: OpenAPI summary.
        description: OpenAPI description.

    Returns:
        Tuple of (endpoint_function, route_kwargs).
    """
    # Determine if method is async
    is_async = inspect.iscoroutinefunction(method)

    # Get docstring for OpenAPI
    docstring = method.__doc__ or ""
    if not summary:
        summary = docstring.split("\n")[0].strip() if docstring else method_name
    if not description:
        description = docstring

    # Build route kwargs
    route_kwargs: dict[str, Any] = {
        "summary": summary,
        "description": description,
    }
    if response_type:
        route_kwargs["response_model"] = response_type

    if http_verb == "GET":
        # For GET, parameters become query params
        if is_async:

            @functools.wraps(method)
            async def get_endpoint(**kwargs: Any) -> Any:
                try:
                    return await method(**kwargs)
                except Exception as e:
                    exception_handler(e)
                    return None  # Never reached

        else:

            @functools.wraps(method)
            async def get_endpoint(**kwargs: Any) -> Any:
                try:
                    return method(**kwargs)
                except Exception as e:
                    exception_handler(e)
                    return None

        # Preserve signature for FastAPI
        sig = inspect.signature(method)
        params = [p for p in sig.parameters.values() if p.name != "self"]
        get_endpoint.__signature__ = sig.replace(parameters=params)  # type: ignore[attr-defined]

        return get_endpoint, route_kwargs

    else:
        # For POST/PUT/PATCH/DELETE, use request body
        if request_model:
            if is_async:

                @functools.wraps(method)
                async def body_endpoint(request: request_model) -> Any:  # type: ignore[valid-type]
                    try:
                        return await method(**request.model_dump())  # type: ignore[attr-defined]
                    except Exception as e:
                        exception_handler(e)
                        return None

            else:

                @functools.wraps(method)
                async def body_endpoint(request: request_model) -> Any:  # type: ignore[valid-type]
                    try:
                        return method(**request.model_dump())  # type: ignore[attr-defined]
                    except Exception as e:
                        exception_handler(e)
                        return None

            return body_endpoint, route_kwargs

        else:
            # No parameters
            if is_async:

                @functools.wraps(method)
                async def no_param_endpoint() -> Any:
                    try:
                        return await method()
                    except Exception as e:
                        exception_handler(e)
                        return None

            else:

                @functools.wraps(method)
                async def no_param_endpoint() -> Any:
                    try:
                        return method()
                    except Exception as e:
                        exception_handler(e)
                        return None

            return no_param_endpoint, route_kwargs


# =============================================================================
# Main Function
# =============================================================================


def router_from_object(
    obj: Any,
    *,
    methods: dict[str, str] | None = None,
    exclude: list[str] | None = None,
    prefix: str = "",
    tags: list[str] | None = None,
    auth_required: bool = False,
    include_private: bool = False,
    exception_handlers: dict[type[Exception], int] | None = None,
) -> Any:
    """Convert a Python object's methods into a FastAPI router.

    Discovers callable methods on the object and creates corresponding
    FastAPI endpoints with automatic HTTP verb inference, path generation,
    and request/response model creation.

    Args:
        obj: The object whose methods become endpoints.
        methods: Override HTTP verb for specific methods. Keys are method
            names, values are HTTP verbs ("GET", "POST", etc.). If provided,
            only methods in this dict are included.
        exclude: Methods to exclude from the router.
        prefix: URL prefix for all endpoints.
        tags: OpenAPI tags (defaults to class name).
        auth_required: If True, uses user_router (JWT auth required).
            If False, uses public_router (no auth).
        include_private: Include methods starting with _ (excluded by default).
        exception_handlers: Custom exception to HTTP status mapping.

    Returns:
        A DualAPIRouter instance from svc-infra.

    Raises:
        ImportError: If FastAPI or svc-infra is not installed.

    Example:
        >>> class Calculator:
        ...     def add(self, a: float, b: float) -> float:
        ...         return a + b
        ...
        ...     def get_history(self) -> list[str]:
        ...         return []
        >>>
        >>> router = router_from_object(Calculator(), prefix="/calc")
        >>> # Creates:
        >>> # POST /calc/add     -> {"a": 1, "b": 2} -> 3.0
        >>> # GET  /calc/history -> [] -> []
    """
    class_name = type(obj).__name__
    default_tags = tags or [class_name]

    # Create router using svc-infra dual routers (MANDATORY per AGENTS.md)
    router: Any  # Can be DualAPIRouter or APIRouter depending on availability
    try:
        if auth_required:
            from svc_infra.api.fastapi.dual import user_router

            router = user_router(prefix=prefix, tags=default_tags)
        else:
            from svc_infra.api.fastapi.dual import public_router

            router = public_router(prefix=prefix, tags=default_tags)
    except ImportError:
        logger.warning(
            "svc-infra dual routers not available, using generic APIRouter. "
            "Install svc-infra for proper dual router support."
        )
        from fastapi import APIRouter

        router = APIRouter(prefix=prefix, tags=default_tags)  # type: ignore[arg-type]

    # Create exception handler
    exception_handler = _create_exception_handler(exception_handlers)

    # Discover and filter methods
    candidates = _get_method_candidates(obj)
    filtered = _filter_methods(
        candidates,
        methods=methods,
        exclude=exclude,
        include_private=include_private,
    )

    # Create endpoints for each method
    for method_name, method in filtered:
        # Check for @endpoint decorator config
        config = getattr(method, _ENDPOINT_CONFIG_ATTR, {})

        # Determine HTTP verb
        if methods and method_name in methods:
            http_verb = methods[method_name].upper()
        elif "method" in config:
            http_verb = config["method"].upper()
        else:
            http_verb = _infer_http_verb(method_name)

        # Determine path
        if "path" in config:
            path = config["path"]
        else:
            path = "/" + _generate_path(method_name)

        # Create request/response models
        request_model = _create_request_model(method, method_name, class_name)
        response_type = config.get("response_model") or _get_response_type(method)

        # Get summary/description from config
        summary = config.get("summary")
        description = config.get("description")

        # Create endpoint
        endpoint_func, route_kwargs = _create_endpoint(
            method=method,
            method_name=method_name,
            class_name=class_name,
            http_verb=http_verb,
            path=path,
            request_model=request_model,
            response_type=response_type,
            exception_handler=exception_handler,
            summary=summary,
            description=description,
        )

        # Add status code from config
        if "status_code" in config:
            route_kwargs["status_code"] = config["status_code"]

        # Register the route
        route_decorator = getattr(router, http_verb.lower())
        route_decorator(path, **route_kwargs)(endpoint_func)

        logger.debug(
            "Created %s %s%s for %s.%s",
            http_verb,
            prefix,
            path,
            class_name,
            method_name,
        )

    logger.info(
        "Created router for %s with %d endpoints (prefix='%s', auth=%s)",
        class_name,
        len(filtered),
        prefix,
        auth_required,
    )

    return router


# =============================================================================
# WebSocket Router Generation
# =============================================================================


def _get_websocket_methods(obj: Any) -> list[tuple[str, Callable, dict]]:
    """Get methods marked as WebSocket endpoints.

    Args:
        obj: The object to inspect.

    Returns:
        List of (name, method, config) tuples for WebSocket methods.
    """
    websocket_methods = []
    for name in dir(obj):
        if name.startswith("__") and name.endswith("__"):
            continue

        try:
            attr = getattr(obj, name)
        except AttributeError:
            continue

        if callable(attr) and hasattr(attr, _WEBSOCKET_ENDPOINT_ATTR):
            config = getattr(attr, _WEBSOCKET_ENDPOINT_ATTR, {})
            websocket_methods.append((name, attr, config))

    return websocket_methods


def router_from_object_with_websocket(
    obj: Any,
    *,
    methods: dict[str, str] | None = None,
    exclude: list[str] | None = None,
    prefix: str = "",
    tags: list[str] | None = None,
    auth_required: bool = False,
    include_private: bool = False,
    exception_handlers: dict[type[Exception], int] | None = None,
) -> tuple[Any, Any]:
    """Convert object methods to FastAPI router including WebSocket endpoints.

    This is an extended version of router_from_object that also creates
    a separate WebSocket router for methods marked with @websocket_endpoint.

    Args:
        obj: The object whose methods become endpoints.
        methods: Override HTTP verb for specific methods.
        exclude: Methods to exclude from the router.
        prefix: URL prefix for all endpoints.
        tags: OpenAPI tags (defaults to class name).
        auth_required: If True, uses authenticated routers.
        include_private: Include methods starting with _.
        exception_handlers: Custom exception to HTTP status mapping.

    Returns:
        Tuple of (http_router, websocket_router).

    Example:
        >>> class StreamService:
        ...     def get_status(self) -> dict:
        ...         return {"status": "ok"}
        ...
        ...     @websocket_endpoint(path="/stream")
        ...     async def stream_data(self):
        ...         while True:
        ...             yield {"data": "..."}
        >>>
        >>> http_router, ws_router = router_from_object_with_websocket(
        ...     StreamService(), prefix="/api"
        ... )
        >>> app.include_router(http_router)
        >>> app.include_router(ws_router)
    """
    # Create HTTP router
    http_router = router_from_object(
        obj,
        methods=methods,
        exclude=exclude,
        prefix=prefix,
        tags=tags,
        auth_required=auth_required,
        include_private=include_private,
        exception_handlers=exception_handlers,
    )

    class_name = type(obj).__name__
    default_tags = tags or [class_name]

    # Create WebSocket router using svc-infra dual routers
    ws_router: Any  # Can be DualAPIRouter or APIRouter depending on availability
    try:
        if auth_required:
            from svc_infra.api.fastapi.dual import ws_protected_router

            ws_router = ws_protected_router(prefix=prefix, tags=default_tags)
        else:
            from svc_infra.api.fastapi.dual import ws_public_router

            ws_router = ws_public_router(prefix=prefix, tags=default_tags)
    except ImportError:
        logger.warning("svc-infra WebSocket routers not available, using generic APIRouter.")
        from fastapi import APIRouter

        ws_router = APIRouter(prefix=prefix, tags=default_tags)  # type: ignore[arg-type]

    # Get WebSocket methods
    ws_methods = _get_websocket_methods(obj)

    for method_name, method, config in ws_methods:
        # Determine path
        if "path" in config:
            path = config["path"]
        else:
            path = "/" + _generate_path(method_name)

        # Create WebSocket endpoint
        @ws_router.websocket(path)
        async def websocket_handler(websocket: Any, _method: Callable = method) -> None:
            """WebSocket handler that streams data from the method."""
            await websocket.accept()
            try:
                # Check if method is async generator
                result = _method()
                if hasattr(result, "__anext__"):
                    # Async generator - stream data
                    async for data in result:
                        await websocket.send_json(data)
                elif hasattr(result, "__next__"):
                    # Sync generator - stream data
                    for data in result:
                        await websocket.send_json(data)
                else:
                    # Regular return - send once
                    if inspect.iscoroutine(result):
                        result = await result
                    await websocket.send_json(result)
            except Exception as e:
                await websocket.send_json({"error": str(e)})
            finally:
                await websocket.close()

        logger.debug(
            "Created WebSocket %s%s for %s.%s",
            prefix,
            path,
            class_name,
            method_name,
        )

    logger.info(
        "Created WebSocket router for %s with %d endpoints",
        class_name,
        len(ws_methods),
    )

    return http_router, ws_router

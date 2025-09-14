from typing import Any, Callable, List

from fastapi import APIRouter


def _norm_primary(path: str) -> str:
    # prefer the no-slash version in docs
    return path[:-1] if path.endswith("/") and path != "/" else path


def _alt_with_slash(path: str) -> str:
    # ensure the alternate has a trailing slash (except root "")
    return (path + "/") if not path.endswith("/") else path


class DualAPIRouter(APIRouter):
    """
    Registers two routes per endpoint:
      • primary: shown in OpenAPI (no trailing slash)
      • alternate: hidden in OpenAPI (with trailing slash)
    Keeps redirect_slashes=False behavior (no 307s).
    """

    def _dual_decorator(
        self, path: str, methods: List[str], *, show_in_schema: bool = True, **kwargs
    ):
        primary = _norm_primary(path or "")
        alt = _alt_with_slash(path or "")

        def decorator(func: Callable[..., Any]):
            # visible
            self.add_api_route(
                primary, func, methods=methods, include_in_schema=show_in_schema, **kwargs
            )
            # hidden twin
            self.add_api_route(alt, func, methods=methods, include_in_schema=False, **kwargs)
            return func

        return decorator

    # Convenience shorthands mirroring APIRouter API
    def get(self, path: str, *_, show_in_schema: bool = True, **kwargs):
        return self._dual_decorator(path, ["GET"], show_in_schema=show_in_schema, **kwargs)

    def post(self, path: str, *_, show_in_schema: bool = True, **kwargs):
        return self._dual_decorator(path, ["POST"], show_in_schema=show_in_schema, **kwargs)

    def patch(self, path: str, *_, show_in_schema: bool = True, **kwargs):
        return self._dual_decorator(path, ["PATCH"], show_in_schema=show_in_schema, **kwargs)

    def delete(self, path: str, *_, show_in_schema: bool = True, **kwargs):
        return self._dual_decorator(path, ["DELETE"], show_in_schema=show_in_schema, **kwargs)

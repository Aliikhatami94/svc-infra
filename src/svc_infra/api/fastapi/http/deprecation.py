from functools import wraps


def deprecated(sunset_http_date: str | None = None, link: str | None = None):
    def deco(handler):
        @wraps(handler)
        async def wrapper(*a, **kw):
            resp = await handler(*a, **kw)
            # starlette Response or FastAPI returns both OK
            headers = getattr(resp, "headers", None)
            if headers is not None:
                headers.setdefault("Deprecation", "true")
                if sunset_http_date:
                    headers.setdefault("Sunset", sunset_http_date)
                if link:
                    headers.setdefault("Link", f'<{link}>; rel="deprecation"')
            return resp

        return wrapper

    return deco

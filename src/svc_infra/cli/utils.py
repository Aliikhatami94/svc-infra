import inspect
import asyncio
from functools import wraps

def _async_cmd(fn):
    sig = inspect.signature(fn)
    @wraps(fn)
    def wrapper(*args, **kwargs):
        return asyncio.run(fn(*args, **kwargs))
    wrapper.__signature__ = sig
    return wrapper
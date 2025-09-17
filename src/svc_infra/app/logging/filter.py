from __future__ import annotations

import logging
from typing import Iterable


def _is_metrics_like(record: logging.LogRecord, paths: Iterable[str]) -> bool:
    """
    Heuristics to detect access-log lines for given paths across uvicorn/gunicorn.
    Works with both dict- and string-formatted records.
    """
    try:
        # uvicorn/gunicorn commonly put 'request_line' in args (dict)
        if isinstance(record.args, dict):
            rl = record.args.get("request_line") or record.args.get("r")
            if rl and isinstance(rl, str):
                # request line looks like: "GET /metrics HTTP/1.1"
                for p in paths:
                    if f" {p} " in f" {rl} ":
                        return True
        # Fallback: substring match in rendered message
        msg = record.getMessage()
        if isinstance(msg, str):
            for p in paths:
                if f" {p} " in f" {msg} ":
                    return True
    except Exception:
        pass
    return False


class _DropPathsFilter(logging.Filter):
    def __init__(self, paths: Iterable[str]):
        super().__init__()
        self._paths = tuple(paths)

    def filter(self, record: logging.LogRecord) -> bool:
        # Return False to DROP the record.
        return not _is_metrics_like(record, self._paths)


def filter_logs_for_paths(
    *,
    paths: Iterable[str] = ("/metrics",),
    enabled: bool = True,
) -> None:
    """
    When enabled=True, suppress access logs for given paths on common web servers.
    Safe to call multiple times.
    """
    if not enabled:
        return

    filt = _DropPathsFilter(paths)

    # Common access loggers to target
    for name in ("uvicorn.access", "gunicorn.access"):
        try:
            logger = logging.getLogger(name)
            # Avoid stacking duplicates
            if not any(isinstance(f, _DropPathsFilter) for f in logger.filters):
                logger.addFilter(filt)
        except Exception:
            pass

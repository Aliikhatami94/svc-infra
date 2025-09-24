from __future__ import annotations

import logging

from fastapi import Response, status

from svc_infra.api.fastapi.auth import public_router

router = public_router()
ROUTER_TAG = "health"


@router.get("/ping", status_code=status.HTTP_200_OK)
def ping():
    logging.info("Health check: /ping endpoint accessed. Service is responsive.")
    return Response(status_code=status.HTTP_200_OK)

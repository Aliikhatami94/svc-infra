from __future__ import annotations

import logging

from fastapi import Response, status

from svc_infra.api.fastapi.dual.public import public_router

router = public_router()
ROUTER_TAG = "health"
DESCRIPTION = "Operation to check if the service is up and running."


@router.get("/ping", status_code=status.HTTP_200_OK)
def ping():
    logging.info("Health check: /ping endpoint accessed. Service is responsive.")
    return Response(status_code=status.HTTP_200_OK)

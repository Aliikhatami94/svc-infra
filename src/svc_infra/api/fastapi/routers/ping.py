from __future__ import annotations

import logging

from fastapi import Response, status

from svc_infra.api.fastapi.dual.public import public_router
from svc_infra.api.fastapi.paths.generic import PING_PATH

router = public_router(tags=["Health Check"])


@router.get(
    PING_PATH,
    status_code=status.HTTP_200_OK,
    description="Operation to check if the service is up and running",
    operation_id="health_ping_get",
)
def ping():
    logging.info("Health check: /ping endpoint accessed. Service is responsive.")
    return Response(status_code=status.HTTP_200_OK)

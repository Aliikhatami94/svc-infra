from fastapi import APIRouter, Response, status
import logging

router = APIRouter()

@router.get("/ping", status_code=status.HTTP_200_OK)
def ping():
    logging.info("Health check: /ping endpoint accessed. Service is responsive.")
    return Response(status_code=status.HTTP_200_OK)

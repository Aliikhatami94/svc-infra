from fastapi import HTTPException, Request, status


def require_if_match(request: Request, current_etag: str):
    val = request.headers.get("If-Match")
    if not val:
        raise HTTPException(
            status_code=status.HTTP_428_PRECONDITION_REQUIRED,
            detail="If-Match header required for update.",
        )
    if current_etag not in [t.strip() for t in val.split(",")]:
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED, detail="ETag precondition failed."
        )

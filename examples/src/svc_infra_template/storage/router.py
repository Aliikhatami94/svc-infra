"""FastAPI router for direct storage operations.

This demonstrates direct usage of storage backends without
the document management layer. Useful for simple file storage.
"""

from fastapi import Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

from svc_infra.api.fastapi.dual.public import public_router
from svc_infra.storage import easy_storage
from svc_infra.storage.base import StorageBackend

# Create router using svc-infra's public_router (no auth required for demo)
router = public_router(prefix="/storage", tags=["Storage"])


# Dependency to get storage backend
def get_storage() -> StorageBackend:
    """Get storage backend instance."""
    return easy_storage()


class UploadResponse(BaseModel):
    """Response from file upload."""

    path: str
    size: int
    message: str


class SignedUrlResponse(BaseModel):
    """Response with signed URL."""

    url: str
    expires_in: int


@router.post("/upload", response_model=UploadResponse)
async def upload_file(
    path: str,
    file: UploadFile = File(...),
    storage: StorageBackend = Depends(get_storage),
) -> UploadResponse:
    """Upload a file to storage backend.

    This is direct storage access without document metadata.
    Use /documents/upload for document management with metadata.

    Example:
        ```bash
        curl -X POST http://localhost:8000/storage/upload?path=files/test.pdf \\
          -F "file=@test.pdf"
        ```
    """
    content = await file.read()
    await storage.upload(path=path, content=content)

    return UploadResponse(
        path=path,
        size=len(content),
        message=f"File uploaded to {path}",
    )


@router.get("/download/{path:path}")
async def download_file(
    path: str,
    storage: StorageBackend = Depends(get_storage),
) -> Response:
    """Download a file from storage.

    Example:
        ```bash
        curl http://localhost:8000/storage/download/files/test.pdf -o downloaded.pdf
        ```
    """
    try:
        content = await storage.download(path=path)
        return Response(
            content=content,
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": f'attachment; filename="{path.split("/")[-1]}"',
            },
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"File not found: {path}")


@router.delete("/{path:path}", status_code=204)
async def delete_file(
    path: str,
    storage: StorageBackend = Depends(get_storage),
) -> None:
    """Delete a file from storage.

    Example:
        ```bash
        curl -X DELETE http://localhost:8000/storage/files/test.pdf
        ```
    """
    try:
        await storage.delete(path=path)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"File not found: {path}")


@router.get("/exists/{path:path}")
async def check_file_exists(
    path: str,
    storage: StorageBackend = Depends(get_storage),
) -> dict:
    """Check if a file exists in storage.

    Example:
        ```bash
        curl http://localhost:8000/storage/exists/files/test.pdf
        ```
    """
    exists = await storage.exists(path=path)
    return {"path": path, "exists": exists}


@router.post("/signed-url", response_model=SignedUrlResponse)
async def generate_signed_url(
    path: str,
    expires_in: int = 3600,
    storage: StorageBackend = Depends(get_storage),
) -> SignedUrlResponse:
    """Generate a signed URL for downloading a file.

    This is useful for providing temporary access to private files.

    Example:
        ```bash
        curl -X POST "http://localhost:8000/storage/signed-url?path=files/test.pdf&expires_in=3600"
        ```
    """
    try:
        url = await storage.generate_presigned_url(path=path, expires_in=expires_in)
        return SignedUrlResponse(url=url, expires_in=expires_in)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"File not found: {path}")
    except NotImplementedError:
        raise HTTPException(
            status_code=501,
            detail="Signed URLs not supported by this storage backend",
        )


@router.get("/list")
async def list_files(
    prefix: str = "",
    storage: StorageBackend = Depends(get_storage),
) -> dict:
    """List files in storage with optional prefix filter.

    Example:
        ```bash
        # List all files
        curl http://localhost:8000/storage/list

        # List files in specific directory
        curl http://localhost:8000/storage/list?prefix=files/
        ```
    """
    try:
        files = await storage.list_files(prefix=prefix)
        return {"prefix": prefix, "files": files, "count": len(files)}
    except NotImplementedError:
        raise HTTPException(
            status_code=501,
            detail="File listing not supported by this storage backend",
        )

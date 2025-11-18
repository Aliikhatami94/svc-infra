"""Direct storage backend usage demo.

This module demonstrates Layer 0 (storage backend) usage:
- Direct file upload/download
- Signed URL generation
- Storage backend selection (S3/local/memory)

For higher-level document management with metadata, see the documents module.
"""

from .router import router

__all__ = ["router"]

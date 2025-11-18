"""Documents management module - Generic file/document storage demo.

This module demonstrates Layer 1 (svc-infra) document management:
- Upload documents with metadata tagging
- List and filter documents by metadata
- Download and delete documents
- Storage backend integration (S3/local/memory)

This is a generic pattern that can be extended for domain-specific use cases.
See fin-infra for financial document example with OCR and AI analysis.
"""

from .router import router

__all__ = ["router"]

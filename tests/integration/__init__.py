"""Integration tests for svc-infra.

These tests require actual service credentials to run:
- STRIPE_API_KEY: Stripe test API key
- AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY: AWS credentials
- STORAGE_S3_BUCKET: S3 bucket name

Run integration tests:
    pytest tests/integration -v

Skip integration tests:
    pytest tests/integration -v -m "not integration"
"""

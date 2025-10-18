# Acceptance tests live here. See docs/acceptance.md

Conventions:
- Mark tests with @pytest.mark.acceptance
- Use BASE_URL env var for the target API. When unset, the tests run
  against the in-repo acceptance ASGI app via httpx' ASGITransport so
  scenarios remain self-contained.

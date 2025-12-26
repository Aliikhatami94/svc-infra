# Changelog

All notable changes to this project will be documented in this file.

This file is auto-generated from conventional commits using [git-cliff](https://git-cliff.org/).

## [0.1.716] - 2025-12-26


### Bug Fixes

- Fix mypy missing return statement in circuit breaker protect decorator
- Prevent docs-changelog race condition with publish workflow


### Documentation

- Update changelog [skip ci]


### Features

- Add resilience patterns documentation and implement retry and circuit breaker utilities

## [0.1.715] - 2025-12-24


### Documentation

- Update changelog [skip ci]


### Other Changes

- Add comprehensive tests for object_router functionality

- Implement tests for method-to-endpoint mapping, HTTP verb inference, and path generation.
- Include tests for request/response model generation and exception mapping.
- Cover async method handling and decorator-based configuration.
- Test edge cases, including empty classes and classes with only private methods.
- Validate auth_required parameter functionality and path parameter handling.

## [0.1.714] - 2025-12-23


### Features

- Add skip_paths parameter for middleware to exclude specific endpoints

## [0.1.713] - 2025-12-19


### Bug Fixes

- Lower coverage threshold to 50% to match current state
- Update bandit config to skip false positive security warnings
- Merge deprecation utilities into utils.py


### Features

- Add deprecation policy and helpers


### Miscellaneous

- Update poetry.lock

## [0.1.711] - 2025-12-18


### Features

- Add git-cliff configuration for automated changelog generation

## [0.1.710] - 2025-12-18


### Other Changes

- Refactor test code for improved readability and consistency

- Simplified list comprehensions and lambda functions in various test files.
- Consolidated multi-line statements into single lines where appropriate.
- Enhanced clarity in assertions and mock setups across multiple test cases.
- Ensured consistent formatting and style adherence throughout the test suite.
- Refactor type hints to use `| None` syntax for optional types

- Updated various files to replace `Optional[X]` with `X | None` for better readability and consistency with Python 3.10+ syntax.
- Modified settings, models, and middleware to reflect the new type hinting style.
- Ensured compatibility with Pydantic and FastAPI by adjusting type annotations in configuration and request handling.
- Cleaned up imports by removing unnecessary `Optional` imports where applicable.
- Refactor datetime usage and improve type hints across tests

- Replaced `timezone.utc` with `UTC` from `datetime` module for consistency in datetime handling.
- Updated type hints from `Dict` to `dict` and `List` to `list` for better readability and to align with Python's built-in types.
- Removed unnecessary comments and improved code clarity by simplifying variable names.
- Ensured consistent exception handling by specifying exception types in test cases.
- Cleaned up imports and fixed minor formatting issues in various test files.
- Refactor logging and security modules to use UTC consistently

- Updated datetime handling in logging formatters to use UTC instead of timezone.utc.
- Replaced instances of timezone.utc with UTC in security-related modules for consistency.
- Adjusted type casting to use string literals in various locations for improved clarity.
- Refactored imports to utilize collections.abc for better compatibility with Python 3.9+.
- Ensured all datetime.now() calls are consistent across the codebase to prevent timezone-related issues.
- Refactor type hints to use union types and improve code consistency

- Updated type hints across multiple files to utilize the new union type syntax (e.g., `str | None` instead of `Optional[str]`).
- Removed unnecessary imports of `Optional` where union types are used.
- Adjusted type hints for various function parameters and return types to enhance clarity and maintainability.
- Ensured consistent use of `dict` and `list` instead of `Dict` and `List` for type annotations.
- Improved readability and modernized the codebase in line with recent Python enhancements.

## [0.1.709] - 2025-12-18


### Documentation

- Update changelog [skip ci]


### Features

- Enhance billing module documentation and deprecate synchronous service
- Enhance documentation with comprehensive guides and error handling patterns


### Other Changes

- Implement feature X to enhance user experience and optimize performance

## [0.1.708] - 2025-12-18


### Features

- Add comprehensive unit tests for SQL injection prevention and infrastructure edge cases

## [0.1.707] - 2025-12-18


### Bug Fixes

- Add pytest-asyncio to test dependencies in docker-compose

## [0.1.706] - 2025-12-18


### Features

- Add integration tests for billing service and S3 storage backend

## [0.1.705] - 2025-12-17


### Bug Fixes

- Add check for optional stripe SDK dependency in test
- Refine MongoDB helper function signatures for improved type hinting
- Correct spacing in type ignore comments for AsyncIOMotorDatabase and AsyncIOMotorClient
- Remove unnecessary spaces in type ignore comments for AsyncIOMotorDatabase and AsyncIOMotorClient
- Update poetry.lock for package optionality and platform-specific markers


### Features

- Implement optional MongoDB dependency handling with informative stubs for missing imports
- Add optional MongoDB dependency handling and stubs for missing imports
- Enhance svc-infra with comprehensive API and authentication modules, optional MongoDB support, and improved documentation


### Refactor

- Streamline MongoDB dependency handling and improve ObjectId fallback

## [0.1.704] - 2025-12-17


### Bug Fixes

- Update error and success messages for user deletion

## [0.1.703] - 2025-12-17


### Bug Fixes

- Disable Rich colors in CLI tests for CI consistency
- Match CI config exactly (use ruff defaults)
- Fix type ignore placement + remove mypy from pre-commit
- Apply ruff formatting + switch pre-commit from black to ruff
- Remove unused _Any import in sql/management.py
- Resolve all mypy errors for CI


### Miscellaneous

- Update CI workflow to trigger on successful completion of CI jobs

## [0.1.702] - 2025-12-17


### Refactor

- Clean up imports and remove unused variables in unit tests

## [0.1.701] - 2025-12-16


### Other Changes

- Refactor and enhance various components across the application

- Updated StripeAdapter methods to include type ignores for attribute definitions.
- Modified settings to ensure default provider is set to "stripe" if not specified.
- Improved authentication middleware to handle session middleware checks with type ignores.
- Enhanced MFA router to include type ignores for attribute definitions.
- Updated API key router to include type ignores for attribute definitions.
- Refined OAuth router to improve JWT handling and added type ignores where necessary.
- Enhanced security module to include type ignores for attribute definitions.
- Improved graceful shutdown middleware to handle app state checks more robustly.
- Updated request size limit middleware to improve error handling and logging.
- Enhanced logging formats to include type ignores for attribute definitions.
- Refactored cache module to provide a clearer interface for cache instance access.
- Improved SQL export commands to ensure proper engine casting for async operations.
- Enhanced Redis job queue to include type casting for Redis responses.
- Updated webhook module to introduce a new trigger_webhook function for better event handling.
- Added comprehensive tests for document upload functionality to ensure proper handling of multipart files.

## [0.1.700] - 2025-12-15


### Other Changes

- Refactor type hints and improve type safety across multiple modules

- Updated type hints to use `Literal` and `Optional` for better clarity and type safety in `aiydan.py`, `stripe.py`, and `service.py`.
- Enhanced type annotations in FastAPI routes and dependencies to ensure compatibility with type checkers.
- Added type checks and assertions in various modules to enforce expected types and prevent runtime errors.
- Improved handling of optional parameters and default values in functions across several files, including `add.py`, `management.py`, and `utils.py`.
- Refined logging setup to ensure correct type casting for logging configuration.
- Adjusted Redis job queue handling to ensure proper type conversion and error handling.
- General cleanup of type hints and comments for better maintainability and readability.

## [0.1.699] - 2025-12-14


### Refactor

- Enhance type hinting and casting across multiple modules

## [0.1.698] - 2025-12-14


### Other Changes

- Automated/Bulk Fixes

## [0.1.697] - 2025-12-14


### Features

- Add centralized exception handling and logging utilities for svc-infra

## [0.1.696] - 2025-12-14


### Features

- Enhance logging and add production warnings for in-memory stores across various modules

## [0.1.695] - 2025-12-14


### Features

- Add require_secret function for secure secret loading and enhance webhook secret encryption guidance

## [0.1.694] - 2025-12-14


### Features

- Implement require_secret for sensitive configurations and add encryption for webhook secrets

## [0.1.693] - 2025-12-13


### Other Changes

- Add unit tests for logging and testing modules

- Created unit tests for the svc_infra.logging module, covering flush functionality, JSON and text formatting, container configuration, logger retrieval, and context management.
- Implemented unit tests for the svc_infra.testing module, including tests for CacheEntry, MockCache, MockJob, MockJobQueue, and fixture data generation.

## [0.1.692] - 2025-12-12


### Bug Fixes

- Update repository references from nfraxio to nfraxlab in documentation and code


### Miscellaneous

- Trigger pypi publish
- Re-trigger pypi publish after enabling workflow
- Trigger pypi publish

## [0.1.691] - 2025-12-11


### Refactor

- Enhance DB lifecycle management to preserve existing lifespan context

## [0.1.690] - 2025-12-10


### Miscellaneous

- Remove unnecessary backup files and update dependencies in pyproject.toml

## [0.1.689] - 2025-12-10


### Other Changes

- Remove ai-infra dependency from pyproject.toml

## [0.1.688] - 2025-12-10


### Miscellaneous

- Add MIT License file

## [0.1.687] - 2025-12-10


### Miscellaneous

- Remove outdated ADR for content loaders architecture

## [0.1.686] - 2025-12-10


### Features

- Add tick interval parameter to InMemoryScheduler

## [0.1.685] - 2025-12-09


### Features

- Implement LoadedContent model and URLLoader for fetching content from URLs

## [0.1.684] - 2025-12-08


### Features

- Add support for additional FastAPI kwargs in service API setup

## [0.1.683] - 2025-12-04


### Documentation

- Consolidate badge display in README for improved readability

## [0.1.682] - 2025-12-04


### Documentation

- Update README for improved clarity and structure

## [0.1.681] - 2025-12-02


### Features

- Enhance CORS setup with regex support for wildcard origins

## [0.1.680] - 2025-11-29


### Miscellaneous

- Remove obsolete ADRs and documentation

## [0.1.679] - 2025-11-29


### Other Changes

- Add unit tests for WebSocket functionality

- Implement unit tests for WebSocketClient, covering initialization, connection, messaging, and context manager behavior.
- Add tests for ConnectionManager, including connection lifecycle, messaging, room management, and introspection.
- Create tests for WebSocket router refactoring, ensuring proper route registration and integration with FastAPI.
- Introduce tests for WebSocket authentication, validating token extraction, JWT decoding, and scope enforcement.

## [0.1.678] - 2025-11-29


### Features

- Add WebSocket authentication infrastructure with lightweight JWT support

## [0.1.677] - 2025-11-29


### Features

- Implement WebSocket infrastructure with FastAPI integration and connection management

## [0.1.676] - 2025-11-28


### Features

- Add WebSocket infrastructure with client and server utilities

## [0.1.675] - 2025-11-28


### Bug Fixes

- Correct documentation paths from src/svc_infra/docs to docs/

## [0.1.674] - 2025-11-27


### Other Changes

- Add documentation for tenancy model, timeouts, versioned integrations, and webhooks framework

- Introduced a comprehensive guide on the tenancy model, detailing tenant resolution, enforcement in the data layer, and per-tenant rate limits.
- Documented timeout configurations and resource limits, including request/handler timeouts, outbound HTTP client timeouts, and graceful shutdown procedures.
- Explained the usage of `add_*` functions under versioned routing, providing a simple solution for organizing API endpoints under version namespaces.
- Developed a webhooks framework documentation, covering event publishing, delivery handling, and signature verification in FastAPI.

## [0.1.673] - 2025-11-26


### Features

- Enhance middleware to support skip_paths for streaming and long-running endpoints

## [0.1.672] - 2025-11-26


### Features

- Enhance HandlerTimeoutMiddleware to support streaming responses and adjust timeout behavior

## [0.1.671] - 2025-11-25


### Features

- Add skip_paths option to SimpleRateLimitMiddleware and log skipped paths

## [0.1.670] - 2025-11-25


### Features

- Add skip_paths option to IdempotencyMiddleware for streaming compatibility

## [0.1.669] - 2025-11-25


### Features

- Refactor RequestIdMiddleware for pure ASGI compatibility and streaming safety

## [0.1.668] - 2025-11-19


### Features

- Ignore unknown environment variables in storage settings

## [0.1.667] - 2025-11-18


### Features

- Add document management and storage examples with API endpoints
- Implement document management system with upload, download, and filtering capabilities

## [0.1.666] - 2025-11-18


### Bug Fixes

- Update acceptance tests for improved error handling and unique user IDs

## [0.1.665] - 2025-11-18


### Features

- Implement generic document management system with FastAPI integration

## [0.1.664] - 2025-11-18


### Features

- Implement acceptance tests and storage API endpoints

## [0.1.663] - 2025-11-18


### Other Changes

- Local, Memory, and S3

- Implemented comprehensive unit tests for LocalBackend, covering file storage, retrieval, metadata handling, deletion, and key validation.
- Created unit tests for MemoryBackend, including quota enforcement, metadata retrieval, and concurrent access.
- Developed unit tests for S3Backend, focusing on file operations, presigned URL generation, and metadata handling, with integration tests for real S3 operations.
- Updated tenant CRUD router tests to utilize Pydantic's model_config for attribute mapping.

## [0.1.662] - 2025-11-17


### Refactor

- Remove ProviderAccount model and update OAuth integration notes

## [0.1.661] - 2025-11-17


### Features

- Add import and logging for core security models in env_async and env_sync templates

## [0.1.660] - 2025-11-17


### Bug Fixes

- Update relationship comment for ProviderAccount model

## [0.1.659] - 2025-11-17


### Features

- Implement opt-in OAuth provider account models and update migration templates

## [0.1.658] - 2025-11-17


### Features

- Implement ProviderAccount model for OAuth provider account linking

## [0.1.657] - 2025-11-17


### Bug Fixes

- Prioritize post_login_redirect parameter over settings in _determine_final_redirect_url

## [0.1.656] - 2025-11-17


### Bug Fixes

- Enforce strict checks for SQLAlchemy MetaData instances in _maybe_add and _scan_module_objects

## [0.1.655] - 2025-11-17


### Bug Fixes

- Ensure only SQLAlchemy MetaData objects are added in _maybe_add and _scan_module_objects

## [0.1.654] - 2025-11-17


### Bug Fixes

- Update server_default for created_at columns to use text() for consistency

## [0.1.653] - 2025-11-15


### Refactor

- Rename capture_add_function_router to extract_router and update documentation

## [0.1.652] - 2025-11-15


### Features

- Add capture_add_function_router helper and documentation for versioned routing

## [0.1.651] - 2025-11-15


### Refactor

- Remove scoped documentation registration from payments and auth setup

## [0.1.650] - 2025-11-15


### Refactor

- Remove scoped documentation registration from billing, mongo, and sql resource setup

## [0.1.649] - 2025-11-15


### Features

- Add server URL handling for scoped documentation


### Other Changes

- Add server URL handling for scoped documentation

## [0.1.648] - 2025-11-14


### Features

- Enhance scoped docs handling with root exclusion logic


### Other Changes

- Enhance scoped docs handling with root exclusion logic

## [0.1.647] - 2025-11-14


### Other Changes

- Merge pull request #64 from Aliikhatami94/feat/prod-readiness-v1

Refactor caching and database setup to use async context managers
- Merge branch 'main' into feat/prod-readiness-v1

## [0.1.646] - 2025-11-14


### Other Changes

- Always display root card in service API setup across all en…

## [0.1.645] - 2025-11-14


### Other Changes

- Update test assertions and add missing refresh mocks for …

## [0.1.644] - 2025-11-14


### Other Changes

- Update payload types in CRUD router functions to use speci…

## [0.1.643] - 2025-11-14


### Other Changes

- Register scoped documentation for billing and MongoDB res…

## [0.1.642] - 2025-11-14


### Other Changes

- Add scoped documentation registration for SQL resources

## [0.1.641] - 2025-11-13


### Other Changes

- Update env.py templates to use build_engine for proper SSL …

## [0.1.640] - 2025-11-13


### Other Changes

- Don't add ssl=true to asyncpg URL query, handle in connect_…

## [0.1.639] - 2025-11-13


### Other Changes

- Remove ssl/sslmode from URL query for asyncpg, use connect_…

## [0.1.638] - 2025-11-13


### Other Changes

- Use ssl parameter in connect_args for asyncpg, not sslmode

## [0.1.637] - 2025-11-13


### Other Changes

- Merge pull request #54 from Aliikhatami94/feat/prod-readiness-v1

Feat/prod readiness v1

## [0.1.636] - 2025-11-04


### Other Changes

- Merge pull request #53 from Aliikhatami94/feat/prod-readiness-v1

Feat/prod readiness v1

## [0.1.635] - 2025-11-02


### Other Changes

- Merge pull request #52 from Aliikhatami94/feat/prod-readiness-v1

Feat/prod readiness v1

## [0.1.634] - 2025-11-01


### Other Changes

- Merge pull request #51 from Aliikhatami94/feat/prod-readiness-v1

Feat/prod readiness v1

## [0.1.633] - 2025-10-22


### Other Changes

- Add unit and acceptance tests for timeout handling and j…

## [0.1.632] - 2025-10-22


### Other Changes

- Implement admin API with impersonation support and relat…

## [0.1.631] - 2025-10-22


### Other Changes

- Add easy integration helper `add_cache` for ASGI app lif…

## [0.1.630] - 2025-10-22


### Other Changes

- Merge pull request #47 from Aliikhatami94/feat/prod-readiness-v1

Feat/prod readiness v1

## [0.1.629] - 2025-10-21


### Other Changes

- Update acceptance tests and documentation for CLI migrations, j…

## [0.1.628] - 2025-10-21


### Other Changes

- Enhance acceptance tests for OpenAPI validation, maintenance mo…

## [0.1.627] - 2025-10-21


### Other Changes

- Merge pull request #43 from Aliikhatami94/feat/prod-readiness-v1

Feat/prod readiness v1

## [0.1.626] - 2025-10-20


### Other Changes

- Update healthcheck parameters and improve documentation command…

## [0.1.625] - 2025-10-20


### Other Changes

- Add documentation command to retrieve and display available doc…

## [0.1.624] - 2025-10-20


### Other Changes

- Add new subcommands for SQL, Docs, DX, Jobs, and SDK groups in …

## [0.1.623] - 2025-10-20


### Other Changes

- Merge pull request #39 from Aliikhatami94/feat/prod-readiness-v1

Add comprehensive documentation for idempotency, background jobs, obs…

## [0.1.622] - 2025-10-19


### Other Changes

- Enhance documentation command handling with improved topic norm…

## [0.1.621] - 2025-10-19


### Other Changes

- Refactor documentation topic discovery to normalize topic names…

## [0.1.620] - 2025-10-19


### Other Changes

- Enhance documentation topic discovery with improved package met…

## [0.1.619] - 2025-10-19


### Other Changes

- Merge pull request #35 from Aliikhatami94/feat/prod-readiness-v1

Feat/prod readiness v1

## [0.1.618] - 2025-10-19


### Bug Fixes

- Always display root card in service API setup across all environments
- Update test assertions and add missing refresh mocks for SQL repository
- Update payload types in CRUD router functions to use specific schemas
- Remove _ensure_ssl_default calls from env.py templates
- Update env.py templates to use build_engine for proper SSL handling
- Don't add ssl=true to asyncpg URL query, handle in connect_args only
- Remove ssl/sslmode from URL query for asyncpg, use connect_args
- Use ssl parameter in connect_args for asyncpg, not sslmode
- Handle asyncpg Railway connections properly
- Ensure proper handling of timeout seconds in middleware and client initialization
- Prevent impersonation override stacking
- Install uvicorn for acceptance api


### Features

- Register scoped documentation for billing and MongoDB resources
- Add scoped documentation registration for SQL resources
- Add user and entity models with migrations
- Implement duplicate prevention in scaffolding scripts
- Add advanced feature setup instructions for authentication, multi-tenancy, and GDPR compliance in README and main.py
- Update security headers and documentation for improved defaults and clarity
- Enhance configuration and security features in environment settings and main application
- Update README to correct documentation links and improve structure
- Enhance __repr__ methods in Project and Task models to handle detached or expired states
- Update CRUD router response models to use specific read schemas and enhance repository object handling
- Update tenant CRUD endpoints to use specific response models and improve error handling
- Remove security hardening section and related middleware from main FastAPI application
- Add billing and subscription settings to configuration and enhance API index response
- Update run.sh to correctly reference the script directory for loading environment variables
- Add async Alembic migration support and CRUD endpoints for Project and Task models
- Enhance cleanup targets to remove example caches and logs
- Added template main FastAPI application and centralized settings management
- Initialize svc-infra template with essential files and configurations
- Add comprehensive documentation for admin scope and impersonation features
- Add comprehensive production readiness punch list for v1 framework release
- Add unit and acceptance tests for timeout handling and job processing
- Implement admin API with impersonation support and related tests
- Add easy integration helper `add_cache` for ASGI app lifecycle management
- Introduce billing primitives and usage aggregation
- Implement timeouts and resource limits, including middleware for body read and handler timeouts, and add acceptance tests for timeout scenarios
- Implement timeouts and resource limits middleware, including graceful shutdown and HTTP client timeout handling
- Update acceptance tests and documentation for CLI migrations, job execution, and acceptance scenarios
- Enhance acceptance tests for OpenAPI validation, maintenance mode, and circuit breaker functionality
- Add acceptance tests for data lifecycle operations including fixtures, erasure, and retention
- Implement tenancy acceptance tests with tenant-aware resource management
- Enhance acceptance tests for idempotency, concurrency, jobs, and webhooks
- Update healthcheck parameters and improve documentation command handling
- Add documentation command to retrieve and display available docs topics
- Add new subcommands for SQL, Docs, DX, Jobs, and SDK groups in svc-infra CLI
- Enhance documentation command handling with improved topic normalization and directory options
- Refactor documentation topic discovery to normalize topic names and streamline fallback mechanisms
- Enhance documentation topic discovery with improved package metadata handling and fallback to site-packages
- Implement fixed-window rate limiting for acceptance tests with header-based isolation
- Update Docker Compose to use --root-user-action=ignore for pip installs and implement header-only rate limiting middleware
- Refactor CLI command structure and update documentation for consistency


### Other Changes

- Update version in pyproject.toml and enhance documentation comm…
- Refactor caching and database setup to use async context managers

- Updated caching setup in `src/svc_infra/api/fastapi/cache/add.py` to utilize async context managers for startup and shutdown events, improving resource management.
- Refactored MongoDB setup in `src/svc_infra/api/fastapi/db/nosql/mongo/add.py` to replace deprecated event handlers with async context managers for better lifecycle management.
- Modified SQL database setup in `src/svc_infra/api/fastapi/db/sql/add.py` to adopt async context managers, ensuring proper session initialization and disposal.
- Changed root documentation visibility in `src/svc_infra/api/fastapi/setup.py` to always enable in all environments, simplifying access to API documentation.
- Remove .github/agents.md from tracking
- Remove production readiness punch list and update .gitignore to exclude documentation files
- Commit billing job mutations before closing session
- Restore env prep for docs MCP help
- Include docs in distribution
- Add comprehensive documentation for idempotency, background jobs, observability, operations, rate limiting, security, tenancy, and webhooks

- Introduced detailed guides on idempotency and concurrency controls, including middleware usage and testing strategies.
- Documented background jobs and scheduling with Redis and in-memory implementations, including CLI usage.
- Added observability guide covering Prometheus metrics and OpenTelemetry instrumentation.
- Provided insights on SLOs and operations, including probes and circuit breaker patterns.
- Explained rate limiting features, including global middleware, per-route dependencies, and request size guards.
- Compiled security configuration and examples, detailing password policies, account lockout, sessions, JWT rotation, and CORS.
- Outlined tenancy model and integration strategies for soft-tenant isolation.
- Developed a webhooks framework for event publishing, signature verification, and robust retries.
- Fix MCP subcommand help invocation for grouped commands
- Merge branch 'main' into feat/prod-readiness-v1

## [0.1.617] - 2025-10-19


### Other Changes

- Merge pull request #32 from Aliikhatami94/feat/prod-readiness-v1

Feat/prod readiness v1

## [0.1.616] - 2025-10-19


### Other Changes

- Add bundled documentation support and enhance CLI for dynamic t…

## [0.1.615] - 2025-10-19


### Other Changes

- Add documentation command group with dynamic topic subcommands …

## [0.1.614] - 2025-10-19


### Other Changes

- Add acceptance tests for rate limiting and abuse heuristics, en…

## [0.1.613] - 2025-10-18


### Features

- Update version in pyproject.toml and enhance documentation command to support packaged topics
- Refactor documentation handling and enhance rate limiting middleware for better test isolation
- Remove bundled documentation files from the project
- Add bundled documentation support and enhance CLI for dynamic topic resolution
- Add documentation command group with dynamic topic subcommands and tests
- Add acceptance tests for rate limiting and abuse heuristics, enhance error handling with headers
- Enhance acceptance tests for authentication flows, password policies, and API key lifecycle
- Add acceptance tests for RBAC/ABAC and enhance security demo routes - fixed acceptance tests


### Other Changes

- Merge pull request #28 from Aliikhatami94/feat/prod-readiness-v1

Feat/prod readiness v1
- Guard rate limit tenant fallback header
- Fix docs dir propagation for CLI subcommands

## [0.1.612] - 2025-10-18


### Features

- Update cache setup to default to in-memory backend and enhance tag resolution with template rendering

## [0.1.611] - 2025-10-18


### Features

- Enhance logging and caching functionality with comprehensive tests and documentation updates

## [0.1.610] - 2025-10-18


### Features

- Add observability metrics and acceptance tests for metrics exposure

## [0.1.609] - 2025-10-18


### Features

- Enhance CLI functionality with acceptance data seeding and comprehensive command help


### Other Changes

- Merge pull request #27 from Aliikhatami94/feat/prod-readiness-v1

Feat/prod readiness v1
- Update feat/prod-readiness-v1 with latest main

## [0.1.608] - 2025-10-18


### Bug Fixes

- Update SBOM artifact naming and paths for consistency


### Features

- Add Trivy ignore list for vendor images and update scanning conditions
- Improve acceptance testing setup and API readiness checks
- Enhance acceptance testing framework and improve CI/CD workflows


### Other Changes

- Merge pull request #26 from Aliikhatami94/feat/prod-readiness-v1

Feat/prod readiness v1
- Ensure accept target always tears down
- Merge pull request #24 from Aliikhatami94/codex/fix-failed-acceptance-tests

Make acceptance tests self-contained
- Extend acceptance stub session execute support
- Make acceptance tests self-contained

## [0.1.607] - 2025-10-18


### Features

- Implement A0 Acceptance Harness and CI Promotion Gate


### Other Changes

- Implement A0 Acceptance Harness and CI Promotion Gate

## [0.1.606] - 2025-10-17


### Other Changes

- Merge pull request #22 from Aliikhatami94/feat/prod-readiness-v1

Add unit tests for security models, session endpoints, and tenancy fe…
- Add unit tests for security models, session endpoints, and tenancy features

- Implement tests for refresh token generation, hashing, and rotation.
- Add tests for audit hash chain continuity.
- Create tests for session listing and revocation, ensuring proper access control.
- Introduce tests for session refresh rotation and revocation tracking.
- Develop tests for signed cookies, including signing, verification, and expiration.
- Add tests for tenancy helpers and context resolution.
- Implement CRUD tests for tenant-specific operations.
- Create tests for webhook functionality, including subscription handling and signature verification.
- Ensure comprehensive coverage of utility functions for testing.

## [0.1.605] - 2025-10-17


### Features

- Add comprehensive documentation for API and SDK generation


### Other Changes

- Merge pull request #21 from Aliikhatami94/feat/prod-readiness-v1

Feat/prod readiness v1
- Bug fix
- DX & Quality Gates implementation completed

## [0.1.604] - 2025-10-16


### Other Changes

- Merge pull request #20 from Aliikhatami94/feat/prod-readiness-v1

SLOs & Ops implementation done
- Prevent duplicate Prometheus middleware with custom route classifier
- SLOs & Ops implementation done

## [0.1.603] - 2025-10-16


### Other Changes

- Merge pull request #19 from Aliikhatami94/feat/prod-readiness-v1

Data Lifecycle implemented
- Preserve existing FastAPI startup handlers
- Data Lifecycle implemented

## [0.1.602] - 2025-10-16


### Other Changes

- Merge pull request #18 from Aliikhatami94/feat/prod-readiness-v1

push old commits
- Push old commits

## [0.1.601] - 2025-10-16


### Other Changes

- Per-tenant rate limits (middleware+dep), tenant export CLI, …
- Handle async engines in tenant export CLI
- Per-tenant rate limits (middleware+dep), tenant export CLI, tenancy marker+docs; wire tenant CRUD; fix SqlRepository.delete fast path; update PLANS

## [0.1.600] - 2025-10-16


### Other Changes

- Bug fix

## [0.1.599] - 2025-10-15


### Documentation

- Refresh readme and helper guides
- Add environment variable reference


### Other Changes

- Merge pull request #16 from Aliikhatami94/feat/prod-readiness-v1

Feat/prod readiness v1
- Fix CORS allow_origins for wildcard configuration
- Merge pull request #15 from Aliikhatami94/codex/audit-and-document-environment-variables

Add environment variable reference documentation
- Merge branch 'feat/prod-readiness-v1' into codex/audit-and-document-environment-variables
- Merge pull request #14 from Aliikhatami94/codex/update-readme-with-project-overview-and-examples

Refresh README with helper overview and docs index
- Merge pull request #13 from Aliikhatami94/codex/add-security-middleware-installation

Add security helper for FastAPI apps
- Add reusable security helper with CORS and session options
- Merge pull request #12 from Aliikhatami94/codex/create-add_webhooks-function-and-documentation

Add FastAPI helper for webhooks integration
- Defer FastAPI import for webhooks helper
- Add FastAPI helper for webhooks integration
- Merge pull request #11 from Aliikhatami94/codex/review-svc-infra-setup-for-consistency-and-flexibility

Add repo integration review documentation
- Add integration review summary

## [0.1.598] - 2025-10-15


### Other Changes

- Merge pull request #10 from Aliikhatami94/feat/prod-readiness-v1

Added Background Jobs & Scheduling
- Include subscription metadata in webhook outbox payloads
- Added Background Jobs & Scheduling

## [0.1.597] - 2025-10-15


### Other Changes

- Merge pull request #9 from Aliikhatami94/feat/prod-readiness-v1

Background Jobs & Scheduling
- Restore timed out Redis jobs to ready queue
- Background Jobs & Scheduling

## [0.1.596] - 2025-10-15


### Other Changes

- Merge pull request #8 from Aliikhatami94/feat/prod-readiness-v1
- Added Idempotency & Concurrency Controls

## [0.1.595] - 2025-10-15


### Other Changes

- Merge pull request #7 from Aliikhatami94/feat/prod-readiness-v1

Feat/prod readiness v1
- Added docs to security and ratelimits
- Merge pull request #2 from Aliikhatami94/codex/update-oauth-callback-to-return-redirectresponse

Ensure OAuth callback returns redirect response
- Merge branch 'feat/prod-readiness-v1' into codex/update-oauth-callback-to-return-redirectresponse
- Fix OAuth callback response and add test
- Merge pull request #5 from Aliikhatami94/codex/modify-session-refresh-logic

Reject reuse of rotated refresh tokens
- Handle rotation failures in refresh endpoint
- Guard refresh rotation against revoked tokens
- Merge pull request #4 from Aliikhatami94/codex/replace-hard-coded-tenant_id-in-get_service

Improve payments tenant resolution coverage
- Improve payments tenant resolution coverage
- Merge pull request #3 from Aliikhatami94/codex/reposition-return-statement-in-oauth_router.py

Add targeted OAuth refresh hook tests
- Add dedicated OAuth refresh hook tests

## [0.1.594] - 2025-10-15


### Features

- Enhance security features and implement rate limiting
- Implement rotating JWT strategy with support for old secrets and update related tests
- Consolidate security hardening (password policy, lockout, refresh rotation, RBAC, audit chain) and planning docs


### Miscellaneous

- Fix flake8 E101 by normalizing docstring indentation


### Other Changes

- Merge pull request #6 from Aliikhatami94/feat/prod-readiness-v1

Feat/prod readiness v1
- Fix OAuth callback to return redirect response
- Updated plan and added more implementations

## [0.1.593] - 2025-10-14


### Other Changes

- Added Ayden as another porvider for payment systems

## [0.1.592] - 2025-10-14


### Other Changes

- Configured github copilot actions

## [0.1.591] - 2025-10-14


### Bug Fixes

- Fixed test warnings

## [0.1.590] - 2025-10-14


### Other Changes

- Full test code coverage

## [0.1.589] - 2025-10-13


### Other Changes

- Moved payments conftest to payments

## [0.1.588] - 2025-10-13


### Other Changes

- Added payment test cases

## [0.1.587] - 2025-10-13


### Other Changes

- Expanded stripe functionalities

## [0.1.586] - 2025-10-13


### Other Changes

- Changed security levels for some of the payment endpoints

## [0.1.585] - 2025-10-13


### Other Changes

- Removed dupe tags

## [0.1.584] - 2025-10-13


### Other Changes

- Removed dupe tags

## [0.1.583] - 2025-10-13


### Other Changes

- Added tags

## [0.1.582] - 2025-10-13


### Other Changes

- Removed deprecated endpoint

## [0.1.581] - 2025-10-13


### Other Changes

- Updated delete functionalities

## [0.1.580] - 2025-10-13


### Other Changes

- Added more prod ready payment functionalities

## [0.1.579] - 2025-10-13


### Other Changes

- Updated openapi issues

## [0.1.578] - 2025-10-13


### Other Changes

- Updated openapi issues

## [0.1.577] - 2025-10-13


### Other Changes

- Added p0 functionalities for payments

## [0.1.576] - 2025-10-13


### Other Changes

- Bug fix

## [0.1.575] - 2025-10-13


### Other Changes

- Extended payment services

## [0.1.574] - 2025-10-12


### Other Changes

- Mutator bug fix

## [0.1.573] - 2025-10-12


### Other Changes

- Bug fix

## [0.1.572] - 2025-10-12


### Other Changes

- Bug fix

## [0.1.571] - 2025-10-12


### Other Changes

- Bug fix

## [0.1.570] - 2025-10-12


### Bug Fixes

- Fixing idempotency in mutators

## [0.1.569] - 2025-10-12


### Other Changes

- Expnaded idempotency to fix dupe bugs

## [0.1.568] - 2025-10-12


### Other Changes

- Bug fix

## [0.1.567] - 2025-10-12


### Other Changes

- Added idempotency to payment funcs

## [0.1.566] - 2025-10-12


### Other Changes

- Updated created from 200 to 201

## [0.1.565] - 2025-10-12


### Other Changes

- Enhanced pagination overall and for payments pagination

## [0.1.564] - 2025-10-12


### Other Changes

- Added capture, list intents, invoice line items, usage records etc

## [0.1.563] - 2025-10-12


### Other Changes

- Updated mutators

## [0.1.562] - 2025-10-11


### Other Changes

- Routers updated for payments with pagination and correct schema

## [0.1.561] - 2025-10-10


### Other Changes

- Bug fix

## [0.1.560] - 2025-10-10


### Other Changes

- Bug fix

## [0.1.559] - 2025-10-10


### Bug Fixes

- Fixing env issues

## [0.1.558] - 2025-10-10


### Other Changes

- Expanded envs

## [0.1.557] - 2025-10-10


### Other Changes

- Added more payment functionalities

## [0.1.556] - 2025-10-10


### Documentation

- Doc clean ups

## [0.1.555] - 2025-10-09


### Documentation

- Doc setup fix

## [0.1.554] - 2025-10-09


### Bug Fixes

- Fixing docs auth issues

## [0.1.553] - 2025-10-09


### Other Changes

- Bug fix

## [0.1.552] - 2025-10-09


### Other Changes

- Limiting non local envs

## [0.1.551] - 2025-10-09


### Other Changes

- Clean ups

## [0.1.550] - 2025-10-09


### Other Changes

- Clean ups

## [0.1.549] - 2025-10-09


### Other Changes

- Merging auth and oauth

## [0.1.548] - 2025-10-09


### Other Changes

- Adding users docs as well

## [0.1.547] - 2025-10-09


### Other Changes

- Bug fix for docs

## [0.1.546] - 2025-10-09


### Other Changes

- Bug fix for docs

## [0.1.545] - 2025-10-09


### Other Changes

- Bug fix

## [0.1.544] - 2025-10-09


### Other Changes

- Changing scope of docs to more organized place

## [0.1.543] - 2025-10-09


### Other Changes

- Reverted back to original gh workflow
- Updated gh action
- Updated gh action
- Gh action issue
- Updated payments apf

## [0.1.541] - 2025-10-09


### Other Changes

- Env payment enablement fix

## [0.1.540] - 2025-10-09


### Other Changes

- Fk bug fix

## [0.1.539] - 2025-10-09


### Other Changes

- Wiring up payments tables to users

## [0.1.538] - 2025-10-09


### Other Changes

- Attached payments models to users

## [0.1.537] - 2025-10-08


### Other Changes

- Updated payments models to sqlalchemy

## [0.1.536] - 2025-10-08


### Other Changes

- Env import migration fix

## [0.1.535] - 2025-10-08


### Other Changes

- Env import migration fix

## [0.1.534] - 2025-10-08


### Other Changes

- Updated env tmpls for migrations fix

## [0.1.533] - 2025-10-08


### Other Changes

- Updated env tmpls for migrations

## [0.1.532] - 2025-10-08


### Other Changes

- Updated env tmpls for migrations

## [0.1.531] - 2025-10-08


### Other Changes

- Updated env tmpls for migrations

## [0.1.530] - 2025-10-08


### Other Changes

- Updated env tmpls for migrations

## [0.1.529] - 2025-10-08


### Other Changes

- Brought back ModelBase discovery to migrations

## [0.1.528] - 2025-10-08


### Other Changes

- Updated envs for sync and async to align for alembic push of apf payments

## [0.1.527] - 2025-10-07


### Other Changes

- Adding apf payments

## [0.1.526] - 2025-10-04


### Other Changes

- Bug fixes

## [0.1.525] - 2025-10-04


### Other Changes

- Bug fixes

## [0.1.524] - 2025-10-04


### Other Changes

- Bug fixes

## [0.1.523] - 2025-10-04


### Other Changes

- Added nice to haves to our fastapi service

## [0.1.522] - 2025-10-04


### Other Changes

- Bug fix

## [0.1.521] - 2025-10-04


### Other Changes

- Bug fix

## [0.1.520] - 2025-10-04


### Other Changes

- Added more pagination helpers

## [0.1.519] - 2025-10-04


### Other Changes

- Bug fix

## [0.1.518] - 2025-10-03


### Other Changes

- Bug fix

## [0.1.517] - 2025-10-03


### Other Changes

- Bug fix

## [0.1.516] - 2025-10-03


### Other Changes

- Bug fix

## [0.1.515] - 2025-10-03


### Other Changes

- Bug fix

## [0.1.514] - 2025-10-03


### Other Changes

- Added pagination funcs into listings

## [0.1.513] - 2025-10-03


### Other Changes

- More clean ups

## [0.1.512] - 2025-10-03


### Other Changes

- Cleaned up mutators

## [0.1.511] - 2025-10-03


### Other Changes

- Clean ups

## [0.1.510] - 2025-10-03


### Other Changes

- Clean ups

## [0.1.509] - 2025-10-03


### Other Changes

- Clean ups

## [0.1.508] - 2025-10-03


### Other Changes

- Clean ups

## [0.1.507] - 2025-10-03


### Other Changes

- Clean ups

## [0.1.506] - 2025-10-03


### Other Changes

- Cleaned up schema

## [0.1.505] - 2025-10-02


### Other Changes

- Cleaned up auth paths and tags

## [0.1.504] - 2025-10-02


### Other Changes

- Cleaned up auth paths and tags

## [0.1.503] - 2025-10-02


### Other Changes

- Cleaned up auth paths and tags

## [0.1.502] - 2025-10-01


### Other Changes

- Updated login routes

## [0.1.501] - 2025-10-01


### Other Changes

- Bug fix

## [0.1.500] - 2025-10-01


### Other Changes

- Added new mutators

## [0.1.499] - 2025-10-01


### Other Changes

- Cleaning routes

## [0.1.498] - 2025-10-01


### Other Changes

- Cleaning routes

## [0.1.497] - 2025-09-30


### Other Changes

- Bug fix

## [0.1.496] - 2025-09-30


### Other Changes

- Bug fix

## [0.1.495] - 2025-09-30


### Bug Fixes

- Fixing dupe and path issues

## [0.1.494] - 2025-09-30


### Testing

- Testing

## [0.1.493] - 2025-09-30


### Testing

- Testing

## [0.1.492] - 2025-09-30


### Testing

- Testing

## [0.1.491] - 2025-09-30


### Other Changes

- Bug fix

## [0.1.490] - 2025-09-30


### Other Changes

- Bug fix

## [0.1.489] - 2025-09-30


### Other Changes

- Bug fix

## [0.1.488] - 2025-09-30


### Other Changes

- Bug fix

## [0.1.487] - 2025-09-30


### Other Changes

- Bug fix

## [0.1.486] - 2025-09-30


### Other Changes

- Bug fix

## [0.1.485] - 2025-09-30


### Other Changes

- Mfa bug fix

## [0.1.484] - 2025-09-30


### Other Changes

- Mfa bug fix

## [0.1.483] - 2025-09-30


### Other Changes

- Cleanups

## [0.1.482] - 2025-09-30


### Other Changes

- Cleanups

## [0.1.481] - 2025-09-30


### Other Changes

- Cleanups

## [0.1.480] - 2025-09-30


### Other Changes

- Cleanups

## [0.1.479] - 2025-09-30


### Other Changes

- Cleanups

## [0.1.478] - 2025-09-30


### Other Changes

- Expanded mutators and added descriptions

## [0.1.477] - 2025-09-30


### Other Changes

- Expanded mutators and added descriptions

## [0.1.476] - 2025-09-30


### Other Changes

- Expanded mutators

## [0.1.475] - 2025-09-30


### Other Changes

- Expanded mutators

## [0.1.474] - 2025-09-30


### Refactor

- Refactored mutators

## [0.1.473] - 2025-09-29


### Other Changes

- Adding apikey enablement abilities to root like child

## [0.1.472] - 2025-09-29


### Other Changes

- Expanded mutators to parent and child

## [0.1.471] - 2025-09-29


### Other Changes

- Recactored code

## [0.1.470] - 2025-09-29


### Other Changes

- Bug fix prior unification

## [0.1.469] - 2025-09-29


### Other Changes

- Bug fix

## [0.1.468] - 2025-09-29


### Other Changes

- Bug fix

## [0.1.467] - 2025-09-29


### Other Changes

- Bug fix

## [0.1.466] - 2025-09-29


### Other Changes

- Bug fix

## [0.1.465] - 2025-09-28


### Other Changes

- Reverting

## [0.1.464] - 2025-09-28


### Other Changes

- Bug fix

## [0.1.463] - 2025-09-28


### Other Changes

- Bug fix

## [0.1.462] - 2025-09-28


### Other Changes

- Response and error enhancements

## [0.1.461] - 2025-09-28


### Other Changes

- Bug fix

## [0.1.460] - 2025-09-28


### Other Changes

- Enhancing responses and errors

## [0.1.459] - 2025-09-28


### Other Changes

- Enhancing responses and errors

## [0.1.458] - 2025-09-28


### Other Changes

- Enhancing responses and errors

## [0.1.457] - 2025-09-28


### Other Changes

- Prior standardizing erros responses openapi etc

## [0.1.456] - 2025-09-28


### Other Changes

- Bug fix openapis

## [0.1.455] - 2025-09-28


### Other Changes

- Bug fix openapis

## [0.1.454] - 2025-09-28


### Other Changes

- Removed extra logout endpoint

## [0.1.453] - 2025-09-28


### Other Changes

- Auth bug fix attempt

## [0.1.452] - 2025-09-28


### Other Changes

- Enhanced openapi security and auth

## [0.1.451] - 2025-09-28


### Other Changes

- Enhanced openapi security and auth

## [0.1.450] - 2025-09-28


### Other Changes

- Updated imports

## [0.1.449] - 2025-09-28


### Other Changes

- Updated imports

## [0.1.448] - 2025-09-28


### Other Changes

- Bug fix

## [0.1.447] - 2025-09-28


### Other Changes

- Enhanced account endpoints and mfa

## [0.1.446] - 2025-09-27


### Other Changes

- Expanded dx

## [0.1.445] - 2025-09-27


### Other Changes

- Bug fix

## [0.1.444] - 2025-09-27


### Other Changes

- Added dx for best dev exp

## [0.1.443] - 2025-09-27


### Other Changes

- Simplified routers and principals

## [0.1.442] - 2025-09-27


### Other Changes

- Prior to simplifying the routers and principals

## [0.1.441] - 2025-09-27


### Other Changes

- Added hard delete funcs to apikeys

## [0.1.440] - 2025-09-27


### Bug Fixes

- Fixing apikey auth issues

## [0.1.439] - 2025-09-27


### Bug Fixes

- Fixing auth issues

## [0.1.438] - 2025-09-27


### Other Changes

- Import bug fix

## [0.1.437] - 2025-09-27


### Other Changes

- Import bug fix

## [0.1.436] - 2025-09-27


### Other Changes

- Import bug fix

## [0.1.435] - 2025-09-27


### Other Changes

- Import bug fix

## [0.1.434] - 2025-09-27


### Other Changes

- Import bug fix

## [0.1.433] - 2025-09-27


### Other Changes

- Bug fix

## [0.1.432] - 2025-09-27


### Other Changes

- Bug fix

## [0.1.431] - 2025-09-27


### Other Changes

- Bug fix

## [0.1.430] - 2025-09-27


### Other Changes

- Bug fix

## [0.1.429] - 2025-09-27


### Other Changes

- Bug fix

## [0.1.428] - 2025-09-27


### Other Changes

- Expanded dualizing existing routers in auth as well as public

## [0.1.427] - 2025-09-27


### Bug Fixes

- Fixing auth issues further

## [0.1.426] - 2025-09-27


### Bug Fixes

- Fixing auth issues

## [0.1.425] - 2025-09-27


### Other Changes

- Reverted
- Reverted

## [0.1.421] - 2025-09-27


### Bug Fixes

- Fixing openapi issue

## [0.1.420] - 2025-09-26


### Other Changes

- Bug fix

## [0.1.419] - 2025-09-26


### Other Changes

- Ton of updates from integating auth to all endpoints when needed as well as including reusable routers etc

## [0.1.418] - 2025-09-26


### Other Changes

- Bug fix

## [0.1.417] - 2025-09-26


### Other Changes

- Bug fix

## [0.1.416] - 2025-09-26


### Other Changes

- Generalizing apikeys  model for migration and inclusion

## [0.1.415] - 2025-09-26


### Other Changes

- Enhanced ownership of apikeys

## [0.1.414] - 2025-09-26


### Other Changes

- Enhanced ownership of apikeys

## [0.1.413] - 2025-09-26


### Other Changes

- Added apikey capabilities

## [0.1.412] - 2025-09-26


### Other Changes

- Added apikey capabilities

## [0.1.411] - 2025-09-26


### Other Changes

- Quick auth fix

## [0.1.410] - 2025-09-26


### Other Changes

- Bug fix

## [0.1.409] - 2025-09-26


### Other Changes

- Cleanups

## [0.1.408] - 2025-09-26


### Other Changes

- Login records

## [0.1.407] - 2025-09-26


### Other Changes

- Added account mgmt funcs like disable and delete

## [0.1.406] - 2025-09-26


### Other Changes

- Bug fix

## [0.1.405] - 2025-09-26


### Other Changes

- Bug fix

## [0.1.404] - 2025-09-26


### Other Changes

- Added email totp functionality

## [0.1.403] - 2025-09-26


### Other Changes

- Mfa verification bug fix

## [0.1.402] - 2025-09-26


### Other Changes

- Mfa verification bug fix

## [0.1.401] - 2025-09-26


### Other Changes

- Mfa bug fix

## [0.1.400] - 2025-09-26


### Other Changes

- Mfa bug fix

## [0.1.399] - 2025-09-26


### Other Changes

- Making mfa accept cookies as well

## [0.1.398] - 2025-09-26


### Other Changes

- Making mfa accept cookies as well

## [0.1.397] - 2025-09-26


### Other Changes

- Making mfa accept cookies as well

## [0.1.396] - 2025-09-26


### Other Changes

- Mfa bug fix

## [0.1.395] - 2025-09-26


### Other Changes

- Bug fix

## [0.1.394] - 2025-09-26


### Other Changes

- Bug fix

## [0.1.393] - 2025-09-26


### Refactor

- Refactored auth code

## [0.1.392] - 2025-09-25


### Other Changes

- Added mfa policy

## [0.1.391] - 2025-09-25


### Other Changes

- Bug fix

## [0.1.390] - 2025-09-25


### Other Changes

- Added mfa to oauth functionalities totp

## [0.1.389] - 2025-09-25


### Other Changes

- Added mfa to auth functionalities totp

## [0.1.388] - 2025-09-25


### Refactor

- Refactored code and added ability for openapi description and summary

## [0.1.387] - 2025-09-25


### Other Changes

- Added password reset functionalities

## [0.1.386] - 2025-09-25


### Bug Fixes

- Fixing auth register issues

## [0.1.385] - 2025-09-25


### Bug Fixes

- Fixing docs issues

## [0.1.384] - 2025-09-25


### Bug Fixes

- Fixing docs issues

## [0.1.383] - 2025-09-25


### Other Changes

- Added email verification functionalities

## [0.1.382] - 2025-09-25


### Other Changes

- Future proof for client users

## [0.1.381] - 2025-09-25


### Bug Fixes

- Fixing jwt login path

## [0.1.380] - 2025-09-25


### Other Changes

- Updated auth schemas to align with fastapi-users

## [0.1.379] - 2025-09-25


### Other Changes

- Updated auth prefix

## [0.1.378] - 2025-09-25


### Other Changes

- Adding sign up funcs through app

## [0.1.377] - 2025-09-25


### Other Changes

- Import issue fix

## [0.1.376] - 2025-09-25


### Other Changes

- Import issue fix

## [0.1.375] - 2025-09-25


### Other Changes

- Import issue fix

## [0.1.374] - 2025-09-24


### Other Changes

- Import issue fix

## [0.1.373] - 2025-09-24


### Other Changes

- Import issue fix

## [0.1.372] - 2025-09-24


### Other Changes

- Import issue fix

## [0.1.371] - 2025-09-24


### Other Changes

- Import issue fix

## [0.1.370] - 2025-09-24


### Other Changes

- Import issue fix

## [0.1.369] - 2025-09-24


### Other Changes

- Import issue fix

## [0.1.368] - 2025-09-24


### Other Changes

- Import issue fix

## [0.1.367] - 2025-09-24


### Other Changes

- Import issue fix

## [0.1.366] - 2025-09-24


### Other Changes

- Complemented auth routers to simple reusable functions

## [0.1.365] - 2025-09-24


### Other Changes

- Refresh bug fix auth

## [0.1.364] - 2025-09-24


### Other Changes

- Refresh bug fix auth

## [0.1.363] - 2025-09-24


### Other Changes

- Cookie storage bug fix

## [0.1.362] - 2025-09-24


### Other Changes

- Cookie storage bug fix

## [0.1.361] - 2025-09-24


### Other Changes

- Bug fix

## [0.1.360] - 2025-09-24


### Other Changes

- Bug fix for cookie token refresh

## [0.1.359] - 2025-09-24


### Other Changes

- Added refresh functionalities

## [0.1.358] - 2025-09-24


### Other Changes

- Added bug fix for timezones

## [0.1.357] - 2025-09-24


### Other Changes

- Added bug fix for timezones

## [0.1.356] - 2025-09-23


### Other Changes

- Added provider account model

## [0.1.355] - 2025-09-23


### Other Changes

- Enhanced auth setup tmpls and oauth routers login/logout

## [0.1.354] - 2025-09-23


### Other Changes

- Enhanced auth setup tmpls and oauth routers login/logout

## [0.1.353] - 2025-09-23


### Other Changes

- Bug fix for github oauth async issues

## [0.1.352] - 2025-09-23


### Other Changes

- Bug fix

## [0.1.351] - 2025-09-23


### Other Changes

- Bug fix

## [0.1.350] - 2025-09-23


### Other Changes

- Updated callback piece of oauth

## [0.1.349] - 2025-09-23


### Other Changes

- Re-running
- Bug fix

## [0.1.348] - 2025-09-23


### Other Changes

- Bug fix

## [0.1.347] - 2025-09-23


### Other Changes

- Updated by adding isdangerous

## [0.1.346] - 2025-09-23


### Other Changes

- Updated oauth router to accept either or both password and provider oauth

## [0.1.345] - 2025-09-23


### Other Changes

- Updated models tmpl for auth

## [0.1.344] - 2025-09-23


### Other Changes

- Bug fix for auth

## [0.1.343] - 2025-09-23


### Other Changes

- Bug fix for auth

## [0.1.342] - 2025-09-23


### Other Changes

- Shipping and testing oauth funcs

## [0.1.341] - 2025-09-23


### Other Changes

- Removed caching cli funcs
- Mcp bug fix
- Resolving mcp issues and wrong old imports
- Removed uncessary imports from cache __init__
- Added readme alongside simpler demo


### Refactor

- Refactored cache code for more readability

## [0.1.335] - 2025-09-22


### Other Changes

- Solid caching funcs

## [0.1.334] - 2025-09-22


### Other Changes

- Working demo w/ prod ready caching - needs clean up

## [0.1.333] - 2025-09-20


### Other Changes

- Enhanced caching

## [0.1.332] - 2025-09-20


### Other Changes

- Enhanced caching

## [0.1.331] - 2025-09-20


### Other Changes

- Prior enhancing caching

## [0.1.330] - 2025-09-19


### Other Changes

- Updated caching

## [0.1.329] - 2025-09-19


### Other Changes

- Moved intervals to 5s

## [0.1.328] - 2025-09-19


### Other Changes

- Removed logs from grafana

## [0.1.327] - 2025-09-19


### Refactor

- Refactoring

## [0.1.326] - 2025-09-19


### Other Changes

- Bug fix

## [0.1.325] - 2025-09-19


### Other Changes

- Bug fix

## [0.1.324] - 2025-09-19


### Other Changes

- Bug fix

## [0.1.323] - 2025-09-19


### Other Changes

- Added logs to grafana obs

## [0.1.322] - 2025-09-19


### Other Changes

- Added logs to grafana obs

## [0.1.321] - 2025-09-19


### Other Changes

- Added env derived easy app/api setup

## [0.1.320] - 2025-09-19


### Other Changes

- Updated easy app/api setup

## [0.1.319] - 2025-09-19


### Other Changes

- Enhanced landing page of apis

## [0.1.318] - 2025-09-19


### Other Changes

- Enhanced landing page of apis

## [0.1.317] - 2025-09-19


### Other Changes

- Api doc landing page ui clean up

## [0.1.316] - 2025-09-19


### Other Changes

- Api doc landing page ui clean up

## [0.1.315] - 2025-09-19


### Other Changes

- Api doc landing page ui clean up

## [0.1.314] - 2025-09-19


### Other Changes

- Api doc landing page ui clean up

## [0.1.313] - 2025-09-19


### Other Changes

- Cleaned up api docs landing page ui

## [0.1.312] - 2025-09-19


### Other Changes

- Optionally adds /metrics to schema on local and dev

## [0.1.311] - 2025-09-18


### Other Changes

- Added sugar quick/easy app/api setup

## [0.1.310] - 2025-09-18


### Other Changes

- Quick title fix

## [0.1.309] - 2025-09-18


### Other Changes

- Bug fix

## [0.1.308] - 2025-09-18


### Other Changes

- Changed the structure of setup_fastapi to set ping at the root

## [0.1.307] - 2025-09-18


### Other Changes

- Added global envs for convenience

## [0.1.306] - 2025-09-18


### Other Changes

- Added global envs for convenience

## [0.1.305] - 2025-09-17


### Other Changes

- Updated app imports for bug fix

## [0.1.304] - 2025-09-17


### Other Changes

- Added filtering ability to logging + readme

## [0.1.303] - 2025-09-17


### Other Changes

- Expanded on obs readme

## [0.1.302] - 2025-09-17


### Other Changes

- Added obs intervals to envs

## [0.1.301] - 2025-09-17


### Bug Fixes

- Fixing rps issues in grafana

## [0.1.300] - 2025-09-17


### Bug Fixes

- Fixing rps issues in grafana

## [0.1.299] - 2025-09-17


### Bug Fixes

- Fixing rps issues in grafana

## [0.1.298] - 2025-09-17


### Other Changes

- Added readme for observability

## [0.1.297] - 2025-09-17


### Other Changes

- Changed scrape interval from  5s to 60s

## [0.1.296] - 2025-09-17


### Other Changes

- Removed hardcoded tmpls

## [0.1.295] - 2025-09-16


### Other Changes

- Bug fix for obs local to grafana cloud

## [0.1.294] - 2025-09-16


### Other Changes

- Bug fix for obs local to grafana cloud

## [0.1.293] - 2025-09-16


### Other Changes

- Bug fix obs cmds

## [0.1.292] - 2025-09-16


### Other Changes

- Port bug fix for local obs

## [0.1.291] - 2025-09-16


### Other Changes

- Updated grafana to handle all situations

## [0.1.290] - 2025-09-16


### Other Changes

- Working to enable grafana cloud

## [0.1.289] - 2025-09-16


### Other Changes

- Removed uptrace

## [0.1.288] - 2025-09-16


### Other Changes

- Tracing import bug fix

## [0.1.287] - 2025-09-15


### Other Changes

- Tracing import bug fix

## [0.1.286] - 2025-09-15


### Other Changes

- Removed imports from add.py of observability

## [0.1.285] - 2025-09-15


### Other Changes

- Mcp bug fix

## [0.1.284] - 2025-09-15


### Other Changes

- Updated svc-infra commands subcommand guide

## [0.1.283] - 2025-09-15


### Documentation

- Docker compose obs uptace update

## [0.1.282] - 2025-09-15


### Other Changes

- Added uptrace to svc-infra clis

## [0.1.281] - 2025-09-15


### Other Changes

- Added uptrace to obs funx

## [0.1.280] - 2025-09-15


### Other Changes

- Quick fixes

## [0.1.279] - 2025-09-15


### Other Changes

- Bug fix

## [0.1.278] - 2025-09-15


### Other Changes

- Bug fix

## [0.1.277] - 2025-09-15


### Other Changes

- Bug fix

## [0.1.276] - 2025-09-15


### Other Changes

- Bug fix

## [0.1.275] - 2025-09-15


### Other Changes

- Bug fix

## [0.1.274] - 2025-09-15


### Other Changes

- Bug fix

## [0.1.273] - 2025-09-15


### Other Changes

- Bug fix

## [0.1.272] - 2025-09-15


### Other Changes

- Updated all apirouters to dual routers

## [0.1.271] - 2025-09-14


### Other Changes

- Updated fastapi integration

## [0.1.270] - 2025-09-14


### Other Changes

- Added clis for cache doc, ping, setup etc

## [0.1.269] - 2025-09-14


### Other Changes

- Prior building cli and scaffolding for caching

## [0.1.268] - 2025-09-14


### Refactor

- Refactoring code to where it would make sense

## [0.1.267] - 2025-09-14


### Other Changes

- Added dualrouter to ping as well

## [0.1.266] - 2025-09-14


### Other Changes

- Removing double trails from docs by adding dualrouters

## [0.1.265] - 2025-09-14


### Other Changes

- Enabling schemas for all endpoints and app versions in local env

## [0.1.264] - 2025-09-14


### Other Changes

- Cleanups

## [0.1.263] - 2025-09-14


### Other Changes

- Sql bug fix

## [0.1.262] - 2025-09-14


### Other Changes

- Sql bug fix

## [0.1.261] - 2025-09-14


### Other Changes

- Sql bug fix

## [0.1.260] - 2025-09-14


### Other Changes

- Sql bug fix

## [0.1.259] - 2025-09-14


### Other Changes

- Import fix

## [0.1.258] - 2025-09-14


### Other Changes

- Added wrapper for full setup of sql db

## [0.1.257] - 2025-09-13


### Other Changes

- Added readme for mongo integrations and setup

## [0.1.256] - 2025-09-13


### Other Changes

- Mongodb setup functionalities are ready

## [0.1.255] - 2025-09-13


### Other Changes

- Bug fix when schemas are not passed

## [0.1.254] - 2025-09-13


### Other Changes

- Updated schemas for mongo nosql

## [0.1.253] - 2025-09-13


### Other Changes

- Updated schemas for mongo nosql

## [0.1.252] - 2025-09-13


### Other Changes

- Bug fix of mongo

## [0.1.251] - 2025-09-13


### Other Changes

- Bug fix of mongo

## [0.1.250] - 2025-09-13


### Other Changes

- Combining managements and added crud_schemas

## [0.1.249] - 2025-09-13


### Other Changes

- Bug fix

## [0.1.248] - 2025-09-13


### Other Changes

- Bug fix

## [0.1.247] - 2025-09-13


### Other Changes

- Updated mongo cli cmds

## [0.1.246] - 2025-09-13


### Other Changes

- Reverting to full nosql for mongodb

## [0.1.245] - 2025-09-12


### Other Changes

- Reverting to full nosql for mongodb

## [0.1.244] - 2025-09-12


### Other Changes

- Moved get db to next get db

## [0.1.243] - 2025-09-12


### Other Changes

- Curd router bug fix in mongo nosql

## [0.1.242] - 2025-09-12


### Other Changes

- Curd router bug fix in mongo nosql

## [0.1.241] - 2025-09-12


### Other Changes

- Curd router bug fix in mongo nosql

## [0.1.240] - 2025-09-12


### Other Changes

- Adding nosql validation pre flight

## [0.1.239] - 2025-09-12


### Other Changes

- Adding nosql validation pre flight

## [0.1.238] - 2025-09-12


### Other Changes

- Adding nosql validation pre flight

## [0.1.237] - 2025-09-11


### Other Changes

- Collection naming bug fix

## [0.1.236] - 2025-09-11


### Other Changes

- Nosqlresource bug fix

## [0.1.235] - 2025-09-11


### Other Changes

- Converting db to sql for all sql related

## [0.1.234] - 2025-09-11


### Other Changes

- Bug fix

## [0.1.233] - 2025-09-11


### Other Changes

- Bug fix

## [0.1.232] - 2025-09-11


### Other Changes

- Bug fix

## [0.1.231] - 2025-09-11


### Other Changes

- Bug fix

## [0.1.230] - 2025-09-11


### Other Changes

- Bug fix

## [0.1.229] - 2025-09-11


### Other Changes

- Added scaffold resources cmd for mongo nosql

## [0.1.228] - 2025-09-11


### Other Changes

- Added mongo clis

## [0.1.227] - 2025-09-11


### Other Changes

- Added db setup functionalities for nosql

## [0.1.226] - 2025-09-11


### Other Changes

- Added db setup functionalities for nosql

## [0.1.225] - 2025-09-11


### Other Changes

- Mongodb bug fix

## [0.1.224] - 2025-09-11


### Other Changes

- Working to add nosql and aligning with sql fxns

## [0.1.223] - 2025-09-10


### Other Changes

- Updating imports

## [0.1.222] - 2025-09-10


### Other Changes

- Removed readme for now
- Added precommits
- Added precommits

## [0.1.220] - 2025-09-10


### Other Changes

- Added precommits

## [0.1.219] - 2025-09-10


### Other Changes

- Added precommits

## [0.1.218] - 2025-09-10


### Other Changes

- Singled out sql separated from nosql/mongodb

## [0.1.217] - 2025-09-10


### Other Changes

- Separating sql and nosql

## [0.1.216] - 2025-09-10


### Other Changes

- Prior mongo nosql setup

## [0.1.215] - 2025-09-10


### Other Changes

- Moved all db setups under relational dir

## [0.1.214] - 2025-09-10


### Other Changes

- Bug fix

## [0.1.213] - 2025-09-10


### Other Changes

- Enhanced tmpls for non pg db setups

## [0.1.212] - 2025-09-10


### Other Changes

- Updated the templates to align for any dbs

## [0.1.211] - 2025-09-10


### Other Changes

- Obs tmpl clean up

## [0.1.210] - 2025-09-10


### Other Changes

- Bug fix of obs

## [0.1.209] - 2025-09-10


### Other Changes

- Expanding obs in grafana

## [0.1.208] - 2025-09-10


### Other Changes

- Enhancing obs-dashboard view

## [0.1.207] - 2025-09-10


### Other Changes

- Enhancing obs-dashboard view

## [0.1.206] - 2025-09-10


### Bug Fixes

- Fixing obs-up issues

## [0.1.205] - 2025-09-09


### Other Changes

- Autosetup obs with docker or native to svc-infra

## [0.1.204] - 2025-09-09


### Other Changes

- Autosetup obs with docker or native to svc-infra

## [0.1.203] - 2025-09-09


### Other Changes

- Adding tmpl for grafana dashboard

## [0.1.202] - 2025-09-09


### Other Changes

- Adding ready to go obs dashboard

## [0.1.201] - 2025-09-09


### Bug Fixes

- Fixing obs issues

## [0.1.200] - 2025-09-09


### Other Changes

- Adding flexibility to auth type tmpls for naming

## [0.1.199] - 2025-09-09


### Other Changes

- Entity tmpl clean up to align with names

## [0.1.198] - 2025-09-09


### Other Changes

- Tmpl bug fix

## [0.1.197] - 2025-09-09


### Other Changes

- Tmpl bug fix

## [0.1.196] - 2025-09-09


### Other Changes

- Tmpl bug fix

## [0.1.195] - 2025-09-09


### Other Changes

- Tmpl bug fix

## [0.1.194] - 2025-09-09


### Other Changes

- Tmpl bug fix

## [0.1.193] - 2025-09-09


### Other Changes

- Updated entity models tmpl

## [0.1.192] - 2025-09-09


### Other Changes

- Adding user service to tmpl

## [0.1.191] - 2025-09-09


### Other Changes

- Passing pre hooks to tmpls

## [0.1.190] - 2025-09-09


### Other Changes

- Generalizing dedupe

## [0.1.189] - 2025-09-09


### Other Changes

- Generalizing dedupe

## [0.1.188] - 2025-09-09


### Other Changes

- Generalizing dedupes

## [0.1.187] - 2025-09-08


### Other Changes

- Enhancing uniquness for db creation and update with better error handling

## [0.1.186] - 2025-09-08


### Other Changes

- Bug fix

## [0.1.185] - 2025-09-08


### Other Changes

- Bug fix

## [0.1.184] - 2025-09-08


### Other Changes

- Enhancing dupe checks

## [0.1.183] - 2025-09-08


### Other Changes

- Enhancing dupe checks

## [0.1.182] - 2025-09-08


### Other Changes

- Dupe validation for users

## [0.1.181] - 2025-09-08


### Other Changes

- Bug fix

## [0.1.180] - 2025-09-08


### Other Changes

- Bug fix

## [0.1.179] - 2025-09-08


### Other Changes

- Bug fix

## [0.1.178] - 2025-09-08


### Other Changes

- Bug fix

## [0.1.177] - 2025-09-08


### Other Changes

- Updating default user service

## [0.1.176] - 2025-09-08


### Other Changes

- Enhancing user service schemas

## [0.1.175] - 2025-09-08


### Other Changes

- Schema enhancement

## [0.1.174] - 2025-09-08


### Other Changes

- Schema enhancement

## [0.1.173] - 2025-09-08


### Other Changes

- Bug fix

## [0.1.172] - 2025-09-08


### Other Changes

- Enhancing the integration funcs

## [0.1.171] - 2025-09-08


### Other Changes

- Enhancing the integration funcs

## [0.1.170] - 2025-09-08


### Other Changes

- Updating sessiondeps

## [0.1.169] - 2025-09-08


### Other Changes

- Crud bug fix

## [0.1.168] - 2025-09-08


### Other Changes

- Bug fix resource add

## [0.1.167] - 2025-09-08


### Other Changes

- Bug fix resource add

## [0.1.166] - 2025-09-08


### Other Changes

- Bug fix resource add

## [0.1.165] - 2025-09-08


### Other Changes

- Resource router bug fix

## [0.1.164] - 2025-09-08


### Other Changes

- Bug fix db integration to fastapi

## [0.1.163] - 2025-09-08


### Other Changes

- Final fix

## [0.1.162] - 2025-09-08


### Other Changes

- Mcp bug fix

## [0.1.161] - 2025-09-08


### Other Changes

- Mcp bug fix
- Mcp bug fix
- Mcp bug fix

## [0.1.159] - 2025-09-08


### Other Changes

- Mcp bug fix

## [0.1.158] - 2025-09-08


### Other Changes

- Mcp bug fix

## [0.1.157] - 2025-09-08


### Other Changes

- Mcp bug fix

## [0.1.156] - 2025-09-08


### Other Changes

- Mcp bug fix

## [0.1.155] - 2025-09-08


### Other Changes

- Mcp bug fix

## [0.1.154] - 2025-09-08


### Other Changes

- Imported cli help cmds from ai infra for mcp

## [0.1.153] - 2025-09-08


### Other Changes

- Centralizing cmd helpers to ai_infra tools

## [0.1.152] - 2025-09-08


### Other Changes

- Generalizing cli

## [0.1.151] - 2025-09-07


### Other Changes

- Bug fix mcp

## [0.1.150] - 2025-09-07


### Other Changes

- Bug fix

## [0.1.149] - 2025-09-07


### Other Changes

- Bug fix

## [0.1.148] - 2025-09-07


### Other Changes

- Retry

## [0.1.147] - 2025-09-07


### Other Changes

- Enhanced cli cmds

## [0.1.146] - 2025-09-07


### Other Changes

- Mcp bug fix

## [0.1.145] - 2025-09-07


### Other Changes

- Mcp bug fix

## [0.1.144] - 2025-09-07


### Other Changes

- Added cli mcp

## [0.1.143] - 2025-09-07


### Other Changes

- Removed db setup mcp completely

## [0.1.142] - 2025-09-07


### Bug Fixes

- Fixing db url issues

## [0.1.141] - 2025-09-07


### Bug Fixes

- Fixing db url issues

## [0.1.140] - 2025-09-07


### Bug Fixes

- Fixing db url issues

## [0.1.139] - 2025-09-07


### Bug Fixes

- Fixing db url issues

## [0.1.138] - 2025-09-07


### Bug Fixes

- Fixing db url issues

## [0.1.137] - 2025-09-07


### Bug Fixes

- Fixing db url issues

## [0.1.136] - 2025-09-07


### Other Changes

- Returning dict for final db setup response

## [0.1.135] - 2025-09-07


### Other Changes

- Trying to fix the mcp bug

## [0.1.134] - 2025-09-07


### Other Changes

- Updated our cli guide for svc-infra. mcp svc infra has still many issues for the same funcs

## [0.1.133] - 2025-09-07


### Other Changes

- Updated the tmpls

## [0.1.132] - 2025-09-07


### Other Changes

- Updating env tmplts

## [0.1.131] - 2025-09-07


### Other Changes

- Trying to fix psycopg2 bug

## [0.1.130] - 2025-09-07


### Other Changes

- Updated env.py temp

## [0.1.129] - 2025-09-07


### Other Changes

- Removed the env wrapper

## [0.1.128] - 2025-09-06


### Bug Fixes

- Fix bugs

## [0.1.127] - 2025-09-06


### Bug Fixes

- Fixing db setup

## [0.1.126] - 2025-09-06


### Other Changes

- Updated observability and test cases

## [0.1.125] - 2025-09-06


### Other Changes

- Updated observability and test cases

## [0.1.124] - 2025-09-06


### Other Changes

- Expanded db set up

## [0.1.123] - 2025-09-06


### Other Changes

- Quick poetry config

## [0.1.122] - 2025-09-06


### Other Changes

- Autoconfigured sync/async of db setups

## [0.1.121] - 2025-09-06


### Other Changes

- Pushed metrics

## [0.1.120] - 2025-09-06


### Other Changes

- Adding observability and metrics

## [0.1.119] - 2025-09-06


### Other Changes

- Adding observability and metrics

## [0.1.118] - 2025-09-06


### Other Changes

- Adding observability and metrics

## [0.1.117] - 2025-09-06


### Other Changes

- Added example clis to readme

## [0.1.116] - 2025-09-06


### Other Changes

- Bug fix with db setups

## [0.1.115] - 2025-09-06


### Other Changes

- Bug fix

## [0.1.114] - 2025-09-06


### Other Changes

- Bug fix

## [0.1.113] - 2025-09-06


### Other Changes

- Bug fix

## [0.1.112] - 2025-09-06


### Other Changes

- Resolved env bug

## [0.1.111] - 2025-09-06


### Other Changes

- Added test users of auth

## [0.1.110] - 2025-09-06


### Other Changes

- Added auth settings test cases

## [0.1.109] - 2025-09-06


### Other Changes

- Added more test cases

## [0.1.108] - 2025-09-06


### Other Changes

- Added more test cases

## [0.1.107] - 2025-09-06


### Testing

- Add integration tests for include_auth

## [0.1.106] - 2025-09-06


### Other Changes

- Added more test cases

## [0.1.105] - 2025-09-06


### Other Changes

- Added more test cases

## [0.1.104] - 2025-09-06


### Other Changes

- Added more test cases for managing dbs

## [0.1.103] - 2025-09-06


### Other Changes

- Db code cleanup

## [0.1.102] - 2025-09-06


### Other Changes

- Bug fix

## [0.1.101] - 2025-09-06


### Other Changes

- Updated db setup

## [0.1.100] - 2025-09-05


### Other Changes

- Moved all db manage funcs under manage

## [0.1.99] - 2025-09-05


### Refactor

- Refactor the code further

## [0.1.98] - 2025-09-05


### Other Changes

- Removed hardcoded templates for db setups

## [0.1.97] - 2025-09-05


### Bug Fixes

- Fixing router issues


### Other Changes

- Moved all scaffolds to templates
- Moved all scaffolds to templates
- Added readme.md for cli

## [0.1.95] - 2025-09-05


### Other Changes

- Bug fix

## [0.1.94] - 2025-09-05


### Other Changes

- Added test cases for scaffolds

## [0.1.93] - 2025-09-05


### Other Changes

- Enhanced our scaffolders to max

## [0.1.92] - 2025-09-05


### Other Changes

- Merging auth and entity kind db scaffolds into one so that we can remove auth ones

## [0.1.91] - 2025-09-04


### Other Changes

- Added all db scaffolds to its cli

## [0.1.90] - 2025-09-04


### Other Changes

- Added test cases for db scaffolding

## [0.1.89] - 2025-09-04


### Other Changes

- Added scaffolding for db management

## [0.1.88] - 2025-09-04


### Other Changes

- Added extra deps

## [0.1.87] - 2025-09-04


### Other Changes

- Making db funcs more explicit through docstrings. adding psycopg2-binary as deps

## [0.1.86] - 2025-09-04


### Other Changes

- Added setup and migrate to mcps

## [0.1.85] - 2025-09-04


### Other Changes

- Centralizing model bases

## [0.1.84] - 2025-09-04


### Other Changes

- Bug fix

## [0.1.83] - 2025-09-04


### Other Changes

- Bug fix

## [0.1.82] - 2025-09-04


### Other Changes

- Bug fix

## [0.1.81] - 2025-09-04


### Other Changes

- Bug fix

## [0.1.80] - 2025-09-04


### Other Changes

- Bug fix

## [0.1.79] - 2025-09-04


### Other Changes

- Bug fix

## [0.1.78] - 2025-09-04


### Bug Fixes

- Fixing base

## [0.1.77] - 2025-09-04


### Other Changes

- Bug fix and clean ups

## [0.1.76] - 2025-09-04


### Other Changes

- Added docstring for each db management tool

## [0.1.75] - 2025-09-04


### Other Changes

- Added test cases

## [0.1.74] - 2025-09-04


### Refactor

- Refactored db funcs and added test cases

## [0.1.73] - 2025-09-04


### Refactor

- Refactored db funcs and added test cases

## [0.1.72] - 2025-09-04


### Other Changes

- Adding db management funcs

## [0.1.71] - 2025-09-03


### Other Changes

- Enhanced auth scaffolds

## [0.1.70] - 2025-09-03


### Other Changes

- Enhanced auth scaffolds

## [0.1.69] - 2025-09-03


### Other Changes

- Enhanced auth scaffolds to use both relative and abs paths

## [0.1.68] - 2025-09-03


### Other Changes

- Enhanced auth scaffolds

## [0.1.67] - 2025-09-03


### Other Changes

- Bug fixes

## [0.1.66] - 2025-09-03


### Other Changes

- Exposing auth-infra db-management mcps

## [0.1.65] - 2025-09-03


### Other Changes

- Mcp availability bug fix

## [0.1.64] - 2025-09-03


### Other Changes

- Making mcps avaialble to git

## [0.1.63] - 2025-09-03


### Other Changes

- Making mcps avaialble to git

## [0.1.62] - 2025-09-03


### Other Changes

- Making mcps avaialble to git

## [0.1.61] - 2025-09-03


### Other Changes

- Making mcps avaialble to git

## [0.1.60] - 2025-09-03


### Other Changes

- Making mcps avaialble to git

## [0.1.59] - 2025-09-03


### Other Changes

- Making mcps avaialble to git

## [0.1.58] - 2025-09-03


### Other Changes

- Making mcps avaialble to git

## [0.1.57] - 2025-09-03


### Other Changes

- Making mcps avaialble to git

## [0.1.56] - 2025-09-03


### Other Changes

- Bug fix

## [0.1.55] - 2025-09-03


### Other Changes

- Bug fix

## [0.1.54] - 2025-09-03


### Other Changes

- Bug fix

## [0.1.53] - 2025-09-03


### Other Changes

- Bug fix

## [0.1.52] - 2025-09-03


### Other Changes

- Bug fix

## [0.1.51] - 2025-09-03


### Other Changes

- Bug fix

## [0.1.50] - 2025-09-03


### Other Changes

- Bug fix

## [0.1.49] - 2025-09-03


### Other Changes

- Bug fix

## [0.1.48] - 2025-09-03


### Other Changes

- Bug fix

## [0.1.47] - 2025-09-03


### Other Changes

- Bug fix

## [0.1.46] - 2025-09-03


### Other Changes

- Bug fix

## [0.1.45] - 2025-09-03


### Other Changes

- Bug fix

## [0.1.44] - 2025-09-03


### Other Changes

- Bug fix

## [0.1.43] - 2025-09-03


### Other Changes

- Bug fix

## [0.1.42] - 2025-09-03


### Other Changes

- Bug fix

## [0.1.41] - 2025-09-03


### Other Changes

- Bug fix

## [0.1.40] - 2025-09-03


### Other Changes

- Bug fix

## [0.1.39] - 2025-09-03


### Other Changes

- Bug fix

## [0.1.38] - 2025-09-03


### Other Changes

- Bug fix

## [0.1.37] - 2025-09-03


### Other Changes

- Bug fix

## [0.1.36] - 2025-09-03


### Other Changes

- Bug fix

## [0.1.35] - 2025-09-02


### Other Changes

- Cli agent is ready and decent to push forward

## [0.1.34] - 2025-09-02


### Other Changes

- Upgraded our cli agent to mcp use. refactored code

## [0.1.33] - 2025-09-02


### Other Changes

- Enhanced the graph with mcps

## [0.1.32] - 2025-09-02


### Other Changes

- Enhanced the graph with mcps

## [0.1.31] - 2025-09-02


### Other Changes

- Bug fix

## [0.1.30] - 2025-09-02


### Other Changes

- Keeping svc infra cli commands for auth and db but adding mcp on top of them
- Converting cli commands to mcps

## [0.1.29] - 2025-09-02


### Other Changes

- Imprvoing cli agent

## [0.1.28] - 2025-08-31


### Other Changes

- Iterating to improve cli agent

## [0.1.27] - 2025-08-29


### Other Changes

- Prior moving to graph type cli agent

## [0.1.26] - 2025-08-28


### Other Changes

- Cli agent needs much more work in prompting. but the functionality is great

## [0.1.25] - 2025-08-28


### Other Changes

- Cli command agent is running well with mcp

## [0.1.24] - 2025-08-27


### Other Changes

- Added file manaamgent capabilities on top of run command using ai-infra mcp custom servers on stdio

## [0.1.23] - 2025-08-27


### Other Changes

- Enhanced cli agent sys msg by far with write context and helpers

## [0.1.22] - 2025-08-27


### Other Changes

- Enhanced cli agent to get git and project context

## [0.1.21] - 2025-08-27


### Other Changes

- Enhancing cli agent

## [0.1.20] - 2025-08-27


### Other Changes

- Enhancing our cli agent to all funcitonatlities

## [0.1.19] - 2025-08-27


### Other Changes

- Working to merge all cli calls under one cmd and add ai to it

## [0.1.18] - 2025-08-26


### Other Changes

- Working on generalizing ai command runner for auth, db, other custom clies as well as any terminal commands

## [0.1.17] - 2025-08-26


### Other Changes

- Huge improvements to cli ai

## [0.1.16] - 2025-08-26


### Other Changes

- Solid response from ai cli

## [0.1.15] - 2025-08-25


### Other Changes

- Simplified db ai cli

## [0.1.14] - 2025-08-25


### Other Changes

- Improved all ai funcs through cli for planning etc

## [0.1.13] - 2025-08-25


### Other Changes

- Enhancing db agent interactions

## [0.1.12] - 2025-08-25


### Other Changes

- Added db agent for easier command control

## [0.1.11] - 2025-08-24


### Other Changes

- Improved readme for cli'

## [0.1.10] - 2025-08-24


### Other Changes

- Bug fix

## [0.1.9] - 2025-08-24


### Miscellaneous

- Regenerate poetry.lock


### Other Changes

- Bug fix
- Bug fix
- Bug fix
- Bug fix
- Bug fix
- Bug fix
- Bug fix
- Trying oicd
- Trying oicd

## [0.1.8] - 2025-08-24


### Bug Fixes

- Fixing db schema router bug
- Fixing db schema router bug
- Fixing db schema router bug
- Fixed cors issues
- Fixing path conflicts
- Fixing path conflicts
- Fixing path conflicts
- Fixing path conflicts
- Fixing path conflicts
- Make nonprod optional in pick(), update logging and router registration for env refactor
- Use StrEnum for logging config enums and update imports for consistency
- Use StrEnum for log level/format options for Pydantic compatibility
- Improve logging config validation and traceback formatting for pydantic v2+ and Python 3.11+
- Ensure FastAPI app name/version always use AppSettings defaults if None is passed
- Ensure AppSettings defaults are used when name/version is None


### Features

- Add 'staging' synonym, ALL_ENVIRONMENTS, and improve router exclusion logic
- Switch to ROUTER_EXCLUDED_ENVIRONMENTS for router registration control
- Make router exclusion dynamic and add pydantic schema for routers_exclude


### Miscellaneous

- Remove __pycache__ and *.pyc; update .gitignore to exclude pycache/pyc and .pytest_cache
- Silence multipart parser logs in non-debug environments
- Push all recent changes
- Update and refactor router exclusion and settings handling
- Update and refactor router exclusion and settings handling
- Update and refactor router exclusion and settings handling


### Other Changes

- Lock deps
- Updated our pypi yml
- Added readme
- Published for mass consume
- Adding back error handler from child
- Removed error handler from child
- Passing our error handlers to parent
- Moving all db routers to /_db
- Added crud funcs for fastapi
- Added crud funcs for fastapi
- Added drop table cli
- Added drop table cli
- Added drop table cli
- Alembic will autodiscover models with base type
- Bug fix
- Getting close to first iteration
- Getting close to first iteration
- Getting close to first iteration
- Getting close to first iteration
- Getting close to first iteration
- Improving alembic logging
- Improving alembic logging
- Improving alembic logging
- Improving alembic logging
- Improving auth
- Improving auth
- Improving auth
- Improving auth
- Improving auth
- Improving auth
- Improving auth
- Upgrading to remove sessiondeps
- Upgrading to remove sessiondeps
- Upgrading to remove sessiondeps
- Upgrading to remove sessiondeps
- Upgrading to remove sessiondeps
- Upgrading to remove sessiondeps
- Separated cli commands for auth and added readme for them
- Separated cli commands for auth and added readme for them
- Getting close to first iteration
- Getting close to first iteration
- Getting close to first iteration
- Getting close to first iteration
- Auto-create __init__.py in target directories when generating models/schemas/routers
- Added cli commands for auth purposes
- Upgrading to add ability for cli functionalities and scaffolding for each
- Added cli commands for auth purposes
- Added cli commands for auth purposes
- Added cli commands for auth purposes
- Added cli commands for auth purposes
- Adding new version
- Adding new version
- Adding db funcs
- Add copy-pasteable Widget model, WidgetRepository, and FastAPI router; update db README with examples and CLI quickstart
- Init, makemigrations, upgrade, downgrade; includes --help with usage
- Enforce SoftDelete in get/list/count with is_deleted filter; add include_deleted override; refactor to use _base_select and apply_filters; fix typing warnings and unused imports; keep behavior consistent and tests green
- Adding db funcs
- Adding db funcs
- Adding db funcs
- Adding db funcs
- Adding db funcs
- Adding db funcs
- Adding db funcs
- Adding db funcs
- Adding db funcs
- Adding multi versioning
- Cleaning up func ids
- Cleaning up func ids
- Updated our error handling middleware
- Push all recent changes
- Add python-dotenv dependency via Poetry
- Add FastAPI router discovery and registration utility
- Restructure pyproject.toml sections only, no content changes
- Restructure pyproject.toml to use [tool.poetry] section
- Remove svc-infra.iml from git tracking and update .gitignore
- First commit
- First commit


### Refactor

- Refactored fastapi app settings
- Refactored fastapi app settings
- Rename execute_api to create_and_register_api and improve naming/documentation
- Use self-documenting environment naming (Environment, CURRENT_ENVIRONMENT, etc.) everywhere
- Improve execute_api for readability, robustness, and production readiness


### Testing

- Testing pypi publication
- Testing pypi publication
- Testing pypi publication
- Testing auth cli
- Testing auth cli

<!-- Generated by git-cliff -->

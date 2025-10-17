# Planning Methodology (PLANS_METHOD)

This document describes the standardized method used to build the production readiness plan in `PLANS.md`. Follow these steps to create future plans that are actionable, testable, and traceable.

---
## 1. Scope Definition
- Clarify the objective (e.g., "Production Readiness v1", "Introduce Billing Module", "Refactor Auth").
- Identify mandatory vs. optional (fast follow) components.
- Capture constraints (time, team size, external dependencies) and assumptions.

Deliverable: Intro paragraph + Must-have vs Nice-to-have section skeleton.

---
## 2. Decomposition into Domains
Break the scope into high-level domains (e.g., Security, Rate Limiting, Tenancy, Data Lifecycle).

Heuristics:
- Group by operational concern (security, reliability, data).
- Keep each domain independently shippable.
- Avoid mixing infrastructure concerns (e.g., background jobs) with feature concerns (e.g., billing).

Deliverable: Domain list with headings.

---
## 3. Standard Subtask Pattern
Each domain should follow the same subtask lifecycle:
1. Research – Verify if functionality already exists; list existing code references for reuse or mark as skipped (~).
2. Design – Produce ADR or schema proposal; define interfaces & data models.
3. Implement – Code changes; keep atomic and reference PR links.
4. Tests – Unit + integration tests; define markers per domain (e.g., `pytest -m security`).
5. Verify – Run domain-focused test marker; optionally stress or load checks.
6. Docs – Update developer guides, API references, or operational runbooks.
7. Acceptance (pre-deploy) – Run acceptance scenarios (A-IDs) in an ephemeral stack in CI; gate artifact promotion on success.

Represent these steps as individual checklist items.

---
## 3.1 Hard Gates Between Stages (MANDATORY)
To ensure discipline and traceability, later stages must not begin until all prior stages are completed and recorded. These are hard gates, not guidelines:

- Gate A (Design): Do not start Design until Research is completed and sources are recorded in the plan (paths, notes, or [~] skips).
- Gate B (Implement): Do not start Implementation until both Research and Design are completed with ADR links and explicit acceptance criteria.
- Gate C (Tests): Tests must be authored alongside or before code changes. Do not mark Verify until tests exist and cover the changed behavior.
- Gate D (Verify): Do not proceed to Docs until Verify passes for the domain (marker subset and/or focused test run is green).
- Gate E (Docs): Docs are the final step. Do not mark the domain done unless Docs are updated and discoverable.
- Gate F (Acceptance): Promotion gate must pass. Do not publish artifacts until Acceptance scenarios for the domain (A-IDs) are green in CI on an ephemeral environment.

Enforcement and Evidence:
- Each checklist item must include a brief note and links: file paths, ADR IDs, PR numbers/commits, and any test names/markers.
- It is not allowed to “jump ahead” in the checklist. If an item is found out-of-order, revert status and complete prerequisites first.
- When work already exists, mark the prior stages as [~] Skipped with explicit paths and rationale.

Example (proper ordering with evidence):
```
- [x] Research: rate limit storage exists (src/svc_infra/api/fastapi/rate_limit/store.py)
- [x] Design: ADR-007 add tenant scope; keys & error semantics
- [x] Implement: tenant-scoped limiter (PR-154, commit abc123)
- [x] Tests: tests/api/test_rate_limit_tenant.py::test_scope_applies
- [x] Verify: pytest -q -k rate_limit_tenant passed
- [x] Docs: docs/rate-limiting.md updated with examples
- [x] Acceptance: A2-01..A2-03 green in CI (run: build-and-accept #123, link)
```

---
## 4. Check Types & Notation
- [ ] Pending
- [x] Completed
- [~] Skipped (already exists, out of scope, or replaced)
- (note) Inline context, decisions, or links (ADR-###, PR-###).

Use consistent ordering: Research → Design → Implement → Tests → Verify → Docs → Acceptance (pre-deploy).
Append “Acceptance (pre-deploy)” after Docs to record the CI promotion gate results, and treat it as a mandatory promotion gate.

---
## 5. Skipping Existing Functionality
During Research:
- Use code search (grep/semantic) to locate potential existing implementations.
- If found adequate: mark item as [~] Skipped; add note with file path.
- If partial: adjust Design/Implement scope to extend rather than rebuild.

Example:
```
- [~] Implement: security headers middleware (already in `security/headers.py`)
```

---
## 6. Test Integration Strategy
For each domain define test markers or folder naming patterns:
- security → tests/security/* or marker `@pytest.mark.security`
- rate limiting → tests/rate_limit/* or marker `rate_limit`
- billing → tests/billing/*

Add at least:
- Happy path test.
- Boundary/edge test.
- Failure mode test (e.g., lockout triggers, exceeded rate limit).

Include verification step: run marker subset + full suite post-domain completion.
Add acceptance step: run `pytest -m "acceptance or smoke"` against an ephemeral stack (Docker Compose or Testcontainers) after build and before promotion.

---
## 7. Global Verification Section
Add a final section that consolidates:
- Full pytest run after each major domain.
- Flakiness detection (rerun markers multiple times).
- Release readiness report (counts of completed vs. skipped items).
- Changelog & version tag tasks.
- Acceptance gate summary: CI job link(s), A-IDs passed, compose up/down status.

---
## 8. Traceability & ADRs
- For every non-trivial design choice create an ADR (Architecture Decision Record).
- Link ADR IDs in plan items: `(ADR-005)`.
- Maintain a running Notes / Decisions log at bottom of plan.

ADR Minimum Fields:
- Context, Decision, Alternatives, Consequences.

---
## 9. Incremental Updates Workflow
1. Add domain section with all subtasks in Pending state.
2. Perform Research → update statuses (mark Skipped or refine tasks).
3. Draft Design → link ADR.
4. Implement incrementally; after each PR, flip [ ] → [x] and append `(PR-###)`.
5. Write tests before or with implementation; mark them as part of Tests subtask.
6. Run Verify step; if pass, proceed to Docs.
7. Avoid large batch flips—update each checkbox as work lands.
8. Maintain an acceptance matrix doc mapping A-IDs to endpoints/CLIs/fixtures; reference it in each domain’s Acceptance item.
9. Add an Owner: line per domain and maintain an Evidence: bullet list with PRs/commits, key test names/markers, and CI run URLs.

---
## 10. Quality Gate Alignment
Ensure each domain references quality gates:
- Lint / Typecheck / Tests / Security scan / SBOM.
Add subtask if domain introduces new tooling.
Additionally, define acceptance gates per domain (A-IDs) and reference them in Verify and Acceptance items. Each checklist item should include evidence: PR/commit, test names, marker, and CI run URL.

---
## 11. Versioning & Releases
Before declaring Done:
- All Must-have domains fully completed (no unchecked items except intentional skips).
- Global verification tasks all [x].
- Produce release notes summarizing domain outcomes & major ADRs.

---
## 12. Example Template Snippet
```
# PLANS_METHOD (Concise)

Goal: Produce a single self-contained plan in `PLANS.md` that is actionable, testable, and replaceable. When a new initiative starts, discard the old plan and regenerate with the same structure.

## Core Pattern (Per Domain)
Checklist order: Research → Design → Implement → Tests → Verify → Docs
Symbols: [ ] pending | [x] done | [~] skipped (already exists / out of scope)

## Steps
1. Define Scope: Title + Must-have vs Nice-to-have domains.
2. List Domains: Each is a heading (e.g., Security, Rate Limiting, Tenancy...).
3. For each Domain add the six lifecycle subtasks as checkboxes.
4. Research Phase: Search codebase first; mark existing features as [~] with file path.
5. Design Phase: Create minimal ADR(s) if structural changes (note ADR IDs inline).
6. Implement Phase: Ship smallest pieces; update checkboxes immediately with (PR-###).
7. Tests Phase: Add unit + at least one integration test; mark domain test marker (optional).
8. Verify Phase: Run selective pytest (e.g., markers) plus full suite when a domain completes.
9. Docs Phase: Add or extend developer guide sections; keep docs light but discoverable at root of the project /docs.
10. Global Section: Add final block with full test run, flakiness check, and release tag tasks.
11. Replace Not Append: When starting next plan, overwrite `PLANS.md` using this pattern.

## Minimal Domain Template
```
### Domain Name
- [ ] Research: existing implementation (paths: ...)
- [ ] Design: ADR-### summary
- [ ] Implement: core components
- [ ] Tests: unit + integration
- [ ] Verify: pytest -m domain_name (and full suite)
- [ ] Docs: usage & notes
```

## Skipping Example
```
- [~] Implement: security headers middleware (already in src/svc_infra/security/headers.py)
```

## Global Block Template
```
### Global Verification
- [ ] Full pytest run
- [ ] Flaky re-run (key markers x3)
- [ ] Update PR / ADR links
- [ ] Release readiness summary
- [ ] Tag version & changelog
```

## Do / Don't
Do: keep tasks atomic; update immediately after merge; record skips.
Don't: batch-complete large sections without intermediate test/verify; duplicate old plans; start later stages before earlier ones are completed (respect Hard Gates).

## ADR Minimum Fields
Context | Decision | Alternatives | Consequences (keep short; skip if trivial).

## Ready Check (Before Release)
All Must-have domains: Tests & Verify checked; Docs present; Acceptance (pre-deploy) green; Global Verification complete.

### 3.5 Acceptance Matrix (new)
- Define A-IDs (A1-01…) covering golden paths, negative cases, and ops.
- Each domain’s “Acceptance” task references the relevant A-IDs.
- CI gate runs A-IDs post-build in an ephemeral environment (Docker Compose or Testcontainers). Artifact promotion depends on pass.
- Keep docs in `docs/acceptance-matrix.md` with mapping: A-ID → endpoints/CLIs/fixtures and any seed data required. Link the doc from each domain section.

This concise method is sufficient to regenerate plans of the same style without extra overhead.

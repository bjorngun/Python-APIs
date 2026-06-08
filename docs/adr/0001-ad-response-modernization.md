# ADR 0001: AD Response Modernization and Compatibility Policy

- Status: Draft
- Date: 2026-06-08
- Related issue: #16

## Context

This package is introducing staged modernization for AD-facing APIs and services.
Downstream systems currently depend on response shapes and behavior that evolved over time,
including legacy keys and permissive contracts. Moving too quickly risks regressions in
production integrations.

Issue #16 defines the governance and rollout policy for introducing richer response metadata,
explicit compatibility modes, and deprecation control without breaking consumers in Stage N.

## Scope

This ADR defines:

- Compatibility mode expectations across rollout stages.
- Additive-first policy for Stage N.
- SemVer guardrails for removal of legacy behavior.
- Required migration guidance for behavior changes.
- Contract-test expectations for response-shape changes.

## Non-Goals

This ADR does not:

- Implement runtime feature changes directly.
- Redesign every AD API in one step.
- Remove legacy behavior in Stage N.
- Replace issue-level implementation details in follow-up tickets.

## Decision

The project will use staged, compatibility-first modernization:

1. Stage N: additive only; preserve existing behavior contracts.
2. Stage N+1: default new behavior where approved, while compatibility controls remain.
3. Stage N+2: allow removals only under explicit semver-major scope with migration support.

## Policy (Initial)

- Public API shape/signature changes must include compatibility behavior and migration guidance.
- Legacy-compatible behavior removal is forbidden outside explicit semver-major scope.
- Batch read paths must not silently drop failed records; failure details must be surfaced.
- When SemVer impact is unclear, stop and clarify before merge/release.

## Consequences

Positive:

- Reduced breakage risk for downstream consumers.
- Clear migration path and predictable rollout sequencing.
- Better review discipline for API contract changes.

Trade-offs:

- Additional implementation overhead for compatibility mirroring and documentation.
- Longer overlap period where old and new behaviors coexist.

## Rollout Stages

- Stage N: additive behavior and compatibility guarantees only.
- Stage N+1: migration nudges, warnings, and broader adoption of modern contracts.
- Stage N+2: controlled cleanup for approved semver-major items.

## Migration Guidance Requirements

Any PR that changes public behavior must include:

- Expected SemVer impact and rationale.
- Before/after usage guidance where relevant.
- Explicit compatibility note for existing consumers.

## Test and Validation Expectations

For response contract changes, require contract-level tests covering:

- Success and failure response shapes.
- Compatibility mode behavior where applicable.
- Not-found and partial-failure semantics where applicable.

## Open Questions

- Final compatibility mode names and defaults for runtime APIs.
- Standardized error taxonomy naming and granularity.
- Exact deprecation-warning mechanism and timeline criteria.

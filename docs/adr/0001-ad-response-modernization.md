# ADR 0001: AD Response Modernization and Compatibility Policy

- Status: Accepted
- Date: 2026-06-08
- Related issue: #16

## Context

This package is introducing staged modernization for AD-facing APIs and services.
Downstream systems currently depend on response shapes and behavior that evolved over time,
including legacy keys and permissive contracts. Moving too quickly risks regressions in
production integrations.

Issue #16 defines the governance and rollout policy for introducing richer response metadata,
explicit compatibility modes, and deprecation control without breaking consumers in Stage N.

## Baseline Behavior (Current State)

Current implementation characteristics that this ADR must preserve in Stage N:

- AD connection operations commonly return dictionaries with legacy keys such as `success` and
  `result`.
- `ADConnection.get()` currently returns an empty-string `defaultdict` when no result is found,
  rather than a typed not-found contract.
- LDAP communication/session failures are retried via reconnect logic in the API layer, including
  paths that can perform write operations.
- User batch reads in service layer perform schema validation and can skip invalid records after
  logging validation errors.

Current release automation constraints:

- Publish workflow derives bump type from merged PR SemVer label (`semver:major`,
  `semver:minor`, `semver:none`).
- Exactly one SemVer label is required for release-relevant PRs.
- `semver:none` explicitly skips version bump and publish.

Known compatibility risks:

- Downstream consumers may rely on legacy `result` payload shape and permissive return patterns.
- Tightening not-found or validation behavior without compatibility mode can cause regressions.
- Retry policy changes for write paths may alter observed side effects if not staged carefully.

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

## Compatibility Modes

The AD modernization rollout uses three compatibility modes to make behavior explicit while
preserving safety for existing consumers.

| Mode | Default stage | Contract intent | Required invariants |
| --- | --- | --- | --- |
| `legacy` | Stage N default | Preserve pre-modernization behavior by default. | Keep legacy envelope keys (`success`, `result`) available; preserve permissive not-found semantics; avoid raising new contract-level exceptions for existing call paths. |
| `mixed` | Opt-in during Stage N and broad in Stage N+1 | Return modern envelope fields while mirroring legacy fields. | Include modern metadata and normalized error shape while still emitting legacy mirror keys; behavior must remain non-breaking for consumers reading only legacy keys. |
| `strict` | Opt-in in Stage N/N+1, candidate default in Stage N+2 | Enforce modern contract without legacy mirrors. | Legacy keys may be omitted; not-found and partial-failure semantics follow modern typed contract; normalized error taxonomy is mandatory. |

Stage N default is `legacy` to guarantee a non-breaking baseline. `mixed` and `strict` are
adoption tools and must never be forced as the default in Stage N.

## Envelope Deprecation and Mirroring Rules

Envelope modernization follows additive-first rollout and explicit removal gates.

### Envelope shape policy

- Stage N introduces a modern response envelope additively.
- Stage N and Stage N+1 must mirror legacy keys for compatibility in `legacy` and `mixed`.
- Mirror fields must represent the same logical outcome as modern fields; divergence is treated
  as a defect.

### Deprecation timeline

| Stage | Legacy mirror fields | Warnings | Removal eligibility |
| --- | --- | --- | --- |
| N | Required | Optional informational guidance only. | Not eligible. |
| N+1 | Required in `legacy`/`mixed`; optional in `strict`. | Required deprecation warnings when legacy fields are consumed or requested through compatibility controls. | Not eligible for default behavior removals. |
| N+2 (`semver:major`) | Optional and off by default. | Migration warnings may remain for one major cycle if mirrors are temporarily enabled. | Eligible only when migration guidance, release notes, and compatibility window evidence are complete. |

### Removal gates

Legacy mirror removal requires all of the following:

- PRs are explicitly scoped as breaking and labeled `semver:major`.
- ADR-linked migration notes provide before/after examples for affected endpoints.
- Contract tests cover legacy-disabled behavior and assert normalized modern envelope only.
- Downstream impact assessment is recorded in the issue/PR thread.

## Retry and Error Normalization Policy

Retry behavior and error taxonomy must be consistent across AD API/service boundaries.

### Retry defaults

- Read operations: automatic retry-once after reconnect is allowed by default for transient
  LDAP/session failures.
- Write operations: no implicit retry by default to avoid duplicate side effects.
- Any write-path retry must be explicit, idempotency-justified, and documented in code and PR.
- Retry overrides must be configurable and default-preserving in Stage N.

### Telemetry requirements

For each retry attempt (or skip decision), emit structured telemetry with at least:

- operation name and read/write classification,
- attempt count and outcome,
- error code/category observed,
- compatibility mode and envelope mode context.

Telemetry data must allow distinguishing transient transport failures from deterministic
validation or authorization failures.

### Normalized error taxonomy

Modern responses should provide normalized machine-routable error codes. Initial required
categories are:

- `not_found`
- `validation_error`
- `auth_error`
- `permission_denied`
- `connection_error`
- `timeout`
- `conflict`
- `unknown_error`

Unknown or unmapped failures must resolve to `unknown_error` while preserving diagnostic context
in logs/metadata. Consumers must be able to route based on normalized code without parsing human
message text.

## Rollout Stage to Issue Mapping

The following issues define implementation sequencing for this ADR.

| Stage | Goal | Issues | Dependency notes |
| --- | --- | --- | --- |
| Stage N (additive, non-breaking baseline) | Establish compatibility controls and modern envelope primitives while preserving legacy behavior. | #17 global compatibility modes; #18 typed response models with dict-compatible adapters; #19 operation envelope with legacy mirroring; #20 normalized error taxonomy utilities; #21 retry metadata and policy telemetry. | Sequence: #17 -> #18 -> #19. Then #20 and #21 build on envelope and mode context from #17/#19. |
| Stage N+1 (adoption and expansion) | Expand modern APIs and migration tooling while keeping compatibility controls available. | #22 membership APIs v2 (direct groups/primary group); #23 membership APIs v2 (transitive groups/members paging); #24 batch read v2 partial-failure contract; #25 multivalue dual-form support; #26 explicit get_v2 typed not-found contract; #27 in-package discoverability toolkit. | #22 should precede #23 for membership layering. #24/#25/#26 depend on Stage N envelope and error primitives. #27 should follow early N+1 implementations to document finalized usage. |
| Stage N+2 (major cleanup) | Remove legacy mirrors and legacy get semantics under explicit breaking scope. | #28 [MAJOR] remove legacy mirrored keys and legacy get semantics. | Requires Stage N and N+1 migration signals, published guidance, and explicit `semver:major` release intent. |
| Cross-stage governance (supports all stages) | Enforce release and plan protocol discipline during rollout. | #29 PR-time SemVer label validation; #30 PR template SemVer checklist; #31 harden plan-issue discoverability; #32 enforce commit-after-each-task policy. | Can run in parallel with implementation stages; should land before broad N+1 rollout to reduce process drift. |

This mapping is sequencing guidance, not a hard gate matrix. If scope changes, update this ADR and
the linked issue set in the same PR.

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

# Changelog

<!-- markdownlint-disable MD024 -->

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/en/1.0.0/)
and this project adheres to [Semantic Versioning](http://semver.org/spec/v2.0.0.html).

<!-- insertion marker -->
## [v0.4.13](https://github.com/bjorngun/Python-APIs/releases/tag/v0.4.13) - 2026-01-26

### Added

- `force_change_password_at_next_logon` method to ADConnection for setting/clearing the "User must change password at next logon" flag via `pwdLastSet` attribute
- `must_change_at_next_logon` parameter to `ADUserService.set_password()` for forcing password change at next logon
- `must_change_password_at_next_logon` option to `ADUserService.create_user()` for setting password change requirement during user creation
- 7 new unit tests for password change functionality (55 total tests)

## Unreleased

### Breaking Changes

- **AD layer is now strict-only (issue #28, `semver:major`).** ADR 0001 Stage N+2 cleanup: the
  compatibility-mode system and all legacy mirror behavior have been removed. See
  `docs/migration/v-major-upgrade.md` for a full before/after upgrade guide.
- Removed `ADConnection.get()` (the empty-string `defaultdict` read). Use
  `ADConnection.get_v2()` → `ADGetResult` instead.
- Removed the `result` and `message` legacy mirror keys from `ADOperationEnvelope`. Read
  `ldap_result` and `exception_message` instead. `ADOperationEnvelope.to_response()` no longer
  takes a `mode` argument and always emits the strict payload (equal to `to_dict()`).
- AD write methods (`enable_user`, `disable_user`, `add_member`, `remove_member`,
  `move_user_to_ou`, `modify_user`, `set_password`, `create_user`, `rename_user_cn`,
  `modify_group`, `modify_ou`) now **always** return the strict envelope (no `result`/`message`
  keys); the previous default raw-dict return is gone.
- Removed the `compatibility_mode` parameter from every AD service constructor and method, plus
  the `_resolve_effective_mode`/`get_compatibility_mode` helpers and `ADConnection.compatibility_mode`.
- Removed mode infrastructure: `AD_COMPATIBILITY_MODES`, `AD_DEFAULT_COMPATIBILITY_MODE`,
  `AD_COMPATIBILITY_ENV_VAR`, `resolve_ad_compatibility_mode`, `resolve_service_compatibility_mode`,
  and `ADCompatibilityMode`. The `PYTHON_APIS_AD_COMPAT_MODE` environment variable is no longer read.
  `python_apis.services.compatibility_mode` now exports only the strict-only
  `finalize_ad_write_response`/`finalize_ad_read_response` (no `effective_mode` parameter).
- Removed the `compatibility-modes` discovery capability and the `active_compatibility_mode` /
  `describe_compatibility_modes` introspection helpers, and dropped the
  `compatibility_mode_selection` migration example.
- Read methods keep their historic typed return values; only the `compatibility_mode` parameter
  was removed.

### Added

- PR-time `validate-semver-label` CI check (issue #29, `semver:none`) that fails a pull request
  early when it is missing a SemVer label or has more than one, before merge.
- In-package discoverability toolkit for the modernized AD surface (issue #27): `python_apis.discovery` (capability registry via `list_capabilities`/`get_capability` and a printable `quick_reference`), `python_apis.deprecation` (`warn_legacy` structured migration warnings), and `python_apis.migration_examples` (connection-free before/after snippets). All additive (`semver:minor`).
- rename_user_cn functionality to ADUserService for renaming user common names
- Python 3.14 support and optimized CI/CD workflows  
- Comprehensive test coverage (100% function coverage with 48 tests)
- Automatic LDAP reconnect/rebind on session expiry or communication errors in `ADConnection`
- Public `rebind()` method on `ADConnection` for explicit re-establishment of the LDAP session
- 8 new unit tests for reconnect behaviour (64 total tests)
- Repository planning and PR workflow skills: `plan-issue`, `pr-create`, and `pr-comments`
- PR template and contributor guidance for SemVer labeling and task-bounded commit workflow
- Typed, dict-compatible AD response models (`ADResponse`, `ADOperationResponse`, `ADEntry`,
  `ADSearchResponse`) with legacy-key parity, lossless `from_legacy`/`to_dict` adapters, and JSON
  serialization (additive, non-breaking; exported from `python_apis.models`)
- Contract tests pinning AD response model field names, types, dict-compatibility, and JSON
  serializability
- AD operation envelope (`ADOperationEnvelope`) for service write operations with modern fields
  (`success`, `operation_kind`, `ldap_result`, `exception_type`/`exception_message`,
  `request_context`) and `error_code`/`retry_count`/`retried` metadata; wired into
  `ADUserService`, `ADGroupService`, and `ADOrganizationalUnitService` write ops
- Service-layer envelope contract tests across user/group/OU write operations
- Migration guide for the AD operation envelope (`docs/migration/ad-operation-envelope.md`)
- Normalized AD error taxonomy (`python_apis.services.error_taxonomy`) with eight canonical,
  transport-agnostic error codes (`AD_NOT_FOUND`, `AD_VALIDATION_ERROR`, `AD_AUTH_ERROR`,
  `AD_PERMISSION_DENIED`, `AD_CONNECTION_ERROR`, `AD_TIMEOUT`, `AD_CONFLICT`, `AD_UNKNOWN`) and
  pure mapping utilities (`map_exception_to_error_code`, `map_ldap_result_to_error_code`,
  `resolve_error_code`) that classify ldap3/`pydantic` exceptions and LDAP result states, with a
  deterministic `AD_UNKNOWN` fallback
- Automatic population of `ADOperationEnvelope.error_code` for AD write operations (successful ops
  carry `error_code = None`)
- Unit tests for the AD error taxonomy and its service-layer integration
- Retry telemetry and policy metadata on AD responses (issue #21): `ADOperationEnvelope` carries
  `would_retry`, `retry_policy`, and a `did_retry` mirror alongside `retry_count`/`retried`
- `RetryTelemetry` dataclass plus `AD_READ_RETRY_POLICY`/`AD_WRITE_RETRY_POLICY` policy constants and
  `ADConnection.last_retry_telemetry`, capturing per-operation retry outcome (operation kind, attempt
  count, retried/would-retry/recovered, policy) for the auto-reconnect path (read/write classified)
- `finalize_ad_read_response` opt-in helper for structured AD read reporting and retry-telemetry
  threading into AD write finalization across user/group/OU services (default read return types
  unchanged)
- Unit tests for AD retry telemetry capture and read/write retry reporting
- Membership APIs v2 on `ADGroupService` (issue #22): `get_user_direct_groups(user)` returning the
  user's direct group memberships (`list[ADGroup]` via `(&(objectClass=group)(member=<userDN>))`) and
  `resolve_primary_group(user)` resolving the user's primary group (`ADGroup | None`). Because
  `primaryGroupToken` is a constructed attribute that cannot be used in an LDAP search filter, the
  primary group SID is derived from the user's `objectSid` (domain portion) plus `primaryGroupID`
  (RID) and looked up via `(&(objectClass=group)(objectSid=<sid>))`, returning `None` gracefully when
  the user has no `objectSid`/`primaryGroupID`. `get_user_direct_groups` accepts an `ADUser` or
  distinguishedName string; both escape LDAP filter values and reuse the retry-capable read path
  (additive, backward-compatible)
- Contract tests for the membership APIs covering happy and edge paths
- Membership APIs v2 on `ADGroupService` (issue #23): `get_user_transitive_groups(user)` returning
  every group a user belongs to including nested memberships (`list[ADGroup]`, sorted by
  `distinguishedName` for determinism) via the AD matching rule `LDAP_MATCHING_RULE_IN_CHAIN`
  (`member:1.2.840.113556.1.4.1941:=<userDN>`), and `get_group_members(group)` returning a paged
  `ADMembersPage` (`members`, `total_count`, `page_info`, `truncated`) of member distinguishedNames
  that scales to large groups via LDAP ranged retrieval (`member;range=lo-hi`) with client-side
  paging (`page_size`/`offset`) and an optional `max_members` cap; both accept an `ADUser`/`ADGroup`
  or distinguishedName string and escape LDAP filter values (additive, backward-compatible)
- `ADMembersPage` typed paged response model (exported from `python_apis.models`) and
  `ADConnection.get_ranged_attribute` for LDAP ranged multi-valued attribute retrieval, with an
  optional `limit` to early-stop range reads (so `max_members` bounds LDAP traffic on large groups)
  and resilience to empty ranged echoes returned alongside the real bounded range
- Contract tests for transitive group resolution, paged group member retrieval, and ranged-attribute
  assembly
- Canonical membership API usage example (`examples/membership_apis.py`)
- Batch read v2 APIs with a partial-failure contract (issue #24): `get_users_from_ad_v2`,
  `get_groups_from_ad_v2`, and `get_ous_from_ad_v2` on the AD services return an `ADBatchReadResult`
  envelope (`returned_items`, `failed_items`, `totals`, optional `continuation_state`) instead of
  silently dropping records that fail schema validation; each `failed_items` entry is an
  `ADBatchItemFailure` carrying `identity` (dn/account id), `failure_classification`, `error_code`
  (from the AD error taxonomy), and `raw_validation_details`. The existing `get_users_from_ad`,
  `get_groups_from_ad`, and `get_ous_from_ad` list-returning methods are unchanged (additive,
  backward-compatible)
- `ADBatchReadResult` and `ADBatchItemFailure` typed response models (exported from
  `python_apis.models`) and a shared `python_apis.services.batch_read.build_batch_read_result` helper
- Contract tests for the batch read v2 APIs (all-success/all-failure/mixed/empty and unchanged
  list-method signatures) and a canonical usage example (`examples/batch_read_v2.py`) plus migration
  guide (`docs/migration/ad-batch-read-v2.md`)
- Multivalue dual-form support for AD attributes (issue #25): `ADMultiValue` exposes the `raw` source
  value (preserved verbatim), a deterministically `normalized` `list[str]` (`values`), and
  `metadata` (`ADMultiValueMetadata` with `source`/`normalized`/`count`/`delimiter`), plus an
  `as_legacy_string()` accessor that reproduces the historic comma-joined string during the
  transition. A pure `normalize_multivalue(raw, *, delimiter=",")` helper implements the documented
  deterministic normalization rules. Existing schema field types and their comma-joining behavior are
  unchanged (additive, backward-compatible; exported from `python_apis.models`)
- Contract tests for the multivalue dual-form (normalization rules, determinism, legacy-accessor
  parity, shape invariants), a migration guide documenting the normalization rules
  (`docs/migration/ad-multivalue-dual-form.md`), and a usage example
  (`examples/multivalue_dual_form.py`)
- Explicit single-object `get_v2` AD read with a typed not-found result (issue #26):
  `ADConnection.get_v2(search_filter, attributes)` returns an `ADGetResult` envelope (exported from
  `python_apis.models`) with an explicit `found` flag, the matched `item`, a deterministic
  `not_found_reason` (`"no_match"`), and a canonical `error_code` (`"AD_NOT_FOUND"`), so callers can
  distinguish "absent" from "present but empty". Not-found semantics are deterministic (zero rows →
  not found; one or more rows → first match). The legacy `ADConnection.get` behavior is unchanged
  (additive, backward-compatible)
- Contract tests for `ADGetResult` and `get_v2` (found, first-of-many, not-found, unchanged legacy
  `get`), a migration guide (`docs/migration/ad-get-v2.md`), and a usage example with a migration
  helper (`examples/get_v2.py`)

### Fixed

- CI pipeline shell compatibility issues for cross-platform builds
- Auto-changelog integration conflicts

### Changed

- Optimized GitHub Actions workflow from 8 to 5 jobs for better efficiency
- Updated Python version matrix to support 3.10-3.14
- Publish workflow now derives version bump from merged PR SemVer label and skips publish for
  `semver:none`

## [v0.4.9](https://github.com/bjorngun/Python-APIs/releases/tag/v0.4.9) - 2025-10-27

- Added carLicence field to user fetch functionality

## [v0.4.8](https://github.com/bjorngun/Python-APIs/releases/tag/v0.4.8) - 2025-10-27

- Added carLicence field to user model

## [v0.4.5](https://github.com/bjorngun/Python-APIs/releases/tag/v0.4.5) - 2025-10-22

- Added enable_user functionality to ADUserService

## [v0.4.4](https://github.com/bjorngun/Python-APIs/releases/tag/v0.4.4) - 2025-10-22

- Added set_password function to ADUserService

## [v0.4.3](https://github.com/bjorngun/Python-APIs/releases/tag/v0.4.3) - 2025-10-16

- Added functionality to get all SAM account names
- Fixed linting issues

## [v0.4.2](https://github.com/bjorngun/Python-APIs/releases/tag/v0.4.2) - 2025-10-14

- Added move_user_to_ou function for moving users between organizational units

## [v0.4.1](https://github.com/bjorngun/Python-APIs/releases/tag/v0.4.1) - 2025-08-12

- Internal improvements and maintenance

## [v0.3.9](https://github.com/bjorngun/Python-APIs/releases/tag/v0.3.9) - 2025-08-11

- Internal improvements and maintenance

## [v0.3.8](https://github.com/bjorngun/Python-APIs/releases/tag/v0.3.8) - 2025-06-20

- Internal improvements and maintenance

## [v0.3.7](https://github.com/bjorngun/Python-APIs/releases/tag/v0.3.7) - 2025-06-04

- Added status badges to README

## [v0.3.6](https://github.com/bjorngun/Python-APIs/releases/tag/v0.3.6) - 2025-06-04

- Fixed bug in bump-version file for handling quotes in pyproject.toml

## [v0.3.5](https://github.com/bjorngun/Python-APIs/releases/tag/v0.3.5) - 2025-06-04

Major release with comprehensive improvements:

### Added

- Linux compatibility and Ubuntu-specific dependencies
- GitHub Actions automation and LDAP3 logging options
- SAP employee model and service with MainJob field
- Schema validation system
- Comprehensive README documentation

### Fixed

- OS-dependent GitHub Actions bugs
- OU service attributes with comprehensive tests
- Various linting issues throughout codebase
- README content and formatting

### Changed

- Updated version detection regex for pyproject.toml
- Migrated from Ruby to Node.js for changelog generation
- Improved OS-dependent dependency management
- Enhanced LDAP connection with OS-specific SASL packages
- Updated PyPI authentication to use tokens instead of username/password
- Added Linux compatibility for Active Directory connections
- Standardized logging and return values for modify_user function

## [v0.1.0](https://github.com/bjorngun/Python-APIs/releases/tag/v0.1.0) - 2022-11-07

- Initial project setup with core configuration files
- Basic project structure and packaging configuration

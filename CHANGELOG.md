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

### Added

- rename_user_cn functionality to ADUserService for renaming user common names
- Python 3.14 support and optimized CI/CD workflows  
- Comprehensive test coverage (100% function coverage with 48 tests)
- Automatic LDAP reconnect/rebind on session expiry or communication errors in `ADConnection`
- Public `rebind()` method on `ADConnection` for explicit re-establishment of the LDAP session
- 8 new unit tests for reconnect behaviour (64 total tests)
- Repository planning and PR workflow skills: `plan-issue`, `pr-create`, and `pr-comments`
- PR template and contributor guidance for SemVer labeling and task-bounded commit workflow
- AD compatibility mode framework with `legacy`, `mixed`, and `strict` modes, including:
  global/env resolution (`PYTHON_APIS_AD_COMPAT_MODE`), service defaults, per-call overrides,
  and runtime introspection helpers for AD services and ADConnection
- Expanded compatibility-mode coverage across AD API and service tests
- Typed, dict-compatible AD response models (`ADResponse`, `ADOperationResponse`, `ADEntry`,
  `ADSearchResponse`) with legacy-key parity, lossless `from_legacy`/`to_dict` adapters, and JSON
  serialization (additive, non-breaking; exported from `python_apis.models`)
- Contract tests pinning AD response model field names, types, dict-compatibility, and JSON
  serializability
- AD operation envelope (`ADOperationEnvelope`) for service write operations with
  compatibility-mode-driven legacy key mirroring (`success`/`result`/`message`), modern fields
  (`operation_kind`, `ldap_result`, `exception_type`/`exception_message`, `request_context`), and
  forward-compatible defaults (`error_code`, `retry_count`, `retried`); wired into
  `ADUserService`, `ADGroupService`, and `ADOrganizationalUnitService` write ops with optional
  per-call `compatibility_mode` overrides (additive, non-breaking; `legacy` returns the historic
  dict unchanged, `mixed` mirrors legacy keys, `strict` omits them)
- Service-layer envelope contract tests across user/group/OU write operations
- Migration guide for the AD operation envelope (`docs/migration/ad-operation-envelope.md`)
- Normalized AD error taxonomy (`python_apis.services.error_taxonomy`) with eight canonical,
  transport-agnostic error codes (`AD_NOT_FOUND`, `AD_VALIDATION_ERROR`, `AD_AUTH_ERROR`,
  `AD_PERMISSION_DENIED`, `AD_CONNECTION_ERROR`, `AD_TIMEOUT`, `AD_CONFLICT`, `AD_UNKNOWN`) and
  pure mapping utilities (`map_exception_to_error_code`, `map_ldap_result_to_error_code`,
  `resolve_error_code`) that classify ldap3/`pydantic` exceptions and LDAP result states, with a
  deterministic `AD_UNKNOWN` fallback
- Automatic population of `ADOperationEnvelope.error_code` for AD write operations in `mixed`/`strict`
  compatibility modes (`legacy` responses remain byte-for-byte unchanged; successful ops carry
  `error_code = None`)
- Unit tests for the AD error taxonomy and its service-layer integration
- Retry telemetry and policy metadata on AD responses (issue #21): `ADOperationEnvelope` now carries
  `would_retry`, `retry_policy`, and a `did_retry` mirror (alongside the existing `retry_count`/
  `retried`), surfaced in `mixed`/`strict` modes (`legacy` responses remain byte-for-byte unchanged)
- `RetryTelemetry` dataclass plus `AD_READ_RETRY_POLICY`/`AD_WRITE_RETRY_POLICY` policy constants and
  `ADConnection.last_retry_telemetry`, capturing per-operation retry outcome (operation kind, attempt
  count, retried/would-retry/recovered, policy) for the auto-reconnect path (read/write classified)
- `finalize_ad_read_response` opt-in helper for structured AD read reporting and retry-telemetry
  threading into AD write finalization across user/group/OU services (default read return types and
  `legacy` behavior unchanged)
- Unit tests for AD retry telemetry capture and read/write retry reporting
- Membership APIs v2 on `ADGroupService` (issue #22): `get_user_direct_groups(user)` returning the
  user's direct group memberships (`list[ADGroup]` via `(&(objectClass=group)(member=<userDN>))`) and
  `resolve_primary_group(user)` resolving the user's primary group (`ADGroup | None` via the group
  `primaryGroupToken` constructed attribute), returning `None` gracefully when the user has no
  `primaryGroupID`; both accept an `ADUser` or string, escape LDAP filter values, and reuse the
  retry-capable read path (additive, backward-compatible)
- Contract tests for the membership APIs covering happy and edge paths

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

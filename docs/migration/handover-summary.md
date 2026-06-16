# Handover: `python-apis` Modernization (Issues #16–#30)

> **Audience:** Teams whose tools depend on `python-apis` but have **not** upgraded since before
> the AD modernization sprint (i.e. still on the `0.4.x` line or earlier).
>
> **Date:** 2026-06-16
>
> **Authoritative policy:** [ADR 0001](../adr/0001-ad-response-modernization.md)

---

## Version facts (verified against PyPI)

| Fact | Value |
| --- | --- |
| Package (PyPI) | [`python-apis`](https://pypi.org/project/python-apis/) |
| Import name | `python_apis` |
| **Current latest release** | **`1.0.0`** (uploaded 2026-06-10) |
| Minimum Python | `>=3.10` |
| Last pre-modernization line | `0.4.x` (last was `0.4.18`, 2026-04-20) |
| Modernization shipped in | `0.5.0` → `1.0.0` (2026-06-09 / 2026-06-10) |
| First breaking (major) release | `1.0.0` — strict-only AD layer (issue #28) |

**What this means for you:** upgrading from any `0.4.x` (or earlier) pin straight to `1.0.0`
applies **every** breaking change in one step. Read **Section A** before bumping.

```bash
pip install --upgrade "python-apis>=1.0.0"
```

---

## TL;DR

The AD layer was modernized in stages under ADR 0001:

- **Stage N / N+1 (issues #17–#27)** — *additive, backward-compatible*. New typed models, v2
  read/membership/batch APIs, error taxonomy, retry telemetry, discoverability. Old code kept
  working.
- **Stage N+2 (issue #28, `1.0.0`, `semver:major`)** — *breaking*. All legacy compatibility
  scaffolding was **removed**; the AD layer is now **strict-only**.
- **Issues #29–#30** — repo process/governance (PR SemVer labels + PR template). No runtime impact.

Full upgrade walkthrough: [`v-major-upgrade.md`](v-major-upgrade.md).

---

## A. Breaking changes — you MUST address these before upgrading to `1.0.0` (#28)

| Removed | Replacement |
| --- | --- |
| `ADConnection.get()` | `ADConnection.get_v2()` → `ADGetResult` |
| Envelope `result` key | `ldap_result` |
| Envelope `message` key | `exception_message` |
| `to_response(mode)` | `to_response()` (no argument; always strict) |
| `compatibility_mode` on all AD service constructors/methods | removed — strict is the only behavior |
| `AD_COMPATIBILITY_MODES`, `AD_DEFAULT_COMPATIBILITY_MODE`, `AD_COMPATIBILITY_ENV_VAR` | removed |
| `resolve_ad_compatibility_mode`, `resolve_service_compatibility_mode`, `ADCompatibilityMode` | removed |
| `ADConnection.compatibility_mode` attribute | removed |
| Discovery `compatibility-modes` capability, `active_compatibility_mode`, `describe_compatibility_modes` | removed |
| `migration_examples.compatibility_mode_selection` | removed |
| `PYTHON_APIS_AD_COMPAT_MODE` environment variable | no longer read |

### 1. AD write methods now always return the strict envelope

Affected: `ADUserService.{enable_user, disable_user, add_member, remove_member, move_user_to_ou,
modify_user, set_password, create_user, rename_user_cn}`, `ADGroupService.modify_group`,
`ADOrganizationalUnitService.modify_ou`.

```python
# Before
resp = service.enable_user(user)
if resp["success"]:
    outcome = resp["result"]        # legacy mirror key
    error   = resp.get("message")   # legacy mirror key

# After (1.0.0)
resp = service.enable_user(user)
if resp["success"]:
    outcome = resp["ldap_result"]       # was result
    error   = resp["exception_message"] # was message
    code     = resp["error_code"]       # normalized taxonomy code on failure
```

Strict envelope keys: `success`, `operation_kind` (`"write"`), `ldap_result`, `exception_type`,
`exception_message`, `request_context`, `retry_count`, `retried`, `would_retry`, `retry_policy`,
`error_code`, `did_retry`, plus operation extras (`changes` / `dn` / `old_dn` / `new_dn`).
There are **no** `result` / `message` keys, and missing keys now raise `KeyError` (the old
empty-default behavior is gone).

### 2. Remove every `compatibility_mode` argument

```python
# Before
service = ADGroupService(ad_conn, sql_conn, compatibility_mode="strict")
service.modify_group(group, changes, compatibility_mode="mixed")

# After (1.0.0)
service = ADGroupService(ad_conn, sql_conn)
service.modify_group(group, changes)
```

`_resolve_effective_mode()` / `get_compatibility_mode()` no longer exist; the
`PYTHON_APIS_AD_COMPAT_MODE` env var is no longer read.

### 3. Replace `get()` with `get_v2()`

```python
# Before — ambiguous absent vs present-but-empty
obj = conn.get("(sAMAccountName=jdoe)", ["cn", "sAMAccountName"])

# After (1.0.0) — deterministic
result = conn.get_v2("(sAMAccountName=jdoe)", ["cn", "sAMAccountName"])
if result.found:
    handle(result.item)
else:
    handle_missing()   # result.not_found_reason == "no_match"
```

Drop-in helper for `Optional[dict]` call sites:

```python
def get_or_none(conn, search_filter, attributes):
    r = conn.get_v2(search_filter, attributes)
    return r.item if r.found else None
```

### 4. Envelope attribute access

`envelope.result` → `envelope.ldap_result`; `envelope.message` → `envelope.exception_message`;
`envelope.to_response("strict")` → `envelope.to_response()`.

### 5. Remove dead imports

Any import of the removed module-level symbols above (from `python_apis.apis` and
`python_apis.services` / `python_apis.services.compatibility_mode`). The `compatibility_mode`
module still exists but exports only `finalize_ad_write_response` / `finalize_ad_read_response`
(strict-only, no `effective_mode`).

> **Read methods are unchanged in return type.** `get_users_from_ad`, etc. keep their historic
> typed returns (`list[ADUser]`, `list[ADGroup]`, …). Only the `compatibility_mode` parameter was
> removed; reads are never silently wrapped in an envelope.

---

## B. New additive APIs — you SHOULD adopt these (Stage N / N+1, #18–#27)

These were introduced backward-compatibly and are the recommended surface going forward.

- **Typed response models (#18):** `ADResponse`, `ADOperationResponse`, `ADEntry`,
  `ADSearchResponse` — dict-compatible, JSON-serializable, from `python_apis.models`.
- **Operation envelope (#19) + error taxonomy (#20):** write ops carry `error_code` from a
  normalized set — `AD_NOT_FOUND`, `AD_VALIDATION_ERROR`, `AD_AUTH_ERROR`, `AD_PERMISSION_DENIED`,
  `AD_CONNECTION_ERROR`, `AD_TIMEOUT`, `AD_CONFLICT`, `AD_UNKNOWN`. Route on the code instead of
  parsing message text.
- **Retry telemetry (#21):** envelopes carry `would_retry`, `retry_policy`, `did_retry`,
  `retry_count`, `retried`; `ADConnection.last_retry_telemetry` exposes per-operation retry
  outcome. Reads retry-once on transient failures; writes never implicitly retry.
- **Membership APIs v2 (#22, #23) on `ADGroupService`:**
  - `get_user_direct_groups(user)` → `list[ADGroup]`
  - `resolve_primary_group(user)` → `ADGroup | None`
  - `get_user_transitive_groups(user)` → `list[ADGroup]` (nested, `LDAP_MATCHING_RULE_IN_CHAIN`)
  - `get_group_members(group)` → `ADMembersPage` (paged; scales to large groups via LDAP ranged
    retrieval)
- **Batch read v2 (#24):** `get_users_from_ad_v2`, `get_groups_from_ad_v2`, `get_ous_from_ad_v2`
  return `ADBatchReadResult` (`returned_items`, `failed_items`, `totals`, `continuation_state`).
  Unlike the legacy list methods, **failed records are surfaced, not silently dropped** (each as
  `ADBatchItemFailure` with `identity`, `failure_classification`, `error_code`,
  `raw_validation_details`). See [`ad-batch-read-v2.md`](ad-batch-read-v2.md).
- **Multivalue dual-form (#25):** `normalize_multivalue(raw, *, delimiter=",")` → `ADMultiValue`
  (`raw`, `values`, `metadata`); `as_legacy_string()` reproduces the historic comma-joined form.
  See [`ad-multivalue-dual-form.md`](ad-multivalue-dual-form.md).
- **`get_v2` typed not-found (#26):** `ADGetResult` (`found`, `item`, `not_found_reason`,
  `error_code`). See [`ad-get-v2.md`](ad-get-v2.md).
- **In-package discoverability (#27):** `python_apis.discovery` (`list_capabilities`,
  `get_capability`, `quick_reference`), `python_apis.deprecation` (`warn_legacy`), and
  `python_apis.migration_examples` (connection-free before/after snippets:
  `legacy_get_to_get_v2`, `list_read_to_batch_v2`, `raw_multivalue_to_dual_form`,
  `error_handling_with_taxonomy`).

---

## C. Process/governance (#29, #30) — contributors only, no runtime impact

If your tool contributes PRs to this repo: every release-relevant PR now requires **exactly one**
SemVer label (`semver:major` / `semver:minor` / `semver:none`), enforced by a CI
`validate-semver-label` check, and the PR template includes SemVer classification guidance.

---

## D. Upgrade checklist

1. Bump to `python-apis>=1.0.0` (current latest is `1.0.0`; Python `>=3.10`).
2. Grep your codebase for: `.get(` on AD connections, `compatibility_mode`, `["result"]` / `.result`,
   `["message"]` / `.message`, `to_response(`, and any removed imports.
3. Apply Section A replacements; run your test suite.
4. Optionally migrate to Section B v2 APIs (especially batch-read v2 to stop losing invalid
   records, and error-code routing).
5. Reference guides in `docs/migration/`: start with [`v-major-upgrade.md`](v-major-upgrade.md),
   then the per-feature guides.

# Major Upgrade Guide: Strict-Only AD Layer (Issue #28)

> SemVer: **major** (breaking)
> Related: [ADR 0001](../adr/0001-ad-response-modernization.md), issue #28
> Supersedes the compatibility-mode behavior in
> [`ad-operation-envelope.md`](ad-operation-envelope.md) and the legacy `get` in
> [`ad-get-v2.md`](ad-get-v2.md).

This release completes ADR 0001 Stage N+2: the AD layer is now **strict-only**. All legacy
compatibility scaffolding has been removed. This guide lists every breaking change with
before/after snippets.

## At a glance

| Removed | Replacement |
| --- | --- |
| `ADConnection.get()` | `ADConnection.get_v2()` → `ADGetResult` |
| `compatibility_mode` on AD service constructors/methods | (removed — strict is the only behavior) |
| Envelope `result` key | `ldap_result` |
| Envelope `message` key | `exception_message` |
| `to_response(mode)` | `to_response()` (no argument) |
| `AD_COMPATIBILITY_MODES`, `AD_DEFAULT_COMPATIBILITY_MODE`, `AD_COMPATIBILITY_ENV_VAR` | (removed) |
| `resolve_ad_compatibility_mode`, `resolve_service_compatibility_mode`, `ADCompatibilityMode` | (removed) |
| `ADConnection.compatibility_mode` attribute | (removed) |
| Discovery `compatibility-modes` capability, `active_compatibility_mode`, `describe_compatibility_modes` | (removed) |
| `migration_examples.compatibility_mode_selection` | (removed) |
| `PYTHON_APIS_AD_COMPAT_MODE` environment variable | (no longer read) |

## 1. AD write methods now always return the strict envelope

Affected methods: `ADUserService.{enable_user, disable_user, add_member, remove_member,
move_user_to_ou, modify_user, set_password, create_user, rename_user_cn}`,
`ADGroupService.modify_group`, `ADOrganizationalUnitService.modify_ou`.

**Before:**

```python
service = ADUserService(ad_connection, sql_connection)  # defaulted to legacy
resp = service.enable_user(user)
if resp["success"]:
    outcome = resp["result"]          # legacy mirror key
    error = resp.get("message")       # legacy mirror key
```

**After:**

```python
service = ADUserService(ad_connection, sql_connection)
resp = service.enable_user(user)
if resp["success"]:
    outcome = resp["ldap_result"]     # was resp["result"]
    error = resp["exception_message"] # was resp["message"]
    code = resp["error_code"]         # normalized taxonomy code on failure
```

The strict envelope keys are: `success`, `operation_kind` (`"write"`), `ldap_result`,
`exception_type`, `exception_message`, `request_context`, `retry_count`, `retried`,
`would_retry`, `retry_policy`, `error_code`, `did_retry`, plus operation extras such as
`changes` / `dn` / `old_dn` / `new_dn` preserved as top-level keys. There are **no** `result`
or `message` keys.

## 2. Drop the `compatibility_mode` parameter everywhere

**Before:**

```python
service = ADGroupService(ad_connection, sql_connection, compatibility_mode="strict")
service.modify_group(group, changes, compatibility_mode="mixed")
```

**After:**

```python
service = ADGroupService(ad_connection, sql_connection)
service.modify_group(group, changes)
```

`_resolve_effective_mode()` and `get_compatibility_mode()` no longer exist. Remove any code
that read or set them. The `PYTHON_APIS_AD_COMPAT_MODE` environment variable is no longer
consulted.

## 3. Replace `ADConnection.get()` with `get_v2()`

**Before:**

```python
obj = conn.get("(sAMAccountName=jdoe)", ["cn", "sAMAccountName"])
if obj.get("sAMAccountName"):
    handle(obj)
else:
    handle_missing()  # ambiguous: absent vs. present-but-empty
```

**After:**

```python
result = conn.get_v2("(sAMAccountName=jdoe)", ["cn", "sAMAccountName"])
if result.found:
    handle(result.item)
else:
    handle_missing()  # deterministic: result.not_found_reason == "no_match"
```

One-line helper for `Optional[dict]` call sites:

```python
def get_or_none(conn, search_filter, attributes):
    result = conn.get_v2(search_filter, attributes)
    return result.item if result.found else None
```

See [`ad-get-v2.md`](ad-get-v2.md) for the full `ADGetResult` contract.

## 4. Envelope API changes (`ADOperationEnvelope`)

**Before:**

```python
envelope.result            # legacy mirror of ldap_result
envelope.message           # legacy mirror of exception_message
payload = envelope.to_response("strict")
```

**After:**

```python
envelope.ldap_result
envelope.exception_message
payload = envelope.to_response()   # no argument; equals to_dict() / model_dump()
```

`to_response()` is strict and never contains `result` / `message`. Missing keys on the
envelope mapping now raise `KeyError` (the old empty-default behavior is gone).

## 5. Removed module-level symbols

These names are no longer importable; remove the imports:

```python
# python_apis.apis
AD_COMPATIBILITY_MODES, AD_DEFAULT_COMPATIBILITY_MODE, AD_COMPATIBILITY_ENV_VAR,
resolve_ad_compatibility_mode

# python_apis.services / python_apis.services.compatibility_mode
ADCompatibilityMode, resolve_service_compatibility_mode,
AD_COMPATIBILITY_MODES, AD_DEFAULT_COMPATIBILITY_MODE, AD_COMPATIBILITY_ENV_VAR
```

`python_apis.services.compatibility_mode` still exists but exports only
`finalize_ad_write_response` and `finalize_ad_read_response`, both strict-only and without an
`effective_mode` parameter.

## 6. Discoverability toolkit

**Before:**

```python
from python_apis.discovery import active_compatibility_mode, describe_compatibility_modes
active_compatibility_mode()
describe_compatibility_modes()
```

**After:** these helpers and the `compatibility-modes` capability have been removed. The
remaining discovery surface (`list_capabilities`, `quick_reference`, etc.) no longer references
modes. Likewise `python_apis.migration_examples.all_examples()` no longer includes
`compatibility_mode_selection`; the remaining examples are `legacy_get_to_get_v2`,
`list_read_to_batch_v2`, `raw_multivalue_to_dual_form`, and `error_handling_with_taxonomy`.

## Read methods are unchanged in return type

AD read methods keep their historic typed returns (`list[ADUser]`, `list[ADGroup]`,
`ADBatchReadResult`, `ADMembersPage`, `ADGetResult`, etc.). Only the `compatibility_mode`
parameter was removed; reads are never silently wrapped in an envelope.

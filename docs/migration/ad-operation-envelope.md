# Migration Guide: AD Operation Envelope (Issue #19)

> Status: **Superseded by Stage N+2 (Issue #28) — the AD layer is now strict-only.**
> Related: [ADR 0001](../adr/0001-ad-response-modernization.md), issues #17, #18, #19, #28

> **⚠️ Stage N+2 update (Issue #28, `semver:major`):** Compatibility modes and the legacy
> `result`/`message` mirror keys have been **removed**. AD write methods now **always** return the
> strict envelope shown under [Current (strict-only) shape](#current-strict-only-shape). The
> `compatibility_mode` parameter no longer exists on any service or method, and `request_context`
> no longer contains a `compatibility_mode` key. The mode/mirror sections below are retained as
> historical context only. For the full upgrade walkthrough see
> [`v-major-upgrade.md`](v-major-upgrade.md).

## Current (strict-only) shape

Write methods (`modify_group`, `modify_user`, `enable_user`, `disable_user`, `add_member`,
`remove_member`, `move_user_to_ou`, `set_password`, `create_user`, `rename_user_cn`, `modify_ou`)
return the strict envelope:

```python
service = ADGroupService(ad_connection, sql_connection)  # no compatibility_mode
result = service.modify_group(group, [("description", "new")])

# {
#     "success": True,
#     "operation_kind": "write",
#     "ldap_result": "ok",          # the old "result" value lives here now
#     "exception_type": None,
#     "exception_message": None,    # the old "message" value lives here now
#     "request_context": {"changes": {"description": "old -> new"}},
#     "retry_count": 0,
#     "retried": False,
#     "would_retry": False,
#     "retry_policy": "ad-write-no-retry",
#     "error_code": None,
#     "did_retry": False,
#     "changes": {"description": "old -> new"},
# }
if result["success"]:
    outcome = result["ldap_result"]   # was result["result"]
```

There are **no** `result` or `message` keys. Read `ldap_result` instead of `result` and
`exception_message` instead of `message`.

---

## Historical context (Stage N / N+1)

The remainder of this guide describes the now-removed compatibility-mode behavior and is kept
for historical reference only.

Issue #19 introduced a consistent **operation envelope** for AD service write
operations, built on the dict-compatible response models from #18. The envelope
adds modern, machine-routable metadata while preserving the legacy dict shape
under the default `legacy` compatibility mode.

This guide shows before/after usage and how each compatibility mode shapes the
returned payload.

## Envelope fields

The envelope (`ADOperationEnvelope`) exposes the following modern fields:

| Field | Type | Notes |
| --- | --- | --- |
| `success` | `bool` | Operation outcome. |
| `operation_kind` | `"read"` \| `"write"` | Distinguishes read vs. write paths. |
| `ldap_result` | `Any` | Raw LDAP result (mirrored as legacy `result`). |
| `exception_type` | `str \| None` | Exception class name when an error was captured. |
| `exception_message` | `str \| None` | Exception text (mirrored as legacy `message`). |
| `request_context` | `dict[str, Any]` | Operation extras (`changes`, `dn`, ...) plus `compatibility_mode`. |
| `retry_count` | `int` | Forward-compatible default `0` (populated by #21). |
| `retried` | `bool` | Forward-compatible default `False` (populated by #21). |
| `error_code` | `str \| None` | Forward-compatible default `None` (taxonomy in #20). |

Legacy mirror keys `success`, `result`, and `message` remain available in
`legacy` and `mixed` modes.

## Compatibility modes at a glance

| Mode | Legacy keys (`result`, `message`) | Modern envelope fields | Stage N default |
| --- | --- | --- | --- |
| `legacy` | Present (dict returned unchanged) | Not added | Yes |
| `mixed` | Present (mirrored) | Present | No (opt-in) |
| `strict` | Omitted | Present | No (opt-in) |

Mode precedence: per-call `compatibility_mode` argument -> service default ->
`PYTHON_APIS_AD_COMPAT_MODE` environment variable -> `legacy` fallback.

## Write path: before / after

### Before (legacy, unchanged default)

```python
service = ADGroupService()  # defaults to legacy
result = service.modify_group(group, [("description", "new")])

# Legacy dict shape is preserved exactly:
# {
#     "success": True,
#     "result": "ok",
#     "changes": {"description": "old -> new"},
# }
if result["success"]:
    ...
```

Existing consumers reading `result["success"]` / `result["result"]` continue to
work with no changes.

### After (opt-in modern envelope)

```python
# Opt in per call ...
result = service.modify_group(
    group, [("description", "new")], compatibility_mode="mixed"
)

# ... or per service instance / environment.
service = ADGroupService(compatibility_mode="mixed")
```

`mixed` mode output (legacy mirrors + modern fields):

```python
{
    "success": True,
    "operation_kind": "write",
    "ldap_result": "ok",
    "result": "ok",            # legacy mirror of ldap_result
    "exception_type": None,
    "exception_message": None,
    "message": None,           # legacy mirror of exception_message
    "request_context": {
        "changes": {"description": "old -> new"},
        "compatibility_mode": "mixed",
    },
    "retry_count": 0,
    "retried": False,
    "error_code": None,
    "changes": {"description": "old -> new"},
}
```

`strict` mode output (modern only; legacy `result`/`message` omitted):

```python
{
    "success": True,
    "operation_kind": "write",
    "ldap_result": "ok",
    "exception_type": None,
    "exception_message": None,
    "request_context": {
        "changes": {"description": "old -> new"},
        "compatibility_mode": "strict",
    },
    "retry_count": 0,
    "retried": False,
    "error_code": None,
    "changes": {"description": "old -> new"},
}
```

### Exception paths

When a write raises an `LDAPException`, the envelope captures the failure
(`mixed`/`strict`):

```python
{
    "success": False,
    "operation_kind": "write",
    "ldap_result": "boom",
    "exception_type": "LDAPException",
    "exception_message": "boom",
    # legacy mirrors `result`/`message` present in mixed, omitted in strict
    ...
}
```

In `legacy` mode the historic shape is preserved unchanged:
`{"success": False, "result": "boom"}`.

## Read path

Read operations already return typed, dict-compatible responses from #18
(`ADEntry` / `ADSearchResponse`). They are intentionally **out of scope** for
envelope conversion in #19 to keep the `semver:minor` contract non-breaking;
`operation_kind` still distinguishes `read` from `write` for the shared builder
and future read adoption. Continue reading entries as mappings:

```python
users = service.get_users_from_ad()  # list[ADUser]
for user in users:
    name = user["sAMAccountName"]  # dict-compatible access
```

## Recommended adoption path

1. Stay on `legacy` (default) — no changes required.
2. Opt into `mixed` to consume modern fields while legacy keys remain mirrored.
3. Move to `strict` once consumers no longer read legacy `result`/`message`.

Legacy mirror removal is gated to a future `semver:major` stage (N+2) per
ADR 0001; do not rely on mirrors being removed before then.

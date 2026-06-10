# Migration Guide: AD Batch Read v2 (Issue #24)

> Status: Additive, non-breaking (SemVer **minor**)
> Related: [ADR 0001](../adr/0001-ad-response-modernization.md), issue #24

Issue #24 introduces **batch read v2** methods for the AD services. The existing
`list`-returning read methods (`get_users_from_ad`, `get_groups_from_ad`,
`get_ous_from_ad`) **silently drop** any record that fails Pydantic validation —
the failure is logged but the caller never sees it. The new v2 methods return a
partial-failure-aware envelope (`ADBatchReadResult`) so no record is silently
dropped.

The legacy `list`-returning methods are **unchanged**. The v2 methods are purely
additive.

## What changed

| Legacy method (unchanged) | New v2 method | Returns |
| --- | --- | --- |
| `ADUserService.get_users_from_ad` | `ADUserService.get_users_from_ad_v2` | `ADBatchReadResult` |
| `ADGroupService.get_groups_from_ad` | `ADGroupService.get_groups_from_ad_v2` | `ADBatchReadResult` |
| `ADOrganizationalUnitService.get_ous_from_ad` | `ADOrganizationalUnitService.get_ous_from_ad_v2` | `ADBatchReadResult` |

## The batch envelope

`ADBatchReadResult` exposes:

| Field | Type | Notes |
| --- | --- | --- |
| `returned_items` | `list` | Successfully validated/built models. |
| `failed_items` | `list[ADBatchItemFailure]` | One entry per record that failed validation. |
| `totals` | `dict[str, int]` | `requested` / `returned` / `failed` counts. |
| `continuation_state` | `Any` | `None` today; reserved for future paged reads. |

Each `ADBatchItemFailure` carries:

| Field | Type | Notes |
| --- | --- | --- |
| `identity` | `str \| None` | Best-effort identity (dn → account id → GUID/SID). |
| `failure_classification` | `str` | Coarse category, currently `"validation"`. |
| `error_code` | `str` | Canonical taxonomy code, e.g. `AD_VALIDATION_ERROR`. |
| `raw_validation_details` | `Any` | Underlying validation error details for diagnostics. |

`ADBatchReadResult.to_dict()` returns a JSON-serializable representation of the
whole envelope.

## Before / after

### Before (legacy list method — failures invisible)

```python
from python_apis.services import ADUserService

service = ADUserService()

users = service.get_users_from_ad("(objectClass=user)")
# users: list[ADUser] — any record that failed validation was logged and dropped.
for user in users:
    print(user.sAMAccountName)
```

### After (batch v2 — failures surfaced)

```python
from python_apis.services import ADUserService

service = ADUserService()

result = service.get_users_from_ad_v2("(objectClass=user)")

# Successful records:
for user in result.returned_items:
    print(user.sAMAccountName)

# Failed records are no longer dropped:
for failure in result.failed_items:
    print(
        f"failed: identity={failure.identity} "
        f"code={failure.error_code} "
        f"class={failure.failure_classification}"
    )
    # failure.raw_validation_details holds the underlying validation errors.

print(result.totals)  # {'requested': N, 'returned': X, 'failed': Y}
```

## Notes

- The v2 methods accept the same `search_filter` and `compatibility_mode`
  arguments as their legacy counterparts.
- `continuation_state` is `None` for now: the full result set is returned in a
  single call. The field exists so a future paged batch read can be added
  without a breaking change.
- Because the change is additive, callers can adopt the v2 methods incrementally;
  existing code that depends on the list signatures keeps working unchanged.

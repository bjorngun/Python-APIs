# Migration Guide: AD Multivalue Dual-Form (Issue #25)

> Status: Additive, non-breaking (SemVer **minor**)
> Related: [ADR 0001](../adr/0001-ad-response-modernization.md), issue #25

Active Directory multivalue attributes (for example `proxyAddresses`, `memberOf`,
`objectClass`) are returned by ldap3 as Python lists. The legacy schema path
(`ADUserSchema`/`ADGroupSchema`/`ADOrganizationalUnitSchema`) flattens every list
into a single comma-joined string, which **loses the raw source value, element
boundaries, and ordering metadata**.

Issue #25 adds an **additive** dual-form representation, `ADMultiValue`, that
preserves the raw value, exposes a deterministically normalized `list[str]`, and
carries metadata. The existing schema field types and their comma-joining
behavior are **unchanged**; the dual-form is opt-in.

## The dual-form contract

`ADMultiValue` exposes:

| Field | Type | Notes |
| --- | --- | --- |
| `raw` | `Any` | Original AD source value, preserved verbatim (list/str/int/None). |
| `values` | `list[str]` | Deterministically normalized list form. |
| `metadata` | `ADMultiValueMetadata` | Source kind and normalization status. |

`ADMultiValueMetadata` carries:

| Field | Type | Notes |
| --- | --- | --- |
| `source` | `"absent" \| "list" \| "scalar" \| "delimited_string"` | Kind of the raw value. |
| `normalized` | `bool` | True when `values` was derived/transformed from `raw`. |
| `count` | `int` | `len(values)`. |
| `delimiter` | `str` | Delimiter used for splitting and the legacy accessor (default `","`). |

`ADMultiValue.as_legacy_string(delimiter=None)` reproduces the historic
delimiter-joined string so existing comma-joined consumers keep working during
the transition. `ADMultiValue.to_dict()` returns a JSON-serializable payload.

## Deterministic normalization rules

`normalize_multivalue(raw, *, delimiter=",")` is deterministic — the same input
always yields identical output. The rules:

1. `None` → `values=[]`, `source="absent"`, `normalized=False`.
2. Empty list `[]` → `values=[]`, `source="list"`, `normalized=True`.
3. `list` → each element `str(el).strip()`; drop elements that are `None` or empty
   after strip; **preserve original order and duplicates**; `source="list"`,
   `normalized=True`.
4. Non-`str` scalar (e.g. `int`) → `values=[str(raw).strip()]` when non-empty;
   `source="scalar"`, `normalized=True`.
5. `str` containing the delimiter → split on the delimiter, `strip()` each, drop
   empties, preserve order and duplicates; `source="delimited_string"`,
   `normalized=True`.
6. `str` without the delimiter → `values=[raw.strip()]` when non-empty else `[]`;
   `source="scalar"`, `normalized=False`.
7. `count = len(values)` in all cases.

## Before / after

### Before (legacy comma-joined string — lossy)

```python
# proxyAddresses came back as ['SMTP:a@x', 'smtp:b@x'] but is flattened to:
raw_value = "SMTP:a@x,smtp:b@x"
addresses = raw_value.split(",")  # caller must guess the delimiter
```

### After (dual-form — raw + normalized + metadata)

```python
from python_apis.models import normalize_multivalue

mv = normalize_multivalue(["SMTP:a@x", "smtp:b@x"])

mv.raw               # ['SMTP:a@x', 'smtp:b@x'] (verbatim)
mv.values            # ['SMTP:a@x', 'smtp:b@x'] (normalized list)
mv.metadata.source   # 'list'
mv.metadata.count    # 2

# Legacy delimited string is still available during the transition:
mv.as_legacy_string()  # 'SMTP:a@x,smtp:b@x'
```

## Notes

- This is purely additive: existing schema fields still return the legacy
  comma-joined string. Adopt the dual-form incrementally where you need the raw
  value or structured list.
- `as_legacy_string()` lets you reproduce the historic representation from the
  dual-form, so a consumer can migrate to `ADMultiValue` without losing the old
  string shape.

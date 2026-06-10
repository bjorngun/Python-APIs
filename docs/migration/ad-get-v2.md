# Migration Guide: AD `get_v2` Typed Not-Found (Issue #26)

> Status: Additive, non-breaking (SemVer **minor**)
> Related: [ADR 0001](../adr/0001-ad-response-modernization.md), issue #26

Issue #26 introduces an **additive** single-object read, `ADConnection.get_v2`.
The legacy `ADConnection.get(search_filter, attributes)` returns the first matched
object as a `dict`, or an empty `collections.defaultdict(lambda: '')` when nothing
matches. That empty default is **indistinguishable** from a real object whose
attributes happen to all be empty, so callers cannot reliably tell "absent" from
"present but empty".

`get_v2` returns an `ADGetResult` envelope with an explicit `found` flag plus a
deterministic `not_found_reason`. The legacy `get` is **unchanged**; `get_v2` is
purely additive.

## What changed

| Legacy method (unchanged) | New v2 method | Returns |
| --- | --- | --- |
| `ADConnection.get` | `ADConnection.get_v2` | `ADGetResult` |

## The result envelope

`ADGetResult` (exported from `python_apis.models`) exposes:

| Field | Type | Notes |
| --- | --- | --- |
| `found` | `bool` | `True` when an object matched and is present in `item`. |
| `item` | `Any` | Matched AD object mapping (first match when several matched); `None` when absent. |
| `not_found_reason` | `"no_match" \| None` | Deterministic absence reason; `None` when found. |
| `error_code` | `str \| None` | Canonical taxonomy code for the absence (`"AD_NOT_FOUND"`); `None` when found. |

Constructors: `ADGetResult.found_item(item)` and `ADGetResult.not_found(reason="no_match")`.
`ADGetResult.to_dict()` returns a plain dict view of the envelope.

## Deterministic not-found semantics

`get_v2` is deterministic — the same search always yields the same envelope shape:

1. Search returns **zero** rows → `found=False`, `item=None`,
   `not_found_reason="no_match"`, `error_code="AD_NOT_FOUND"`.
2. Search returns **one or more** rows → `found=True`, `item` is the **first**
   matched object (matching legacy `get`), `not_found_reason=None`,
   `error_code=None`.

## Before / after

**Before (legacy, ambiguous):**

```python
obj = conn.get("(sAMAccountName=jdoe)", ["cn", "sAMAccountName"])
# Empty default and "present but empty" look identical:
if obj.get("sAMAccountName"):
    handle(obj)
else:
    handle_missing()  # could be either "absent" or "present but empty"
```

**After (typed, unambiguous):**

```python
result = conn.get_v2("(sAMAccountName=jdoe)", ["cn", "sAMAccountName"])
if result.found:
    handle(result.item)
else:
    handle_missing()  # deterministic: result.not_found_reason == "no_match"
```

## Migration helper

To adopt `get_v2` at an existing `Optional[dict]` call site with a one-line change,
wrap it to return the matched mapping or `None`:

```python
def get_or_none(conn, search_filter, attributes):
    result = conn.get_v2(search_filter, attributes)
    return result.item if result.found else None
```

See [`examples/get_v2.py`](../../examples/get_v2.py) for runnable usage, including a
connection-free envelope demo and a migration helper.

## SemVer impact

Additive and backward-compatible → **minor**. The legacy `get` keeps its exact
behavior; no existing call site needs to change.

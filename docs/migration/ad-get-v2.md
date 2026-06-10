# Migration Guide: AD `get_v2` Typed Not-Found (Issue #26)

> Status: **Stage N+2 (Issue #28): legacy `get` removed — `get_v2` is now the only single-object read.**
> Related: [ADR 0001](../adr/0001-ad-response-modernization.md), issues #26, #28

> **⚠️ Stage N+2 update (Issue #28, `semver:major`):** `ADConnection.get()` has been **removed**.
> `ADConnection.get_v2()` returning an `ADGetResult` is now the single canonical single-object
> read. Replace every `conn.get(...)` call with `conn.get_v2(...)` (see
> [Before / after](#before--after) and the [migration helper](#migration-helper)).

Issue #26 introduced an **additive** single-object read, `ADConnection.get_v2`.
The former `ADConnection.get(search_filter, attributes)` returned the first matched
object as a `dict`, or an empty `collections.defaultdict(lambda: '')` when nothing
matched. That empty default was **indistinguishable** from a real object whose
attributes happen to all be empty, so callers could not reliably tell "absent" from
"present but empty". As of #28 that ambiguous `get` is gone.

`get_v2` returns an `ADGetResult` envelope with an explicit `found` flag plus a
deterministic `not_found_reason`.

## What changed

| Removed in #28 | Replacement | Returns |
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

**Before (removed legacy `get`, ambiguous):**

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

Removing `ADConnection.get` is **breaking** → **major** (shipped under #28). `get_v2` itself was
introduced additively in #26 (minor); after #28 it is the only single-object read.

# Active Directory Connection Resilience

`ADConnection` provides configurable LDAP timeouts, paging, search overrides, bounded whole-query
read retries, controller-aware rebinding, and safe retry telemetry. These features are independent
of any consumer database or ORM model.

Issue #52 changes write retry from implicit retry-once to disabled by default. That behavior change
requires a major release. Read retry remains enabled once by default.

## Connection Configuration

The first three constructor arguments retain their existing positional behavior. New options are
keyword-only:

```python
from python_apis.apis import ADConnection

connection = ADConnection(
    ["ldap01.example.com", "ldap02.example.com"],
    "DC=example,DC=com",
    False,
    receive_timeout=30,
    connect_timeout=5,
    page_size=500,
    read_retry_count=1,
    read_retry_backoff_seconds=0.5,
    write_retry_count=0,
)
```

| Option | Default | Validation | Applied to |
| --- | ---: | --- | --- |
| `receive_timeout` | `10` | Positive finite number | `ldap3.Connection` response wait |
| `connect_timeout` | `None` | `None` or positive finite number | Every configured `ldap3.Server` |
| `page_size` | `500` | Positive integer | Paged searches without an override |
| `read_retry_count` | `1` | Non-negative integer | Retries after the initial read attempt |
| `read_retry_backoff_seconds` | `0` | Non-negative finite number | Delay between failed read attempts |
| `write_retry_count` | `0` | Non-negative integer | Explicit write retry opt-in |

Validation happens before an LDAP `Server` or `Connection` is created. Manual `rebind()` and
automatic retry rebinding reuse the validated options.

## Search Overrides and Precedence

`search()` retains `search(filter, attributes)` and adds keyword-only overrides:

```python
from ldap3 import LEVEL

organizational_units = connection.search(
    "(objectClass=organizationalUnit)",
    ["distinguishedName", "description"],
    search_base="OU=Departments,DC=example,DC=com",
    search_scope=LEVEL,
    page_size=200,
)
```

Precedence is:

1. A per-search `search_base` or `page_size` override.
2. The connection's configured search base or page size.

`search_scope` defaults to `SUBTREE`; supported values are the standard `ldap3` constants `BASE`,
`LEVEL`, and `SUBTREE`. Overrides apply to one call and do not mutate connection settings.

## Server Pools Versus Whole-Query Retry

A server pool selects a controller while establishing a connection. It does not restart a paged
query when that established connection fails after one or more pages.

`ADConnection.search()` protects the complete lazy paged generator:

1. Start the paged query.
2. Materialize every returned entry for that attempt.
3. On `LDAPCommunicationError` or `LDAPSessionTerminatedByServerError`, discard the attempt's local
   entries.
4. Close the failed connection where possible.
5. Prefer another configured controller when the bound controller is known.
6. Apply configured read backoff and bind a fresh connection.
7. Restart the query at page one.
8. Return only after a complete attempt succeeds.

Partial entries are discarded because returning them would make absence ambiguous and could produce
an incomplete synchronization without an error. When retries are exhausted, the final recoverable
LDAP exception is raised.

`read_retry_count=0` disables read retry. The default `1` permits two total attempts. Larger values
remain bounded by the configured count.

## Read and Write Safety

Reads can normally be repeated because they do not change directory state. Writes are different: a
controller can apply a write and lose the response. Retrying then may apply the change twice or
produce a conflict.

For that reason, `write_retry_count=0` is the default. Set a positive value only when the individual
operation is idempotent or the caller explicitly accepts duplicate-side-effect risk:

```python
# Explicit opt-in; do not use without an operation-specific idempotency decision.
connection = ADConnection(
    servers,
    search_base,
    write_retry_count=1,
)
```

Upgrading from a release that retried writes implicitly requires reviewing every write path. Do not
turn retries on globally merely to reproduce the old behavior.

## Controller Rotation and Backoff

After a recoverable failure, automatic retry rebinding orders configured alternatives before the
failed controller when it can identify the bound host. A single-controller configuration still
retries against that controller. Manual `rebind()` continues to use the original configured order.

Backoff applies after closing the failed connection and before the fresh bind. The default is zero;
choose a non-zero delay from observed controller and network recovery behavior rather than treating
it as a universal tuning value.

## Retry Telemetry

After a decorated operation, inspect `connection.last_retry_telemetry`. Existing fields remain and
new fields are additive:

| Field | Meaning |
| --- | --- |
| `operation_kind` | `read` or `write` classification |
| `operation_name` | Decorated method name |
| `attempt_count` | Operation invocations made |
| `retry_count` | Retries initiated after the first attempt |
| `retried` | Whether a retry was initiated |
| `would_retry` | Whether a recoverable failure entered the enabled retry path |
| `recovered` | Whether a later attempt succeeded |
| `failed_server` | Masked token for the last failed controller |
| `selected_server` | Masked token for the currently selected controller |
| `elapsed_seconds` | Monotonic elapsed operation time |
| `exception_type` | Last recoverable LDAP exception type, when present |
| `policy` | Attempts, retries, strategy, recoverable types, and backoff |

Server fields are stable `controller-<hash>` tokens. They are suitable for correlation but are not
raw hostnames. Telemetry policy dictionaries are copied per operation, so caller mutation does not
change package defaults.

No-retry success, recovered retry, and exhausted retry all leave telemetry available. Read it before
starting another decorated operation because the property always describes the most recent one.

## Safe Bind Errors and Logging

Connection failures have distinct public errors:

```python
from python_apis.apis import ADBindError, ADMissingServersError

try:
    connection = ADConnection(servers, search_base)
except ADMissingServersError:
    handle_missing_configuration()
except ADBindError as error:
    report_bind_failure(error.result_code, error.controller)
```

`ADBindError` contains an LDAP result code when available and a masked controller token. If
`ldap3` raises during bind, the original exception is preserved as `__cause__`; its text is not
copied into the safe public message.

Normal retry logs include operation, exception type, attempt number, and masked controller token.
Do not add credentials, complete records, raw user DNs, or raw controller names to consumer logs.

## Complete Example

See [`examples/ad_resilient_search.py`](../examples/ad_resilient_search.py) for an environment-based
example that performs a resilient read and reports only aggregate count and masked telemetry.

OU-tree retrieval and caller-defined inheritance are documented in the
[AD resilience and OU inheritance migration guide](migration/ad-resilience-ou-inheritance.md).

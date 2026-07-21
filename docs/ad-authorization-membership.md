# Fail-Closed AD Authorization Membership

`ADMembershipService` provides strict AD-only reads for consumers that maintain authorization
snapshots outside their normal request path. It does not schedule refreshes, cache directory data,
define database tables, or write snapshots.

## Read Transitive Enabled Users

```python
from python_apis.services import ADMembershipService

membership = ADMembershipService(connection)
result = membership.get_transitive_enabled_group_members(configured_group_id)
```

The method:

1. Resolves the group's current DN from its stable `sAMAccountName` on every refresh.
2. Escapes every caller/directory value before filter interpolation.
3. Uses AD matching-rule-in-chain to expand nested membership server-side.
4. Uses AD bitwise matching to exclude disabled accounts.
5. Filters to person/user objects so groups, computers, and contacts are not returned as users.
6. Reads all normal LDAP pages through `search_strict()`.
7. Returns unique deterministic casefolded `sAMAccountName` values.

A group move between OUs is safe because the DN is not accepted or cached as the public identifier.

## Outcome Contract

`ADGroupMembersResult` separates directory state from operational failure:

| Outcome | Contract | Snapshot action |
| --- | --- | --- |
| Existing group with members | `group_found=True`, non-empty `members` | Atomically replace with returned members. |
| Existing empty group | `group_found=True`, `members=()` | Atomically replace with the valid empty snapshot. |
| Missing group | `group_found=False`, `error_code="AD_NOT_FOUND"` | Do not replace; alert/configure according to consumer policy. |
| Bind/TLS/timeout/transport/rejected/malformed failure | Safe typed exception with stable `error_code` | Do not replace; retain the previous snapshot. |

Do not infer success from `len(result.members)`. Check `group_found` first and let raised read
failures abort the refresh.

## Consumer-Owned Atomic Replacement

The persistence transaction starts only after a complete successful read:

```python
from python_apis.apis import ADReadError

try:
    result = membership.get_transitive_enabled_group_members(configured_group_id)
except ADReadError as error:
    logger.error("Authorization refresh failed: error_code=%s", error.error_code)
    return

if not result.group_found:
    logger.error("Authorization refresh skipped: error_code=%s", result.error_code)
    return

with database.transaction():
    snapshot_repository.replace(result.members)
```

The consumer owns the exact transaction, group-to-snapshot key, timestamps, audit metadata,
scheduler, refresh lock, and behavior when one of several configured groups fails. Do not log the
configured group ID or member identities.

## Retry and Paging

Strict paged reads restart the complete query after one recoverable communication/session failure
by default. Entries from an interrupted attempt are discarded. Exhaustion raises `ADTransportError`
instead of returning partial or empty success. Writes still default to no automatic retry.

Capture `connection.last_retry_telemetry` immediately after the operation if aggregate attempt,
recovery, elapsed-time, and masked controller metadata is needed.

## Rollout

1. Configure [explicit validated LDAPS](ad-secure-connection.md) and the chosen authentication mode.
2. Keep the existing consumer wrapper behind a rollback switch.
3. Run old/new reads without snapshot writes and compare protected identity-set results.
4. Test direct/nested members, disabled users, non-user members, empty group, missing group, moved
   group, multiple pages, bind/TLS failure, rejected query, and partial-page interruption.
5. Prove every failure leaves the previous database snapshot unchanged.
6. Canary atomic replacement, observe aggregate diagnostics, then cut over.
7. Remove the consumer wrapper only after parity and operational acceptance.

See [the authorization membership example](../examples/authorization_membership.py) for an
injectable persistence boundary.

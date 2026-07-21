# Migrate to AD Resilience and OU Inheritance

This guide migrates an AD synchronization project from a local LDAP connection and per-object OU
lookups to the shared, consumer-neutral `python-apis` connection and OU service.

The release containing issue #52 is a major release because write operations no longer retry
implicitly. Connection/search additions and OU APIs are otherwise additive. Pin the tested release
explicitly before rollout.

## Ownership Boundaries

`ADConnection` owns:

- LDAP server and TLS setup.
- Connect and receive timeouts.
- Paging, search base, and search scope.
- Complete-query read retry, controller rotation, backoff, and telemetry.
- Low-level LDAP reads and writes.

`ADOrganizationalUnitService` owns:

- One-query OU-tree retrieval.
- LDAP-aware parent/child construction.
- Generic inherited-attribute rules.
- Ordered bulk resolution.

Consumers own:

- Target output names and organization-specific defaults.
- Normalization and acceptance callables.
- Local models and explicit application of returned values.
- OU-tree lifetime, feature switches, and transaction boundaries.

## Replace a Local Connection

A local implementation commonly hardcodes paging and handles only connection establishment:

```python
# Before: consumer-owned paging and timeout behavior.
entries = local_connection.get_paged_search(
    search_base=search_base,
    search_filter="(objectClass=user)",
    page_size=500,
)
```

Use the shared connection with explicit environment-appropriate settings:

```python
from python_apis.apis import ADConnection

connection = ADConnection(
    servers,
    search_base,
    receive_timeout=30,
    connect_timeout=5,
    page_size=500,
    read_retry_count=1,
    read_retry_backoff_seconds=0.5,
    write_retry_count=0,
)

entries = connection.search(
    "(objectClass=user)",
    ["distinguishedName", "sAMAccountName"],
)
```

The complete paged generator is materialized inside the retry boundary. A recoverable failure after
partial pages discards that attempt and restarts from page one. See
[`docs/ad-resilience.md`](../ad-resilience.md) for policy and telemetry details.

## Create an AD-Only OU Service

OU hierarchy operations do not require a SQL connection:

```python
from python_apis.services import ADOrganizationalUnitService

ou_service = ADOrganizationalUnitService.for_active_directory(connection)
```

The legacy constructor remains available for callers that use the service's database methods.
`for_active_directory()` initializes no SQL connection and reads no SQL environment settings.

## Define Consumer-Owned Rules

Rule dictionary keys are caller-selected output names. The package does not know consumer columns or
organization defaults:

```python
from python_apis.services import OUAttributeRule


def remove_hyphens(value: object) -> str:
    return str(value).replace("-", "")


def is_numeric_text(value: object) -> bool:
    return str(value).isdigit()


rules = {
    "department_code": OUAttributeRule(
        source="description",
        normalize=remove_hyphens,
        accept=is_numeric_text,
        default=None,
    ),
    "office_phone": OUAttributeRule(
        source="telephoneNumber",
        default=None,
    ),
    "office_address": OUAttributeRule(
        source="street",
        aliases=("streetAddress",),
        default=None,
    ),
    "postal_code": OUAttributeRule(
        source="postalCode",
        default=None,
    ),
}
```

For each target, resolution starts at the immediate OU and walks toward the root. At each OU it
checks the source then aliases, skips null/empty candidates, normalizes, applies the acceptance
predicate, and returns the first accepted value. The default is returned only after the path is
exhausted.

Description hyphens are preserved in the OU tree. Removing them is a rule decision, as shown above,
rather than a global schema transform.

## Load and Reuse One OU Tree

Request every source and alias used by the rules:

```python
attributes = [
    attribute
    for rule in rules.values()
    for attribute in (rule.source, *rule.aliases)
]
ou_tree = ou_service.get_ou_tree(
    attributes=attributes,
    search_base=None,
)
```

`distinguishedName` is added automatically. The method performs one `SUBTREE` search and returns a
`dict[str, ADOrganizationalUnit]` keyed by DN.

For $n$ OUs and $m$ objects, tree construction is $O(n)$ after LDAP materialization. Resolution is
in memory and proportional to each object's ancestor depth. Load one tree per synchronization run
unless the consumer has a deliberate refresh policy. The package does not impose a process-global
cache.

## Resolve Many Objects Without Mutation

Mappings can name their OU field directly:

```python
resolved_rows = ou_service.resolve_inherited_attributes_for_objects(
    rows,
    rules,
    distinguished_name_attribute="organizational_unit_dn",
    ou_tree=ou_tree,
)
```

Plain objects can use a callback:

```python
resolved_rows = ou_service.resolve_inherited_attributes_for_objects(
    objects,
    rules,
    get_ou_dn=lambda item: item.organizational_unit_dn,
    ou_tree=ou_tree,
)
```

Output order matches input order. Repeated OUs reuse resolution internally, but every input receives
a separate dictionary. The service does not mutate objects:

```python
for item, values in zip(objects, resolved_rows):
    for target, value in values.items():
        setattr(item, target, value)
```

Keep this explicit application inside the consumer's transaction and only after parity checks pass.

## Error Behavior

- `ADOrganizationalUnitTreeError` aborts tree construction for invalid records, missing/malformed
  DNs, or duplicate DNs. No malformed batch entry is silently dropped.
- Missing parent records leave valid root/orphan nodes and do not abort the tree.
- `OUInheritanceCycleError` aborts resolution when parent links cycle.
- Missing object OU DNs in bulk input raise an index-only `ValueError`.
- An unknown but non-empty starting OU DN resolves rule defaults.

Do not continue a synchronization with an incomplete tree after `ADOrganizationalUnitTreeError`.
That could silently apply defaults where real ancestor values exist.

## Breaking Changes to Review

Before pinning the new major release, review:

1. Writes default to `write_retry_count=0`; prior releases retried once implicitly.
2. OU descriptions retain hyphens; consumer rules must request any normalization.
3. `parent_ou_distinguished_name` now removes the complete first RDN and is LDAP-aware.
4. Search-result `ou` extraction is LDAP-aware for escaped or multi-valued object RDNs.

Legacy constructor/search call shapes and existing exports remain available.

## Staged Rollout

### Stage 1: Shared Reads

- Pin the exact candidate package release.
- Create a feature switch between the local and shared read connection.
- Run both against representative data without writing warehouse changes.
- Compare total count and a stable identity set, not result order alone.
- Inject a recoverable failure after partial pages and verify the final set matches a clean run.

### Stage 2: Shared OU Tree

- Load one tree per run.
- Compare OU DNs, parent DNs, orphan counts, and escaped-DN cases with the current hierarchy.
- Treat malformed/duplicate failures as run failures.

### Stage 3: Rule Parity

- Define consumer target names/defaults outside the package.
- Resolve representative objects through old and new logic.
- Compare every target field, including rejected child values, aliases, and defaults.
- Do not mutate persistent objects until parity is accepted.

### Stage 4: Canary Cutover

- Enable the shared path for a bounded run or environment.
- Monitor attempts, retries, recovery, elapsed time, and masked controller transitions.
- Keep write retry disabled unless an operation-specific review explicitly opts in.
- Retain the prior package pin and feature switch for rollback.

### Stage 5: Remove Local Code

- Remove the local AD connection only after read, tree, and rule parity pass.
- Keep consumer models, defaults, mutation, and transactions in the consumer repository.
- Record the tested package version and operational settings in the consumer handover.

## Verification Checklist

- Legacy positional constructor calls still import and initialize.
- `search(filter, attributes)` retains list return behavior.
- Receive/connect timeouts and page size reach `ldap3`.
- Failures before and after partial pages restart the complete read.
- Exhaustion raises the final recoverable exception.
- Telemetry is correct for no-retry, recovered, and exhausted operations.
- Alternate-controller preference and masked logs work in the deployment environment.
- The OU tree uses one query and preserves escaped DNs.
- Rules match existing target values and defaults.
- Bulk resolution performs no LDAP request per object and preserves order.
- Database writes remain under the consumer's transaction and rollback policy.

See [`examples/ou_inheritance.py`](../../examples/ou_inheritance.py) for a complete neutral example.

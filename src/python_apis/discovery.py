"""In-package discoverability toolkit for modernized AD behavior (issue #27).

This module lets users and agents understand the modernized, additive AD
behaviors **from the Python REPL and IDE hints alone**, without needing to
visit the GitHub docs under ``docs/migration/`` or ``docs/adr/``.

It provides:

* A runtime **capability registry** describing each modernized behavior, its
  public entry points, and its legacy-to-v2 migration note
  (:func:`list_capabilities`, :func:`get_capability`).
* A printable **quick reference** cheat sheet (:func:`quick_reference`,
  :func:`print_quick_reference`).

Everything here is pure Python over already-public names; calling any function
needs no AD connection and adds no new dependencies.

Example:
    >>> from python_apis import discovery
    >>> names = [cap["name"] for cap in discovery.list_capabilities()]
    >>> "get-v2" in names
    True
"""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Capability:
    """One modernized AD behavior described for runtime discovery.

    Attributes:
        name: Stable short identifier (for example ``"get-v2"``).
        summary: One-sentence description of the behavior.
        since_issue: GitHub issue number that introduced the behavior.
        entry_points: Importable public symbols in ``module:attr`` form, where
            ``attr`` may be a dotted path (for example
            ``python_apis.services:ADGroupService.get_group_members``).
        legacy: Legacy API the behavior modernizes, or ``None`` if net-new.
        migration: One-line legacy-to-v2 migration note.
        example: Reference to a runnable example (repo path or in-package func).
    """

    name: str
    summary: str
    since_issue: int
    entry_points: tuple[str, ...]
    legacy: str | None
    migration: str
    example: str

    def to_dict(self) -> dict[str, Any]:
        """Return a plain, JSON-serializable ``dict`` of this capability."""

        return {
            "name": self.name,
            "summary": self.summary,
            "since_issue": self.since_issue,
            "entry_points": list(self.entry_points),
            "legacy": self.legacy,
            "migration": self.migration,
            "example": self.example,
        }


AD_CAPABILITIES: tuple[Capability, ...] = (
    Capability(
        name="operation-envelope",
        summary=(
            "Typed, dict-compatible AD operation envelope exposing structured "
            "metadata (strict-only since the Stage 3 cleanup)."
        ),
        since_issue=19,
        entry_points=(
            "python_apis.models:ADOperationEnvelope",
            "python_apis.models:ADResponse",
        ),
        legacy="dict with 'success'/'result'/'message' keys",
        migration=(
            "AD writes now return a strict ADOperationEnvelope; read 'ldap_result' "
            "and 'error_code' instead of the removed 'result'/'message' keys."
        ),
        example="docs/migration/ad-operation-envelope.md",
    ),
    Capability(
        name="error-taxonomy",
        summary="Canonical AD error codes and a single resolver for operation outcomes.",
        since_issue=20,
        entry_points=(
            "python_apis.services.error_taxonomy:AD_ERROR_CODES",
            "python_apis.services.error_taxonomy:resolve_error_code",
        ),
        legacy="raw ldap3 exceptions / result dicts",
        migration=(
            "Classify failures with resolve_error_code(...) instead of matching "
            "ldap3 exception types by hand."
        ),
        example="python_apis.migration_examples.error_handling_with_taxonomy()",
    ),
    Capability(
        name="membership-apis",
        summary="Transitive group membership and paged group-member reads.",
        since_issue=22,
        entry_points=(
            "python_apis.services:ADGroupService.get_user_direct_groups",
            "python_apis.services:ADGroupService.get_user_transitive_groups",
            "python_apis.services:ADGroupService.resolve_primary_group",
            "python_apis.services:ADGroupService.get_group_members",
            "python_apis.models:ADMembersPage",
        ),
        legacy="manual nested-group walking / unpaged member reads",
        migration=(
            "Use get_group_members(...) for an ADMembersPage with page_info / "
            "has_next_page instead of reading 'member' directly."
        ),
        example="examples/membership_apis.py",
    ),
    Capability(
        name="batch-read-v2",
        summary=(
            "Partial-failure-aware batch reads that surface failed records instead "
            "of silently dropping them."
        ),
        since_issue=24,
        entry_points=(
            "python_apis.services:ADUserService.get_users_from_ad_v2",
            "python_apis.services:ADGroupService.get_groups_from_ad_v2",
            "python_apis.services:ADOrganizationalUnitService.get_ous_from_ad_v2",
            "python_apis.models:ADBatchReadResult",
        ),
        legacy="get_users_from_ad / get_groups_from_ad / get_ous_from_ad (list)",
        migration=(
            "Switch to get_*_from_ad_v2 and read returned_items / failed_items "
            "from the ADBatchReadResult envelope."
        ),
        example="examples/batch_read_v2.py",
    ),
    Capability(
        name="multivalue-dual-form",
        summary=(
            "Dual-form AD multivalue attributes: raw value + normalized list + "
            "source metadata."
        ),
        since_issue=25,
        entry_points=(
            "python_apis.models:ADMultiValue",
            "python_apis.models:normalize_multivalue",
        ),
        legacy="comma-joined string from the schema layer",
        migration=(
            "Wrap raw values with normalize_multivalue(...); use as_legacy_string() "
            "to reproduce the historic comma-joined string."
        ),
        example="examples/multivalue_dual_form.py",
    ),
    Capability(
        name="get-v2",
        summary=(
            "Typed single-object read with an explicit found/not-found envelope."
        ),
        since_issue=26,
        entry_points=(
            "python_apis.apis:ADConnection.get_v2",
            "python_apis.models:ADGetResult",
        ),
        legacy="ADConnection.get (removed in the Stage 3 cleanup)",
        migration=(
            "Use get_v2(...) and branch on result.found instead of probing an "
            "empty default mapping; the legacy get(...) no longer exists."
        ),
        example="examples/get_v2.py",
    ),
)


def list_capabilities() -> list[dict[str, Any]]:
    """Return all modernized AD capabilities as JSON-serializable dicts."""

    return [capability.to_dict() for capability in AD_CAPABILITIES]


def get_capability(name: str) -> dict[str, Any]:
    """Return one capability record by ``name``.

    Args:
        name: A capability identifier (see :func:`list_capabilities`).

    Returns:
        The capability record as a dict.

    Raises:
        KeyError: If ``name`` is unknown; the message lists available names.
    """

    for capability in AD_CAPABILITIES:
        if capability.name == name:
            return capability.to_dict()
    available = ", ".join(capability.name for capability in AD_CAPABILITIES)
    raise KeyError(f"Unknown capability '{name}'. Available: {available}")


def quick_reference() -> str:
    """Return a printable cheat sheet for the modernized AD behaviors.

    The string lists each capability with its primary entry point and migration
    note, so the whole surface is discoverable from a single REPL call.
    """

    lines: list[str] = [
        "python_apis - AD modernization quick reference",
        "=" * 46,
        "",
        "Capabilities (legacy -> v2):",
    ]
    for capability in AD_CAPABILITIES:
        primary = capability.entry_points[0] if capability.entry_points else "-"
        legacy = capability.legacy or "(net-new)"
        lines.append(f"  - {capability.name} (#{capability.since_issue})")
        lines.append(f"      {capability.summary}")
        lines.append(f"      from   : {legacy}")
        lines.append(f"      use    : {primary}")
        lines.append(f"      hint   : {capability.migration}")
    lines.append("")
    lines.append(
        "Discover more: python_apis.discovery.list_capabilities(); "
        "python_apis.migration_examples.print_all()."
    )
    return "\n".join(lines)


def print_quick_reference() -> None:
    """Print the :func:`quick_reference` cheat sheet to stdout."""

    print(quick_reference())


__all__ = [
    "Capability",
    "AD_CAPABILITIES",
    "list_capabilities",
    "get_capability",
    "quick_reference",
    "print_quick_reference",
]

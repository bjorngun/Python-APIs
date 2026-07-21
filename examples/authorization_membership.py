"""Refresh an authorization snapshot through a consumer-owned persistence callback."""

from collections.abc import Callable
from typing import Literal

from python_apis.models import ADGroupMembersResult
from python_apis.services import ADMembershipService

SnapshotStatus = Literal["updated", "group_not_found"]
ReplaceSnapshot = Callable[[tuple[str, ...]], None]


def apply_membership_result(
    result: ADGroupMembersResult,
    replace_snapshot: ReplaceSnapshot,
) -> SnapshotStatus:
    """Replace a snapshot only for a complete found-group result."""

    if not result.group_found:
        return "group_not_found"
    replace_snapshot(result.members)
    return "updated"


def refresh_authorization_snapshot(
    membership: ADMembershipService,
    group_id: str,
    replace_snapshot: ReplaceSnapshot,
) -> SnapshotStatus:
    """Read strict membership, then invoke consumer persistence on success only.

    Safe typed AD read exceptions intentionally propagate before the callback is
    reached, leaving the consumer's previous snapshot untouched.
    """

    result = membership.get_transitive_enabled_group_members(group_id)
    return apply_membership_result(result, replace_snapshot)


__all__ = [
    "ReplaceSnapshot",
    "SnapshotStatus",
    "apply_membership_result",
    "refresh_authorization_snapshot",
]

"""Structured deprecation warnings with actionable migration hints (issue #27).

Modernized AD behaviors are additive: legacy entry points keep working, but a
structured :class:`DeprecationWarning` points callers at the modern replacement
so the migration is discoverable at runtime. The warning text alone names the
legacy symbol, its replacement, and a concrete migration hint, so no external
docs are required to act on it.

Example:
    >>> import warnings
    >>> from python_apis.deprecation import warn_legacy
    >>> with warnings.catch_warnings(record=True) as caught:
    ...     warnings.simplefilter("always")
    ...     msg = warn_legacy(
    ...         "ADConnection.get",
    ...         replacement="ADConnection.get_v2",
    ...         migration_hint="Branch on result.found instead of an empty mapping.",
    ...     )
    >>> "ADConnection.get_v2" in msg
    True
"""

import warnings


def build_legacy_message(
    legacy: str,
    *,
    replacement: str,
    migration_hint: str,
    since: str | None = None,
) -> str:
    """Build a single-line, actionable legacy-migration message.

    Args:
        legacy: The legacy symbol being used (for example ``"ADConnection.get"``).
        replacement: The modern replacement symbol to adopt.
        migration_hint: A concrete, actionable hint describing the change.
        since: Optional version/issue marker for when ``legacy`` was superseded.

    Returns:
        The composed message string.
    """

    since_part = f" (since {since})" if since else ""
    return (
        f"{legacy} is legacy{since_part}; use {replacement} instead. "
        f"Migration: {migration_hint}"
    )


def warn_legacy(  # pylint: disable=too-many-arguments
    legacy: str,
    *,
    replacement: str,
    migration_hint: str,
    since: str | None = None,
    category: type[Warning] = DeprecationWarning,
    stacklevel: int = 2,
) -> str:
    """Emit a structured legacy-migration warning and return its message.

    The emitted warning carries the same text returned by
    :func:`build_legacy_message`, so the migration is actionable from the
    warning alone. The call is purely informational and does not change the
    behavior of the legacy code path.

    Args:
        legacy: The legacy symbol being used.
        replacement: The modern replacement symbol to adopt.
        migration_hint: A concrete, actionable migration hint.
        since: Optional version/issue marker for when ``legacy`` was superseded.
        category: Warning category to emit (default :class:`DeprecationWarning`).
        stacklevel: Stack level so the warning points at the caller's call site.

    Returns:
        The warning message that was emitted.
    """

    message = build_legacy_message(
        legacy,
        replacement=replacement,
        migration_hint=migration_hint,
        since=since,
    )
    warnings.warn(message, category=category, stacklevel=stacklevel + 1)
    return message


__all__ = [
    "build_legacy_message",
    "warn_legacy",
]

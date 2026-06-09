"""Normalized AD error taxonomy and mapping utilities (ADR 0001, Stage N).

This module defines a small, stable set of canonical error codes for Active
Directory operations and (in later tasks) utilities that map ldap3 exceptions,
``pydantic`` validation errors, and raw LDAP result states onto those codes.

The canonical codes are intentionally transport-agnostic and machine-routable so
consumers can branch on a stable string instead of parsing human-readable error
text. They populate the ``error_code`` field of
:class:`python_apis.models.ad_responses.ADOperationEnvelope`.

Mapping table (canonical code -> meaning):

==========================  =================================================
Code                        Meaning
==========================  =================================================
``AD_NOT_FOUND``            Target object does not exist (e.g. noSuchObject).
``AD_VALIDATION_ERROR``     Invalid input/attribute or constraint violation,
                            including schema/``pydantic`` validation failures.
``AD_AUTH_ERROR``           Authentication/bind failure (e.g. invalid
                            credentials).
``AD_PERMISSION_DENIED``    Caller lacks rights for the operation (e.g.
                            insufficientAccessRights).
``AD_CONNECTION_ERROR``     Transport/session failure (e.g. communication or
                            session terminated by server).
``AD_TIMEOUT``             Operation exceeded a time limit / socket timeout.
``AD_CONFLICT``            Conflicting state (e.g. entryAlreadyExists).
``AD_UNKNOWN``             Deterministic fallback for any unmapped failure.
==========================  =================================================

Any exception or non-success result state that is not explicitly mapped resolves
to :data:`AD_UNKNOWN`, so the taxonomy is always total over failure inputs.
"""

from typing import Final

AD_NOT_FOUND: Final = "AD_NOT_FOUND"
AD_VALIDATION_ERROR: Final = "AD_VALIDATION_ERROR"
AD_AUTH_ERROR: Final = "AD_AUTH_ERROR"
AD_PERMISSION_DENIED: Final = "AD_PERMISSION_DENIED"
AD_CONNECTION_ERROR: Final = "AD_CONNECTION_ERROR"
AD_TIMEOUT: Final = "AD_TIMEOUT"
AD_CONFLICT: Final = "AD_CONFLICT"
AD_UNKNOWN: Final = "AD_UNKNOWN"

# Ordered, immutable surface of all canonical error codes. ``AD_UNKNOWN`` is the
# deterministic fallback sentinel and is intentionally listed last.
AD_ERROR_CODES: Final[tuple[str, ...]] = (
    AD_NOT_FOUND,
    AD_VALIDATION_ERROR,
    AD_AUTH_ERROR,
    AD_PERMISSION_DENIED,
    AD_CONNECTION_ERROR,
    AD_TIMEOUT,
    AD_CONFLICT,
    AD_UNKNOWN,
)


__all__ = [
    "AD_NOT_FOUND",
    "AD_VALIDATION_ERROR",
    "AD_AUTH_ERROR",
    "AD_PERMISSION_DENIED",
    "AD_CONNECTION_ERROR",
    "AD_TIMEOUT",
    "AD_CONFLICT",
    "AD_UNKNOWN",
    "AD_ERROR_CODES",
]

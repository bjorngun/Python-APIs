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

from collections.abc import Mapping
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


# Maps ldap3 exception / ``pydantic`` error class names to canonical codes. Keyed
# by class name (rather than imported types) so the mapping is robust to ldap3's
# large, dynamically generated exception hierarchy without importing every class.
# Lookup walks the exception's MRO, so subclasses resolve to their nearest mapped
# ancestor. Names not present here fall through to :data:`AD_UNKNOWN`.
_EXCEPTION_NAME_TO_CODE: Final[dict[str, str]] = {
    # Not found
    "LDAPNoSuchObjectResult": AD_NOT_FOUND,
    "LDAPNoSuchAttributeResult": AD_NOT_FOUND,
    # Validation / constraint / schema
    "ValidationError": AD_VALIDATION_ERROR,
    "LDAPConstraintViolationResult": AD_VALIDATION_ERROR,
    "LDAPInvalidAttributeSyntaxResult": AD_VALIDATION_ERROR,
    "LDAPInvalidDNSyntaxResult": AD_VALIDATION_ERROR,
    "LDAPNamingViolationResult": AD_VALIDATION_ERROR,
    "LDAPObjectClassViolationResult": AD_VALIDATION_ERROR,
    "LDAPUndefinedAttributeTypeResult": AD_VALIDATION_ERROR,
    "LDAPInvalidValueError": AD_VALIDATION_ERROR,
    "LDAPAttributeError": AD_VALIDATION_ERROR,
    # Authentication / bind
    "LDAPBindError": AD_AUTH_ERROR,
    "LDAPInvalidCredentialsResult": AD_AUTH_ERROR,
    "LDAPInappropriateAuthenticationResult": AD_AUTH_ERROR,
    "LDAPAuthMethodNotSupportedResult": AD_AUTH_ERROR,
    "LDAPStrongerAuthRequiredResult": AD_AUTH_ERROR,
    # Permission / authorization
    "LDAPInsufficientAccessRightsResult": AD_PERMISSION_DENIED,
    "LDAPAuthorizationDeniedResult": AD_PERMISSION_DENIED,
    "LDAPConfidentialityRequiredResult": AD_PERMISSION_DENIED,
    "LDAPUnwillingToPerformResult": AD_PERMISSION_DENIED,
    # Conflict / already exists
    "LDAPEntryAlreadyExistsResult": AD_CONFLICT,
    "LDAPAttributeOrValueExistsResult": AD_CONFLICT,
    # Timeout
    "LDAPTimeLimitExceededResult": AD_TIMEOUT,
    "LDAPResponseTimeoutError": AD_TIMEOUT,
    # Connection / transport / session
    "LDAPCommunicationError": AD_CONNECTION_ERROR,
    "LDAPSessionTerminatedByServerError": AD_CONNECTION_ERROR,
    "LDAPSocketOpenError": AD_CONNECTION_ERROR,
    "LDAPSocketSendError": AD_CONNECTION_ERROR,
    "LDAPSocketReceiveError": AD_CONNECTION_ERROR,
    "LDAPSocketCloseError": AD_CONNECTION_ERROR,
    "LDAPServerPoolExhaustedError": AD_CONNECTION_ERROR,
}


def map_exception_to_error_code(exception: BaseException | None) -> str:
    """Map an exception to a canonical AD error code.

    Resolves ldap3 exceptions and :class:`pydantic.ValidationError` to a stable
    code by walking the exception's MRO and matching class names against the
    documented mapping table. Any unmapped or ``None`` exception resolves
    deterministically to :data:`AD_UNKNOWN`.
    """

    if exception is None:
        return AD_UNKNOWN
    for klass in type(exception).__mro__:
        code = _EXCEPTION_NAME_TO_CODE.get(klass.__name__)
        if code is not None:
            return code
    return AD_UNKNOWN


# Maps standard LDAP numeric result codes (RFC 4511 + common extensions) to
# canonical codes. ``0`` (success) is intentionally absent; success yields no
# error code. Non-zero result codes not listed here resolve to
# :data:`AD_UNKNOWN`.
_LDAP_RESULT_CODE_TO_CODE: Final[dict[int, str]] = {
    1: AD_UNKNOWN,            # operationsError
    2: AD_VALIDATION_ERROR,   # protocolError
    3: AD_TIMEOUT,            # timeLimitExceeded
    4: AD_VALIDATION_ERROR,   # sizeLimitExceeded
    7: AD_AUTH_ERROR,         # authMethodNotSupported
    8: AD_AUTH_ERROR,         # strongerAuthRequired
    11: AD_PERMISSION_DENIED,  # adminLimitExceeded
    13: AD_PERMISSION_DENIED,  # confidentialityRequired
    16: AD_NOT_FOUND,         # noSuchAttribute
    17: AD_VALIDATION_ERROR,  # undefinedAttributeType
    18: AD_VALIDATION_ERROR,  # inappropriateMatching
    19: AD_VALIDATION_ERROR,  # constraintViolation
    20: AD_CONFLICT,          # attributeOrValueExists
    21: AD_VALIDATION_ERROR,  # invalidAttributeSyntax
    32: AD_NOT_FOUND,         # noSuchObject
    34: AD_VALIDATION_ERROR,  # invalidDNSyntax
    48: AD_AUTH_ERROR,        # inappropriateAuthentication
    49: AD_AUTH_ERROR,        # invalidCredentials
    50: AD_PERMISSION_DENIED,  # insufficientAccessRights
    51: AD_CONNECTION_ERROR,  # busy
    52: AD_CONNECTION_ERROR,  # unavailable
    53: AD_PERMISSION_DENIED,  # unwillingToPerform
    64: AD_VALIDATION_ERROR,  # namingViolation
    65: AD_VALIDATION_ERROR,  # objectClassViolation
    68: AD_CONFLICT,          # entryAlreadyExists
}


def map_ldap_result_to_error_code(result: object) -> str | None:
    """Map an LDAP result state to a canonical AD error code.

    Accepts either a raw integer result code or an ldap3 result mapping (which
    exposes the numeric code under a ``result`` key). A success code (``0``)
    returns ``None`` (no error). Any unrecognized non-zero result state resolves
    deterministically to :data:`AD_UNKNOWN`. Inputs that carry no usable result
    code also resolve to :data:`AD_UNKNOWN`.
    """

    code: int | None = None
    if isinstance(result, bool):
        # Guard against bool (a subclass of int) being treated as 0/1 codes.
        code = None
    elif isinstance(result, int):
        code = result
    elif isinstance(result, Mapping):
        raw = result.get("result")
        if isinstance(raw, int) and not isinstance(raw, bool):
            code = raw

    if code is None:
        return AD_UNKNOWN
    if code == 0:
        return None
    return _LDAP_RESULT_CODE_TO_CODE.get(code, AD_UNKNOWN)


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
    "map_exception_to_error_code",
    "map_ldap_result_to_error_code",
]

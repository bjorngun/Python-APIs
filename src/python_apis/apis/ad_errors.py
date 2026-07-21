"""Safe public exceptions for Active Directory connection and read failures."""

# pylint: disable=duplicate-code

AD_NOT_FOUND = "AD_NOT_FOUND"
AD_VALIDATION_ERROR = "AD_VALIDATION_ERROR"
AD_AUTH_ERROR = "AD_AUTH_ERROR"
AD_PERMISSION_DENIED = "AD_PERMISSION_DENIED"
AD_CONNECTION_ERROR = "AD_CONNECTION_ERROR"
AD_TIMEOUT = "AD_TIMEOUT"
AD_UNKNOWN = "AD_UNKNOWN"


class ADConnectionError(Exception):
    """Base exception exposing a stable code without sensitive LDAP details."""

    error_code = AD_CONNECTION_ERROR


class ADConfigurationError(ADConnectionError, ValueError):
    """Raised when AD connection/query configuration is invalid."""

    error_code = AD_VALIDATION_ERROR


class ADTLSConfigurationError(ADConfigurationError):
    """Raised when an explicit TLS trust or cipher profile is invalid."""

    def __init__(self) -> None:
        super().__init__("Invalid TLS trust or cipher configuration")


class ADMissingServersError(ADConfigurationError):
    """Raised when an AD connection is created without servers."""

    def __init__(self) -> None:
        super().__init__("At least one Active Directory server is required")


class ADBindError(ADConnectionError):
    """Raised when an LDAP bind fails with safe diagnostic details."""

    error_code = AD_AUTH_ERROR

    def __init__(
        self,
        result_code: int | str | None,
        controller: str,
    ) -> None:
        self.result_code = result_code
        self.controller = controller
        super().__init__(
            "Failed to bind to Active Directory "
            f"(result_code={result_code!r}, controller={controller})"
        )


class ADReadError(ADConnectionError):
    """Base exception for fail-closed Active Directory reads."""


class ADSearchError(ADReadError):
    """Raised for a non-success LDAP search result without raw diagnostics."""

    def __init__(
        self,
        *,
        error_code: str = AD_UNKNOWN,
        result_code: int | str | None = None,
        controller: str = "controller-unknown",
    ) -> None:
        self.error_code = error_code
        self.result_code = result_code
        self.controller = controller
        super().__init__(
            "Active Directory search failed "
            f"(error_code={error_code}, result_code={result_code!r}, "
            f"controller={controller})"
        )


class ADQueryRejectedError(ADSearchError):
    """Raised when the directory rejects an otherwise well-formed search."""


class ADMalformedQueryError(ADReadError, ValueError):
    """Raised when a caller-provided query cannot be parsed safely."""

    error_code = AD_VALIDATION_ERROR

    def __init__(self) -> None:
        super().__init__("Active Directory query is malformed")


class ADMalformedResultError(ADReadError):
    """Raised when the directory returns an unusable result shape."""

    error_code = AD_VALIDATION_ERROR

    def __init__(self) -> None:
        super().__init__("Active Directory returned a malformed result")


class ADTransportError(ADReadError):
    """Raised after recoverable LDAP transport attempts are exhausted."""

    error_code = AD_CONNECTION_ERROR

    def __init__(self, controller: str = "controller-unknown") -> None:
        self.controller = controller
        super().__init__(
            "Active Directory transport failed "
            f"(controller={controller})"
        )


class ADTimeoutError(ADReadError, TimeoutError):
    """Raised when an Active Directory read exceeds its timeout."""

    error_code = AD_TIMEOUT

    def __init__(self, controller: str = "controller-unknown") -> None:
        self.controller = controller
        super().__init__(
            "Active Directory read timed out "
            f"(controller={controller})"
        )


__all__ = [
    "ADBindError",
    "ADConfigurationError",
    "ADConnectionError",
    "ADMalformedQueryError",
    "ADMalformedResultError",
    "ADMissingServersError",
    "ADQueryRejectedError",
    "ADReadError",
    "ADSearchError",
    "ADTimeoutError",
    "ADTLSConfigurationError",
    "ADTransportError",
]

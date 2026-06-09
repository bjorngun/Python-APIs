"""Utilities for resolving AD compatibility mode in service layer code.

This module centralizes mode resolution for AD services while reusing the
contract defined in ``python_apis.apis.ad_api``.
"""

from typing import Any, Literal, cast

from python_apis.apis.ad_api import (
    AD_COMPATIBILITY_ENV_VAR,
    AD_COMPATIBILITY_MODES,
    AD_DEFAULT_COMPATIBILITY_MODE,
    resolve_ad_compatibility_mode,
)
from python_apis.models import ADOperationEnvelope

ADCompatibilityMode = Literal["legacy", "mixed", "strict"]


def resolve_service_compatibility_mode(
    per_call_mode: str | None = None,
    service_mode: str | None = None,
    env_mode: str | None = None,
) -> ADCompatibilityMode:
    """Resolve effective AD compatibility mode for service-layer operations.

    Precedence is ``per_call_mode`` -> ``service_mode`` -> environment
    (``PYTHON_APIS_AD_COMPAT_MODE``) -> ``legacy`` fallback.
    """

    return cast(
        ADCompatibilityMode,
        resolve_ad_compatibility_mode(
            per_call_mode=per_call_mode,
            service_mode=service_mode,
            env_mode=env_mode,
        ),
    )


def finalize_ad_write_response(
    legacy_response: dict[str, Any],
    *,
    effective_mode: str,
    exception: BaseException | None = None,
) -> dict[str, Any]:
    """Shape an AD write-operation response for the effective compatibility mode.

    In ``legacy`` mode the original response dict is returned unchanged to
    preserve pre-modernization behavior (the non-breaking Stage N default). In
    ``mixed`` and ``strict`` modes an :class:`ADOperationEnvelope` is emitted:
    ``mixed`` mirrors the legacy keys (``success``, ``result``, ``message``)
    while ``strict`` omits them. Operation-specific extras (for example ``dn``
    or ``changes``) are preserved as top-level keys and captured in
    ``request_context``.
    """

    if effective_mode == "legacy":
        return legacy_response

    extras = {
        key: value
        for key, value in legacy_response.items()
        if key not in ("success", "result")
    }
    success = (
        False if exception is not None else bool(legacy_response.get("success"))
    )
    envelope = ADOperationEnvelope.from_operation(
        operation_kind="write",
        success=success,
        ldap_result=legacy_response.get("result"),
        exception=exception,
        request_context={**extras, "compatibility_mode": effective_mode},
    )
    payload = envelope.to_response(effective_mode)
    for key, value in extras.items():
        payload.setdefault(key, value)
    return payload


__all__ = [
    "ADCompatibilityMode",
    "AD_COMPATIBILITY_MODES",
    "AD_DEFAULT_COMPATIBILITY_MODE",
    "AD_COMPATIBILITY_ENV_VAR",
    "resolve_service_compatibility_mode",
    "finalize_ad_write_response",
]

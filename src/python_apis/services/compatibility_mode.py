"""Utilities for resolving AD compatibility mode in service layer code.

This module centralizes mode resolution for AD services while reusing the
contract defined in ``python_apis.apis.ad_api``.
"""

from typing import Any, Literal, cast

from python_apis.apis.ad_api import (
    AD_COMPATIBILITY_ENV_VAR,
    AD_COMPATIBILITY_MODES,
    AD_DEFAULT_COMPATIBILITY_MODE,
    RetryTelemetry,
    resolve_ad_compatibility_mode,
)
from python_apis.models import ADOperationEnvelope
from python_apis.services.error_taxonomy import resolve_error_code

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


def _retry_envelope_kwargs(retry_telemetry: RetryTelemetry | None) -> dict[str, Any]:
    """Translate captured retry telemetry into envelope ``from_operation`` kwargs.

    Returns an empty mapping (safe envelope defaults) when no telemetry is
    available, so callers can always ``**``-splat the result.
    """

    if retry_telemetry is None:
        return {}
    return {
        "retry_count": retry_telemetry.retry_count,
        "retried": retry_telemetry.retried,
        "would_retry": retry_telemetry.would_retry,
        "retry_policy": dict(retry_telemetry.policy) if retry_telemetry.policy else None,
    }


def finalize_ad_write_response(
    legacy_response: dict[str, Any],
    *,
    effective_mode: str,
    exception: BaseException | None = None,
    retry_telemetry: RetryTelemetry | None = None,
) -> dict[str, Any]:
    """Shape an AD write-operation response for the effective compatibility mode.

    In ``legacy`` mode the original response dict is returned unchanged to
    preserve pre-modernization behavior (the non-breaking Stage N default). In
    ``mixed`` and ``strict`` modes an :class:`ADOperationEnvelope` is emitted:
    ``mixed`` mirrors the legacy keys (``success``, ``result``, ``message``)
    while ``strict`` omits them. Operation-specific extras (for example ``dn``
    or ``changes``) are preserved as top-level keys and captured in
    ``request_context``.

    When ``retry_telemetry`` is provided (typically
    ``ADConnection.last_retry_telemetry`` captured immediately after the
    operation), its retry counters and policy metadata are surfaced on the
    envelope; ``legacy`` mode output is unaffected.
    """

    if effective_mode == "legacy":
        return legacy_response

    extras = {
        key: value
        for key, value in legacy_response.items()
        if key not in ("success", "result", "message")
    }
    success = (
        False if exception is not None else bool(legacy_response.get("success"))
    )
    error_code = resolve_error_code(
        exception=exception,
        ldap_result=legacy_response.get("result"),
        success=success,
    )
    envelope = ADOperationEnvelope.from_operation(
        operation_kind="write",
        success=success,
        ldap_result=legacy_response.get("result"),
        exception=exception,
        request_context={**extras, "compatibility_mode": effective_mode},
        error_code=error_code,
        **_retry_envelope_kwargs(retry_telemetry),
    )
    payload = envelope.to_response(effective_mode)
    for key, value in extras.items():
        payload.setdefault(key, value)
    return payload


def finalize_ad_read_response(  # pylint: disable=too-many-arguments
    read_result: Any,
    *,
    effective_mode: str,
    success: bool | None = None,
    exception: BaseException | None = None,
    retry_telemetry: RetryTelemetry | None = None,
    request_context: dict[str, Any] | None = None,
) -> Any:
    """Optionally wrap an AD read outcome in an operation envelope.

    This helper is opt-in: default read service methods keep returning their
    historic value (for example ``list[ADUser]``). In ``legacy`` mode the raw
    ``read_result`` is returned unchanged (non-breaking, mirroring
    :func:`finalize_ad_write_response`). In ``mixed`` and ``strict`` modes an
    :class:`ADOperationEnvelope` with ``operation_kind="read"`` is built, with
    ``read_result`` exposed as ``ldap_result`` and any captured
    ``retry_telemetry`` surfaced as retry metadata.

    ``success`` defaults to ``exception is None`` when not supplied.
    """

    if effective_mode == "legacy":
        return read_result

    if success is None:
        success = exception is None
    error_code = resolve_error_code(
        exception=exception,
        ldap_result=read_result,
        success=success,
    )
    context = dict(request_context or {})
    context["compatibility_mode"] = effective_mode
    envelope = ADOperationEnvelope.from_operation(
        operation_kind="read",
        success=success,
        ldap_result=read_result,
        exception=exception,
        request_context=context,
        error_code=error_code,
        **_retry_envelope_kwargs(retry_telemetry),
    )
    return envelope.to_response(effective_mode)


__all__ = [
    "ADCompatibilityMode",
    "AD_COMPATIBILITY_MODES",
    "AD_DEFAULT_COMPATIBILITY_MODE",
    "AD_COMPATIBILITY_ENV_VAR",
    "resolve_service_compatibility_mode",
    "finalize_ad_write_response",
    "finalize_ad_read_response",
]

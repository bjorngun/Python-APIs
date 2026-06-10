"""Helpers for shaping AD service-layer responses into operation envelopes.

Since the Stage 3 breaking cleanup, AD services always emit strict
:class:`ADOperationEnvelope` responses. There is no compatibility-mode
selection: the legacy raw-dict and mixed-mirror shapes have been removed.
"""

from typing import Any

from python_apis.apis.ad_api import RetryTelemetry
from python_apis.models import ADOperationEnvelope
from python_apis.services.error_taxonomy import resolve_error_code


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
    exception: BaseException | None = None,
    retry_telemetry: RetryTelemetry | None = None,
) -> dict[str, Any]:
    """Shape an AD write-operation response as a strict operation envelope.

    A strict :class:`ADOperationEnvelope` is always emitted; the legacy mirror
    keys (``success``, ``result``, ``message``) are not included.
    Operation-specific extras (for example ``dn`` or ``changes``) are preserved
    as top-level keys and captured in ``request_context``.

    When ``retry_telemetry`` is provided (typically
    ``ADConnection.last_retry_telemetry`` captured immediately after the
    operation), its retry counters and policy metadata are surfaced on the
    envelope.
    """

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
        request_context=dict(extras),
        error_code=error_code,
        **_retry_envelope_kwargs(retry_telemetry),
    )
    payload = envelope.to_response()
    for key, value in extras.items():
        payload.setdefault(key, value)
    return payload


def finalize_ad_read_response(
    read_result: Any,
    *,
    success: bool | None = None,
    exception: BaseException | None = None,
    retry_telemetry: RetryTelemetry | None = None,
    request_context: dict[str, Any] | None = None,
) -> Any:
    """Wrap an AD read outcome in a strict operation envelope.

    This helper is opt-in: default read service methods keep returning their
    historic value (for example ``list[ADUser]``). When used, a strict
    :class:`ADOperationEnvelope` with ``operation_kind="read"`` is built, with
    ``read_result`` exposed as ``ldap_result`` and any captured
    ``retry_telemetry`` surfaced as retry metadata.

    ``success`` defaults to ``exception is None`` when not supplied.
    """

    if success is None:
        success = exception is None
    error_code = resolve_error_code(
        exception=exception,
        ldap_result=read_result,
        success=success,
    )
    context = dict(request_context or {})
    envelope = ADOperationEnvelope.from_operation(
        operation_kind="read",
        success=success,
        ldap_result=read_result,
        exception=exception,
        request_context=context,
        error_code=error_code,
        **_retry_envelope_kwargs(retry_telemetry),
    )
    return envelope.to_response()


__all__ = [
    "finalize_ad_write_response",
    "finalize_ad_read_response",
]

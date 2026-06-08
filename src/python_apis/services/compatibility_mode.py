"""Utilities for resolving AD compatibility mode in service layer code.

This module centralizes mode resolution for AD services while reusing the
contract defined in ``python_apis.apis.ad_api``.
"""

from typing import Literal, cast

from python_apis.apis.ad_api import (
    AD_COMPATIBILITY_ENV_VAR,
    AD_COMPATIBILITY_MODES,
    AD_DEFAULT_COMPATIBILITY_MODE,
    resolve_ad_compatibility_mode,
)

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


__all__ = [
    "ADCompatibilityMode",
    "AD_COMPATIBILITY_MODES",
    "AD_DEFAULT_COMPATIBILITY_MODE",
    "AD_COMPATIBILITY_ENV_VAR",
    "resolve_service_compatibility_mode",
]

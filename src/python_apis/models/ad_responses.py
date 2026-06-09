"""Typed, dict-compatible AD response models (ADR 0001, Stage N).

This module provides additive typed response models for Active Directory
operations. The models are JSON-serializable Pydantic models that also behave
like read-only mappings, so existing consumers that rely on legacy dictionary
access (for example ``response['success']`` or ``response['result']``) continue
to work unchanged.

Stage N scope note:
    These models are introduced additively. They do not change what
    ``python_apis.apis.ad_api.ADConnection`` methods return today; wiring the
    models into live operation envelopes with legacy mirroring is tracked
    separately (issue #19).
"""

__all__: list[str] = []

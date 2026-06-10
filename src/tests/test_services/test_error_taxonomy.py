"""Tests for the normalized AD error taxonomy and mapping utilities."""

import unittest

from ldap3.core.exceptions import (
    LDAPCommunicationError,
    LDAPEntryAlreadyExistsResult,
    LDAPInsufficientAccessRightsResult,
    LDAPNoSuchObjectResult,
)
from pydantic import BaseModel, ValidationError

from python_apis.services.compatibility_mode import finalize_ad_write_response
from python_apis.services.error_taxonomy import (
    AD_AUTH_ERROR,
    AD_CONFLICT,
    AD_CONNECTION_ERROR,
    AD_ERROR_CODES,
    AD_NOT_FOUND,
    AD_PERMISSION_DENIED,
    AD_TIMEOUT,
    AD_UNKNOWN,
    AD_VALIDATION_ERROR,
    map_exception_to_error_code,
    map_ldap_result_to_error_code,
    resolve_error_code,
)


class _StrictModel(BaseModel):
    """Minimal model used to provoke a real ``pydantic`` ValidationError."""

    value: int


class _SubclassedNoSuchObject(LDAPNoSuchObjectResult):
    """Subclass to verify MRO-based resolution to the nearest mapped ancestor."""


class TestCanonicalCodes(unittest.TestCase):
    """Validate the canonical code surface is stable and total."""

    def test_unknown_is_last_sentinel(self):
        self.assertEqual(AD_ERROR_CODES[-1], AD_UNKNOWN)

    def test_all_codes_unique(self):
        self.assertEqual(len(set(AD_ERROR_CODES)), len(AD_ERROR_CODES))

    def test_expected_codes_present(self):
        self.assertEqual(
            set(AD_ERROR_CODES),
            {
                AD_NOT_FOUND,
                AD_VALIDATION_ERROR,
                AD_AUTH_ERROR,
                AD_PERMISSION_DENIED,
                AD_CONNECTION_ERROR,
                AD_TIMEOUT,
                AD_CONFLICT,
                AD_UNKNOWN,
            },
        )


class TestMapExceptionToErrorCode(unittest.TestCase):
    """Validate exception-to-code mapping behavior."""

    def test_none_resolves_to_unknown(self):
        self.assertEqual(map_exception_to_error_code(None), AD_UNKNOWN)

    def test_pydantic_validation_error_maps_to_validation(self):
        try:
            _StrictModel(value="not-an-int")
        except ValidationError as exc:
            self.assertEqual(
                map_exception_to_error_code(exc), AD_VALIDATION_ERROR
            )
        else:  # pragma: no cover - guard against silent pass
            self.fail("expected ValidationError")

    def test_ldap_not_found_maps_by_class_name(self):
        self.assertEqual(
            map_exception_to_error_code(LDAPNoSuchObjectResult()),
            AD_NOT_FOUND,
        )

    def test_permission_denied_maps_by_class_name(self):
        self.assertEqual(
            map_exception_to_error_code(LDAPInsufficientAccessRightsResult()),
            AD_PERMISSION_DENIED,
        )

    def test_connection_error_maps_by_class_name(self):
        self.assertEqual(
            map_exception_to_error_code(LDAPCommunicationError()),
            AD_CONNECTION_ERROR,
        )

    def test_subclass_resolves_via_mro(self):
        self.assertEqual(
            map_exception_to_error_code(_SubclassedNoSuchObject()),
            AD_NOT_FOUND,
        )

    def test_unmapped_exception_resolves_to_unknown(self):
        self.assertEqual(
            map_exception_to_error_code(RuntimeError("boom")), AD_UNKNOWN
        )


class TestMapLDAPResultToErrorCode(unittest.TestCase):
    """Validate LDAP result-state mapping behavior."""

    def test_success_code_returns_none(self):
        self.assertIsNone(map_ldap_result_to_error_code(0))

    def test_known_numeric_codes(self):
        self.assertEqual(map_ldap_result_to_error_code(32), AD_NOT_FOUND)
        self.assertEqual(map_ldap_result_to_error_code(49), AD_AUTH_ERROR)
        self.assertEqual(
            map_ldap_result_to_error_code(50), AD_PERMISSION_DENIED
        )
        self.assertEqual(map_ldap_result_to_error_code(68), AD_CONFLICT)
        self.assertEqual(map_ldap_result_to_error_code(19), AD_VALIDATION_ERROR)
        self.assertEqual(map_ldap_result_to_error_code(3), AD_TIMEOUT)

    def test_mapping_with_result_key(self):
        self.assertEqual(
            map_ldap_result_to_error_code({"result": 32, "description": "x"}),
            AD_NOT_FOUND,
        )

    def test_mapping_success_returns_none(self):
        self.assertIsNone(map_ldap_result_to_error_code({"result": 0}))

    def test_bool_is_not_treated_as_code(self):
        self.assertEqual(map_ldap_result_to_error_code(True), AD_UNKNOWN)
        self.assertEqual(map_ldap_result_to_error_code(False), AD_UNKNOWN)

    def test_unrecognized_nonzero_resolves_to_unknown(self):
        self.assertEqual(map_ldap_result_to_error_code(9999), AD_UNKNOWN)

    def test_unusable_input_resolves_to_unknown(self):
        self.assertEqual(map_ldap_result_to_error_code("denied"), AD_UNKNOWN)
        self.assertEqual(map_ldap_result_to_error_code(None), AD_UNKNOWN)

    def test_aggregate_partial_failure_preserves_subop_code(self):
        # create_user partial-failure payloads carry no top-level "result" key.
        self.assertEqual(
            map_ldap_result_to_error_code(
                {"create": 0, "password": 49}
            ),
            AD_AUTH_ERROR,
        )
        self.assertEqual(
            map_ldap_result_to_error_code(
                {"create": 0, "enable": 50}
            ),
            AD_PERMISSION_DENIED,
        )

    def test_aggregate_with_nested_result_mapping(self):
        self.assertEqual(
            map_ldap_result_to_error_code(
                {"create": {"result": 0}, "password": {"result": 53}}
            ),
            AD_PERMISSION_DENIED,
        )

    def test_aggregate_without_classifiable_subop_resolves_to_unknown(self):
        self.assertEqual(
            map_ldap_result_to_error_code(
                {"create": "ok", "password": "invalidCredentials"}
            ),
            AD_UNKNOWN,
        )


class TestResolveErrorCode(unittest.TestCase):
    """Validate the unified resolver precedence and fallback rules."""

    def test_exception_takes_precedence(self):
        self.assertEqual(
            resolve_error_code(
                exception=LDAPNoSuchObjectResult(),
                ldap_result=0,
                success=True,
            ),
            AD_NOT_FOUND,
        )

    def test_explicit_success_returns_none(self):
        self.assertIsNone(resolve_error_code(success=True))
        self.assertIsNone(resolve_error_code(success=True, ldap_result=49))

    def test_failure_with_known_result_code(self):
        self.assertEqual(
            resolve_error_code(ldap_result=49, success=False), AD_AUTH_ERROR
        )

    def test_failure_with_unusable_result_falls_back_to_unknown(self):
        self.assertEqual(
            resolve_error_code(ldap_result="denied", success=False),
            AD_UNKNOWN,
        )

    def test_failure_without_code_falls_back_to_unknown(self):
        self.assertEqual(resolve_error_code(success=False), AD_UNKNOWN)

    def test_success_result_state_returns_none(self):
        self.assertIsNone(resolve_error_code(ldap_result=0))

    def test_no_signals_returns_none(self):
        self.assertIsNone(resolve_error_code())


class TestServiceIntegration(unittest.TestCase):
    """Validate error_code wiring through finalize_ad_write_response."""

    def test_strict_success_has_none_error_code(self):
        result = finalize_ad_write_response(
            {"success": True, "result": "ok"}
        )

        self.assertIsNone(result["error_code"])

    def test_failure_with_exception_populates_error_code(self):
        result = finalize_ad_write_response(
            {"success": False, "result": "denied"},
            exception=LDAPInsufficientAccessRightsResult(),
        )

        self.assertEqual(result["error_code"], AD_PERMISSION_DENIED)

    def test_strict_failure_with_result_code_populates_error_code(self):
        result = finalize_ad_write_response(
            {"success": False, "result": 49}
        )

        self.assertEqual(result["error_code"], AD_AUTH_ERROR)

    def test_conflict_exception_maps_to_error_code(self):
        result = finalize_ad_write_response(
            {"success": False, "result": "exists"},
            exception=LDAPEntryAlreadyExistsResult(),
        )

        self.assertEqual(result["error_code"], AD_CONFLICT)

    def test_partial_failure_aggregate_surfaces_subop_code(self):
        # Mirrors create_user's partial-failure payload (add ok, sub-op failed).
        result = finalize_ad_write_response(
            {
                "success": False,
                "result": {"create": 0, "password": 49},
                "dn": "CN=x,OU=y",
            },
        )

        self.assertEqual(result["error_code"], AD_AUTH_ERROR)


if __name__ == "__main__":
    unittest.main()

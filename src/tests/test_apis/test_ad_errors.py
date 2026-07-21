"""Tests for safe public Active Directory errors."""

import unittest

from python_apis.apis import (
    ADBindError,
    ADConfigurationError,
    ADConnectionError,
    ADMalformedQueryError,
    ADMalformedResultError,
    ADMissingServersError,
    ADQueryRejectedError,
    ADReadError,
    ADSearchError,
    ADTimeoutError,
    ADTLSConfigurationError,
    ADTransportError,
)
from python_apis.services.error_taxonomy import (
    AD_AUTH_ERROR,
    AD_CONNECTION_ERROR,
    AD_PERMISSION_DENIED,
    AD_TIMEOUT,
    AD_VALIDATION_ERROR,
    map_exception_to_error_code,
)


class TestADErrorHierarchy(unittest.TestCase):
    """Verify compatibility, canonical codes, and safe diagnostics."""

    def test_existing_connection_errors_remain_compatible(self):
        self.assertTrue(issubclass(ADBindError, ADConnectionError))
        self.assertTrue(issubclass(ADMissingServersError, ADConnectionError))
        self.assertTrue(issubclass(ADMissingServersError, ValueError))

    def test_configuration_errors_have_validation_code(self):
        errors = (
            ADConfigurationError("invalid"),
            ADTLSConfigurationError(),
            ADMissingServersError(),
            ADMalformedQueryError(),
            ADMalformedResultError(),
        )

        for error in errors:
            with self.subTest(error=type(error).__name__):
                self.assertEqual(error.error_code, AD_VALIDATION_ERROR)
                self.assertEqual(
                    map_exception_to_error_code(error), AD_VALIDATION_ERROR
                )

    def test_bind_error_has_safe_auth_code(self):
        error = ADBindError(49, "controller-deadbeef")

        self.assertEqual(error.error_code, AD_AUTH_ERROR)
        self.assertEqual(map_exception_to_error_code(error), AD_AUTH_ERROR)
        self.assertNotIn("CREDENTIAL_CANARY", str(error))

    def test_search_error_supports_specific_safe_code(self):
        error = ADQueryRejectedError(
            error_code=AD_PERMISSION_DENIED,
            result_code=50,
            controller="controller-deadbeef",
        )

        self.assertIsInstance(error, ADSearchError)
        self.assertIsInstance(error, ADReadError)
        self.assertEqual(error.error_code, AD_PERMISSION_DENIED)
        self.assertEqual(
            map_exception_to_error_code(error), AD_PERMISSION_DENIED
        )
        message = str(error)
        self.assertNotIn("FILTER_CANARY", message)
        self.assertNotIn("LDAP_DIAGNOSTIC_CANARY", message)

    def test_transport_and_timeout_codes_are_stable(self):
        transport = ADTransportError("controller-deadbeef")
        timeout = ADTimeoutError("controller-deadbeef")

        self.assertEqual(transport.error_code, AD_CONNECTION_ERROR)
        self.assertEqual(timeout.error_code, AD_TIMEOUT)
        self.assertEqual(
            map_exception_to_error_code(transport), AD_CONNECTION_ERROR
        )
        self.assertEqual(map_exception_to_error_code(timeout), AD_TIMEOUT)


if __name__ == "__main__":
    unittest.main()

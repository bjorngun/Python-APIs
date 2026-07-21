"""Tests for Active Directory authentication and TLS configuration."""

import ssl
import unittest
from dataclasses import FrozenInstanceError
from typing import get_args

from python_apis.apis import ADAuthenticationMode, ADTLSConfig


class TestADTLSConfig(unittest.TestCase):
    """Verify secure defaults, validation, and representation safety."""

    def test_secure_factory_uses_modern_validated_defaults(self):
        config = ADTLSConfig.secure()

        self.assertEqual(config.validate, ssl.CERT_REQUIRED)
        self.assertIsNone(config.version)
        self.assertEqual(config.ssl_options, ())
        self.assertFalse(config.legacy_leaf_key_compatibility)

    def test_secure_factory_preserves_custom_trust_configuration(self):
        config = ADTLSConfig.secure(
            ca_certs_file="ca-file.pem",
            ca_certs_path="ca-directory",
            ca_certs_data="CA_DATA_CANARY",
            valid_names=("directory.example.test",),
            ssl_options=(ssl.OP_NO_COMPRESSION,),
            ciphers="HIGH:!aNULL",
        )

        self.assertEqual(config.ca_certs_file, "ca-file.pem")
        self.assertEqual(config.ca_certs_path, "ca-directory")
        self.assertEqual(config.ca_certs_data, "CA_DATA_CANARY")
        self.assertEqual(config.valid_names, ("directory.example.test",))
        self.assertEqual(config.ssl_options, (ssl.OP_NO_COMPRESSION,))
        self.assertEqual(config.ciphers, "HIGH:!aNULL")

    def test_sensitive_trust_values_are_excluded_from_repr(self):
        config = ADTLSConfig.secure(
            ca_certs_file="CA_FILE_CANARY",
            ca_certs_path="CA_PATH_CANARY",
            ca_certs_data="CA_DATA_CANARY",
            valid_names=("SERVER_NAME_CANARY",),
        )

        representation = repr(config)

        self.assertNotIn("CA_FILE_CANARY", representation)
        self.assertNotIn("CA_PATH_CANARY", representation)
        self.assertNotIn("CA_DATA_CANARY", representation)
        self.assertNotIn("SERVER_NAME_CANARY", representation)

    def test_config_is_immutable(self):
        config = ADTLSConfig.secure()

        with self.assertRaises(FrozenInstanceError):
            config.validate = ssl.CERT_NONE

    def test_rejects_legacy_leaf_key_without_required_validation(self):
        with self.assertRaisesRegex(ValueError, "requires certificate validation"):
            ADTLSConfig(
                validate=ssl.CERT_NONE,
                legacy_leaf_key_compatibility=True,
            )

    def test_rejects_custom_ciphers_with_legacy_leaf_key_mode(self):
        with self.assertRaisesRegex(ValueError, "manages ciphers"):
            ADTLSConfig.secure(
                ciphers="HIGH",
                legacy_leaf_key_compatibility=True,
            )

    def test_rejects_wildcard_valid_name(self):
        with self.assertRaisesRegex(ValueError, "cannot include"):
            ADTLSConfig.secure(valid_names=("*",))

    def test_rejects_invalid_collection_types(self):
        invalid_options = (
            {"ssl_options": [ssl.OP_NO_COMPRESSION]},
            {"valid_names": ["directory.example.test"]},
        )

        for options in invalid_options:
            with self.subTest(options=options), self.assertRaises(ValueError):
                ADTLSConfig(**options)

    def test_rejects_empty_string_settings(self):
        for field_name in (
            "ca_certs_file",
            "ca_certs_path",
            "ca_certs_data",
            "ciphers",
        ):
            with self.subTest(field=field_name), self.assertRaisesRegex(
                ValueError, field_name
            ):
                ADTLSConfig(**{field_name: " "})

    def test_authentication_modes_are_closed(self):
        self.assertEqual(set(get_args(ADAuthenticationMode)), {"gssapi", "simple"})


if __name__ == "__main__":
    unittest.main()
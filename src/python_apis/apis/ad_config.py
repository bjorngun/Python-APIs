"""Configuration contracts for Active Directory authentication and LDAPS."""

import ssl
from dataclasses import dataclass, field
from typing import Literal

ADAuthenticationMode = Literal["gssapi", "simple"]


@dataclass(frozen=True)
class ADTLSConfig:  # pylint: disable=too-many-instance-attributes
    """Immutable explicit TLS settings for an Active Directory connection.

    Omitting this object from :class:`~python_apis.apis.ADConnection` preserves
    the package's historical unvalidated TLS behavior. Use :meth:`secure` to
    opt a connection into certificate-chain and hostname validation.
    """

    validate: ssl.VerifyMode = ssl.CERT_REQUIRED
    version: int | None = None
    ssl_options: tuple[int, ...] = ()
    ca_certs_file: str | None = field(default=None, repr=False)
    ca_certs_path: str | None = field(default=None, repr=False)
    ca_certs_data: str | None = field(default=None, repr=False)
    valid_names: tuple[str, ...] = field(default=(), repr=False)
    ciphers: str | None = None
    legacy_leaf_key_compatibility: bool = False

    def __post_init__(self) -> None:
        """Reject ambiguous or security-bypassing TLS settings."""

        if self.validate not in (ssl.CERT_NONE, ssl.CERT_OPTIONAL, ssl.CERT_REQUIRED):
            raise ValueError("validate must be a supported ssl verification mode")
        if self.version is not None and (
            isinstance(self.version, bool) or not isinstance(self.version, int)
        ):
            raise ValueError("version must be an ssl protocol constant or None")
        if not isinstance(self.ssl_options, tuple) or any(
            isinstance(option, bool) or not isinstance(option, int)
            for option in self.ssl_options
        ):
            raise ValueError("ssl_options must be a tuple of ssl option constants")

        for name in ("ca_certs_file", "ca_certs_path", "ca_certs_data", "ciphers"):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise ValueError(f"{name} must be a non-empty string or None")

        if not isinstance(self.valid_names, tuple) or any(
            not isinstance(name, str) or not name.strip() or name == "*"
            for name in self.valid_names
        ):
            raise ValueError("valid_names must contain non-empty names and cannot include '*'")
        if not isinstance(self.legacy_leaf_key_compatibility, bool):
            raise ValueError("legacy_leaf_key_compatibility must be a boolean")
        if self.legacy_leaf_key_compatibility and self.validate != ssl.CERT_REQUIRED:
            raise ValueError(
                "legacy leaf-key compatibility requires certificate validation"
            )
        if self.legacy_leaf_key_compatibility and self.ciphers is not None:
            raise ValueError(
                "legacy leaf-key compatibility manages ciphers and cannot use custom ciphers"
            )

    @classmethod
    def secure(  # pylint: disable=too-many-arguments
        cls,
        *,
        ca_certs_file: str | None = None,
        ca_certs_path: str | None = None,
        ca_certs_data: str | None = None,
        valid_names: tuple[str, ...] = (),
        ssl_options: tuple[int, ...] = (),
        ciphers: str | None = None,
        legacy_leaf_key_compatibility: bool = False,
    ) -> "ADTLSConfig":
        """Build a validated modern TLS configuration."""

        return cls(
            validate=ssl.CERT_REQUIRED,
            version=None,
            ssl_options=ssl_options,
            ca_certs_file=ca_certs_file,
            ca_certs_path=ca_certs_path,
            ca_certs_data=ca_certs_data,
            valid_names=valid_names,
            ciphers=ciphers,
            legacy_leaf_key_compatibility=legacy_leaf_key_compatibility,
        )


__all__ = ["ADAuthenticationMode", "ADTLSConfig"]

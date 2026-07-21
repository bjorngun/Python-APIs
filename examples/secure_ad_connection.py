"""Build an explicit validated AD connection from caller-owned configuration.

Required environment variables:

- ``LDAP_SERVER_LIST``: whitespace-separated LDAPS server names.
- ``SEARCH_BASE``: default LDAP search base.

Optional variables:

- ``LDAP_CA_CERTS_FILE``: approved CA bundle path; omit to use OS trust.
- ``LDAP_AUTHENTICATION``: ``gssapi`` (default) or ``simple``.
- ``LDAP_BIND_USERNAME`` / ``LDAP_BIND_PASSWORD``: secret-provider values for simple bind.
"""

import os

from python_apis.apis import (
    ADAuthenticationMode,
    ADConfigurationError,
    ADConnection,
    ADConnectionError,
    ADTLSConfig,
)


def build_connection() -> ADConnection:
    """Build an explicit secure connection from environment configuration."""

    authentication_value = os.getenv("LDAP_AUTHENTICATION", "gssapi").casefold()
    if authentication_value not in ("gssapi", "simple"):
        raise ADConfigurationError("Unsupported authentication mode")
    authentication: ADAuthenticationMode = authentication_value
    username = os.getenv("LDAP_BIND_USERNAME") if authentication == "simple" else None
    password = os.getenv("LDAP_BIND_PASSWORD") if authentication == "simple" else None
    return ADConnection(
        os.getenv("LDAP_SERVER_LIST", "").split(),
        os.getenv("SEARCH_BASE", ""),
        authentication=authentication,
        username=username,
        password=password,
        tls=ADTLSConfig.secure(
            ca_certs_file=os.getenv("LDAP_CA_CERTS_FILE") or None,
        ),
        connect_timeout=5,
        receive_timeout=30,
        read_retry_count=1,
        write_retry_count=0,
    )


def main() -> None:
    """Validate bind and cleanup without printing directory configuration."""

    try:
        with build_connection():
            print("Secure Active Directory connection established.")
    except ADConnectionError as error:
        print(f"Secure Active Directory connection failed: error_code={error.error_code}")


if __name__ == "__main__":
    main()

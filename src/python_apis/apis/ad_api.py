"""This module contains the functionality concerning the
connection and the methods that gets data from AD and can modify the AD.

This module was build as an "in the same domain" AD connection and has no plans
to extend to being able to connect through a custom user and password. Hence
this package will need a user that has the required permissions to edit/read the
AD to run it effectively.
"""

# pylint: disable=too-many-lines

import functools
import hashlib
import logging
import math
import ssl
import time
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

from ldap3.utils.log import (
    BASIC,
    set_library_log_detail_level,
    set_library_log_hide_sensitive_data,
)
from ldap3 import (ALL_ATTRIBUTES, BASE, LEVEL, MODIFY_ADD, MODIFY_DELETE,
                   MODIFY_REPLACE, ROUND_ROBIN, SASL, SIMPLE, SUBTREE, GSSAPI,
                   Connection, Server, ServerPool, Tls)
from ldap3.core.exceptions import (
    LDAPCommunicationError,
    LDAPException,
    LDAPInvalidDnError,
    LDAPSessionTerminatedByServerError,
)
from ldap3.utils.dn import parse_dn

from python_apis.apis.ad_config import ADAuthenticationMode, ADTLSConfig
from python_apis.apis.ad_errors import (  # pylint: disable=unused-import
    ADBindError,
    ADConnectionError as ADConnectionError,
    ADMissingServersError,
    ADTLSConfigurationError,
)
from python_apis.models.ad_get import ADGetResult

logger = logging.getLogger(__name__)

AD_RECOVERABLE_READ_EXCEPTIONS = (
    LDAPSessionTerminatedByServerError,
    LDAPCommunicationError,
)
_RECOVERABLE_EXCEPTIONS = AD_RECOVERABLE_READ_EXCEPTIONS
_RECOVERABLE_EXCEPTION_NAMES = tuple(exc.__name__ for exc in _RECOVERABLE_EXCEPTIONS)
_SUPPORTED_SEARCH_SCOPES = frozenset((BASE, LEVEL, SUBTREE))
_LEGACY_LEAF_KEY_CIPHERS = "DEFAULT:@SECLEVEL=1"


def _build_retry_policy(operation_kind: str, max_retries: int) -> dict[str, Any]:
    """Describe the configured retry policy for an operation classification."""

    if max_retries == 0:
        strategy = "no_retry"
    elif max_retries == 1:
        strategy = "rebind_once"
    else:
        strategy = "bounded_rebind"

    return {
        "operation_kind": operation_kind,
        "max_attempts": max_retries + 1,
        "max_retries": max_retries,
        "strategy": strategy,
        "retry_on": _RECOVERABLE_EXCEPTION_NAMES,
    }


AD_READ_RETRY_POLICY = _build_retry_policy("read", 1)
AD_WRITE_RETRY_POLICY = _build_retry_policy("write", 0)


@dataclass(frozen=True)
class RetryTelemetry:  # pylint: disable=too-many-instance-attributes
    """Immutable record of the retry outcome for a single AD operation.

    Captured by :func:`_auto_reconnect` on every decorated call and exposed via
    :attr:`ADConnection.last_retry_telemetry` so service-layer finalizers can
    surface retry metadata on the operation envelope (issue #21). Recording is
    observational only and does not alter retry behavior.
    """

    operation_kind: str
    retry_count: int = 0
    retried: bool = False
    would_retry: bool = False
    recovered: bool = False
    policy: dict[str, Any] = field(default_factory=dict)
    attempt_count: int = 1
    operation_name: str | None = None
    failed_server: str | None = None
    selected_server: str | None = None
    elapsed_seconds: float = 0
    exception_type: str | None = None


@dataclass(frozen=True)
class _ADConnectionOptions:
    """Validated immutable settings reused by every LDAP bind."""

    receive_timeout: float
    connect_timeout: float | None
    page_size: int
    read_retry_count: int
    read_retry_backoff_seconds: float
    write_retry_count: int


def _auto_reconnect(operation_kind: str = "write"):
    """Build a decorator for bounded retries after recoverable LDAP failures."""

    def decorator(method):
        @functools.wraps(method)
        def wrapper(self, *args, **kwargs):  # pylint: disable=too-many-locals
            started_at = time.monotonic()
            attempt_count = 0
            retry_count = 0
            retried = False
            would_retry = False
            recovered = False
            failed_server_token = None
            exception_type = None
            retry_limit = (
                self.read_retry_count
                if operation_kind == "read"
                else self.write_retry_count
            )
            policy = _build_retry_policy(operation_kind, retry_limit)
            policy["backoff_seconds"] = (
                self.read_retry_backoff_seconds if operation_kind == "read" else 0
            )
            try:
                while True:
                    attempt_count += 1
                    try:
                        result = method(self, *args, **kwargs)
                        recovered = retry_count > 0
                        return result
                    except _RECOVERABLE_EXCEPTIONS as exc:
                        exception_type = type(exc).__name__
                        failed_server_token = self._mask_server_identifier(  # pylint: disable=protected-access
                            self._selected_server  # pylint: disable=protected-access
                        )
                        if retry_count >= retry_limit:
                            raise
                        would_retry = True
                        retried = True
                        retry_count += 1
                        failed_server = self._selected_server  # pylint: disable=protected-access
                        logger.warning(
                            "Recoverable LDAP %s in %s; retrying (%d/%d), controller=%s",
                            type(exc).__name__,
                            method.__name__,
                            retry_count,
                            retry_limit,
                            self._mask_server_identifier(  # pylint: disable=protected-access
                                failed_server
                            ),
                        )
                        backoff_seconds = (
                            self.read_retry_backoff_seconds
                            if operation_kind == "read"
                            else 0
                        )
                        self._rebind_after_failure(  # pylint: disable=protected-access
                            failed_server=failed_server,
                            backoff_seconds=backoff_seconds,
                        )
            finally:
                self._last_retry_telemetry = RetryTelemetry(  # pylint: disable=protected-access
                    operation_kind=operation_kind,
                    retry_count=retry_count,
                    retried=retried,
                    would_retry=would_retry,
                    recovered=recovered,
                    policy=dict(policy),
                    attempt_count=attempt_count,
                    operation_name=method.__name__,
                    failed_server=failed_server_token,
                    selected_server=self._mask_server_identifier(  # pylint: disable=protected-access
                        self._selected_server  # pylint: disable=protected-access
                    ),
                    elapsed_seconds=max(0, time.monotonic() - started_at),
                    exception_type=exception_type,
                )

        return wrapper

    return decorator


class ADConnection:  # pylint: disable=too-many-instance-attributes,too-many-public-methods
    """This class contains the functionality concerning the
    connection and the methods that gets data from AD and can modify the AD.

        Compatibility mode contract (Stage N):
        - Supported modes: ``legacy``, ``mixed``, ``strict``.
        - Mode precedence: per-call override, then service default, then environment
            default, and finally ``legacy`` fallback.
        - Invalid or empty mode values always resolve to ``legacy``.
    """

    def __init__(  # pylint: disable=too-many-arguments
        self,
        servers: list[str],
        search_base: str,
        enable_ldap_logging: bool = False,
        *,
        receive_timeout: float = 10,
        connect_timeout: float | None = None,
        page_size: int = 500,
        read_retry_count: int = 1,
        read_retry_backoff_seconds: float = 0,
        write_retry_count: int = 0,
        authentication: ADAuthenticationMode = "gssapi",
        username: str | None = None,
        password: str | None = None,
        tls: ADTLSConfig | None = None,
    ):
        self._validate_connection_options(
            receive_timeout=receive_timeout,
            connect_timeout=connect_timeout,
            page_size=page_size,
            read_retry_count=read_retry_count,
            read_retry_backoff_seconds=read_retry_backoff_seconds,
            write_retry_count=write_retry_count,
        )
        if tls is not None and not isinstance(tls, ADTLSConfig):
            raise TypeError("tls must be an ADTLSConfig or None")
        self._validate_authentication_options(
            authentication=authentication,
            username=username,
            password=password,
            tls=tls,
        )
        self._validate_tls_runtime_config(tls)
        if enable_ldap_logging:
            set_library_log_hide_sensitive_data(True)
            set_library_log_detail_level(BASIC)

        self._servers = servers
        self.search_base = search_base
        self._options = _ADConnectionOptions(
            receive_timeout=receive_timeout,
            connect_timeout=connect_timeout,
            page_size=page_size,
            read_retry_count=read_retry_count,
            read_retry_backoff_seconds=read_retry_backoff_seconds,
            write_retry_count=write_retry_count,
        )
        self._last_retry_telemetry: RetryTelemetry | None = None
        self._selected_server: str | None = None
        self._authentication = authentication
        self._username = username
        self._password = password
        self._tls_config = tls
        if tls is not None and tls.legacy_leaf_key_compatibility:
            logger.warning(
                "Legacy leaf-key compatibility is enabled; certificate and hostname "
                "validation remain required."
            )
        self.connection = self._get_connection(servers)

    @property
    def receive_timeout(self) -> float:
        """Maximum seconds to wait for an LDAP response."""
        return self._options.receive_timeout

    @property
    def connect_timeout(self) -> float | None:
        """Maximum seconds to wait for a server connection, when configured."""
        return self._options.connect_timeout

    @property
    def page_size(self) -> int:
        """Default number of entries requested per LDAP search page."""
        return self._options.page_size

    @property
    def read_retry_count(self) -> int:
        """Maximum number of retries after the initial read attempt."""
        return self._options.read_retry_count

    @property
    def read_retry_backoff_seconds(self) -> float:
        """Seconds to wait between recoverable read attempts."""
        return self._options.read_retry_backoff_seconds

    @property
    def write_retry_count(self) -> int:
        """Maximum retries for writes; disabled unless explicitly configured."""
        return self._options.write_retry_count

    @property
    def tls_config(self) -> ADTLSConfig | None:
        """Explicit TLS settings, or ``None`` for historical default behavior."""
        return self._tls_config

    @property
    def authentication_mode(self) -> ADAuthenticationMode:
        """Configured authentication mode without exposing credentials."""
        return self._authentication

    def __repr__(self) -> str:
        """Return safe connection configuration metadata without directory values."""

        tls_mode = "legacy-default" if self._tls_config is None else "explicit"
        return (
            f"ADConnection(authentication={self._authentication!r}, "
            f"tls={tls_mode!r}, servers={len(self._servers)})"
        )

    @staticmethod
    def _validate_connection_options(  # pylint: disable=too-many-arguments
        *,
        receive_timeout: float,
        connect_timeout: float | None,
        page_size: int,
        read_retry_count: int,
        read_retry_backoff_seconds: float,
        write_retry_count: int,
    ) -> None:
        """Validate connection policy before constructing LDAP objects."""

        positive_numbers = {
            "receive_timeout": receive_timeout,
            "connect_timeout": connect_timeout,
        }
        for name, value in positive_numbers.items():
            if value is None and name == "connect_timeout":
                continue
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or (isinstance(value, float) and not math.isfinite(value))
                or value <= 0
            ):
                raise ValueError(f"{name} must be a positive number")

        if isinstance(page_size, bool) or not isinstance(page_size, int) or page_size <= 0:
            raise ValueError("page_size must be a positive integer")
        if (
            isinstance(read_retry_count, bool)
            or not isinstance(read_retry_count, int)
            or read_retry_count < 0
        ):
            raise ValueError("read_retry_count must be a non-negative integer")
        if (
            isinstance(write_retry_count, bool)
            or not isinstance(write_retry_count, int)
            or write_retry_count < 0
        ):
            raise ValueError("write_retry_count must be a non-negative integer")
        if (
            isinstance(read_retry_backoff_seconds, bool)
            or not isinstance(read_retry_backoff_seconds, (int, float))
            or (
                isinstance(read_retry_backoff_seconds, float)
                and not math.isfinite(read_retry_backoff_seconds)
            )
            or read_retry_backoff_seconds < 0
        ):
            raise ValueError("read_retry_backoff_seconds must be a non-negative number")

    @property
    def last_retry_telemetry(self) -> RetryTelemetry | None:
        """Retry telemetry recorded for the most recent decorated AD operation.

        Returns ``None`` until at least one auto-reconnect-wrapped operation has
        run on this connection. Service-layer finalizers read this immediately
        after an operation to surface retry metadata on the response envelope.
        """

        return self._last_retry_telemetry

    @staticmethod
    def _validate_tls_runtime_config(tls: ADTLSConfig | None) -> None:
        """Preflight explicit trust and cipher settings without exposing values."""

        if tls is None:
            return

        context = ssl.create_default_context()
        ciphers = (
            _LEGACY_LEAF_KEY_CIPHERS
            if tls.legacy_leaf_key_compatibility
            else tls.ciphers
        )
        try:
            if ciphers is not None:
                context.set_ciphers(ciphers)
            if tls.ca_certs_file or tls.ca_certs_path or tls.ca_certs_data:
                context.load_verify_locations(
                    cafile=tls.ca_certs_file,
                    capath=tls.ca_certs_path,
                    cadata=tls.ca_certs_data,
                )
        except (OSError, ValueError, ssl.SSLError) as exc:
            raise ADTLSConfigurationError() from exc

    @staticmethod
    def _validate_authentication_options(
        *,
        authentication: str,
        username: str | None,
        password: str | None,
        tls: ADTLSConfig | None,
    ) -> None:
        """Validate authentication inputs before constructing LDAP objects."""

        if authentication not in ("gssapi", "simple"):
            raise ValueError("authentication must be 'gssapi' or 'simple'")
        if authentication == "gssapi":
            if username is not None or password is not None:
                raise ValueError("username and password must be omitted for gssapi")
            return
        if not isinstance(username, str) or not username.strip():
            raise ValueError("username must be a non-empty string for simple authentication")
        if not isinstance(password, str) or not password:
            raise ValueError("password must be a non-empty string for simple authentication")
        if tls is None or tls.validate != ssl.CERT_REQUIRED:
            raise ValueError("simple authentication requires validated TLS")

    @staticmethod
    def _scrub_bound_simple_credentials(connection: Connection) -> None:
        """Remove simple-bind credentials from the bound ldap3 representation."""

        connection.user = None
        connection.password = None

    @staticmethod
    def _secure_server_endpoint(server: str) -> tuple[str, int | None]:
        """Return a host and optional port suitable for validated TLS."""

        candidate = server.strip()
        parsed = urlsplit(candidate if "://" in candidate else f"//{candidate}")
        host = parsed.hostname
        if not host:
            raise ValueError("Configured server must include a valid host")
        try:
            port = parsed.port
        except ValueError as exc:
            raise ValueError("Configured server must include a valid port") from exc
        return host, port

    @staticmethod
    def _build_explicit_tls(tls: ADTLSConfig, server_host: str) -> Tls:
        """Build a per-server ldap3 TLS object from validated explicit config."""

        ciphers = (
            _LEGACY_LEAF_KEY_CIPHERS
            if tls.legacy_leaf_key_compatibility
            else tls.ciphers
        )
        return Tls(
            validate=tls.validate,
            version=tls.version,
            ssl_options=tls.ssl_options,
            ca_certs_file=tls.ca_certs_file,
            ca_certs_path=tls.ca_certs_path,
            ca_certs_data=tls.ca_certs_data,
            valid_names=tls.valid_names,
            ciphers=ciphers,
            sni=server_host,
        )

    def _get_connection(self, servers: list[str]) -> Connection:  # pylint: disable=too-many-locals
        """initializes a connection to the active directory.
        """
        if not servers:
            raise ADMissingServersError  # Explicitly handle empty server list

        if self._tls_config is None:
            tls = Tls(validate=ssl.CERT_NONE, version=ssl.PROTOCOL_TLSv1_2)
            server_options = {"use_ssl": True, "tls": tls}
            if self.connect_timeout is not None:
                server_options["connect_timeout"] = self.connect_timeout
            ldap_servers = [Server(server, **server_options) for server in servers]
        else:
            ldap_servers = []
            for server in servers:
                server_host, server_port = self._secure_server_endpoint(server)
                server_options = {
                    "use_ssl": True,
                    "tls": self._build_explicit_tls(self._tls_config, server_host),
                }
                if server_port is not None:
                    server_options["port"] = server_port
                if self.connect_timeout is not None:
                    server_options["connect_timeout"] = self.connect_timeout
                ldap_servers.append(Server(server_host, **server_options))

        server_pool = ServerPool(ldap_servers, ROUND_ROBIN, active=True, exhaust=True)

        connection_options: dict[str, Any] = {
            "receive_timeout": self.receive_timeout,
        }
        if self._authentication == "simple":
            connection_options.update({
                "authentication": SIMPLE,
                "user": self._username,
                "password": self._password,
                "auto_referrals": False,
            })
        else:
            connection_options.update({
                "authentication": SASL,
                "sasl_mechanism": GSSAPI,
            })
        connection = Connection(server_pool, **connection_options)
        try:
            bound = connection.bind()
        except LDAPException as exc:
            controller = self._mask_server_identifier(
                self._bound_server_identifier(connection)
            )
            raise ADBindError(None, controller) from exc
        if not bound:
            result = connection.result if isinstance(connection.result, dict) else {}
            result_code = result.get("result")
            controller = self._mask_server_identifier(
                self._bound_server_identifier(connection)
            )
            raise ADBindError(result_code, controller)
        if self._authentication == "simple":
            self._scrub_bound_simple_credentials(connection)
        self._selected_server = self._bound_server_identifier(connection)
        return connection

    @staticmethod
    def _bound_server_identifier(connection: Connection) -> str | None:
        """Return the bound server host for internal failover decisions."""

        server = getattr(connection, "server", None)
        host = getattr(server, "host", None)
        return host if isinstance(host, str) else None

    @staticmethod
    def _normalize_server_identifier(server: str) -> str:
        """Normalize configured URLs and bound hosts for internal comparison."""

        candidate = server.strip()
        parsed = urlsplit(candidate if "://" in candidate else f"//{candidate}")
        return (parsed.hostname or candidate).casefold()

    @classmethod
    def _mask_server_identifier(cls, server: str | None) -> str:
        """Return a stable non-reversible controller token for logs and telemetry."""

        if not server:
            return "controller-unknown"
        normalized = cls._normalize_server_identifier(server)
        digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:8]
        return f"controller-{digest}"

    def _prioritize_alternate_servers(self, failed_server: str | None) -> list[str]:
        """Order configured controllers with the failed controller last."""

        if not failed_server or len(self._servers) < 2:
            return list(self._servers)
        normalized_failed = self._normalize_server_identifier(failed_server)
        alternates = [
            server
            for server in self._servers
            if self._normalize_server_identifier(server) != normalized_failed
        ]
        failed = [
            server
            for server in self._servers
            if self._normalize_server_identifier(server) == normalized_failed
        ]
        return alternates + failed if alternates else list(self._servers)

    def _rebind_after_failure(
        self,
        *,
        failed_server: str | None,
        backoff_seconds: float,
    ) -> None:
        """Close a failed connection, back off, and prefer another controller."""

        self._close_connection()
        if backoff_seconds > 0:
            time.sleep(backoff_seconds)
        ordered_servers = self._prioritize_alternate_servers(failed_server)
        self.connection = self._get_connection(ordered_servers)

    def rebind(self) -> None:
        """Re-establish the LDAP connection using the original server list.

        Call this explicitly to force a fresh bind, or rely on the automatic
        reconnect behaviour built into every public operation method.
        """
        logger.info("Re-binding to Active Directory.")
        self._close_connection()
        self.connection = self._get_connection(self._servers)

    def _close_connection(self) -> None:
        """Attempt to cleanly close the current LDAP connection."""
        try:
            self.connection.unbind()
        except (LDAPSessionTerminatedByServerError, LDAPCommunicationError, OSError):
            logger.debug("Could not cleanly unbind the previous connection.")

    def _get_paged_search(  # pylint: disable=too-many-arguments
        self,
        search_filter: str,
        attributes: list[str] | str,
        *,
        search_base: str,
        search_scope: str,
        page_size: int,
    ):
        """Returns a entry_generator.
        """
        entry_generator = self.connection.extend.standard.paged_search(
            search_base=search_base,
            search_filter=search_filter,
            search_scope=search_scope,
            attributes=attributes,
            paged_size=page_size,
            generator=True,
        )
        return entry_generator

    @staticmethod
    def _validate_search_options(
        search_base: str | None,
        search_scope: str,
        page_size: int | None,
    ) -> None:
        """Validate per-search overrides before invoking LDAP."""

        if search_base is not None and (
            not isinstance(search_base, str) or not search_base.strip()
        ):
            raise ValueError("search_base must be a non-empty string or None")
        if search_scope not in _SUPPORTED_SEARCH_SCOPES:
            raise ValueError("search_scope must be BASE, LEVEL, or SUBTREE")
        if page_size is not None and (
            isinstance(page_size, bool) or not isinstance(page_size, int) or page_size <= 0
        ):
            raise ValueError("page_size must be a positive integer or None")

    def _set_ou_for_object(self, ad_object: dict[str, Any]) -> None:
        """Add the OU extracted from ``distinguishedName`` to ``ad_object`` in place."""

        if 'distinguishedName' not in ad_object or 'ou' in ad_object:
            return

        distinguished_name = ad_object['distinguishedName']
        if not isinstance(distinguished_name, str):
            return
        try:
            parsed_components = parse_dn(
                distinguished_name,
                escape=True,
                strip=True,
            )
        except LDAPInvalidDnError:
            return
        first_rdn_end = next(
            (
                index
                for index, (_attribute, _value, separator) in enumerate(parsed_components)
                if separator != '+'
            ),
            len(parsed_components) - 1,
        )
        parent_components = parsed_components[first_rdn_end + 1:]
        if parent_components:
            ad_object['ou'] = ''.join(
                f"{attribute}={value}{separator}"
                for attribute, value, separator in parent_components
            )

    @_auto_reconnect("read")
    def search(  # pylint: disable=too-many-arguments
        self,
        search_filter: str,
        attributes: list[str] | None = None,
        *,
        search_base: str | None = None,
        search_scope: str = SUBTREE,
        page_size: int | None = None,
    ) -> list[dict[str, str]]:
        """Returns a single result or false if none exist.

        Args:
            search_filter (str): An LDAP filter string.
            attributes (list[str]): A list of attributes that will be fetched.
            search_base (str | None): Base DN override; ``None`` uses the connection default.
            search_scope (str): One of the standard ``ldap3`` search scope constants.
            page_size (int | None): Page-size override; ``None`` uses the connection default.

        Returns:
            list[dict[str, str]]: AD objects presented as dictionaries.
        """

        if attributes is None:
            attributes = ALL_ATTRIBUTES

        self._validate_search_options(search_base, search_scope, page_size)
        effective_search_base = self.search_base if search_base is None else search_base
        effective_page_size = self.page_size if page_size is None else page_size
        entry_generator = self._get_paged_search(
            search_filter,
            attributes,
            search_base=effective_search_base,
            search_scope=search_scope,
            page_size=effective_page_size,
        )
        result_list = [x['attributes'] for x in entry_generator if 'attributes' in x]
        for ad_object in result_list:
            self._set_ou_for_object(ad_object)
        return result_list

    def get_v2(
        self, search_filter: str, attributes: list[str] | None = None
    ) -> ADGetResult:
        """Read a single AD object as a typed, found/not-found-aware envelope.

        Returns an :class:`ADGetResult` envelope with an explicit ``found`` flag
        and a deterministic ``not_found_reason`` so callers can tell "absent"
        from "present but empty".

        Not-found semantics are deterministic: a search returning zero rows
        yields ``found=False`` with ``not_found_reason="no_match"``. When several
        rows match, the first is returned as ``found=True``.

        Args:
            search_filter (str): An LDAP filter string.
            attributes (list[str] | None): Attributes to fetch; ``None`` fetches
                ``ALL_ATTRIBUTES``.

        Returns:
            ADGetResult: A typed found/not-found envelope.
        """

        search_result = self.search(search_filter, attributes)
        if search_result:
            return ADGetResult.found_item(search_result[0])
        return ADGetResult.not_found()

    @staticmethod
    def _parse_ranged_attribute(
        attributes: dict[str, Any], attribute: str
    ) -> tuple[list[str], int | None]:
        """Extract values and the next range start from a ranged search result.

        Active Directory returns large multi-valued attributes under a ranged
        key such as ``member;range=0-1499``. This inspects ``attributes`` for
        either the plain ``attribute`` key (small object, whole value returned)
        or its ranged variant and returns ``(values, next_start)`` where
        ``next_start`` is ``None`` once the terminal range (``*``) is reached.
        """

        for key, value in attributes.items():
            if key != attribute and not key.startswith(f"{attribute};range="):
                continue
            values = value if isinstance(value, list) else [value]
            if not values:
                # AD may echo the requested range back as an empty attribute
                # (for example ``member;range=0-*``) alongside the real bounded
                # range (``member;range=0-1499``). Skip empty echoes so the
                # non-empty range drives assembly instead of stopping early.
                continue
            if ";range=" not in key:
                return values, None
            high = key.rsplit("-", 1)[-1]
            if high == "*":
                return values, None
            return values, int(high) + 1
        return [], None

    @_auto_reconnect("read")
    def get_ranged_attribute(
        self,
        distinguished_name: str,
        attribute: str,
        limit: int | None = None,
    ) -> list[str]:
        """Retrieve all values of a multi-valued attribute via LDAP ranged reads.

        Active Directory caps how many values of a multi-valued attribute (for
        example ``member`` on a large group) it returns at once and exposes the
        remainder through the ``attribute;range=lo-hi`` mechanism. This walks
        every range (base-scoped reads of ``distinguished_name``) until the
        server returns the terminal range and returns the assembled values in
        server order. Returns ``[]`` when the object or attribute is absent.

        Args:
            distinguished_name (str): DN of the object to read.
            attribute (str): The multi-valued attribute to assemble.
            limit (int | None): Optional early-stop bound. When provided, range
                reads stop as soon as at least ``limit`` values are collected and
                the result is truncated to ``limit``; this avoids unbounded LDAP
                traffic/memory for very large attributes when the caller only
                needs a bounded number of values. ``None`` reads every range.

        Returns:
            list[str]: Values of ``attribute`` in server order (at most ``limit``
            when ``limit`` is set).
        """

        values: list[str] = []
        start = 0
        while True:
            ranged_key = f"{attribute};range={start}-*"
            found = self.connection.search(
                search_base=distinguished_name,
                search_filter="(objectClass=*)",
                search_scope=BASE,
                attributes=[ranged_key],
            )
            if not found or not self.connection.response:
                break
            entry_attributes = self.connection.response[0].get("attributes", {}) or {}
            chunk, next_start = self._parse_ranged_attribute(entry_attributes, attribute)
            values.extend(chunk)
            if limit is not None and len(values) >= limit:
                return values[:limit]
            if next_start is None:
                break
            start = next_start
        return values

    @_auto_reconnect("write")
    def modify(self, distinguished_name: str, changes: list[tuple[str, str]]) -> dict[str, Any]:
        """Takes in distinguished_name and dict of changes.

        Example:
            modify(user_distinguishedName, [('departmentNumber': '11122')])

        Args:
            distinguished_name (str): A distinguished name of a AD User.
            changes (list[tuple[str, str]]): [('AD field name': 'new field value')]

        Returns:
            dict[str, Any]: The result from the attempted modification
        """

        changes = {key: [MODIFY_REPLACE, value] for key, value in changes}
        success = self.connection.modify(distinguished_name, changes)
        return {'result': self.connection.result, 'success': success}

    @_auto_reconnect("write")
    def add_value(self, distinguished_name: str, changes: dict[str, str]) -> dict[str, Any]:
        """Takes in distinguished_name and dict of field and value where the value is added to
        the field specified, this is very useful to add a value to a list.

        Example:
            modify(group_distinguishedName, {'member': 'user_distinguishedName'})

        Args:
            distinguished_name (str): A distinguished name of a AD Object.
            changes (dict[str, str]): {'AD field name': 'value to be added'}

        Returns:
            dict[str, Any]: The result from the attempted addition
        """

        changes = {key: [MODIFY_ADD, value] for key, value in changes.items()}
        success = self.connection.modify(distinguished_name, changes)
        return {'result': self.connection.result, 'success': success}

    @_auto_reconnect("write")
    def remove_value(self, distinguished_name: str, changes: dict[str, str]) -> dict[str, Any]:
        """Takes in distinguished_name and dict of field and value where the specified value is
        removed to the field specified, this is very useful to add a value to a
        list.

        Example:
            modify(group_distinguishedName, {'member': 'user_distinguishedName'})

        Args:
            distinguished_name (str): A distinguished name of a AD Object.
            changes (dict[str, str]): {'AD field name': 'value to be deleted'}

        Returns:
            dict[str, Any]: The result from the attempted addition
        """

        changes = {key: [MODIFY_DELETE, value] for key, value in changes.items()}
        success = self.connection.modify(distinguished_name, changes)
        return {'result': self.connection.result, 'success': success}

    def add_member(self, user_dn: str, group_dn: str):
        """Takes in a user distinguishedName and a group distinguishedName adds the specified user
        to the group in AD.

        Args:
            user_dn (str): AD user distinguishedName
            group_dn (str): AD group distinguishedName

        Returns:
            str: The result from the attempt to add the user to the group
        """

        changes = {'member': user_dn}
        return self.add_value(group_dn, changes)

    def remove_member(self, user_dn: str, group_dn: str):
        """Takes in a user distinguishedName and a group distinguishedName removes the specified
        user from the group in AD.

        Args:
            user_dn (str): AD user distinguishedName
            group_dn (str): AD group distinguishedName

        Returns:
            str: The result from the attempt to remove the user from the group
        """

        changes = {'member': user_dn}
        return self.remove_value(group_dn, changes)

    @_auto_reconnect("write")
    def move_entry(self, distinguished_name: str, new_ou_dn: str) -> dict[str, Any]:
        """Move an AD object to the provided OU while keeping the same relative DN.

        Args:
            distinguished_name (str): Current distinguished name for the AD object.
            new_ou_dn (str): Target OU distinguished name to move the object under.

        Returns:
            dict[str, Any]: Result payload containing the LDAP response and success flag.
        """

        relative_dn = distinguished_name.split(',', 1)[0]
        success = self.connection.modify_dn(
            distinguished_name,
            relative_dn,
            new_superior=new_ou_dn,
        )
        return {'result': self.connection.result, 'success': success}

    @_auto_reconnect("write")
    def rename_dn(self, distinguished_name: str, new_relative_dn: str) -> dict[str, Any]:
        """Rename an AD object's relative DN (CN) while keeping it in the same OU.

        Args:
            distinguished_name (str): Current distinguished name for the AD object.
            new_relative_dn (str): New relative DN (e.g., 'CN=NewName').

        Returns:
            dict[str, Any]: Result payload containing the LDAP response and success flag.
        """
        success = self.connection.modify_dn(
            distinguished_name,
            new_relative_dn,
        )
        return {'result': self.connection.result, 'success': success}


    # ---------------------------------------------------------------------
    # Create new user
    # ---------------------------------------------------------------------
    @_auto_reconnect("write")
    def add_entry(self, distinguished_name: str, attributes: dict[str, object]) -> dict[str, Any]:
        """Create a new AD object (e.g., user) at the given DN with the provided attributes.
        `attributes` MUST include a valid objectClass list,
        e.g., ['top', 'person', 'organizationalPerson', 'user'].
        """

        success = self.connection.add(distinguished_name, attributes=attributes)
        return {'result': self.connection.result, 'success': success}

    @_auto_reconnect("write")
    def set_password(self, distinguished_name: str, new_password: str) -> dict[str, Any]:
        """Set the user's password. Requires LDAPS/StartTLS and appropriate rights.
        """
        password_ext = self.connection.extend.microsoft
        success = password_ext.modify_password(distinguished_name, new_password)
        return {'result': self.connection.result, 'success': success}

    @_auto_reconnect("write")
    def force_change_password_at_next_logon(
        self, distinguished_name: str, force: bool = True
    ) -> dict[str, Any]:
        """Set or clear the 'User must change password at next logon' flag.

        Args:
            distinguished_name (str): The user's distinguished name.
            force (bool): If True, user must change password at next logon.
                          If False, clears the flag (sets pwdLastSet to -1).

        Returns:
            dict[str, Any]: Result payload containing the LDAP response and success flag.
        """
        # pwdLastSet = 0 means "must change password at next logon"
        # pwdLastSet = -1 means "set to current time" (clears the flag)
        pwd_last_set_value = 0 if force else -1
        changes = {'pwdLastSet': [MODIFY_REPLACE, pwd_last_set_value]}
        success = self.connection.modify(distinguished_name, changes)
        return {'result': self.connection.result, 'success': success}

    @_auto_reconnect("write")
    def enable_user(self, distinguished_name: str) -> dict[str, Any]:
        """Enable an AD user by setting userAccountControl to 512 (NORMAL_ACCOUNT).
        """

        changes = {'userAccountControl': [MODIFY_REPLACE, 512]}
        success = self.connection.modify(distinguished_name, changes)
        return {'result': self.connection.result, 'success': success}

    @_auto_reconnect("write")
    def disable_user(self, distinguished_name: str) -> dict[str, Any]:
        """Disable an AD user by setting userAccountControl to 514 (ACCOUNTDISABLE).
        """

        changes = {'userAccountControl': [MODIFY_REPLACE, 514]}
        success = self.connection.modify(distinguished_name, changes)
        return {'result': self.connection.result, 'success': success}

"""This module contains the functionality concerning the
connection and the methods that gets data from AD and can modify the AD.

This module was build as an "in the same domain" AD connection and has no plans
to extend to being able to connect through a custom user and password. Hence
this package will need a user that has the required permissions to edit/read the
AD to run it effectively.
"""

import collections
import functools
import logging
import os
import ssl
from dataclasses import dataclass, field
from typing import Any

from ldap3.utils.log import set_library_log_detail_level, BASIC
from ldap3 import (ALL_ATTRIBUTES, BASE, MODIFY_ADD, MODIFY_DELETE,
                   MODIFY_REPLACE, ROUND_ROBIN, SASL, SUBTREE, GSSAPI,
                   Connection, Server, ServerPool, Tls)
from ldap3.core.exceptions import LDAPCommunicationError, LDAPSessionTerminatedByServerError

from python_apis.deprecation import warn_legacy
from python_apis.models.ad_get import ADGetResult

logger = logging.getLogger(__name__)

_RECOVERABLE_EXCEPTIONS = (LDAPSessionTerminatedByServerError, LDAPCommunicationError)
_RECOVERABLE_EXCEPTION_NAMES = tuple(exc.__name__ for exc in _RECOVERABLE_EXCEPTIONS)

AD_COMPATIBILITY_MODES = ('legacy', 'mixed', 'strict')
AD_DEFAULT_COMPATIBILITY_MODE = 'legacy'
AD_COMPATIBILITY_ENV_VAR = 'PYTHON_APIS_AD_COMPAT_MODE'


def _build_retry_policy(operation_kind: str) -> dict[str, Any]:
    """Describe the current retry policy for a given operation classification.

    The policy is descriptive (not a control knob in Stage N): every decorated
    AD operation retries at most once after a rebind when a recoverable
    transport/session error is raised, so reads and writes currently share the
    same ``rebind_once`` behavior.
    """

    return {
        "operation_kind": operation_kind,
        "max_attempts": 2,
        "max_retries": 1,
        "strategy": "rebind_once",
        "retry_on": _RECOVERABLE_EXCEPTION_NAMES,
    }


AD_READ_RETRY_POLICY = _build_retry_policy("read")
AD_WRITE_RETRY_POLICY = _build_retry_policy("write")
_RETRY_POLICY_BY_KIND = {
    "read": AD_READ_RETRY_POLICY,
    "write": AD_WRITE_RETRY_POLICY,
}


@dataclass(frozen=True)
class RetryTelemetry:
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


def resolve_ad_compatibility_mode(
    per_call_mode: str | None = None,
    service_mode: str | None = None,
    env_mode: str | None = None,
) -> str:
    """Resolve the effective AD compatibility mode.

    Precedence is deterministic and shared across AD APIs/services:
    `per_call_mode` -> `service_mode` -> environment variable
    (`PYTHON_APIS_AD_COMPAT_MODE`) -> `legacy`.

    Any unknown, empty, or whitespace-only mode value falls back to `legacy`.
    """

    selected_env_mode = env_mode if env_mode is not None else os.getenv(AD_COMPATIBILITY_ENV_VAR)
    candidates = (per_call_mode, service_mode, selected_env_mode)
    for mode in candidates:
        if mode is None:
            continue
        normalized_mode = str(mode).strip().lower()
        if not normalized_mode:
            continue
        if normalized_mode in AD_COMPATIBILITY_MODES:
            return normalized_mode
        logger.warning(
            "Unsupported AD compatibility mode '%s'. Falling back to '%s'.",
            mode,
            AD_DEFAULT_COMPATIBILITY_MODE,
        )
        return AD_DEFAULT_COMPATIBILITY_MODE

    return AD_DEFAULT_COMPATIBILITY_MODE


def _auto_reconnect(operation_kind: str = "write"):
    """Build a decorator that retries once after a rebind on recoverable errors.

    ``operation_kind`` (``"read"`` or ``"write"``) selects the descriptive retry
    policy attached to the recorded :class:`RetryTelemetry`. The control flow is
    unchanged from the historic behavior: the wrapped method is retried at most
    once after :meth:`ADConnection.rebind` when a recoverable LDAP
    session/communication error is raised. Telemetry is recorded for every call
    (including the no-retry success path) on the connection instance.
    """

    policy = _RETRY_POLICY_BY_KIND.get(operation_kind, AD_WRITE_RETRY_POLICY)

    def decorator(method):
        @functools.wraps(method)
        def wrapper(self, *args, **kwargs):
            retry_count = 0
            retried = False
            would_retry = False
            recovered = False
            try:
                try:
                    return method(self, *args, **kwargs)
                except _RECOVERABLE_EXCEPTIONS as exc:
                    logger.warning(
                        "LDAP session error in %s, attempting rebind: %s",
                        method.__name__, exc,
                    )
                    would_retry = True
                    retried = True
                    retry_count = 1
                    self.rebind()
                    result = method(self, *args, **kwargs)
                    recovered = True
                    return result
            finally:
                self._last_retry_telemetry = RetryTelemetry(  # pylint: disable=protected-access
                    operation_kind=operation_kind,
                    retry_count=retry_count,
                    retried=retried,
                    would_retry=would_retry,
                    recovered=recovered,
                    policy=dict(policy),
                )

        return wrapper

    return decorator


class ADConnectionError(Exception):
    """Custom exception for errors related to Active Directory connections."""


class ADMissingServersError(Exception):
    """Custom exception for errors related to missing Active Directory servers."""


class ADConnection:
    """This class contains the functionality concerning the
    connection and the methods that gets data from AD and can modify the AD.

        Compatibility mode contract (Stage N):
        - Supported modes: ``legacy``, ``mixed``, ``strict``.
        - Mode precedence: per-call override, then service default, then environment
            default, and finally ``legacy`` fallback.
        - Invalid or empty mode values always resolve to ``legacy``.
    """

    def __init__(
        self,
        servers: list,
        search_base: str,
        enable_ldap_logging: bool = False,
        compatibility_mode: str | None = None,
    ):
        if enable_ldap_logging:
            set_library_log_detail_level(BASIC)

        self._servers = servers
        self.compatibility_mode = resolve_ad_compatibility_mode(service_mode=compatibility_mode)
        self.connection = self._get_connection(servers)
        self.search_base = search_base
        self._last_retry_telemetry: RetryTelemetry | None = None

    @property
    def last_retry_telemetry(self) -> RetryTelemetry | None:
        """Retry telemetry recorded for the most recent decorated AD operation.

        Returns ``None`` until at least one auto-reconnect-wrapped operation has
        run on this connection. Service-layer finalizers read this immediately
        after an operation to surface retry metadata on the response envelope.
        """

        return self._last_retry_telemetry

    def _get_connection(self, servers: list) -> Connection:
        """initializes a connection to the active directory.
        """
        if not servers:
            raise ADMissingServersError  # Explicitly handle empty server list

        tls = Tls(validate=ssl.CERT_NONE, version=ssl.PROTOCOL_TLSv1_2)
        ldap_servers = [Server(x, use_ssl=True, tls=tls) for x in servers]

        server_pool = ServerPool(ldap_servers, ROUND_ROBIN, active=True, exhaust=True)

        connection = Connection(
            server_pool,
            authentication=SASL,
            sasl_mechanism=GSSAPI,
            receive_timeout=10,
        )
        if not connection.bind():
            raise ADConnectionError(
                f"Failed to bind to Active Directory: {connection.result['description']}"
            )
        return connection

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

    def _get_paged_search(self, search_filter: str, attributes: list[str]):
        """Returns a entry_generator.
        """
        entry_generator = self.connection.extend.standard.paged_search(
            search_base=self.search_base,
            search_filter=search_filter,
            search_scope=SUBTREE,
            attributes=attributes,
            paged_size=500,
            generator=True,
        )
        return entry_generator

    def _set_ou_for_object(self, ad_object: dict[str, Any]) -> None:
        """Add the OU extracted from ``distinguishedName`` to ``ad_object`` in place."""

        if 'distinguishedName' not in ad_object or 'ou' in ad_object:
            return

        distinguished_name = ad_object['distinguishedName']
        if ',' not in distinguished_name:
            return

        ad_object['ou'] = ','.join(distinguished_name.split(',')[1:])

    @_auto_reconnect("read")
    def search(
        self, search_filter: str, attributes: list[str] | None = None
    ) -> list[dict[str, str]]:
        """Returns a single result or false if none exist.

        Args:
            search_filter (str): An LDAP filter string.
            attributes (list[str]): A list of attributes that will be fetched.

        Returns:
            list[dict[str, str]]: AD objects presented as dictionaries.
        """

        if attributes is None:
            attributes = ALL_ATTRIBUTES

        entry_generator = self._get_paged_search(search_filter, attributes)
        result_list = [x['attributes'] for x in entry_generator if 'attributes' in x]
        for ad_object in result_list:
            self._set_ou_for_object(ad_object)
        return result_list

    def get(self, search_filter: str, attributes: list[str] | None = None) -> dict[str, str]:
        """Returns a single result, the first result if more then one result
        is matched and an empty dict if zero results where returned.

        .. deprecated::
            Prefer :meth:`get_v2`, which returns a typed :class:`ADGetResult`
            with an explicit ``found`` flag. The legacy empty-default mapping is
            indistinguishable from a real object whose attributes are all empty.

            Before (legacy, ambiguous)::

                obj = conn.get("(sAMAccountName=jdoe)", ["cn"])
                if obj.get("cn"):   # empty default vs present-but-empty
                    ...

            After (typed, unambiguous)::

                res = conn.get_v2("(sAMAccountName=jdoe)", ["cn"])
                if res.found:
                    use(res.item)

            See ``python_apis.discovery.get_capability('get-v2')`` and
            ``python_apis.migration_examples.legacy_get_to_get_v2()``.

        Args:
            search_filter (str): An LDAP filter string.
            attributes (list[str] | None): Attributes to fetch; ``None`` fetches
                ``ALL_ATTRIBUTES``.

        Returns:
            dict[str, str]: AD object as a dict, empty values if none were found.
        """

        warn_legacy(
            "ADConnection.get",
            replacement="ADConnection.get_v2",
            migration_hint=(
                "Branch on ADGetResult.found instead of probing the empty default "
                "mapping; see python_apis.discovery.get_capability('get-v2')."
            ),
        )
        search_result = self.search(search_filter, attributes)
        return search_result[0] if len(search_result) > 0 else collections.defaultdict(lambda: '')

    def get_v2(
        self, search_filter: str, attributes: list[str] | None = None
    ) -> ADGetResult:
        """Typed, found/not-found-aware counterpart of :meth:`get`.

        Unlike :meth:`get`, which returns an empty ``defaultdict`` when nothing
        matches (indistinguishable from a real object whose attributes are all
        empty), this returns an :class:`ADGetResult` envelope with an explicit
        ``found`` flag and a deterministic ``not_found_reason`` so callers can
        tell "absent" from "present but empty". The legacy :meth:`get` is
        unchanged.

        Not-found semantics are deterministic: a search returning zero rows
        yields ``found=False`` with ``not_found_reason="no_match"``. When several
        rows match, the first is returned as ``found=True`` (matching :meth:`get`).

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

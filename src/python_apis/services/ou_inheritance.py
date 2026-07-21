"""Consumer-neutral rules for resolving inherited OU attributes."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from python_apis.models.ad_ou import (
    ADOrganizationalUnit,
    CanonicalDistinguishedName,
    canonicalize_distinguished_name,
)


class OUInheritanceCycleError(ValueError):
    """Raised when OU parent links contain a cycle."""


@dataclass(frozen=True)
class OUAttributeRule:
    """Describe how one caller-selected output value is inherited from OUs."""

    source: str
    aliases: tuple[str, ...] = ()
    default: object | None = None
    normalize: Callable[[object], object] | None = None
    accept: Callable[[object], bool] | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.source, str) or not self.source.strip():
            raise ValueError("OU rule source must be a non-empty string")
        names = (self.source, *self.aliases)
        if any(not isinstance(name, str) or not name.strip() for name in names):
            raise ValueError("OU rule aliases must be non-empty strings")
        folded_names = [name.casefold() for name in names]
        if len(folded_names) != len(set(folded_names)):
            raise ValueError("OU rule source and aliases must be unique")
        if self.normalize is not None and not callable(self.normalize):
            raise ValueError("OU rule normalize must be callable or None")
        if self.accept is not None and not callable(self.accept):
            raise ValueError("OU rule accept must be callable or None")


def _build_ancestor_path(
    ou_dn: str,
    ou_tree: Mapping[str, ADOrganizationalUnit],
) -> list[ADOrganizationalUnit]:
    """Build a nearest-first path and reject cyclic parent links."""

    canonical_tree = {
        canonicalize_distinguished_name(tree_dn): organizational_unit
        for tree_dn, organizational_unit in ou_tree.items()
    }
    current = canonical_tree.get(canonicalize_distinguished_name(ou_dn))
    path: list[ADOrganizationalUnit] = []
    visited: set[CanonicalDistinguishedName] = set()
    while current is not None:
        distinguished_name = current.distinguishedName
        if not isinstance(distinguished_name, str) or not distinguished_name:
            raise ValueError("OU tree contains an invalid distinguished name")
        cycle_key = canonicalize_distinguished_name(distinguished_name)
        if cycle_key in visited:
            raise OUInheritanceCycleError("Cycle detected in OU hierarchy")
        visited.add(cycle_key)
        path.append(current)
        current = current.parent
    return path


def _read_ou_attribute(organizational_unit: ADOrganizationalUnit, name: str) -> Any:
    """Read a modeled or arbitrary LDAP attribute case-insensitively."""

    requested_name = name.casefold()
    for attribute, value in organizational_unit.ldap_attributes.items():
        if attribute.casefold() == requested_name:
            return value
    for attribute, value in vars(organizational_unit).items():
        if attribute.casefold() == requested_name:
            return value
    return getattr(organizational_unit, name, None)


def _is_empty(value: object) -> bool:
    """Return whether a candidate is absent for inheritance purposes."""

    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple, set, dict)):
        return not value
    return False


def _resolve_rule(
    path: list[ADOrganizationalUnit],
    rule: OUAttributeRule,
) -> object | None:
    """Resolve one rule against a prevalidated nearest-first OU path."""

    for organizational_unit in path:
        for attribute in (rule.source, *rule.aliases):
            candidate = _read_ou_attribute(organizational_unit, attribute)
            if _is_empty(candidate):
                continue
            if rule.normalize is not None:
                candidate = rule.normalize(candidate)
            if _is_empty(candidate):
                continue
            if rule.accept is None or rule.accept(candidate):
                return candidate
    return rule.default


def resolve_inherited_attributes(
    ou_dn: str,
    rules: Mapping[str, OUAttributeRule],
    ou_tree: Mapping[str, ADOrganizationalUnit],
) -> dict[str, object | None]:
    """Resolve caller-selected outputs from the immediate OU toward the root."""

    if not isinstance(ou_dn, str) or not ou_dn.strip():
        raise ValueError("ou_dn must be a non-empty string")
    for target, rule in rules.items():
        if not isinstance(target, str) or not target.strip():
            raise ValueError("OU rule targets must be non-empty strings")
        if not isinstance(rule, OUAttributeRule):
            raise TypeError("OU rule values must be OUAttributeRule instances")

    path = _build_ancestor_path(ou_dn, ou_tree)
    return {
        target: _resolve_rule(path, rule)
        for target, rule in rules.items()
    }

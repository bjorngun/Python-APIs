"""Typed results for strict Active Directory membership reads."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

AD_NOT_FOUND_CODE = "AD_NOT_FOUND"
ADGroupNotFoundReason = Literal["group_not_found"]


class ADGroupMembersResult(BaseModel):
    """Distinguish found membership, valid empty, and missing group outcomes."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    group_found: bool
    members: tuple[str, ...] = Field(default_factory=tuple)
    not_found_reason: ADGroupNotFoundReason | None = None
    error_code: str | None = None

    @field_validator("members")
    @classmethod
    def _normalize_members(cls, members: tuple[str, ...]) -> tuple[str, ...]:
        """Require normalized identities and return deterministic unique order."""

        if any(
            not isinstance(member, str)
            or not member
            or member != member.casefold()
            for member in members
        ):
            raise ValueError("members must contain non-empty casefolded strings")
        return tuple(sorted(set(members)))

    @model_validator(mode="after")
    def _validate_outcome(self) -> "ADGroupMembersResult":
        """Reject contradictory found and not-found result states."""

        if self.group_found:
            if self.not_found_reason is not None or self.error_code is not None:
                raise ValueError("found group cannot carry not-found metadata")
        else:
            if self.members:
                raise ValueError("missing group cannot carry members")
            if self.not_found_reason != "group_not_found":
                raise ValueError("missing group requires group_not_found reason")
            if self.error_code != AD_NOT_FOUND_CODE:
                raise ValueError("missing group requires AD_NOT_FOUND error code")
        return self

    @classmethod
    def found(cls, members: set[str] | tuple[str, ...]) -> "ADGroupMembersResult":
        """Build a found result, including a valid empty membership set."""

        return cls(group_found=True, members=tuple(members))

    @classmethod
    def not_found(cls) -> "ADGroupMembersResult":
        """Build an explicit missing-group result."""

        return cls(
            group_found=False,
            not_found_reason="group_not_found",
            error_code=AD_NOT_FOUND_CODE,
        )


__all__ = [
    "ADGroupMembersResult",
    "ADGroupNotFoundReason",
    "AD_NOT_FOUND_CODE",
]

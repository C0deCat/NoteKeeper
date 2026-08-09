"""Tuple member replacement helper."""

from typing import Protocol, TypeVar

from ...errors import CampaignValidationError

T = TypeVar("T", bound="Identified")


class Identified(Protocol):
    @property
    def id(self) -> object: ...


def replace_member(
    members: tuple[T, ...],
    member_id: object,
    replacement: T,
    label: str,
) -> tuple[T, ...]:
    replaced = False
    updated: list[T] = []
    for member in members:
        if member.id == member_id:
            updated.append(replacement)
            replaced = True
        else:
            updated.append(member)

    if not replaced:
        raise CampaignValidationError(f"{label} is not in the campaign")

    return tuple(updated)

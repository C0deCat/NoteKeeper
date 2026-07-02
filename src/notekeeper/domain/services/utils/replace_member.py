"""Tuple member replacement helper."""

from ...errors import CampaignValidationError


def replace_member(
    members: tuple,
    member_id: object,
    replacement: object,
    label: str,
) -> tuple:
    replaced = False
    updated = []
    for member in members:
        if member.id == member_id:
            updated.append(replacement)
            replaced = True
        else:
            updated.append(member)

    if not replaced:
        raise CampaignValidationError(f"{label} is not in the campaign")

    return tuple(updated)

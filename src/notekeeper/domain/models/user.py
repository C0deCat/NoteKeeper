"""Authenticated application user."""

from dataclasses import dataclass

from ..ids import UserId
from ..validation import non_empty_str


@dataclass(frozen=True, slots=True)
class User:
    id: UserId
    login: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "login", non_empty_str(self.login, "login"))


AuthenticatedUser = User

__all__ = ["AuthenticatedUser", "User"]

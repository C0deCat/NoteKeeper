"""Authentication provider port."""

from typing import Protocol

from notekeeper.domain import AuthenticatedUser, UserId


class AuthProvider(Protocol):
    def authenticate(self, login: str, password: str) -> AuthenticatedUser: ...

    def register(self, login: str, password: str) -> AuthenticatedUser: ...


class CurrentUserProvider(Protocol):
    def require_user_id(self) -> UserId: ...


__all__ = ["AuthProvider", "CurrentUserProvider"]

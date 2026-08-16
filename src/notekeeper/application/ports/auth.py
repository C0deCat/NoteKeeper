"""Authentication provider port."""

from typing import Protocol

from notekeeper.domain import AuthenticatedUser


class AuthProvider(Protocol):
    def authenticate(self, login: str, password: str) -> AuthenticatedUser: ...

    def register(self, login: str, password: str) -> AuthenticatedUser: ...


__all__ = ["AuthProvider"]

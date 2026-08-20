"""Authentication provider port."""

from typing import Protocol

from notekeeper.domain import AuthenticatedUser, UserId


class AuthProvider(Protocol):
    def authenticate(self, login: str, password: str) -> AuthenticatedUser: ...

    def register(self, login: str, password: str) -> AuthenticatedUser: ...

    def find_by_login(self, login: str) -> AuthenticatedUser | None: ...

    def get(self, user_id: UserId) -> AuthenticatedUser | None: ...

    def update_login(
        self, user_id: UserId, current_password: str, new_login: str
    ) -> AuthenticatedUser: ...

    def update_password(
        self, user_id: UserId, current_password: str, new_password: str
    ) -> AuthenticatedUser: ...


__all__ = ["AuthProvider"]

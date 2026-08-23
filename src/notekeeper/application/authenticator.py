"""Stateless authentication service."""

from notekeeper.application.ports import AuthProvider
from notekeeper.domain import AuthenticatedUser, UserId


class Authenticator:
    def __init__(self, provider: AuthProvider, *, enabled: bool) -> None:
        self._provider = provider
        self._enabled = enabled

    @property
    def enabled(self) -> bool:
        return self._enabled

    def authenticate(self, login: str, password: str) -> AuthenticatedUser:
        return self._provider.authenticate(login, password)

    def register(self, login: str, password: str) -> AuthenticatedUser:
        return self._provider.register(login, password)

    def find_by_login(self, login: str) -> AuthenticatedUser | None:
        return self._provider.find_by_login(login)

    def get(self, user_id: UserId) -> AuthenticatedUser | None:
        return self._provider.get(user_id)

    def update_login(
        self, user_id: UserId, current_password: str, new_login: str
    ) -> AuthenticatedUser:
        return self._provider.update_login(user_id, current_password, new_login)

    def update_password(
        self, user_id: UserId, current_password: str, new_password: str
    ) -> AuthenticatedUser:
        return self._provider.update_password(user_id, current_password, new_password)


__all__ = ["Authenticator"]

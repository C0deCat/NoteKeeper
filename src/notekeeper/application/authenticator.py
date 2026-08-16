"""Stateless authentication service."""

from notekeeper.application.ports import AuthProvider
from notekeeper.domain import AuthenticatedUser


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


__all__ = ["Authenticator"]

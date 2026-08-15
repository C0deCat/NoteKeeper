"""Runtime authentication context."""

from notekeeper.domain import (
    BUILTIN_ROOT_USER_ID,
    AuthenticatedUser,
    User,
    UserId,
)

from .errors import AuthenticationRequiredError
from .ports import AuthProvider


class AuthContext:
    def __init__(self, provider: AuthProvider, *, enabled: bool) -> None:
        self._provider = provider
        self._enabled = enabled
        self._current_user: AuthenticatedUser | None = (
            None if enabled else User(BUILTIN_ROOT_USER_ID, "root")
        )

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def current_user(self) -> AuthenticatedUser | None:
        return self._current_user

    def login(self, login: str, password: str) -> AuthenticatedUser:
        user = self._provider.authenticate(login, password)
        self._current_user = user
        return user

    def register(self, login: str, password: str) -> AuthenticatedUser:
        user = self._provider.register(login, password)
        self._current_user = user
        return user

    def logout(self) -> None:
        if self._enabled:
            self._current_user = None

    def require_user(self) -> AuthenticatedUser:
        if self._current_user is None:
            raise AuthenticationRequiredError(
                "authentication required; run notekeeper auth login"
            )
        return self._current_user

    def require_user_id(self) -> UserId:
        return self.require_user().id


__all__ = ["AuthContext"]

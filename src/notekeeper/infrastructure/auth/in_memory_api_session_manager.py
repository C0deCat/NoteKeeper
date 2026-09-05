"""Thread-safe in-memory bearer sessions for the local API profile."""

from __future__ import annotations

import hashlib
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass
from threading import RLock

from notekeeper.application.errors import AuthenticationRequiredError
from notekeeper.domain import AuthenticatedUser


@dataclass(frozen=True, slots=True)
class BearerTokenPair:
    access_token: str
    refresh_token: str
    access_expires_in: int
    refresh_expires_in: int


@dataclass(slots=True)
class _SessionFamily:
    user: AuthenticatedUser
    access_digest: str
    refresh_digest: str
    access_expires_at: float
    refresh_expires_at: float


class InMemoryApiSessionManager:
    """Issue and rotate opaque tokens without retaining plaintext values."""

    def __init__(
        self,
        *,
        access_ttl_seconds: int,
        refresh_ttl_seconds: int,
        clock: Callable[[], float] = time.time,
    ) -> None:
        if access_ttl_seconds <= 0 or refresh_ttl_seconds <= 0:
            raise ValueError("API token TTL values must be positive")
        if refresh_ttl_seconds <= access_ttl_seconds:
            raise ValueError("refresh token TTL must exceed access token TTL")
        self._access_ttl = access_ttl_seconds
        self._refresh_ttl = refresh_ttl_seconds
        self._clock = clock
        self._lock = RLock()
        self._families: dict[str, _SessionFamily] = {}
        self._access_index: dict[str, str] = {}
        self._refresh_index: dict[str, str] = {}

    def issue(self, user: AuthenticatedUser) -> BearerTokenPair:
        with self._lock:
            return self._issue_locked(user)

    def resolve(self, access_token: str) -> AuthenticatedUser:
        digest = self._digest(self._required_token(access_token))
        with self._lock:
            family_id = self._access_index.get(digest)
            family = self._families.get(family_id or "")
            if family is None or family.access_digest != digest:
                raise AuthenticationRequiredError("invalid or expired access token")
            if family.access_expires_at <= self._clock():
                self._remove_family_locked(family_id or "")
                raise AuthenticationRequiredError("invalid or expired access token")
            return family.user

    def refresh(self, refresh_token: str) -> tuple[AuthenticatedUser, BearerTokenPair]:
        digest = self._digest(self._required_token(refresh_token))
        with self._lock:
            family_id = self._refresh_index.get(digest)
            family = self._families.get(family_id or "")
            if family is None or family.refresh_digest != digest:
                raise AuthenticationRequiredError("invalid or expired refresh token")
            if family.refresh_expires_at <= self._clock():
                self._remove_family_locked(family_id or "")
                raise AuthenticationRequiredError("invalid or expired refresh token")
            user = family.user
            self._remove_family_locked(family_id or "")
            return user, self._issue_locked(user)

    def revoke(self, refresh_token: str) -> None:
        digest = self._digest(self._required_token(refresh_token))
        with self._lock:
            family_id = self._refresh_index.get(digest)
            family = self._families.get(family_id or "")
            if family is None or family.refresh_digest != digest:
                raise AuthenticationRequiredError("invalid or expired refresh token")
            self._remove_family_locked(family_id or "")

    def _issue_locked(self, user: AuthenticatedUser) -> BearerTokenPair:
        now = self._clock()
        family_id = secrets.token_urlsafe(24)
        access_token = f"nk_access_{secrets.token_urlsafe(32)}"
        refresh_token = f"nk_refresh_{secrets.token_urlsafe(48)}"
        family = _SessionFamily(
            user=user,
            access_digest=self._digest(access_token),
            refresh_digest=self._digest(refresh_token),
            access_expires_at=now + self._access_ttl,
            refresh_expires_at=now + self._refresh_ttl,
        )
        self._families[family_id] = family
        self._access_index[family.access_digest] = family_id
        self._refresh_index[family.refresh_digest] = family_id
        return BearerTokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
            access_expires_in=self._access_ttl,
            refresh_expires_in=self._refresh_ttl,
        )

    def _remove_family_locked(self, family_id: str) -> None:
        family = self._families.pop(family_id, None)
        if family is None:
            return
        self._access_index.pop(family.access_digest, None)
        self._refresh_index.pop(family.refresh_digest, None)

    @staticmethod
    def _required_token(token: str) -> str:
        normalized = token.strip()
        if not normalized:
            raise AuthenticationRequiredError("authentication token is required")
        return normalized

    @staticmethod
    def _digest(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()


__all__ = ["BearerTokenPair", "InMemoryApiSessionManager"]

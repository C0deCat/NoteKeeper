from notekeeper.application import AuthenticationRequiredError
from notekeeper.domain import User, UserId
from notekeeper.infrastructure.auth import InMemoryApiSessionManager

import pytest


def test_api_session_rotation_revokes_old_tokens_and_logout_revokes_family() -> None:
    now = [1000.0]
    manager = InMemoryApiSessionManager(
        access_ttl_seconds=10,
        refresh_ttl_seconds=100,
        clock=lambda: now[0],
    )
    user = User(UserId("user-1"), "alice")

    first = manager.issue(user)
    assert manager.resolve(first.access_token) == user
    restarted = InMemoryApiSessionManager(
        access_ttl_seconds=10,
        refresh_ttl_seconds=100,
        clock=lambda: now[0],
    )
    with pytest.raises(AuthenticationRequiredError):
        restarted.resolve(first.access_token)

    refreshed_user, second = manager.refresh(first.refresh_token)
    assert refreshed_user == user
    assert second.access_token != first.access_token
    assert second.refresh_token != first.refresh_token
    with pytest.raises(AuthenticationRequiredError):
        manager.resolve(first.access_token)
    with pytest.raises(AuthenticationRequiredError):
        manager.refresh(first.refresh_token)

    manager.revoke(second.refresh_token)
    with pytest.raises(AuthenticationRequiredError):
        manager.resolve(second.access_token)


def test_api_session_expiration_removes_access_and_refresh_tokens() -> None:
    now = [1000.0]
    manager = InMemoryApiSessionManager(
        access_ttl_seconds=10,
        refresh_ttl_seconds=100,
        clock=lambda: now[0],
    )
    user = User(UserId("user-1"), "alice")
    pair = manager.issue(user)

    now[0] = 1010.0
    with pytest.raises(AuthenticationRequiredError):
        manager.resolve(pair.access_token)

    pair = manager.issue(user)
    now[0] = 1110.0
    with pytest.raises(AuthenticationRequiredError):
        manager.refresh(pair.refresh_token)

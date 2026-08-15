from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path

import pytest

from notekeeper.application import (
    InvalidCredentialsError,
    PortExecutionError,
    UserAlreadyExistsError,
)
from notekeeper.domain import BUILTIN_ROOT_USER_ID
from notekeeper.infrastructure.auth import LocalAuthProvider, LocalCliSessionStore


def test_local_auth_provider_seeds_root_on_first_authentication(tmp_path: Path) -> None:
    users_path = tmp_path / "users.json"
    provider = LocalAuthProvider(users_path)

    assert not users_path.exists()
    user = provider.authenticate("root", "root")

    assert user.id == BUILTIN_ROOT_USER_ID
    assert json.loads(users_path.read_text(encoding="utf-8")) == [
        {
            "user_id": str(BUILTIN_ROOT_USER_ID),
            "login": "root",
            "password": "root",
        }
    ]


def test_local_auth_provider_registers_and_authenticates_case_insensitively(
    tmp_path: Path,
) -> None:
    provider = LocalAuthProvider(tmp_path / "users.json")
    registered = provider.register(" Alice ", "secret")

    assert provider.authenticate("alice", "secret") == registered
    with pytest.raises(UserAlreadyExistsError):
        provider.register("ALICE", "another")
    with pytest.raises(InvalidCredentialsError, match="invalid login or password"):
        provider.authenticate("alice", "wrong")


def test_local_auth_provider_rejects_invalid_manual_file(tmp_path: Path) -> None:
    users_path = tmp_path / "users.json"
    users_path.write_text(
        '[{"user_id": "same", "login": "A", "password": "x"},'
        '{"user_id": "same", "login": "B", "password": "y"}]',
        encoding="utf-8",
    )

    with pytest.raises(PortExecutionError, match="duplicate local user_id"):
        LocalAuthProvider(users_path)


def test_local_auth_provider_serializes_concurrent_registrations(tmp_path: Path) -> None:
    users_path = tmp_path / "users.json"

    def register(index: int) -> str:
        return str(LocalAuthProvider(users_path).register(f"user-{index}", "pw").id)

    with ThreadPoolExecutor(max_workers=4) as executor:
        user_ids = tuple(executor.map(register, range(8)))

    assert len(set(user_ids)) == 8
    payload = json.loads(users_path.read_text(encoding="utf-8"))
    assert len(payload) == 9


def test_local_cli_session_store_round_trips_and_clears(tmp_path: Path) -> None:
    store = LocalCliSessionStore(tmp_path / "session.json")

    assert store.load() is None
    store.save("alice", "secret")
    assert store.load() == ("alice", "secret")
    store.clear()
    assert store.load() is None

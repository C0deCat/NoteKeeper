"""Plain-text JSON authentication provider for local use."""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any

from filelock import FileLock

from notekeeper.application.errors import (
    InvalidCredentialsError,
    PortExecutionError,
    UserAlreadyExistsError,
)
from notekeeper.application.ports import AuthProvider
from notekeeper.domain import (
    BUILTIN_ROOT_USER_ID,
    AuthenticatedUser,
    User,
    UserId,
)


class LocalAuthProvider(AuthProvider):
    def __init__(self, users_path: str | Path) -> None:
        self._users_path = Path(users_path)
        self._lock = FileLock(f"{self._users_path}.lock")
        if self._users_path.exists():
            with self._lock:
                self._read_users()

    def authenticate(self, login: str, password: str) -> AuthenticatedUser:
        self._ensure_store()
        normalized_login = self._validated_login(login)
        if not password:
            raise InvalidCredentialsError("invalid login or password")
        with self._lock:
            users = self._read_users()
        login_key = normalized_login.casefold()
        for record in users:
            if record["login"].casefold() == login_key and record["password"] == password:
                return User(UserId(record["user_id"]), record["login"])
        raise InvalidCredentialsError("invalid login or password")

    def register(self, login: str, password: str) -> AuthenticatedUser:
        self._ensure_store()
        normalized_login = self._validated_login(login)
        if not password:
            raise PortExecutionError("password must not be empty")
        with self._lock:
            users = self._read_users()
            login_key = normalized_login.casefold()
            if any(record["login"].casefold() == login_key for record in users):
                raise UserAlreadyExistsError(
                    f"user login {normalized_login!r} is already registered"
                )
            user = User(UserId(str(uuid.uuid4())), normalized_login)
            users.append(
                {
                    "user_id": str(user.id),
                    "login": user.login,
                    "password": password,
                }
            )
            self._write_users(users)
        return user

    def _ensure_store(self) -> None:
        with self._lock:
            if self._users_path.exists():
                self._read_users()
                return
            self._write_users(
                [
                    {
                        "user_id": str(BUILTIN_ROOT_USER_ID),
                        "login": "root",
                        "password": "root",
                    }
                ]
            )

    def _read_users(self) -> list[dict[str, str]]:
        try:
            payload: Any = json.loads(self._users_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise PortExecutionError(
                f"could not read local users file {self._users_path}: {exc}"
            ) from exc
        if not isinstance(payload, list):
            raise PortExecutionError("local users file must contain a JSON list")

        users: list[dict[str, str]] = []
        user_ids: set[str] = set()
        logins: set[str] = set()
        for index, value in enumerate(payload):
            if not isinstance(value, dict):
                raise PortExecutionError(f"local user at index {index} must be an object")
            user_id = value.get("user_id")
            login = value.get("login")
            password = value.get("password")
            if (
                not isinstance(user_id, str)
                or not user_id
                or not isinstance(login, str)
                or not login
                or not isinstance(password, str)
                or not password
            ):
                raise PortExecutionError(
                    f"local user at index {index} requires non-empty user_id, login, and password"
                )
            normalized_login = login.strip()
            if not normalized_login:
                raise PortExecutionError(f"local user at index {index} has an empty login")
            login_key = normalized_login.casefold()
            if user_id in user_ids:
                raise PortExecutionError(f"duplicate local user_id {user_id!r}")
            if login_key in logins:
                raise PortExecutionError(f"duplicate local login {normalized_login!r}")
            user_ids.add(user_id)
            logins.add(login_key)
            users.append(
                {"user_id": user_id, "login": normalized_login, "password": password}
            )
        return users

    def _write_users(self, users: list[dict[str, str]]) -> None:
        self._users_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self._users_path.with_name(f".{self._users_path.name}.tmp")
        try:
            temporary_path.write_text(
                json.dumps(users, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            os.replace(temporary_path, self._users_path)
        except OSError as exc:
            raise PortExecutionError(
                f"could not write local users file {self._users_path}: {exc}"
            ) from exc
        finally:
            if temporary_path.exists():
                temporary_path.unlink()

    @staticmethod
    def _validated_login(login: str) -> str:
        normalized = login.strip()
        if not normalized:
            raise InvalidCredentialsError("invalid login or password")
        return normalized


__all__ = ["LocalAuthProvider"]

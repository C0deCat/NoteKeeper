"""Plain-text persisted credentials for local CLI sessions."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from filelock import FileLock

from notekeeper.application.errors import PortExecutionError


class LocalCliSessionStore:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._lock = FileLock(f"{self._path}.lock")

    def load(self) -> tuple[str, str] | None:
        with self._lock:
            if not self._path.exists():
                return None
            try:
                payload: Any = json.loads(self._path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise PortExecutionError(
                    f"could not read CLI auth session {self._path}: {exc}"
                ) from exc
            if not isinstance(payload, dict):
                raise PortExecutionError("CLI auth session must be a JSON object")
            login = payload.get("login")
            password = payload.get("password")
            if (
                not isinstance(login, str)
                or not login
                or not isinstance(password, str)
                or not password
            ):
                raise PortExecutionError(
                    "CLI auth session requires non-empty login and password"
                )
            return login, password

    def save(self, login: str, password: str) -> None:
        with self._lock:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            temporary_path = self._path.with_name(f".{self._path.name}.tmp")
            try:
                temporary_path.write_text(
                    json.dumps(
                        {"login": login, "password": password},
                        ensure_ascii=False,
                        indent=2,
                    )
                    + "\n",
                    encoding="utf-8",
                )
                os.replace(temporary_path, self._path)
            except OSError as exc:
                raise PortExecutionError(
                    f"could not write CLI auth session {self._path}: {exc}"
                ) from exc
            finally:
                if temporary_path.exists():
                    temporary_path.unlink()

    def clear(self) -> None:
        with self._lock:
            try:
                self._path.unlink(missing_ok=True)
            except OSError as exc:
                raise PortExecutionError(
                    f"could not remove CLI auth session {self._path}: {exc}"
                ) from exc


__all__ = ["LocalCliSessionStore"]

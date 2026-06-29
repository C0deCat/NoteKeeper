"""Internal validation helpers for domain objects."""

import math
from typing import TypeVar

from .errors import DomainValidationError

T = TypeVar("T")


def non_empty_str(value: str, field_name: str) -> str:
    if not isinstance(value, str):
        raise DomainValidationError(f"{field_name} must be a string")

    stripped = value.strip()
    if not stripped:
        raise DomainValidationError(f"{field_name} must be non-empty")

    return stripped


def optional_non_empty_str(value: str | None, field_name: str) -> str | None:
    if value is None:
        return None

    return non_empty_str(value, field_name)


def finite_float(value: float | int, field_name: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise DomainValidationError(f"{field_name} must be finite")

    return number


def positive_float(value: float | int, field_name: str) -> float:
    number = finite_float(value, field_name)
    if number <= 0:
        raise DomainValidationError(f"{field_name} must be positive")

    return number


def non_negative_float(value: float | int, field_name: str) -> float:
    number = finite_float(value, field_name)
    if number < 0:
        raise DomainValidationError(f"{field_name} must be non-negative")

    return number


def optional_positive_int(value: int | None, field_name: str) -> int | None:
    if value is None:
        return None

    if not isinstance(value, int) or value <= 0:
        raise DomainValidationError(f"{field_name} must be a positive integer")

    return value


def optional_non_negative_int(value: int | None, field_name: str) -> int | None:
    if value is None:
        return None

    if not isinstance(value, int) or value < 0:
        raise DomainValidationError(f"{field_name} must be a non-negative integer")

    return value


def as_tuple(value: tuple[T, ...] | list[T], field_name: str) -> tuple[T, ...]:
    if isinstance(value, tuple):
        return value

    if isinstance(value, list):
        return tuple(value)

    raise DomainValidationError(f"{field_name} must be a tuple or list")

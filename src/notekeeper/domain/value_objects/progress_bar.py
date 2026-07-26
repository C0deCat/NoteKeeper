"""Generic immutable progress-bar value object."""

from dataclasses import dataclass, replace

from ..errors import DomainValidationError


@dataclass(frozen=True, slots=True)
class ProgressBar:
    stage: str
    expected_duration: int = 0
    current_duration: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.stage, str):
            raise DomainValidationError("stage must be a string")
        stage = self.stage.strip()
        if not stage:
            raise DomainValidationError("stage must not be empty")
        _validate_duration(self.expected_duration, "expected_duration")
        _validate_duration(self.current_duration, "current_duration")
        object.__setattr__(self, "stage", stage)

    @property
    def percent(self) -> float:
        if self.expected_duration == 0:
            return 0.0
        value = min(self.current_duration / self.expected_duration * 100.0, 100.0)
        return round(value, 1)

    @property
    def remaining_duration(self) -> int:
        return max(self.expected_duration - self.current_duration, 0)

    def update_expected_duration(self, duration: int) -> "ProgressBar":
        return replace(self, expected_duration=duration)

    def update_current_duration(self, duration: int) -> "ProgressBar":
        return replace(self, current_duration=duration)

    def update_stage(self, stage: str) -> "ProgressBar":
        return ProgressBar(stage=stage)


def _validate_duration(value: int, field: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise DomainValidationError(f"{field} must be a non-negative integer")


__all__ = ["ProgressBar"]

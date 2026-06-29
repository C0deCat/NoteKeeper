"""Time range value object."""

from dataclasses import dataclass

from ..errors import DomainValidationError
from ..validation import finite_float, non_negative_float


@dataclass(frozen=True, slots=True)
class TimeRange:
    start_seconds: float
    end_seconds: float

    def __post_init__(self) -> None:
        start_seconds = non_negative_float(self.start_seconds, "start_seconds")
        end_seconds = finite_float(self.end_seconds, "end_seconds")

        if end_seconds < start_seconds:
            raise DomainValidationError(
                "end_seconds must be greater than or equal to start_seconds"
            )

        object.__setattr__(self, "start_seconds", start_seconds)
        object.__setattr__(self, "end_seconds", end_seconds)

    @property
    def duration_seconds(self) -> float:
        return self.end_seconds - self.start_seconds

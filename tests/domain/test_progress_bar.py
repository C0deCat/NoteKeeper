"""Tests for the generic progress value object."""

import pytest

from notekeeper.domain import DomainValidationError, ProgressBar


def test_progress_bar_calculates_bounded_percent_and_remaining() -> None:
    progress = ProgressBar(
        stage="transcribing",
        expected_duration=3000,
        current_duration=2000,
    )

    assert progress.percent == 66.7
    assert progress.remaining_duration == 1000

    exceeded = progress.update_current_duration(4000)
    assert exceeded.percent == 100.0
    assert exceeded.remaining_duration == 0


def test_progress_bar_handles_unknown_expected_duration() -> None:
    progress = ProgressBar(stage="estimating", current_duration=500)

    assert progress.percent == 0.0
    assert progress.remaining_duration == 0


def test_progress_bar_updates_are_immutable_and_stage_resets_timing() -> None:
    original = ProgressBar("first", 1000, 500)
    updated = original.update_expected_duration(2000).update_current_duration(750)
    next_stage = updated.update_stage("second")

    assert original == ProgressBar("first", 1000, 500)
    assert updated == ProgressBar("first", 2000, 750)
    assert next_stage == ProgressBar("second")


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("expected_duration", -1),
        ("current_duration", -1),
        ("expected_duration", True),
        ("current_duration", 1.5),
    ),
)
def test_progress_bar_rejects_invalid_durations(field: str, value: object) -> None:
    arguments = {"stage": "stage", field: value}
    with pytest.raises(DomainValidationError):
        ProgressBar(**arguments)


def test_progress_bar_rejects_empty_or_non_string_stage() -> None:
    with pytest.raises(DomainValidationError):
        ProgressBar(" ")
    with pytest.raises(DomainValidationError):
        ProgressBar(None)  # type: ignore[arg-type]

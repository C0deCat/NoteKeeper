"""Backward-compatible import for the generic local job cleaner."""

from .job_cleaner import LocalJobCleaner

LocalFailedJobCleaner = LocalJobCleaner

__all__ = ["LocalFailedJobCleaner"]

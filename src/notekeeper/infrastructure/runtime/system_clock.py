"""System clock adapter."""

from datetime import datetime, timezone

from notekeeper.application.ports import Clock


class SystemClock(Clock):
    def now(self) -> datetime:
        return datetime.now(timezone.utc)

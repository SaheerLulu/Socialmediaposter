"""Throttling and quiet-hours enforcement shared by tools and the scheduler."""

from __future__ import annotations

import time
from datetime import datetime

from .config import marketing_settings


class SendGovernor:
    """Enforces min spacing, per-day caps, and quiet hours for outreach."""

    def __init__(self) -> None:
        self._last_send_ts: float = 0.0
        self._day: str = ""
        self._sent_today: int = 0

    def _roll_day(self) -> None:
        today = datetime.now().strftime("%Y-%m-%d")
        if today != self._day:
            self._day = today
            self._sent_today = 0

    def in_quiet_hours(self, now: datetime | None = None) -> bool:
        now = now or datetime.now()
        h = now.hour
        start, end = marketing_settings.quiet_start_hour, marketing_settings.quiet_end_hour
        if start == end:
            return False
        if start < end:
            return start <= h < end
        # window wraps midnight (e.g. 21 -> 8)
        return h >= start or h < end

    def can_send(self) -> tuple[bool, str]:
        self._roll_day()
        if self.in_quiet_hours():
            return False, "within quiet hours"
        if self._sent_today >= marketing_settings.max_per_day:
            return False, f"daily cap reached ({marketing_settings.max_per_day})"
        return True, ""

    def wait_for_slot(self) -> None:
        gap = marketing_settings.min_seconds_between_sends
        elapsed = time.time() - self._last_send_ts
        if elapsed < gap:
            time.sleep(gap - elapsed)

    def record(self) -> None:
        self._roll_day()
        self._last_send_ts = time.time()
        self._sent_today += 1

    @property
    def sent_today(self) -> int:
        self._roll_day()
        return self._sent_today


# Process-wide governor shared across tool invocations.
governor = SendGovernor()

"""A parent-only logical deadline clock, with an independent wall-clock guard.

Phase tests must reach their injected boundary before testing its deadline.
Cold spawn scheduling is tested separately with the real monotonic clock.
The worker and socket timeouts always retain the real clock.
"""

import time


class DeadlineClock:
    def __init__(self, total=1.0, wall_limit=10.0):
        self.total = total
        self.wall_limit = wall_limit
        self.started = time.monotonic()
        self.expired_at = None
        self.pending_reads = None
        self.wall_guard_fired = False

    def expire(self):
        if self.expired_at is None:
            self.expired_at = time.monotonic()

    def after_stage_read(self):
        # The supervisor checks the clock once before accepting this stage.
        # Expire at its next check, after the actual worker phase is recorded.
        if self.pending_reads is None and self.expired_at is None:
            self.pending_reads = 1

    def monotonic(self):
        now = time.monotonic()
        if self.expired_at is None and now - self.started >= self.wall_limit:
            self.wall_guard_fired = True
            self.expire()
        if self.pending_reads is not None and self.expired_at is None:
            if self.pending_reads == 0:
                self.expire()
            else:
                self.pending_reads -= 1
        if self.expired_at is None:
            return 100.0
        # Cleanup still measures elapsed wall time; it is never frozen.
        return 100.0 + self.total + time.monotonic() - self.expired_at

"""297 caller-owned transaction; all domain SQL remains in owner adapters."""

from contextlib import contextmanager


class PostgresProblemPlanUnitOfWork:
    def __init__(self, problems, control):
        self.problems = problems
        self.control = control

    @contextmanager
    def transaction(self, connection=None):
        # READ COMMITTED plus owner claim/row locks: equal requests serialize,
        # while all writes and the completed claim share this single commit.
        if connection is not None:
            yield connection
        else:
            with self.problems.pool.connection() as owned, owned.transaction():
                yield owned

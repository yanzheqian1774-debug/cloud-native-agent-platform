"""297 caller-owned transaction; all domain SQL remains in owner adapters."""

from contextlib import contextmanager


class PostgresProblemPlanUnitOfWork:
    def __init__(self, problems, control):
        self.problems = problems
        self.control = control

    @contextmanager
    def transaction(self):
        # READ COMMITTED plus owner claim/row locks: equal requests serialize,
        # while all writes and the completed claim share this single commit.
        with self.problems.pool.connection() as connection, connection.transaction():
            yield connection

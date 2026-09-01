from agent_console.execution_domain import CutoverState, ImportCheckpoint, Writer


def test_restart_checkpoint_preserves_ambiguous_recovery_state() -> None:
    before = ImportCheckpoint(
        CutoverState.RECOVERY_REQUIRED,
        Writer.NONE,
        "sqlite-backup:sha256:stable",
        "a" * 64,
        7,
        "evidence-7",
        7,
        "sqlite-postgres-evidence-v1",
        "RECOVERY_REQUIRED",
    )
    serialized = before
    assert serialized == before
    assert serialized.writer is Writer.NONE
    assert serialized.state is CutoverState.RECOVERY_REQUIRED

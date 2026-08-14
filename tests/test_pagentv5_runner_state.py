import pytest

from pagentv5.runtime import (
    RunnerPhase,
    RunnerState,
    RunnerStateError,
    TranslationContext,
)


def test_runner_state_starts_idle():
    state = RunnerState()
    assert state.phase is RunnerPhase.IDLE
    assert state.busy is False
    assert state.run_id is None
    assert state.stop_reason is None


def test_begin_run_moves_to_running():
    state = RunnerState()
    state.begin_run("run_1")
    assert state.phase is RunnerPhase.RUNNING
    assert state.busy is True
    assert state.run_id == "run_1"


def test_end_run_returns_to_idle_and_records_stop_reason():
    state = RunnerState()
    state.begin_run("run_1")
    state.end_run("completed")
    assert state.phase is RunnerPhase.IDLE
    assert state.busy is False
    assert state.stop_reason == "completed"


def test_runner_state_is_reusable_across_runs():
    state = RunnerState()
    state.begin_run("run_1")
    state.end_run("completed")

    state.begin_run("run_2")
    assert state.run_id == "run_2"
    assert state.turn_index == 0
    assert state.step_index == 0
    assert state.stop_reason is None


def test_cannot_begin_while_running():
    state = RunnerState()
    state.begin_run("run_1")
    with pytest.raises(RunnerStateError, match="cannot begin"):
        state.begin_run("run_2")


def test_cannot_end_while_idle():
    state = RunnerState()
    with pytest.raises(RunnerStateError, match="cannot end"):
        state.end_run("completed")


def test_context_requires_a_run_in_flight():
    state = RunnerState()
    with pytest.raises(RunnerStateError, match="no run is in flight"):
        state.context()


def test_context_reflects_current_run_position():
    state = RunnerState()
    state.begin_run("run_1")
    state.advance_step()
    state.advance_turn()
    state.advance_turn()
    state.advance_step()
    assert state.context() == TranslationContext(
        run_id="run_1", turn_index=2, step_index=1
    )


def test_advancing_turn_resets_step_index():
    state = RunnerState()
    state.begin_run("run_1")
    state.advance_step()
    state.advance_turn()

    assert state.turn_index == 1
    assert state.step_index == 0


def test_cannot_advance_position_while_idle():
    state = RunnerState()

    with pytest.raises(RunnerStateError, match="advance a step"):
        state.advance_step()
    with pytest.raises(RunnerStateError, match="advance a turn"):
        state.advance_turn()

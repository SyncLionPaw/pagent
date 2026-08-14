from dataclasses import dataclass
from enum import Enum

from ..events.runner import RunStopReason
from .event_translation import TranslationContext


class RunnerPhase(Enum):
    IDLE = "idle"
    RUNNING = "running"


class RunnerStateError(RuntimeError):
    """Raised when a runner-state transition is not allowed from the current phase."""


@dataclass
class RunnerState:
    """Single source of truth for a runner's phase and current-run position.

    A runner is long-lived and reusable: it sits ``IDLE`` between runs, switches
    to ``RUNNING`` for the duration of one run, and returns to ``IDLE`` when that
    run ends so the next run can start. The run identifier together with the
    current turn and step index describe the run in flight, and the runner
    derives its :class:`TranslationContext` from here so run position lives in
    exactly one place.
    """

    phase: RunnerPhase = RunnerPhase.IDLE
    run_id: str | None = None
    turn_index: int = 0
    step_index: int = 0
    stop_reason: RunStopReason | None = None

    @property
    def busy(self) -> bool:
        return self.phase is RunnerPhase.RUNNING

    def context(self) -> TranslationContext:
        if self.run_id is None:
            raise RunnerStateError("no run is in flight")
        return TranslationContext(
            run_id=self.run_id,
            turn_index=self.turn_index,
            step_index=self.step_index,
        )

    def begin_run(self, run_id: str) -> None:
        if self.phase is not RunnerPhase.IDLE:
            raise RunnerStateError(
                f"cannot begin a run while runner is {self.phase.value}"
            )
        self.phase = RunnerPhase.RUNNING
        self.run_id = run_id
        self.turn_index = 0
        self.step_index = 0
        self.stop_reason = None

    def advance_step(self) -> None:
        if self.phase is not RunnerPhase.RUNNING:
            raise RunnerStateError(
                f"cannot advance a step while runner is {self.phase.value}"
            )
        self.step_index += 1

    def advance_turn(self) -> None:
        if self.phase is not RunnerPhase.RUNNING:
            raise RunnerStateError(
                f"cannot advance a turn while runner is {self.phase.value}"
            )
        self.turn_index += 1
        self.step_index = 0

    def end_run(self, stop_reason: RunStopReason) -> None:
        if self.phase is not RunnerPhase.RUNNING:
            raise RunnerStateError(
                f"cannot end a run while runner is {self.phase.value}"
            )
        self.phase = RunnerPhase.IDLE
        self.stop_reason = stop_reason

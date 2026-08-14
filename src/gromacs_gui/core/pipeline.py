from __future__ import annotations

from gromacs_gui.core.project import Project
from gromacs_gui.core.step_state import STEP_ORDER, StepState


def is_step_ready(project: Project, step_name: str) -> bool:
    """A step can run once every step before it in STEP_ORDER is DONE."""
    index = STEP_ORDER.index(step_name)
    return all(project.step_record(name).state == StepState.DONE for name in STEP_ORDER[:index])


def next_runnable_step(project: Project) -> str | None:
    """First step that still needs (re-)running and has its dependencies met."""
    runnable_states = (StepState.PENDING, StepState.STALE, StepState.FAILED)
    for name in STEP_ORDER:
        if project.step_record(name).state in runnable_states and is_step_ready(project, name):
            return name
    return None

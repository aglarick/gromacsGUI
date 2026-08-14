from __future__ import annotations

from gromacs_gui.core.pipeline import is_step_ready, next_runnable_step
from gromacs_gui.core.project import Project
from gromacs_gui.core.step_state import STEP_ORDER


def test_first_step_is_always_ready(tmp_path):
    project = Project.create(tmp_path / "proj")

    assert is_step_ready(project, "structure") is True


def test_later_step_not_ready_until_dependencies_done(tmp_path):
    project = Project.create(tmp_path / "proj")

    assert is_step_ready(project, "box") is False

    project.record_step_finished("structure", output_files=[])

    assert is_step_ready(project, "box") is True


def test_next_runnable_step_progresses_through_pipeline(tmp_path):
    project = Project.create(tmp_path / "proj")

    assert next_runnable_step(project) == "structure"

    project.record_step_finished("structure", output_files=[])
    assert next_runnable_step(project) == "box"

    project.record_step_finished("box", output_files=[])
    assert next_runnable_step(project) == "solvate"


def test_next_runnable_step_is_none_when_pipeline_complete(tmp_path):
    project = Project.create(tmp_path / "proj")
    for step_name in STEP_ORDER:
        project.record_step_finished(step_name, output_files=[])

    assert next_runnable_step(project) is None

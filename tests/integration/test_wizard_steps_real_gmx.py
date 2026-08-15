from __future__ import annotations

from pathlib import Path

import pytest

from gromacs_gui.core.project import Project
from gromacs_gui.core.step_state import StepState
from gromacs_gui.ui.wizard.steps.step_box import StepBoxWidget
from gromacs_gui.ui.wizard.steps.step_ions import StepIonsWidget
from gromacs_gui.ui.wizard.steps.step_solvate import StepSolvateWidget
from gromacs_gui.ui.wizard.steps.step_structure import StepStructureWidget
from gromacs_gui.utils.settings import with_gmx_defaults

pytestmark = pytest.mark.requires_gmx

FIXTURE_PDB = Path(__file__).parent.parent / "fixtures" / "1aki.pdb"


def _wait_for_step_done(qtbot, project, step_name, timeout=60000):
    qtbot.waitUntil(
        lambda: project.step_record(step_name).state in (StepState.DONE, StepState.FAILED),
        timeout=timeout,
    )
    record = project.step_record(step_name)
    assert record.state == StepState.DONE, record.error_message


def test_full_wizard_ui_pipeline_structure_through_ions(qtbot, tmp_path, gmx_environment):
    """Drives the real wizard step widgets (not just the command builders) the
    same way a user clicking 'Run' would, end to end against a real gmx build.
    """
    env = with_gmx_defaults(gmx_environment)
    project = Project.create(tmp_path / "myproj")

    structure_widget = StepStructureWidget(project, env)
    qtbot.addWidget(structure_widget)
    structure_widget._set_structure_path(FIXTURE_PDB)
    assert structure_widget.force_field_combo.count() > 0, "no force fields discovered"
    ff_index = structure_widget.force_field_combo.findData("amber99sb-ildn")
    assert ff_index >= 0
    structure_widget.force_field_combo.setCurrentIndex(ff_index)
    water_index = structure_widget.water_model_combo.findData("tip3p")
    assert water_index >= 0
    structure_widget.water_model_combo.setCurrentIndex(water_index)

    structure_widget._on_run_clicked()
    _wait_for_step_done(qtbot, project, "structure")

    box_widget = StepBoxWidget(project, env)
    qtbot.addWidget(box_widget)
    assert box_widget.is_valid()
    box_widget._on_run_clicked()
    _wait_for_step_done(qtbot, project, "box")

    solvate_widget = StepSolvateWidget(project, env)
    qtbot.addWidget(solvate_widget)
    assert solvate_widget.is_valid()
    solvate_widget._on_run_clicked()
    _wait_for_step_done(qtbot, project, "solvate")

    ions_widget = StepIonsWidget(project, env)
    qtbot.addWidget(ions_widget)
    assert ions_widget.is_valid()
    ions_widget._on_run_clicked()
    _wait_for_step_done(qtbot, project, "ions")

    assert (project.step_dir("ions") / "ionized.gro").is_file()

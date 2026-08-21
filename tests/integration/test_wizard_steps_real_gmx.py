from __future__ import annotations

from pathlib import Path

import pytest

from gromacs_gui.core.project import Project
from gromacs_gui.core.step_state import StepState
from gromacs_gui.ui.wizard.steps.step_cleanup import CleanupToolWidget
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


def test_wizard_ui_pipeline_cleanup_through_structure(
    qtbot, tmp_path, gmx_environment, monkeypatch
):
    """Drives the real wizard step widgets (not just the command builders)
    the same way a user clicking 'Test system' would, against a real gmx
    build - including the real grompp consistency check Structure now runs
    on finish. The post-check dialogs are monkeypatched out (not just their
    QMessageBox.exec(), the whole prompt methods) purely because a real
    modal would block this unattended test forever waiting for a click;
    grompp itself still runs for real.
    """
    monkeypatch.setattr(StepStructureWidget, "_prompt_accept_system", lambda self: False)
    monkeypatch.setattr(StepStructureWidget, "_prompt_inconsistent_system", lambda self: None)
    env = with_gmx_defaults(gmx_environment)
    project = Project.create(tmp_path / "myproj")

    # Step 1 no longer strips crystal waters itself; the standalone cleanup
    # tool (Step 0) does that now, ahead of the pipeline.
    cleanup_widget = CleanupToolWidget(project, env)
    qtbot.addWidget(cleanup_widget)
    cleanup_widget._set_input_path(FIXTURE_PDB)
    assert cleanup_widget._residue_checkboxes["HOH"].isChecked() is False  # not kept by default
    cleaned_pdb = project.root / "cleanup" / "1aki_cleaned.pdb"
    cleanup_widget._save_to(cleaned_pdb)
    assert cleaned_pdb.is_file()

    structure_widget = StepStructureWidget(project, env)
    qtbot.addWidget(structure_widget)
    assert structure_widget.force_field_combo.count() > 0, "no force fields discovered"
    ff_index = structure_widget.force_field_combo.findData("amber99sb-ildn")
    assert ff_index >= 0
    structure_widget.force_field_combo.setCurrentIndex(ff_index)
    water_index = structure_widget.water_model_combo.findData("tip3p")
    assert water_index >= 0
    structure_widget.water_model_combo.setCurrentIndex(water_index)

    row = structure_widget._rows[0]
    row.structure_path = cleaned_pdb
    assert structure_widget.is_valid()

    structure_widget._on_run_clicked()
    _wait_for_step_done(qtbot, project, "structure")

    mol_gro = project.step_dir("structure") / "mol_0.gro"
    assert mol_gro.is_file()
    combined_top = project.root / "topology" / "topol.top"
    top_text = combined_top.read_text()
    assert '#include "amber99sb-ildn.ff/forcefield.itp"' in top_text
    assert '#include "amber99sb-ildn.ff/tip3p.itp"' in top_text
    assert "[ moleculetype ]" in top_text
    assert "[ molecules ]" in top_text
    assert (project.root / "topology" / "posre_mol0.itp").is_file()

    combined_gro = project.step_dir("structure") / "processed.gro"
    assert combined_gro.is_file()  # written by the grompp consistency check

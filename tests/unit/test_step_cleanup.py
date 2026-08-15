from __future__ import annotations

from gromacs_gui.core.project import Project
from gromacs_gui.ui.wizard.steps.step_cleanup import CleanupToolWidget

PDB_WITH_HETATM = (
    "ATOM      1  CA  ALA A   1      0.000   0.000   0.000\n"
    "HETATM    2  O   HOH A 200      1.000   1.000   1.000\n"
    "HETATM    3  C1  LIG A 201      2.000   2.000   2.000\n"
)


def test_pdb_input_defaults_hetatm_checked_and_atom_unchecked(qtbot, tmp_path):
    project = Project.create(tmp_path / "proj")
    widget = CleanupToolWidget(project, {})
    qtbot.addWidget(widget)
    pdb = tmp_path / "in.pdb"
    pdb.write_text(PDB_WITH_HETATM)

    widget._set_input_path(pdb)

    assert set(widget._residue_checkboxes) == {"ALA", "HOH", "LIG"}
    assert widget._residue_checkboxes["ALA"].isChecked() is False
    assert widget._residue_checkboxes["HOH"].isChecked() is True
    assert widget._residue_checkboxes["LIG"].isChecked() is True


def test_gro_input_defaults_nothing_checked(qtbot, tmp_path):
    project = Project.create(tmp_path / "proj")
    widget = CleanupToolWidget(project, {})
    qtbot.addWidget(widget)
    gro = tmp_path / "in.gro"
    gro.write_text(
        "Test system\n"
        "    2\n"
        "    1ALA      CA    1   0.000   0.000   0.000\n"
        "  200HOH       O    2   1.000   1.000   1.000\n"
        "   3.00000   3.00000   3.00000\n"
    )

    widget._set_input_path(gro)

    assert set(widget._residue_checkboxes) == {"ALA", "HOH"}
    assert all(not cb.isChecked() for cb in widget._residue_checkboxes.values())


def test_save_writes_cleaned_copy_into_project_cleanup_folder(qtbot, tmp_path):
    project = Project.create(tmp_path / "proj")
    widget = CleanupToolWidget(project, {})
    qtbot.addWidget(widget)
    pdb = tmp_path / "system.pdb"
    pdb.write_text(PDB_WITH_HETATM)
    widget._set_input_path(pdb)

    # Both HETATM residues (HOH, LIG) are checked by default; explicitly keep
    # LIG to confirm unchecking a default preserves it in the output.
    widget._residue_checkboxes["LIG"].setChecked(False)
    widget._on_save_clicked()

    output = project.root / "cleanup" / "system_cleaned.pdb"
    assert output.is_file()
    text = output.read_text()
    assert "ALA" in text
    assert "LIG" in text
    assert "HOH" not in text
    assert "Guardado en" in widget._status_label.text()


def test_save_with_nothing_selected_just_copies_the_file(qtbot, tmp_path):
    project = Project.create(tmp_path / "proj")
    widget = CleanupToolWidget(project, {})
    qtbot.addWidget(widget)
    gro = tmp_path / "system.gro"
    gro.write_text(
        "Test system\n    1\n    1ALA      CA    1   0.000   0.000   0.000\n   1.0   1.0   1.0\n"
    )
    widget._set_input_path(gro)

    widget._on_save_clicked()

    output = project.root / "cleanup" / "system_cleaned.gro"
    assert output.read_text() == gro.read_text()


def test_does_not_gate_or_record_project_step_state(qtbot, tmp_path):
    project = Project.create(tmp_path / "proj")
    widget = CleanupToolWidget(project, {})
    qtbot.addWidget(widget)
    pdb = tmp_path / "system.pdb"
    pdb.write_text(PDB_WITH_HETATM)
    widget._set_input_path(pdb)

    widget._on_save_clicked()

    from gromacs_gui.core.step_state import STEP_ORDER, StepState

    for step_name in STEP_ORDER:
        assert project.step_record(step_name).state == StepState.PENDING

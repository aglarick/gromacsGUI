from __future__ import annotations

from gromacs_gui.core.project import Project
from gromacs_gui.ui.wizard.steps.step_cleanup import CleanupToolWidget

PDB_WITH_HETATM = (
    "ATOM      1  CA  ALA A   1      0.000   0.000   0.000\n"
    "HETATM    2  O   HOH A 200      1.000   1.000   1.000\n"
    "HETATM    3  C1  LIG A 201      2.000   2.000   2.000\n"
)

PDB_WITH_REPEATED_HOH = (
    "ATOM      1  CA  ALA A   1      0.000   0.000   0.000\n"
    "HETATM    2  O   HOH A 200      1.000   1.000   1.000\n"
    "HETATM    3  O   HOH A 201      2.000   2.000   2.000\n"
)

GRO_WITH_REPEATED_HOH = (
    "Test system\n"
    "    3\n"
    "    1ALA      CA    1   0.000   0.000   0.000\n"
    "  200HOH       O    2   1.000   1.000   1.000\n"
    "  201HOH       O    3   2.000   2.000   2.000\n"
    "   3.00000   3.00000   3.00000\n"
)


def test_pdb_input_defaults_atom_kept_and_hetatm_not_kept(qtbot, tmp_path):
    project = Project.create(tmp_path / "proj")
    widget = CleanupToolWidget(project, {})
    qtbot.addWidget(widget)
    pdb = tmp_path / "in.pdb"
    pdb.write_text(PDB_WITH_HETATM)

    widget._set_input_path(pdb)

    assert set(widget._residue_checkboxes) == {"ALA", "HOH", "LIG"}
    assert widget._residue_checkboxes["ALA"].isChecked() is True
    assert widget._residue_checkboxes["HOH"].isChecked() is False
    assert widget._residue_checkboxes["LIG"].isChecked() is False


def test_hetatm_residues_are_flagged_in_the_checklist_label(qtbot, tmp_path):
    project = Project.create(tmp_path / "proj")
    widget = CleanupToolWidget(project, {})
    qtbot.addWidget(widget)
    pdb = tmp_path / "in.pdb"
    pdb.write_text(PDB_WITH_HETATM)

    widget._set_input_path(pdb)

    assert "[HETATM]" in widget._residue_checkboxes["HOH"].text()
    assert "[HETATM]" in widget._residue_checkboxes["LIG"].text()
    assert "[HETATM]" not in widget._residue_checkboxes["ALA"].text()


def test_hetatm_hint_shown_only_when_hetatm_detected(qtbot, tmp_path):
    project = Project.create(tmp_path / "proj")
    widget = CleanupToolWidget(project, {})
    qtbot.addWidget(widget)

    pdb = tmp_path / "in.pdb"
    pdb.write_text(PDB_WITH_HETATM)
    widget._set_input_path(pdb)
    assert widget._hetatm_hint_label.isHidden() is False
    assert "HOH" in widget._hetatm_hint_label.text()

    plain_pdb = tmp_path / "plain.pdb"
    plain_pdb.write_text("ATOM      1  CA  ALA A   1      0.000   0.000   0.000\n")
    widget._set_input_path(plain_pdb)
    assert widget._hetatm_hint_label.isHidden() is True


def test_gro_input_defaults_everything_kept(qtbot, tmp_path):
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
    assert all(cb.isChecked() for cb in widget._residue_checkboxes.values())
    assert widget._hetatm_hint_label.isHidden() is True


def test_select_all_and_select_none_buttons(qtbot, tmp_path):
    project = Project.create(tmp_path / "proj")
    widget = CleanupToolWidget(project, {})
    qtbot.addWidget(widget)
    pdb = tmp_path / "in.pdb"
    pdb.write_text(PDB_WITH_HETATM)
    widget._set_input_path(pdb)

    widget._set_all_checked(False)
    assert all(not cb.isChecked() for cb in widget._residue_checkboxes.values())

    widget._set_all_checked(True)
    assert all(cb.isChecked() for cb in widget._residue_checkboxes.values())


def test_extract_mode_button_label_toggles(qtbot, tmp_path):
    project = Project.create(tmp_path / "proj")
    widget = CleanupToolWidget(project, {})
    qtbot.addWidget(widget)

    assert widget._extract_mode_button.text() == "Extract all molecules"
    widget._extract_mode_button.setChecked(True)
    assert widget._extract_mode_button.text() == "Extract one molecule"
    widget._extract_mode_button.setChecked(False)
    assert widget._extract_mode_button.text() == "Extract all molecules"


def test_save_keeps_only_checked_residues(qtbot, tmp_path):
    project = Project.create(tmp_path / "proj")
    widget = CleanupToolWidget(project, {})
    qtbot.addWidget(widget)
    pdb = tmp_path / "system.pdb"
    pdb.write_text(PDB_WITH_HETATM)
    widget._set_input_path(pdb)

    # ALA is kept by default; explicitly check LIG too, leave HOH unchecked.
    widget._residue_checkboxes["LIG"].setChecked(True)
    output = project.root / "cleanup" / "system_cleaned.pdb"
    widget._save_to(output)

    assert output.is_file()
    text = output.read_text()
    assert "ALA" in text
    assert "LIG" in text
    assert "HOH" not in text
    assert "Guardado en" in widget._status_label.text()


def test_extract_all_molecules_mode_keeps_every_instance(qtbot, tmp_path):
    project = Project.create(tmp_path / "proj")
    widget = CleanupToolWidget(project, {})
    qtbot.addWidget(widget)
    pdb = tmp_path / "system.pdb"
    pdb.write_text(PDB_WITH_REPEATED_HOH)
    widget._set_input_path(pdb)

    widget._residue_checkboxes["HOH"].setChecked(True)
    output = project.root / "cleanup" / "system_cleaned.pdb"
    widget._save_to(output)

    text = output.read_text()
    assert text.count("HOH") == 2


def test_extract_one_molecule_mode_keeps_only_the_first_instance_pdb(qtbot, tmp_path):
    project = Project.create(tmp_path / "proj")
    widget = CleanupToolWidget(project, {})
    qtbot.addWidget(widget)
    pdb = tmp_path / "system.pdb"
    pdb.write_text(PDB_WITH_REPEATED_HOH)
    widget._set_input_path(pdb)

    widget._set_all_checked(False)
    widget._residue_checkboxes["HOH"].setChecked(True)
    widget._extract_mode_button.setChecked(True)
    output = project.root / "cleanup" / "one_hoh.pdb"
    widget._save_to(output)

    text = output.read_text()
    assert text.count("HOH") == 1
    assert "ALA" not in text


def test_extract_one_molecule_mode_keeps_only_the_first_instance_gro(qtbot, tmp_path):
    project = Project.create(tmp_path / "proj")
    widget = CleanupToolWidget(project, {})
    qtbot.addWidget(widget)
    gro = tmp_path / "system.gro"
    gro.write_text(GRO_WITH_REPEATED_HOH)
    widget._set_input_path(gro)

    widget._set_all_checked(False)
    widget._residue_checkboxes["HOH"].setChecked(True)
    widget._extract_mode_button.setChecked(True)
    output = project.root / "cleanup" / "one_hoh.gro"
    widget._save_to(output)

    lines = output.read_text().splitlines()
    assert lines[1].strip() == "1"
    assert lines[-1].strip() == "3.00000   3.00000   3.00000"


def test_save_can_extract_a_single_molecule(qtbot, tmp_path):
    """The advertised use case: deselect everything, keep only the one
    molecule of interest, save — used later to feed the Structure step.
    """
    project = Project.create(tmp_path / "proj")
    widget = CleanupToolWidget(project, {})
    qtbot.addWidget(widget)
    pdb = tmp_path / "system.pdb"
    pdb.write_text(PDB_WITH_HETATM)
    widget._set_input_path(pdb)

    widget._set_all_checked(False)
    widget._residue_checkboxes["LIG"].setChecked(True)
    output = project.root / "cleanup" / "system_cleaned.pdb"
    widget._save_to(output)

    text = output.read_text()
    assert "LIG" in text
    assert "ALA" not in text
    assert "HOH" not in text


def test_save_with_default_selection_just_copies_the_file(qtbot, tmp_path):
    project = Project.create(tmp_path / "proj")
    widget = CleanupToolWidget(project, {})
    qtbot.addWidget(widget)
    gro = tmp_path / "system.gro"
    gro.write_text(
        "Test system\n    1\n    1ALA      CA    1   0.000   0.000   0.000\n   1.0   1.0   1.0\n"
    )
    widget._set_input_path(gro)

    output = project.root / "cleanup" / "system_cleaned.gro"
    widget._save_to(output)

    assert output.read_text() == gro.read_text()


def test_save_with_nothing_checked_refuses_to_write(qtbot, tmp_path):
    project = Project.create(tmp_path / "proj")
    widget = CleanupToolWidget(project, {})
    qtbot.addWidget(widget)
    pdb = tmp_path / "system.pdb"
    pdb.write_text(PDB_WITH_HETATM)
    widget._set_input_path(pdb)
    widget._set_all_checked(False)

    output = project.root / "cleanup" / "system_cleaned.pdb"
    widget._save_to(output)

    assert not output.exists()
    assert "Selecciona al menos" in widget._status_label.text()


def test_does_not_gate_or_record_project_step_state(qtbot, tmp_path):
    project = Project.create(tmp_path / "proj")
    widget = CleanupToolWidget(project, {})
    qtbot.addWidget(widget)
    pdb = tmp_path / "system.pdb"
    pdb.write_text(PDB_WITH_HETATM)
    widget._set_input_path(pdb)

    widget._save_to(project.root / "cleanup" / "system_cleaned.pdb")

    from gromacs_gui.core.step_state import STEP_ORDER, StepState

    for step_name in STEP_ORDER:
        assert project.step_record(step_name).state == StepState.PENDING

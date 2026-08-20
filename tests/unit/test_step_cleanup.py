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

# Two separate, well-isolated single-atom "SOL" molecules, plus a POL
# "polymer" split across two residues that share a name (mirrors a real
# P3HT chain: every monomer is its own same-named residue) and are close
# enough (1.5 A) to be guessed as bonded - the whole point of fragment-based
# "extract one molecule" is that this counts as ONE molecule, not two.
PDB_WITH_BONDED_POLYMER = (
    "ATOM      1  O   SOL A   1       0.000   0.000   0.000  1.00  0.00\n"
    "ATOM      2  O   SOL A   2      20.000  20.000  20.000  1.00  0.00\n"
    "ATOM      3  C1  POL A   3      50.000   0.000   0.000  1.00  0.00\n"
    "ATOM      4  C2  POL A   3      51.500   0.000   0.000  1.00  0.00\n"
    "ATOM      5  C1  POL A   4      53.000   0.000   0.000  1.00  0.00\n"
    "ATOM      6  C2  POL A   4      54.500   0.000   0.000  1.00  0.00\n"
)


class _FakeViewer:
    """Stand-in for MoleculeViewer3D that records what the widget asked it
    to render, without touching matplotlib/Qt canvases.
    """

    def __init__(self) -> None:
        self.last_atoms: list | None = None
        self.last_message: str | None = None

    def set_atoms(self, atoms: list) -> None:
        self.last_atoms = atoms
        self.last_message = None

    def show_message(self, text: str) -> None:
        self.last_message = text
        self.last_atoms = None


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
    assert "Saved to" in widget._status_label.text()


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


def test_extract_one_molecule_mode_picks_one_of_several_separate_instances(qtbot, tmp_path):
    project = Project.create(tmp_path / "proj")
    widget = CleanupToolWidget(project, {})
    qtbot.addWidget(widget)
    pdb = tmp_path / "system.pdb"
    pdb.write_text(PDB_WITH_BONDED_POLYMER)
    widget._set_input_path(pdb)

    widget._set_all_checked(False)
    widget._residue_checkboxes["SOL"].setChecked(True)
    widget._extract_mode_button.setChecked(True)
    output = project.root / "cleanup" / "one_sol.pdb"
    widget._save_to(output)

    text = output.read_text()
    assert text.count("SOL") == 1  # only one of the two separate SOL atoms
    assert "POL" not in text


def test_extract_one_molecule_mode_keeps_the_whole_connected_molecule(qtbot, tmp_path):
    """Regression test for the real bug: a molecule split across several
    same-named residues (e.g. every P3HT monomer is its own "P3HT" residue)
    must be extracted whole, not just its first residue.
    """
    project = Project.create(tmp_path / "proj")
    widget = CleanupToolWidget(project, {})
    qtbot.addWidget(widget)
    pdb = tmp_path / "system.pdb"
    pdb.write_text(PDB_WITH_BONDED_POLYMER)
    widget._set_input_path(pdb)

    widget._set_all_checked(False)
    widget._residue_checkboxes["POL"].setChecked(True)
    widget._extract_mode_button.setChecked(True)
    output = project.root / "cleanup" / "whole_polymer.pdb"
    widget._save_to(output)

    text = output.read_text()
    assert text.count("POL") == 4  # both residues, all 4 atoms
    assert "SOL" not in text


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
    assert "Select at least" in widget._status_label.text()


def test_preview_reflects_default_selection_on_load(qtbot, tmp_path):
    project = Project.create(tmp_path / "proj")
    widget = CleanupToolWidget(project, {})
    qtbot.addWidget(widget)
    fake_viewer = _FakeViewer()
    widget._viewer = fake_viewer

    pdb = tmp_path / "system.pdb"
    pdb.write_text(PDB_WITH_HETATM)
    widget._set_input_path(pdb)

    assert fake_viewer.last_atoms is not None
    assert {a.residue_name for a in fake_viewer.last_atoms} == {"ALA"}


def test_preview_updates_when_checkbox_toggled(qtbot, tmp_path):
    project = Project.create(tmp_path / "proj")
    widget = CleanupToolWidget(project, {})
    qtbot.addWidget(widget)
    fake_viewer = _FakeViewer()
    widget._viewer = fake_viewer

    pdb = tmp_path / "system.pdb"
    pdb.write_text(PDB_WITH_HETATM)
    widget._set_input_path(pdb)

    widget._residue_checkboxes["LIG"].setChecked(True)
    assert {a.residue_name for a in fake_viewer.last_atoms} == {"ALA", "LIG"}


def test_preview_reflects_extract_one_molecule_mode(qtbot, tmp_path):
    """The preview must match what saving would produce: the whole
    connected POL molecule (4 atoms across 2 residues), not just one atom
    or one residue.
    """
    project = Project.create(tmp_path / "proj")
    widget = CleanupToolWidget(project, {})
    qtbot.addWidget(widget)
    fake_viewer = _FakeViewer()
    widget._viewer = fake_viewer

    pdb = tmp_path / "system.pdb"
    pdb.write_text(PDB_WITH_BONDED_POLYMER)
    widget._set_input_path(pdb)
    widget._set_all_checked(False)
    widget._residue_checkboxes["POL"].setChecked(True)

    widget._extract_mode_button.setChecked(True)

    assert len(fake_viewer.last_atoms) == 4
    assert {a.residue_name for a in fake_viewer.last_atoms} == {"POL"}


def test_preview_shows_nothing_when_selection_is_empty(qtbot, tmp_path):
    project = Project.create(tmp_path / "proj")
    widget = CleanupToolWidget(project, {})
    qtbot.addWidget(widget)
    fake_viewer = _FakeViewer()
    widget._viewer = fake_viewer

    pdb = tmp_path / "system.pdb"
    pdb.write_text(PDB_WITH_HETATM)
    widget._set_input_path(pdb)
    widget._set_all_checked(False)

    assert fake_viewer.last_atoms == []


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


def test_works_without_a_project(qtbot, tmp_path):
    """The tool is usable before a project folder exists at all (e.g. on
    the app's startup screen) - defaults the save location to the input
    file's own folder instead of a project's cleanup/ dir.
    """
    widget = CleanupToolWidget(None, {})
    qtbot.addWidget(widget)
    pdb = tmp_path / "system.pdb"
    pdb.write_text(PDB_WITH_HETATM)
    widget._set_input_path(pdb)

    output = tmp_path / "system_cleaned.pdb"
    widget._save_to(output)

    assert output.is_file()
    assert "Saved to" in widget._status_label.text()

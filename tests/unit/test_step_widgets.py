from __future__ import annotations

from pathlib import Path

from gromacs_gui.core.project import Project
from gromacs_gui.ui.wizard.steps.step_box import StepBoxWidget
from gromacs_gui.ui.wizard.steps.step_ions import StepIonsWidget
from gromacs_gui.ui.wizard.steps.step_solvate import StepSolvateWidget
from gromacs_gui.ui.wizard.steps.step_structure import StepStructureWidget


def _fake_gmx_env(tmp_path: Path) -> dict[str, str]:
    top_dir = tmp_path / "gmxdata" / "top"
    ff_dir = top_dir / "myff.ff"
    ff_dir.mkdir(parents=True)
    (ff_dir / "forcefield.doc").write_text("My Force Field\n")
    (ff_dir / "watermodels.dat").write_text("tip3p TIP3P TIP 3-point\n")
    return {"GMXDATA": str(top_dir.parent)}


def test_step_structure_invalid_without_a_file_selected(qtbot, tmp_path):
    project = Project.create(tmp_path / "proj")
    widget = StepStructureWidget(project, _fake_gmx_env(tmp_path))
    qtbot.addWidget(widget)

    assert widget.force_field_combo.count() == 1
    assert widget.water_model_combo.count() == 1
    assert widget.is_valid() is False


def test_step_structure_valid_once_file_and_ff_selected(qtbot, tmp_path):
    project = Project.create(tmp_path / "proj")
    widget = StepStructureWidget(project, _fake_gmx_env(tmp_path))
    qtbot.addWidget(widget)
    pdb = tmp_path / "in.pdb"
    pdb.write_text("ATOM      1  CA  ALA A   1      0.000   0.000   0.000\n")
    widget._set_structure_path(pdb)

    assert widget.is_valid() is True
    commands = widget.build_commands()
    assert len(commands) == 1
    assert commands[0].args[0] == "pdb2gmx"


def test_step_structure_hetatm_checklist_defaults_to_all_checked(qtbot, tmp_path):
    project = Project.create(tmp_path / "proj")
    widget = StepStructureWidget(project, _fake_gmx_env(tmp_path))
    qtbot.addWidget(widget)
    pdb = tmp_path / "in.pdb"
    pdb.write_text(
        "ATOM      1  CA  ALA A   1      0.000   0.000   0.000\n"
        "HETATM    2  O   HOH A 200      1.000   1.000   1.000\n"
        "HETATM    3  C1  LIG A 201      2.000   2.000   2.000\n"
    )

    widget._set_structure_path(pdb)

    assert not widget._cleanup_group.isHidden()
    assert set(widget._residue_checkboxes) == {"HOH", "LIG"}
    assert all(cb.isChecked() for cb in widget._residue_checkboxes.values())

    # unchecking LIG means it's kept in the cleaned file build_commands() writes
    widget._residue_checkboxes["LIG"].setChecked(False)
    widget.force_field_combo.setCurrentIndex(0)
    widget.build_commands()

    cleaned_text = (project.step_dir("structure") / "cleaned.pdb").read_text()
    assert "LIG" in cleaned_text
    assert "HOH" not in cleaned_text


def test_step_structure_gro_input_has_no_cleanup_section(qtbot, tmp_path):
    project = Project.create(tmp_path / "proj")
    widget = StepStructureWidget(project, _fake_gmx_env(tmp_path))
    qtbot.addWidget(widget)
    gro = tmp_path / "in.gro"
    gro.write_text("fake gro\n")

    widget._set_structure_path(gro)

    assert widget._cleanup_group.isHidden()
    assert widget._residue_checkboxes == {}


def test_step_structure_bring_own_topology_stages_files_without_gmx(qtbot, tmp_path):
    project = Project.create(tmp_path / "proj")
    widget = StepStructureWidget(project, _fake_gmx_env(tmp_path))
    qtbot.addWidget(widget)

    coords = tmp_path / "ligand.gro"
    coords.write_text("fake gro\n")
    topology = tmp_path / "ligand.top"
    topology.write_text("fake top\n")

    widget._bring_own_radio.setChecked(True)
    assert widget.is_valid() is False  # no files picked yet

    widget._own_coords_path = coords
    widget._own_topology_path = topology

    assert widget.is_valid() is True
    commands = widget.build_commands()

    assert commands == []
    assert (project.step_dir("structure") / "processed.gro").read_text() == "fake gro\n"
    assert (project.root / "topology" / "topol.top").read_text() == "fake top\n"
    assert widget.output_files() == [
        "00_structure/processed.gro",
        "topology/topol.top",
    ]


def test_step_structure_bring_own_itp_gets_wrapped_into_a_top(qtbot, tmp_path):
    project = Project.create(tmp_path / "proj")
    widget = StepStructureWidget(project, _fake_gmx_env(tmp_path))
    qtbot.addWidget(widget)

    coords = tmp_path / "ligand.gro"
    coords.write_text("fake gro\n")
    itp = tmp_path / "ligand.itp"
    itp.write_text("[ moleculetype ]\nLIG   3\n")

    widget._bring_own_radio.setChecked(True)
    widget._own_coords_path = coords
    widget._own_topology_path = itp

    # The force field combo defaults to its first entry, so this is already
    # valid; explicitly confirming the selection made below is used.
    assert widget.is_valid() is True
    widget._own_topology_ff_combo.setCurrentIndex(0)

    commands = widget.build_commands()

    assert commands == []
    top_text = (project.root / "topology" / "topol.top").read_text()
    assert '#include "myff.ff/forcefield.itp"' in top_text
    assert '#include "ligand.itp"' in top_text
    assert "LIG" in top_text
    assert (project.root / "topology" / "ligand.itp").is_file()


def test_step_structure_bring_own_itp_with_custom_ff_folder(qtbot, tmp_path):
    project = Project.create(tmp_path / "proj")
    widget = StepStructureWidget(project, _fake_gmx_env(tmp_path))
    qtbot.addWidget(widget)

    coords = tmp_path / "ligand.gro"
    coords.write_text("fake gro\n")
    itp = tmp_path / "ligand.itp"
    itp.write_text("[ moleculetype ]\nLIG   3\n")

    # A custom force field folder, like the one LigParGen/ATB might produce,
    # not one of the GROMACS-bundled ones from _fake_gmx_env.
    custom_ff = tmp_path / "oplsaam.ff"
    custom_ff.mkdir()
    (custom_ff / "forcefield.itp").write_text("[ defaults ]\n1 3 yes 0.5 0.5\n")
    (custom_ff / "ffnonbonded.itp").write_text("; custom params\n")

    widget._bring_own_radio.setChecked(True)
    widget._own_coords_path = coords
    widget._own_topology_path = itp

    custom_index = widget._own_topology_ff_combo.findData("__custom_ff__")
    assert custom_index >= 0
    widget._own_topology_ff_combo.setCurrentIndex(custom_index)
    assert widget.is_valid() is False  # no folder picked yet

    widget._own_custom_ff_path = custom_ff
    assert widget.is_valid() is True

    commands = widget.build_commands()

    assert commands == []
    top_text = (project.root / "topology" / "topol.top").read_text()
    assert '#include "oplsaam.ff/forcefield.itp"' in top_text
    assert (project.root / "topology" / "oplsaam.ff" / "forcefield.itp").is_file()
    assert (project.root / "topology" / "oplsaam.ff" / "ffnonbonded.itp").is_file()


def test_step_structure_server_mode_disables_run_and_is_invalid(qtbot, tmp_path):
    project = Project.create(tmp_path / "proj")
    widget = StepStructureWidget(project, _fake_gmx_env(tmp_path))
    qtbot.addWidget(widget)

    widget._server_radio.setChecked(True)

    assert widget.is_valid() is False
    assert widget.run_button.isEnabled() is False


def test_step_box_invalid_before_structure_step_ran(qtbot, tmp_path):
    project = Project.create(tmp_path / "proj")
    widget = StepBoxWidget(project, {})
    qtbot.addWidget(widget)

    assert widget.is_valid() is False


def test_step_box_valid_once_structure_output_exists(qtbot, tmp_path):
    project = Project.create(tmp_path / "proj")
    (project.step_dir("structure") / "processed.gro").write_text("fake")
    widget = StepBoxWidget(project, {})
    qtbot.addWidget(widget)

    assert widget.is_valid() is True
    commands = widget.build_commands()
    assert commands[0].args[0] == "editconf"


def test_step_solvate_build_commands_uses_default_box(qtbot, tmp_path):
    project = Project.create(tmp_path / "proj")
    (project.step_dir("box") / "boxed.gro").write_text("fake")
    widget = StepSolvateWidget(project, {})
    qtbot.addWidget(widget)

    assert widget.is_valid() is True
    commands = widget.build_commands()
    assert commands[0].args[0] == "solvate"


def test_step_solvate_defaults_box_from_project_water_model(qtbot, tmp_path):
    project = Project.create(tmp_path / "proj")
    project.manifest.water_model = "tip4p"
    (project.step_dir("box") / "boxed.gro").write_text("fake")

    widget = StepSolvateWidget(project, {})
    qtbot.addWidget(widget)

    assert widget.solvent_box_edit.text() == "tip4p.gro"


def test_step_ions_builds_grompp_then_genion_with_stdin(qtbot, tmp_path):
    project = Project.create(tmp_path / "proj")
    (project.step_dir("solvate") / "solvated.gro").write_text("fake")
    widget = StepIonsWidget(project, {})
    qtbot.addWidget(widget)

    assert widget.is_valid() is True
    commands = widget.build_commands()
    assert len(commands) == 2
    assert commands[0].args[0] == "grompp"
    assert commands[0].stdin is None
    assert commands[1].args[0] == "genion"
    assert commands[1].stdin == "SOL\n"

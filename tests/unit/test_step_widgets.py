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
    widget._input_path = pdb

    assert widget.is_valid() is True
    commands = widget.build_commands()
    assert len(commands) == 1
    assert commands[0].args[0] == "pdb2gmx"


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

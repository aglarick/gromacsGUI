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
    (ff_dir / "aminoacids.rtp").write_text("[ bondedtypes ]\n\n[ ALA ]\n [ atoms ]\n")
    return {"GMXDATA": str(top_dir.parent)}


def test_step_structure_invalid_without_any_row_filled(qtbot, tmp_path):
    project = Project.create(tmp_path / "proj")
    widget = StepStructureWidget(project, _fake_gmx_env(tmp_path))
    qtbot.addWidget(widget)

    assert widget.force_field_combo.count() == 2  # "myff" plus "Custom .ff folder..."
    assert widget.water_model_combo.count() == 2  # "None" plus the fake ff's tip3p
    assert len(widget._rows) == 1
    assert widget.is_valid() is False


def test_step_structure_valid_with_only_coordinates_generates_via_pdb2gmx(qtbot, tmp_path):
    project = Project.create(tmp_path / "proj")
    widget = StepStructureWidget(project, _fake_gmx_env(tmp_path))
    qtbot.addWidget(widget)
    pdb = tmp_path / "in.pdb"
    pdb.write_text("ATOM      1  CA  ALA A   1      0.000   0.000   0.000\n")

    widget._rows[0].structure_path = pdb

    assert widget.is_valid() is True
    commands = widget.build_commands()
    assert len(commands) == 1
    assert commands[0].args[0] == "pdb2gmx"


def test_step_structure_row_with_itp_does_not_run_pdb2gmx(qtbot, tmp_path):
    project = Project.create(tmp_path / "proj")
    widget = StepStructureWidget(project, _fake_gmx_env(tmp_path))
    qtbot.addWidget(widget)
    pdb = tmp_path / "in.pdb"
    pdb.write_text("ATOM      1  C1  LIG A   1      0.000   0.000   0.000\n")
    itp = tmp_path / "lig.itp"
    itp.write_text("[ moleculetype ]\nLIG   3\n")

    row = widget._rows[0]
    row.structure_path = pdb
    row.itp_path = itp

    assert widget.is_valid() is True
    assert widget.build_commands() == []


def test_step_structure_custom_ff_folder_requires_itp_on_every_row(qtbot, tmp_path):
    project = Project.create(tmp_path / "proj")
    widget = StepStructureWidget(project, _fake_gmx_env(tmp_path))
    qtbot.addWidget(widget)

    custom_ff = tmp_path / "oplsaam.ff"
    custom_ff.mkdir()
    (custom_ff / "forcefield.itp").write_text("[ defaults ]\n1 3 yes 0.5 0.5\n")

    custom_index = widget.force_field_combo.findData("__custom_ff__")
    widget.force_field_combo.setCurrentIndex(custom_index)
    widget._custom_ff_path = custom_ff

    pdb = tmp_path / "in.pdb"
    pdb.write_text("ATOM      1  CA  ALA A   1      0.000   0.000   0.000\n")
    row = widget._rows[0]
    row.structure_path = pdb

    assert row.is_valid() is False
    assert row.error_label.isHidden() is False
    assert widget.is_valid() is False

    itp = tmp_path / "lig.itp"
    itp.write_text("[ moleculetype ]\nLIG   3\n")
    row.itp_path = itp

    assert row.is_valid() is True
    assert widget.is_valid() is True


def test_step_structure_add_and_remove_row(qtbot, tmp_path):
    project = Project.create(tmp_path / "proj")
    widget = StepStructureWidget(project, _fake_gmx_env(tmp_path))
    qtbot.addWidget(widget)

    widget.add_row()
    assert len(widget._rows) == 2

    widget.remove_row(widget._rows[1])
    assert len(widget._rows) == 1

    # The last remaining row can't be removed.
    widget.remove_row(widget._rows[0])
    assert len(widget._rows) == 1


def test_step_structure_combines_pdb2gmx_and_itp_rows_into_one_topology(qtbot, tmp_path):
    """Simulates what on_all_commands_finished() sees after two pdb2gmx-run
    rows finish and one manual .itp row is staged, without needing real gmx:
    each pdb2gmx row's raw output is hand-written matching the real format
    (verified against an actual pdb2gmx run), then the merge runs for real.
    """
    project = Project.create(tmp_path / "proj")
    widget = StepStructureWidget(project, _fake_gmx_env(tmp_path))
    qtbot.addWidget(widget)

    generated_top = (
        "; header\n"
        '#include "myff.ff/forcefield.itp"\n\n'
        "[ moleculetype ]\n; Name nrexcl\nProtein_chain_A     3\n\n"
        "[ atoms ]\n1 N 1 ALA N 1 0.0 14.0\n\n"
        '; Include Position restraint file\n#ifdef POSRES\n#include "posre.itp"\n#endif\n\n'
        '; Include water topology\n#include "myff.ff/tip3p.itp"\n\n'
        "#ifdef POSRES_WATER\n[ position_restraints ]\n1 1 1000 1000 1000\n#endif\n\n"
        '; Include topology for ions\n#include "myff.ff/ions.itp"\n\n'
        "[ system ]\n; Name\nSYS\n\n[ molecules ]\n; Compound #mols\nProtein_chain_A 1\n"
    )

    # Row 0/1: pdb2gmx-generated (no .itp given), two copies to exercise the
    # name-collision rename path (both would otherwise be "Protein_chain_A").
    pdb = tmp_path / "a.pdb"
    pdb.write_text("ATOM      1  CA  ALA A   1      0.000   0.000   0.000\n")
    widget._rows[0].structure_path = pdb

    widget.add_row()
    widget._rows[1].structure_path = pdb

    widget.add_row()
    row2 = widget._rows[2]
    ligand_pdb = tmp_path / "lig.pdb"
    ligand_pdb.write_text("ATOM      1  C1  LIG A   1      0.000   0.000   0.000\n")
    row2.structure_path = ligand_pdb
    ligand_itp = tmp_path / "lig.itp"
    ligand_itp.write_text("[ moleculetype ]\nLIG   3\n\n[ atoms ]\n1 c3 1 LIG C1 1 0.0\n")
    row2.itp_path = ligand_itp

    assert widget.is_valid() is True

    # Hand-write what real pdb2gmx runs would have produced for rows 0/1.
    for i in (0, 1):
        mol_dir = project.step_dir("structure") / f"mol_{i}"
        mol_dir.mkdir(parents=True)
        (mol_dir / "processed.gro").write_text(f"fake gro {i}\n")
        (mol_dir / "topol.top").write_text(generated_top)
        (mol_dir / "posre.itp").write_text(f"; posre {i}\n")

    widget.on_all_commands_finished()

    top_text = (project.root / "topology" / "topol.top").read_text()
    assert top_text.count('#include "myff.ff/forcefield.itp"') == 1
    assert top_text.count('#include "myff.ff/tip3p.itp"') == 1  # only the first row's water
    assert top_text.count('#include "myff.ff/ions.itp"') == 1
    assert "Protein_chain_A" in top_text
    assert "Protein_chain_A_2" in top_text  # renamed to avoid colliding with row 0
    assert '#include "posre_mol0.itp"' in top_text
    assert '#include "posre_mol1.itp"' in top_text
    assert (project.root / "topology" / "posre_mol0.itp").is_file()
    assert (project.root / "topology" / "posre_mol1.itp").is_file()
    assert '#include "lig.itp"' in top_text
    assert "LIG" in top_text
    assert (project.root / "topology" / "lig.itp").is_file()
    assert (project.step_dir("structure") / "mol_0.gro").read_text() == "fake gro 0\n"
    assert (project.step_dir("structure") / "mol_2.pdb").is_file()


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

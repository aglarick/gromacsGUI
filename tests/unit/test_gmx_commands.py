from __future__ import annotations

from gromacs_gui.gmx.commands.editconf import build_editconf_command
from gromacs_gui.gmx.commands.genion import build_genion_command, genion_stdin
from gromacs_gui.gmx.commands.grompp import build_grompp_command
from gromacs_gui.gmx.commands.pdb2gmx import (
    build_pdb2gmx_command,
    list_heteroatom_residues,
    remove_residues,
)
from gromacs_gui.gmx.commands.solvate import build_solvate_command


def test_build_pdb2gmx_command_includes_ff_and_water_to_avoid_prompts():
    args = build_pdb2gmx_command(
        "in.pdb", "out.gro", "topol.top", "posre.itp", "amber99sb-ildn", "tip3p"
    )

    assert args[0] == "pdb2gmx"
    assert args[args.index("-ff") + 1] == "amber99sb-ildn"
    assert args[args.index("-water") + 1] == "tip3p"
    assert "-ignh" in args


def test_build_pdb2gmx_command_without_ignore_hydrogens():
    args = build_pdb2gmx_command(
        "in.pdb", "out.gro", "topol.top", "posre.itp", "oplsaa", "spce", ignore_hydrogens=False
    )

    assert "-ignh" not in args


def test_build_editconf_command_defaults():
    args = build_editconf_command("in.gro", "out.gro")

    assert args == ["editconf", "-f", "in.gro", "-o", "out.gro", "-bt", "cubic", "-d", "1.0", "-c"]


def test_build_editconf_command_without_centering():
    args = build_editconf_command("in.gro", "out.gro", center=False)

    assert "-c" not in args


def test_build_solvate_command_uses_default_box():
    args = build_solvate_command("in.gro", "topol.top", "out.gro")

    assert args[args.index("-cs") + 1] == "spc216.gro"


def test_build_grompp_command_omits_maxwarn_by_default():
    args = build_grompp_command("em.mdp", "in.gro", "topol.top", "out.tpr")

    assert "-maxwarn" not in args


def test_build_grompp_command_includes_maxwarn_when_given():
    args = build_grompp_command("ions.mdp", "in.gro", "topol.top", "out.tpr", maxwarn=1)

    assert args[args.index("-maxwarn") + 1] == "1"


def test_build_genion_command_defaults_to_neutralizing_with_na_cl():
    args = build_genion_command("ions.tpr", "topol.top", "out.gro")

    assert args[args.index("-pname") + 1] == "NA"
    assert args[args.index("-nname") + 1] == "CL"
    assert "-neutral" in args


def test_build_genion_command_without_neutralization():
    args = build_genion_command("ions.tpr", "topol.top", "out.gro", neutral=False)

    assert "-neutral" not in args


def test_genion_stdin_answers_with_solvent_group_name():
    assert genion_stdin() == "SOL\n"
    assert genion_stdin("Water") == "Water\n"


def test_list_heteroatom_residues_counts_by_residue_name(tmp_path):
    pdb = tmp_path / "test.pdb"
    pdb.write_text(
        "ATOM      1  CA  ALA A   1      0.000   0.000   0.000\n"
        "HETATM    2  O   HOH A 200      1.000   1.000   1.000\n"
        "HETATM    3  O   HOH A 201      1.000   1.000   1.000\n"
        "HETATM    4  C1  LIG A 202      2.000   2.000   2.000\n"
    )

    assert list_heteroatom_residues(pdb) == {"HOH": 2, "LIG": 1}


def test_list_heteroatom_residues_empty_when_no_hetatm(tmp_path):
    pdb = tmp_path / "test.pdb"
    pdb.write_text("ATOM      1  CA  ALA A   1      0.000   0.000   0.000\n")

    assert list_heteroatom_residues(pdb) == {}


def test_remove_residues_removes_only_the_selected_names(tmp_path):
    input_pdb = tmp_path / "in.pdb"
    input_pdb.write_text(
        "ATOM      1  CA  ALA A   1      0.000   0.000   0.000\n"
        "HETATM    2  O   HOH A 200      1.000   1.000   1.000\n"
        "HETATM    3  C1  LIG A 201      2.000   2.000   2.000\n"
        "HETATM    4  S   SO4 A 202      3.000   3.000   3.000\n"
    )
    output_pdb = tmp_path / "out.pdb"

    remove_residues(input_pdb, output_pdb, {"HOH", "SO4"})

    text = output_pdb.read_text()
    assert "ALA" in text
    assert "LIG" in text
    assert "HOH" not in text
    assert "SO4" not in text

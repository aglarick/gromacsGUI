from __future__ import annotations

from pathlib import Path

import pytest

from gromacs_gui.core.pipeline import is_step_ready
from gromacs_gui.core.project import Project
from gromacs_gui.core.step_state import StepState
from gromacs_gui.gmx.commands.editconf import build_editconf_command
from gromacs_gui.gmx.commands.genion import build_genion_command, genion_stdin
from gromacs_gui.gmx.commands.grompp import build_grompp_command
from gromacs_gui.gmx.commands.pdb2gmx import (
    build_pdb2gmx_command,
    find_unsupported_heteroatoms,
    strip_crystal_waters,
)
from gromacs_gui.gmx.commands.solvate import build_solvate_command
from gromacs_gui.gmx.forcefields import gmxdata_top_dir, list_force_fields, list_water_models
from gromacs_gui.gmx.runner import GmxProcessRunner
from gromacs_gui.mdp.defaults import default_mdp_path
from gromacs_gui.utils.settings import find_gmx_binary, with_gmx_defaults

pytestmark = pytest.mark.requires_gmx

FIXTURE_PDB = Path(__file__).parent.parent / "fixtures" / "1aki.pdb"


def _run(qtbot, gmx_path, args, env, cwd, stdin=None, timeout=60000):
    """Run one gmx subcommand to completion through GmxProcessRunner and
    return (exit_code, captured_output_lines).
    """
    runner = GmxProcessRunner()
    lines: list[tuple[str, str]] = []
    runner.output_line.connect(lambda text, stream: lines.append((text, stream)))
    with qtbot.waitSignal(runner.finished, timeout=timeout) as blocker:
        runner.start(gmx_path, args, cwd=str(cwd), env=env)
        if stdin is not None:
            runner.write_stdin(stdin)
            runner.close_stdin()
    return blocker.args[0], lines


def test_structure_through_ions_pipeline_on_real_gmx(qtbot, tmp_path, gmx_environment):
    """Runs pdb2gmx -> editconf -> solvate -> grompp+genion on a real protein
    (1AKI, lysozyme) through the real gmx binary, driven the same way the GUI
    will drive it: GmxProcessRunner + Project recording each step's state.
    """
    env = with_gmx_defaults(gmx_environment)
    gmx_path = find_gmx_binary(env)
    assert gmx_path is not None

    top_dir = gmxdata_top_dir(env)
    assert top_dir is not None
    assert "amber99sb-ildn" in {ff.name for ff in list_force_fields(top_dir)}
    assert "tip3p" in {w.name for w in list_water_models(top_dir, "amber99sb-ildn")}

    # 1AKI has only crystallographic water HETATM records, no ligands.
    assert find_unsupported_heteroatoms(FIXTURE_PDB) == set()

    project = Project.create(tmp_path / "myproj")
    topology_dir = project.root / "topology"

    # --- structure (pdb2gmx) ---
    assert is_step_ready(project, "structure")
    structure_dir = project.step_dir("structure")
    clean_pdb = structure_dir / "clean.pdb"
    strip_crystal_waters(FIXTURE_PDB, clean_pdb)

    processed_gro = structure_dir / "processed.gro"
    topol_top = topology_dir / "topol.top"
    posre_itp = topology_dir / "posre.itp"
    args = build_pdb2gmx_command(
        clean_pdb, processed_gro, topol_top, posre_itp, "amber99sb-ildn", "tip3p"
    )
    project.record_step_started("structure")
    exit_code, _ = _run(qtbot, gmx_path, args, env, project.root)
    assert exit_code == 0
    assert processed_gro.is_file()
    assert topol_top.is_file()
    project.record_step_finished(
        "structure",
        output_files=[
            str(processed_gro.relative_to(project.root)),
            str(topol_top.relative_to(project.root)),
            str(posre_itp.relative_to(project.root)),
        ],
    )
    assert project.step_record("structure").state == StepState.DONE

    # --- box (editconf) ---
    assert is_step_ready(project, "box")
    boxed_gro = project.step_dir("box") / "boxed.gro"
    args = build_editconf_command(processed_gro, boxed_gro)
    project.record_step_started("box")
    exit_code, _ = _run(qtbot, gmx_path, args, env, project.root)
    assert exit_code == 0
    assert boxed_gro.is_file()
    project.record_step_finished("box", output_files=[str(boxed_gro.relative_to(project.root))])

    # --- solvate ---
    assert is_step_ready(project, "solvate")
    solvated_gro = project.step_dir("solvate") / "solvated.gro"
    args = build_solvate_command(boxed_gro, topol_top, solvated_gro)
    project.record_step_started("solvate")
    exit_code, _ = _run(qtbot, gmx_path, args, env, project.root)
    assert exit_code == 0
    assert solvated_gro.is_file()
    project.record_step_finished(
        "solvate", output_files=[str(solvated_gro.relative_to(project.root))]
    )

    # --- ions (grompp + genion) ---
    assert is_step_ready(project, "ions")
    ions_dir = project.step_dir("ions")
    ions_tpr = ions_dir / "ions.tpr"
    grompp_args = build_grompp_command(
        default_mdp_path("ions"), solvated_gro, topol_top, ions_tpr, maxwarn=1
    )
    project.record_step_started("ions")
    exit_code, _ = _run(qtbot, gmx_path, grompp_args, env, project.root)
    assert exit_code == 0
    assert ions_tpr.is_file()

    ionized_gro = ions_dir / "ionized.gro"
    genion_args = build_genion_command(ions_tpr, topol_top, ionized_gro)
    exit_code, lines = _run(qtbot, gmx_path, genion_args, env, project.root, stdin=genion_stdin())
    assert exit_code == 0, "\n".join(text for text, _ in lines)
    assert ionized_gro.is_file()
    project.record_step_finished("ions", output_files=[str(ionized_gro.relative_to(project.root))])
    assert project.step_record("ions").state == StepState.DONE

    # Re-opening the project from disk should reconcile cleanly (all output
    # files are really there) and leave the next stage runnable.
    reopened = Project.open(project.root)
    for step_name in ["structure", "box", "solvate", "ions"]:
        assert reopened.step_record(step_name).state == StepState.DONE
    assert is_step_ready(reopened, "em")

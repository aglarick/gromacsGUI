from __future__ import annotations

from pathlib import Path

# HETATM residue names pdb2gmx already knows how to fold into ordinary water;
# anything else HETATM is unsupported in Phase 1 (ligands, cofactors, modified
# residues need extra topology work a standard force field doesn't provide).
_KNOWN_WATER_RESIDUES = frozenset({"HOH", "WAT", "SOL"})


def find_unsupported_heteroatoms(pdb_path: Path) -> set[str]:
    """Return HETATM residue names that Phase 1 can't handle automatically."""
    unsupported: set[str] = set()
    for line in Path(pdb_path).read_text(errors="replace").splitlines():
        if not line.startswith("HETATM"):
            continue
        residue_name = line[17:20].strip()
        if residue_name and residue_name not in _KNOWN_WATER_RESIDUES:
            unsupported.add(residue_name)
    return unsupported


def strip_crystal_waters(input_pdb: Path, output_pdb: Path) -> None:
    """Remove crystallographic water HETATM records, keeping everything else.

    Standard pre-processing before pdb2gmx: crystal waters are discarded here
    and replaced by GROMACS-generated solvent in the later `solvate` step.
    """
    lines = Path(input_pdb).read_text(errors="replace").splitlines(keepends=True)
    kept = [
        line
        for line in lines
        if not (line.startswith("HETATM") and line[17:20].strip() in {"HOH", "WAT"})
    ]
    Path(output_pdb).write_text("".join(kept))


def build_pdb2gmx_command(
    input_structure: Path,
    output_gro: Path,
    topology_top: Path,
    posre_itp: Path,
    force_field: str,
    water_model: str,
    ignore_hydrogens: bool = True,
) -> list[str]:
    """-ff/-water make this non-interactive; pdb2gmx would otherwise prompt
    with a numbered menu for both.
    """
    args = [
        "pdb2gmx",
        "-f",
        str(input_structure),
        "-o",
        str(output_gro),
        "-p",
        str(topology_top),
        "-i",
        str(posre_itp),
        "-ff",
        force_field,
        "-water",
        water_model,
    ]
    if ignore_hydrogens:
        args.append("-ignh")
    return args

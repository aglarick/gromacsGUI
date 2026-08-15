from __future__ import annotations

from pathlib import Path


def list_heteroatom_residues(pdb_path: Path) -> dict[str, int]:
    """Count HETATM records by residue name.

    Per the PDB format's own ATOM/HETATM distinction, this reliably finds
    everything that isn't part of the standard polymer chain: crystallographic
    water, ions, ligands, cofactors, and any modified residue a standard force
    field's pdb2gmx database doesn't recognize. The GUI shows this list to the
    user rather than guessing what to remove.
    """
    counts: dict[str, int] = {}
    for line in Path(pdb_path).read_text(errors="replace").splitlines():
        if not line.startswith("HETATM"):
            continue
        residue_name = line[17:20].strip()
        if residue_name:
            counts[residue_name] = counts.get(residue_name, 0) + 1
    return counts


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

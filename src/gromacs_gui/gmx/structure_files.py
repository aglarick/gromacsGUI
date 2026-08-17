"""General-purpose residue listing/filtering for .pdb and .gro files.

Unlike gmx/commands/pdb2gmx.py's list_heteroatom_residues (which only looks
at HETATM records, specifically to flag what pdb2gmx can't handle), these
functions cover every residue regardless of the PDB ATOM/HETATM distinction
and work on .gro too - needed for cleaning up an already-assembled box with
multiple combined molecules, not just a single protein straight from the PDB.
"""

from __future__ import annotations

from pathlib import Path


def list_residues(structure_path: Path) -> dict[str, int]:
    """Count every residue by name in a .pdb or .gro file."""
    if Path(structure_path).suffix.lower() == ".gro":
        return _list_residues_gro(structure_path)
    return _list_residues_pdb(structure_path)


def remove_residues(input_path: Path, output_path: Path, residue_names: set[str]) -> None:
    """Write a copy of input_path with every atom belonging to the given
    residue names removed, keeping everything else untouched.
    """
    if Path(input_path).suffix.lower() == ".gro":
        _remove_residues_gro(input_path, output_path, residue_names)
    else:
        _remove_residues_pdb(input_path, output_path, residue_names)


def extract_first_instance(input_path: Path, output_path: Path, residue_names: set[str]) -> None:
    """Write only the first molecule instance (in file order) whose residue
    name is in residue_names, discarding every other atom. Used to isolate a
    single copy of a repeated molecule out of a box (e.g. one SOL out of
    hundreds) rather than keeping every instance of that residue name.
    """
    if Path(input_path).suffix.lower() == ".gro":
        _extract_first_instance_gro(input_path, output_path, residue_names)
    else:
        _extract_first_instance_pdb(input_path, output_path, residue_names)


def _list_residues_pdb(pdb_path: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    for line in Path(pdb_path).read_text(errors="replace").splitlines():
        if not line.startswith(("ATOM", "HETATM")):
            continue
        name = line[17:20].strip()
        if name:
            counts[name] = counts.get(name, 0) + 1
    return counts


def _remove_residues_pdb(input_path: Path, output_path: Path, residue_names: set[str]) -> None:
    lines = Path(input_path).read_text(errors="replace").splitlines(keepends=True)
    kept = [
        line
        for line in lines
        if not (line.startswith(("ATOM", "HETATM")) and line[17:20].strip() in residue_names)
    ]
    Path(output_path).write_text("".join(kept))


def _extract_first_instance_pdb(
    input_path: Path, output_path: Path, residue_names: set[str]
) -> None:
    lines = Path(input_path).read_text(errors="replace").splitlines(keepends=True)

    target_key = None
    for line in lines:
        if line.startswith(("ATOM", "HETATM")) and line[17:20].strip() in residue_names:
            target_key = line[21:27]  # chain + resSeq + iCode: one instance
            break

    kept = [
        line
        for line in lines
        if not line.startswith(("ATOM", "HETATM")) or line[21:27] == target_key
    ]
    Path(output_path).write_text("".join(kept))


def _list_residues_gro(gro_path: Path) -> dict[str, int]:
    lines = Path(gro_path).read_text(errors="replace").splitlines()
    atom_lines = _gro_atom_lines(lines)
    counts: dict[str, int] = {}
    for line in atom_lines:
        name = line[5:10].strip()
        if name:
            counts[name] = counts.get(name, 0) + 1
    return counts


def _remove_residues_gro(input_path: Path, output_path: Path, residue_names: set[str]) -> None:
    lines = Path(input_path).read_text(errors="replace").splitlines()
    if len(lines) < 3:
        Path(output_path).write_text("\n".join(lines) + ("\n" if lines else ""))
        return

    title = lines[0]
    atom_lines = _gro_atom_lines(lines)
    box_line = lines[2 + len(atom_lines)] if len(lines) > 2 + len(atom_lines) else ""

    kept_atom_lines = [line for line in atom_lines if line[5:10].strip() not in residue_names]

    output_lines = [title, str(len(kept_atom_lines)), *kept_atom_lines, box_line]
    Path(output_path).write_text("\n".join(output_lines) + "\n")


def _extract_first_instance_gro(
    input_path: Path, output_path: Path, residue_names: set[str]
) -> None:
    lines = Path(input_path).read_text(errors="replace").splitlines()
    if len(lines) < 3:
        Path(output_path).write_text("\n".join(lines) + ("\n" if lines else ""))
        return

    title = lines[0]
    atom_lines = _gro_atom_lines(lines)
    box_line = lines[2 + len(atom_lines)] if len(lines) > 2 + len(atom_lines) else ""

    target_resid = None
    for line in atom_lines:
        if line[5:10].strip() in residue_names:
            target_resid = line[0:5]  # resid field: one molecule instance
            break

    kept_atom_lines = [line for line in atom_lines if line[0:5] == target_resid]

    output_lines = [title, str(len(kept_atom_lines)), *kept_atom_lines, box_line]
    Path(output_path).write_text("\n".join(output_lines) + "\n")


def _gro_atom_lines(lines: list[str]) -> list[str]:
    """lines[0] is a title, lines[1] is the atom count, then that many atom
    lines follow, then a final box-vectors line.
    """
    if len(lines) < 2:
        return []
    try:
        atom_count = int(lines[1].strip())
    except ValueError:
        return []
    return lines[2 : 2 + atom_count]

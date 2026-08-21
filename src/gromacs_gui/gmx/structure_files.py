"""General-purpose residue listing/filtering for .pdb and .gro files.

Unlike gmx/commands/pdb2gmx.py's list_heteroatom_residues (which only looks
at HETATM records, specifically to flag what pdb2gmx can't handle), these
functions cover every residue regardless of the PDB ATOM/HETATM distinction
and work on .gro too - needed for cleaning up an already-assembled box with
multiple combined molecules, not just a single protein straight from the PDB.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AtomPosition:
    """One atom's coordinates plus enough identity to group it into its
    molecule instance - used for the cleanup tool's live preview, not for
    writing files (which works on raw lines to preserve exact formatting).
    Coordinates are always in angstrom (.gro's native nanometers are
    converted on read) so a synthesized preview PDB is unit-correct
    regardless of the source format.
    """

    residue_name: str
    atom_name: str
    instance_key: str
    x: float
    y: float
    z: float


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


def read_atom_positions(structure_path: Path) -> list[AtomPosition]:
    """Parse every atom's coordinates for the cleanup tool's live preview."""
    if Path(structure_path).suffix.lower() == ".gro":
        return _read_atom_positions_gro(structure_path)
    return _read_atom_positions_pdb(structure_path)


def format_atoms_as_pdb(atoms: list[AtomPosition]) -> str:
    """Synthesize a minimal PDB text from parsed preview atoms, purely to
    feed an external molecular viewer - never written to disk as the tool's
    actual saved output, so residue/atom numbering here is just sequential
    order, not the original file's own numbers.
    """
    lines = []
    instance_order: dict[str, int] = {}
    for serial, atom in enumerate(atoms, start=1):
        res_seq = instance_order.setdefault(atom.instance_key, len(instance_order) + 1)
        name = atom.atom_name[:4]
        name_field = name if len(name) == 4 else f" {name:<3}"
        lines.append(
            "ATOM  "
            f"{serial:>5} "
            f"{name_field:<4} "
            f"{atom.residue_name[:3]:>3} A"
            f"{res_seq:>4}    "
            f"{atom.x:>8.3f}{atom.y:>8.3f}{atom.z:>8.3f}"
            "  1.00  0.00\n"
        )
    lines.append("END\n")
    return "".join(lines)


def write_gro(
    path: Path,
    atoms: list[AtomPosition],
    box_nm: tuple[float, float, float],
    title: str = "Combined system",
) -> None:
    """Write parsed atoms back out as a minimal valid .gro file - like
    format_atoms_as_pdb, but for callers (e.g. Structure's grompp
    consistency check) that need a real coordinate file grompp can read,
    not just something to feed to a viewer.
    """
    lines = [title, str(len(atoms))]
    instance_order: dict[str, int] = {}
    for serial, atom in enumerate(atoms, start=1):
        res_seq = instance_order.setdefault(atom.instance_key, len(instance_order) + 1)
        lines.append(
            f"{res_seq % 100000:>5}{atom.residue_name[:5]:<5}{atom.atom_name[:5]:>5}"
            f"{serial % 100000:>5}"
            f"{atom.x / 10:>8.3f}{atom.y / 10:>8.3f}{atom.z / 10:>8.3f}"
        )
    lines.append(f"{box_nm[0]:>10.5f}{box_nm[1]:>10.5f}{box_nm[2]:>10.5f}")
    Path(path).write_text("\n".join(lines) + "\n")


def select_preview_atoms(
    atoms: list[AtomPosition], residue_names_to_keep: set[str]
) -> list[AtomPosition]:
    """Filter parsed atoms the same way _save_to's "keep by residue name"
    mode would filter file lines, so the preview matches what saving would
    actually produce. ("Extract one molecule" mode uses connectivity-based
    fragment selection instead - see gmx/molecule_fragments.py.)
    """
    return [atom for atom in atoms if atom.residue_name in residue_names_to_keep]


def _read_atom_positions_pdb(pdb_path: Path) -> list[AtomPosition]:
    positions = []
    for line in Path(pdb_path).read_text(errors="replace").splitlines():
        if not line.startswith(("ATOM", "HETATM")):
            continue
        name = line[17:20].strip()
        if not name:
            continue
        try:
            x, y, z = float(line[30:38]), float(line[38:46]), float(line[46:54])
        except ValueError:
            continue
        atom_name = line[12:16].strip()
        positions.append(AtomPosition(name, atom_name, line[21:27], x, y, z))
    return positions


def _read_atom_positions_gro(gro_path: Path) -> list[AtomPosition]:
    """Coordinates are split by whitespace rather than sliced at fixed
    columns: .gro widens the coordinate field width dynamically for very
    large/negative values, so the nominal 8-char field spec can't be relied
    on - only the leading resnum/resname/atomname/atomnr columns are truly
    fixed-width. .gro coordinates are in nanometers; multiply by 10 so
    AtomPosition is always angstrom, regardless of source format.
    """
    lines = Path(gro_path).read_text(errors="replace").splitlines()
    positions = []
    for line in _gro_atom_lines(lines):
        name = line[5:10].strip()
        if not name:
            continue
        parts = line[20:].split()
        if len(parts) < 3:
            continue
        try:
            x, y, z = float(parts[0]) * 10, float(parts[1]) * 10, float(parts[2]) * 10
        except ValueError:
            continue
        atom_name = line[10:15].strip()
        positions.append(AtomPosition(name, atom_name, line[0:5], x, y, z))
    return positions


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

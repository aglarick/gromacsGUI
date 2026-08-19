from __future__ import annotations

from gromacs_gui.gmx.structure_files import (
    format_atoms_as_pdb,
    list_residues,
    read_atom_positions,
    remove_residues,
    select_preview_atoms,
)


def _gro_atom_line(
    resnum: int, resname: str, atomname: str, atomnr: int, x: float, y: float, z: float
) -> str:
    """Builds a line matching GROMACS's real fixed-width .gro atom format
    (%5d%-5s%5s%5d%8.3f%8.3f%8.3f), so fixtures can't drift out of column
    alignment the way hand-typed strings can.
    """
    return f"{resnum:>5}{resname:<5}{atomname:>5}{atomnr:>5}{x:>8.3f}{y:>8.3f}{z:>8.3f}"


PDB_SAMPLE = (
    "ATOM      1  CA  ALA A   1      0.000   0.000   0.000\n"
    "HETATM    2  O   HOH A 200      1.000   1.000   1.000\n"
    "HETATM    3  C1  LIG A 201      2.000   2.000   2.000\n"
)

GRO_SAMPLE = (
    "Test system\n"
    "    3\n"
    + _gro_atom_line(1, "ALA", "CA", 1, 0.0, 0.0, 0.0)
    + "\n"
    + _gro_atom_line(200, "HOH", "O", 2, 1.0, 1.0, 1.0)
    + "\n"
    + _gro_atom_line(201, "LIG", "C1", 3, 2.0, 2.0, 2.0)
    + "\n"
    "   3.00000   3.00000   3.00000\n"
)

PDB_REPEATED_HOH = (
    "ATOM      1  CA  ALA A   1      0.000   0.000   0.000\n"
    "HETATM    2  O   HOH A 200      1.000   1.000   1.000\n"
    "HETATM    3  O   HOH A 201      2.000   2.000   2.000\n"
)


def test_list_residues_pdb_counts_atom_and_hetatm(tmp_path):
    pdb = tmp_path / "test.pdb"
    pdb.write_text(PDB_SAMPLE)

    assert list_residues(pdb) == {"ALA": 1, "HOH": 1, "LIG": 1}


def test_remove_residues_pdb_removes_selected_names_regardless_of_atom_hetatm(tmp_path):
    pdb = tmp_path / "in.pdb"
    pdb.write_text(PDB_SAMPLE)
    output = tmp_path / "out.pdb"

    remove_residues(pdb, output, {"HOH"})

    text = output.read_text()
    assert "ALA" in text
    assert "LIG" in text
    assert "HOH" not in text


def test_list_residues_gro_counts_by_name(tmp_path):
    gro = tmp_path / "test.gro"
    gro.write_text(GRO_SAMPLE)

    assert list_residues(gro) == {"ALA": 1, "HOH": 1, "LIG": 1}


def test_remove_residues_gro_updates_atom_count_header(tmp_path):
    gro = tmp_path / "in.gro"
    gro.write_text(GRO_SAMPLE)
    output = tmp_path / "out.gro"

    remove_residues(gro, output, {"HOH"})

    lines = output.read_text().splitlines()
    assert lines[1].strip() == "2"
    assert not any("HOH" in line for line in lines)
    assert any("ALA" in line for line in lines)
    assert any("LIG" in line for line in lines)
    assert lines[-1].strip() == "3.00000   3.00000   3.00000"


def test_read_atom_positions_pdb(tmp_path):
    pdb = tmp_path / "in.pdb"
    pdb.write_text(PDB_SAMPLE)

    positions = read_atom_positions(pdb)

    assert [p.residue_name for p in positions] == ["ALA", "HOH", "LIG"]
    assert positions[0].atom_name == "CA"
    assert positions[0].x == 0.0
    assert positions[2].z == 2.0


def test_read_atom_positions_gro(tmp_path):
    gro = tmp_path / "in.gro"
    gro.write_text(GRO_SAMPLE)

    positions = read_atom_positions(gro)

    assert [p.residue_name for p in positions] == ["ALA", "HOH", "LIG"]
    assert positions[1].atom_name == "O"
    assert positions[1].y == 10.0  # nm converted to angstrom


def test_select_preview_atoms_keeps_all_instances_of_kept_names(tmp_path):
    pdb = tmp_path / "in.pdb"
    pdb.write_text(PDB_REPEATED_HOH)
    atoms = read_atom_positions(pdb)

    selected = select_preview_atoms(atoms, {"HOH"})

    assert len(selected) == 2
    assert all(a.residue_name == "HOH" for a in selected)


def test_select_preview_atoms_empty_keep_set_returns_nothing(tmp_path):
    pdb = tmp_path / "in.pdb"
    pdb.write_text(PDB_SAMPLE)
    atoms = read_atom_positions(pdb)

    assert select_preview_atoms(atoms, set()) == []


def test_format_atoms_as_pdb_produces_parseable_fixed_width_records(tmp_path):
    pdb = tmp_path / "in.pdb"
    pdb.write_text(PDB_SAMPLE)
    atoms = read_atom_positions(pdb)

    text = format_atoms_as_pdb(atoms)
    lines = text.splitlines()

    assert lines[-1] == "END"
    assert all(line.startswith("ATOM") for line in lines[:-1])
    for line in lines[:-1]:
        # Coordinate columns must be numeric and in the standard PDB slots.
        float(line[30:38])
        float(line[38:46])
        float(line[46:54])
    assert "ALA" in lines[0]
    assert "HOH" in lines[1]
    assert "LIG" in lines[2]


def test_format_atoms_as_pdb_round_trips_coordinates(tmp_path):
    pdb = tmp_path / "in.pdb"
    pdb.write_text(PDB_SAMPLE)
    atoms = read_atom_positions(pdb)

    text = format_atoms_as_pdb(atoms)
    lines = text.splitlines()

    assert float(lines[2][30:38]) == 2.0
    assert float(lines[2][38:46]) == 2.0
    assert float(lines[2][46:54]) == 2.0

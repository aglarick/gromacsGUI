from __future__ import annotations

from gromacs_gui.gmx.structure_files import list_residues, remove_residues

PDB_SAMPLE = (
    "ATOM      1  CA  ALA A   1      0.000   0.000   0.000\n"
    "HETATM    2  O   HOH A 200      1.000   1.000   1.000\n"
    "HETATM    3  C1  LIG A 201      2.000   2.000   2.000\n"
)

GRO_SAMPLE = (
    "Test system\n"
    "    3\n"
    "    1ALA      CA    1   0.000   0.000   0.000\n"
    "  200HOH       O    2   1.000   1.000   1.000\n"
    "  201LIG      C1    3   2.000   2.000   2.000\n"
    "   3.00000   3.00000   3.00000\n"
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

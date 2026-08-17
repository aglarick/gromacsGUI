from __future__ import annotations

from gromacs_gui.gmx.structure_files import (
    extract_first_instance,
    list_residues,
    read_atom_positions,
    remove_residues,
    select_preview_atoms,
)

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

PDB_REPEATED_HOH = (
    "ATOM      1  CA  ALA A   1      0.000   0.000   0.000\n"
    "HETATM    2  O   HOH A 200      1.000   1.000   1.000\n"
    "HETATM    3  O   HOH A 201      2.000   2.000   2.000\n"
)

GRO_REPEATED_HOH = (
    "Test system\n"
    "    3\n"
    "    1ALA      CA    1   0.000   0.000   0.000\n"
    "  200HOH       O    2   1.000   1.000   1.000\n"
    "  201HOH       O    3   2.000   2.000   2.000\n"
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


def test_extract_first_instance_pdb_keeps_only_one_copy(tmp_path):
    pdb = tmp_path / "in.pdb"
    pdb.write_text(PDB_REPEATED_HOH)
    output = tmp_path / "out.pdb"

    extract_first_instance(pdb, output, {"HOH"})

    text = output.read_text()
    assert text.count("HOH") == 1
    assert "ALA" not in text
    assert "200" in text  # kept the first instance, not the second
    assert "201" not in text


def test_extract_first_instance_gro_keeps_only_one_copy(tmp_path):
    gro = tmp_path / "in.gro"
    gro.write_text(GRO_REPEATED_HOH)
    output = tmp_path / "out.gro"

    extract_first_instance(gro, output, {"HOH"})

    lines = output.read_text().splitlines()
    assert lines[1].strip() == "1"
    assert lines[2].strip().startswith("200HOH")
    assert lines[-1].strip() == "3.00000   3.00000   3.00000"


def test_read_atom_positions_pdb(tmp_path):
    pdb = tmp_path / "in.pdb"
    pdb.write_text(PDB_SAMPLE)

    positions = read_atom_positions(pdb)

    assert [p.residue_name for p in positions] == ["ALA", "HOH", "LIG"]
    assert positions[0].x == 0.0
    assert positions[2].z == 2.0


def test_read_atom_positions_gro(tmp_path):
    gro = tmp_path / "in.gro"
    gro.write_text(GRO_SAMPLE)

    positions = read_atom_positions(gro)

    assert [p.residue_name for p in positions] == ["ALA", "HOH", "LIG"]
    assert positions[1].y == 1.0


def test_select_preview_atoms_all_instances(tmp_path):
    pdb = tmp_path / "in.pdb"
    pdb.write_text(PDB_REPEATED_HOH)
    atoms = read_atom_positions(pdb)

    selected = select_preview_atoms(atoms, {"HOH"}, single_instance=False)

    assert len(selected) == 2
    assert all(a.residue_name == "HOH" for a in selected)


def test_select_preview_atoms_single_instance(tmp_path):
    pdb = tmp_path / "in.pdb"
    pdb.write_text(PDB_REPEATED_HOH)
    atoms = read_atom_positions(pdb)

    selected = select_preview_atoms(atoms, {"HOH"}, single_instance=True)

    assert len(selected) == 1
    assert selected[0].instance_key == atoms[1].instance_key  # the first HOH instance


def test_select_preview_atoms_empty_keep_set_returns_nothing(tmp_path):
    pdb = tmp_path / "in.pdb"
    pdb.write_text(PDB_SAMPLE)
    atoms = read_atom_positions(pdb)

    assert select_preview_atoms(atoms, set(), single_instance=False) == []
    assert select_preview_atoms(atoms, set(), single_instance=True) == []

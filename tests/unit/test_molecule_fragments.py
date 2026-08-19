from __future__ import annotations

from gromacs_gui.gmx.molecule_fragments import (
    compute_fragments,
    first_fragment_with_residue,
    fragment_to_atom_positions,
)

# Two isolated single-atom SOL "molecules" plus a POL molecule split across
# two residues sharing a name (mirrors a real polymer chain: every monomer
# is its own same-named residue) whose atoms are close enough (1.5 A) to be
# guessed as bonded together.
PDB_WITH_BONDED_POLYMER = (
    "ATOM      1  O   SOL A   1       0.000   0.000   0.000  1.00  0.00\n"
    "ATOM      2  O   SOL A   2      20.000  20.000  20.000  1.00  0.00\n"
    "ATOM      3  C1  POL A   3      50.000   0.000   0.000  1.00  0.00\n"
    "ATOM      4  C2  POL A   3      51.500   0.000   0.000  1.00  0.00\n"
    "ATOM      5  C1  POL A   4      53.000   0.000   0.000  1.00  0.00\n"
    "ATOM      6  C2  POL A   4      54.500   0.000   0.000  1.00  0.00\n"
)

# Same molecules, but written as .gro instead (coordinates in nm, not
# angstrom - 0.150 nm steps below are ~1.5 A, a plausible C-C bond length)
# - same connectivity claim should hold for either input format.
GRO_WITH_BONDED_POLYMER = (
    "Test system\n"
    "    6\n"
    "    1SOL      O    1   0.000   0.000   0.000\n"
    "    2SOL      O    2   2.000   2.000   2.000\n"
    "    3POL     C1    3   5.000   0.000   0.000\n"
    "    3POL     C2    4   5.150   0.000   0.000\n"
    "    4POL     C1    5   5.300   0.000   0.000\n"
    "    4POL     C2    6   5.450   0.000   0.000\n"
    "  10.00000  10.00000  10.00000\n"
)


def test_compute_fragments_separates_unconnected_molecules(tmp_path):
    pdb = tmp_path / "system.pdb"
    pdb.write_text(PDB_WITH_BONDED_POLYMER)

    fragments = compute_fragments(pdb)

    sizes = sorted(len(f) for f in fragments)
    assert sizes == [1, 1, 4]


def test_compute_fragments_keeps_multi_residue_molecule_whole_pdb(tmp_path):
    pdb = tmp_path / "system.pdb"
    pdb.write_text(PDB_WITH_BONDED_POLYMER)

    fragments = compute_fragments(pdb)
    polymer = first_fragment_with_residue(fragments, {"POL"})

    assert len(polymer) == 4
    assert set(polymer.resids) == {3, 4}


def test_compute_fragments_keeps_multi_residue_molecule_whole_gro(tmp_path):
    gro = tmp_path / "system.gro"
    gro.write_text(GRO_WITH_BONDED_POLYMER)

    fragments = compute_fragments(gro)
    polymer = first_fragment_with_residue(fragments, {"POL"})

    assert len(polymer) == 4
    assert set(polymer.resids) == {3, 4}


def test_first_fragment_with_residue_picks_only_one_of_several_separate_instances(tmp_path):
    pdb = tmp_path / "system.pdb"
    pdb.write_text(PDB_WITH_BONDED_POLYMER)
    fragments = compute_fragments(pdb)

    fragment = first_fragment_with_residue(fragments, {"SOL"})

    assert len(fragment) == 1
    assert set(fragment.resnames) == {"SOL"}


def test_first_fragment_with_residue_returns_none_when_no_match(tmp_path):
    pdb = tmp_path / "system.pdb"
    pdb.write_text(PDB_WITH_BONDED_POLYMER)
    fragments = compute_fragments(pdb)

    assert first_fragment_with_residue(fragments, {"NOPE"}) is None


def test_compute_fragments_handles_unrecognized_atom_types(tmp_path):
    """Real bug hit on a coarse-grained force field: MDAnalysis's default
    bond-guessing raises ValueError for atom types it has no van der Waals
    radius for (e.g. a custom type like "V" for a virtual/dummy site).
    compute_fragments must retry with a generic fallback radius instead of
    crashing the whole cleanup tool.
    """
    pdb = tmp_path / "system.pdb"
    pdb.write_text(
        "ATOM      1  V1  POL A   1       0.000   0.000   0.000  1.00  0.00\n"
        "ATOM      2  V2  POL A   1       1.500   0.000   0.000  1.00  0.00\n"
    )

    fragments = compute_fragments(pdb)

    assert len(fragments) == 1
    assert len(fragments[0]) == 2


def test_fragment_to_atom_positions_preserves_names_and_coordinates(tmp_path):
    pdb = tmp_path / "system.pdb"
    pdb.write_text(PDB_WITH_BONDED_POLYMER)
    fragments = compute_fragments(pdb)
    polymer = first_fragment_with_residue(fragments, {"POL"})

    positions = fragment_to_atom_positions(polymer)

    assert len(positions) == 4
    assert {p.atom_name for p in positions} == {"C1", "C2"}
    assert all(p.residue_name == "POL" for p in positions)
    xs = sorted(p.x for p in positions)
    assert xs[0] == 50.0
    assert xs[-1] == 54.5

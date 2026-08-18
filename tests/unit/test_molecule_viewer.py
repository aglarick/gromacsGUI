from __future__ import annotations

from gromacs_gui.gmx.structure_files import AtomPosition
from gromacs_gui.ui.widgets.molecule_viewer import MoleculeViewer3D


def test_shows_placeholder_message_on_construction(qtbot):
    viewer = MoleculeViewer3D()
    qtbot.addWidget(viewer)

    assert viewer._axes.texts  # placeholder text drawn


def test_set_atoms_renders_a_scatter_per_residue(qtbot):
    viewer = MoleculeViewer3D()
    qtbot.addWidget(viewer)

    atoms = [
        AtomPosition("ALA", "CA", "A1", 0.0, 0.0, 0.0),
        AtomPosition("HOH", "O", "A2", 1.0, 1.0, 1.0),
    ]
    viewer.set_atoms(atoms)

    assert len(viewer._axes.collections) == 2  # one scatter series per residue name


def test_set_atoms_with_empty_list_shows_message(qtbot):
    viewer = MoleculeViewer3D()
    qtbot.addWidget(viewer)

    viewer.set_atoms([])

    assert viewer._axes.texts


def test_oversized_selection_falls_back_to_message_instead_of_freezing(qtbot):
    viewer = MoleculeViewer3D()
    qtbot.addWidget(viewer)
    atoms = [AtomPosition("SOL", "O", str(i), 0.0, 0.0, 0.0) for i in range(25000)]

    viewer.set_atoms(atoms)

    assert viewer._axes.texts
    assert not viewer._axes.collections

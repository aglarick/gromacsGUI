from __future__ import annotations

import pytest

from gromacs_gui.gmx.structure_files import AtomPosition
from gromacs_gui.ui.wizard.steps.step_cleanup import _create_viewer

try:
    from gromacs_gui.ui.widgets.molecule_viewer_web import MoleculeViewerWeb

    _WEBENGINE_AVAILABLE = True
except ImportError:
    _WEBENGINE_AVAILABLE = False


def test_create_viewer_always_returns_something_usable(qtbot):
    """Whichever backend gets picked (web or matplotlib fallback), it must
    expose the same duck-typed interface the cleanup tool relies on.
    """
    viewer = _create_viewer(None)
    qtbot.addWidget(viewer)

    assert hasattr(viewer, "set_atoms")
    assert hasattr(viewer, "show_message")


@pytest.mark.skipif(not _WEBENGINE_AVAILABLE, reason="QtWebEngine not importable here")
def test_molecule_viewer_web_set_atoms_does_not_raise(qtbot):
    viewer = MoleculeViewerWeb()
    qtbot.addWidget(viewer)

    viewer.set_atoms([AtomPosition("ALA", "CA", "A1", 0.0, 0.0, 0.0)])
    viewer.set_atoms([])
    viewer.show_message("test")

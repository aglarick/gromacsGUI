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


@pytest.mark.skipif(not _WEBENGINE_AVAILABLE, reason="QtWebEngine not importable here")
def test_molecule_viewer_web_actually_loads_a_structure(qtbot):
    """Regression test: a past version called a nonexistent viewer.clear()
    (silently breaking every load) and dropped set_atoms() calls made
    before the page finished loading molstar.js - both left Mol* showing
    an empty viewport with no visible error. Asserts the structure Mol*
    actually holds after loading, not just that no exception was raised.
    """
    viewer = MoleculeViewerWeb()
    qtbot.addWidget(viewer)
    viewer.show()

    # Exercise the exact race that broke this before: call set_atoms()
    # immediately, without waiting for the page to finish loading first.
    viewer.set_atoms([AtomPosition("ALA", "CA", "A1", 0.0, 0.0, 0.0)])

    result = {}

    def _poll_structure_count():
        js = (
            "window.__gromacsGuiViewer && window.__gromacsGuiViewer.then("
            "function(v) { "
            "window.__testStructureCount = "
            "v.plugin.managers.structure.hierarchy.current.structures.length; "
            "});"
        )
        viewer._view.page().runJavaScript(js)
        viewer._view.page().runJavaScript(
            "window.__testStructureCount", lambda count: result.update(count=count)
        )

    qtbot.waitUntil(lambda: (_poll_structure_count(), result.get("count"))[1] == 1, timeout=15000)

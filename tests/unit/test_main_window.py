from PySide6.QtWidgets import QLabel

from gromacs_gui.main_window import MainWindow
from gromacs_gui.ui.wizard.steps import step_cleanup


def test_main_window_creates_and_shows(qtbot, monkeypatch):
    # Showing the real Cleanup tool for the first time makes its matplotlib
    # (QtAgg) preview canvas paint for real, which segfaults under the
    # offscreen QPA platform this suite runs under (freetype/fontconfig
    # native conflict, reproduced independently of this app's own code) -
    # stub the 3D viewer so this test can exercise a real window .show()
    # without hitting that unrelated environment bug.
    monkeypatch.setattr(step_cleanup, "_create_viewer", lambda parent: QLabel(parent))

    window = MainWindow()
    qtbot.addWidget(window)
    window.show()

    assert window.windowTitle() == "GromacsGUI"
    assert window.isVisible()

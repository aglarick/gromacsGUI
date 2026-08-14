from gromacs_gui.main_window import MainWindow


def test_main_window_creates_and_shows(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()

    assert window.windowTitle() == "GromacsGUI"
    assert window.isVisible()

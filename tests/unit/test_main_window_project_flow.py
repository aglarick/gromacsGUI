from __future__ import annotations

from gromacs_gui.core.project import Project
from gromacs_gui.main_window import MainWindow
from gromacs_gui.ui.wizard.wizard_window import WizardWindow


def test_open_project_flow_creates_new_project_and_swaps_to_wizard(qtbot, tmp_path, monkeypatch):
    window = MainWindow()
    qtbot.addWidget(window)
    monkeypatch.setattr(window, "_ensure_gmx_configured", lambda: {})
    project_dir = tmp_path / "myproj"
    monkeypatch.setattr(
        "gromacs_gui.main_window.QFileDialog.getExistingDirectory",
        lambda *args, **kwargs: str(project_dir),
    )

    window._on_open_project_clicked()

    assert isinstance(window.centralWidget(), WizardWindow)
    assert (project_dir / "project.json").is_file()


def test_open_project_flow_reopens_existing_project(qtbot, tmp_path, monkeypatch):
    project_dir = tmp_path / "myproj"
    Project.create(project_dir).record_step_finished("structure", output_files=[])

    window = MainWindow()
    qtbot.addWidget(window)
    monkeypatch.setattr(window, "_ensure_gmx_configured", lambda: {})
    monkeypatch.setattr(
        "gromacs_gui.main_window.QFileDialog.getExistingDirectory",
        lambda *args, **kwargs: str(project_dir),
    )

    window._on_open_project_clicked()

    wizard = window.centralWidget()
    assert isinstance(wizard, WizardWindow)
    assert wizard.project.step_record("structure").state.value == "done"


def test_cancelling_the_folder_picker_keeps_welcome_page(qtbot, tmp_path, monkeypatch):
    window = MainWindow()
    qtbot.addWidget(window)
    monkeypatch.setattr(window, "_ensure_gmx_configured", lambda: {})
    monkeypatch.setattr(
        "gromacs_gui.main_window.QFileDialog.getExistingDirectory", lambda *a, **k: ""
    )

    window._on_open_project_clicked()

    assert not isinstance(window.centralWidget(), WizardWindow)

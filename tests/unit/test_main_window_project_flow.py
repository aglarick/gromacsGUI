from __future__ import annotations

from gromacs_gui.core.project import Project
from gromacs_gui.main_window import MainWindow
from gromacs_gui.ui.wizard.wizard_window import WizardWindow


def test_central_widget_is_always_a_wizard_window(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)

    assert isinstance(window.centralWidget(), WizardWindow)
    assert window.centralWidget().project is None


def test_request_project_creates_a_new_project(qtbot, tmp_path, monkeypatch):
    window = MainWindow()
    qtbot.addWidget(window)
    monkeypatch.setattr(window, "_ensure_gmx_configured", lambda: {})
    project_dir = tmp_path / "myproj"
    monkeypatch.setattr(
        "gromacs_gui.main_window.QFileDialog.getExistingDirectory",
        lambda *args, **kwargs: str(project_dir),
    )

    result = window._request_project()

    assert result is not None
    project, env = result
    assert isinstance(project, Project)
    assert env == {}
    assert (project_dir / "project.json").is_file()


def test_request_project_reopens_an_existing_project(qtbot, tmp_path, monkeypatch):
    project_dir = tmp_path / "myproj"
    Project.create(project_dir).record_step_finished("structure", output_files=[])

    window = MainWindow()
    qtbot.addWidget(window)
    monkeypatch.setattr(window, "_ensure_gmx_configured", lambda: {})
    monkeypatch.setattr(
        "gromacs_gui.main_window.QFileDialog.getExistingDirectory",
        lambda *args, **kwargs: str(project_dir),
    )

    project, _env = window._request_project()

    assert project.step_record("structure").state.value == "done"


def test_request_project_returns_none_when_folder_picker_is_cancelled(qtbot, monkeypatch):
    window = MainWindow()
    qtbot.addWidget(window)
    monkeypatch.setattr(window, "_ensure_gmx_configured", lambda: {})
    monkeypatch.setattr(
        "gromacs_gui.main_window.QFileDialog.getExistingDirectory", lambda *a, **k: ""
    )

    assert window._request_project() is None


def test_request_project_returns_none_when_gmx_env_unresolved(qtbot, monkeypatch):
    window = MainWindow()
    qtbot.addWidget(window)
    monkeypatch.setattr(window, "_ensure_gmx_configured", lambda: None)

    assert window._request_project() is None

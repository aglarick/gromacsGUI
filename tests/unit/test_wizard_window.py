from __future__ import annotations

from PySide6.QtCore import Qt

from gromacs_gui.core.project import Project
from gromacs_gui.ui.wizard.wizard_window import WizardWindow


def _is_enabled(list_widget, row):
    return bool(list_widget.item(row).flags() & Qt.ItemFlag.ItemIsEnabled)


def test_cleanup_row_is_always_enabled(qtbot, tmp_path):
    project = Project.create(tmp_path / "proj")
    wizard = WizardWindow(project, gmx_env={})
    qtbot.addWidget(wizard)

    assert _is_enabled(wizard._sidebar, 0)  # 0. Cleanup — never gated


def test_only_first_pipeline_row_enabled_for_a_fresh_project(qtbot, tmp_path):
    project = Project.create(tmp_path / "proj")
    wizard = WizardWindow(project, gmx_env={})
    qtbot.addWidget(wizard)

    assert _is_enabled(wizard._sidebar, 1)  # structure
    assert not _is_enabled(wizard._sidebar, 2)  # box


def test_finishing_a_step_enables_the_next_row(qtbot, tmp_path):
    project = Project.create(tmp_path / "proj")
    wizard = WizardWindow(project, gmx_env={})
    qtbot.addWidget(wizard)

    project.record_step_finished("structure", output_files=[])

    assert _is_enabled(wizard._sidebar, 2)  # box now ready


def test_analysis_row_reflects_files_actually_on_disk(qtbot, tmp_path):
    project_root = tmp_path / "proj"
    project = Project.create(project_root)
    wizard = WizardWindow(project, gmx_env={})
    qtbot.addWidget(wizard)

    assert "Energy analysis (.edr found): no" in wizard._analysis_page._label.text()

    (project_root / "run.edr").write_bytes(b"\x00")
    project.record_step_finished("structure", output_files=[])  # triggers state_changed -> refresh

    assert "Energy analysis (.edr found): yes" in wizard._analysis_page._label.text()

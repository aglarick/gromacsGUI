from __future__ import annotations

from PySide6.QtCore import Qt

from gromacs_gui.core.project import Project
from gromacs_gui.ui.wizard.wizard_window import WizardWindow


def _is_enabled(item) -> bool:
    return bool(item.flags() & Qt.ItemFlag.ItemIsEnabled)


def _make_request_project(project: Project, gmx_env: dict | None = None):
    """A fake request_project callback that always succeeds with the given
    project, recording how many times it was called.
    """
    calls = []

    def request_project():
        calls.append(1)
        return project, gmx_env or {}

    request_project.calls = calls
    return request_project


def test_cleanup_is_always_present_and_enabled_without_a_project(qtbot):
    wizard = WizardWindow(request_project=lambda: None)
    qtbot.addWidget(wizard)

    tools_item = wizard._sidebar.topLevelItem(0)
    cleanup_item = tools_item.child(0)
    assert cleanup_item.text(0) == "Cleanup"
    assert _is_enabled(cleanup_item)
    assert wizard.project is None


def test_clicking_molecular_dynamics_without_a_project_requests_one(qtbot):
    project_holder = {}

    def request_project():
        project_holder["called"] = True
        return None  # user cancels

    wizard = WizardWindow(request_project=request_project)
    qtbot.addWidget(wizard)

    wizard._on_item_clicked(wizard._md_item, 0)

    assert project_holder.get("called") is True
    assert wizard.project is None
    assert "structure" not in wizard._step_items


def test_clicking_molecular_dynamics_with_a_project_just_navigates(qtbot, tmp_path):
    project = Project.create(tmp_path / "proj")
    request_project = _make_request_project(project)
    wizard = WizardWindow(request_project=request_project)
    qtbot.addWidget(wizard)
    wizard._on_item_clicked(wizard._md_item, 0)
    assert len(request_project.calls) == 1

    wizard._on_item_clicked(wizard._md_item, 0)

    assert len(request_project.calls) == 1  # not called again


def test_double_clicking_molecular_dynamics_always_requests_a_project(qtbot, tmp_path):
    project = Project.create(tmp_path / "proj")
    request_project = _make_request_project(project)
    wizard = WizardWindow(request_project=request_project)
    qtbot.addWidget(wizard)
    wizard._on_item_clicked(wizard._md_item, 0)
    assert len(request_project.calls) == 1

    wizard._on_item_double_clicked(wizard._md_item, 0)

    assert len(request_project.calls) == 2


def test_only_first_pipeline_step_enabled_for_a_fresh_project(qtbot, tmp_path):
    project = Project.create(tmp_path / "proj")
    wizard = WizardWindow(request_project=_make_request_project(project))
    qtbot.addWidget(wizard)

    wizard._on_item_clicked(wizard._md_item, 0)

    assert _is_enabled(wizard._step_items["structure"])
    assert not _is_enabled(wizard._step_items["box"])


def test_finishing_a_step_enables_the_next_one(qtbot, tmp_path):
    project = Project.create(tmp_path / "proj")
    wizard = WizardWindow(request_project=_make_request_project(project))
    qtbot.addWidget(wizard)
    wizard._on_item_clicked(wizard._md_item, 0)

    project.record_step_finished("structure", output_files=[])

    assert _is_enabled(wizard._step_items["box"])


def test_analysis_preview_disabled_until_a_project_exists(qtbot):
    wizard = WizardWindow(request_project=lambda: None)
    qtbot.addWidget(wizard)

    assert not _is_enabled(wizard._analysis_preview_item)


def test_analysis_reflects_files_actually_on_disk(qtbot, tmp_path):
    project_root = tmp_path / "proj"
    project = Project.create(project_root)
    wizard = WizardWindow(request_project=_make_request_project(project))
    qtbot.addWidget(wizard)
    wizard._on_item_clicked(wizard._md_item, 0)

    assert _is_enabled(wizard._analysis_preview_item)
    assert "Energy analysis (.edr found): no" in wizard._analysis_page._label.text()

    (project_root / "run.edr").write_bytes(b"\x00")
    project.record_step_finished("structure", output_files=[])  # triggers state_changed -> refresh

    assert "Energy analysis (.edr found): yes" in wizard._analysis_page._label.text()


def test_switching_projects_rebuilds_step_children(qtbot, tmp_path):
    project_a = Project.create(tmp_path / "proj_a")
    project_a.record_step_finished("structure", output_files=[])
    project_b = Project.create(tmp_path / "proj_b")

    calls = iter([project_a, project_b])
    wizard = WizardWindow(request_project=lambda: (next(calls), {}))
    qtbot.addWidget(wizard)

    wizard._on_item_clicked(wizard._md_item, 0)
    assert wizard.project is project_a
    assert _is_enabled(wizard._step_items["box"])  # structure already done for project_a

    wizard._on_item_double_clicked(wizard._md_item, 0)

    assert wizard.project is project_b
    assert not _is_enabled(wizard._step_items["box"])  # fresh project, not done yet

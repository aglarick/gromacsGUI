from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QStackedWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from gromacs_gui.core.capabilities import Capability, detect_capabilities
from gromacs_gui.core.pipeline import is_step_ready
from gromacs_gui.core.project import Project
from gromacs_gui.core.step_state import STEP_ORDER
from gromacs_gui.ui.wizard.step_base import StepBase
from gromacs_gui.ui.wizard.steps.step_box import StepBoxWidget
from gromacs_gui.ui.wizard.steps.step_cleanup import CleanupToolWidget
from gromacs_gui.ui.wizard.steps.step_ions import StepIonsWidget
from gromacs_gui.ui.wizard.steps.step_solvate import StepSolvateWidget
from gromacs_gui.ui.wizard.steps.step_structure import StepStructureWidget

_TOOLS_LABEL = "Tools"
_CLEANUP_LABEL = "Cleanup"
_MD_LABEL = "Molecular dynamics"
_ANALYSIS_LABEL = "Analysis"
_ANALYSIS_PREVIEW_LABEL = "Preview"

_STEP_LABELS = {
    "structure": "1. Structure",
    "box": "2. Box",
    "solvate": "3. Solvate",
    "ions": "4. Ions",
    "em": "5. Minimization",
    "nvt": "6. NVT",
    "npt": "7. NPT",
    "production": "8. Production",
}

# em/nvt/npt/production land in later milestones; ions is the last one built so far.
_STEP_WIDGET_CLASSES = {
    "structure": StepStructureWidget,
    "box": StepBoxWidget,
    "solvate": StepSolvateWidget,
    "ions": StepIonsWidget,
}

RequestProject = Callable[[], "tuple[Project, dict[str, str]] | None"]


class _NotBuiltYetPage(QWidget):
    def __init__(self, step_name: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        label = QLabel(f"'{step_name}' isn't built yet — coming in a later milestone.", self)
        label.setWordWrap(True)
        layout = QVBoxLayout(self)
        layout.addWidget(label)
        layout.addStretch(1)


class _InfoPage(QWidget):
    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        label = QLabel(text, self)
        label.setWordWrap(True)
        layout = QVBoxLayout(self)
        layout.addWidget(label)
        layout.addStretch(1)


class _AnalysisPreviewPage(QWidget):
    """Shows what analyses look computable purely from what's on disk right
    now, independent of Project's own manifest. Analysis itself isn't
    implemented yet; this validates the detection mechanism it'll run on.
    """

    def __init__(self, project: Project, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.project = project
        self._label = QLabel(self)
        self._label.setWordWrap(True)
        layout = QVBoxLayout(self)
        layout.addWidget(self._label)
        layout.addStretch(1)
        self.refresh()

    def refresh(self) -> None:
        caps = detect_capabilities(self.project.root)
        trajectory_line = "not available yet"
        if Capability.TRAJECTORY_MULTI_FRAME in caps:
            trajectory_line = "time-averaged (.trr/.xtc found)"
        elif Capability.TRAJECTORY_SINGLE_FRAME in caps:
            trajectory_line = "single-frame only (.gro found, no trajectory yet)"

        self._label.setText(
            "Analysis isn't built yet (a later milestone). Based on what's actually "
            "in this project folder right now:\n\n"
            f"- Structure available: {'yes' if Capability.STRUCTURE in caps else 'no'}\n"
            f"- Energy analysis (.edr found): {'yes' if Capability.ENERGY in caps else 'no'}\n"
            f"- Trajectory analysis: {trajectory_line}"
        )


class WizardWindow(QWidget):
    """Tree-shaped sidebar: "Tools" (standalone utilities, no project
    needed), "Molecular dynamics" (the numbered simulation steps, gated
    behind picking a project folder), and "Analysis" (future analysis
    tools). Clicking "Molecular dynamics" the first time - or double-
    clicking it any time - asks for a project folder via request_project;
    its step children only exist once a project has been chosen.
    """

    def __init__(self, request_project: RequestProject, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._request_project = request_project
        self.project: Project | None = None
        self.gmx_env: dict[str, str] = {}
        self._step_items: dict[str, QTreeWidgetItem] = {}
        self._page_for_item: dict[int, QWidget] = {}
        self._analysis_page: _AnalysisPreviewPage | None = None

        self._sidebar = QTreeWidget(self)
        self._sidebar.setFixedWidth(220)
        self._sidebar.setHeaderHidden(True)
        self._sidebar.setExpandsOnDoubleClick(False)
        self._stack = QStackedWidget(self)

        tools_item = QTreeWidgetItem([_TOOLS_LABEL])
        self._sidebar.addTopLevelItem(tools_item)
        cleanup_item = QTreeWidgetItem([_CLEANUP_LABEL])
        tools_item.addChild(cleanup_item)
        self._add_page(cleanup_item, CleanupToolWidget(None, {}, self))

        self._md_item = QTreeWidgetItem([_MD_LABEL])
        self._sidebar.addTopLevelItem(self._md_item)
        self._add_page(
            self._md_item,
            _InfoPage("Click here to choose a project folder and start.", self),
        )

        analysis_item = QTreeWidgetItem([_ANALYSIS_LABEL])
        self._sidebar.addTopLevelItem(analysis_item)
        self._analysis_preview_item = QTreeWidgetItem([_ANALYSIS_PREVIEW_LABEL])
        analysis_item.addChild(self._analysis_preview_item)
        self._add_page(
            self._analysis_preview_item,
            _InfoPage("Select a project via 'Molecular dynamics' first.", self),
        )
        self._set_item_enabled(self._analysis_preview_item, False)

        self._sidebar.expandAll()
        self._sidebar.itemClicked.connect(self._on_item_clicked)
        self._sidebar.itemDoubleClicked.connect(self._on_item_double_clicked)

        layout = QHBoxLayout(self)
        layout.addWidget(self._sidebar)
        layout.addWidget(self._stack, 1)

        self._sidebar.setCurrentItem(cleanup_item)
        self._show_item_page(cleanup_item)

    # --- page bookkeeping ---
    def _add_page(self, item: QTreeWidgetItem, page: QWidget) -> None:
        self._stack.addWidget(page)
        self._page_for_item[id(item)] = page

    def _replace_page(self, item: QTreeWidgetItem, new_page: QWidget) -> None:
        old_page = self._page_for_item.pop(id(item), None)
        if old_page is not None:
            self._stack.removeWidget(old_page)
            old_page.deleteLater()
        self._add_page(item, new_page)

    def _show_item_page(self, item: QTreeWidgetItem) -> None:
        page = self._page_for_item.get(id(item))
        if page is not None:
            self._stack.setCurrentWidget(page)

    @staticmethod
    def _set_item_enabled(item: QTreeWidgetItem, enabled: bool) -> None:
        flags = item.flags()
        if enabled:
            item.setFlags(flags | Qt.ItemFlag.ItemIsEnabled)
        else:
            item.setFlags(flags & ~Qt.ItemFlag.ItemIsEnabled)

    # --- navigation ---
    def _on_item_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        if item is self._md_item:
            if self.project is None:
                self._prompt_for_project()
            else:
                self._show_item_page(item)
            return
        self._show_item_page(item)

    def _on_item_double_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        if item is self._md_item:
            self._prompt_for_project()

    def _on_step_advance_requested(self, step_name: str) -> None:
        item = self._step_items.get(step_name)
        if item is None:
            return
        self._sidebar.setCurrentItem(item)
        self._show_item_page(item)

    def _prompt_for_project(self) -> None:
        result = self._request_project()
        if result is None:
            return
        project, gmx_env = result
        self._set_project(project, gmx_env)

    # --- project (re)binding ---
    def _set_project(self, project: Project, gmx_env: dict[str, str]) -> None:
        if self.project is not None:
            try:
                self.project.state_changed.disconnect(self.refresh)
            except (RuntimeError, TypeError):
                pass

        self.project = project
        self.gmx_env = gmx_env

        for item in self._step_items.values():
            self._md_item.removeChild(item)
            page = self._page_for_item.pop(id(item), None)
            if page is not None:
                self._stack.removeWidget(page)
                page.deleteLater()
        self._step_items.clear()

        for step_name in STEP_ORDER:
            item = QTreeWidgetItem([_STEP_LABELS[step_name]])
            self._md_item.addChild(item)
            widget_cls = _STEP_WIDGET_CLASSES.get(step_name)
            page = (
                widget_cls(project, gmx_env, self)
                if widget_cls is not None
                else _NotBuiltYetPage(step_name, self)
            )
            if isinstance(page, StepBase):
                page.advance_requested.connect(self._on_step_advance_requested)
            self._add_page(item, page)
            self._step_items[step_name] = item

        self._replace_page(self._md_item, _InfoPage(f"Project: {project.root}", self))

        self._analysis_page = _AnalysisPreviewPage(project, self)
        self._replace_page(self._analysis_preview_item, self._analysis_page)
        self._set_item_enabled(self._analysis_preview_item, True)

        self.project.state_changed.connect(self.refresh)
        self._sidebar.expandAll()
        self.refresh()

        structure_item = self._step_items["structure"]
        self._sidebar.setCurrentItem(structure_item)
        self._show_item_page(structure_item)

    def refresh(self) -> None:
        if self.project is None:
            return
        for step_name, item in self._step_items.items():
            self._set_item_enabled(item, is_step_ready(self.project, step_name))
        if self._analysis_page is not None:
            self._analysis_page.refresh()

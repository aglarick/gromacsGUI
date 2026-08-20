from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from gromacs_gui.core.capabilities import Capability, detect_capabilities
from gromacs_gui.core.pipeline import is_step_ready
from gromacs_gui.core.project import Project
from gromacs_gui.core.step_state import STEP_ORDER
from gromacs_gui.ui.wizard.steps.step_box import StepBoxWidget
from gromacs_gui.ui.wizard.steps.step_cleanup import CleanupToolWidget
from gromacs_gui.ui.wizard.steps.step_ions import StepIonsWidget
from gromacs_gui.ui.wizard.steps.step_solvate import StepSolvateWidget
from gromacs_gui.ui.wizard.steps.step_structure import StepStructureWidget

_CLEANUP_ROW_LABEL = "0. Cleanup"

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

# em/nvt/npt/production land in Milestones 6-8; ions is the last one built so far.
_STEP_WIDGET_CLASSES = {
    "structure": StepStructureWidget,
    "box": StepBoxWidget,
    "solvate": StepSolvateWidget,
    "ions": StepIonsWidget,
}

_ANALYSIS_ROW_LABEL = "Analysis (preview)"


class _NotBuiltYetPage(QWidget):
    def __init__(self, step_name: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        label = QLabel(f"'{step_name}' isn't built yet — coming in a later milestone.", self)
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
    """Left-hand sidebar of steps that enable progressively as the Project
    advances, with each step's page on the right. A project is a folder the
    user pointed the app at; opening one with prior progress re-enables
    whichever tabs its manifest says are ready.
    """

    def __init__(
        self,
        project: Project,
        gmx_env: dict[str, str],
        parent: QWidget | None = None,
        initial_row: int = 0,
    ) -> None:
        super().__init__(parent)
        self.project = project
        self.gmx_env = gmx_env

        self._sidebar = QListWidget(self)
        self._sidebar.setFixedWidth(200)
        self._stack = QStackedWidget(self)

        self._sidebar.addItem(QListWidgetItem(_CLEANUP_ROW_LABEL))
        self._stack.addWidget(CleanupToolWidget(project, gmx_env, self))
        self._step_row_start = 1  # row 0 is the always-enabled cleanup tool above

        for step_name in STEP_ORDER:
            self._sidebar.addItem(QListWidgetItem(_STEP_LABELS[step_name]))
            widget_cls = _STEP_WIDGET_CLASSES.get(step_name)
            page = (
                widget_cls(project, gmx_env, self)
                if widget_cls is not None
                else _NotBuiltYetPage(step_name, self)
            )
            self._stack.addWidget(page)

        self._sidebar.addItem(QListWidgetItem(_ANALYSIS_ROW_LABEL))
        self._analysis_page = _AnalysisPreviewPage(project, self)
        self._stack.addWidget(self._analysis_page)

        self._sidebar.currentRowChanged.connect(self._on_row_changed)

        layout = QHBoxLayout(self)
        layout.addWidget(self._sidebar)
        layout.addWidget(self._stack, 1)

        self.project.state_changed.connect(self.refresh)
        self.refresh()
        self._sidebar.setCurrentRow(initial_row)

    def refresh(self) -> None:
        for offset, step_name in enumerate(STEP_ORDER):
            item = self._sidebar.item(self._step_row_start + offset)
            self._set_row_enabled(item, is_step_ready(self.project, step_name))
        self._analysis_page.refresh()

    @staticmethod
    def _set_row_enabled(item: QListWidgetItem, enabled: bool) -> None:
        flags = item.flags()
        if enabled:
            item.setFlags(flags | Qt.ItemFlag.ItemIsEnabled)
        else:
            item.setFlags(flags & ~Qt.ItemFlag.ItemIsEnabled)

    def _on_row_changed(self, row: int) -> None:
        if row >= 0:
            self._stack.setCurrentIndex(row)

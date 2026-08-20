from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gromacs_gui.core.project import Project
from gromacs_gui.ui.wizard.steps.step_cleanup import CleanupToolWidget
from gromacs_gui.ui.wizard.wizard_window import WizardWindow
from gromacs_gui.utils.settings import (
    GmxEnvironmentError,
    Settings,
    find_gmx_binary,
    resolve_gmx_environment,
)

# Sidebar row 0 is "0. Cleanup" (always enabled), row 1 is the first entry
# of STEP_ORDER ("structure") - see WizardWindow._step_row_start.
_STRUCTURE_ROW = 1


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("GromacsGUI")
        self.resize(1000, 650)

        self.settings = Settings.load()
        self.project: Project | None = None
        self.gmx_env: dict[str, str] | None = None

        self.setCentralWidget(self._build_startup_page())

    def _build_startup_page(self) -> QWidget:
        """No project folder is needed to use the cleanup tool, so the app
        opens straight into it - a project is only requested once the user
        actually wants to move on to Structure (step 1).
        """
        page = QWidget(self)
        continue_button = QPushButton("Continue to Structure (Step 1) →", page)
        continue_button.clicked.connect(self._on_continue_to_structure_clicked)
        continue_row = QHBoxLayout()
        continue_row.addStretch(1)
        continue_row.addWidget(continue_button)

        layout = QVBoxLayout(page)
        layout.addWidget(QLabel("GromacsGUI", page))
        layout.addLayout(continue_row)
        layout.addWidget(CleanupToolWidget(None, {}, page), 1)
        return page

    def _on_continue_to_structure_clicked(self) -> None:
        env = self._ensure_gmx_configured()
        if env is None:
            return

        folder = QFileDialog.getExistingDirectory(
            self, "Select or create a project folder", str(Path.home())
        )
        if not folder:
            return

        root = Path(folder)
        has_manifest = (root / "project.json").is_file()
        try:
            project = Project.open(root) if has_manifest else Project.create(root)
        except OSError as exc:
            QMessageBox.critical(self, "Project error", str(exc))
            return

        self.project = project
        self.gmx_env = env
        self.setCentralWidget(WizardWindow(project, env, self, initial_row=_STRUCTURE_ROW))

    def _ensure_gmx_configured(self) -> dict[str, str] | None:
        if self.settings.gmxrc_path:
            try:
                return resolve_gmx_environment(self.settings.gmxrc_path)
            except GmxEnvironmentError as exc:
                QMessageBox.warning(self, "GROMACS environment", str(exc))
                self.settings.gmxrc_path = None

        # Fall back to the process's own environment, e.g. if the GUI was launched
        # from a terminal that had already sourced GMXRC.
        env = dict(os.environ)
        if find_gmx_binary(env):
            return env

        path, _ = QFileDialog.getOpenFileName(
            self, "Select GMXRC (in your GROMACS install's bin/ directory)", str(Path.home())
        )
        if not path:
            return None
        try:
            env = resolve_gmx_environment(path)
        except GmxEnvironmentError as exc:
            QMessageBox.critical(self, "GROMACS environment", str(exc))
            return None
        self.settings.gmxrc_path = path
        self.settings.save()
        return env

from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QMainWindow, QMessageBox

from gromacs_gui.core.project import Project
from gromacs_gui.ui.wizard.wizard_window import WizardWindow
from gromacs_gui.utils.settings import (
    GmxEnvironmentError,
    Settings,
    find_gmx_binary,
    resolve_gmx_environment,
)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("GromacsGUI")
        self.resize(1000, 650)

        self.settings = Settings.load()
        self.setCentralWidget(WizardWindow(self._request_project, self))

    def _request_project(self) -> tuple[Project, dict[str, str]] | None:
        """Passed into WizardWindow, which calls this when the user clicks
        (or double-clicks, to switch projects) "Molecular dynamics" -
        resolves the GROMACS environment, asks for a project folder, and
        opens/creates the project. Returns None if the user cancels at any
        point, or if the project folder itself can't be opened.
        """
        env = self._ensure_gmx_configured()
        if env is None:
            return None

        folder = QFileDialog.getExistingDirectory(
            self, "Select or create a project folder", str(Path.home())
        )
        if not folder:
            return None

        root = Path(folder)
        has_manifest = (root / "project.json").is_file()
        try:
            project = Project.open(root) if has_manifest else Project.create(root)
        except OSError as exc:
            QMessageBox.critical(self, "Project error", str(exc))
            return None

        return project, env

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

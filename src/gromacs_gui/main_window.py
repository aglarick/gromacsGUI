from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

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
        self.project: Project | None = None
        self.gmx_env: dict[str, str] | None = None

        self.setCentralWidget(self._build_welcome_page())

    def _build_welcome_page(self) -> QWidget:
        page = QWidget(self)
        title = QLabel("GromacsGUI", page)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle = QLabel(
            "Choose an empty folder to start a new simulation project, or an\n"
            "existing project folder to resume it.",
            page,
        )
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        open_button = QPushButton("Open or Create Project Folder…", page)
        open_button.clicked.connect(self._on_open_project_clicked)

        layout = QVBoxLayout(page)
        layout.addStretch(1)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(open_button, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addStretch(1)
        return page

    def _on_open_project_clicked(self) -> None:
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
        self.setCentralWidget(WizardWindow(project, env, self))

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

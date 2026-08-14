from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gromacs_gui.gmx.runner import GmxProcessRunner
from gromacs_gui.ui.widgets.log_console import LogConsole
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
        self.resize(900, 600)

        self.settings = Settings.load()
        self.runner = GmxProcessRunner(self)
        self.runner.output_line.connect(self._on_output_line)
        self.runner.finished.connect(self._on_finished)
        self.runner.cancelled.connect(self._on_cancelled)
        self.runner.error_occurred.connect(self._on_error)

        self.log_console = LogConsole(self)
        self.run_button = QPushButton("Run gmx --version")
        self.run_button.clicked.connect(self._on_run_version_clicked)

        button_row = QHBoxLayout()
        button_row.addWidget(self.run_button)
        button_row.addStretch(1)

        central = QWidget(self)
        layout = QVBoxLayout(central)
        layout.addLayout(button_row)
        layout.addWidget(self.log_console)
        self.setCentralWidget(central)

    def _on_run_version_clicked(self) -> None:
        if self.runner.is_running:
            return
        env = self._ensure_gmx_configured()
        if env is None:
            return
        gmx_path = find_gmx_binary(env) or "gmx"
        self.log_console.clear_log()
        self.run_button.setEnabled(False)
        self.runner.start(gmx_path, ["--version"], env=env)

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

    def _on_output_line(self, text: str, stream: str) -> None:
        self.log_console.append_line(text, stream)

    def _on_finished(self, exit_code: int) -> None:
        self.log_console.append_line(f"[gmx exited with code {exit_code}]", "info")
        self.run_button.setEnabled(True)

    def _on_cancelled(self) -> None:
        self.log_console.append_line("[cancelled]", "info")
        self.run_button.setEnabled(True)

    def _on_error(self, message: str) -> None:
        self.log_console.append_line(f"[error] {message}", "stderr")
        self.run_button.setEnabled(True)

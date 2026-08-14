from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtWidgets import QFormLayout, QMessageBox, QPushButton, QVBoxLayout, QWidget

from gromacs_gui.core.project import Project
from gromacs_gui.gmx.runner import GmxProcessRunner
from gromacs_gui.ui.widgets.log_console import LogConsole
from gromacs_gui.utils.settings import find_gmx_binary


@dataclass
class StepCommand:
    args: list[str]
    stdin: str | None = None


class StepBase(QWidget):
    """Common shell for one wizard step: a step-specific form (subclasses add
    widgets to `self.form_layout`), a Run button, and a shared log console
    wired to run a *sequence* of gmx commands (some steps need more than one,
    e.g. ions needs grompp then genion), recording progress on the Project.
    """

    step_name: str = ""  # must match an entry in core.step_state.STEP_ORDER

    def __init__(
        self, project: Project, gmx_env: dict[str, str], parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.project = project
        self.gmx_env = gmx_env

        self.form_layout = QFormLayout()
        self.run_button = QPushButton("Run", self)
        self.run_button.clicked.connect(self._on_run_clicked)
        self.log_console = LogConsole(self)

        layout = QVBoxLayout(self)
        layout.addLayout(self.form_layout)
        layout.addWidget(self.run_button)
        layout.addWidget(self.log_console, 1)

        self._pending_commands: list[StepCommand] = []
        self._runner: GmxProcessRunner | None = None

    # --- subclasses implement these ---
    def is_valid(self) -> bool:
        raise NotImplementedError

    def build_commands(self) -> list[StepCommand]:
        raise NotImplementedError

    def output_files(self) -> list[str]:
        raise NotImplementedError

    # --- shared run orchestration ---
    def _on_run_clicked(self) -> None:
        if self._runner is not None and self._runner.is_running:
            return
        if not self.is_valid():
            QMessageBox.warning(
                self, "Missing input", "Please complete the required fields before running."
            )
            return

        self._pending_commands = list(self.build_commands())
        if not self._pending_commands:
            return

        self.log_console.clear_log()
        self.run_button.setEnabled(False)
        self.project.record_step_started(self.step_name)
        self._run_next_command()

    def _run_next_command(self) -> None:
        command = self._pending_commands.pop(0)
        gmx_path = find_gmx_binary(self.gmx_env) or "gmx"

        runner = GmxProcessRunner(self)
        runner.output_line.connect(self._on_output_line)
        runner.finished.connect(self._on_command_finished)
        runner.error_occurred.connect(self._on_error)
        self._runner = runner

        runner.start(gmx_path, command.args, cwd=str(self.project.root), env=self.gmx_env)
        if command.stdin is not None:
            runner.write_stdin(command.stdin)
            runner.close_stdin()

    def _on_output_line(self, text: str, stream: str) -> None:
        self.log_console.append_line(text, stream)

    def _on_command_finished(self, exit_code: int) -> None:
        if exit_code != 0:
            self._fail(f"gmx exited with code {exit_code}")
            return

        if self._pending_commands:
            self._run_next_command()
            return

        self.run_button.setEnabled(True)
        self.project.record_step_finished(self.step_name, output_files=self.output_files())
        self.log_console.append_line("[step completed successfully]", "info")

    def _on_error(self, message: str) -> None:
        self._fail(message)

    def _fail(self, message: str) -> None:
        self.run_button.setEnabled(True)
        self.project.record_step_failed(self.step_name, message)
        self.log_console.append_line(f"[error] {message}", "stderr")
        self._pending_commands = []

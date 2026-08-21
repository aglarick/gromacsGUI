from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFormLayout, QLabel, QMessageBox, QPushButton, QVBoxLayout, QWidget

from gromacs_gui.core.project import Project
from gromacs_gui.gmx.runner import GmxProcessRunner
from gromacs_gui.ui.widgets.log_console import LogConsole
from gromacs_gui.utils.settings import find_gmx_binary


@dataclass
class StepCommand:
    args: list[str]
    stdin: str | None = None


class StepBase(QWidget):
    """Common shell for one wizard step: a description of what the step does,
    a step-specific form (subclasses add widgets to `self.form_layout`), a Run
    button, and a shared log console wired to run a *sequence* of gmx commands
    (some steps need more than one, e.g. ions needs grompp then genion),
    recording progress on the Project. A step with no gmx command to run at
    all (e.g. registering files the user already prepared elsewhere) can
    return an empty list from build_commands() to finish immediately.
    """

    step_name: str = ""  # must match an entry in core.step_state.STEP_ORDER
    DESCRIPTION: str = ""  # plain-language explanation shown above the form
    RUN_BUTTON_LABEL: str = "Run"

    # Emitted with a step_name to ask the wizard to switch to it - e.g.
    # Structure's "Test system" flow asking to jump to Box once accepted.
    advance_requested = Signal(str)

    def __init__(
        self, project: Project, gmx_env: dict[str, str], parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.project = project
        self.gmx_env = gmx_env

        self.form_layout = QFormLayout()
        self.run_button = QPushButton(self.RUN_BUTTON_LABEL, self)
        self.run_button.clicked.connect(self._on_run_clicked)
        self.log_console = LogConsole(self)

        layout = QVBoxLayout(self)
        if self.DESCRIPTION:
            description_label = QLabel(self.DESCRIPTION, self)
            description_label.setWordWrap(True)
            description_label.setStyleSheet("color: #555;")
            layout.addWidget(description_label)
        layout.addLayout(self.form_layout)
        layout.addWidget(self.run_button)
        layout.addWidget(self.log_console, 1)

        self._pending_commands: list[StepCommand] = []
        self._runner: GmxProcessRunner | None = None

    # --- subclasses implement these ---
    def is_valid(self) -> bool:
        raise NotImplementedError

    def build_commands(self) -> list[StepCommand]:
        """Return the gmx command(s) to run, in order. May also perform
        non-gmx side effects (e.g. copying user-supplied files into the
        project) and return an empty list if there's nothing left to run.
        """
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

        self.log_console.clear_log()
        self.run_button.setEnabled(False)
        self.project.record_step_started(self.step_name)

        try:
            self._pending_commands = list(self.build_commands())
        except Exception as exc:  # surfaced in the log/manifest, not a crash
            self._fail(str(exc))
            return

        if not self._pending_commands:
            self._finish_successfully()
            return

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

        self._finish_successfully()

    def _on_error(self, message: str) -> None:
        self._fail(message)

    def on_all_commands_finished(self) -> None:
        """Optional hook for subclasses that need pure-Python post-processing
        after every gmx command in the sequence has succeeded but before the
        step is recorded as done (e.g. merging several generated topology
        files into one combined topol.top). May raise; doing so fails the
        step the same way a failed gmx command would.
        """

    def verify_before_finish(self) -> None:
        """Optional hook: an extra synchronous check that runs after
        on_all_commands_finished() succeeds but before the step is recorded
        as done - e.g. Structure's grompp consistency check, which also owns
        deciding whether to prompt the user to advance. Raise to fail the
        step the same way a failed gmx command would. Default: no-op.
        """

    def _finish_successfully(self) -> None:
        self.run_button.setEnabled(True)
        try:
            self.on_all_commands_finished()
            self.verify_before_finish()
        except Exception as exc:
            self._fail(str(exc))
            return
        self.project.record_step_finished(self.step_name, output_files=self.output_files())
        self.log_console.append_line("[step completed successfully]", "info")

    def _fail(self, message: str) -> None:
        self.run_button.setEnabled(True)
        self.project.record_step_failed(self.step_name, message)
        self.log_console.append_line(f"[error] {message}", "stderr")
        self._pending_commands = []

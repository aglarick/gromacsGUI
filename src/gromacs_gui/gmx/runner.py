from __future__ import annotations

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, Signal


class GmxProcessRunner(QObject):
    """Runs a single `gmx` subcommand via QProcess, streaming its output.

    QProcess integrates with Qt's event loop, so stdout/stderr streaming and
    cancellation don't require managing threads manually.
    """

    output_line = Signal(str, str)  # (text, stream) where stream is "stdout" or "stderr"
    finished = Signal(int)  # exit code
    cancelled = Signal()
    error_occurred = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._process: QProcess | None = None
        self._was_cancelled = False

    @property
    def is_running(self) -> bool:
        if self._process is None:
            return False
        return self._process.state() != QProcess.ProcessState.NotRunning

    def start(
        self,
        program: str,
        arguments: list[str],
        cwd: str | None = None,
        env: dict[str, str] | None = None,
    ) -> None:
        if self.is_running:
            raise RuntimeError("A gmx process is already running")

        self._was_cancelled = False
        process = QProcess(self)
        if cwd:
            process.setWorkingDirectory(cwd)
        if env is not None:
            qenv = QProcessEnvironment()
            for key, value in env.items():
                qenv.insert(key, value)
            process.setProcessEnvironment(qenv)

        process.readyReadStandardOutput.connect(lambda: self._emit_output("stdout"))
        process.readyReadStandardError.connect(lambda: self._emit_output("stderr"))
        process.finished.connect(self._on_finished)
        process.errorOccurred.connect(self._on_error)

        self._process = process
        process.start(program, arguments)

    def write_stdin(self, text: str) -> None:
        if self._process is None:
            raise RuntimeError("No process is running")
        self._process.write(text.encode())

    def close_stdin(self) -> None:
        if self._process is not None:
            self._process.closeWriteChannel()

    def cancel(self, grace_period_ms: int = 3000) -> None:
        if self._process is None:
            return
        self._was_cancelled = True
        self._process.terminate()
        if not self._process.waitForFinished(grace_period_ms):
            self._process.kill()

    def _emit_output(self, stream: str) -> None:
        if self._process is None:
            return
        data = (
            self._process.readAllStandardOutput()
            if stream == "stdout"
            else self._process.readAllStandardError()
        )
        text = bytes(data).decode(errors="replace")
        for line in text.splitlines():
            self.output_line.emit(line, stream)

    def _on_finished(self, exit_code: int, _exit_status: QProcess.ExitStatus) -> None:
        self._process = None
        if self._was_cancelled:
            self.cancelled.emit()
        else:
            self.finished.emit(exit_code)

    def _on_error(self, error: QProcess.ProcessError) -> None:
        process = self._process
        if process is None:
            return
        if error == QProcess.ProcessError.FailedToStart:
            self._process = None
        self.error_occurred.emit(process.errorString())

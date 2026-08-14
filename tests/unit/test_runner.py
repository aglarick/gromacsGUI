from __future__ import annotations

from gromacs_gui.gmx.runner import GmxProcessRunner


def test_runner_streams_stdout_and_stderr_and_finishes(qtbot):
    runner = GmxProcessRunner()
    lines: list[tuple[str, str]] = []
    runner.output_line.connect(lambda text, stream: lines.append((text, stream)))

    with qtbot.waitSignal(runner.finished, timeout=5000) as blocker:
        runner.start("bash", ["-c", "echo out-line; echo err-line 1>&2"])

    assert blocker.args[0] == 0
    assert ("out-line", "stdout") in lines
    assert ("err-line", "stderr") in lines


def test_runner_cancel_stops_a_running_process(qtbot):
    runner = GmxProcessRunner()

    with qtbot.waitSignal(runner.cancelled, timeout=5000):
        runner.start("sleep", ["5"])
        runner.cancel()

    assert not runner.is_running


def test_runner_reports_error_for_missing_executable(qtbot):
    runner = GmxProcessRunner()

    with qtbot.waitSignal(runner.error_occurred, timeout=5000):
        runner.start("this-binary-does-not-exist", [])

    assert not runner.is_running

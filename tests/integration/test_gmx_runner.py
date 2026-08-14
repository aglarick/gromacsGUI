from __future__ import annotations

import pytest

from gromacs_gui.gmx.runner import GmxProcessRunner
from gromacs_gui.utils.settings import find_gmx_binary

pytestmark = pytest.mark.requires_gmx


def test_gmx_version_streams_output_and_finishes(qtbot, gmx_environment):
    runner = GmxProcessRunner()
    lines: list[tuple[str, str]] = []
    runner.output_line.connect(lambda text, stream: lines.append((text, stream)))

    gmx_path = find_gmx_binary(gmx_environment)
    assert gmx_path is not None

    with qtbot.waitSignal(runner.finished, timeout=15000) as blocker:
        runner.start(gmx_path, ["--version"], env=gmx_environment)

    exit_code = blocker.args[0]
    assert exit_code == 0
    combined_output = "\n".join(text for text, _ in lines)
    assert "GROMACS version" in combined_output

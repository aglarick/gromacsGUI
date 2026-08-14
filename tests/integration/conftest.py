from __future__ import annotations

import os
from pathlib import Path

import pytest

from gromacs_gui.utils.settings import (
    GmxEnvironmentError,
    find_gmx_binary,
    resolve_gmx_environment,
)

# Known-good location on the primary dev machine; override with
# GROMACS_GUI_TEST_GMXRC on other machines/CI.
_FALLBACK_GMXRC_CANDIDATES = [
    Path("/home/francisco/local/gromacs-2025.3/bin/GMXRC"),
]


@pytest.fixture(scope="session")
def gmx_environment() -> dict[str, str]:
    gmxrc = os.environ.get("GROMACS_GUI_TEST_GMXRC")
    candidates = [Path(gmxrc)] if gmxrc else _FALLBACK_GMXRC_CANDIDATES

    for candidate in candidates:
        if candidate.is_file():
            try:
                env = resolve_gmx_environment(candidate)
            except GmxEnvironmentError:
                continue
            if find_gmx_binary(env):
                return env

    if find_gmx_binary(dict(os.environ)):
        return dict(os.environ)

    pytest.skip("No GROMACS installation found (set GROMACS_GUI_TEST_GMXRC)")

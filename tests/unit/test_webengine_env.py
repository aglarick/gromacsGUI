from __future__ import annotations

import subprocess
from unittest.mock import patch

from gromacs_gui.utils.webengine_env import find_system_library_paths

_LDCONFIG_OUTPUT = """\
\tlibkrb5.so.3 (libc6,x86-64) => /usr/lib/x86_64-linux-gnu/libkrb5.so.3
\tlibgssapi_krb5.so.2 (libc6,x86-64) => /usr/lib/x86_64-linux-gnu/libgssapi_krb5.so.2
\tlibkrb5support.so.0 (libc6,x86-64) => /usr/lib/x86_64-linux-gnu/libkrb5support.so.0
"""


def _fake_run(*args, **kwargs):
    return subprocess.CompletedProcess(args, 0, stdout=_LDCONFIG_OUTPUT)


def test_finds_all_requested_sonames():
    with patch("subprocess.run", side_effect=_fake_run):
        paths = find_system_library_paths(["libkrb5.so.3", "libgssapi_krb5.so.2"])

    assert paths == [
        "/usr/lib/x86_64-linux-gnu/libkrb5.so.3",
        "/usr/lib/x86_64-linux-gnu/libgssapi_krb5.so.2",
    ]


def test_returns_none_when_a_soname_is_missing():
    with patch("subprocess.run", side_effect=_fake_run):
        paths = find_system_library_paths(["libkrb5.so.3", "libnope.so.99"])

    assert paths is None


def test_returns_none_when_ldconfig_is_unavailable():
    with patch("subprocess.run", side_effect=FileNotFoundError):
        paths = find_system_library_paths(["libkrb5.so.3"])

    assert paths is None

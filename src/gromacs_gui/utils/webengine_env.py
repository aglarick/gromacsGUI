"""Self-heals a specific conda/system Kerberos library conflict that
otherwise breaks importing PySide6.QtWebEngineWidgets: conda-forge's krb5
package here is newer than what this system's libgssapi_krb5 was built
against (missing the krb5_ser_context_init symbol), and conda's copy gets
resolved first regardless of LD_LIBRARY_PATH. Since LD_PRELOAD can only be
set before the interpreter starts, the fix is to re-exec the process once
with it set - but only when WebEngine actually fails to import and the
system's own copies of these libraries can be found; otherwise this is a
no-op, so machines without the conflict never pay for an extra restart.
"""

from __future__ import annotations

import os
import subprocess
import sys

_KRB5_SONAMES = [
    "libkrb5support.so.0",
    "libk5crypto.so.3",
    "libkrb5.so.3",
    "libgssapi_krb5.so.2",
]

_REEXEC_MARKER = "_GROMACS_GUI_KRB5_PRELOAD_DONE"


def find_system_library_paths(sonames: list[str]) -> list[str] | None:
    """Resolve each soname via ldconfig's cache, which reflects real
    system-installed libraries regardless of conda's environment overrides.
    Returns None if ldconfig is unavailable or any soname isn't found.
    """
    try:
        output = subprocess.run(
            ["ldconfig", "-p"], capture_output=True, text=True, check=True, timeout=5
        ).stdout
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None

    paths_by_soname: dict[str, str] = {}
    for line in output.splitlines():
        if "=>" not in line:
            continue
        left, path = line.split("=>", 1)
        # left looks like "\tlibfoo.so.1 (libc6,x86-64) " - the soname is
        # just its first whitespace-separated token, not everything before
        # the arrow.
        tokens = left.split()
        if not tokens:
            continue
        paths_by_soname.setdefault(tokens[0], path.strip())

    resolved = [paths_by_soname[name] for name in sonames if name in paths_by_soname]
    if len(resolved) != len(sonames):
        return None
    return resolved


def ensure_webengine_importable() -> None:
    """Call once at process startup, before constructing QApplication. If
    QtWebEngineWidgets already imports fine, or the system libraries needed
    to fix it can't be found, this does nothing - callers of
    QWebEngineView are expected to handle ImportError and fall back
    gracefully either way.

    The fix re-execs the process once. sys.argv alone can't reliably
    reproduce a `-m`/`-c` invocation (Python doesn't expose the original
    command line in a re-runnable form), so instead of trying to replay it,
    this always relaunches via `python -m gromacs_gui.app`, passing through
    any extra CLI args (e.g. Qt's own -style/-display) - that's the app's
    real entry point regardless of how the current process was started.
    """
    if os.environ.get(_REEXEC_MARKER):
        return

    try:
        import PySide6.QtWebEngineWidgets  # noqa: F401

        return
    except ImportError:
        pass

    paths = find_system_library_paths(_KRB5_SONAMES)
    if paths is None:
        return

    env = os.environ.copy()
    env["LD_PRELOAD"] = ":".join(paths)
    env[_REEXEC_MARKER] = "1"
    os.execve(
        sys.executable,
        [sys.executable, "-m", "gromacs_gui.app", *sys.argv[1:]],
        env,
    )

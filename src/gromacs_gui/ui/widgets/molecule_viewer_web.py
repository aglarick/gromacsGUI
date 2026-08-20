"""Embedded Mol* 3D viewer via QWebEngineView.

Preferred over MoleculeViewer3D (the matplotlib fallback) whenever it's
available: Mol* uses GPU instancing/impostor rendering built specifically
for very large macromolecular assemblies, so it doesn't need the aggressive
atom-count cap the matplotlib panel needs to avoid freezing. Requires
QtWebEngine to import successfully - see utils/webengine_env.py for the
conda/system Kerberos conflict that can block that on some machines.
Callers should catch ImportError and fall back to MoleculeViewer3D.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtWebEngineCore import QWebEnginePage
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QLabel, QStackedWidget, QVBoxLayout, QWidget

from gromacs_gui.gmx.structure_files import AtomPosition, format_atoms_as_pdb

_logger = logging.getLogger(__name__)

_WEB_ASSETS_DIR = Path(__file__).parent / "web_assets"

_HTML_SHELL = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<link rel="stylesheet" type="text/css" href="molstar.css">
<style>
  html, body, #app { width: 100%; height: 100%; margin: 0; padding: 0; background: #101010; }
</style>
</head>
<body>
<div id="app"></div>
<script src="molstar.js"></script>
<script>
  window.__gromacsGuiViewer = molstar.Viewer.create('app', {
      layoutIsExpanded: false,
      layoutShowControls: false,
      layoutShowSequence: false,
      layoutShowLog: false,
      layoutShowLeftPanel: false,
      viewportShowExpand: false,
      viewportShowSelectionMode: false,
  });

  window.__gromacsGuiSetPdb = function(pdbText) {
    window.__gromacsGuiViewer.then(function (viewer) {
      // Viewer itself has no clear() - the underlying plugin does, and it
      // returns a command/task, not necessarily a native Promise, so wrap
      // it to be safe before chaining the next load onto it.
      Promise.resolve(viewer.plugin.clear()).then(function () {
        if (pdbText) {
          viewer.loadStructureFromData(pdbText, 'pdb').catch(function (err) {
            console.error('gromacsGui: loadStructureFromData failed', err);
          });
        }
      });
    });
  };
</script>
</body>
</html>
"""


class _LoggingWebEnginePage(QWebEnginePage):
    """Forwards the page's browser-console output (including Mol*'s own
    errors) to Python logging - otherwise JS-side failures are invisible
    since this view has no visible devtools.
    """

    def javaScriptConsoleMessage(self, level, message, line, source):  # noqa: N802
        _logger.debug("[molstar console] %s:%s %s", source, line, message)


class MoleculeViewerWeb(QWidget):
    """Same set_atoms()/show_message() interface as MoleculeViewer3D, so
    the cleanup step can use either backend interchangeably.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        # loadStructureFromData calls made before the page finishes loading
        # molstar.js (a ~5MB script) are silently dropped, since
        # window.__gromacsGuiSetPdb doesn't exist yet - buffer the most
        # recent request and flush it once loadFinished fires.
        self._page_ready = False
        self._pending_pdb_text: str | None = None

        self._view = QWebEngineView(self)
        self._view.setPage(_LoggingWebEnginePage(self._view))
        self._view.loadFinished.connect(self._on_load_finished)
        base_url = QUrl.fromLocalFile(str(_WEB_ASSETS_DIR) + "/")
        self._view.setHtml(_HTML_SHELL, base_url)

        self._message_label = QLabel("", self)
        self._message_label.setWordWrap(True)
        self._message_label.setStyleSheet("padding: 12px;")

        self._stack = QStackedWidget(self)
        self._stack.addWidget(self._view)
        self._stack.addWidget(self._message_label)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._stack)

        self.show_message("Select a file to preview.")

    def _on_load_finished(self, ok: bool) -> None:
        self._page_ready = ok
        if ok and self._pending_pdb_text is not None:
            self._run_set_pdb(self._pending_pdb_text)
            self._pending_pdb_text = None

    def _run_set_pdb(self, pdb_text: str) -> None:
        js = f"window.__gromacsGuiSetPdb && window.__gromacsGuiSetPdb({json.dumps(pdb_text)});"
        self._view.page().runJavaScript(js)

    def _send_pdb(self, pdb_text: str) -> None:
        if self._page_ready:
            self._run_set_pdb(pdb_text)
        else:
            self._pending_pdb_text = pdb_text

    def show_message(self, text: str) -> None:
        self._message_label.setText(text)
        self._stack.setCurrentWidget(self._message_label)
        self._send_pdb("")

    def set_atoms(self, atoms: list[AtomPosition]) -> None:
        if not atoms:
            self.show_message("Nothing selected to save.")
            return
        self._stack.setCurrentWidget(self._view)
        self._send_pdb(format_atoms_as_pdb(atoms))

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
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QLabel, QStackedWidget, QVBoxLayout, QWidget

from gromacs_gui.gmx.structure_files import AtomPosition, format_atoms_as_pdb

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
      viewer.clear();
      if (pdbText) {
        viewer.loadStructureFromData(pdbText, 'pdb', false);
      }
    });
  };
</script>
</body>
</html>
"""


class MoleculeViewerWeb(QWidget):
    """Same set_atoms()/show_message() interface as MoleculeViewer3D, so
    the cleanup step can use either backend interchangeably.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._view = QWebEngineView(self)
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

        self.show_message("Selecciona un archivo para previsualizar.")

    def show_message(self, text: str) -> None:
        self._message_label.setText(text)
        self._stack.setCurrentWidget(self._message_label)
        self._view.page().runJavaScript(
            "window.__gromacsGuiSetPdb && window.__gromacsGuiSetPdb('');"
        )

    def set_atoms(self, atoms: list[AtomPosition]) -> None:
        if not atoms:
            self.show_message("Nada seleccionado para guardar.")
            return
        self._stack.setCurrentWidget(self._view)
        pdb_text = format_atoms_as_pdb(atoms)
        js = f"window.__gromacsGuiSetPdb && window.__gromacsGuiSetPdb({json.dumps(pdb_text)});"
        self._view.page().runJavaScript(js)

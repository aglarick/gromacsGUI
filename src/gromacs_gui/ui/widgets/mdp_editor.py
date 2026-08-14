from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QPlainTextEdit, QVBoxLayout, QWidget

from gromacs_gui.mdp.mdp_model import MdpFile


class MdpEditor(QWidget):
    """Raw-text .mdp editor.

    Milestone 4 ships text mode only, so students can see and edit the exact
    file GROMACS will use. A form mode with per-parameter tooltips is planned
    for a later milestone, on top of the same MdpFile model.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._text_edit = QPlainTextEdit(self)
        self._text_edit.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)

        layout = QVBoxLayout(self)
        layout.addWidget(self._text_edit)

    def load_mdp(self, mdp: MdpFile) -> None:
        self._text_edit.setPlainText(mdp.to_text())

    def load_file(self, path: Path) -> None:
        self.load_mdp(MdpFile.load(path))

    def to_mdp(self) -> MdpFile:
        return MdpFile.parse(self._text_edit.toPlainText())

    def save_to(self, path: Path) -> None:
        self.to_mdp().save(path)

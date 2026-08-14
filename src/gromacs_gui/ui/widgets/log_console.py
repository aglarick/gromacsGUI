from __future__ import annotations

from html import escape

from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QPlainTextEdit

from gromacs_gui.gmx.error_catalog import ErrorCatalog, ErrorMatch

_STREAM_COLORS = {
    "stdout": "#2c2c2c",
    "stderr": "#c0392b",
    "info": "#2471a3",
}


class LogConsole(QPlainTextEdit):
    """Streams gmx subprocess output, flagging known error patterns inline."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setReadOnly(True)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.setMaximumBlockCount(20000)
        self._error_catalog = ErrorCatalog.load()

    def append_line(self, text: str, stream: str = "stdout") -> None:
        color = _STREAM_COLORS.get(stream, _STREAM_COLORS["stdout"])
        self.appendHtml(f'<span style="color:{color}; white-space:pre;">{escape(text)}</span>')

        match = self._error_catalog.match(text)
        if match is not None:
            self._append_explanation(match)

        self.moveCursor(QTextCursor.MoveOperation.End)

    def _append_explanation(self, match: ErrorMatch) -> None:
        html = (
            '<div style="margin:4px 0; padding:6px; border-left:3px solid #d35400; '
            'background:#fdf1e8;">'
            f"<b>{escape(match.title)}</b><br>{escape(match.explanation)}"
        )
        if match.suggestion:
            html += f"<br><i>{escape(match.suggestion)}</i>"
        html += "</div>"
        self.appendHtml(html)

    def clear_log(self) -> None:
        self.clear()

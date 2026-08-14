from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_KEY_VALUE_RE = re.compile(r"^(?P<key>[^=;]+?)\s*=\s*(?P<value>[^;]*?)\s*(?P<comment>;.*)?$")


@dataclass
class MdpLine:
    raw: str
    key: str | None = None
    value: str | None = None


class MdpFile:
    """An in-memory .mdp file that preserves comments, blank lines, and key
    order across a read-modify-write round trip.

    GROMACS .mdp files are simple `key = value` lines with optional `;` inline
    or full-line comments; students editing them expect their comments and
    layout to survive a save from the GUI, not get silently reformatted away.
    """

    def __init__(self, lines: list[MdpLine]) -> None:
        self._lines = lines

    @classmethod
    def parse(cls, text: str) -> MdpFile:
        lines: list[MdpLine] = []
        for raw_line in text.splitlines():
            stripped = raw_line.strip()
            if not stripped or stripped.startswith(";"):
                lines.append(MdpLine(raw=raw_line))
                continue
            match = _KEY_VALUE_RE.match(raw_line)
            if not match:
                lines.append(MdpLine(raw=raw_line))
                continue
            lines.append(
                MdpLine(
                    raw=raw_line,
                    key=match.group("key").strip(),
                    value=match.group("value").strip(),
                )
            )
        return cls(lines)

    @classmethod
    def load(cls, path: Path) -> MdpFile:
        return cls.parse(Path(path).read_text())

    def get(self, key: str) -> str | None:
        for line in self._lines:
            if line.key is not None and _normalize(line.key) == _normalize(key):
                return line.value
        return None

    def set(self, key: str, value: str) -> None:
        normalized = _normalize(key)
        for i, line in enumerate(self._lines):
            if line.key is not None and _normalize(line.key) == normalized:
                new_raw = _replace_value(line.raw, line.value or "", value)
                self._lines[i] = MdpLine(raw=new_raw, key=line.key, value=value)
                return
        self._lines.append(MdpLine(raw=f"{key} = {value}", key=key, value=value))

    def keys(self) -> list[str]:
        return [line.key for line in self._lines if line.key is not None]

    def to_text(self) -> str:
        return "\n".join(line.raw for line in self._lines) + "\n"

    def save(self, path: Path) -> None:
        Path(path).write_text(self.to_text())


def _normalize(key: str) -> str:
    return key.strip().lower()


def _replace_value(raw: str, old_value: str, new_value: str) -> str:
    """Replace only the value portion of a `key = value ; comment` line,
    keeping the key's original spacing and any inline comment intact.
    """
    eq_index = raw.index("=")
    before_eq = raw[: eq_index + 1]
    after = raw[eq_index + 1 :]
    value_index = after.find(old_value) if old_value else 0
    before_value = after[:value_index] or " "
    after_value = after[value_index + len(old_value) :]
    return f"{before_eq}{before_value}{new_value}{after_value}"

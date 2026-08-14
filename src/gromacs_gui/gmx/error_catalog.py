from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

DEFAULT_CATALOG_PATH = Path(__file__).parent / "errors.yaml"


@dataclass
class ErrorMatch:
    title: str
    explanation: str
    suggestion: str | None = None


class ErrorCatalog:
    def __init__(self, entries: list[dict]) -> None:
        self._entries = entries

    @classmethod
    def load(cls, path: Path | None = None) -> ErrorCatalog:
        path = path or DEFAULT_CATALOG_PATH
        entries = yaml.safe_load(path.read_text()) or []
        return cls(entries)

    def match(self, text: str) -> ErrorMatch | None:
        for entry in self._entries:
            if re.search(entry["pattern"], text, re.IGNORECASE):
                return ErrorMatch(
                    title=entry["title"],
                    explanation=entry["explanation"].strip(),
                    suggestion=entry.get("suggestion", "").strip() or None,
                )
        return None

"""Article dataclass for structured publication metadata."""

import dataclasses
import json
from pathlib import Path


@dataclasses.dataclass
class Article:
    """Structured metadata for a single publication."""

    title: str
    authors: list[str]
    venue: str
    pdf_url: str | None
    links: dict[str, str]

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Article":
        return cls(**d)

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
        )

    @classmethod
    def load(cls, path: str | Path) -> "Article":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.from_dict(data)

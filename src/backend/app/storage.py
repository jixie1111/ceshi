from __future__ import annotations

import json
import re
from pathlib import Path
from threading import RLock
from typing import Any, Dict, List

from .core.config import get_settings
from .models.schemas import IntegratedGraph, KnowledgeGraph, Textbook


class JsonStore:
    """Tiny JSON document store for hackathon-friendly reproducibility.

    It deliberately avoids a heavyweight database so judges can clone and run the
    project with only Python + Node. The store is thread-safe for normal FastAPI
    development usage. For production, replace with Postgres/S3 without changing
    service interfaces.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self.root: Path = settings.data_dir
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()

    def _path(self, name: str) -> Path:
        return self.root / name

    def read_json(self, name: str, default: Any) -> Any:
        with self._lock:
            path = self._path(name)
            if not path.exists():
                return default
            with path.open("r", encoding="utf-8") as f:
                return json.load(f)

    def write_json(self, name: str, data: Any) -> None:
        with self._lock:
            path = self._path(name)
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(path.suffix + ".tmp")
            with tmp.open("w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
            tmp.replace(path)

    def list_books(self) -> List[Textbook]:
        return sorted([Textbook.model_validate(x) for x in self.read_json("books.json", [])], key=_book_sort_key)

    def save_books(self, books: List[Textbook]) -> None:
        self.write_json("books.json", [b.model_dump(mode="json") for b in sorted(books, key=_book_sort_key)])

    def upsert_book(self, book: Textbook) -> None:
        books = self.list_books()
        books = [b for b in books if b.textbook_id != book.textbook_id]
        books.append(book)
        self.save_books(books)

    def get_book(self, textbook_id: str) -> Textbook | None:
        return next((b for b in self.list_books() if b.textbook_id == textbook_id), None)

    def list_graphs(self) -> Dict[str, KnowledgeGraph]:
        raw = self.read_json("graphs.json", {})
        return {k: KnowledgeGraph.model_validate(v) for k, v in raw.items()}

    def save_graph(self, graph: KnowledgeGraph) -> None:
        graphs = self.list_graphs()
        graphs[graph.textbook_id] = graph
        self.write_json("graphs.json", {k: v.model_dump(mode="json") for k, v in graphs.items()})

    def get_graph(self, textbook_id: str) -> KnowledgeGraph | None:
        return self.list_graphs().get(textbook_id)

    def save_integration(self, graph: IntegratedGraph) -> None:
        self.write_json("integration.json", graph.model_dump(mode="json"))

    def get_integration(self) -> IntegratedGraph:
        return IntegratedGraph.model_validate(self.read_json("integration.json", {}))

    def append_chat(self, role: str, content: str) -> None:
        history = self.read_json("chat_history.json", [])
        history.append({"role": role, "content": content})
        self.write_json("chat_history.json", history[-200:])

    def chat_history(self) -> List[Dict[str, str]]:
        return self.read_json("chat_history.json", [])


store = JsonStore()


def _book_sort_key(book: Textbook) -> tuple[int, str]:
    title = book.title or book.filename
    match = re.match(r"^\s*(\d+)", title)
    return (int(match.group(1)) if match else 9999, title)

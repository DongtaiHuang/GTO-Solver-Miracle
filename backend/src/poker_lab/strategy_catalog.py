"""Local, transactional catalog. No HTTP import, scraping, or automatic validation claims."""

import json
import sqlite3
from datetime import UTC, datetime
from importlib.resources import files
from pathlib import Path

from poker_lab.strategy_models import Approval, Dataset, ImportedSolution

MAX_CATALOG_SOLUTIONS = 128
MAX_IMPORT_BYTES = 8 * 1024 * 1024


def strict_json(text: str) -> object:
    def object_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result

    def invalid_constant(value: str) -> object:
        raise ValueError(f"Nonfinite JSON number: {value}")

    return json.loads(text, object_pairs_hook=object_pairs, parse_constant=invalid_constant)


class SolutionCatalog:
    def __init__(self, entries: list[ImportedSolution] | None = None) -> None:
        self.entries = list(entries or [])
        self._check()

    def _check(self) -> None:
        if len(self.entries) > MAX_CATALOG_SOLUTIONS:
            raise ValueError("Catalog exceeds the 128-solution limit")
        ids = [entry.document.solution_id for entry in self.entries]
        keys = [(e.document.kind, e.document.scenario.scenario_id) for e in self.entries]
        if len(set(ids)) != len(ids) or len(set(keys)) != len(keys):
            raise ValueError("Duplicate solution ID or conflicting exact scenario in catalog")

    def visible(self, mode: str) -> list[ImportedSolution]:
        return [
            entry
            for entry in self.entries
            if (entry.public_demo if mode == "synthetic_demo" else entry.public_baseline)
        ]

    def find(self, scenario_id: str, mode: str) -> ImportedSolution | None:
        return next(
            (e for e in self.visible(mode) if e.document.scenario.scenario_id == scenario_id), None
        )

    def source(self, solution_id: str, mode: str) -> ImportedSolution | None:
        return next((e for e in self.visible(mode) if e.document.solution_id == solution_id), None)


def demo_catalog() -> SolutionCatalog:
    payload = files("poker_lab").joinpath("data/strategy_demo_v1.json").read_text(encoding="utf-8")
    dataset = Dataset.model_validate(strict_json(payload))
    now = datetime.now(UTC)
    return SolutionCatalog(
        [ImportedSolution(document=s, imported_at=now) for s in dataset.solutions]
    )


def read_dataset(path: Path) -> Dataset:
    if path.stat().st_size > MAX_IMPORT_BYTES:
        raise ValueError("Dataset exceeds the 8 MiB import limit")
    return Dataset.model_validate(strict_json(path.read_text(encoding="utf-8")))


def load_catalog(path: Path) -> SolutionCatalog:
    # Read-only: a missing path or malformed entry fails clearly rather than creating a database.
    with sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True) as connection:
        rows = connection.execute("SELECT entry_json FROM solutions LIMIT 129").fetchall()
    return SolutionCatalog([ImportedSolution.model_validate(strict_json(row[0])) for row in rows])


def import_dataset(
    dataset: Dataset,
    path: Path,
    *,
    reviewer: str | None = None,
    evidence: str | None = None,
    confirm_rights: bool = False,
) -> int:
    now = datetime.now(UTC)
    entries = []
    for solution in dataset.solutions:
        approval = None
        if reviewer is not None:
            if not evidence or not confirm_rights:
                raise ValueError(
                    "Approval requires evidence and explicit source/rights confirmation"
                )
            approval = Approval(
                content_hash=solution.content_hash,
                reviewer=reviewer,
                evidence_reference=evidence,
                approved_at=now,
                confirmed_source_and_rights=True,
            )
        entries.append(ImportedSolution(document=solution, imported_at=now, approval=approval))
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as connection:
        connection.execute("""CREATE TABLE IF NOT EXISTS solutions(
            solution_id TEXT PRIMARY KEY, scenario_id TEXT NOT NULL, kind TEXT NOT NULL,
            entry_json TEXT NOT NULL, UNIQUE(scenario_id, kind))""")
        existing = connection.execute("SELECT COUNT(*) FROM solutions").fetchone()[0]
        if existing + len(entries) > MAX_CATALOG_SOLUTIONS - 4:
            raise ValueError("Imported catalog exceeds 124 entries (four slots reserved for demos)")
        try:
            connection.executemany(
                "INSERT INTO solutions VALUES (?, ?, ?, ?)",
                [
                    (
                        e.document.solution_id,
                        e.document.scenario.scenario_id,
                        e.document.kind,
                        e.model_dump_json(),
                    )
                    for e in entries
                ],
            )
        except sqlite3.IntegrityError:
            raise ValueError(
                "Duplicate solution ID or conflicting scenario; nothing imported"
            ) from None
    return len(entries)


def configured_catalog(path: str | None) -> SolutionCatalog:
    demos = demo_catalog()
    if path is None:
        return demos
    imported = load_catalog(Path(path))
    return SolutionCatalog(demos.entries + imported.entries)

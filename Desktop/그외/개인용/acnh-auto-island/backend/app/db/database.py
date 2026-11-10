"""SQLite 저장소. 구조화된 설계 데이터를 JSON 문서로 저장한다."""
from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from backend.app.schemas.design import Design, RunResult, Zone, ZoneIn

_TABLES = ("zones", "designs", "runs")


def new_id() -> str:
    return uuid.uuid4().hex[:12]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Repository:
    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._path = str(db_path)
        with self._conn() as c:
            for t in _TABLES:
                c.execute(
                    f"CREATE TABLE IF NOT EXISTS {t} "
                    "(id TEXT PRIMARY KEY, parent_id TEXT, created_at TEXT NOT NULL, doc TEXT NOT NULL)"
                )

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self._path)

    def _put(self, table: str, id_: str, parent_id: str | None, doc: str) -> None:
        with self._conn() as c:
            c.execute(
                f"INSERT INTO {table} (id, parent_id, created_at, doc) VALUES (?,?,?,?) "
                "ON CONFLICT(id) DO UPDATE SET doc=excluded.doc",
                (id_, parent_id, now_iso(), doc),
            )

    def _get(self, table: str, id_: str) -> str | None:
        with self._conn() as c:
            row = c.execute(f"SELECT doc FROM {table} WHERE id=?", (id_,)).fetchone()
        return row[0] if row else None

    def _list(self, table: str, parent_id: str | None = None) -> list[str]:
        q = f"SELECT doc FROM {table}"
        args: tuple = ()
        if parent_id is not None:
            q += " WHERE parent_id=?"
            args = (parent_id,)
        with self._conn() as c:
            return [r[0] for r in c.execute(q + " ORDER BY created_at, rowid", args)]

    # zones
    def save_zone(self, zone_in: ZoneIn, zone_id: str | None = None) -> Zone:
        zone = Zone(id=zone_id or new_id(), **zone_in.model_dump(exclude={"id"}))
        self._put("zones", zone.id, None, zone.model_dump_json())
        return zone

    def get_zone(self, zone_id: str) -> Zone | None:
        doc = self._get("zones", zone_id)
        return Zone.model_validate_json(doc) if doc else None

    def list_zones(self) -> list[Zone]:
        return [Zone.model_validate_json(d) for d in self._list("zones")]

    # designs
    def save_design(self, design: Design) -> Design:
        self._put("designs", design.id, design.zone_id, design.model_dump_json())
        return design

    def get_design(self, design_id: str) -> Design | None:
        doc = self._get("designs", design_id)
        return Design.model_validate_json(doc) if doc else None

    def list_designs(self, zone_id: str | None = None) -> list[Design]:
        return [Design.model_validate_json(d) for d in self._list("designs", zone_id)]

    # runs
    def save_run(self, run: RunResult) -> RunResult:
        self._put("runs", run.id, run.design_id, run.model_dump_json())
        return run

    def list_runs(self, design_id: str | None = None) -> list[RunResult]:
        return [RunResult.model_validate_json(d) for d in self._list("runs", design_id)]

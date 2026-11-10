"""아이템 카탈로그 로더."""
from __future__ import annotations

import json
from pathlib import Path

from backend.app.schemas.design import CatalogItem, Placement


class Catalog:
    def __init__(self, items: list[CatalogItem]) -> None:
        self._items = {i.id: i for i in items}

    @classmethod
    def load(cls, path: Path) -> "Catalog":
        raw = json.loads(path.read_text(encoding="utf-8"))
        return cls([CatalogItem.model_validate(i) for i in raw["items"]])

    def get(self, item_id: str) -> CatalogItem | None:
        return self._items.get(item_id)

    def all(self) -> list[CatalogItem]:
        return list(self._items.values())

    def by_category(self, category: str) -> list[CatalogItem]:
        return [i for i in self._items.values() if i.category == category]


def footprint(item: CatalogItem, p: Placement) -> list[tuple[int, int]]:
    """회전을 반영한 점유 타일 목록. (x, y)는 좌상단 기준점."""
    w, h = (item.height, item.width) if p.rotation in (90, 270) else (item.width, item.height)
    return [(p.x + dx, p.y + dy) for dy in range(h) for dx in range(w)]

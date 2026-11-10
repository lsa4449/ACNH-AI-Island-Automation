"""배치 규칙 검증기.

규칙은 모동숲 규칙을 단순화한 것이다 (docs/feasibility.md 참고).
- 길(ground)과 오브젝트(object)는 서로 다른 레이어다.
- 꽃/나무는 길 위에 심을 수 없고, 가구는 길 위에 놓을 수 있다.
- 나무는 주변 clearance칸(8방향)에 다른 나무·통과 불가 오브젝트·물/절벽/건물이 없어야 한다.
"""
from __future__ import annotations

from backend.app.schemas.design import (
    HARD_TERRAIN,
    Placement,
    RejectedPlacement,
    Terrain,
    ValidationResult,
    ZoneIn,
)
from backend.app.services.planner.catalog import Catalog, footprint


class _State:
    def __init__(self) -> None:
        self.ground: dict[tuple[int, int], str] = {}
        self.objects: dict[tuple[int, int], str] = {}


def _neighbors(x: int, y: int, r: int):
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            if dx or dy:
                yield x + dx, y + dy


def _check(zone: ZoneIn, catalog: Catalog, st: _State, p: Placement) -> tuple[str, str] | None:
    item = catalog.get(p.item_id)
    if item is None:
        return "UNKNOWN_ITEM", f"카탈로그에 없는 아이템: {p.item_id}"
    cells = footprint(item, p)
    if any(not zone.in_bounds(x, y) for x, y in cells):
        return "OUT_OF_BOUNDS", "구역 범위를 벗어납니다"
    for x, y in cells:
        t = zone.terrain(x, y)
        if t == Terrain.UNKNOWN:
            return "TERRAIN_UNKNOWN", f"({x},{y}) 지형이 확정되지 않았습니다"
        if t not in item.allowed_terrain:
            return "TERRAIN_NOT_ALLOWED", f"({x},{y}) {t.value} 지형에는 놓을 수 없습니다"
    layer = st.ground if item.layer == "ground" else st.objects
    for c in cells:
        if c in layer:
            return "OVERLAP", f"{c} 타일에 이미 {layer[c]}이(가) 있습니다"
    if item.layer == "ground":
        for c in cells:
            other = catalog.get(st.objects.get(c, ""))
            if other and not other.allow_on_path:
                return "PATH_UNDER_PLANT", f"{c} 타일의 {other.id} 아래에는 길을 깔 수 없습니다"
    elif not item.allow_on_path and any(c in st.ground for c in cells):
        return "ON_PATH", "길 위에는 심을 수 없습니다"
    if not item.walkable and tuple(zone.start) in cells:
        return "START_BLOCKED", "캐릭터 시작 타일을 막습니다"
    # 나무 간격: 새 나무 주변, 그리고 기존 나무 주변 양쪽을 모두 확인한다.
    if item.clearance:
        for x, y in cells:
            for nx, ny in _neighbors(x, y, item.clearance):
                if not zone.in_bounds(nx, ny):
                    continue
                if zone.terrain(nx, ny) in HARD_TERRAIN:
                    return "TREE_CLEARANCE", f"({nx},{ny}) 지형과 너무 가깝습니다"
                other = catalog.get(st.objects.get((nx, ny), ""))
                if other and not other.walkable:
                    return "TREE_CLEARANCE", f"({nx},{ny})의 {other.id}와 너무 가깝습니다"
    if not item.walkable:
        for x, y in cells:
            for (ox, oy), oid in st.objects.items():
                other = catalog.get(oid)
                if other and other.clearance and max(abs(ox - x), abs(oy - y)) <= other.clearance:
                    return "TREE_CLEARANCE", f"({ox},{oy})의 {oid} 성장 공간을 침범합니다"
    return None


def validate(zone: ZoneIn, catalog: Catalog, placements: list[Placement]) -> ValidationResult:
    """입력 순서대로 검사하되 길(ground)을 먼저 처리한다. 규칙 위반 항목은 rejected로 분리."""
    st = _State()
    accepted: list[Placement] = []
    rejected: list[RejectedPlacement] = []

    def layer_rank(p: Placement) -> int:
        item = catalog.get(p.item_id)
        return 0 if item and item.layer == "ground" else 1

    for p in sorted(placements, key=layer_rank):  # 안정 정렬: 레이어 내 순서 유지
        err = _check(zone, catalog, st, p)
        if err:
            rejected.append(RejectedPlacement(placement=p, code=err[0], message=err[1]))
            continue
        item = catalog.get(p.item_id)
        layer = st.ground if item.layer == "ground" else st.objects
        for c in footprint(item, p):
            layer[c] = item.id
        accepted.append(p)
    return ValidationResult(accepted=accepted, rejected=rejected)

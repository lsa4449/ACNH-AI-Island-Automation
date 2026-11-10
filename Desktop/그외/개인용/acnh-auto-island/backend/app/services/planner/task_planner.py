"""검증된 설계를 실행 가능한 작업 목록으로 변환한다.

각 작업은 "대상 타일 옆(4방향)에 서서 대상 방향을 본 뒤 설치"로 모델링한다.
여러 칸짜리 가구가 캐릭터 기준 어느 쪽에 놓이는지는 실제 게임에서 검증이 필요하다(Phase 4).
도달할 수 없는 작업은 실행한 척하지 않고 needs_user로 표시한다.
"""
from __future__ import annotations

from collections import deque

from backend.app.schemas.design import WALKABLE_TERRAIN, Placement, Plan, Task, ZoneIn
from backend.app.services.planner.catalog import Catalog, footprint

DIRS = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}
Cell = tuple[int, int]


def bfs(zone: ZoneIn, blocked: set[Cell], start: Cell) -> dict[Cell, Cell | None]:
    """start에서 걸어서 갈 수 있는 모든 타일의 부모 맵."""
    parent: dict[Cell, Cell | None] = {start: None}
    q = deque([start])
    while q:
        x, y = q.popleft()
        for dx, dy in DIRS.values():
            n = (x + dx, y + dy)
            if n in parent or not zone.in_bounds(*n) or n in blocked:
                continue
            if zone.terrain(*n) not in WALKABLE_TERRAIN:
                continue
            parent[n] = (x, y)
            q.append(n)
    return parent


def _trace(parent: dict[Cell, Cell | None], goal: Cell) -> list[Cell]:
    path: list[Cell] = []
    cur: Cell | None = goal
    while cur is not None and parent[cur] is not None:
        path.append(cur)
        cur = parent[cur]
    return path[::-1]


def _approach(zone, parent, target: Cell, cells: list[Cell]):
    """target에 인접하고 도달 가능한 타일 중 가장 가까운 곳과 바라볼 방향."""
    best = None
    for name, (dx, dy) in DIRS.items():
        stand = (target[0] - dx, target[1] - dy)
        if stand in cells or stand not in parent:
            continue
        path = _trace(parent, stand)
        if best is None or len(path) < len(best[2]):
            best = (stand, name, path)
    return best


def build_plan(zone: ZoneIn, catalog: Catalog, design_id: str, placements: list[Placement]) -> Plan:
    start: Cell = tuple(zone.start)
    blocked: set[Cell] = set()
    parent0 = bfs(zone, set(), start)
    dist0 = {c: len(_trace(parent0, c)) for c in parent0}

    def far_first(p: Placement) -> tuple[int, int]:
        item = catalog.get(p.item_id)
        # 길을 먼저, 그 다음 시작점에서 먼 오브젝트부터 (스스로 길을 막지 않기 위해)
        return (0 if item.layer == "ground" else 1, -dist0.get((p.x, p.y), 10**6))

    pending = sorted(placements, key=far_first)
    tasks: list[Task] = []
    pos = start
    required: dict[str, int] = {}
    deferred: list[Placement] = []

    def try_place(p: Placement) -> bool:
        nonlocal pos
        item = catalog.get(p.item_id)
        cells = footprint(item, p)
        if pos in cells and not item.walkable:
            return False
        parent = bfs(zone, blocked, pos)
        found = _approach(zone, parent, (p.x, p.y), cells)
        if found is None:
            return False
        stand, facing, path = found
        tasks.append(Task(id=len(tasks) + 1, item_id=p.item_id, target=(p.x, p.y), rotation=p.rotation,
                          stand=stand, facing=facing, path=path))
        pos = stand
        if not item.walkable:
            blocked.update(cells)
        return True

    for p in pending:
        required[p.item_id] = required.get(p.item_id, 0) + 1
        if not try_place(p):
            deferred.append(p)
    for p in deferred:  # 한 번 더 시도 후에도 안 되면 사용자 개입
        if not try_place(p):
            tasks.append(Task(id=len(tasks) + 1, item_id=p.item_id, target=(p.x, p.y), rotation=p.rotation,
                              status="needs_user", reason="걸어서 도달할 수 있는 인접 타일이 없습니다"))
    return Plan(
        design_id=design_id,
        tasks=tasks,
        required_items=required,
        total_steps=sum(len(t.path) for t in tasks),
        needs_user=sum(t.status == "needs_user" for t in tasks),
    )

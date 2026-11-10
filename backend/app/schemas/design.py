"""설계 데이터 스키마. 모든 좌표는 타일 단위이며 x=오른쪽, y=아래쪽, 0부터 시작한다."""
from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class Terrain(str, Enum):
    GRASS = "grass"
    SAND = "sand"
    WATER = "water"
    CLIFF = "cliff"
    BUILDING = "building"
    UNKNOWN = "unknown"  # 인식 실패/미확인. 사용자가 확정하기 전에는 배치 불가.


WALKABLE_TERRAIN = {Terrain.GRASS, Terrain.SAND}
HARD_TERRAIN = {Terrain.WATER, Terrain.CLIFF, Terrain.BUILDING}

Rotation = Literal[0, 90, 180, 270]


class CatalogItem(BaseModel):
    id: str
    name_ko: str
    category: Literal["path", "flower", "tree", "furniture"]
    layer: Literal["ground", "object"]
    width: int = 1
    height: int = 1
    allowed_terrain: list[Terrain] = [Terrain.GRASS]
    allow_on_path: bool = False  # 길 타일 위에 올릴 수 있는가 (가구만 가능)
    walkable: bool = True  # 설치 후 캐릭터가 지나갈 수 있는가
    clearance: int = 0  # 나무: 주변 N칸에 다른 나무/장애물이 없어야 함


class ZoneIn(BaseModel):
    name: str
    width: int = Field(ge=1, le=112)  # 섬 전체 지도는 112x96 타일
    height: int = Field(ge=1, le=96)
    tiles: list[list[Terrain]]
    start: tuple[int, int] = (0, 0)  # 캐릭터 시작 타일
    confidence: list[list[float]] | None = None  # 지도 인식 초안일 때만 존재

    @model_validator(mode="after")
    def _check_shape(self) -> "ZoneIn":
        if len(self.tiles) != self.height or any(len(r) != self.width for r in self.tiles):
            raise ValueError("tiles 크기가 width/height와 일치하지 않습니다")
        sx, sy = self.start
        if not (0 <= sx < self.width and 0 <= sy < self.height):
            raise ValueError("start가 구역 밖에 있습니다")
        return self

    def terrain(self, x: int, y: int) -> Terrain:
        return self.tiles[y][x]

    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height


class Zone(ZoneIn):
    id: str


class Placement(BaseModel):
    item_id: str
    x: int
    y: int
    rotation: Rotation = 0


class RejectedPlacement(BaseModel):
    placement: Placement
    code: str
    message: str


class DesignRequest(BaseModel):
    zone_id: str
    prompt: str = Field(min_length=1, max_length=2000)
    use_llm: bool = True
    seed: int | None = None


class Design(BaseModel):
    id: str
    zone_id: str
    prompt: str
    source: Literal["ollama", "rule_based"]
    model: str | None = None
    notes: str = ""
    placements: list[Placement]
    rejected: list[RejectedPlacement] = []
    created_at: str


class ValidateRequest(BaseModel):
    zone_id: str
    placements: list[Placement]


class ValidationResult(BaseModel):
    accepted: list[Placement]
    rejected: list[RejectedPlacement]


class Task(BaseModel):
    id: int
    kind: Literal["place"] = "place"
    item_id: str
    target: tuple[int, int]
    rotation: Rotation = 0
    stand: tuple[int, int] | None = None  # 작업 시 캐릭터가 설 타일
    facing: str | None = None  # up/down/left/right
    path: list[tuple[int, int]] = []  # 직전 위치에서 stand까지 (시작 타일 제외)
    status: Literal["planned", "needs_user"] = "planned"
    reason: str = ""


class Plan(BaseModel):
    design_id: str
    tasks: list[Task]
    required_items: dict[str, int]
    total_steps: int
    needs_user: int


class RunRequest(BaseModel):
    dry_run: bool = True  # 기본은 항상 Dry Run
    controller: Literal["mock"] = "mock"  # Phase 1에는 mock만 존재
    approved: bool = False  # 실제 하드웨어 실행 승인 (Phase 2 이후 사용)
    timeout_s: float = Field(default=30.0, gt=0, le=3600)


class Command(BaseModel):
    task_id: int
    op: Literal["move", "turn", "press"]
    arg: str
    duration_ms: int
    note: str = ""


class RunResult(BaseModel):
    id: str
    design_id: str
    dry_run: bool
    status: Literal["completed", "stopped", "timeout", "failed"]
    message: str = ""
    completed_tasks: list[int]
    skipped_tasks: list[int]
    commands: list[Command]
    final_position: tuple[int, int] | None = None
    created_at: str

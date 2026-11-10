"""AI Island Designer.

LLM은 "어디에 무엇을 둘지"만 JSON으로 제안한다. 제안은 반드시 검증기를 통과해야 하며
규칙 위반 항목은 rejected로 분리된다. Ollama를 쓸 수 없으면 규칙 기반 생성기로 대체한다.
"""
from __future__ import annotations

import random

from pydantic import BaseModel, ValidationError

from backend.app.db.database import new_id, now_iso
from backend.app.schemas.design import Design, Placement, Terrain, ZoneIn
from backend.app.services.ai.ollama_client import OllamaClient, OllamaError
from backend.app.services.planner.catalog import Catalog
from backend.app.services.planner.validator import validate

_SYMBOL = {Terrain.GRASS: ".", Terrain.SAND: "s", Terrain.WATER: "~", Terrain.CLIFF: "^",
           Terrain.BUILDING: "#", Terrain.UNKNOWN: "?"}

SYSTEM_PROMPT = (
    "너는 '모여봐요 동물의 숲' 섬 디자이너다. 주어진 타일 격자 위에 아이템 배치 계획을 JSON으로만 출력한다.\n"
    "규칙: 좌표는 x(오른쪽, 0부터), y(아래쪽, 0부터). 카탈로그에 있는 item_id만 사용한다. "
    "'.'(잔디) 타일에만 배치한다. 길은 사람이 걸을 수 있게 이어지도록 깐다. "
    "꽃과 나무는 길 위에 두지 않는다. 나무끼리는 최소 한 칸 띄우고 물·절벽·건물 옆에 두지 않는다. "
    "S는 캐릭터 시작 위치이며 비워 둔다."
)


class _LLMOutput(BaseModel):
    placements: list[Placement]
    notes: str = ""


def render_zone(zone: ZoneIn) -> str:
    rows = []
    for y, row in enumerate(zone.tiles):
        line = "".join("S" if (x, y) == tuple(zone.start) else _SYMBOL[t] for x, t in enumerate(row))
        rows.append(f"y={y:02d} {line}")
    return "\n".join(rows)


def build_user_prompt(zone: ZoneIn, catalog: Catalog, prompt: str) -> str:
    items = "\n".join(
        f"- {i.id}: {i.name_ko} ({i.category}, {i.width}x{i.height})" for i in catalog.all()
    )
    return (
        f"구역 크기: {zone.width}x{zone.height}\n"
        "범례: .=잔디 s=모래 ~=물 ^=절벽 #=건물 ?=미확인 S=시작\n"
        f"{render_zone(zone)}\n\n카탈로그:\n{items}\n\n요청: {prompt}"
    )


def _wants(prompt: str) -> dict[str, bool]:
    p = prompt.lower()
    keys = {
        "path": ("길", "산책로", "path"),
        "flower": ("꽃", "화단", "정원", "flower"),
        "tree": ("나무", "숲", "과수", "tree"),
        "furniture": ("벤치", "가구", "가로등", "쉼터", "공원", "bench"),
    }
    wants = {k: any(w in p for w in ws) for k, ws in keys.items()}
    return wants if any(wants.values()) else {k: True for k in keys}


def rule_based_candidates(zone: ZoneIn, catalog: Catalog, prompt: str, seed: int | None) -> list[Placement]:
    """결정적(seed) 후보 생성. 최종 필터링은 검증기가 담당한다."""
    rng = random.Random(seed if seed is not None else 0)
    wants = _wants(prompt)
    out: list[Placement] = []
    row = zone.start[1]
    grass_row = [x for x in range(zone.width) if zone.terrain(x, row) == Terrain.GRASS]
    used: set[tuple[int, int]] = {tuple(zone.start)}

    if wants["path"] and catalog.by_category("path"):
        path = catalog.by_category("path")[0]
        out += [Placement(item_id=path.id, x=x, y=row) for x in grass_row]
        used |= {(x, row) for x in grass_row}
    if wants["furniture"]:
        for item_id, x in (("garden_bench", 1), ("streetlamp", zone.width - 2)):
            if catalog.get(item_id):
                for y in (row - 1, row + 1):
                    if zone.in_bounds(x, y) and (x, y) not in used:
                        out.append(Placement(item_id=item_id, x=x, y=y))
                        used |= {(x, y), (x + 1, y)}
                        break
    if wants["flower"] and catalog.by_category("flower"):
        flowers = catalog.by_category("flower")
        for y in (row - 1, row + 1):
            for x in range(0, zone.width, 2):
                if zone.in_bounds(x, y) and (x, y) not in used:
                    out.append(Placement(item_id=rng.choice(flowers).id, x=x, y=y))
                    used.add((x, y))
    if wants["tree"] and catalog.by_category("tree"):
        trees = catalog.by_category("tree")
        cells = [(x, y) for y in range(zone.height) for x in range(zone.width)
                 if abs(y - row) >= 3 and (x, y) not in used]
        rng.shuffle(cells)
        out += [Placement(item_id=rng.choice(trees).id, x=x, y=y) for x, y in cells[:40]]
    return out


def generate_design(zone_id: str, zone: ZoneIn, catalog: Catalog, prompt: str,
                    client: OllamaClient | None, use_llm: bool = True, seed: int | None = None) -> Design:
    notes = ""
    if use_llm and client is not None:
        try:
            raw = client.chat_json(SYSTEM_PROMPT, build_user_prompt(zone, catalog, prompt),
                                   _LLMOutput.model_json_schema())
            parsed = _LLMOutput.model_validate(raw)
            result = validate(zone, catalog, parsed.placements)
            if result.accepted:
                return Design(id=new_id(), zone_id=zone_id, prompt=prompt, source="ollama",
                              model=client.model, notes=parsed.notes, placements=result.accepted,
                              rejected=result.rejected, created_at=now_iso())
            notes = "LLM 제안이 모두 규칙을 위반해 규칙 기반 생성기로 대체했습니다."
        except (OllamaError, ValidationError) as e:
            notes = f"Ollama를 사용할 수 없어 규칙 기반 생성기로 대체했습니다. ({str(e)[:200]})"
    result = validate(zone, catalog, rule_based_candidates(zone, catalog, prompt, seed))
    # 규칙 기반 후보의 탈락분은 생성 과정의 부산물이므로 rejected에 싣지 않는다.
    return Design(id=new_id(), zone_id=zone_id, prompt=prompt, source="rule_based", notes=notes,
                  placements=result.accepted, created_at=now_iso())

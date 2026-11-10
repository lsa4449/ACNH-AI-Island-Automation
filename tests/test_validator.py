from backend.app.schemas.design import Placement as P
from backend.app.services.planner.validator import validate


def codes(result):
    return [r.code for r in result.rejected]


def test_valid_placements_accepted(zone, catalog):
    r = validate(zone, catalog, [P(item_id="path_stone", x=3, y=5), P(item_id="flower_tulip_red", x=3, y=4)])
    assert len(r.accepted) == 2 and not r.rejected


def test_unknown_item_and_bounds(zone, catalog):
    r = validate(zone, catalog, [P(item_id="nope", x=3, y=5), P(item_id="streetlamp", x=10, y=5)])
    assert codes(r) == ["UNKNOWN_ITEM", "OUT_OF_BOUNDS"]


def test_terrain_rules(zone, catalog):
    r = validate(zone, catalog, [P(item_id="flower_tulip_red", x=7, y=0), P(item_id="streetlamp", x=0, y=0)])
    assert codes(r) == ["TERRAIN_NOT_ALLOWED"] * 2


def test_overlap_same_layer(zone, catalog):
    r = validate(zone, catalog, [P(item_id="streetlamp", x=4, y=7), P(item_id="flower_tulip_red", x=4, y=7)])
    assert codes(r) == ["OVERLAP"]


def test_plants_not_on_path_but_furniture_ok(zone, catalog):
    r = validate(zone, catalog, [
        P(item_id="flower_tulip_red", x=4, y=6),  # 길보다 먼저 나와도 길이 우선 처리된다
        P(item_id="path_stone", x=4, y=6),
        P(item_id="path_stone", x=5, y=6),
        P(item_id="streetlamp", x=5, y=6),
    ])
    assert codes(r) == ["ON_PATH"] and len(r.accepted) == 3


def test_rotation_changes_footprint(zone, catalog):
    # 가든 벤치 2x1: (9,5)에서 0도면 범위 밖, 90도면 세로로 들어간다
    r = validate(zone, catalog, [P(item_id="garden_bench", x=9, y=5), P(item_id="garden_bench", x=9, y=5, rotation=90)])
    assert codes(r) == ["OUT_OF_BOUNDS"] and r.accepted[0].rotation == 90


def test_tree_clearance(zone, catalog):
    r = validate(zone, catalog, [
        P(item_id="sapling", x=3, y=7),
        P(item_id="sapling", x=4, y=8),      # 대각선 인접
        P(item_id="sapling", x=6, y=2),      # 물(7,*) 옆
        P(item_id="streetlamp", x=2, y=7),   # 기존 나무 옆 가구
        P(item_id="flower_tulip_red", x=2, y=8),  # 꽃은 나무 옆 가능
        P(item_id="sapling", x=5, y=7),      # 한 칸 띄움
    ])
    assert codes(r) == ["TREE_CLEARANCE"] * 3 and len(r.accepted) == 3


def test_start_tile_not_blocked(zone, catalog):
    r = validate(zone, catalog, [P(item_id="streetlamp", x=2, y=5), P(item_id="path_stone", x=2, y=5)])
    assert codes(r) == ["START_BLOCKED"] and len(r.accepted) == 1

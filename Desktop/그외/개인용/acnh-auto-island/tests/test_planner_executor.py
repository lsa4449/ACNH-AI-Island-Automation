import threading

import pytest

from backend.app.schemas.design import Placement as P
from backend.app.schemas.design import WALKABLE_TERRAIN
from backend.app.services.ai.designer import generate_design
from backend.app.services.automation.executor import Executor
from backend.app.services.planner.task_planner import build_plan
from switch_worker.controller.base import Button, Direction
from switch_worker.controller.mock import MockController


def make_plan(zone, catalog, placements=None):
    if placements is None:
        placements = generate_design("z", zone, catalog, "공원", None, use_llm=False, seed=1).placements
    return build_plan(zone, catalog, "d", placements)


def mock_for(zone, **kw):
    return MockController(start=tuple(zone.start),
                          is_blocked=lambda c: not zone.in_bounds(*c) or zone.terrain(*c) not in WALKABLE_TERRAIN, **kw)


def test_plan_paths_are_contiguous_and_walkable(zone, catalog):
    plan = make_plan(zone, catalog)
    assert plan.tasks and plan.needs_user == 0
    pos = tuple(zone.start)
    for t in plan.tasks:
        for step in t.path:
            assert abs(step[0] - pos[0]) + abs(step[1] - pos[1]) == 1
            assert zone.terrain(*step) in WALKABLE_TERRAIN
            pos = tuple(step)
        assert pos == tuple(t.stand) and pos != tuple(t.target)
    assert sum(plan.required_items.values()) == len(plan.tasks)


def test_far_objects_are_placed_before_blockers(zone, catalog):
    # 가로등 두 개가 (8,0)으로 가는 유일한 통로를 막지만, 먼 꽃을 먼저 심어 해결한다
    plan = make_plan(zone, catalog, [P(item_id="streetlamp", x=8, y=4), P(item_id="streetlamp", x=9, y=4),
                                     P(item_id="flower_tulip_red", x=8, y=0)])
    assert plan.needs_user == 0 and plan.tasks[0].item_id == "flower_tulip_red"


def test_unreachable_target_needs_user(zone, catalog):
    zone.tiles[4][8] = zone.tiles[4][9] = "water"  # 강 건너편이 완전히 고립됨
    plan = make_plan(zone, catalog, [P(item_id="flower_tulip_red", x=8, y=0), P(item_id="path_stone", x=3, y=5)])
    blocked = [t for t in plan.tasks if t.status == "needs_user"]
    assert plan.needs_user == 1 and blocked[0].target == (8, 0) and blocked[0].stand is None
    out = Executor().run(zone, plan)
    assert out.skipped == [blocked[0].id] and len(out.completed) == 1


def test_dry_run_sends_nothing(zone, catalog):
    plan = make_plan(zone, catalog)
    out = Executor().run(zone, plan)  # 기본값이 dry_run
    assert out.status == "completed" and len(out.completed) == len(plan.tasks)
    assert any(c.op == "press" for c in out.commands)


def test_mock_run_verifies_position(zone, catalog):
    plan = make_plan(zone, catalog)
    ctrl = mock_for(zone)
    out = Executor().run(zone, plan, ctrl, ctrl, dry_run=False)
    assert out.status == "completed", out.message
    assert out.final_position == ctrl.position == tuple(plan.tasks[-1].stand)
    assert sum(1 for e in ctrl.log if e[0] == "press") == len(plan.tasks)
    assert ctrl.log[-1] == ("release_all",) and not ctrl.connected


def test_missed_input_is_retried(zone, catalog):
    plan = make_plan(zone, catalog)
    ctrl = mock_for(zone, slip_moves={1})
    out = Executor().run(zone, plan, ctrl, ctrl, dry_run=False)
    assert out.status == "completed" and any(c.note == "재시도" for c in out.commands)


def test_persistent_failure_stops(zone, catalog):
    plan = make_plan(zone, catalog)
    ctrl = mock_for(zone, slip_moves={1, 2, 3})
    out = Executor().run(zone, plan, ctrl, ctrl, dry_run=False)
    assert out.status == "failed" and not out.completed


def test_low_confidence_stops(zone, catalog):
    ctrl = mock_for(zone, confidence=0.5)
    out = Executor().run(zone, make_plan(zone, catalog), ctrl, ctrl, dry_run=False)
    assert out.status == "failed" and "신뢰도" in out.message and not any(e[0] == "move" for e in ctrl.log)


def test_emergency_stop_and_timeout(zone, catalog):
    plan = make_plan(zone, catalog)
    ev = threading.Event()
    ev.set()
    assert Executor(ev).run(zone, plan).status == "stopped"
    ticks = iter(range(0, 10_000, 5))
    out = Executor(clock=lambda: next(ticks)).run(zone, plan, timeout_s=12)
    assert out.status == "timeout" and len(out.completed) < len(plan.tasks)


def test_live_run_requires_controller(zone, catalog):
    with pytest.raises(ValueError):
        Executor().run(zone, make_plan(zone, catalog), dry_run=False)


def test_mock_controller_basics():
    c = MockController(start=(1, 1), is_blocked=lambda p: p == (3, 1))
    with pytest.raises(RuntimeError):
        c.press(Button.A)
    c.connect()
    c.move(Direction.RIGHT, 750)  # 3칸 요청, (3,1)에서 막힘
    assert c.position == (2, 1)
    c.move(Direction.UP, 80)  # 짧은 입력은 방향만
    assert c.position == (2, 1) and c.observe().facing == Direction.UP
    assert c.get_status()["connected"] is True

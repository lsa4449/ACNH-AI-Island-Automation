"""작업 실행기 (규칙 기반 상태 머신).

AI는 버튼을 만들지 않는다. 계획(Task)을 받아 OBSERVE → ACT → VERIFY 순서로
짧은 명령만 내보내고, 매 명령 전에 긴급 정지와 타임아웃을 확인한다.

주의: PLACE_SEQUENCE와 타이밍 값은 자리표시자이며 실제 게임에서 검증되지 않았다.
"""
from __future__ import annotations

import threading
import time
from typing import Protocol

from backend.app.schemas.design import Command, Plan, ZoneIn
from switch_worker.controller.base import Button, ControllerAdapter, Direction, Observation

VERIFIED_ON_HARDWARE = False
TILE_MS = 250  # 한 칸 이동 입력 시간 (MockController 모델과 동일, 실측 필요)
TURN_MS = 80  # 제자리 방향 전환 입력 시간 (실측 필요)
PLACE_SEQUENCE: list[tuple[Button, int]] = [(Button.A, 100)]  # 자리표시자
MIN_CONFIDENCE = 0.8
MAX_RETRIES = 2

_DELTA = {(0, -1): Direction.UP, (0, 1): Direction.DOWN, (-1, 0): Direction.LEFT, (1, 0): Direction.RIGHT}


class Observer(Protocol):
    def observe(self) -> Observation: ...


class RunOutcome:
    def __init__(self) -> None:
        self.status = "completed"
        self.message = ""
        self.completed: list[int] = []
        self.skipped: list[int] = []
        self.commands: list[Command] = []
        self.final_position: tuple[int, int] | None = None


class _Abort(Exception):
    def __init__(self, status: str, message: str) -> None:
        self.status, self.message = status, message


class Executor:
    def __init__(self, stop_event: threading.Event | None = None, clock=time.monotonic) -> None:
        self.stop_event = stop_event or threading.Event()
        self._clock = clock

    def stop(self) -> None:
        self.stop_event.set()

    def run(
        self,
        zone: ZoneIn,
        plan: Plan,
        controller: ControllerAdapter | None = None,
        observer: Observer | None = None,
        dry_run: bool = True,
        timeout_s: float = 30.0,
    ) -> RunOutcome:
        out = RunOutcome()
        live = not dry_run
        if live and (controller is None or observer is None):
            raise ValueError("실제 실행에는 controller와 observer가 필요합니다")
        deadline = self._clock() + timeout_s
        pos = tuple(zone.start)

        def guard() -> None:
            if self.stop_event.is_set():
                raise _Abort("stopped", "긴급 정지 요청으로 중단했습니다")
            if self._clock() > deadline:
                raise _Abort("timeout", f"{timeout_s}초 타임아웃")

        def emit(task_id: int, op: str, arg: str, ms: int, note: str = "") -> None:
            out.commands.append(Command(task_id=task_id, op=op, arg=arg, duration_ms=ms, note=note))

        def observe() -> Observation:
            obs = observer.observe()
            if obs.confidence < MIN_CONFIDENCE:
                raise _Abort("failed", f"인식 신뢰도 {obs.confidence:.2f} < {MIN_CONFIDENCE}: 실행 중지")
            return obs

        try:
            if live:
                controller.connect()
                if observe().position != pos:
                    raise _Abort("failed", "시작 위치가 계획과 다릅니다")
            for task in plan.tasks:
                guard()
                if task.status != "planned":
                    out.skipped.append(task.id)
                    continue
                for step in task.path:
                    direction = _DELTA[(step[0] - pos[0], step[1] - pos[1])]
                    for attempt in range(MAX_RETRIES + 1):
                        guard()
                        emit(task.id, "move", direction.value, TILE_MS, "재시도" if attempt else "")
                        if not live:
                            break
                        controller.move(direction, TILE_MS)
                        seen = observe().position
                        if seen == tuple(step):
                            break
                        if seen != pos:
                            raise _Abort("failed", f"예상 밖 위치 {seen} (기대 {tuple(step)})")
                    else:
                        raise _Abort("failed", f"{tuple(step)}로 이동하지 못했습니다")
                    pos = tuple(step)
                guard()
                facing = Direction(task.facing)
                emit(task.id, "turn", facing.value, TURN_MS)
                if live:
                    controller.move(facing, TURN_MS)
                    obs = observe()
                    if obs.position != pos or obs.facing != facing:
                        raise _Abort("failed", "방향 전환 검증 실패")
                for button, ms in PLACE_SEQUENCE:
                    guard()
                    emit(task.id, "press", button.value, ms, f"place {task.item_id} (미검증 시퀀스)")
                    if live:
                        controller.press(button, ms)
                # 설치 결과의 화면 검증은 Phase 4에서 Vision 엔진으로 구현한다.
                out.completed.append(task.id)
        except _Abort as e:
            out.status, out.message = e.status, e.message
        finally:
            if live and controller is not None:
                controller.release_all()
                controller.disconnect()
        out.final_position = pos
        return out

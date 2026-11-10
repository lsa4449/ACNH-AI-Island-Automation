"""MockController: 실제 스위치 없이 자동화 흐름을 검증하기 위한 시뮬레이터.

단순 모델: tile_ms 미만의 입력은 방향 전환만, 그 이상은 (duration // tile_ms)칸 이동.
이 타이밍 모델은 실제 게임을 측정한 값이 아니다.
"""
from __future__ import annotations

from typing import Callable

from switch_worker.controller.base import Button, ControllerAdapter, Direction, Observation

_DELTA = {Direction.UP: (0, -1), Direction.DOWN: (0, 1), Direction.LEFT: (-1, 0), Direction.RIGHT: (1, 0)}


class MockController(ControllerAdapter):
    def __init__(
        self,
        start: tuple[int, int] = (0, 0),
        tile_ms: int = 250,
        is_blocked: Callable[[tuple[int, int]], bool] | None = None,
        slip_moves: set[int] | None = None,
        confidence: float = 1.0,
    ) -> None:
        self.position = start
        self.facing = Direction.DOWN
        self.tile_ms = tile_ms
        self.is_blocked = is_blocked or (lambda c: False)
        self.slip_moves = slip_moves or set()  # 이 순번의 이동 입력은 무시(입력 누락 재현)
        self.confidence = confidence
        self.connected = False
        self.log: list[tuple] = []
        self._moves = 0

    def connect(self) -> None:
        self.connected = True

    def disconnect(self) -> None:
        self.release_all()
        self.connected = False

    def _require(self) -> None:
        if not self.connected:
            raise RuntimeError("MockController가 연결되지 않았습니다")

    def press(self, button: Button, duration_ms: int = 100) -> None:
        self._require()
        self.log.append(("press", Button(button).value, duration_ms))

    def move(self, direction: Direction, duration_ms: int) -> None:
        self._require()
        direction = Direction(direction)
        self.log.append(("move", direction.value, duration_ms))
        self._moves += 1
        if self._moves in self.slip_moves:
            return
        self.facing = direction
        dx, dy = _DELTA[direction]
        for _ in range(duration_ms // self.tile_ms):
            nxt = (self.position[0] + dx, self.position[1] + dy)
            if self.is_blocked(nxt):
                break
            self.position = nxt

    def release_all(self) -> None:
        self.log.append(("release_all",))

    def get_status(self) -> dict:
        return {"type": "mock", "connected": self.connected, "commands": len(self.log)}

    def observe(self) -> Observation:
        return Observation(position=self.position, facing=self.facing, confidence=self.confidence)

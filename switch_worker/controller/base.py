"""컨트롤러 어댑터 인터페이스. 하드웨어 구현(ESP32-S3 등)은 이 인터페이스 뒤에 숨긴다."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum


class Button(str, Enum):
    A = "A"
    B = "B"
    X = "X"
    Y = "Y"
    L = "L"
    R = "R"
    ZL = "ZL"
    ZR = "ZR"
    PLUS = "PLUS"
    MINUS = "MINUS"
    HOME = "HOME"
    DPAD_UP = "DPAD_UP"
    DPAD_DOWN = "DPAD_DOWN"
    DPAD_LEFT = "DPAD_LEFT"
    DPAD_RIGHT = "DPAD_RIGHT"


class Direction(str, Enum):
    UP = "up"
    DOWN = "down"
    LEFT = "left"
    RIGHT = "right"


@dataclass
class Observation:
    """화면 관찰 결과. Phase 3에서 Vision 엔진이 같은 형태로 제공한다."""
    position: tuple[int, int]
    facing: Direction
    confidence: float


class ControllerAdapter(ABC):
    @abstractmethod
    def connect(self) -> None: ...

    @abstractmethod
    def disconnect(self) -> None: ...

    @abstractmethod
    def press(self, button: Button, duration_ms: int = 100) -> None: ...

    @abstractmethod
    def move(self, direction: Direction, duration_ms: int) -> None: ...

    @abstractmethod
    def release_all(self) -> None: ...

    @abstractmethod
    def get_status(self) -> dict: ...

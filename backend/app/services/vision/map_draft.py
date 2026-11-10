"""지도 이미지 → 타일 격자 "초안" (실험적).

이미지를 cols x rows 격자로 나누고 칸마다 HSV 색상 비율로 잔디/물/모래를 추정한다.
임계값은 실제 게임 지도 스크린샷으로 보정된 값이 아니다. 건물·절벽 구분은 하지 않으며
신뢰도가 낮은 칸은 unknown으로 남겨 사용자가 직접 확정하도록 한다.
"""
from __future__ import annotations

import cv2
import numpy as np

from backend.app.schemas.design import Terrain, ZoneIn

MIN_CONFIDENCE = 0.6
# OpenCV HSV: H 0~179
_RANGES = {
    Terrain.GRASS: ((35, 40, 40), (85, 255, 255)),
    Terrain.WATER: ((86, 40, 40), (130, 255, 255)),
    Terrain.SAND: ((15, 30, 120), (34, 255, 255)),
}


def draft_zone_from_image(data: bytes, cols: int, rows: int, name: str) -> ZoneIn:
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("이미지를 읽을 수 없습니다")
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    h, w = hsv.shape[:2]
    if cols > w or rows > h:
        raise ValueError("격자가 이미지 해상도보다 촘촘합니다")
    masks = {t: cv2.inRange(hsv, np.array(lo), np.array(hi)) > 0 for t, (lo, hi) in _RANGES.items()}
    tiles: list[list[Terrain]] = []
    conf: list[list[float]] = []
    for r in range(rows):
        y0, y1 = r * h // rows, (r + 1) * h // rows
        trow, crow = [], []
        for c in range(cols):
            x0, x1 = c * w // cols, (c + 1) * w // cols
            ratios = {t: float(m[y0:y1, x0:x1].mean()) for t, m in masks.items()}
            best = max(ratios, key=ratios.get)
            score = round(ratios[best], 3)
            trow.append(best if score >= MIN_CONFIDENCE else Terrain.UNKNOWN)
            crow.append(score)
        tiles.append(trow)
        conf.append(crow)
    start = next(((x, y) for y in range(rows) for x in range(cols) if tiles[y][x] == Terrain.GRASS), (0, 0))
    return ZoneIn(name=name, width=cols, height=rows, tiles=tiles, start=start, confidence=conf)

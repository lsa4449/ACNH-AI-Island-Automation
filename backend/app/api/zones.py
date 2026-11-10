"""구역(타일 격자) 및 지도 이미지 API."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from backend.app.api.deps import get_repo, get_settings, zone_or_404
from backend.app.config import Settings
from backend.app.db.database import Repository, new_id
from backend.app.schemas.design import Zone, ZoneIn
from backend.app.services.vision.map_draft import draft_zone_from_image

router = APIRouter(prefix="/api", tags=["zones"])
MAX_UPLOAD_BYTES = 10 * 1024 * 1024


@router.get("/zones", response_model=list[Zone])
def list_zones(repo: Repository = Depends(get_repo)):
    return repo.list_zones()


@router.post("/zones", response_model=Zone, status_code=201)
def create_zone(zone: ZoneIn, repo: Repository = Depends(get_repo)):
    return repo.save_zone(zone)


@router.post("/zones/sample", response_model=Zone, status_code=201)
def create_sample_zone(repo: Repository = Depends(get_repo), settings: Settings = Depends(get_settings)):
    raw = json.loads(settings.sample_zone_path.read_text(encoding="utf-8"))
    return repo.save_zone(ZoneIn.model_validate(raw))


@router.get("/zones/{zone_id}", response_model=Zone)
def get_zone(zone_id: str, repo: Repository = Depends(get_repo)):
    return zone_or_404(repo, zone_id)


@router.put("/zones/{zone_id}", response_model=Zone)
def update_zone(zone_id: str, zone: ZoneIn, repo: Repository = Depends(get_repo)):
    """타일 수동 보정용. 지도 인식 초안의 unknown 칸을 여기서 확정한다."""
    zone_or_404(repo, zone_id)
    return repo.save_zone(zone, zone_id)


@router.post("/maps/draft-zone", response_model=Zone, status_code=201)
async def draft_zone(
    file: UploadFile = File(...),
    cols: int = Form(..., ge=1, le=112),
    rows: int = Form(..., ge=1, le=96),
    name: str = Form("지도 초안"),
    repo: Repository = Depends(get_repo),
    settings: Settings = Depends(get_settings),
):
    """지도 이미지를 저장하고 색상 기반 타일 초안을 만든다(실험적, 수동 보정 전제)."""
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "이미지가 너무 큽니다 (최대 10MB)")
    try:
        zone_in = draft_zone_from_image(data, cols, rows, name)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    zone = repo.save_zone(zone_in, new_id())
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    (settings.upload_dir / f"{zone.id}.img").write_bytes(data)
    return zone

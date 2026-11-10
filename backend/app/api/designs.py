"""설계 생성/조회/검증/계획/시뮬레이션 API."""
from __future__ import annotations

import threading

from fastapi import APIRouter, Depends, HTTPException, Request

from backend.app.api.deps import design_or_404, get_catalog, get_ollama, get_repo, zone_or_404
from backend.app.db.database import Repository, new_id, now_iso
from backend.app.schemas.design import (
    WALKABLE_TERRAIN,
    CatalogItem,
    Design,
    DesignRequest,
    Plan,
    RunRequest,
    RunResult,
    ValidateRequest,
    ValidationResult,
)
from backend.app.services.ai.designer import generate_design
from backend.app.services.ai.ollama_client import OllamaClient
from backend.app.services.automation.executor import Executor
from backend.app.services.planner.catalog import Catalog
from backend.app.services.planner.task_planner import build_plan
from backend.app.services.planner.validator import validate
from switch_worker.controller.mock import MockController

router = APIRouter(prefix="/api", tags=["designs"])


@router.get("/catalog", response_model=list[CatalogItem])
def get_catalog_items(catalog: Catalog = Depends(get_catalog)):
    return catalog.all()


@router.post("/designs", response_model=Design, status_code=201)
def create_design(req: DesignRequest, repo: Repository = Depends(get_repo),
                  catalog: Catalog = Depends(get_catalog), ollama: OllamaClient = Depends(get_ollama)):
    zone = zone_or_404(repo, req.zone_id)
    design = generate_design(zone.id, zone, catalog, req.prompt, ollama, req.use_llm, req.seed)
    return repo.save_design(design)


@router.get("/designs", response_model=list[Design])
def list_designs(zone_id: str | None = None, repo: Repository = Depends(get_repo)):
    return repo.list_designs(zone_id)


@router.get("/designs/{design_id}", response_model=Design)
def get_design(design_id: str, repo: Repository = Depends(get_repo)):
    return design_or_404(repo, design_id)


@router.post("/designs/validate", response_model=ValidationResult)
def validate_placements(req: ValidateRequest, repo: Repository = Depends(get_repo),
                        catalog: Catalog = Depends(get_catalog)):
    return validate(zone_or_404(repo, req.zone_id), catalog, req.placements)


def _plan(repo: Repository, catalog: Catalog, design: Design) -> tuple:
    zone = zone_or_404(repo, design.zone_id)
    return zone, build_plan(zone, catalog, design.id, design.placements)


@router.get("/designs/{design_id}/plan", response_model=Plan)
def get_plan(design_id: str, repo: Repository = Depends(get_repo), catalog: Catalog = Depends(get_catalog)):
    return _plan(repo, catalog, design_or_404(repo, design_id))[1]


@router.post("/designs/{design_id}/run", response_model=RunResult)
def run_design(design_id: str, req: RunRequest, request: Request, repo: Repository = Depends(get_repo),
               catalog: Catalog = Depends(get_catalog)):
    """dry_run=true: 명령 목록만 계산. dry_run=false: MockController에서 실행(실제 스위치 아님)."""
    design = design_or_404(repo, design_id)
    zone, plan = _plan(repo, catalog, design)
    stop_event: threading.Event = request.app.state.stop_event
    if stop_event.is_set():
        raise HTTPException(409, "긴급 정지 상태입니다. /api/runs/reset 호출 후 다시 실행하세요")
    controller = None
    if not req.dry_run:
        controller = MockController(
            start=tuple(zone.start),
            is_blocked=lambda c: not zone.in_bounds(*c) or zone.terrain(*c) not in WALKABLE_TERRAIN,
        )
    out = Executor(stop_event).run(zone, plan, controller, controller, req.dry_run, req.timeout_s)
    return repo.save_run(RunResult(
        id=new_id(), design_id=design.id, dry_run=req.dry_run, status=out.status, message=out.message,
        completed_tasks=out.completed, skipped_tasks=out.skipped, commands=out.commands,
        final_position=out.final_position, created_at=now_iso(),
    ))


@router.get("/designs/{design_id}/runs", response_model=list[RunResult])
def list_runs(design_id: str, repo: Repository = Depends(get_repo)):
    return repo.list_runs(design_id)


@router.post("/runs/stop")
def emergency_stop(request: Request):
    request.app.state.stop_event.set()
    return {"stopped": True}


@router.post("/runs/reset")
def reset_stop(request: Request):
    request.app.state.stop_event.clear()
    return {"stopped": False}

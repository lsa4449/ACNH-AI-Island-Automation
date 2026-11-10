"""요청별 의존성."""
from __future__ import annotations

from fastapi import HTTPException, Request

from backend.app.config import Settings
from backend.app.db.database import Repository
from backend.app.schemas.design import Design, Zone
from backend.app.services.ai.ollama_client import OllamaClient
from backend.app.services.planner.catalog import Catalog


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_repo(request: Request) -> Repository:
    return request.app.state.repo


def get_catalog(request: Request) -> Catalog:
    return request.app.state.catalog


def get_ollama(request: Request) -> OllamaClient:
    return request.app.state.ollama


def zone_or_404(repo: Repository, zone_id: str) -> Zone:
    zone = repo.get_zone(zone_id)
    if zone is None:
        raise HTTPException(404, "구역을 찾을 수 없습니다")
    return zone


def design_or_404(repo: Repository, design_id: str) -> Design:
    design = repo.get_design(design_id)
    if design is None:
        raise HTTPException(404, "설계를 찾을 수 없습니다")
    return design

"""FastAPI 진입점. 실행: uvicorn backend.app.main:app --reload (프로젝트 루트에서)"""
from __future__ import annotations

import threading

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api import designs, zones
from backend.app.config import Settings, load_settings
from backend.app.db.database import Repository
from backend.app.services.ai.ollama_client import OllamaClient
from backend.app.services.planner.catalog import Catalog


def create_app(settings: Settings | None = None, ollama: OllamaClient | None = None) -> FastAPI:
    settings = settings or load_settings()
    app = FastAPI(title="ACNH AI Island Automation", version="0.1.0")
    app.state.settings = settings
    app.state.repo = Repository(settings.db_path)
    app.state.catalog = Catalog.load(settings.catalog_path)
    app.state.ollama = ollama or OllamaClient(settings.ollama_url, settings.ollama_model,
                                              settings.ollama_timeout_s)
    app.state.stop_event = threading.Event()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(zones.router)
    app.include_router(designs.router)

    @app.get("/api/health")
    def health():
        return {
            "status": "ok",
            "phase": 1,
            "dry_run_default": True,
            "controllers": ["mock"],
            "ollama": app.state.ollama.status(),
            "emergency_stop": app.state.stop_event.is_set(),
        }

    return app


app = create_app()

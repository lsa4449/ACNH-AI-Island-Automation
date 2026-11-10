import json

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.app.config import ROOT, Settings
from backend.app.main import create_app
from backend.app.schemas.design import ZoneIn
from backend.app.services.ai.ollama_client import OllamaClient
from backend.app.services.planner.catalog import Catalog


@pytest.fixture
def catalog() -> Catalog:
    return Catalog.load(ROOT / "data" / "catalog.json")


@pytest.fixture
def zone() -> ZoneIn:
    return ZoneIn.model_validate(json.loads((ROOT / "data" / "sample_zone_10x10.json").read_text("utf-8")))


def fake_ollama(content: dict | None) -> OllamaClient:
    """실제 Ollama 없이 /api/chat, /api/tags 응답을 흉내낸다. None이면 연결 실패."""
    def handler(request: httpx.Request) -> httpx.Response:
        if content is None:
            raise httpx.ConnectError("connection refused")
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "fake"}]})
        body = json.loads(request.content)
        assert body["stream"] is False and "format" in body
        return httpx.Response(200, json={"message": {"content": json.dumps(content)}})

    return OllamaClient("http://ollama.test", "fake", transport=httpx.MockTransport(handler))


@pytest.fixture
def client(tmp_path):
    settings = Settings(data_dir=tmp_path, db_path=tmp_path / "t.db", ollama_url="http://ollama.test",
                        ollama_model="fake", ollama_timeout_s=1)
    return TestClient(create_app(settings, fake_ollama(None)))

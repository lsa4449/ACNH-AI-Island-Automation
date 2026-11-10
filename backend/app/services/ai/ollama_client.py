"""Ollama 로컬 REST API 클라이언트.

사용 엔드포인트 (Ollama 공식 API):
- GET  /api/tags  : 설치된 모델 목록
- POST /api/chat  : stream=false, format=<JSON 스키마> 로 구조화 출력 요청
"""
from __future__ import annotations

import json

import httpx


class OllamaError(RuntimeError):
    pass


class OllamaClient:
    def __init__(self, base_url: str, model: str, timeout_s: float = 120.0,
                 transport: httpx.BaseTransport | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._timeout = timeout_s
        self._transport = transport

    def _client(self, timeout: float) -> httpx.Client:
        return httpx.Client(base_url=self.base_url, timeout=timeout, transport=self._transport)

    def status(self) -> dict:
        try:
            with self._client(3.0) as c:
                r = c.get("/api/tags")
                r.raise_for_status()
                models = [m.get("name", "") for m in r.json().get("models", [])]
        except (httpx.HTTPError, ValueError) as e:
            return {"available": False, "model": self.model, "models": [], "error": str(e)}
        return {"available": True, "model": self.model, "models": models}

    def chat_json(self, system: str, user: str, schema: dict) -> dict:
        payload = {
            "model": self.model,
            "stream": False,
            "format": schema,
            "options": {"temperature": 0.4},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }
        try:
            with self._client(self._timeout) as c:
                r = c.post("/api/chat", json=payload)
                r.raise_for_status()
                return json.loads(r.json()["message"]["content"])
        except (httpx.HTTPError, KeyError, ValueError, TypeError) as e:
            raise OllamaError(f"Ollama 호출 실패: {e}") from e

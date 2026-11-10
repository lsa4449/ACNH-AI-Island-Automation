"""환경 변수 기반 설정. 모든 값은 로컬 실행 기준 기본값을 가진다."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    db_path: Path
    ollama_url: str
    ollama_model: str
    ollama_timeout_s: float

    @property
    def catalog_path(self) -> Path:
        return ROOT / "data" / "catalog.json"

    @property
    def sample_zone_path(self) -> Path:
        return ROOT / "data" / "sample_zone_10x10.json"

    @property
    def upload_dir(self) -> Path:
        return self.data_dir / "uploads"


def load_settings() -> Settings:
    data_dir = Path(os.getenv("ACNH_DATA_DIR", ROOT / "data"))
    return Settings(
        data_dir=data_dir,
        db_path=Path(os.getenv("ACNH_DB_PATH", data_dir / "acnh.db")),
        ollama_url=os.getenv("ACNH_OLLAMA_URL", "http://127.0.0.1:11434"),
        ollama_model=os.getenv("ACNH_OLLAMA_MODEL", "llama3.2"),
        ollama_timeout_s=float(os.getenv("ACNH_OLLAMA_TIMEOUT_S", "120")),
    )

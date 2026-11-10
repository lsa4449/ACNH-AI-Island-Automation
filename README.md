# ACNH AI Island Automation

모여봐요 동물의 숲 섬을 AI가 설계하고, 화면 인식과 컨트롤러 자동화로 시공하는 것을 목표로 하는 개인 프로젝트.

**현재 단계: Phase 1 (하드웨어 없는 설계·시뮬레이션).** 실제 Switch 제어는 아직 구현되지 않았다.

## Phase 1에서 되는 것

- 타일 격자 구역 관리(10×10 샘플 포함), 지도 이미지 → 타일 초안(실험적, 수동 보정 전제)
- 자연어 요청 → 배치 JSON 생성: Ollama 사용, 실패 시 규칙 기반 생성기로 자동 대체
- 배치 규칙 검증(범위, 지형, 겹침, 길 위 식물, 나무 간격)
- 작업 계획(이동 경로, 필요 아이템, 도달 불가 작업은 `needs_user`)
- Dry Run(기본값) 및 MockController 시뮬레이션, 타임아웃·긴급 정지
- React + Konva 2D 설계도

## 설치 및 실행 (Windows PowerShell)

```powershell
cd acnh-auto-island
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt

# 테스트
pytest

# API 서버 (http://127.0.0.1:8000/docs)
uvicorn backend.app.main:app --reload
```

Ollama (선택): https://ollama.com 에서 설치 후

```powershell
ollama pull llama3.2
$env:ACNH_OLLAMA_MODEL = "llama3.2"   # 다른 모델을 쓸 때만 변경
```

프론트엔드 (새 PowerShell 창, Node.js 18+):

```powershell
cd acnh-auto-island\frontend
npm install
npm run dev    # http://localhost:5173
```

## API 빠른 확인

```powershell
$zone = Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/zones/sample
$body = @{ zone_id = $zone.id; prompt = "꽃길과 나무가 있는 작은 공원" } | ConvertTo-Json
$design = Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/designs -ContentType "application/json; charset=utf-8" -Body ([Text.Encoding]::UTF8.GetBytes($body))
Invoke-RestMethod http://127.0.0.1:8000/api/designs/$($design.id)/plan
Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/designs/$($design.id)/run -ContentType "application/json" -Body '{"dry_run": true}'
```

## 구조

```
backend/app/
  main.py, config.py
  api/            zones.py, designs.py, deps.py
  schemas/        design.py            # 모든 구조화 데이터
  db/             database.py          # SQLite
  services/ai/        ollama_client.py, designer.py
  services/planner/   catalog.py, validator.py, task_planner.py
  services/automation/ executor.py     # 상태 머신 (OBSERVE→ACT→VERIFY)
  services/vision/    map_draft.py     # 지도 초안 (실험적)
switch_worker/controller/  base.py (ControllerAdapter), mock.py
frontend/         React + Konva 설계도
data/             catalog.json, sample_zone_10x10.json
tests/            pytest
docs/             feasibility.md, TODO.md
```

`switch_worker/capture`, `firmware/`, `integrations/`는 Phase 2에서 필요해질 때 만든다.

## 환경 변수

| 변수 | 기본값 |
|---|---|
| `ACNH_OLLAMA_URL` | `http://127.0.0.1:11434` |
| `ACNH_OLLAMA_MODEL` | `llama3.2` |
| `ACNH_OLLAMA_TIMEOUT_S` | `120` |
| `ACNH_DATA_DIR` / `ACNH_DB_PATH` | `data/` / `data/acnh.db` |

## 검증 상태

- 검증됨(Linux, Python 3.13): pytest 30개 통과, API 서버 기동, 프론트엔드 빌드 및 화면 동작
- 검증 안 됨: Windows에서의 실행, 실제 Ollama 모델 응답, 실제 게임 지도 이미지, 모든 하드웨어 동작

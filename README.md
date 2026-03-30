# SonarQube Monitor

SonarQube 이슈를 대시보드(프로젝트·모듈·Severity)와 상세 목록으로 보는 도구입니다. **FastAPI** + **Vue 3 / Vite**입니다.

## 빠른 시작

1. **`.env`** (프로젝트 루트): `cp .env.example .env` 후 `SONAR_BASE_URL`, `SONAR_TOKEN` 필수. Sonar 호스트는 **`.env`에만** 두고 코드에는 넣지 않습니다.
2. **백엔드** (포트 `9999`):

   ```bash
   python main.py
   ```

   또는 **uvicorn**으로 직접 실행:

   ```bash
   uvicorn main:app --host 127.0.0.1 --port 9999
   ```

3. **프론트 개발** (포트 `5173`, `/api` → 9999 프록시):

   ```bash
   cd web && npm install && npm run dev
   ```

   브라우저: **http://127.0.0.1:5173**

4. **한 포트로만 쓰기**: `cd web && npm run build` 후 루트에서 `python main.py` 또는 위 `uvicorn` 명령 → **http://127.0.0.1:9999**

## 설정 파일 (`config/`)

| 파일 | 용도 |
|------|------|
| `component_projects.json` | 프로젝트 목록·Sonar `componentKey` |
| `module_grouping.json` | 프로젝트별 모듈 추출(Java `/fims/`·Vue `src/` 등) |
| `dashboard.json` | 대시보드 제목·설명 문구 |

## 주요 API

- `GET /api/health`
- `GET /api/metrics/dashboard` — 대시보드 집계
- `GET /api/issues/search` — Sonar 이슈 검색 프록시

Python 3.11+ 권장.

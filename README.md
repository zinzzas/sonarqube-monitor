# SonarQube Monitor

SonarQube **OPEN 이슈**를 대시보드(프로젝트·모듈·Severity·팀 High risk)와 상세 목록으로 봅니다. **FastAPI** + **Vue 3 / Vite**.

상세 문서 흐름: **[docs/README.md](docs/README.md)** · 배포·실행: **[docs/06_release/deployment-guide.md](docs/06_release/deployment-guide.md)**

---

## 한 줄 요약

| 무엇 | 어떻게 |
|------|--------|
| 백엔드 | `uvicorn main:app --reload --host localhost --port 9999` (Windows는 `hatch run dev` 권장) |
| 프론트 개발 | `cd web && npm install && npm run dev` → **http://localhost:5173** (`/api` → 9999) |
| 한 포트만 | `cd web && npm run build` 후 루트에서 백엔드만 → **http://localhost:9999** |

---

## Windows (PowerShell, Hatch)

**전제:** Python 3.11+ 가 PATH에 있어야 합니다. 없으면 [python.org](https://www.python.org/downloads/windows/) 또는 `winget install Python.Python.3.12` 후 터미널을 다시 엽니다.

1. **Hatch 설치**

   ```powershell
   py -m pip install --user hatch
   ```

   `hatch`를 찾지 못하면 사용자 `Scripts`를 PATH에 추가합니다 (예: `%APPDATA%\Python\Python312\Scripts`).

2. **저장소·환경**

   ```powershell
   git clone <URL> sonarqube-monitor
   cd sonarqube-monitor
   hatch env create
   ```

3. **`.env`** — 루트에 두고 Sonar 접속 정보를 넣습니다. (`notepad .env`)

   | 변수 | 설명 |
   |------|------|
   | `SONAR_BASE_URL` | SonarQube 베이스 URL |
   | `SONAR_TOKEN` | 조회용 토큰 |
   | `SONAR_SAMPLE_COMPONENT_KEYS` | (선택) 기본 component 키 |
   | `HTTP_LOG_LEVEL` | (선택) `off` / `info` / `debug` |
   | `SONAR_HTTPX_TRUST_ENV` | (선택) 프록시 꼬임 시 `false` 검토 |
   | `SONAR_ISSUES_PAGE_SIZE` | (선택) 기본 `200`, 최대 `500` 등 |
   | `SONAR_ISSUES_PAGE_DELAY_MS` | (선택) 페이징 간 지연(ms) |
   | `SONAR_HTTP_*` | (선택) 연결·타임아웃 등 |

   나머지(`SONAR_AUTH`, `SONAR_PROXY` 등)는 `.env` 주석 참고.

4. **백엔드**

   ```powershell
   hatch run dev
   ```

   → **http://localhost:9999** · 헬스: `GET /api/health`

   | 명령 | 비고 |
   |------|------|
   | `hatch run dev` | 권장. `uvicorn` + reload, `localhost:9999` |
   | `hatch run start` | reload + `0.0.0.0:9999` (LAN) |
   | `hatch run serve` | reload 없음 |

   Vite는 `web/vite.config.js`에서 API를 **9999**로 보냅니다. 포트를 바꾸면 Vite 프록시도 같이 맞춥니다.

5. **프론트 (Node LTS + npm)**

   ```powershell
   cd web
   npm install
   npm run dev
   ```

   **http://localhost:5173**

   단일 포트로 쓰려면: `npm run build` 후 상위에서 `hatch run start` 등으로 백엔드만 — **`web/dist`가 있어야** 루트에서 SPA가 뜹니다.

---

## macOS

```bash
cd /path/to/sonarqube-monitor
source .venv/bin/activate   # 또는 hatch / uv로 환경 준비
uvicorn main:app --reload --host localhost --port 9999
```

Hatch 사용 시: `hatch run dev` (Windows와 동일). `.env`는 위 표와 같습니다.

---

## 자주 겪는 문제

| 증상 | 점검 |
|------|------|
| `hatch` 없음 | Scripts 경로·터미널 재시작 |
| Sonar 연결 실패 | VPN, `SONAR_BASE_URL`, 방화벽, `SONAR_SSL_VERIFY` |
| 9999 사용 중 | 다른 프로세스 종료 또는 포트 변경 |
| 빈 화면(9999) | `web`에서 `npm run build`, `web/dist` 존재 여부 |

---

## `config/` 요약

| 파일 | 용도 |
|------|------|
| `component_projects.json` | 프로젝트·Sonar `componentKey` |
| `module_grouping.json` | 모듈 경로 추출 규칙 |
| `dashboard.json` | 대시보드 문구 |
| `module_segment_labels.json` | 라벨·팀 매핑 — [module-segment-labels.md](docs/03_design/module-segment-labels.md) |

---

## API 예시

`GET /api/health` · `GET /api/metrics/dashboard` · `GET /api/issues/search` (Sonar 프록시)

전체: [docs/02_analysis/api-requirements.md](docs/02_analysis/api-requirements.md)

---

## 요구 사항

- **Python** 3.11+ · **Hatch** (Windows 가이드) 또는 동등한 venv
- **Node.js** LTS + npm (프론트 개발·빌드)

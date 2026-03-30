# SonarQube Monitor — 현재 코드베이스 기준

## 목적

SonarQube API로 이슈를 조회·집계해 **대시보드**(프로젝트·모듈·Severity)와 **이슈 상세 목록** UI를 제공한다.

## 스택

- **백엔드**: Python 3.11+, FastAPI, Uvicorn, `httpx` → SonarQube 프록시 및 메트릭 집계
- **프론트**: Vue 3, Vite, Vue Router, Chart.js / vue-chartjs
- **설정**: 프로젝트 루트 `config/*.json`, 환경은 루트 `.env` (`app/core/config.py`)

`pyproject.toml`에 LangChain·Torch 등이 있어도 **현재 앱 경로(`app/`)에서는 미사용**일 수 있다. 실제 동작은 FastAPI + Sonar 클라이언트 + 메트릭 서비스 중심이다.

## 디렉터리 (요약)

```
main.py                 # FastAPI, web/dist 있으면 SPA 동시 제공
app/api/                # issues, metrics, projects, sonar(진단)
app/services/           # sonarqube_client, sonar_api(프록시), metrics_service
app/core/               # config, severity, module_extract, exceptions
config/                 # component_projects, module_grouping, dashboard
web/src/                # Vue: views/DashboardView, IssueListView, router, assets/app.css
```

## Severity 표준

플랫폼 표시: **BLOCKER / HIGH / MEDIUM / LOW / INFO**  
Sonar API: `CRITICAL`→HIGH, `MAJOR`→MEDIUM, `MINOR`→LOW 매핑 (`app/core/severity.py`, `web/src/severity.js`).

## 주요 HTTP API

| 경로 | 역할 |
|------|------|
| `GET /api/health` | 헬스 |
| `GET /api/projects` | `config/component_projects.json` |
| `GET /api/metrics/dashboard` | 집계(요약·byProject·globalModules) |
| `GET /api/issues/search` | Sonar `issues/search` 프록시(쿼리 전달) |
| `GET /api/sonar/*` | 설정 요약·연결 진단(선택) |

## 프론트 라우트

- `/` — 대시보드
- `/issues/:projectId` — 이슈 목록(쿼리 `module`, `severity` 등)

## 확장 시

- 모듈 추출 규칙: **`config/module_grouping.json`** (프로젝트별 프로필)
- 대시보드 카피: **`config/dashboard.json`**
- **민감값(토큰)은 규칙·README에 커밋하지 말 것**

# Architecture Summary

## Persona

- **Architect / 시니어 개발자**: 경계·의존성·확장 포인트
- **DevOps**: 무엇이 배포 단위인지

## Stack

| 층 | 기술 | Why |
|----|------|-----|
| API | FastAPI, Uvicorn | 비동기 Sonar 호출·프록시에 적합 |
| HTTP 클라이언트 | httpx | 연결 풀 재사용 (`sonarqube_client`) |
| UI | Vue 3, Vite, Vue Router | SPA, `web/dist`를 백엔드가 서빙 가능 |
| 차트 | Chart.js / vue-chartjs | 대시보드 시각화 |
| 설정 | `config/*.json`, `.env` | 코드 없이 프로젝트·용어 변경 |

> `pyproject.toml`에 다른 의존성이 있어도 **런타임 핵심 경로**는 `app/` FastAPI + Sonar + metrics 중심이다.

## Directory (요약)

```
main.py              # FastAPI, /api 우선, web/dist 있으면 SPA
app/api/             # health, metrics, issues, projects, sonar 진단, admin
app/services/        # metrics_service, sonarqube_issues_fetch, issue_snapshot_store,
                     # issue_snapshot_query, issue_snapshot_coordinator, sonar_api, …
app/core/            # config, severity, module_extract, team_high_risk, …
config/              # component_projects, module_grouping, module_segment_labels, dashboard
data/issue_snapshots/# 런타임 디스크 캐시(기본, .gitignore) — 집계·이슈 목록 정합
web/src/             # DashboardView, IssueListView, app.css, router
```

## 데이터 흐름 (요약)

| 층 | 역할 |
|----|------|
| Sonar API | OPEN 이슈 수집(페이징·10k 분할은 `sonarqube_issues_fetch`) |
| 메모리 | 프로젝트별 집계 결과 + 조합된 대시보드 응답 — TTL |
| 디스크 | 프로젝트별 `issues_full` / `issues_bhm` + `manifest.json`(`severityFloor`) — TTL·floor 불일치 시 폐기 |
| 무효화 | 팀 매핑 PUT · `POST /api/admin/invalidate-cache` · 서버 재시작(메모리만 초기화, 디스크는 TTL/floor) |

## Severity 표준

플랫폼 표시: **BLOCKER / HIGH / MEDIUM / LOW / INFO**  
Sonar → 표준: `CRITICAL`→HIGH, `MAJOR`→MEDIUM, `MINOR`→LOW (`app/core/severity.py`, `web/src/severity.js`).

## See also

- [../03_design/system-architecture.md](../03_design/system-architecture.md) — 모듈 추출·집계 상세
- [../02_analysis/api-requirements.md](../02_analysis/api-requirements.md) — 엔드포인트 표

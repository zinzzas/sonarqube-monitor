# Frontend UI & Routing

## Persona

- **Frontend Developer**
- **UX-aware PM** — 화면 흐름만

## Routing

- `/` → `DashboardView`
- `/issues/:projectId` → `IssueListView`
- `/admin/team-mapping` → 팀 매핑(관리)

## Dashboard — 프로젝트 범위

| 콤보 | API `projectId` | 집계 |
|------|-----------------|------|
| **전체 (ALL)** | `all` | `component_projects.json` **전체 id** 기준 병합. `componentKey`가 비어 있으면 Sonar 호출 없이 0건. Sonar는 **OPEN** 중 **BLOCKER·HIGH·MEDIUM**(API: BLOCKER, CRITICAL, MAJOR)만 수집. |
| 개별 프로젝트 | 해당 id | **OPEN** 전 심각도 — 백엔드는 `componentKey`가 있는 행만 Sonar 집계에 포함. |

**UI**: ALL 선택 시 상단 안내 배너, KPI 칩·파이·엑셀형 표는 **B·H·M**만 노출. Module×Severity 스택 차트와 모듈 상세 블록은 숨김(모듈은 프로젝트 단일 선택 시만).

**Why**: 단일 SPA, 백엔드가 `web/dist` 서빙 시 **딥링크**는 `index.html` 폴백 필요(구현은 `main.py`).

## Issue list entry (대시보드 → 목록)

| 출처 | 쿼리 | 비고 |
|------|------|------|
| Severity 엑셀형 | `?severity=` (선택) | `module` 없음 |
| Module × Severity | `?module=&severity=` | `module`은 **클라이언트**에서 `issueMatchesModuleFilter` |

**설계 원칙**

1. API 재조회 트리거는 **`useIssueListApiTrigger`** 에만 — `route.query.module`을 의존성에 넣지 않는다 (목록 비는 버그 방지).
2. 쿼리 조립: `web/src/lib/sonarIssuesSearchParams.js`
3. 기본 정렬 **`severity_desc`** — 첫 페이지만 볼 때 HIGH가 아래로 밀리는 현상 완화.

## Design tokens & CSS

- **단일 출처**: `web/src/assets/app.css`
- 히어로·카드·엑셀형·차트·대시보드 전용 클래스 — [coding-guidelines.md](../04_development/coding-guidelines.md) 의 Web UI 절 참고

## See also

- [../04_development/coding-guidelines.md](../04_development/coding-guidelines.md)
- [../00_overview/architecture-summary.md](../00_overview/architecture-summary.md)

# 이슈 목록 진입 경로 (대시보드 → `/issues/:projectId`)

## 두 가지 UX

| 출처 | 대시보드 영역 | 쿼리 특징 | Sonar API |
|------|----------------|-----------|-----------|
| **A. Severity 엑셀형** | 프로젝트별 Severity (엑셀형) | `?severity=` (선택), `module` 없음 | `componentKeys` + 필터만 |
| **B. Module × Severity** | 프로젝트별 Module × Severity | `?module=<경로>&severity=` (선택) | **A와 동일** (`module` 미전송) |

`module`은 `web/src/module.js`의 `issueMatchesModuleFilter`로 **로드된 행만** 클라이언트 필터링한다.

## 설계 원칙

1. **API 재조회**는 `web/src/composables/useIssueListApiTrigger.js`에서만 트리거한다. 의존성에 **`route.query.module`을 넣지 않는다.** (과거: `module` 변경 시 `loadFirst` 재호출 → 목록이 비는 재현)
2. **모듈 자동 추가 로드**는 `IssueListView.vue`의 기존 `watch`(모듈 필터 + `loadMore`)가 담당한다.
3. **쿼리 조립**은 `web/src/lib/sonarIssuesSearchParams.js` (집계와 동일한 최소 규칙).

## 관련 소스

- `web/src/views/DashboardView.vue` — `goIssues(projectId, query)` (`nav` 쿼리로 출처 표시)
- `web/src/views/IssueListView.vue` — `moduleFilter`, `displayedIssues`, 모듈 자동 fetch watch
- `web/src/composables/useSonarIssuesPaging.js` — 페이징·fetch
- `web/src/module.js` — 경로 매칭

# API Design

## Persona

- **Architect / Senior Dev**

## Principles

1. **Browser → 이 앱** 만 호출하고, Sonar URL/토큰은 서버 측에 둔다.
2. **집계**는 전량 수집 후 디스크 스냅샷 + TTL; **이슈 목록**은 스냅샷이 있으면 동일 데이터로 로컬 검색, 없으면 Sonar 페이징 프록시.
3. **Admin** API는 토큰 보호 시에만 쓰기 허용. `POST /api/admin/invalidate-cache` 는 팀 매핑 저장과 동일하게 집계·스냅샷을 비운다.

## Dashboard metrics

- `GET /api/metrics/dashboard?projectId=...`  
- 응답: summary, byProject, globalModules 등 — 상세 필드는 코드 `metrics_service` 기준.

## Issues search

- `GET /api/issues/search` — 스냅샷(`issues_full`)이 TTL·`severityFloor` 에 맞으면 `issue_snapshot_query` 로 필터·정렬·`teamId`; 없거나 미지원이면 Sonar `sonar_api` 프록시.
- 대시보드 집계와 **동일** `issues_full` 을 쓰므로, 스냅샷 모드에서 목록 건수·심각도 분포가 집계와 어긋나지 않는다(같은 하한·같은 소스).

## Issues fetch (internal)

- 대시보드 집계용 전량 수집은 **`sonarqube_issues_fetch.fetch_all_issues`** — Sonar 10k 제약 시 severity·날짜 분할.

## Why

엔드포인트마다 **책임**을 나눠 프록시와 집계 로직이 섞이지 않게 한다.

## See also

- [../02_analysis/api-requirements.md](../02_analysis/api-requirements.md)

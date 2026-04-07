# API Design

## Persona

- **Architect / Senior Dev**

## Principles

1. **Browser → 이 앱** 만 호출하고, Sonar URL/토큰은 서버 측에 둔다.
2. **집계**와 **이슈 목록**은 용도가 다름 — 전자는 전량·캐시, 후자는 페이징·프록시.
3. **Admin** API는 토큰 보호 시에만 쓰기 허용.

## Dashboard metrics

- `GET /api/metrics/dashboard?projectId=...`  
- 응답: summary, byProject, globalModules 등 — 상세 필드는 코드 `metrics_service` 기준.

## Issues proxy

- `GET /api/issues/search` — 쿼리를 Sonar에 그대로 전달 (`sonar_api`).

## Issues fetch (internal)

- 대시보드 집계용 전량 수집은 **`sonarqube_issues_fetch.fetch_all_issues`** — Sonar 10k 제약 시 severity·날짜 분할.

## Why

엔드포인트마다 **책임**을 나눠 프록시와 집계 로직이 섞이지 않게 한다.

## See also

- [../02_analysis/api-requirements.md](../02_analysis/api-requirements.md)

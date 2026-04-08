# API Requirements

## Persona

- **백엔드 개발자** — 계약 정의
- **프론트 개발자** — 호출 파라미터

## Internal (이 앱이 제공)

| Method | Path | 역할 |
|--------|------|------|
| GET | `/api/health` | 헬스 |
| GET | `/api/projects` | `component_projects.json` |
| GET | `/api/metrics/dashboard` | 집계(요약·byProject·globalModules 등) |
| GET | `/api/issues/search` | 스냅샷 있으면 로컬 필터·페이징(대시보드와 동일 이슈 세트); 없으면 Sonar 프록시. `?source=live` 는 항상 Sonar |
| GET | `/api/sonar/*` | 설정·연결 진단(선택) |
| GET/PUT | `/api/admin/team-mapping` | 팀 매핑(토큰 보호 시) |
| POST | `/api/admin/invalidate-cache` | 집계·스냅샷 무효화(팀 매핑 PUT과 동일 효과, 토큰 규칙 동일) |

## Upstream (SonarQube)

| 용도 | 대표 경로 |
|------|-----------|
| 이슈 검색 | `GET /api/issues/search` |
| (진단) | `api/system/status` 등 — `sonar` 라우트 참고 |

## Contract Notes

- **민감값**: 토큰은 `.env`만 — 문서·규칙에 실제 토큰 금지.
- **이슈 수집**: 대시보드 집계는 서버에서 **전량 페이징**(10k 제약은 서비스 레이어에서 분할). 디스크 스냅샷 `manifest.json` 에 `severityFloor` 를 기록해 `component_projects.json` 하한 변경 시 TTL 전에도 스냅샷을 쓰지 않음.
- **이슈 목록**: 브라우저는 `/api/issues/search`만 호출. 스냅샷 적중 시 Sonar 추가 호출 없이 필터; 내부 전용 `source`·`teamId`는 업스트림에 전달하지 않음.

## Why

프론트·백·Sonar **세 축**에서 같은 파라미터 이름(`componentKeys`, `severities` 등)을 맞추기 위한 단일 참조.

## See also

- [../03_design/api-design.md](../03_design/api-design.md)
- [../00_overview/architecture-summary.md](../00_overview/architecture-summary.md)

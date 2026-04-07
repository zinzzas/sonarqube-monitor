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
| GET | `/api/issues/search` | Sonar `issues/search` 프록시(쿼리 전달) |
| GET | `/api/sonar/*` | 설정·연결 진단(선택) |
| GET/PUT | `/api/admin/team-mapping` | 팀 매핑(토큰 보호 시) |

## Upstream (SonarQube)

| 용도 | 대표 경로 |
|------|-----------|
| 이슈 검색 | `GET /api/issues/search` |
| (진단) | `api/system/status` 등 — `sonar` 라우트 참고 |

## Contract Notes

- **민감값**: 토큰은 `.env`만 — 문서·규칙에 실제 토큰 금지.
- **이슈 수집**: 대시보드 집계는 서버에서 **전량 페이징**(10k 제약은 서비스 레이어에서 분할).
- **프록시**: 브라우저는 주로 `/api/issues/search`만 호출하고 Sonar URL은 노출하지 않는 것을 권장.

## Why

프론트·백·Sonar **세 축**에서 같은 파라미터 이름(`componentKeys`, `severities` 등)을 맞추기 위한 단일 참조.

## See also

- [../03_design/api-design.md](../03_design/api-design.md)
- [../00_overview/architecture-summary.md](../00_overview/architecture-summary.md)

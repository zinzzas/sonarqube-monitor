# Module Structure

## Persona

- **Developer**

## Backend (`app/`)

| 경로 | 책임 |
|------|------|
| `api/` | HTTP 라우트 |
| `services/` | Sonar 클라이언트, 메트릭, 이슈 fetch |
| `core/` | 설정·도메인 순수 로직(module_extract, team_high_risk, severity) |
| `config/` (패키지) | JSON 로더 |

## Frontend (`web/src/`)

| 경로 | 책임 |
|------|------|
| `views/` | 페이지 단위 |
| `composables/` | 이슈 페이징·API 트리거 등 |
| `lib/` | Sonar 쿼리·모듈 라벨 유틸 |
| `assets/app.css` | 글로벌 스타일 |

## Config repo root (`config/`)

런타임·빌드에 포함되는 JSON — **스키마 문서**는 [../03_design/](../03_design/) 참고.

## Why

신규 기능 추가 시 **어느 층에 넣을지** 빠르게 정한다.

## See also

- [../00_overview/architecture-summary.md](../00_overview/architecture-summary.md)

# Coding Guidelines

## Persona

- **Developer**

## Python

- **타입**: 신규 코드는 타입 힌트 유지 (`app/` 스타일 따름).
- **설정**: `app/core/config.py` / pydantic-settings — 비밀은 `.env`.
- **Sonar 호출**: `app/services/sonarqube_client.py` 공유 클라이언트 사용.
- **이슈 전량 수집**: `app/services/sonarqube_issues_fetch.py` — 10k 분할 로직은 여기만.

## Vue

- **스타일**: `web/src/assets/app.css` 토큰·클래스 재사용, 화면별 임의 색상 최소화.
- **심각도**: `web/src/severity.js` 와 백엔드 `severity.py` 매핑 일치 유지.

## Web UI (대시보드·이슈)

- 레이아웃 셸: `.app` → `.wrap` 패턴.
- 신규 화면: [../03_design/frontend-ui.md](../03_design/frontend-ui.md) 체크리스트.

## Why

팀 없이도 **같은 레포 안 관례**로 리뷰 비용을 줄인다.

## See also

- [module-structure.md](./module-structure.md)
- [web-dashboard-css.md](./web-dashboard-css.md) — 대시보드 CSS 패턴

# Web Dashboard — CSS 패턴

## Persona

- **Frontend Developer**

## Why

`web/src/assets/app.css` 가 **단일 출처**다. 새 화면은 토큰·기존 클래스를 재사용한다.

## 폰트

- 본문·제목: Plus Jakarta Sans  
- 코드: IBM Plex Mono  
- `web/index.html` — `preconnect` + Google Fonts

## 레이아웃

| 클래스 | 역할 |
|--------|------|
| `.app` | 루트 `min-height: 100vh` |
| `.app__bg` | 메시 배경 `aria-hidden` |
| `.wrap` | `max-width: 1280px` 중앙 |

## 토큰 (`:root`)

`--bg-*`, `--text-*`, `--border`, `--accent*`, `--shadow-*`, `--radius-*`, 테이블 높이 변수 등.

## 블록 패턴 (요약)

히어로 `.hero`, 카드 `.card`, 필터 `.filter-group`, 칩 `.chk-chip`, 테이블 `.table-panel` / `.tbl`, 대시보드 `.dashboard` / `.excel-block` / `.kpi` …

## 테이블 높이

`.table-panel` — `max-height: min(92vh, calc(...))` 로 **약 15 데이터 행**이 보이도록.

## See also

- [../03_design/frontend-ui.md](../03_design/frontend-ui.md)
- 소스: `web/src/assets/app.css`, `web/src/views/DashboardView.vue`, `IssueListView.vue`

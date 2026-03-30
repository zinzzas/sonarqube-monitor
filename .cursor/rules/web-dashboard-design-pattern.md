# Web 대시보드 디자인 패턴 (Dashboard + Issues)

메인 대시보드·추가 화면을 만들 때 **동일한 시각·구조 패턴**을 따른다. 구현의 단일 출처는 `web/src/assets/app.css` 이다.

---

## 1. 벤치마크

- SonarQube / GitHub Issues 스타일 이슈·데이터 테이블
- Linear / Vercel 계열 SaaS: 메시 배경, 카드, 타이포, CTA

---

## 2. 폰트 (`web/index.html`)

- **본문·제목**: Plus Jakarta Sans  
- **코드·모노**: IBM Plex Mono  
- `preconnect` + Google Fonts 링크 유지

---

## 3. 레이아웃 셸

| 클래스 | 역할 |
|--------|------|
| `.app` | 루트, `min-height: 100vh` |
| `.app__bg` | 고정 전체 배경, `aria-hidden="true"`, 메시 그라데이션만 |
| `.wrap` | `max-width: 1280px`, 중앙 정렬, 좌우 `clamp` 패딩 |

새 페이지도 **동일 셸**으로 감싼다.

---

## 4. 디자인 토큰 (`:root`)

- 색: `--bg-base`, `--bg-elevated`, `--bg-subtle`, `--text`, `--text-muted`, `--border`, `--accent`, `--accent-soft`, `--accent-ring`
- 그림자: `--shadow-sm`, `--shadow-md`
- 반경: `--radius-sm|md|lg`
- 테이블 높이: `--table-panel-visible-rows` (기본 15), `--table-row-estimate`, `--table-head-estimate`

메인 대시보드에서 색을 바꿀 때는 **토큰만 조정**하고 컴포넌트에 하드코딩하지 않는다.

---

## 5. 블록 패턴

| 블록 | 클래스 | 용도 |
|------|--------|------|
| 히어로 | `.hero`, `.hero__eyebrow`, `.hero__sub` | 페이지 상단 제목·설명 |
| 카드 | `.card`, `.card--filters`, `.card__head`, `.card__title` | 필터·설정 묶음 |
| 필터 행 | `.filter-group`, `.filter-title` | 라벨 + 컨트롤 한 줄 |
| 칩 체크 | `.chk-chip`, `.chk-chip__face` | 다중 선택 (Severity/Status 등) |
| 필드 | `.field`, `.select`, `.narrow` | 입력·콤보 |
| 액션 | `.toolbar`, `.btn` | 주요 버튼 (그라데이션 CTA) |
| 통계 | `.stats`, `.stat-pill`, `.stat-dot` | 건수·상태 요약 |
| 알림 | `.err` | 오류 메시지 |
| 테이블 | `.table-panel`, `.tbl` | 스크롤 카드 + 표 |
| 심각도 | `.pill`, `.sev-*` | 이슈 심각도 뱃지 |
| 무한 스크롤 로딩 | `.load-more-overlay`, `.load-more-overlay__logo`, `.load-more-overlay__img` | `public/load-more-chevron.png` · 배경 투명 · `border-radius: var(--radius-lg)` + `Teleport` |

---

## 6. 테이블 스크롤 영역 높이

- `.table-panel`의 `max-height`는  
  `min(92vh, calc(var(--table-head-estimate) + var(--table-panel-visible-rows) * var(--table-row-estimate)))`  
  로 두어 **데이터 행 약 15줄**이 한 화면에 들어가도록 한다.
- 행에 긴 메시지로 줄이 늘어나면 실제 보이는 “줄 수”는 줄어든다. 더 촘촘히 보이게 하려면 `--table-row-estimate`를 약간 줄인다.

---

## 7. 라우팅·페이지

- `web/src/router.js`: `/` → `DashboardView`, `/issues/:projectId` → `IssueListView`
- 루트 셸: `web/src/App.vue` — `.app` / `.app__bg` + `<router-view />`
- 스타일 단일 출처: `web/src/assets/app.css`

## 8. 대시보드 전용 패턴

| 클래스 | 용도 |
|--------|------|
| `.dashboard`, `.dash-summary`, `.kpi` | 요약 KPI |
| `.dash-charts`, `.chart-card`, `.chart-box` | Chart.js 영역 |
| `.excel-block`, `.excel`, `.excel__th--risk`, `.excel__cell--risk` | 엑셀형 표 |
| `.card__head--actions`, `.btn--head`, `.btn--secondary` | 제목 줄 우측 액션 |
| `.module-block`, `.module-block__title` | 통합 Module×Severity 블록 내 프로젝트 구획 |
| `.dashboard .dash-chart-last` | 차트와 첫 표 사이 간격 |

히어로 문구는 `config/dashboard.json`에서 로드(`web/src/config/dashboardConfig.js`).

## 9. 신규 화면 체크리스트

1. `main.js`: `app.css` + `vue-router` 등록.
2. `.app` → `.wrap` (또는 동일 토큰) 유지.
3. 카드·버튼·테이블은 기존 클래스 재사용.
4. 새 토큰은 `:root`에만 추가.

## 10. 관련 파일

- 스타일: `web/src/assets/app.css`
- 폰트: `web/index.html`
- 참고: `web/src/views/DashboardView.vue`, `web/src/views/IssueListView.vue`

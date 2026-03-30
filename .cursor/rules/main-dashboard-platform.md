# 대시보드 집계 — Module & Severity

## 목적

프로젝트별·모듈별·Severity별 이슈 통계를 PM 의사결정용으로 보여준다.

## 모듈 그룹핑 (구현 단일 출처)

**`config/module_grouping.json`** 에서 프로필(`java_fims`, `vue_src` 등)과 `projectProfiles`(프로젝트 id → 프로필)를 정의한다.

- **Java 예**: `split_after`, `after: "/fims/"`, `segment_index: 0` → `/fims/{module}/…` 의 module
- **Vue 예**: `after: "src/"` 등 → 첫 경로 세그먼트(예: views, components)

백엔드: `app/core/module_extract.py`  
프론트(필터): `web/src/module.js` (동일 규칙)

`split_after` 프로필: 루트 `defaults.splitAfterModuleRows`(또는 프로필별 `defaultModuleRows` 재정의)로 플랫 표 기본 행 순서를 잡는다. `path_tree`는 집계 키만 사용한다.

## 집계 API

- `GET /api/metrics/dashboard` — summary, byProject, globalModules  
- 서버 메모리 캐시(TTL) 사용 가능 → 설정 변경 후 반영이 늦으면 백엔드 재시작

## UI

- 차트(Pie, Bar, Stacked) + 엑셀형 표 + CSV 다운로드(섹션별)
- 숫자 클릭 → `/issues/:projectId?module=&severity=` (상세 목록에서 클라이언트 필터)

## 참고 (레거시 예시 경로)

Java 컴포넌트 예: `…/fims-lib-auth/…/us/fims/auth/…` → `/fims/` 기준으로 module 추출.

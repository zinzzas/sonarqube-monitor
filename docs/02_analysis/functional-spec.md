# Functional Specification

## Persona

- **Planner / 개발자** — 무엇을 만들지 합의
- **QA** — 범위·엣지 확인

## Features

| ID | 기능 | 설명 |
|----|------|------|
| F1 | 프로젝트 목록 | `component_projects.json` 기반 노출 |
| F2 | 대시보드 집계 | OPEN 이슈 수집 후 Severity·모듈·차트·팀 High risk — 메모리·디스크 스냅샷·TTL·`severityFloor` 정합 |
| F3 | 이슈 검색 | `GET /api/issues/search` — 스냅샷 적중 시 로컬 검색, 아니면 Sonar 프록시(`?source=live` 는 항상 Sonar) |
| F4 | 모듈 경로 추출 | `module_grouping.json` 프로필별 `path_tree` / `split_after` |
| F5 | 세그먼트 한글 라벨 | `module_segment_labels.json` 표시 치환, exclude는 모듈·차트만 |
| F6 | 팀 매핑 | HIGH RISK 팀 버킷, precedence + fallback |
| F7 | Sonar 진단 | `/api/sonar/*` 연결 확인(선택) |
| F8 | 이슈 전량 수집 | Sonar 10k 제약 시 severity·날짜 분할 (`sonarqube_issues_fetch`) |

## Edge Cases

| 상황 | 동작 |
|------|------|
| Sonar `paging.total` > 10k | 프로브 후 severity(및 필요 시 날짜) 분할 수집 |
| `paging.total` 없음 | 선형 페이징 + 상한/400 시 분할로 폴백 |
| 팀 매칭 경로 토큰 없음 | fallback(ETC) 버킷 |
| 모듈 exclude | Severity 총합에는 포함, 모듈·스택 축에서만 제외 |
| `component_projects.json` 의 `severityFloor` 변경 | 디스크 `manifest.severityFloor` 와 불일치 시 스냅샷 미사용 → 재수집 |
| 구형 스냅샷(manifest 에 floor 없음) | 로드 시 stale 처리 후 재수집으로 이행 |
| 이슈에 `component` 없고 `mainComponent.key` 만 있음 | 집계·팀·이슈 목록 모두 `issue_component_key` 규칙으로 통일 |
| 팀 매핑 저장 / 캐시 초기화 API | 메모리·디스크 스냅샷 전부 무효화 |

## Why

기능 목록을 **API·화면과 1:1로 추적**해 변경 시 회귀 범위를 정한다.

## See also

- [api-requirements.md](./api-requirements.md)
- [../03_design/system-architecture.md](../03_design/system-architecture.md)

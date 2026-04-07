# Functional Specification

## Persona

- **Planner / 개발자** — 무엇을 만들지 합의
- **QA** — 범위·엣지 확인

## Features

| ID | 기능 | 설명 |
|----|------|------|
| F1 | 프로젝트 목록 | `component_projects.json` 기반 노출 |
| F2 | 대시보드 집계 | OPEN 이슈 전량 수집 후 Severity·모듈·차트·팀 High risk |
| F3 | 이슈 검색 프록시 | `GET /api/issues/search` → Sonar 업스트림 |
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

## Why

기능 목록을 **API·화면과 1:1로 추적**해 변경 시 회귀 범위를 정한다.

## See also

- [api-requirements.md](./api-requirements.md)
- [../03_design/system-architecture.md](../03_design/system-architecture.md)

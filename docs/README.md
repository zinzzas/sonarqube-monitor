# 문서 인덱스 (SonarQube Monitor)

**목적**: 기획 → 분석 → 설계 → 개발 → 테스트 → 출시 흐름으로 **누가 무엇을 읽는지** 분리하고, Cursor·AI가 맥락을 따라가도록 **작은 파일 + 링크**로 유지한다.

## 저장소 문서 위치 (단일 출처)

| 위치 | 역할 |
|------|------|
| [README.md](../README.md) (루트) | 클론·Hatch·`.env` 표·빠른 실행 — **온보딩** |
| **`docs/`** (본 트리) | 기획~출시 **본문** |
| [`.cursor/rules/`](../.cursor/rules/) | Cursor 규칙 **요약** — 상세는 항상 `docs/` 링크 |

**통합·삭제한 것**: 예전 `docs/module-segment-labels-design.md`, `docs/issue-list-navigation.md` 는 각각 [03_design/module-segment-labels.md](./03_design/module-segment-labels.md), [03_design/frontend-ui.md](./03_design/frontend-ui.md) 로 흡수 후 파일 제거.

## 품질 체크리스트

| 기준 | 이 저장소 |
|------|-----------|
| 단계별 분리 | `00`~`06` 폴더 |
| 페르소나 | 각 문서 상단 **Persona** 블록 |
| 문서 간 연결 | 아래 표 + 각 문서 하단 **See also** |
| 중복 최소화 | 요구(01) vs 설계(03) 분리 — 같은 문장을 두 곳에 두지 않음 |
| AI 친화 | 한 파일 한 주제, 길면 하위 파일로 분할 |

## 흐름 맵

```
01 Planning (왜) → 02 Analysis (무엇) → 03 Design (어떻게)
    → 04 Development (구현 규칙) → 05 Testing → 06 Release
```

| 단계 | 경로 | 핵심 질문 |
|------|------|-----------|
| Overview | [00_overview](./00_overview/) | 무엇이며 스택·경계는? |
| Planning | [01_planning](./01_planning/) | 왜 만들고 누가 쓰나? |
| Analysis | [02_analysis](./02_analysis/) | 기능·API·엣지는? |
| Design | [03_design](./03_design/) | 구조·UI·데이터 설계는? |
| Development | [04_development](./04_development/) | 코드는 어디에 어떻게? |
| Testing | [05_testing](./05_testing/) | 무엇을 어떻게 검증? |
| Release | [06_release](./06_release/) | 어떻게 띄우고 되돌리나? |

## 빠른 링크

- [프로젝트 개요](./00_overview/project-overview.md)
- [아키텍처 요약](./00_overview/architecture-summary.md) — 스냅샷·캐시·무효화
- [비즈니스 요구](./01_planning/business-requirements.md)
- [기능 명세](./02_analysis/functional-spec.md)
- [API 요구·목록](./02_analysis/api-requirements.md)
- [시스템 설계](./03_design/system-architecture.md)
- [프론트 UI·라우팅](./03_design/frontend-ui.md)
- [대시보드 → 이슈 목록 딥링크 설계](./03_design/dashboard-issue-deep-links.md)
- [모듈 세그먼트 라벨](./03_design/module-segment-labels.md)
- [배포 가이드](./06_release/deployment-guide.md) — 운영·출시 유의·스모크
- [대시보드 CSS 패턴](./04_development/web-dashboard-css.md)

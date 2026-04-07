# Module Segment Labels (Design)

## Persona

- **Architect / PL** — 용어·경로 기준 합의
- **설정 담당** — JSON 편집

## Goal

`module_grouping.json`으로 나온 **경로 세그먼트**에 **한글 표시명**을 입힌다. 집계 **키는 바꾸지 않고** 표시 직전에 치환한다.

## Why

- 영문 약어(`portal`, `domain`)는 이해자마다 다름 → **설정으로만** 바꾼다.
- 트리 형상(앵커·깊이)은 **`module_grouping`** 단일 출처, 본 레이어는 **표시만** 담당한다.

## Files

- `config/module_segment_labels.json` — `maps.<profileId>`, `teamMapping`, `exclude`
- 프론트: `web/src/lib/moduleSegmentLabels.js` (빌드 시 번들 가능)

## Exclude (모듈·스택만)

`exclude`에 걸린 경로는 **모듈 롤업·스택 차트**에서 빠지고, **Severity 합계·이슈 원본 수**는 유지한다.

## Personas (stakeholder view)

| 역할 | 관심사 |
|------|--------|
| PM | 차트·표에 한글 용어 |
| PL | 팀 합의 용어표 유지 |
| 개발 | 매핑 누락 시 `unknown`·원문 확인 경로 |

## Open points

- 누적 경로 표기 스타일, 대소문자 정규화 — 구현·운영에서 고정.

## See also

- [system-architecture.md](./system-architecture.md)  
- 구 설계 원문은 본 문서로 **흡수**됨 (중복 파일 제거).

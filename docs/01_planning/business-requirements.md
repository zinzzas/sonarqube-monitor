# Business Requirements

## Persona

- **PM / Business Owner**
- **제품 담당**

## Goal

조직에서 Sonar 이슈를 **프로젝트·모듈·심각도** 관점으로 한 화면에서 비교하고, 필요 시 **상세 이슈 목록**으로 내려가 확인할 수 있게 한다.

## Why (결정 배경)

| 배경 | 설명 |
|------|------|
| 다중 프로젝트 | 여러 `componentKey`를 설정 파일로 묶어 **한 대시보드**에서 본다. |
| 업무 용어 | 경로 세그먼트(`portal`, `domain` 등)를 **한글 라벨**로 바꿔 PL/PM이 읽기 쉽게 한다. |
| High risk 팀 | BLOCKER·HIGH를 **팀 규칙**에 따라 버킷팅해 리스크 관리 회의에 쓴다. |

## User Scenario (요약)

1. 담당자가 대시보드를 연다 → 프로젝트별 Severity·모듈·차트를 본다.
2. 숫자/행을 클릭한다 → `/issues/:projectId`에서 이슈 목록을 본다 (필요 시 클라이언트에서 모듈 필터).
3. (선택) 관리자가 팀 매핑 JSON을 수정한다 → 저장 후 집계가 새 규칙을 따른다.

## Success Metrics (제안)

- 설정된 프로젝트에 대해 **집계 API가 오류 없이** 응답한다.
- Sonar 장애 시 **에러가 UI/API에 노출**되고 숨겨지지 않는다.

## Out of Scope

- Sonar **스캔 실행·품질 게이트** 설정
- 이 저장소 외부 **티켓 시스템**과의 자동 연동

## See also

- [user-scenarios.md](./user-scenarios.md)
- [../02_analysis/functional-spec.md](../02_analysis/functional-spec.md)

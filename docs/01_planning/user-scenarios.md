# User Scenarios

## Persona

- **PM / PL**: 대시보드에서 수치 확인
- **개발자**: 이슈 목록에서 규칙·파일 경로 확인

## Scenario A — 대시보드 요약

**Given** `config/component_projects.json`에 프로젝트가 등록되어 있다.  
**When** 사용자가 `/`에 접속한다.  
**Then** 프로젝트별 Severity 합계, 모듈·스택 차트, (설정 시) 팀별 High risk가 보인다.

## Scenario B — 이슈 목록으로 드릴다운

**Given** 대시보드에서 특정 프로젝트·심각도(또는 모듈)를 클릭한다.  
**When** `/issues/:projectId?severity=&module=` 로 이동한다.  
**Then** Sonar `issues/search`와 동일한 필터 체계로 목록이 로드되고, `module`은 클라이언트에서 추가 필터될 수 있다.

## Scenario C — 팀 매핑 관리

**Given** 관리 토큰이 설정되어 있다.  
**When** `/admin/team-mapping`에서 규칙을 저장한다.  
**Then** JSON이 갱신되고 메트릭 캐시가 무효화되어 이후 집계에 반영된다.

## Why (시나리오 분리)

대시보드는 **전량 집계(캐시 가능)** , 이슈 목록은 **페이징·정렬 UX**가 달라 화면·API 사용 패턴을 나눈다.

## See also

- [../03_design/frontend-ui.md](../03_design/frontend-ui.md) — 라우팅·쿼리 설계
- [../02_analysis/functional-spec.md](../02_analysis/functional-spec.md)

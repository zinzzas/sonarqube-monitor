# Project Overview

## Persona

- **PM / 제품**: 제품 범위·우선순위 파악
- **신규 개발자**: 저장소가 무엇을 하는지 5분 안에 파악

## Goal

SonarQube **OPEN 이슈**를 조회·집계해 **대시보드**(프로젝트·모듈·Severity·팀 High risk)와 **이슈 상세 목록**을 제공한다.

## Why

- Sonar UI만으로는 **여러 프로젝트·모듈 단위** 비교와 **내부 용어(한글 라벨)** 반영이 번거롭다.
- 이 앱은 **설정 JSON + 백엔드 집계 + Vue**로 그 갭을 메운다.

## Scope (비범위 포함)

| 포함 | 제외 |
|------|------|
| Sonar 이슈 조회·프록시, 메트릭 집계, SPA | Sonar 서버 자체 운영, 분석 스캔 실행 |
| `config/*.json` 기반 멀티 프로젝트 | 별도 DB — 영속 저장소 없음 |

## Success Metrics (예시)

- 대시보드가 **설정된 프로젝트** 기준으로 집계를 표시한다.
- 이슈 목록이 Sonar와 **동일 필터 규칙**으로 동작한다.

## See also

- [architecture-summary.md](./architecture-summary.md) — 스택·디렉터리
- [../01_planning/business-requirements.md](../01_planning/business-requirements.md) — 왜·KPI
- [../06_release/deployment-guide.md](../06_release/deployment-guide.md) — 실행 방법

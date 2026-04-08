# Deployment Guide

## Persona

- **DevOps / Operator**
- **로컬 개발자**

## Production-like (단일 포트)

1. `web/` 에서 `npm install && npm run build` → `web/dist` 생성  
2. 프로젝트 루트 `.env` 설정 (`SONAR_BASE_URL`, `SONAR_TOKEN` 등)  
3. `hatch run serve` 또는 `uvicorn main:app --host 0.0.0.0 --port 9999`  
4. 브라우저에서 루트 URL — API는 동일 오리진 `/api/*`

**Why**: `main.py`가 `web/dist`가 있으면 정적 파일 + `index.html` SPA 폴백을 처리한다.

## Development (분리 포트)

- 백엔드: `hatch run start` (reload) — 기본 `9999`  
- 프론트: `cd web && npm run dev` — Vite가 `/api`를 백엔드로 프록시 (`vite.config.js`)

## Environment variables

상세 표는 **루트 `README.md`** 의 환경 변수 절을 참고한다 (운영 문서와 중복하지 않음).

## 운영·출시 시 유의

| 항목 | 설명 |
|------|------|
| `data/issue_snapshots/` | 런타임에 생성·갱신. 배포 시 쓰기 가능한 볼륨이면 재시작 후에도 TTL 동안 유지. 디스크 부족 시 정리 또는 관리 API로 무효화. |
| 설정 변경 | `component_projects.json` 의 `severityFloor` 변경 시 manifest 와 불일치하면 자동으로 스냅샷을 쓰지 않음. 팀 매핑 변경은 저장 시 또는 `POST /api/admin/invalidate-cache` 로 전체 무효화. |
| 실시간 이슈 | 스냅샷은 집계 주기·TTL에 따름. Sonar 최신만 보려면 이슈 API에 `?source=live`(항상 업스트림). |
| 출시 전 점검 | `hatch run test`(또는 `python -m unittest discover -s tests -p 'test_*.py'`), `cd web && npm run build`, 스테이징에서 Sonar 연결·대시보드·이슈 목록·팀 필터 스모크. |

## See also

- [rollback-strategy.md](./rollback-strategy.md)
- [../../README.md](../../README.md) — Windows Hatch 상세

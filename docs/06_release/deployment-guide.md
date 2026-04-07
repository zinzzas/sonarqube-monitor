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

## See also

- [rollback-strategy.md](./rollback-strategy.md)
- [../../README.md](../../README.md) — Windows Hatch 상세

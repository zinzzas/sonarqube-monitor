# 대시보드 집계 — Cursor 규칙 (요약)

## Persona

- **AI / 백엔드·프론트 개발자**

## 단일 출처

- 모듈 프로필: `config/module_grouping.json` → [docs/03_design/system-architecture.md](../../docs/03_design/system-architecture.md)
- 집계 API: `GET /api/metrics/dashboard` — [docs/02_analysis/api-requirements.md](../../docs/02_analysis/api-requirements.md)
- 이슈 전량 수집·10k 분할: `app/services/sonarqube_issues_fetch.py`

## Why

구 `.cursor/rules` 장문은 **docs로 이전**했다. 집계 변경 시 **metrics_service / sonarqube_issues_fetch** 와 문서를 함께 본다.

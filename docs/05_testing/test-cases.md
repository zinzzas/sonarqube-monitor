# Test Cases (inventory)

## Persona

- **QA / Developer**

## Automated (Python)

| 모듈 | 파일(예) | 내용 |
|------|-----------|------|
| 이슈 fetch | `tests/test_sonarqube_issues_fetch.py` | total>10k severity 분할, 선형, 400 폴백 |
| 팀 매핑 | `tests/test_team_high_risk.py` | 경로 세그먼트·팀 버킷 |
| 관리 API | `tests/test_admin_team_mapping.py` | GET/PUT, 캐시 무효화 |
| SPA | `tests/test_spa_fallback.py` | 딥링크·정적 서빙 |

실행 (프로젝트 루트, venv 권장):

```bash
python -m unittest discover -s tests -p 'test_*.py' -v
```

## Manual / smoke

- `GET /api/health`
- `GET /api/metrics/dashboard` (유효 projectId)
- 빌드 후 `hatch run start` — `http://127.0.0.1:9999` 에서 SPA 로드

## Why

자동화 목록을 **한 곳**에 두어 “뭐가 돌아가는지” AI·신규 인력이 찾기 쉽게 한다.

## See also

- [test-strategy.md](./test-strategy.md)

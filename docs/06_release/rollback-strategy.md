# Rollback Strategy

## Persona

- **DevOps / Operator**

## Application

| 상황 | 조치 |
|------|------|
| 잘못된 배포 | 이전 **커밋**으로 재배포, `web/dist` 재빌드 |
| 잘못된 설정 | `config/*.json` 또는 `.env` 를 이전 버전으로 복구 후 **프로세스 재시작** |

## Data

- DB가 없으므로 **롤백 = 코드·설정·정적 자산** 단위다.
- `module_segment_labels.json` 을 관리 API로 수정한 경우 — **Git 또는 백업 파일**로 되돌린다.

## Cache

- 메트릭은 **인메모리** — 재시작으로 초기화된다.
- 팀 매핑 저장 시 앱이 캐시 무효화를 호출한다 — 이상 시 **서버 재시작**으로 강제 초기화.

## Why

DB 마이그레이션이 없어 롤백이 **단순**하지만, **설정 파일**은 Git으로 추적해야 한다.

## See also

- [deployment-guide.md](./deployment-guide.md)

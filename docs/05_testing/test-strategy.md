# Test Strategy

## Persona

- **QA / Developer**

## Scope

| 층 | 도구 | 범위 |
|----|------|------|
| 백엔드 | `unittest` | API·도메인·fetch 로직 |
| 프론트 | Vitest (`cd web && npm run test`) | `moduleGrouping` 등 순수 JS — 빌드는 `npm run build` |
| Sonar 통합 | 수동 | `.env` + 실제 Sonar |

## Principles

1. **네트워크 없는** 단위 테스트 우선 — Sonar 클라이언트는 mock.
2. **회귀**: 이슈 fetch 10k 분할, 팀 매핑 API 등 **버그가 났던 영역**에 테스트 추가.

## Why

소규모 도구에서 E2E 인프라 비용 대비 **핵심 알고리즘 단위 테스트**가 ROI가 크다.

## See also

- [test-cases.md](./test-cases.md)

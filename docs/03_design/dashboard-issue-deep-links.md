# 대시보드 카운트 → 이슈 목록 딥링크 (설계)

## Persona

- **프론트엔드 / 백엔드** — 집계·목록 일치 유지
- **플랫폼 운영** — 팀 매핑(`module_segment_labels.json`) 변경 시에도 동작 보장

## 목표

대시보드에서 **High risk 합계**, **팀별 High risk 칩** 등을 클릭하면 **이슈 목록**으로 이동하고, **OPEN + 심각도 + (가능하면) 팀**에 맞게 **화면에 보이는 행**이 집계와 같아지게 한다.

## 현재 동작 (기준선)

| 구간 | 방식 |
|------|------|
| 대시보드 → 목록 | `goIssues(projectId, { severity?, module? })` → `/issues/:projectId?...` |
| Sonar `issues/search` | `componentKeys`, `statuses`, `severities`(선택), 정렬 등 — [sonarIssuesSearchParams.js](../../web/src/lib/sonarIssuesSearchParams.js) |
| **모듈** | 쿼리 `module` — **클라이언트만** 필터([IssueListView](../../web/src/views/IssueListView.vue), `issueMatchesModuleFilter`). API 재조회 트리거에 **포함하지 않음**([useIssueListApiTrigger](../../web/src/composables/useIssueListApiTrigger.js)). |
| **팀** | 백엔드 [team_high_risk.py](../../app/core/team_high_risk.py)만 계산. **Sonar API에는 팀 차원 없음.** |

## 제약 (왜 “쉽지 않은지”)

1. **SonarQube는 “팀” 필드를 제공하지 않음.** 팀은 **이슈 `component` 경로** + **`teamMapping` 규칙**으로 **앱이 버킷**한 값이다.
2. 따라서 **팀과 동일한 필터**를 목록에 적용하려면:
   - **앱 내 목록**에서 **이슈마다 경로 세그먼트를 뽑고**, 백엔드와 **동일한 규칙**으로 `teamId`를 계산한 뒤 **클라이언트에서 걸러야** 한다.
3. **Sonar 웹 UI**(`…/project/issues?…`)로 바로 열 경우: URL에 **severities** 등은 버전별로 일부 가능하나, **팀 기준 필터는 재현 불가**에 가깝다. (경로 문자열 검색 API가 아니면)

**결론**: “집계와 같은 데이터만 보기”는 **앱 내 이슈 목록**을 1차 대상으로 두고, Sonar 웹은 **보조 링크**(심각도·OPEN 정도만)로 두는 편이 현실적이다.

## 링크 대상 정의

| 클릭 영역 | 의도 필터 | 비고 |
|-----------|-----------|------|
| High risk **숫자** (BLOCKER+HIGH 합) | OPEN, **BLOCKER + HIGH** (둘 다) | 현재 `?severity=`는 **한 단계**만 반영하는 흐름이 있음 → **다중 심각도** 쿼리 규약 추가 필요(아래). |
| 팀 칩 (예: 공통 65) | 위 + **해당 teamId** | 클라이언트 필터 + 쿼리 `teamId=`(또는 동일 의미 키). |
| “BLOCKER·HIGH OPEN 이슈 있음” 문구 | 위와 동일 | KPI 영역 전체를 버튼으로 감싸거나 숫자만 링크. |

## 쿼리 스키마 (제안)

기존 `severity` 단일값과 호환하면서 확장한다.

| 파라미터 | 예시 | 의미 |
|----------|------|------|
| `severity` | `BLOCKER` | 기존: 단일 심각도만 |
| `severities` | `BLOCKER,HIGH` | **신규**: 표준 심각도 복수(쉼표). 있으면 `severity`보다 우선해 `filterSeverities` 초기화 |
| `teamId` | `shared` | **신규**: `module_segment_labels.json` 의 `teamId` — **표시용 클라이언트 필터** |
| `nav` | 기존 | `severity-excel` / `module-matrix` 등 힌트 유지 |

`IssueListView`에서:

1. `watch(route.query.severities)` 추가 → `filterSeverities`를 파싱된 배열로 설정.
2. `displayedIssues` 계산 시 `teamId`가 있으면 **추가**로 `issueMatchesTeamFilter(row, projectId, teamId)` 적용.

## 팀 매칭 로직 (프론트) — 단일 출처·일치 전략

백엔드 `team_id_for_path_segments` / `_path_segments_for_issue`와 **같은 입력**(component, projectId, profile)에서 **같은 teamId**가 나와야 한다.

**선택지**

| 방안 | 장점 | 단점 |
|------|------|------|
| **A. TypeScript로 규칙 포팅** | 서버 왕복 없음 | `module_grouping` + `teamMapping` + path_tree/split_after **복제** — 변경 시 이중 유지 |
| **B. GET `/api/team/for-issue`** (component, projectId) → teamId | 로직 단일(파이썬) | 이슈 **건수만큼** 호출 불가 → 배치 API 필요 |
| **B′. POST 이슈 목록 일괄 판별** | 정확 | 목록 로드마다 부담 |
| **C. 경로 규칙을 “모듈 prefix 목록”으로 사전 전개** | 필터 단순화 | 팀 규칙이 `first`/`any` 혼합이면 **완전 동치 어려움** |

**권장 (현실적 단계)**:

1. **Phase 1**: `web/src/lib/`에 **경로 세그먼트 추출 + `team_id_for_path_segments` 동등 함수**를 두고, **단위 테스트**를 Python 골든 케이스와 맞춘다(샘플 `component` 문자열·기대 `teamId`).
2. **Phase 2**: 드리프트 방지를 위해 **CI에서** 소량의 **공유 픽스처**로 교차 검증(선택).

데이터 소스:

- `config/module_grouping.json` — 이미 번들 참조([module.js](../../web/src/module.js)).
- `module_segment_labels.json` 의 `teamMapping` — [teamMappingConfig.js](../../web/src/lib/teamMappingConfig.js) 등으로 로드 가능.

## ALL(전체) 범위에서의 제약

- 팀별 숫자는 **여러 프로젝트 componentKey**를 합친 결과다.
- 이슈 목록은 **프로젝트 단위**(`componentKeys` 하나)로만 Sonar를 부른다.
- 따라서 **ALL에서 팀 칩 클릭 시 “한 번에 같은 집계”를 목록으로 재현하는 것은 불가**에 가깝다.

**UI 정책 (제안)**:

- **ALL** 선택 시: 팀 칩·High risk 숫자는 **링크 비활성** + 툴팁 “개별 프로젝트를 선택하면 이슈 목록으로 이동할 수 있습니다.”
- 또는 **프로젝트별로 가장 기여가 큰 한 프로젝트만** 연다 → **오해 소지**가 커서 비권장.

## Sonar 웹 직접 열기 (선택)

이미 [IssueListView](../../web/src/views/IssueListView.vue) 의 `sonarIssueWebUrl` 패턴이 있다. **심각도·OPEN**만 반영한 URL을 보조 링크로 줄 수 있으나, **팀 일치는 포기**한다는 전제를 라벨에 명시.

## 구현 단계 (권장)

1. **High risk → `severities=BLOCKER,HIGH` + OPEN 유지**  
   - `goIssues` / `IssueListView` 초기화·watch 확장.
2. **팀 칩 → `teamId=` + `issueMatchesTeamFilter`**  
   - 포팅 + 골든 테스트.
3. **ALL 시 링크 비활성** 및 문구.
4. (선택) KPI 영역 **포커스·키보드** 접근성.

## 테스트

- **프론트**: 팀 매칭 순수 함수 — 입력 경로 문자열 → `teamId` (Python 기대값과 동일 케이스).
- **E2E**(선택): 대시보드 클릭 → URL 쿼리 → 목록 건수(샘플 목 데이터).

## See also

- [frontend-ui.md](./frontend-ui.md) — 이슈 목록 쿼리·모듈 필터 원칙
- [module-segment-labels.md](./module-segment-labels.md) — 팀 매핑 설정
- `app/core/team_high_risk.py` — 집계 기준 구현

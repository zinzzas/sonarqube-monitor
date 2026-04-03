# 모듈 경로 세그먼트 ↔ 표시명(한글) 매핑 설계

**상태**: 1차 구현 완료 (대시보드 표·스택 차트). 엑셀(CSV) 다운로드는 후속.  
**목적**: `module_grouping.json`의 `path_tree`·`anchorAfter` 이후 트리와 **동일한 기준**으로, 시스템/패키지 **영문 약어 세그먼트**를 **업무용 표시명**(주로 한글)으로 바꿔 대시보드에 노출한다.  
**구현**: `config/module_segment_labels.json` + `web/src/lib/moduleSegmentLabels.js`. **표시(한글)** 는 집계 키를 바꾸지 않고 치환한다. **`exclude`** 는 모듈 롤업·스택 차트 축에서만 경로를 빼며, **Severity 합계·이슈 원본 수**는 그대로다. 매핑 실패 시 한글 칸은 **`unknown`** (스택 차트 축은 `unknown:영문키`).

---

## 1. 배경과 요구

| 항목 | 설명 |
|------|------|
| **문제** | `portal`, `common`, `domain` 같은 **레이어·시스템 약어**는 개발자·PM·PL·관계자에게 **한글 업무명**이 더 직관적일 수 있음. |
| **예시** | `portal` 하위 `common` → **공통**, `domain` → **업무영역**, `external` → **외부 연동**. |
| **제약** | 트리의 **출발점·깊이**는 이미 `module_grouping.json`의 `path_tree` (`anchorAfter`, `maxDepth`, `stripPrefixes` 등)가 결정한다. 매핑은 그 **결과 경로 세그먼트**에만 레이블을 입힌다. |
| **이식성** | 다른 저장소·프로젝트에서도 **JSON만 교체**해 재사용 가능해야 한다. |
| **정렬** | `module_grouping.json`의 **프로필 id**(`java_tree`, `vue_src_tree` 등)와 **1:1로 연결**되는 설정이어야 한다. |

---

## 2. 페르소나별 관점

### 2.1 제품 / PM

- **보이는 것**: 차트·표·트리에서 **영문 세그먼트 대신(또는 병기)** 짧은 **한글 업무명**.
- **기대**: 동일 Sonar 프로젝트라도 **조직·프로젝트 단계**에서 용어집만 바꿔 재배포할 수 있음.
- **리스크**: 용어가 팀마다 다르므로 **코드가 아닌 설정**으로만 관리해야 함.

### 2.2 PL / 개발 리드

- **보이는 것**: 이슈·모듈 필터에서 경로가 **팀 합의 용어**와 맞음.
- **기대**: `anchorAfter` 이후 **1~3 뎁스**까지 팀 구조(시스템 → 레이어 → 세부)를 반영한 매핑 테이블 유지.
- **주의**: Sonar `component` 실제 경로가 바뀌면 **세그먼트 키**도 맞춰 갱신해야 함 (매핑은 자동 추론하지 않음).

### 2.3 개발자

- **보이는 것**: 디버깅 시 **원문 세그먼트**가 필요할 수 있음 → 표시 정책에 **툴팁·접기** 등 “원문 유지” 옵션을 구현 단계에서 검토.
- **기대**: 매핑 누락 시 한글은 **`unknown`**, 영문 경로는 별도 열·차트 축에서 확인.

### 2.4 아키텍트

- **`module_grouping.json`**: 트리 **형상**(어디를 자르고 몇 단까지 볼지)의 단일 출처.
- **본 설계의 JSON**: 그 트리에서 나온 **각 세그먼트 노드**에 대한 **표시 레이블** 레이어. 두 파일은 **프로필 id**로 묶인다.
- **확장**: 향후 `chartStackAnchorAfter`와 **다른 앵커**를 쓰는 경우, 동일 프로필 안에서 **“어느 축에 레이블을 입힐지”**를 스키마 옵션으로 둘 수 있음 (초기 구현에서는 `path_tree` 누적 키와 스택 버킷 중 하나만 지원해도 됨).

### 2.5 설정 / 운영

- **기준정보 입력**: `common` → `공통` 같은 매핑은 **사람이 JSON에 직접** 넣는다 (자동 생성 없음).
- **배포**: 백엔드 `config/` 또는 프론트 번들에 포함되는 JSON — **환경별 diff**는 용어집 파일만 교체하는 방식이 안전.
- **검증(향후)**: 프로필 id 불일치·깨진 중첩 JSON 등 **시작 시 또는 CI**에서 검증 훅을 둘 수 있음.

---

## 3. `module_grouping.json`과의 정렬 관계

| `module_grouping` | 본 매핑 레이어 |
|-------------------|----------------|
| `profiles.<id>.strategy === "path_tree"` | 해당 `<id>`에 대해 **세그먼트 레이블 맵**을 선택할 수 있음. |
| `anchorAfter` | 경로에서 **트리 시작**을 자른 뒤, **첫 세그먼트가 depth 1** (매핑 트리의 루트 자식과 대응). |
| `maxDepth` | 매핑은 **그 깊이를 초과하는 세그먼트**에는 적용하지 않거나, 초과분은 fallback. |
| `projectProfiles` | 프로젝트 → 프로필 id 결정 → **같은 프로필 id**로 레이블 맵 조회. |

**불변 규칙**: 매핑 JSON은 **경로 계산 로직을 복제하지 않는다**. 오직 **이미 계산된 세그먼트 문자열**(예: `portal`, `common`, 누적 키 `portal/common`)을 키로 조회한다.

---

## 4. 제안 파일과 스키마 (초안)

**파일 위치 (제안)**: `config/module_segment_labels.json`  
**이유**: `module_grouping.json`은 트리 규칙에 집중하고, **용어집은 분리**해 PR·리뷰 단위를 나누기 쉽다. (대안: `module_grouping.json` 내부 `segmentLabelsRef`로 외부 파일만 가리키기 — 구현 시 선택.)

### 4.1 최상위

```json
{
  "version": 1,
  "maps": {}
}
```

- **`maps`**: 키 = **`module_grouping.json`의 `profiles` 키**와 동일해야 함 (예: `java_tree`, `vue_src_tree`).

### 4.2 프로필 단위 (`maps.java_tree`)

| 필드 | 의미 |
|------|------|
| `matchMode` (선택) | 기본 `"segment"`: 앵커 이후 경로를 `/`로 나눈 **각 세그먼트**에 레이블. 향후 `"cumulativePath"` 등 확장 가능. |
| `display` (선택) | `"replace"`: UI에 한글만. `"append"`: `한글 (영문)` 병기. |
| `tree` | **중첩 객체**: 각 키 = **경로의 한 단계 세그먼트**(소스와 동일한 대소문자 권장; 조회 시 폴더 정책에 맞춰 정규화 규칙을 구현 단계에서 고정). |
| `tree.<segment>.label` | 사람이 읽는 표시명. |
| `tree.<segment>.children` | 하위 뎁스 (depth 2, 3…). |
| `exclude` (선택) | **모듈 표·스택 차트에서만** 해당 경로 이슈를 제외한다. `java_tree` / `vue_src_tree` 등 **프로필마다 별도** 객체. Sonar 이슈 수·Severity 총합에는 **포함**된다. |

### 4.2.1 `exclude` (모듈 집계 미노출)

| 필드 | 의미 |
|------|------|
| `pathPrefixes` | **디렉터리 트리** 접두: 앵커 이후 상대 경로이 이 문자열과 같거나 `prefix/…` 이면 제외 (`path_tree`). |
| `pathContains` | 경로에 이 부분 문자열이 **포함**되면 제외 (파일·폴더 공통). |
| `firstSegments` | 경로의 **첫 세그먼트**(첫 `/` 전)가 나열 값과 같으면 제외 (예: 루트 디렉터리 `assets` 전체). |
| `fileSuffixes` | **파일명**(마지막 세그먼트)이 이 접미사로 **끝나면** 제외 (예: `.generated.java`). |

**판정 기준**:

- **`strategy === "path_tree"`**: `stripPrefixes`·`anchorAfter` 적용 **직후**의 경로 문자열 (백엔드 `rollup_path_after_anchor`와 동일).
- **`strategy === "split_after"`**: Sonar `component`의 **프로젝트키 제거 후** 전체 상대 경로.

여러 규칙은 **OR** — 하나라도 맞으면 제외. `_note` 키는 설명용으로 무시된다.

### 4.3 예시 (의도에 맞는 최소 샘플)

아래는 **설명용**이며, 실제 키·이름은 프로젝트 경로에 맞게 수정한다.

```json
{
  "version": 1,
  "maps": {
    "java_tree": {
      "display": "replace",
      "tree": {
        "portal": {
          "label": "포털",
          "children": {
            "common": { "label": "공통" },
            "domain": { "label": "업무영역" },
            "external": { "label": "외부 연동" }
          }
        },
        "atm": {
          "label": "ATM"
        }
      }
    },
    "vue_src_tree": {
      "tree": {}
    }
  }
}
```

**해석**:

- 앵커 이후 첫 세그먼트가 `portal`이면 표시 **포털**; 그 아래 `portal/common`이면 **공통** (또는 경로 전체 표기 정책은 구현 시 결정).
- `atm`처럼 **자식 없이** 레이블만 있어도 됨 (뎁스 1).

### 4.4 뎁스 1~3 확장

- **뎁스 1**: `tree.<seg>.label` 만.
- **뎁스 2**: `tree.<parent>.children.<child>.label`.
- **뎁스 3**: `children` 아래에 또 `children` — 스키마는 **재귀적 객체**로 동일 패턴 유지.

매핑에 없는 세그먼트는 **한글 표시 `unknown`** (영문 경로/키는 별도 열·차트 축 `:영문`으로 유지).

**Vue (`vue_src_tree`)**: `src/` 제거 후 첫 세그먼트가 `views`·`components`·`api` 등으로 갈린다. 라벨 트리에 `api`만 있으면 `views/...` 경로는 첫 단계에서 실패한다. 대응: (1) `tree`에 `views`·`components` 등 실제로 나오는 루트 세그먼트를 추가하거나, (2) 구현상 **접두 세그먼트를 건너 뛰고** `api/common`처럼 트리와 맞는 **접미 경로**로 재시도한다 (`views/x/api/common` → `api/common`).

---

## 5. 해석 알고리즘 (구현 시 참고, 비침투)

입력: `module_grouping` 프로필 id, `path_tree`가 만든 **세그먼트 배열** `["portal", "common", ...]` 또는 누적 키 `portal/common`.

1. `maps[profileId]` 없음 → 전 구간 fallback.
2. `tree`에서 순차적으로 `children`을 따라가며 `label` 수집.
3. 중간에 매칭 실패 → 해당 단계부터 fallback (또는 정책: 전체 경로 fallback).

**표시 레이어**: 한글 매핑은 **표시 직전**에만 치환한다. **`exclude`** 는 키 생성·집계에서 **모듈·스택 차트** 만 빼고, Severity 합계는 유지한다.

---

## 6. Vue / Java 공통 원칙

- 동일 **`profiles` id**를 쓰면 **백엔드 집계·프론트 트리**가 같은 용어집을 참조할 수 있음.
- 프론트가 `module_grouping.json`을 이미 import 한다면, **`module_segment_labels.json`도 동일 방식**으로 두어 빌드 시점에 고정하거나, API로 내려주는 방식 중 선택 (구현 단계).

---

## 7. 오픈 이슈 (컨펌 후 구현)

1. **누적 경로 표기**: `portal/common` 한 줄을 **「포털 · 공통」**처럼 붙일지, 트리 노드마다만 바꿀지.
2. **차트 스택(`chart_stack_bucket`)**: 첫 세그먼트만 쓰는 축에 레이블을 입힐지, `chartStackAnchorAfter` 분기 시 별도 `tree`가 필요한지.
3. **대소문자**: Sonar 경로가 `Portal` vs `portal`일 때 정규화 규칙.
4. **파일 분리 vs 단일 JSON**: 팀 규모가 크면 프로필별 파일 분리 (`module_segment_labels/java_tree.json`)도 고려.

---

## 8. 다음 단계

1. 대시보드 **표·그래프** 컨펌 후, CSV/엑셀 다운로드에 동일 규칙 적용.
2. 필요 시 **프로필별** `maps` 키 추가 (`java_fims` 등).

---

## 9. 장기 운영·리팩터 후보 (코드 영향 없음 / 선택)

| 항목 | 설명 |
|------|------|
| **검증 스크립트** | `module_segment_labels.json`의 `maps` 키가 `module_grouping.profiles`와 교집합인지 CI에서 검사. |
| **프로필별 파일 분할** | 저장소가 커지면 `config/module_segment_labels/java_tree.json` 등으로 분리 후 루트에서 merge. |
| **API로 용어집 제공** | 프론트 번들 없이 운영 중 교체하려면 백엔드가 JSON을 서빙하는 옵션. |
| **툴팁** | 표의 `경로` 열에 hover 시 Sonar `component` 전체(선택). |

---

## 변경 이력

| 일자 | 내용 |
|------|------|
| (초안) | 최초 설계안 작성 |
| (구현) | `module_segment_labels.json`, `moduleSegmentLabels.js`, 대시보드 Module 표·스택 차트 반영 |
| (구현) | `maps.<profile>.exclude` — 프로필별 파일/디렉터리 제외, 백엔드 `module_extract`·`metrics_service` 반영 |

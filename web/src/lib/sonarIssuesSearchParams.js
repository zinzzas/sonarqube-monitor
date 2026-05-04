/**
 * Sonar `GET issues/search` 쿼리 — `app/services/metrics_service.py` 의 `_search_params` 와
 * 동일한 최소 집합을 기본으로 한다 (집계와 목록 불일치 방지).
 *
 * - `issueStatuses` 는 프론트에서 넣지 않음 — `collect_issues_search_params` 가 mirror 시 추가.
 * - 심각도는 전부 선택이면 파라미터 생략(Sonar 전체).
 * - 정렬: IssueList 기본은 `severity_desc`(높은 심각도 우선) — 첫 페이지만 볼 때 HIGH/BLOCKER가 보이도록 함.
 */
import {
  SEVERITY_OPTIONS,
  parseSeverityFloor,
  standardSeveritiesAtOrAbove,
} from "../severity.js";

function isAllSeveritiesSelected(selected) {
  if (!selected?.length) return true;
  if (selected.length !== SEVERITY_OPTIONS.length) return false;
  return SEVERITY_OPTIONS.every((s) => selected.includes(s));
}

function shouldOmitSeveritiesParam(filterSeverities, severityFloor) {
  if (parseSeverityFloor(severityFloor) !== "INFO") {
    return false;
  }
  return isAllSeveritiesSelected(filterSeverities);
}

/**
 * @param {object} args
 * @param {string} args.componentKeys
 * @param {number} args.pageIndex 1-based
 * @param {number} args.ps
 * @param {string[]} args.filterSeverities
 * @param {string[]} args.filterStatuses
 * @param {string} args.sortBySeverity '' | severity_desc | component_asc | …
 * @param {(s: string[]) => string} args.severitiesToApiParam
 * @param {string} [args.authorFilter] Sonar `authors` (SCM 로그인, 콤마 구분 복수 가능)
 * @param {string} [args.severityFloor] component_projects `severityFloor` — INFO면 기존 동작, 그 외는 하한 이상만 API 요청
 * @param {string} [args.teamId] 스냅샷 조회 시 서버 팀 필터(웹 `teamIdForIssue` 와 동일 규칙). Sonar 업스트림에는 전달하지 않음(프록시에서 제거).
 * @returns {URLSearchParams}
 */
export function buildSonarIssuesSearchParams(args) {
  const {
    componentKeys,
    pageIndex,
    ps,
    filterSeverities,
    filterStatuses,
    sortBySeverity,
    severitiesToApiParam,
    authorFilter,
    severityFloor,
    teamId,
  } = args;

  const q = new URLSearchParams();
  const ck = String(componentKeys ?? "").trim();
  if (ck) {
    q.set("componentKeys", ck);
  }
  q.set("p", String(pageIndex));
  q.set("ps", String(ps));

  const statuses =
    filterStatuses?.length > 0 ? [...new Set(filterStatuses)].join(",") : "OPEN";
  q.set("statuses", statuses);

  const auth = typeof authorFilter === "string" ? authorFilter.trim() : "";
  if (auth) {
    q.set("authors", auth);
  }

  const tid = typeof teamId === "string" ? teamId.trim() : "";
  if (tid) {
    q.set("teamId", tid);
  }

  const floor = severityFloor ?? "INFO";
  const allowedStd = standardSeveritiesAtOrAbove(floor);
  let effective = (filterSeverities ?? []).filter((s) => allowedStd.includes(s));
  if (effective.length === 0) {
    effective = [...allowedStd];
  }

  if (!shouldOmitSeveritiesParam(filterSeverities ?? [], floor)) {
    const sev = severitiesToApiParam(effective);
    if (sev) {
      q.set("severities", sev);
    }
  }

  const sort = sortBySeverity ?? "";
  if (sort === "severity_desc") {
    q.set("s", "SEVERITY");
    q.set("asc", "false");
  } else if (sort === "severity_asc") {
    q.set("s", "SEVERITY");
    q.set("asc", "true");
  } else if (sort === "creation_desc") {
    q.set("s", "CREATION_DATE");
    q.set("asc", "false");
  } else if (sort === "creation_asc") {
    q.set("s", "CREATION_DATE");
    q.set("asc", "true");
  } else if (sort === "component_asc") {
    q.set("s", "FILE_LINE");
    q.set("asc", "true");
  } else if (sort === "component_desc") {
    q.set("s", "FILE_LINE");
    q.set("asc", "false");
  }

  return q;
}

/**
 * Sonar `GET issues/search` 쿼리 — `app/services/metrics_service.py` 의 `_search_params` 와
 * 동일한 최소 집합을 기본으로 한다 (집계와 목록 불일치 방지).
 *
 * - `issueStatuses` 는 프론트에서 넣지 않음 — `collect_issues_search_params` 가 mirror 시 추가.
 * - 심각도는 전부 선택이면 파라미터 생략(Sonar 전체).
 * - 정렬은 빈 문자열이면 s/asc 생략(Sonar 기본 순서, 첫 페이지 공백 이슈 완화).
 */
import { SEVERITY_OPTIONS } from "../severity.js";

function isAllSeveritiesSelected(selected) {
  if (!selected?.length) return true;
  if (selected.length !== SEVERITY_OPTIONS.length) return false;
  return SEVERITY_OPTIONS.every((s) => selected.includes(s));
}

/**
 * @param {object} args
 * @param {string} args.componentKeys
 * @param {number} args.pageIndex 1-based
 * @param {number} args.ps
 * @param {string[]} args.filterSeverities
 * @param {string[]} args.filterStatuses
 * @param {string} args.sortBySeverity '' | severity_desc | …
 * @param {(s: string[]) => string} args.severitiesToApiParam
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

  if (!isAllSeveritiesSelected(filterSeverities)) {
    const sev = severitiesToApiParam(filterSeverities);
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
  }

  return q;
}

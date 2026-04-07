/**
 * 플랫폼 표준 severity: BLOCKER | HIGH | MEDIUM | LOW | INFO
 * SonarQube API는 CRITICAL / MAJOR / MINOR 등을 사용 → 표시·집계 시 위 표준으로 매핑.
 */
export const SEVERITY_OPTIONS = ["BLOCKER", "HIGH", "MEDIUM", "LOW", "INFO"];

/** 설정·쿼리용 하한 (대소문자 무시, 잘못된 값은 INFO) */
export function parseSeverityFloor(raw) {
  if (raw == null || String(raw).trim() === "") return "INFO";
  const u = String(raw).trim().toUpperCase();
  return SEVERITY_OPTIONS.includes(u) ? u : "INFO";
}

/** floor 이상의 표준 severity 목록 (BLOCKER만, … 전체) */
export function standardSeveritiesAtOrAbove(floor) {
  const f = parseSeverityFloor(floor);
  const idx = SEVERITY_OPTIONS.indexOf(f);
  return SEVERITY_OPTIONS.slice(0, idx + 1);
}

export const STATUS_OPTIONS = ["OPEN", "CONFIRMED", "RESOLVED"];

/** UI 선택값 → SonarQube `severities` 쿼리 파라미터 */
const UI_TO_API = {
  HIGH: "CRITICAL",
  MEDIUM: "MAJOR",
  LOW: "MINOR",
};

export function severitiesToApiParam(selected) {
  if (!selected?.length) return "";
  const parts = selected.map((s) => UI_TO_API[s] ?? s);
  return [...new Set(parts)].join(",");
}

/** Sonar 원시 severity 등급 비교 (impacts 병합 시) */
const SEVERITY_RANK = {
  BLOCKER: 60,
  CRITICAL: 55,
  HIGH: 52,
  MAJOR: 40,
  MEDIUM: 38,
  MINOR: 30,
  LOW: 25,
  INFO: 10,
};

function severityRank(u) {
  const k = String(u ?? "").trim().toUpperCase();
  return SEVERITY_RANK[k] ?? 0;
}

function pickStrongestSeverity(raws) {
  let best = "";
  let bestR = -1;
  for (const r of raws) {
    if (r == null || String(r).trim() === "") continue;
    const u = String(r).trim().toUpperCase();
    const rr = severityRank(u);
    if (rr > bestR) {
      bestR = rr;
      best = u;
    }
  }
  return best;
}

/**
 * Sonar 이슈 객체에서 표시용 severity 원문 추출.
 * - 최상위 `severity` 우선 (레거시)
 * - 비어 있으면 `impacts[].severity` 중 가장 높은 등급 (Sonar 10.2+)
 */
export function resolveIssueSeverityRaw(issue) {
  if (!issue || typeof issue !== "object") return "";
  const top = issue.severity;
  if (top != null && String(top).trim() !== "") {
    return String(top).trim();
  }
  const impacts = issue.impacts;
  if (!Array.isArray(impacts) || impacts.length === 0) return "";
  const fromImpacts = impacts
    .map((x) => (x && typeof x === "object" ? x.severity : null))
    .filter((x) => x != null && String(x).trim() !== "");
  return pickStrongestSeverity(fromImpacts);
}

/** SonarQube 이슈 severity → 표준 표시 문자열 (대소문자 무시) */
export function displaySeverity(raw) {
  if (raw == null || raw === "") return "—";
  const up = String(raw).trim().toUpperCase();
  const m = {
    CRITICAL: "HIGH",
    MAJOR: "MEDIUM",
    MINOR: "LOW",
  };
  return m[up] ?? up;
}

/** 이슈 행 단위 표시 (severity + impacts) */
export function displaySeverityForIssue(issue) {
  return displaySeverity(resolveIssueSeverityRaw(issue));
}

/** IssueList pill 클래스용 */
export function severityPillClassForIssue(issue) {
  const s = displaySeverityForIssue(issue);
  if (s === "—") return "sev-default";
  const m = {
    BLOCKER: "sev-blocker",
    HIGH: "sev-high",
    MEDIUM: "sev-medium",
    LOW: "sev-low",
    INFO: "sev-info",
  };
  return m[s] ?? "sev-default";
}

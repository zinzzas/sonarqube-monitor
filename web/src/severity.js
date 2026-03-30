/**
 * 플랫폼 표준 severity: BLOCKER | HIGH | MEDIUM | LOW | INFO
 * SonarQube API는 CRITICAL / MAJOR / MINOR 등을 사용 → 표시·집계 시 위 표준으로 매핑.
 */
export const SEVERITY_OPTIONS = ["BLOCKER", "HIGH", "MEDIUM", "LOW", "INFO"];

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

/** SonarQube 이슈 severity → 표준 표시 문자열 */
export function displaySeverity(raw) {
  if (raw == null || raw === "") return "—";
  const m = {
    CRITICAL: "HIGH",
    MAJOR: "MEDIUM",
    MINOR: "LOW",
  };
  return m[raw] ?? raw;
}

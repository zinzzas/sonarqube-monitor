/**
 * 이슈 1건 → teamId — 백엔드 `team_id_for_path_segments` / `team_mapping` 과 정합.
 */
import segmentLabels from "../../../config/module_segment_labels.json";
import { issueComponentKey } from "../module.js";
import { pathSegmentsForTeamMatch } from "./teamPathSegments.js";

function normSeg(s) {
  return String(s || "")
    .trim()
    .toLowerCase();
}

function whenStrList(when, key, legacyKey) {
  const v = when[key] ?? when[legacyKey];
  return Array.isArray(v) ? v : [];
}

function normModuleList(raw) {
  return raw.map((x) => normSeg(x)).filter(Boolean);
}

/** Python `team_high_risk._coerce_when_match_kind` */
export function coerceWhenMatchKind(when) {
  const mk = String(when?.match ?? "")
    .trim()
    .toLowerCase();
  return mk === "first" ? "first" : "any";
}

/**
 * Python `_match_new_style_when` — 신형 modules/match 만. 해당 없으면 null → 레거시 평가.
 * @returns {boolean | null}
 */
export function matchNewStyleWhen(segL, when) {
  if (!when || typeof when !== "object") return null;
  if (!("modules" in when) || !Array.isArray(when.modules)) return null;
  const mods = normModuleList(when.modules);
  if (!mods.length) return null;
  const kind = coerceWhenMatchKind(when);
  if (kind === "first") return mods.includes(segL[0]);
  return segL.some((s) => mods.includes(s));
}

function matchLegacyWhen(segL, when) {
  const fs = normModuleList(whenStrList(when, "firstModule", "firstSegment"));
  const anys = normModuleList(whenStrList(when, "anyModule", "anySegment"));
  if (fs.length && !anys.length) return fs.includes(segL[0]);
  if (anys.length && !fs.length) return segL.some((s) => anys.includes(s));
  if (fs.length && anys.length) return fs.includes(segL[0]) || segL.some((s) => anys.includes(s));
  return false;
}

/** Python `_match_when` */
export function matchWhenForTeam(segments, when) {
  if (!when || typeof when !== "object") return false;
  const segL = segments.map((s) => normSeg(s)).filter(Boolean);
  if (!segL.length) return false;

  const newStyle = matchNewStyleWhen(segL, when);
  if (newStyle !== null) return newStyle;

  return matchLegacyWhen(segL, when);
}

function teamMappingConfig() {
  const tm = segmentLabels.teamMapping;
  return tm && typeof tm === "object" ? tm : {};
}

/** Python team_id_for_path_segments */
export function teamIdForPathSegments(segments, cfg) {
  const mapping = cfg && typeof cfg === "object" ? cfg : teamMappingConfig();
  const prec = mapping.precedence || [];
  if (Array.isArray(prec)) {
    for (const row of prec) {
      if (!row || typeof row !== "object") continue;
      const tid = String(row.teamId || "").trim();
      const w = row.when;
      if (tid && w && typeof w === "object" && matchWhenForTeam(segments, w)) {
        return tid;
      }
    }
  }
  const fb = mapping.fallback;
  if (fb && typeof fb === "object") {
    const fid = String(fb.teamId || "").trim();
    if (fid) return fid;
  }
  return "shared";
}

/**
 * @param {object} row — Sonar issue 행
 * @param {string} projectId
 * @returns {string}
 */
export function teamIdForIssue(row, projectId) {
  const component = issueComponentKey(row);
  const segments = pathSegmentsForTeamMatch(component, projectId);
  return teamIdForPathSegments(segments, teamMappingConfig());
}

/**
 * @param {object} row
 * @param {string} projectId
 * @param {string} teamId
 */
export function issueMatchesTeamFilter(row, projectId, teamId) {
  if (!teamId || !String(teamId).trim()) return true;
  return teamIdForIssue(row, projectId) === String(teamId).trim();
}

/**
 * 이슈 1건 → teamId — 백엔드 `team_id_for_path_segments` / `team_mapping` 과 정합.
 */
import segmentLabels from "../../../config/module_segment_labels.json";
import { issueComponentKey } from "../module.js";
import { pathSegmentsForTeamMatch } from "./teamPathSegments.js";

/** 서버 `team_mapping_config()` 와 맞추기 위해 하이드레이션 시 교체. 없으면 번들 JSON. */
let runtimeTeamMapping = null;

/** @type {Promise<void> | null} */
let hydratePromise = null;

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

export function setRuntimeTeamMapping(tm) {
  runtimeTeamMapping = tm && typeof tm === "object" ? tm : null;
}

function teamMappingConfig() {
  if (runtimeTeamMapping) {
    return runtimeTeamMapping;
  }
  const tm = segmentLabels.teamMapping;
  return tm && typeof tm === "object" ? tm : {};
}

/** `GET /api/config/team-mapping` — 대시보드·스냅샷과 동일 규칙으로 이슈 목록 팀 필터 정합 */
export async function hydrateRuntimeTeamMappingFromServer() {
  try {
    const res = await fetch("/api/config/team-mapping", { cache: "no-store" });
    if (!res.ok) return;
    const data = await res.json().catch(() => ({}));
    if (data.teamMapping && typeof data.teamMapping === "object") {
      setRuntimeTeamMapping(data.teamMapping);
    }
  } catch {
    /* 오프라인·번들 폴백 */
  }
}

/** App 진입·팀 매핑 저장 알림 시 호출 — 진행 중인 요청을 덮어쓴다. */
export function scheduleTeamMappingHydrate() {
  hydratePromise = hydrateRuntimeTeamMappingFromServer();
  return hydratePromise;
}

/** 이슈 목록 첫 조회 전에 대기 — 팀 딥링크 시 클라이언트 필터가 서버와 어긋나 빈 목록이 되지 않게 함 */
export function ensureTeamMappingHydrated() {
  if (!hydratePromise) {
    hydratePromise = hydrateRuntimeTeamMappingFromServer();
  }
  return hydratePromise;
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

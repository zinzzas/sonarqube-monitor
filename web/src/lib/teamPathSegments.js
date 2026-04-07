/**
 * 백엔드 `app/core/team_high_risk._path_segments_for_issue` 와 동일한 경로 세그먼트.
 * `module_grouping.json` + `path_tree` / `split_after` 규칙 정합.
 */
import {
  extractModuleFromComponent,
  profileForProject,
  sonarRelativePath,
} from "../module.js";

const TEAM_MATCH_MAX_DEPTH = 32;

function norm(s) {
  return String(s || "")
    .replace(/\\/g, "/")
    .trim();
}

function stripPrefixesPath(path, profile) {
  let raw = profile.stripPrefixes ?? ["src/"];
  if (typeof raw === "string") raw = [raw];
  const stripPrefixes = raw.map((p) => norm(p)).filter(Boolean);
  let rest = null;
  const pl = path.toLowerCase();
  for (const p of [...stripPrefixes].sort((a, b) => b.length - a.length)) {
    const pn = p.toLowerCase();
    const idx = pl.indexOf(pn);
    if (idx >= 0) {
      rest = path.slice(idx + p.length).replace(/^\//, "");
      break;
    }
  }
  if (rest === null) rest = path;
  return rest;
}

function looksLikeFile(seg) {
  if (!seg || !seg.includes(".") || seg.includes("/")) return false;
  const base = seg.split(".").slice(0, -1).join(".");
  return Boolean(base);
}

function dropLeadingSrcSegments(parts) {
  const out = [...parts];
  while (out.length && out[0].toLowerCase() === "src") {
    out.shift();
  }
  return out;
}

/**
 * @param {string} component
 * @param {object} profile
 * @returns {string|null|string} null = anchor 미매칭(path_tree)
 */
export function rollupPathAfterAnchor(component, profile) {
  const path = sonarRelativePath(component);
  if (!path) return "";
  const rest0 = stripPrefixesPath(path, profile);
  const anchor = norm(profile.anchorAfter ?? "");
  if (!anchor) return rest0;
  const escaped = anchor.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const re = new RegExp(escaped, "i");
  const m = re.exec(rest0);
  if (!m) return null;
  return rest0.slice(m.index + m[0].length).replace(/^\//, "");
}

/**
 * path_tree: anchor 이후 디렉터리 세그먼트 (누적 아님) — Python path_tree_segments
 */
export function pathTreeSegments(component, profile) {
  const rest = rollupPathAfterAnchor(component, profile);
  if (rest == null || !rest) return [];
  let parts = rest.split("/").filter(Boolean);
  parts = dropLeadingSrcSegments(parts);
  while (parts.length && looksLikeFile(parts[parts.length - 1])) {
    parts = parts.slice(0, -1);
  }
  if (!parts.length) return [];
  const maxDepth = Number(profile.maxDepth ?? 8) || 8;
  return parts.slice(0, maxDepth);
}

/** Python strip_only_path_segments */
export function stripOnlyPathSegments(component, profile, maxDepthOverride) {
  const path = sonarRelativePath(component);
  if (!path) return [];
  let rest = stripPrefixesPath(path, profile);
  if (!rest) return [];
  let parts = rest.split("/").filter(Boolean);
  parts = dropLeadingSrcSegments(parts);
  while (parts.length && looksLikeFile(parts[parts.length - 1])) {
    parts = parts.slice(0, -1);
  }
  if (!parts.length) return [];
  const md =
    maxDepthOverride != null
      ? Math.max(1, Number(maxDepthOverride) || 1)
      : Number(profile.maxDepth ?? 8) || 8;
  return parts.slice(0, md);
}

/** Python split_after_path_segments */
export function splitAfterPathSegments(component, profile) {
  const path = sonarRelativePath(component);
  if (!path) return [];
  const after = String(profile.after ?? "/fims/");
  const idx = path.indexOf(after);
  if (idx < 0) return [];
  let rest = path.slice(idx + after.length).replace(/^\//, "");
  let parts = rest.replace(/\\/g, "/").split("/").filter(Boolean);
  while (parts.length && looksLikeFile(parts[parts.length - 1])) {
    parts = parts.slice(0, -1);
  }
  return parts.slice(0, 32);
}

/**
 * @param {string} component
 * @param {string} projectId
 * @returns {string[]}
 */
export function pathSegmentsForTeamMatch(component, projectId) {
  const profile = profileForProject(projectId);
  const strategy = String(profile?.strategy ?? "split_after");
  if (strategy === "path_tree") {
    const segs = pathTreeSegments(component, profile);
    if (segs.length) return segs;
    const anchor = norm(profile.anchorAfter ?? "");
    if (anchor) return [];
    return stripOnlyPathSegments(component, profile, TEAM_MATCH_MAX_DEPTH);
  }
  if (strategy === "split_after") {
    const mod = extractModuleFromComponent(component, projectId);
    if (mod && mod !== "unknown") return [mod];
    const afterSegs = splitAfterPathSegments(component, profile);
    if (afterSegs.length) return afterSegs;
    const path = sonarRelativePath(component);
    const afterPath = String(profile.after ?? "/fims/");
    if (path && afterPath && path.indexOf(afterPath) < 0) return [];
    return stripOnlyPathSegments(component, profile, TEAM_MATCH_MAX_DEPTH);
  }
  const mod = extractModuleFromComponent(component, projectId);
  if (mod && mod !== "unknown") return [mod];
  const afterSegs = splitAfterPathSegments(component, profile);
  if (afterSegs.length) return afterSegs;
  return stripOnlyPathSegments(component, profile, TEAM_MATCH_MAX_DEPTH);
}

import { modulePathDepth } from "./config/moduleGrouping.js";

/**
 * 집계 키 기준으로 기본 펼침: 모듈 경로 `modulePathDepth`(슬래시 구간 수) 기준.
 * `visibleDepthLevels = N` 이면 `1 <= depth < N` 인 키만 expanded → 최대 N단계 경로까지 행 노출.
 * 예: N=3 → depth 1,2 만 expanded(atm, atm/foo) → atm/foo/bar(depth 3) 행까지 보임.
 * 예: N=4 → depth 1,2,3 expanded → 네 번째 세그먼트 행까지 노출.
 * @param {string} projectId
 * @param {Record<string, unknown>} modMap
 * @param {number} visibleDepthLevels
 * @returns {Set<string>} `projectId::path`
 */
export function buildDefaultExpandedModulePathSet(projectId, modMap, visibleDepthLevels) {
  const cap = Number(visibleDepthLevels);
  const n = Number.isFinite(cap) && cap >= 1 ? Math.min(20, Math.floor(cap)) : 4;
  const expanded = new Set();
  for (const k of Object.keys(modMap || {})) {
    const d = modulePathDepth(k);
    if (d >= 1 && d < n) {
      expanded.add(`${projectId}::${k}`);
    }
  }
  return expanded;
}

/**
 * path_tree 모듈 맵(경로 키 → severity)에서 직계 자식 경로만 반환.
 * @param {string} prefix 빈 문자열이면 L1 (슬래시 없는 키)
 * @param {Record<string, unknown>} modMap
 * @returns {string[]}
 */
export function directChildModulePaths(prefix, modMap) {
  const keys = Object.keys(modMap || {});
  if (prefix == null || prefix === "") {
    return keys.filter((k) => !k.includes("/")).sort();
  }
  const p = prefix.endsWith("/") ? prefix : `${prefix}/`;
  return keys
    .filter((k) => {
      if (!k.startsWith(p)) return false;
      const rest = k.slice(p.length);
      return !rest.includes("/");
    })
    .sort();
}

export function modulePathHasChildren(prefix, modMap) {
  return directChildModulePaths(prefix, modMap).length > 0;
}

/**
 * 펼침 상태에서 DFS 순으로 표시할 행 목록
 * @param {string} projectId
 * @param {Record<string, Record<string, number>>} modMap
 * @param {Set<string>} expanded `path` 집합
 * @returns {{ path: string, depth: number, counts: Record<string, number>, hasChild: boolean }[]}
 */
export function visibleModuleTreeRows(projectId, modMap, expanded) {
  const rows = [];

  function walk(prefix, depth) {
    const children = directChildModulePaths(prefix, modMap);
    for (const path of children) {
      const counts = modMap[path] || {};
      const hasChild = modulePathHasChildren(path, modMap);
      rows.push({ path, depth, counts, hasChild });
      if (expanded.has(`${projectId}::${path}`)) {
        walk(path, depth + 1);
      }
    }
  }

  walk("", 0);
  return rows;
}

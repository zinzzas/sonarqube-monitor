import mg from "../../../config/module_grouping.json";

/**
 * `module_grouping.projectProfiles` 의 프로필 id 문자열 (java_tree | vue_src_tree | …).
 * segment_labels·차트 축 등 프로필 키 단일 출처.
 */
export function profileIdForProject(projectId) {
  const defaultId = mg.defaultProfile ?? "vue_src_tree";
  if (projectId != null && mg.projectProfiles?.[projectId] != null) {
    return mg.projectProfiles[projectId];
  }
  return defaultId;
}

/** @returns {Record<string, unknown> | undefined} */
export function getProfileForProject(projectId) {
  const pid = profileIdForProject(projectId);
  const defaultId = mg.defaultProfile ?? "vue_src_tree";
  return mg.profiles?.[pid] ?? mg.profiles?.[defaultId];
}

/** 슬래시 구분 경로의 단계 수 (L1=1) */
export function modulePathDepth(path) {
  if (path == null || typeof path !== "string") return 0;
  const t = path.trim();
  if (!t) return 0;
  return t.split("/").filter(Boolean).length;
}

/**
 * path_tree / 전역 합산 차트 축: 집계 키 중 깊이 1..maxDepth 만, 트리 순(깊이 → 경로명)
 */
export function treeChartLabelsUpToDepth(modMap, maxDepth) {
  const cap = Number(maxDepth);
  const dmax = Number.isFinite(cap) && cap >= 1 ? Math.min(20, Math.floor(cap)) : 3;
  const keys = Object.keys(modMap || {}).filter((k) => {
    const d = modulePathDepth(k);
    return d >= 1 && d <= dmax;
  });
  return keys.sort((a, b) => {
    const da = modulePathDepth(a);
    const db = modulePathDepth(b);
    if (da !== db) return da - db;
    return a.localeCompare(b);
  });
}

function splitAfterDefaultRowsFromConfig() {
  const rows = mg.defaults?.splitAfterModuleRows;
  if (Array.isArray(rows) && rows.length) {
    return [...rows];
  }
  return ["auth", "core", "portal", "unknown"];
}

/**
 * split_after: `profiles.*.defaultModuleRows` 가 있으면 그걸 쓰고, 없으면 루트 `defaults.splitAfterModuleRows`.
 * path_tree: 항상 [] (행은 집계 키에서만).
 */
export function getDefaultModuleRowsForProject(projectId) {
  const profile = getProfileForProject(projectId);
  if (profile?.strategy === "path_tree") {
    return [];
  }
  if (profile?.defaultModuleRows?.length) {
    return [...profile.defaultModuleRows];
  }
  return splitAfterDefaultRowsFromConfig();
}

/** `defaults.chartModuleMaxDepth` (기본 3) */
export function getChartModuleMaxDepth() {
  const d = Number(mg.defaults?.chartModuleMaxDepth ?? 3);
  if (!Number.isFinite(d) || d < 1) return 3;
  return Math.min(20, Math.floor(d));
}

/** `defaults.moduleTreeDefaultExpandDepth` — N이면 경로 깊이 1..N 행까지 보이도록 depth<N 노드 펼침. 설정 없으면 4 */
export function getModuleTreeDefaultExpandDepth() {
  const d = Number(mg.defaults?.moduleTreeDefaultExpandDepth ?? 4);
  if (!Number.isFinite(d) || d < 1) return 4;
  return Math.min(20, Math.floor(d));
}

/** 차트에 경로 깊이 힌트를 붙일지 (전역 합산 또는 path_tree 프로젝트) */
export function chartsUseTreeDepth(scopeId) {
  if (scopeId === "global") return true;
  return getProfileForProject(scopeId)?.strategy === "path_tree";
}

/**
 * 차트 축용 모듈 라벨
 * - 전역 / path_tree: 깊이 1..chartModuleMaxDepth (트리 순)
 * - split_after: 설정 순 + API 키
 * @param {string} scopeId 'global' | 프로젝트 id
 * @param {Record<string, Record<string, number>>} modMap
 */
export function chartModuleLabelsForScope(scopeId, modMap) {
  const keys = Object.keys(modMap || {});
  if (scopeId === "global") {
    return treeChartLabelsUpToDepth(modMap, getChartModuleMaxDepth());
  }
  const profile = getProfileForProject(scopeId);
  if (profile?.strategy === "path_tree") {
    return treeChartLabelsUpToDepth(modMap, getChartModuleMaxDepth());
  }
  const order = getDefaultModuleRowsForProject(scopeId);
  const out = [];
  for (const name of order) {
    out.push(name);
  }
  for (const k of [...keys].sort()) {
    if (!order.includes(k)) out.push(k);
  }
  return out;
}

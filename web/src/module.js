import mg from "../../config/module_grouping.json";

function norm(s) {
  return String(s || "")
    .replace(/\\/g, "/")
    .trim();
}

function profileForProject(projectId) {
  const defaultId = mg.defaultProfile ?? "vue_src_tree";
  const key =
    projectId && mg.projectProfiles?.[projectId] != null
      ? mg.projectProfiles[projectId]
      : defaultId;
  return mg.profiles?.[key] ?? mg.profiles?.[defaultId];
}

function looksLikeFile(seg) {
  if (!seg || !seg.includes(".") || seg.includes("/")) return false;
  const base = seg.split(".").slice(0, -1).join(".");
  return Boolean(base);
}

/**
 * path_tree: 누적 경로 키 목록 (백엔드 path_tree_cumulative_keys 와 동일 규칙)
 */
export function pathTreeCumulativeKeys(component, profile) {
  const path = norm(component);
  if (!path) return [];

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

  const anchor = norm(profile.anchorAfter ?? "");
  if (anchor) {
    const rl = rest.toLowerCase();
    const al = anchor.toLowerCase();
    const idx = rl.indexOf(al);
    if (idx < 0) return ["unknown"];
    rest = rest.slice(idx + anchor.length).replace(/^\//, "");
  }

  let parts = rest.split("/").filter(Boolean);
  while (parts.length && looksLikeFile(parts[parts.length - 1])) {
    parts = parts.slice(0, -1);
  }
  if (!parts.length) return [];

  const maxDepth = Number(profile.maxDepth ?? 8) || 8;
  parts = parts.slice(0, maxDepth);

  const out = [];
  const acc = [];
  for (const p of parts) {
    acc.push(p);
    out.push(acc.join("/"));
  }
  return out;
}

function splitAfterModule(component, profile) {
  const path = String(component || "").trim();
  if (!path) return "unknown";
  const after = profile.after ?? "/fims/";
  const segIdx = Number(profile.segment_index ?? 0);
  const idx = path.indexOf(after);
  if (idx === -1) return "unknown";
  const rest = path.slice(idx + after.length).replace(/^\//, "");
  const parts = rest.replace(/\\/g, "/").split("/").filter(Boolean);
  if (segIdx < parts.length) return parts[segIdx] || "unknown";
  return "unknown";
}

/**
 * Sonar component → 모듈 경로 (path_tree 는 최하위 경로 키).
 */
export function extractModuleFromComponent(component, projectId) {
  if (component == null || typeof component !== "string" || !component.trim()) {
    return "unknown";
  }
  const profile = profileForProject(projectId);
  const strategy = profile?.strategy ?? "split_after";
  if (strategy === "path_tree") {
    const keys = pathTreeCumulativeKeys(component, profile);
    return keys.length ? keys[keys.length - 1] : "unknown";
  }
  if (strategy === "split_after") {
    return splitAfterModule(component, profile);
  }
  return "unknown";
}

/**
 * 이슈 목록 필터: path_tree 는 prefix 일치(하위 경로 포함).
 */
export function issueMatchesModuleFilter(component, projectId, filter) {
  if (filter == null || filter === "") return true;
  const f = String(filter).trim();
  if (!f) return true;
  const profile = profileForProject(projectId);
  const strategy = profile?.strategy ?? "split_after";
  if (strategy === "path_tree") {
    const leaf = extractModuleFromComponent(component, projectId);
    if (leaf === f) return true;
    return leaf.startsWith(`${f}/`);
  }
  return extractModuleFromComponent(component, projectId) === f;
}

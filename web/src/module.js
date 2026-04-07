import mg from "../../config/module_grouping.json";

/**
 * Sonar `issues/search` 한 건에서 파일·모듈 키 문자열 추출.
 * 일부 버전/응답에서 `component`가 `{ key }` 객체이거나, 경로가 다른 필드에만 있을 수 있다.
 */
export function issueComponentKey(row) {
  if (row == null) return "";
  const c = row.component;
  if (typeof c === "string" && c.trim()) return c.trim();
  if (c != null && typeof c === "object") {
    if (typeof c.key === "string" && c.key.trim()) return c.key.trim();
  }
  if (typeof row.componentKey === "string" && row.componentKey.trim()) return row.componentKey.trim();
  if (typeof row.mainComponent === "string" && row.mainComponent.trim()) return row.mainComponent.trim();
  if (row.mainComponent != null && typeof row.mainComponent === "object") {
    const k = row.mainComponent.key;
    if (typeof k === "string" && k.trim()) return k.trim();
  }
  return "";
}

function norm(s) {
  return String(s || "")
    .replace(/\\/g, "/")
    .trim();
}

/** `module_grouping.json` 프로필 — 팀 매칭·모듈 추출과 동일 단일 출처 */
export function profileForProject(projectId) {
  const defaultId = mg.defaultProfile ?? "vue_src_tree";
  const key =
    projectId && mg.projectProfiles?.[projectId] != null
      ? mg.projectProfiles[projectId]
      : defaultId;
  return mg.profiles?.[key] ?? mg.profiles?.[defaultId];
}

/** Sonar `projectKey:relative/path` → 상대 경로 (백엔드 `sonar_relative_path` 와 동일) */
export function sonarRelativePath(component) {
  let path = norm(component);
  const i = path.indexOf(":");
  if (i >= 0) path = path.slice(i + 1).replace(/^\//, "");
  return path;
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
  const path = sonarRelativePath(component);
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
    const escaped = anchor.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const re = new RegExp(escaped, "i");
    const m = re.exec(rest);
    if (!m) return ["unknown"];
    rest = rest.slice(m.index + m[0].length).replace(/^\//, "");
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
  const path = sonarRelativePath(component);
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

/** 누적 키가 어긋질 때: 상대 경로에 모듈 세그먼트가 경로로 등장하는지 (대시보드 키와 완화 매칭) */
function looseModulePathMatch(rel, f) {
  const r = norm(rel).replace(/\\/g, "/");
  const ft = norm(f).replace(/\\/g, "/");
  if (!r || !ft) return false;
  if (r === ft) return true;
  const rl = r.toLowerCase();
  const fl = ft.toLowerCase();
  if (rl === fl) return true;
  if (rl.startsWith(`${fl}/`)) return true;
  if (rl.endsWith(`/${fl}`)) return true;
  if (rl.includes(`/${fl}/`)) return true;
  return false;
}

/**
 * 이슈 목록 필터: path_tree 는 대시보드 집계와 동일하게 누적 경로 키 우선.
 * 키가 unknown 이거나 규칙 불일치 시 상대 경로 완화 매칭.
 * @param {string|object} componentOrRow — component 문자열 또는 Sonar issue 행 객체
 */
export function issueMatchesModuleFilter(componentOrRow, projectId, filter) {
  if (filter == null || filter === "") return true;
  const f = String(filter).trim();
  if (!f) return true;
  const component =
    typeof componentOrRow === "object" && componentOrRow !== null
      ? issueComponentKey(componentOrRow)
      : String(componentOrRow ?? "");
  if (!component) return false;

  const profile = profileForProject(projectId);
  const strategy = profile?.strategy ?? "split_after";
  if (strategy === "path_tree") {
    const keys = pathTreeCumulativeKeys(component, profile);
    if (keys.some((k) => k === f || k.startsWith(`${f}/`))) return true;
    return looseModulePathMatch(sonarRelativePath(component), f);
  }
  return extractModuleFromComponent(component, projectId) === f;
}

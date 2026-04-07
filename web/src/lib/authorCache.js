/**
 * 이슈 목록에서 관측한 Sonar `author`(SCM 로그인)를 프로젝트별로 localStorage에 누적한다.
 * 키: sonarqube-monitor:issue-author-cache → `{ [projectId]: string[] }`
 */
const STORAGE_KEY = "sonarqube-monitor:issue-author-cache";

function readAll() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return {};
    const o = JSON.parse(raw);
    return typeof o === "object" && o != null && !Array.isArray(o) ? o : {};
  } catch {
    return {};
  }
}

function writeAll(map) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(map));
  } catch {
    /* quota / private mode */
  }
}

/**
 * @param {string} projectId
 * @param {unknown[]} issues Sonar issue 객체 배열
 */
export function mergeIssueAuthorsIntoCache(projectId, issues) {
  if (!projectId || !Array.isArray(issues) || issues.length === 0) return;
  const all = readAll();
  const set = new Set(Array.isArray(all[projectId]) ? all[projectId] : []);
  for (const row of issues) {
    if (!row || typeof row !== "object") continue;
    const a = row.author;
    if (typeof a === "string" && a.trim()) {
      set.add(a.trim());
    }
  }
  if (set.size === 0) return;
  all[projectId] = [...set].sort((x, y) => x.localeCompare(y, "en"));
  writeAll(all);
}

/**
 * @param {string} projectId
 * @returns {string[]}
 */
export function getCachedAuthorsForProject(projectId) {
  if (!projectId) return [];
  const all = readAll();
  const arr = all[projectId];
  if (!Array.isArray(arr)) return [];
  return [...new Set(arr.map((s) => String(s).trim()).filter(Boolean))].sort((a, b) =>
    a.localeCompare(b, "en"),
  );
}

/**
 * Sonar `authors` 쿼리와 동일한 의미: 콤마로 구분된 SCM 로그인(OR) 중 하나와 일치.
 * `authorName` 은 쓰지 않고 `author` 만 비교 — API 필터와 표시를 맞춘다.
 */
export function issueMatchesAuthorFilter(row, authorFilter) {
  const q = String(authorFilter ?? "").trim();
  if (!q) return true;
  const login = typeof row?.author === "string" ? row.author.trim() : "";
  const wanted = q
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
  if (wanted.length === 0) return true;
  if (!login) return false;
  const lower = login.toLowerCase();
  return wanted.some((w) => w.toLowerCase() === lower);
}

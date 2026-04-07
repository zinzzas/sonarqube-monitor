/**
 * `config/module_segment_labels.json` — `module_grouping.json` 프로필 id와 정렬.
 * 집계 키(경로)는 백엔드와 동일하게 두고, 표시만 치환한다.
 */
import { profileIdForProject } from "../config/moduleGrouping.js";
import segmentLabels from "../../../config/module_segment_labels.json";

/**
 * 집계 키가 `src/api/common` 처럼 선행 `src` 가 남으면 segment_labels 의 `api` 트리와 맞지 않는다.
 * 백엔드 `module_path_tree._drop_leading_src_segments` 와 동일하게 선행 `src` 세그먼트를 제거한다.
 */
function stripLeadingSrcSegments(segments) {
  const out = [...segments];
  while (out.length && out[0].toLowerCase() === "src") {
    out.shift();
  }
  return out;
}

/** `maps.<id>.tree` 한글 치환 사용 여부. 생략·true면 사용, false면 트리 무시(업무명 unknown). */
export function isTreeLabelsEnabledForProfile(map) {
  if (!map || typeof map !== "object") return false;
  if (map.treeEnabled === false) return false;
  return true;
}

/** 대시보드 Module 표 — `업무명` 열 노출 여부 */
export function isTreeLabelsEnabledForProject(projectId) {
  const profileId = profileIdForProject(projectId);
  return isTreeLabelsEnabledForProfile(segmentLabels.maps?.[profileId]);
}

function findSegmentKey(node, segment) {
  if (!node || typeof node !== "object") return null;
  const lower = String(segment || "").trim().toLowerCase();
  if (!lower) return null;
  for (const k of Object.keys(node)) {
    if (k === "children" || k === "label") continue;
    if (k.startsWith("_")) continue;
    if (k.toLowerCase() === lower) return k;
  }
  return null;
}

/**
 * 트리 루트에서 세그먼트 배열을 한 번에 소비한다.
 */
function walkTreeFromRoot(tree, segs) {
  let node = tree;
  let lastLabel = null;
  const enLeaf = segs.length ? segs[segs.length - 1] : "";
  for (let i = 0; i < segs.length; i++) {
    const seg = segs[i];
    const key = findSegmentKey(node, seg);
    if (key == null) {
      return { ok: false };
    }
    const child = node[key];
    if (typeof child !== "object" || child == null) {
      return { ok: false };
    }
    const lbl = typeof child.label === "string" ? child.label.trim() : "";
    if (lbl) lastLabel = lbl;
    if (i === segs.length - 1) {
      return {
        ok: true,
        ko: lastLabel != null && lastLabel !== "" ? lastLabel : "unknown",
        en: enLeaf,
      };
    }
    node = child.children;
    if (!node || typeof node !== "object") {
      return { ok: false };
    }
  }
  return { ok: false };
}

/**
 * 누적 경로(예: portal/common) 또는 단일 세그먼트(차트 스택 축)에 대해
 * 리프 노드의 한글 레이블과 마지막 세그먼트(영문 키)를 반환한다.
 * Vue 등 경로가 views/.../api/common 처럼 오면 루트만으로는 매칭 실패 → 접두 세그먼트를 건너뛰며 트리 루트와 재시도한다.
 * 매핑 실패 시 ko 는 "unknown".
 *
 * @param {string} profileId module_grouping profiles 키
 * @param {string} cumulativePath 슬래시 구분 경로 또는 단일 세그먼트
 * @returns {{ ko: string, en: string }}
 */
export function resolveLeafDisplay(profileId, cumulativePath) {
  const raw = String(cumulativePath ?? "").trim();
  const segs = stripLeadingSrcSegments(
    raw.split("/").map((s) => s.trim()).filter(Boolean),
  );
  const enLeaf = segs.length ? segs[segs.length - 1] : raw;

  if (!segs.length) {
    return { ko: "unknown", en: enLeaf || "unknown" };
  }

  const map = segmentLabels.maps?.[profileId];
  if (!isTreeLabelsEnabledForProfile(map)) {
    return { ko: "unknown", en: enLeaf };
  }
  const tree = map?.tree;
  if (!tree || typeof tree !== "object") {
    return { ko: "unknown", en: enLeaf };
  }

  for (let start = 0; start < segs.length; start++) {
    const sub = segs.slice(start);
    const r = walkTreeFromRoot(tree, sub);
    if (r.ok) {
      return { ko: r.ko, en: r.en };
    }
  }
  return { ko: "unknown", en: enLeaf };
}

/**
 * 표시용 — projectId 기준 프로필로 리프 한글만
 * @param {string} projectId
 * @param {string} pathOrKey
 */
export function tableModuleKo(projectId, pathOrKey) {
  const profileId = profileIdForProject(projectId);
  return resolveLeafDisplay(profileId, pathOrKey).ko;
}

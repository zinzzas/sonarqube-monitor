/**
 * `config/module_segment_labels.json` 의 teamMapping — 빌드 시 번들됨.
 * API가 구버전이거나 필드가 비어도 대시보드 팀 UI 축·라벨을 유지한다.
 */
import segmentLabels from "../../../config/module_segment_labels.json";

/** @returns {string[]} */
export function teamOrderFromSegmentLabels() {
  const tm = segmentLabels.teamMapping;
  if (!tm || typeof tm !== "object") return [];
  const order = [];
  for (const row of tm.precedence || []) {
    const id = row?.teamId != null ? String(row.teamId).trim() : "";
    if (id) order.push(id);
  }
  const fb = tm.fallback;
  const fid = fb?.teamId != null ? String(fb.teamId).trim() : "";
  if (fid && !order.includes(fid)) order.push(fid);
  return order;
}

/** @returns {Record<string, string>} */
export function teamLabelsFromSegmentLabels() {
  const tm = segmentLabels.teamMapping;
  if (!tm || typeof tm !== "object") return {};
  /** @type {Record<string, string>} */
  const out = {};
  for (const row of tm.precedence || []) {
    const id = row?.teamId != null ? String(row.teamId).trim() : "";
    if (!id) continue;
    const lbl = row?.label != null ? String(row.label).trim() : "";
    out[id] = lbl || id;
  }
  const fb = tm.fallback;
  const fid = fb?.teamId != null ? String(fb.teamId).trim() : "";
  if (fid) {
    const lbl = fb?.label != null ? String(fb.label).trim() : "";
    out[fid] = lbl || fid;
  }
  return out;
}

import { shallowRef } from "vue";

import bundled from "../../../config/component_projects.json";

/**
 * Sonar `componentKeys`·라벨 — 운영 시 디스크 `config/component_projects.json` 과 동일하게 유지.
 * - Vite 번들은 빌드 시점 스냅샷이라, 키만 바꾼 뒤 `web` 재빌드 없이는 이슈 목록이 옛 키를 쓸 수 있음.
 * - 앱 기동 시 `hydrateComponentProjectsFromApi()` 가 `GET /api/projects` 로 최신 행을 덮어써 대시보드 집계와 정합.
 */
export const componentProjects = shallowRef(bundled);

export async function hydrateComponentProjectsFromApi() {
  try {
    const res = await fetch("/api/projects", { cache: "no-store" });
    if (!res.ok) return;
    const data = await res.json();
    if (data && Array.isArray(data.projects)) {
      componentProjects.value = data.projects;
    }
  } catch {
    /* 오프라인·프록시 실패 시 번들 유지 */
  }
}

/** @deprecated 항상 `componentProjects` 사용 — 하위 호환용 초기 번들 참조 */
export const COMPONENT_PROJECTS = bundled;

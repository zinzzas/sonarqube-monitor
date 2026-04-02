import { computed, ref, watch } from "vue";
import { useRoute } from "vue-router";
import { COMPONENT_PROJECTS } from "../config/componentProjects.js";

/**
 * 프로젝트 콤보 선택 → `componentKeys` 문자열(SonarQube API용)
 *
 * `componentKeys`는 URL `params.projectId`를 우선한다. 라우트 진입 직후 `selectedProjectId`가
 * 아직 비어 있으면 조회가 스킵되거나 빈 키로 요청되는 타이밍 버그가 나지 않도록 한다.
 */
export function useComponentProjectSelect() {
  const route = useRoute();
  const selectedProjectId = ref("");

  const projectOptions = COMPONENT_PROJECTS;

  /** 라우트와 동기화 — 대시보드에서 `/issues/:projectId` 로 들어올 때 즉시 반영 */
  watch(
    () => route.params.projectId,
    (pid) => {
      if (pid && typeof pid === "string") {
        selectedProjectId.value = pid;
      }
    },
    { immediate: true },
  );

  const resolvedProjectId = computed(() => {
    const fromRoute = route.params.projectId;
    if (fromRoute && typeof fromRoute === "string" && fromRoute.trim()) {
      return fromRoute.trim();
    }
    return String(selectedProjectId.value ?? "").trim();
  });

  const componentKeys = computed(() => {
    const pid = resolvedProjectId.value;
    if (!pid) {
      return "";
    }
    const row = COMPONENT_PROJECTS.find((p) => p.id === pid);
    const key = row?.componentKey?.trim() ?? "";
    return key;
  });

  return {
    projectOptions,
    selectedProjectId,
    resolvedProjectId,
    componentKeys,
  };
}

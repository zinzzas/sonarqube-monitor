import { computed, ref } from "vue";
import { COMPONENT_PROJECTS } from "../config/componentProjects.js";

/**
 * 프로젝트 콤보 선택 → `componentKeys` 문자열(SonarQube API용)
 */
export function useComponentProjectSelect() {
  const selectedProjectId = ref("");

  const projectOptions = COMPONENT_PROJECTS;

  const componentKeys = computed(() => {
    if (!selectedProjectId.value) {
      return "";
    }
    const row = COMPONENT_PROJECTS.find((p) => p.id === selectedProjectId.value);
    const key = row?.componentKey?.trim() ?? "";
    return key;
  });

  return {
    projectOptions,
    selectedProjectId,
    componentKeys,
  };
}

import { computed, ref, watch } from "vue";
import { useRoute } from "vue-router";
import { componentProjects } from "../config/componentProjects.js";
import { parseSeverityFloor } from "../severity.js";

/**
 * 프로젝트 콤보 선택 → `componentKeys` 문자열(SonarQube API용)
 *
 * `componentKeys`는 URL `params.projectId`를 우선한다. 라우트 진입 직후 `selectedProjectId`가
 * 아직 비어 있으면 조회가 스킵되거나 빈 키로 요청되는 타이밍 버그가 나지 않도록 한다.
 */
export function useComponentProjectSelect() {
  const route = useRoute();
  const selectedProjectId = ref("");

  const projectOptions = computed(() => componentProjects.value);

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
    const row = componentProjects.value.find((p) => p.id === pid);
    const key = row?.componentKey?.trim() ?? "";
    return key;
  });

  /** 이슈 목록·Sonar 쿼리 — 미설정 시 INFO (전 심각도) */
  const severityFloor = computed(() => {
    const pid = resolvedProjectId.value;
    if (!pid) {
      return "INFO";
    }
    const row = componentProjects.value.find((p) => p.id === pid);
    const raw = row?.severityFloor;
    if (raw == null || String(raw).trim() === "") {
      return "INFO";
    }
    return parseSeverityFloor(String(raw));
  });

  return {
    projectOptions,
    selectedProjectId,
    resolvedProjectId,
    componentKeys,
    severityFloor,
  };
}

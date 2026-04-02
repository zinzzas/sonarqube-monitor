import { nextTick, watch } from "vue";

/**
 * 이슈 목록 Sonar API 재조회 트리거만 담당.
 *
 * - `?module=` 은 클라이언트 표시 필터일 뿐이며 Sonar `issues/search`에 포함되지 않는다.
 * - 의존성에 `module`을 넣으면 Module × Severity에서 링크 진입 시 불필요한 loadFirst 반복·경쟁이 난다.
 * - Severity(엑셀형) 진입과 동일한 API 조건만 이 watch로 묶는다.
 */
export function useIssueListApiTrigger({
  route,
  componentKeys,
  filterSeverities,
  filterStatuses,
  sortBySeverity,
  pageSize,
  onLoadFirst,
}) {
  let seq = 0;

  watch(
    () => ({
      name: route.name,
      projectId: route.params.projectId,
      ck: String(componentKeys.value || "").trim(),
      severityQ: String(route.query.severity ?? ""),
      sevKey: JSON.stringify([...(filterSeverities.value ?? [])].sort()),
      stKey: JSON.stringify([...(filterStatuses.value ?? [])].sort()),
      sort: sortBySeverity.value,
      ps: pageSize.value,
    }),
    () => {
      if (route.name !== "issues") return;
      const pid = String(route.params.projectId || "");
      const ck = String(componentKeys.value || "").trim();
      if (!pid || !ck) return;
      const next = ++seq;
      nextTick(() => {
        if (next !== seq) return;
        onLoadFirst();
      });
    },
    { immediate: true },
  );
}

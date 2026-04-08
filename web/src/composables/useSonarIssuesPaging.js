/**
 * SonarQube issues/search 무한 스크롤
 *
 * 모든 요청에서 동일한 `ps = pageSize`로 맞춘다. Sonar는 `(p-1)*ps`로 오프셋을 잡으므로,
 * 첫 페이지만 `ps = pageSize+1`로 두고 이후 페이지는 `ps = pageSize`로 두면 2페이지가
 * 첫 페이지 마지막 이슈와 겹치고, 예전에 쓰던 overflow 병합 시 중복·건수 불일치가 난다.
 *
 * hasMore: `paging.total`이 있으면 loaded < total, 없으면 마지막 배치 길이가 pageSize 이상이면
 * 더 있을 수 있음(다음 페이지로 확인).
 */
import { computed, nextTick, onUnmounted, ref, unref, watch } from "vue";

import { buildSonarIssuesSearchParams } from "../lib/sonarIssuesSearchParams.js";

/** Sonar `issues/search`: total은 paging에만 있을 수 있음. issues는 배열이 아닌 dict로 오는 경우도 보정 */
function extractIssuesList(data) {
  if (!data || typeof data !== "object") return [];
  const raw = data.issues ?? data.Issues;
  if (Array.isArray(raw)) return raw;
  if (raw && typeof raw === "object" && !Array.isArray(raw)) {
    return Object.values(raw);
  }
  if (Array.isArray(data.results)) return data.results;
  return [];
}

function extractTotal(data) {
  if (!data || typeof data !== "object") return null;
  if (typeof data.total === "number") return data.total;
  const p = data.paging;
  if (p && typeof p === "object" && typeof p.total === "number") return p.total;
  return null;
}

/** 디버깅: 조회마다 총건수·이번 페이지 이슈 개수만 출력 (민감정보 제외) */
function logIssuesSearchResponse(phase, qs, data) {
  const t = extractTotal(data);
  const n = extractIssuesList(data).length;
  const p = qs.get("p") ?? "?";
  const ps = qs.get("ps") ?? "?";
  const ck = (qs.get("componentKeys") || "").trim();
  const ckShort = ck.length > 40 ? `${ck.slice(0, 40)}…` : ck || "(none)";
  // eslint-disable-next-line no-console
  console.info(
    `[issues/search] ${phase} p=${p} ps=${ps} key=${ckShort} total=${t ?? "null"} issuesLen=${n}`,
  );
}

async function fetchIssues(qs, phase = "fetch") {
  const url = `/api/issues/search?${qs.toString()}`;
  const res = await fetch(url);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    // eslint-disable-next-line no-console
    console.error(`[issues/search] ${phase} HTTP ${res.status}`, data);
    const d = data.detail ?? data.message;
    const msg =
      typeof d === "string" ? d : d != null ? JSON.stringify(d, null, 2) : res.statusText;
    throw new Error(msg);
  }
  logIssuesSearchResponse(phase, qs, data);
  return data;
}

export function useSonarIssuesPaging(refs) {
  const {
    pageSize,
    componentKeys,
    filterSeverities,
    filterStatuses,
    sortBySeverity,
    severitiesToApiParam,
    filterAuthor,
    severityFloor,
    filterTeamId,
  } = refs;

  /** Ref | ComputedRef | 값 혼용 시에도 안전 */
  function resolveComponentKey() {
    return String(unref(componentKeys) ?? "").trim();
  }

  function commonArgs() {
    const rawAuthor = filterAuthor != null ? unref(filterAuthor) : "";
    const authorFilter = typeof rawAuthor === "string" ? rawAuthor.trim() : "";
    const floorRaw = severityFloor != null ? unref(severityFloor) : "INFO";
    const severityFloorOut =
      typeof floorRaw === "string" && floorRaw.trim() ? floorRaw.trim() : "INFO";
    const rawTeam = filterTeamId != null ? unref(filterTeamId) : "";
    const teamId = typeof rawTeam === "string" ? rawTeam.trim() : "";
    return {
      componentKeys: resolveComponentKey(),
      filterSeverities: unref(filterSeverities),
      filterStatuses: unref(filterStatuses),
      sortBySeverity: unref(sortBySeverity),
      severitiesToApiParam,
      authorFilter,
      severityFloor: severityFloorOut,
      teamId,
    };
  }

  const items = ref([]);
  /** SonarQube `total`; 응답에 없으면 null → hasMore 는 배치 길이 휴리스틱 */
  const total = ref(null);
  /** 다음에 요청할 SonarQube 페이지 번호 (1-based) */
  const nextPage = ref(2);
  const hasMore = ref(false);
  const loading = ref(false);
  const loadingMore = ref(false);
  const error = ref(null);

  const loadedCount = computed(() => items.value.length);

  function recomputeHasMore(lastBatchLen, serverTotal) {
    if (serverTotal != null && typeof serverTotal === "number" && serverTotal >= 0) {
      hasMore.value = items.value.length < serverTotal;
      return;
    }
    if (lastBatchLen === 0) {
      hasMore.value = false;
      return;
    }
    hasMore.value = lastBatchLen >= unref(pageSize);
  }

  async function loadFirst() {
    const ck = resolveComponentKey();
    if (!ck) {
      loading.value = false;
      error.value =
        "Sonar componentKey가 없습니다. config/component_projects.json에 해당 프로젝트의 componentKey를 설정하세요. (키가 비면 API가 잘못된 프로젝트를 조회할 수 있습니다.)";
      items.value = [];
      total.value = null;
      hasMore.value = false;
      // eslint-disable-next-line no-console
      console.warn(
        "[issues/search] loadFirst skipped: componentKey 비어 있음 (URL projectId·component_projects.json 확인)",
      );
      return;
    }

    loading.value = true;
    loadingMore.value = false;
    error.value = null;
    items.value = [];
    nextPage.value = 2;
    hasMore.value = false;

    const ps = unref(pageSize);
    const q = buildSonarIssuesSearchParams({
      ...commonArgs(),
      pageIndex: 1,
      ps,
    });

    let needFollowUpPages = false;

    try {
      const data = await fetchIssues(q, "loadFirst");
      total.value = extractTotal(data);
      const list = extractIssuesList(data);

      if (list.length === 0) {
        hasMore.value = total.value != null && total.value > 0;
        needFollowUpPages = hasMore.value;
      } else {
        items.value = [...list];
        recomputeHasMore(list.length, total.value);
      }
    } catch (e) {
      error.value = String(e.message || e);
    } finally {
      loading.value = false;
    }

    // total>0인데 첫 페이지 issues가 비면 다음 페이지를 순차 요청(센티널 없이도 목록 채움)
    if (needFollowUpPages && items.value.length === 0) {
      let guard = 0;
      const maxFollow = 25;
      while (items.value.length === 0 && hasMore.value && guard < maxFollow) {
        guard += 1;
        await loadMore({ allowDuringInitialLoad: true });
      }
      if (items.value.length === 0 && (total.value ?? 0) > 0) {
        // eslint-disable-next-line no-console
        console.warn(
          `[issues/search] loadFirst: Sonar total=${total.value}건인데 ${maxFollow}페이지까지 issues가 비었습니다. 정렬·statuses·Sonar 버전을 확인하세요.`,
        );
      }
    }
  }

  async function loadMore(options = {}) {
    const allowDuringInitialLoad = Boolean(options.allowDuringInitialLoad);
    if (!resolveComponentKey()) {
      return;
    }
    if (!hasMore.value || loadingMore.value) {
      return;
    }
    if (!allowDuringInitialLoad && loading.value) {
      return;
    }
    loadingMore.value = true;
    error.value = null;

    const q = buildSonarIssuesSearchParams({
      ...commonArgs(),
      pageIndex: nextPage.value,
      ps: unref(pageSize),
    });

    try {
      const data = await fetchIssues(q, "loadMore");
      const t = extractTotal(data);
      if (t != null) {
        total.value = t;
      }
      const batch = extractIssuesList(data);
      if (batch.length === 0) {
        const loaded = items.value.length;
        const serverTotal = total.value;
        if (serverTotal != null && typeof serverTotal === "number" && loaded < serverTotal) {
          nextPage.value += 1;
          hasMore.value = true;
        } else {
          hasMore.value = false;
        }
        return;
      }
      items.value = [...items.value, ...batch];
      nextPage.value += 1;
      recomputeHasMore(batch.length, total.value);
    } catch (e) {
      error.value = String(e.message || e);
    } finally {
      loadingMore.value = false;
    }
  }

  /** 하단 센티널이 보이면 다음 페이지 */
  const sentinelEl = ref(null);
  let observer;

  function attachSentinel() {
    detachSentinel();
    const el = sentinelEl.value;
    if (!el) {
      return;
    }
    observer = new IntersectionObserver(
      (entries) => {
        const hit = entries.some((e) => e.isIntersecting);
        if (hit) {
          loadMore();
        }
      },
      { root: null, rootMargin: "120px", threshold: 0 },
    );
    observer.observe(el);
  }

  function detachSentinel() {
    if (observer) {
      observer.disconnect();
      observer = undefined;
    }
  }

  onUnmounted(detachSentinel);

  watch(
    sentinelEl,
    (el) => {
      if (el) {
        nextTick(() => attachSentinel());
      }
    },
    { flush: "post" },
  );

  return {
    items,
    total,
    loadedCount,
    nextPage,
    hasMore,
    loading,
    loadingMore,
    error,
    loadFirst,
    loadMore,
    sentinelEl,
    attachSentinel,
    detachSentinel,
  };
}

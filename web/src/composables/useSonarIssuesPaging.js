/**
 * SonarQube issues/search 무한 스크롤
 *
 * 최초: ps = pageSize + 1 로 한 건 더 받아 hasMore 판별.
 * len > pageSize 이면 화면에는 pageSize만큼만 두고 나머지 1건은 overflow로 보관 후
 * 다음 페이지(p=2…) 요청 시 앞에 붙여 순서 유지.
 *
 * hasMore: total 이 있으면 loaded < total, 없으면 (첫 응답 len > pageSize) 또는 이후 배치 len === pageSize
 */
import { computed, nextTick, onUnmounted, ref, watch } from "vue";

function buildSearchParams({
  pageSize,
  componentKeys,
  filterSeverities,
  filterStatuses,
  sortBySeverity,
  severitiesToApiParam,
  pageIndex,
  ps,
}) {
  const q = new URLSearchParams();
  if (componentKeys.trim()) {
    q.set("componentKeys", componentKeys.trim());
  }
  q.set("p", String(pageIndex));
  q.set("ps", String(ps));
  const sev = severitiesToApiParam(filterSeverities);
  if (sev) {
    q.set("severities", sev);
  }
  if (filterStatuses.length) {
    q.set("statuses", filterStatuses.join(","));
  }
  const sort = sortBySeverity;
  if (sort === "severity_desc") {
    q.set("s", "SEVERITY");
    q.set("asc", "false");
  } else if (sort === "severity_asc") {
    q.set("s", "SEVERITY");
    q.set("asc", "true");
  } else if (sort === "creation_desc") {
    q.set("s", "CREATION_DATE");
    q.set("asc", "false");
  } else if (sort === "creation_asc") {
    q.set("s", "CREATION_DATE");
    q.set("asc", "true");
  }
  return q;
}

async function fetchIssues(qs) {
  const url = `/api/issues/search?${qs.toString()}`;
  const res = await fetch(url);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const d = data.detail ?? data.message;
    const msg =
      typeof d === "string" ? d : d != null ? JSON.stringify(d, null, 2) : res.statusText;
    throw new Error(msg);
  }
  return data;
}

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

export function useSonarIssuesPaging(refs) {
  const {
    pageSize,
    componentKeys,
    filterSeverities,
    filterStatuses,
    sortBySeverity,
    severitiesToApiParam,
  } = refs;

  const items = ref([]);
  /** SonarQube `total`; 응답에 없으면 null → hasMore 는 배치 길이 휴리스틱 */
  const total = ref(null);
  /** 첫 응답에서 잘라낸 1건 — 다음 API 페이지와 이어 붙임 */
  const overflowIssue = ref(null);
  /** 다음에 요청할 SonarQube 페이지 번호 (1-based) */
  const nextPage = ref(2);
  const hasMore = ref(false);
  const loading = ref(false);
  const loadingMore = ref(false);
  const error = ref(null);

  const loadedCount = computed(() => items.value.length);

  function commonArgs() {
    return {
      pageSize: pageSize.value,
      componentKeys: componentKeys.value,
      filterSeverities: filterSeverities.value,
      filterStatuses: filterStatuses.value,
      sortBySeverity: sortBySeverity.value,
      severitiesToApiParam,
    };
  }

  function recomputeHasMore(lastBatchLen, serverTotal) {
    if (serverTotal != null && typeof serverTotal === "number" && serverTotal >= 0) {
      hasMore.value = items.value.length < serverTotal;
      return;
    }
    if (lastBatchLen === 0) {
      hasMore.value = false;
      return;
    }
    hasMore.value = lastBatchLen >= pageSize.value;
  }

  async function loadFirst() {
    const ck = String(componentKeys.value ?? "").trim();
    if (!ck) {
      loading.value = false;
      error.value =
        "Sonar componentKey가 없습니다. config/component_projects.json에 해당 프로젝트의 componentKey를 설정하세요. (키가 비면 API가 잘못된 프로젝트를 조회할 수 있습니다.)";
      items.value = [];
      total.value = null;
      hasMore.value = false;
      return;
    }

    loading.value = true;
    loadingMore.value = false;
    error.value = null;
    items.value = [];
    overflowIssue.value = null;
    nextPage.value = 2;
    hasMore.value = false;

    const ps = pageSize.value + 1;
    const q = buildSearchParams({
      ...commonArgs(),
      pageIndex: 1,
      ps,
    });

    let needFollowUpPages = false;

    try {
      const data = await fetchIssues(q);
      total.value = extractTotal(data);
      const list = extractIssuesList(data);
      const n = pageSize.value;

      if (list.length === 0) {
        hasMore.value = total.value != null && total.value > 0;
        needFollowUpPages = hasMore.value;
        return;
      }

      if (list.length > n) {
        items.value = list.slice(0, n);
        overflowIssue.value = list[n];
        hasMore.value = true;
        return;
      }

      items.value = [...list];
      overflowIssue.value = null;
      recomputeHasMore(list.length, total.value);
    } catch (e) {
      error.value = String(e.message || e);
    } finally {
      loading.value = false;
    }

    // total>0인데 첫 페이지 issues가 비면 loadMore는 기본적으로 loading 때문에 막혔을 수 있음.
    // 빈 테이블에서는 센티널이 뷰에 안 들어와 무한스크롤이 안 도는 경우도 있어 후속 페이지를 당긴다.
    if (needFollowUpPages && items.value.length === 0) {
      const maxExtra = 5;
      for (let i = 0; i < maxExtra && items.value.length === 0 && hasMore.value; i++) {
        await loadMore({ allowDuringInitialLoad: true });
      }
    }
  }

  async function loadMore(options = {}) {
    const allowDuringInitialLoad = Boolean(options.allowDuringInitialLoad);
    if (!String(componentKeys.value ?? "").trim()) {
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

    const q = buildSearchParams({
      ...commonArgs(),
      pageIndex: nextPage.value,
      ps: pageSize.value,
    });

    try {
      const data = await fetchIssues(q);
      const t = extractTotal(data);
      if (t != null) {
        total.value = t;
      }
      let batch = extractIssuesList(data);
      if (overflowIssue.value) {
        batch = [overflowIssue.value, ...batch];
        overflowIssue.value = null;
      }
      if (batch.length === 0) {
        hasMore.value = false;
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
    overflowIssue,
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

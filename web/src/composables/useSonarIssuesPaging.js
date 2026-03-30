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

    try {
      const data = await fetchIssues(q);
      total.value = typeof data.total === "number" ? data.total : null;
      const list = data.issues ?? [];
      const n = pageSize.value;

      if (list.length === 0) {
        hasMore.value = false;
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
  }

  async function loadMore() {
    if (!hasMore.value || loading.value || loadingMore.value) {
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
      if (typeof data.total === "number") {
        total.value = data.total;
      }
      let batch = data.issues ?? [];
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

<script setup>
import {
  ArcElement,
  BarElement,
  CategoryScale,
  Chart as ChartJS,
  Legend,
  LinearScale,
  Tooltip,
} from "chart.js";
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from "vue";
import { Bar, Pie } from "vue-chartjs";
import { useRouter } from "vue-router";
import { COMPONENT_PROJECTS } from "../config/componentProjects.js";
import { DASHBOARD_HERO } from "../config/dashboardConfig.js";
import {
  getDefaultModuleRowsForProject,
  getModuleTreeDefaultExpandDepth,
  getProfileForProject,
} from "../config/moduleGrouping.js";
import { profileIdForProject } from "../config/moduleGrouping.js";
import { chartStackAxisLabel, tableModuleKo } from "../lib/moduleSegmentLabels.js";
import { TEAM_MAPPING_UPDATED_EVENT } from "../lib/teamMappingEvents.js";
import {
  teamLabelsFromSegmentLabels,
  teamOrderFromSegmentLabels,
} from "../lib/teamMappingConfig.js";
import dashboardGearIcon from "../assets/dashboard-gear.svg?url";
import { LOAD_MORE_CHEVRON_SRC } from "../loadingOverlay.js";
import { buildDefaultExpandedModulePathSet, visibleModuleTreeRows } from "../moduleTree.js";
import { SEVERITY_OPTIONS } from "../severity.js";

ChartJS.register(ArcElement, BarElement, CategoryScale, LinearScale, Tooltip, Legend);

const router = useRouter();

const loading = ref(true);
/** Module×Severity — 이슈 펼침 CSV 생성 중 */
const exportingModuleCsv = ref(false);
const err = ref("");
const payload = ref(null);
/** 마지막으로 집계 API를 성공적으로 받은 시각 (새로고침마다 갱신) */
const lastFetchedAt = ref(null);

/** path_tree 표 펼침 — load()보다 먼저 선언 (TDZ 회피) */
const expandedModulePaths = ref(new Set());

/** `/api/metrics/dashboard`는 프로젝트당 Sonar 순차 호출·이슈 페이징으로 수분 걸릴 수 있음. */
const DASHBOARD_FETCH_TIMEOUT_MS = 600_000;

const SEV_COLORS = {
  BLOCKER: "#b91c1c",
  HIGH: "#ea580c",
  MEDIUM: "#ca8a04",
  LOW: "#16a34a",
  INFO: "#64748b",
};

/** 차트 축·범례 — CSS `--dashboard-chart-*` 톤과 맞춤 */
const CHART_CHROME = {
  axis: "#64748b",
  grid: "rgba(5, 150, 105, 0.11)",
};

/**
 * 건수 고유값(내림차순)별 색: 최다 빨강 → 주황 → 노랑 계열 → 최소는 항상 진녹색.
 * 전부 0이면 중립 회색.
 */
const TEAM_HR_ALL_ZERO = "#94a3b8";

function teamHrRankColor(i, n) {
  if (n < 2) return TEAM_HR_ALL_ZERO;
  if (i === 0) return "#b91c1c";
  if (i === n - 1) return "#15803d";
  if (i === 1) return "#ea580c";
  if (i === 2) return "#ca8a04";
  if (i === 3) return "#eab308";
  return "#84cc16";
}

function teamHrColorsByCounts(order, teamCounts) {
  /** @type {Record<string, string>} */
  const out = {};
  for (const tid of order) {
    out[tid] = TEAM_HR_ALL_ZERO;
  }
  const unique = [...new Set(order.map((tid) => teamCounts[tid] ?? 0))].sort((a, b) => b - a);
  if (unique.length === 1 && unique[0] === 0) {
    return out;
  }
  const n = unique.length;
  if (n === 1) {
    const col = "#b91c1c";
    for (const tid of order) {
      out[tid] = col;
    }
    return out;
  }
  unique.forEach((c, i) => {
    const col = teamHrRankColor(i, n);
    for (const tid of order) {
      if ((teamCounts[tid] ?? 0) === c) {
        out[tid] = col;
      }
    }
  });
  return out;
}

const ALL_SCOPE_ID = "all";

const firstProjectId = COMPONENT_PROJECTS[0]?.id ?? "";
/** 상단 차트·표 범위 — 기본 첫 프로젝트, `all`이면 전 프로젝트 B·H·M 병합 API */
const scopeId = ref(firstProjectId);

const projectSelectOptions = computed(() => [
  { id: ALL_SCOPE_ID, label: "전체 (ALL)" },
  ...COMPONENT_PROJECTS,
]);

const isAllScope = computed(
  () => scopeId.value === ALL_SCOPE_ID || payload.value?.aggregateMode === "all_bhm",
);

const pieSeverityOptions = computed(() =>
  isAllScope.value ? ["BLOCKER", "HIGH", "MEDIUM"] : SEVERITY_OPTIONS,
);

const kpiSeverityChips = computed(() =>
  isAllScope.value ? ["BLOCKER", "HIGH", "MEDIUM"] : SEVERITY_OPTIONS,
);

const excelSeverityColumns = computed(() =>
  isAllScope.value ? ["BLOCKER", "HIGH", "MEDIUM"] : SEVERITY_OPTIONS,
);

const excelSeveritySectionTitle = computed(() =>
  isAllScope.value ? "전체 프로젝트 Severity (엑셀형 · B·H·M)" : "선택 프로젝트 Severity (엑셀형)",
);

function moduleTotal(modCounts) {
  if (!modCounts) return 0;
  return SEVERITY_OPTIONS.reduce((a, s) => a + (modCounts[s] ?? 0), 0);
}

async function load() {
  loading.value = true;
  err.value = "";
  const controller = new AbortController();
  let timeoutId = 0;
  try {
    timeoutId = window.setTimeout(() => controller.abort(), DASHBOARD_FETCH_TIMEOUT_MS);
    const qs = new URLSearchParams();
    if (scopeId.value) qs.set("projectId", scopeId.value === ALL_SCOPE_ID ? "all" : scopeId.value);
    const dashUrl =
      qs.toString().length > 0
        ? `/api/metrics/dashboard?${qs}`
        : "/api/metrics/dashboard";
    const res = await fetch(dashUrl, {
      signal: controller.signal,
      cache: "no-store",
    });
    if (timeoutId) {
      clearTimeout(timeoutId);
      timeoutId = 0;
    }
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const d = data.detail ?? data.message;
      err.value = typeof d === "string" ? d : JSON.stringify(d ?? res.statusText);
      payload.value = null;
      expandedModulePaths.value = new Set();
      return;
    }
    payload.value = data;
    lastFetchedAt.value = new Date();
    await nextTick();
    try {
      expandedModulePaths.value = buildDefaultExpandedFromMergedRows();
    } catch (expandErr) {
      console.error(expandErr);
      expandedModulePaths.value = new Set();
    }
  } catch (e) {
    const name = e?.name ?? "";
    if (name === "AbortError") {
      err.value =
        `집계 요청이 ${DASHBOARD_FETCH_TIMEOUT_MS / 1000}초 안에 끝나지 않았습니다. SonarQube·VPN·네트워크를 확인하거나 잠시 후 새로고침하세요.`;
    } else {
      err.value = String(e?.message || e);
    }
    payload.value = null;
    expandedModulePaths.value = new Set();
  } finally {
    if (timeoutId) clearTimeout(timeoutId);
    loading.value = false;
  }
}

const snapshotAsOfIso = computed(() =>
  lastFetchedAt.value ? lastFetchedAt.value.toISOString() : "",
);

/** 예: 2026년 3월 30일 오후 2:30 */
const snapshotAsOfLabel = computed(() => {
  if (!lastFetchedAt.value) return "";
  return lastFetchedAt.value.toLocaleString("ko-KR", {
    dateStyle: "long",
    timeStyle: "short",
  });
});

const summary = computed(() => payload.value?.summary ?? null);
const byProject = computed(() => payload.value?.byProject ?? []);
const metricErrors = computed(() => payload.value?.errors ?? []);

function emptySevRow() {
  return Object.fromEntries(SEVERITY_OPTIONS.map((s) => [s, 0]));
}

/** config의 모든 프로젝트 + API 집계 병합 (componentKey 없는 항목도 0으로 노출) */
const mergedProjectRows = computed(() => {
  const list = byProject.value;
  return COMPONENT_PROJECTS.map((p) => {
    const row = list.find((b) => b.projectId === p.id);
    if (row) {
      // 표시 라벨은 항상 `component_projects.json`(번들) 기준 — API/백엔드 캐시에 남은 옛 label과 어긋나지 않게 함
      return { ...row, label: p.label };
    }
    return {
      projectId: p.id,
      label: p.label,
      componentKey: String(p.componentKey ?? "").trim(),
      totalIssues: 0,
      severityTotal: emptySevRow(),
      highRisk: 0,
      highRiskByTeam: {},
      modules: {},
      chartStackModules: {},
    };
  });
});

const activeProjectRow = computed(() => {
  if (scopeId.value === ALL_SCOPE_ID) return null;
  return mergedProjectRows.value.find((r) => r.projectId === scopeId.value) ?? null;
});

/** KPI·차트 — ALL은 API summary 병합, 단일 프로젝트는 해당 행 */
const displaySummary = computed(() => {
  if (scopeId.value === ALL_SCOPE_ID) {
    const s = summary.value;
    if (s) {
      return {
        totalIssues: s.totalIssues ?? 0,
        highRisk: s.highRisk ?? 0,
        severityTotal: { ...emptySevRow(), ...(s.severityTotal ?? {}) },
        highRiskByTeam: { ...(s.highRiskByTeam ?? {}) },
      };
    }
    return {
      totalIssues: 0,
      highRisk: 0,
      severityTotal: emptySevRow(),
      highRiskByTeam: {},
    };
  }
  const row = activeProjectRow.value;
  if (row && row.projectId === scopeId.value) {
    return {
      totalIssues: row.totalIssues ?? 0,
      highRisk: row.highRisk ?? 0,
      severityTotal: row.severityTotal ?? emptySevRow(),
      highRiskByTeam: row.highRiskByTeam ?? {},
    };
  }
  return (
    summary.value ?? {
      totalIssues: 0,
      highRisk: 0,
      severityTotal: emptySevRow(),
      highRiskByTeam: {},
    }
  );
});

/**
 * 팀 축·라벨: API 우선, 없으면 번들된 `module_segment_labels.json` teamMapping
 * (uvicorn만 재기동하고 `web/dist` 미빌드인 경우에도 UI 노출).
 */
const highRiskTeamLabels = computed(() => ({
  ...teamLabelsFromSegmentLabels(),
  ...(payload.value?.summary?.highRiskTeamLabels ?? {}),
}));

const highRiskTeamOrder = computed(() => {
  const api = payload.value?.summary?.highRiskTeamOrder;
  if (Array.isArray(api) && api.length > 0) {
    return api;
  }
  return teamOrderFromSegmentLabels();
});

/** 선택 프로젝트 기준 팀별 건수 — 축 순서에 맞춰 0 채움 */
const displayHighRiskByTeam = computed(() => {
  const order = highRiskTeamOrder.value;
  const raw = displaySummary.value?.highRiskByTeam ?? {};
  const out = {};
  for (const tid of order) {
    out[tid] = raw[tid] ?? 0;
  }
  return out;
});

/** 건수 내림차순(동률이면 설정 순서 유지) — KPI·막대 X축 */
const highRiskTeamOrderSorted = computed(() => {
  const base = highRiskTeamOrder.value;
  const counts = displayHighRiskByTeam.value;
  const copy = [...base];
  copy.sort((a, b) => {
    const ca = counts[a] ?? 0;
    const cb = counts[b] ?? 0;
    if (cb !== ca) return cb - ca;
    return base.indexOf(a) - base.indexOf(b);
  });
  return copy;
});

/** teamMapping 이 있으면 항상 팀 블록 표시 */
const showTeamHighRiskUi = computed(
  () => teamOrderFromSegmentLabels().length > 0 || highRiskTeamOrder.value.length > 0,
);

/** KPI·막대 그래프 공통 — 팀 id → 순위 색 */
const teamHrColors = computed(() =>
  teamHrColorsByCounts(highRiskTeamOrderSorted.value, displayHighRiskByTeam.value),
);

const scopeLabel = computed(() => {
  if (scopeId.value === ALL_SCOPE_ID) return "전체 (ALL)";
  return activeProjectRow.value?.label ?? scopeId.value;
});

const severityForScope = computed(() => displaySummary.value?.severityTotal ?? null);

/** 스택 막대: API chartStackModules (anchor 이후 첫 세그먼트만 집계) */
const chartStackMapForScope = computed(
  () => activeProjectRow.value?.chartStackModules ?? {},
);

/** 표·CSV — ALL이면 전 프로젝트 행, 아니면 선택 한 줄 */
const visibleProjectRows = computed(() => {
  if (scopeId.value === ALL_SCOPE_ID) return mergedProjectRows.value;
  return mergedProjectRows.value.filter((r) => r.projectId === scopeId.value);
});

watch(mergedProjectRows, (rows) => {
  if (!rows.length || !scopeId.value) return;
  if (scopeId.value === ALL_SCOPE_ID) return;
  if (!rows.some((r) => r.projectId === scopeId.value)) {
    scopeId.value = COMPONENT_PROJECTS[0]?.id ?? rows[0].projectId;
  }
});

watch(
  scopeId,
  () => {
    load();
  },
  { immediate: true },
);

function onTeamMappingConfigUpdated() {
  load();
}

onMounted(() => {
  window.addEventListener(TEAM_MAPPING_UPDATED_EVENT, onTeamMappingConfigUpdated);
});

onUnmounted(() => {
  window.removeEventListener(TEAM_MAPPING_UPDATED_EVENT, onTeamMappingConfigUpdated);
});

const chartStackLabels = computed(() => {
  const m = chartStackMapForScope.value;
  const keys = Object.keys(m || {});
  return keys.sort((a, b) => {
    const ta = moduleTotal(m[a]);
    const tb = moduleTotal(m[b]);
    if (tb !== ta) return tb - ta;
    return a.localeCompare(b);
  });
});

const stackChartSubtitle = computed(
  () => " · 스택 축: 프로필 chartStackAnchorAfter(없으면 anchorAfter) 직후 첫 경로 세그먼트",
);

/** 트리 표 안내용 (defaults.moduleTreeDefaultExpandDepth) */
const moduleTreeDefaultExpandLabel = computed(() => getModuleTreeDefaultExpandDepth());

const pieChartData = computed(() => {
  const st = severityForScope.value;
  if (!st) {
    return { labels: [], datasets: [] };
  }
  const opts = pieSeverityOptions.value;
  return {
    labels: opts,
    datasets: [
      {
        backgroundColor: opts.map((s) => SEV_COLORS[s] ?? "#94a3b8"),
        data: opts.map((s) => st[s] ?? 0),
      },
    ],
  };
});

const pieOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: {
      position: "bottom",
      labels: {
        color: CHART_CHROME.axis,
        padding: 14,
        usePointStyle: true,
      },
    },
    tooltip: {
      bodyColor: "#334155",
      titleColor: "#334155",
      borderColor: "rgba(16, 185, 129, 0.25)",
      borderWidth: 1,
      backgroundColor: "rgba(255, 255, 255, 0.96)",
    },
  },
};

const stackedBarData = computed(() => {
  const gm = chartStackMapForScope.value;
  const keys = chartStackLabels.value;
  const profileId = profileIdForProject(scopeId.value);
  return {
    labels: keys.map((key) => chartStackAxisLabel(profileId, key)),
    datasets: SEVERITY_OPTIONS.map((sev) => ({
      label: sev,
      data: keys.map((key) => gm[key]?.[sev] ?? 0),
      backgroundColor: SEV_COLORS[sev] ?? "#94a3b8",
    })),
  };
});

/** 팀별 High risk (BLOCKER+HIGH) — 세로 막대, 건수 순위별 색, 많은 팀이 왼쪽 */
const highRiskTeamBarData = computed(() => {
  const order = highRiskTeamOrderSorted.value;
  const labelsMap = highRiskTeamLabels.value;
  const byTeam = displayHighRiskByTeam.value;
  const colors = teamHrColors.value;
  if (!order.length) {
    return { labels: [], datasets: [] };
  }
  const bg = order.map((tid) => colors[tid] ?? TEAM_HR_ALL_ZERO);
  return {
    labels: order.map((tid) => labelsMap[tid] ?? tid),
    datasets: [
      {
        label: "High risk",
        data: order.map((tid) => byTeam[tid] ?? 0),
        backgroundColor: bg,
        borderColor: bg,
        borderWidth: 1,
        borderRadius: 4,
      },
    ],
  };
});

const highRiskTeamBarOptions = {
  responsive: true,
  maintainAspectRatio: false,
  scales: {
    x: {
      stacked: false,
      grid: {
        color: CHART_CHROME.grid,
        drawTicks: true,
      },
      border: { color: "rgba(16, 185, 129, 0.2)" },
      ticks: {
        maxRotation: 32,
        minRotation: 0,
        autoSkip: true,
        color: CHART_CHROME.axis,
      },
    },
    y: {
      beginAtZero: true,
      stacked: false,
      grid: { color: CHART_CHROME.grid },
      border: { color: "rgba(16, 185, 129, 0.2)" },
      ticks: { precision: 0, color: CHART_CHROME.axis },
    },
  },
  plugins: {
    legend: { display: false },
    tooltip: {
      bodyColor: "#334155",
      titleColor: "#334155",
      borderColor: "rgba(16, 185, 129, 0.25)",
      borderWidth: 1,
      backgroundColor: "rgba(255, 255, 255, 0.96)",
    },
  },
};

const stackedBarOptions = {
  responsive: true,
  maintainAspectRatio: false,
  scales: {
    x: {
      stacked: true,
      grid: {
        color: CHART_CHROME.grid,
        drawTicks: true,
      },
      border: { color: "rgba(16, 185, 129, 0.2)" },
      ticks: {
        maxRotation: 48,
        minRotation: 0,
        autoSkip: true,
        color: CHART_CHROME.axis,
      },
    },
    y: {
      stacked: true,
      beginAtZero: true,
      grid: { color: CHART_CHROME.grid },
      border: { color: "rgba(16, 185, 129, 0.2)" },
      ticks: { precision: 0, color: CHART_CHROME.axis },
    },
  },
  plugins: {
    legend: {
      position: "bottom",
      labels: {
        color: CHART_CHROME.axis,
        padding: 12,
        usePointStyle: true,
      },
    },
    tooltip: {
      bodyColor: "#334155",
      titleColor: "#334155",
      borderColor: "rgba(16, 185, 129, 0.25)",
      borderWidth: 1,
      backgroundColor: "rgba(255, 255, 255, 0.96)",
    },
  },
};

function goIssues(projectId, query = {}) {
  const q = {};
  if (query.module) q.module = query.module;
  if (query.severity) q.severity = query.severity;
  /** 이슈 목록에서 출처 구분(문서·필터 힌트용). API에는 전달하지 않음 */
  q.nav = query.module ? "module-matrix" : "severity-excel";
  router.push({ name: "issues", params: { projectId }, query: q });
}

function projectRowTotal(row) {
  return row?.totalIssues ?? moduleTotal(row?.severityTotal);
}

function isRiskSeverity(s) {
  return s === "BLOCKER" || s === "HIGH";
}

function hasProjectKey(proj) {
  return Boolean(proj?.componentKey && String(proj.componentKey).trim());
}

function moduleRowsFor(proj) {
  const m = proj.modules || {};
  const order = getDefaultModuleRowsForProject(proj.projectId);
  const row = (name) => {
    const counts = emptySevRow();
    if (m[name]) {
      for (const s of SEVERITY_OPTIONS) {
        counts[s] = m[name][s] ?? 0;
      }
    }
    return { name, counts };
  };
  const known = order.map((name) => row(name));
  const extras = Object.keys(m)
    .filter((k) => !order.includes(k))
    .sort()
    .map((name) => row(name));
  return [...known, ...extras];
}

function isPathTreeProject(proj) {
  if (proj?.moduleStrategy) return proj.moduleStrategy === "path_tree";
  return getProfileForProject(proj.projectId)?.strategy === "path_tree";
}

/** 집계 반영 후 path_tree 프로젝트 트리 기본 펼침 (defaults.moduleTreeDefaultExpandDepth) */
function buildDefaultExpandedFromMergedRows() {
  const next = new Set();
  if (scopeId.value === ALL_SCOPE_ID) return next;
  const depth = getModuleTreeDefaultExpandDepth();
  const row = mergedProjectRows.value.find((r) => r.projectId === scopeId.value);
  if (!row || !isPathTreeProject(row)) return next;
  const s = buildDefaultExpandedModulePathSet(row.projectId, row.modules || {}, depth);
  for (const x of s) next.add(x);
  return next;
}

function pathTreeVisibleRows(proj) {
  return visibleModuleTreeRows(proj.projectId, proj.modules || {}, expandedModulePaths.value);
}

function toggleModulePath(projectId, path) {
  const k = `${projectId}::${path}`;
  const next = new Set(expandedModulePaths.value);
  if (next.has(k)) next.delete(k);
  else next.add(k);
  expandedModulePaths.value = next;
}

function isModulePathExpanded(projectId, path) {
  return expandedModulePaths.value.has(`${projectId}::${path}`);
}

function csvEscape(v) {
  const t = String(v ?? "");
  if (/[",\n\r]/.test(t)) {
    return `"${t.replace(/"/g, '""')}"`;
  }
  return t;
}

function triggerCsvDownload(lines, filenamePrefix) {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  const name = `${filenamePrefix}-${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}-${pad(d.getHours())}${pad(d.getMinutes())}.csv`;
  const blob = new Blob(["\uFEFF" + lines.join("\n")], { type: "text/csv;charset=utf-8;" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = name;
  a.click();
  URL.revokeObjectURL(a.href);
}

async function downloadModuleCsv() {
  if (exportingModuleCsv.value) return;
  exportingModuleCsv.value = true;
  try {
    const res = await fetch("/api/metrics/export/issues");
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const d = data.detail ?? data.message;
      window.alert(
        typeof d === "string" ? d : `이슈 내보내기 실패 (${res.status})`,
      );
      return;
    }
    const issues = data.issues ?? [];
    const lines = [];
    lines.push("프로젝트별 Module × Severity — 이슈 펼침 (OPEN, 대시보드 집계와 동일 소스)");
    lines.push(
      [
        "프로젝트",
        "Module",
        "Severity",
        "Component",
        "Line",
        "Rule",
        "Message",
        "Status",
        "Issue key",
      ]
        .map(csvEscape)
        .join(","),
    );
    for (const r of issues) {
      const lineVal = r.line != null && r.line !== "" ? r.line : "";
      lines.push(
        [
          r.projectLabel,
          r.moduleBucket,
          r.severity,
          r.component,
          lineVal,
          r.rule,
          r.message,
          r.status,
          r.key,
        ]
          .map(csvEscape)
          .join(","),
      );
    }
    if (data.errors?.length) {
      lines.push("");
      lines.push("# 일부 프로젝트는 캐시에 이슈 원본이 없어 누락됐을 수 있음");
      for (const e of data.errors) {
        lines.push(csvEscape(`${e.projectId}: ${e.message}`));
      }
    }
    triggerCsvDownload(lines, "sonarqube-module-issues");
  } catch (e) {
    window.alert(String(e?.message || e));
  } finally {
    exportingModuleCsv.value = false;
  }
}
</script>

<template>
  <div class="wrap dashboard">
    <header class="hero">
      <p class="hero__eyebrow">{{ DASHBOARD_HERO.eyebrow }}</p>
      <h1>{{ DASHBOARD_HERO.title }}</h1>
      <p class="hero__sub">{{ DASHBOARD_HERO.subtitle }}</p>
    </header>

    <div class="toolbar dashboard__toolbar">
      <div class="dashboard__toolbar-left">
        <p v-if="snapshotAsOfLabel" class="dashboard-asof">
          <span class="dashboard-asof__lead">정적 분석 집계</span>
          <span class="dashboard-asof__sep" aria-hidden="true">·</span>
          <time class="dashboard-asof__time" :datetime="snapshotAsOfIso">{{ snapshotAsOfLabel }}</time>
        </p>
      </div>
      <div class="dashboard__toolbar-right dashboard__toolbar-right--with-gear">
        <router-link
          class="dashboard-toolbar-gear"
          :to="{ name: 'adminTeamMapping' }"
          title="표준서비스 팀 매칭"
        >
          <img
            :src="dashboardGearIcon"
            alt="표준서비스 팀 매칭"
            width="22"
            height="22"
            decoding="async"
          />
        </router-link>
        <button
          class="btn btn--dashboard-refresh"
          type="button"
          :disabled="loading"
          @click="load"
        >
          {{ loading ? "불러오는 중…" : "새로고침" }}
        </button>
      </div>
    </div>

    <div v-if="err" class="err" role="alert">{{ err }}</div>

    <div v-if="metricErrors.length" class="metric-warn">
      <p v-for="(e, i) in metricErrors" :key="i">
        <strong>{{ e.projectId }}</strong>: {{ e.message }}
      </p>
    </div>

    <div v-if="!loading && isAllScope && !err" class="dashboard-all-banner" role="note">
      ALL: OPEN 이슈 중 <strong>BLOCKER·HIGH·MEDIUM</strong>만 집계합니다. (LOW·INFO 제외)
    </div>

    <template v-if="!loading && displaySummary && !err">
      <section class="dash-summary" aria-label="요약">
        <div class="kpi">
          <span
            class="kpi__label"
            :class="{ 'kpi__label--long': isAllScope }"
            >{{
              isAllScope
                ? "OPEN 이슈 (BLOCKER+HIGH+MEDIUM)"
                : "프로젝트 이슈"
            }}</span>
          <span class="kpi__value">{{ displaySummary.totalIssues.toLocaleString("ko-KR") }}</span>
        </div>
        <div
          class="kpi kpi--risk"
          :class="{ 'kpi--risk-clear': displaySummary.highRisk === 0 }"
        >
          <span class="kpi__label">High risk (BLOCKER+HIGH)</span>
          <span
            class="kpi__value"
            :class="{
              'kpi__value--hr-total': true,
              'kpi__value--hr-total-zero': displaySummary.highRisk === 0,
            }"
            >{{ displaySummary.highRisk.toLocaleString("ko-KR") }}</span>
          <p
            v-if="displaySummary.highRisk === 0"
            class="kpi__hint kpi__hint--hr-zero"
          >
            BLOCKER·HIGH OPEN 이슈 없음
          </p>
          <p
            v-else
            class="kpi__hint kpi__hint--hr-alert"
          >
            BLOCKER·HIGH OPEN 이슈 있음
          </p>
          <div
            v-if="showTeamHighRiskUi"
            class="kpi__team-row"
            aria-label="팀별 High risk 건수"
          >
            <span
              v-for="tid in highRiskTeamOrderSorted"
              :key="tid"
              class="kpi__team-chip"
              :style="{ color: teamHrColors[tid] }"
            >
              <span class="kpi__team-name">{{ highRiskTeamLabels[tid] ?? tid }}</span>
              <strong class="kpi__team-num">{{
                (displayHighRiskByTeam[tid] ?? 0).toLocaleString("ko-KR")
              }}</strong>
            </span>
          </div>
        </div>
        <div class="kpi kpi--mini">
          <span class="kpi__label">Severity 합계</span>
          <div class="kpi__chips">
            <span
              v-for="s in kpiSeverityChips"
              :key="s"
              class="sev-chip"
              :class="`sev-chip--${s.toLowerCase()}`"
            >
              {{ s }} {{ displaySummary.severityTotal[s] ?? 0 }}
            </span>
          </div>
        </div>
      </section>

      <div class="dashboard-scope" role="group" aria-label="차트 범위">
        <label class="field dashboard-scope__field">
          <span class="dashboard-scope__label">프로젝트 (선택 시 집계)</span>
          <select v-model="scopeId" class="select dashboard-scope__select">
            <option v-for="p in projectSelectOptions" :key="p.id" :value="p.id">
              {{ p.label }}
            </option>
          </select>
        </label>
      </div>

      <div class="dash-charts dash-charts--triple">
        <div class="card chart-card">
          <div class="card__head">
            <div class="card__head-main">
              <h2 class="card__title">Severity 분포</h2>
              <p class="card__subtitle">{{ scopeLabel }}{{ isAllScope ? " · B·H·M만" : "" }}</p>
            </div>
          </div>
          <div class="chart-box chart-box--pair">
            <Pie v-if="pieChartData.labels.length" :data="pieChartData" :options="pieOptions" />
            <p v-else class="chart-empty">데이터 없음</p>
          </div>
        </div>
        <div v-if="!isAllScope" class="card chart-card">
          <div class="card__head">
            <div class="card__head-main">
              <h2 class="card__title">Module × Severity (스택)</h2>
              <p class="card__subtitle">{{ scopeLabel }}{{ stackChartSubtitle }}</p>
            </div>
          </div>
          <div class="chart-box chart-box--pair">
            <Bar v-if="chartStackLabels.length" :data="stackedBarData" :options="stackedBarOptions" />
            <p v-else class="chart-empty">데이터 없음</p>
          </div>
        </div>
        <div
          v-if="showTeamHighRiskUi"
          class="card chart-card chart-card--team-hr"
          aria-label="팀별 High risk 차트"
        >
          <div class="card__head">
            <div class="card__head-main">
              <h2 class="card__title">팀별 High risk (BLOCKER+HIGH)</h2>
              <p class="card__subtitle">
                {{ scopeLabel }} · 경로 모듈 토큰 기준 팀 매핑{{ isAllScope ? " · OPEN · B·H·M 집계" : "" }}
              </p>
            </div>
          </div>
          <div class="chart-box chart-box--pair">
            <Bar
              v-if="highRiskTeamBarData.labels?.length"
              :data="highRiskTeamBarData"
              :options="highRiskTeamBarOptions"
            />
            <p v-else class="chart-empty">데이터 없음</p>
          </div>
        </div>
      </div>

      <section
        class="card excel-block excel-block--severity dash-chart-last"
        :aria-label="isAllScope ? '전체 프로젝트 집계' : '선택 프로젝트 집계'"
      >
        <div class="card__head">
          <h2 class="card__title">{{ excelSeveritySectionTitle }}</h2>
        </div>
        <div class="excel-wrap">
          <table class="excel">
            <thead>
              <tr>
                <th>프로젝트</th>
                <th
                  v-for="s in excelSeverityColumns"
                  :key="s"
                  :class="isRiskSeverity(s) ? 'excel__th--risk' : undefined"
                >
                  {{ s }}
                </th>
                <th>TOTAL</th>
                <th class="excel__th--risk">High risk</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in visibleProjectRows" :key="row.projectId">
                <td class="excel__name">{{ row.label }}</td>
                <td
                  v-for="s in excelSeverityColumns"
                  :key="s"
                  class="excel__num"
                  :class="{ 'excel__cell--risk': isRiskSeverity(s) }"
                >
                  <button
                    type="button"
                    class="cell-link"
                    :disabled="!hasProjectKey(row)"
                    @click="goIssues(row.projectId, { severity: s })"
                  >
                    {{ row.severityTotal[s] ?? 0 }}
                  </button>
                </td>
                <td class="excel__num excel__num--strong">
                  <button
                    type="button"
                    class="cell-link"
                    :disabled="!hasProjectKey(row)"
                    @click="goIssues(row.projectId)"
                  >
                    {{ projectRowTotal(row).toLocaleString("ko-KR") }}
                  </button>
                </td>
                <td class="excel__num excel__cell--risk">{{ row.highRisk?.toLocaleString("ko-KR") ?? "—" }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section
        v-if="!isAllScope"
        class="card excel-block excel-block--modules"
        aria-label="선택 프로젝트 Module × Severity"
      >
        <div class="card__head card__head--actions">
          <h2 class="card__title">선택 프로젝트 Module × Severity</h2>
          <button
            type="button"
            class="btn btn--secondary btn--head"
            :disabled="loading || !displaySummary || exportingModuleCsv"
            @click="downloadModuleCsv"
          >
            {{ exportingModuleCsv ? "준비 중…" : "이슈 다운로드 CSV" }}
          </button>
        </div>
        <div
          v-for="proj in visibleProjectRows"
          :key="proj.projectId + '-mod'"
          class="module-block"
        >
          <h3 class="module-block__title">{{ proj.label }}</h3>
          <p v-if="!hasProjectKey(proj)" class="module-section__hint">
            <code>componentKey</code>가 비어 있어 Sonar 집계가 없습니다.
            <template v-if="isPathTreeProject(proj)">
              <code>path_tree</code> 모듈 행은 이슈가 잡힌 경로에서만 표시됩니다.
            </template>
            <template v-else>
              <code>split_after</code> 표시 순: <code>defaults.splitAfterModuleRows</code>(또는 프로필
              <code>defaultModuleRows</code> 재정의) 뒤에 API에만 있는 키가 붙습니다.
            </template>
          </p>
          <p v-else-if="isPathTreeProject(proj)" class="module-section__hint">
            <code>path_tree</code> 프로필: 최초 로드·새로고침 시 경로 깊이
            <strong>{{ moduleTreeDefaultExpandLabel }}</strong>단계까지 기본 펼침.
            그 아래는 <strong>+</strong>로 하위(<code>/</code> 구분)를 펼치거나 접습니다.
            셀 클릭 시 해당 경로 접두로 이슈 목록이 열립니다.
          </p>
          <div class="excel-wrap">
            <table class="excel excel--module-bilingual">
              <thead>
                <tr>
                  <th>업무명</th>
                  <th>경로</th>
                  <th
                    v-for="s in SEVERITY_OPTIONS"
                    :key="s"
                    :class="isRiskSeverity(s) ? 'excel__th--risk' : undefined"
                  >
                    {{ s }}
                  </th>
                  <th>TOTAL</th>
                </tr>
              </thead>
              <tbody v-if="isPathTreeProject(proj)">
                <tr v-for="row in pathTreeVisibleRows(proj)" :key="proj.projectId + '-' + row.path">
                  <td class="excel__name excel__name--ko">
                    {{ tableModuleKo(proj.projectId, row.path) }}
                  </td>
                  <td class="excel__name module-tree__module excel__path-cell">
                    <div class="module-tree__row" :style="{ paddingLeft: row.depth * 0.85 + 'rem' }">
                      <button
                        v-if="row.hasChild"
                        type="button"
                        class="module-tree__toggle"
                        :aria-expanded="isModulePathExpanded(proj.projectId, row.path)"
                        @click="toggleModulePath(proj.projectId, row.path)"
                      >
                        {{ isModulePathExpanded(proj.projectId, row.path) ? "−" : "+" }}
                      </button>
                      <span v-else class="module-tree__toggle module-tree__toggle--ghost" aria-hidden="true" />
                      <code class="module-tree__path">{{ row.path }}</code>
                    </div>
                  </td>
                  <td
                    v-for="s in SEVERITY_OPTIONS"
                    :key="s"
                    class="excel__num"
                    :class="{ 'excel__cell--risk': isRiskSeverity(s) }"
                  >
                    <button
                      type="button"
                      class="cell-link"
                      :disabled="!hasProjectKey(proj)"
                      @click="goIssues(proj.projectId, { module: row.path, severity: s })"
                    >
                      {{ row.counts[s] ?? 0 }}
                    </button>
                  </td>
                  <td class="excel__num excel__num--strong">
                    <button
                      type="button"
                      class="cell-link"
                      :disabled="!hasProjectKey(proj)"
                      @click="goIssues(proj.projectId, { module: row.path })"
                    >
                      {{ moduleTotal(row.counts).toLocaleString("ko-KR") }}
                    </button>
                  </td>
                </tr>
              </tbody>
              <tbody v-else>
                <tr v-for="mRow in moduleRowsFor(proj)" :key="proj.projectId + '-' + mRow.name">
                  <td class="excel__name excel__name--ko">
                    {{ tableModuleKo(proj.projectId, mRow.name) }}
                  </td>
                  <td class="excel__name excel__path-cell">
                    <code>{{ mRow.name }}</code>
                  </td>
                  <td
                    v-for="s in SEVERITY_OPTIONS"
                    :key="s"
                    class="excel__num"
                    :class="{ 'excel__cell--risk': isRiskSeverity(s) }"
                  >
                    <button
                      type="button"
                      class="cell-link"
                      :disabled="!hasProjectKey(proj)"
                      @click="goIssues(proj.projectId, { module: mRow.name, severity: s })"
                    >
                      {{ mRow.counts[s] ?? 0 }}
                    </button>
                  </td>
                  <td class="excel__num excel__num--strong">
                    <button
                      type="button"
                      class="cell-link"
                      :disabled="!hasProjectKey(proj)"
                      @click="goIssues(proj.projectId, { module: mRow.name })"
                    >
                      {{ moduleTotal(mRow.counts).toLocaleString("ko-KR") }}
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </section>
    </template>

    <p v-else-if="!loading && !err && !displaySummary" class="empty-note">
      집계할 프로젝트가 없습니다. <code>config/component_projects.json</code>에
      <code>componentKey</code>를 설정하세요.
    </p>

    <Teleport to="body">
      <Transition name="load-more-fade">
        <div
          v-if="loading"
          class="load-more-overlay"
          role="status"
          aria-live="polite"
          aria-busy="true"
        >
          <div class="load-more-overlay__content">
            <div class="load-more-overlay__logo">
              <img
                class="load-more-overlay__img"
                :src="LOAD_MORE_CHEVRON_SRC"
                alt=""
                decoding="async"
                fetchpriority="low"
              />
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

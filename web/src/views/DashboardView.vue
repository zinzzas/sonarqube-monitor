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
import { computed, nextTick, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { Bar, Pie } from "vue-chartjs";
import { DASHBOARD_HERO } from "../config/dashboardConfig.js";
import { COMPONENT_PROJECTS } from "../config/componentProjects.js";
import {
  getDefaultModuleRowsForProject,
  getModuleTreeDefaultExpandDepth,
  getProfileForProject,
} from "../config/moduleGrouping.js";
import { LOAD_MORE_CHEVRON_SRC } from "../loadingOverlay.js";
import { buildDefaultExpandedModulePathSet, visibleModuleTreeRows } from "../moduleTree.js";
import { SEVERITY_OPTIONS } from "../severity.js";

ChartJS.register(ArcElement, BarElement, CategoryScale, LinearScale, Tooltip, Legend);

const router = useRouter();

const loading = ref(true);
const err = ref("");
const payload = ref(null);
/** 마지막으로 집계 API를 성공적으로 받은 시각 (새로고침마다 갱신) */
const lastFetchedAt = ref(null);

/** path_tree 표 펼침 — load()보다 먼저 선언 (TDZ 회피) */
const expandedModulePaths = ref(new Set());

/** `/api/metrics/dashboard`는 Sonar 전량 이슈 집계로 수분 걸릴 수 있음. 무한 로딩 방지용. */
const DASHBOARD_FETCH_TIMEOUT_MS = 120_000;

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
    const res = await fetch("/api/metrics/dashboard", { signal: controller.signal });
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

onMounted(load);

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
const globalModules = computed(() => payload.value?.globalModules ?? {});
const globalChartStackModules = computed(() => payload.value?.globalChartStackModules ?? {});
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
      return { ...row };
    }
    return {
      projectId: p.id,
      label: p.label,
      componentKey: String(p.componentKey ?? "").trim(),
      totalIssues: 0,
      severityTotal: emptySevRow(),
      highRisk: 0,
      modules: {},
      chartStackModules: {},
    };
  });
});

/** 'global' | 프로젝트 id — 상단 차트·요약 KPI 범위 */
const scopeId = ref("global");

watch(mergedProjectRows, (rows) => {
  if (scopeId.value !== "global" && !rows.some((r) => r.projectId === scopeId.value)) {
    scopeId.value = "global";
  }
});

const activeProjectRow = computed(() => {
  if (scopeId.value === "global") return null;
  return mergedProjectRows.value.find((r) => r.projectId === scopeId.value) ?? null;
});

/** KPI·차트에 쓰는 요약 (범위가 전체이면 summary, 아니면 해당 프로젝트) */
const displaySummary = computed(() => {
  if (scopeId.value === "global") return summary.value;
  const row = activeProjectRow.value;
  if (!row) return summary.value;
  return {
    totalIssues: row.totalIssues ?? 0,
    highRisk: row.highRisk ?? 0,
    severityTotal: row.severityTotal ?? emptySevRow(),
  };
});

const scopeLabel = computed(() => {
  if (scopeId.value === "global") return "전체 프로젝트 합산";
  return activeProjectRow.value?.label ?? scopeId.value;
});

const severityForScope = computed(() => displaySummary.value?.severityTotal ?? null);

const moduleMapForScope = computed(() => {
  if (scopeId.value === "global") return globalModules.value;
  return activeProjectRow.value?.modules ?? {};
});

/** 스택 막대: API chartStackModules (anchor 이후 첫 세그먼트만 집계) */
const chartStackMapForScope = computed(() => {
  if (scopeId.value === "global") return globalChartStackModules.value;
  return activeProjectRow.value?.chartStackModules ?? {};
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
  return {
    labels: SEVERITY_OPTIONS,
    datasets: [
      {
        backgroundColor: SEVERITY_OPTIONS.map((s) => SEV_COLORS[s] ?? "#94a3b8"),
        data: SEVERITY_OPTIONS.map((s) => st[s] ?? 0),
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
  const labels = chartStackLabels.value;
  return {
    labels,
    datasets: SEVERITY_OPTIONS.map((sev) => ({
      label: sev,
      data: labels.map((key) => gm[key]?.[sev] ?? 0),
      backgroundColor: SEV_COLORS[sev] ?? "#94a3b8",
    })),
  };
});

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
  const depth = getModuleTreeDefaultExpandDepth();
  const next = new Set();
  for (const row of mergedProjectRows.value) {
    if (!isPathTreeProject(row)) continue;
    const s = buildDefaultExpandedModulePathSet(row.projectId, row.modules || {}, depth);
    for (const x of s) {
      next.add(x);
    }
  }
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

function moduleSegmentLabel(path) {
  if (!path) return "—";
  const parts = path.split("/");
  return parts[parts.length - 1] || path;
}

function modulePathsSortedForCsv(modMap) {
  const keys = Object.keys(modMap || {});
  return keys.sort((a, b) => {
    const da = a.split("/").length;
    const db = b.split("/").length;
    if (da !== db) return da - db;
    return a.localeCompare(b);
  });
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

function downloadSeverityCsv() {
  const rows = mergedProjectRows.value;
  const lines = [];
  lines.push("프로젝트별 Severity (엑셀형)");
  lines.push(["프로젝트", ...SEVERITY_OPTIONS, "TOTAL", "High risk"].map(csvEscape).join(","));
  for (const row of rows) {
    lines.push(
      [
        row.label,
        ...SEVERITY_OPTIONS.map((s) => row.severityTotal[s] ?? 0),
        projectRowTotal(row),
        row.highRisk ?? 0,
      ]
        .map(csvEscape)
        .join(","),
    );
  }
  triggerCsvDownload(lines, "sonarqube-severity");
}

function downloadModuleCsv() {
  const rows = mergedProjectRows.value;
  const lines = [];
  lines.push("프로젝트별 Module × Severity");
  for (const proj of rows) {
    lines.push(`${proj.label} — Module × Severity`);
    lines.push(["Module", ...SEVERITY_OPTIONS, "TOTAL"].map(csvEscape).join(","));
    const m = proj.modules || {};
    if (isPathTreeProject(proj)) {
      for (const path of modulePathsSortedForCsv(m)) {
        const counts = m[path] || {};
        lines.push(
          [
            path,
            ...SEVERITY_OPTIONS.map((s) => counts[s] ?? 0),
            moduleTotal(counts),
          ]
            .map(csvEscape)
            .join(","),
        );
      }
    } else {
      for (const mRow of moduleRowsFor(proj)) {
        lines.push(
          [
            mRow.name,
            ...SEVERITY_OPTIONS.map((s) => mRow.counts[s] ?? 0),
            moduleTotal(mRow.counts),
          ]
            .map(csvEscape)
            .join(","),
        );
      }
    }
    lines.push("");
  }
  triggerCsvDownload(lines, "sonarqube-module");
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
      <div class="dashboard__toolbar-right">
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

    <template v-if="!loading && displaySummary && !err">
      <section class="dash-summary" aria-label="요약">
        <div class="kpi">
          <span class="kpi__label">{{ scopeId === "global" ? "전체 이슈" : "프로젝트 이슈" }}</span>
          <span class="kpi__value">{{ displaySummary.totalIssues.toLocaleString("ko-KR") }}</span>
        </div>
        <div class="kpi kpi--risk">
          <span class="kpi__label">High risk (BLOCKER+HIGH)</span>
          <span class="kpi__value">{{ displaySummary.highRisk.toLocaleString("ko-KR") }}</span>
        </div>
        <div class="kpi kpi--mini">
          <span class="kpi__label">Severity 합계</span>
          <div class="kpi__chips">
            <span v-for="s in SEVERITY_OPTIONS" :key="s" class="sev-chip" :class="`sev-chip--${s.toLowerCase()}`">
              {{ s }} {{ displaySummary.severityTotal[s] ?? 0 }}
            </span>
          </div>
        </div>
      </section>

      <div class="dashboard-scope" role="group" aria-label="차트 범위">
        <label class="field dashboard-scope__field">
          <span class="dashboard-scope__label">차트·요약 범위</span>
          <select v-model="scopeId" class="select dashboard-scope__select">
            <option value="global">전체 프로젝트 합산</option>
            <option v-for="p in mergedProjectRows" :key="p.projectId" :value="p.projectId">
              {{ p.label }}
            </option>
          </select>
        </label>
      </div>

      <div class="dash-charts">
        <div class="card chart-card">
          <div class="card__head">
            <div class="card__head-main">
              <h2 class="card__title">Severity 분포</h2>
              <p class="card__subtitle">{{ scopeLabel }}</p>
            </div>
          </div>
          <div class="chart-box">
            <Pie v-if="pieChartData.labels.length" :data="pieChartData" :options="pieOptions" />
            <p v-else class="chart-empty">데이터 없음</p>
          </div>
        </div>
        <div class="card chart-card">
          <div class="card__head">
            <div class="card__head-main">
              <h2 class="card__title">Module × Severity (스택)</h2>
              <p class="card__subtitle">{{ scopeLabel }}{{ stackChartSubtitle }}</p>
            </div>
          </div>
          <div class="chart-box chart-box--tall">
            <Bar v-if="chartStackLabels.length" :data="stackedBarData" :options="stackedBarOptions" />
            <p v-else class="chart-empty">데이터 없음</p>
          </div>
        </div>
      </div>

      <section class="card excel-block excel-block--severity dash-chart-last" aria-label="프로젝트별 집계">
        <div class="card__head card__head--actions">
          <h2 class="card__title">프로젝트별 Severity (엑셀형)</h2>
          <button
            type="button"
            class="btn btn--secondary btn--head"
            :disabled="loading || !displaySummary"
            @click="downloadSeverityCsv"
          >
            엑셀 다운로드 (CSV)
          </button>
        </div>
        <div class="excel-wrap">
          <table class="excel">
            <thead>
              <tr>
                <th>프로젝트</th>
                <th
                  v-for="s in SEVERITY_OPTIONS"
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
              <tr v-for="row in mergedProjectRows" :key="row.projectId">
                <td class="excel__name">{{ row.label }}</td>
                <td
                  v-for="s in SEVERITY_OPTIONS"
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

      <section class="card excel-block excel-block--modules" aria-label="프로젝트별 Module × Severity">
        <div class="card__head card__head--actions">
          <h2 class="card__title">프로젝트별 Module × Severity</h2>
          <button
            type="button"
            class="btn btn--secondary btn--head"
            :disabled="loading || !displaySummary"
            @click="downloadModuleCsv"
          >
            엑셀 다운로드 (CSV)
          </button>
        </div>
        <div
          v-for="proj in mergedProjectRows"
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
            <table class="excel">
              <thead>
                <tr>
                  <th>Module</th>
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
                  <td class="excel__name module-tree__module">
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
                      <span class="module-tree__path" :title="row.path">{{ moduleSegmentLabel(row.path) }}</span>
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
                  <td class="excel__name">{{ mRow.name }}</td>
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

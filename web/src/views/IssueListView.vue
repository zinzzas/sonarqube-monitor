<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useComponentProjectSelect } from "../composables/useComponentProjectSelect.js";
import { useSonarIssuesPaging } from "../composables/useSonarIssuesPaging.js";
import { issueMatchesModuleFilter } from "../module.js";
import { LOAD_MORE_CHEVRON_SRC } from "../loadingOverlay.js";
import {
  SEVERITY_OPTIONS,
  STATUS_OPTIONS,
  displaySeverity,
  severitiesToApiParam,
} from "../severity.js";

const route = useRoute();
const router = useRouter();

/** SonarQube 웹 UI 베이스 (`/api/sonar/config`, 토큰 없음) */
const sonarBaseUrl = ref("");

const { projectOptions, selectedProjectId, componentKeys } = useComponentProjectSelect();

const pageSize = ref(50);
const sortBySeverity = ref("severity_desc");
const filterSeverities = ref([...SEVERITY_OPTIONS]);
const filterStatuses = ref([...STATUS_OPTIONS]);

const {
  items: issues,
  total,
  loadedCount,
  hasMore,
  loading,
  loadingMore,
  error,
  loadFirst,
  sentinelEl,
} = useSonarIssuesPaging({
  pageSize,
  componentKeys,
  filterSeverities,
  filterStatuses,
  sortBySeverity,
  severitiesToApiParam,
});

const severitySortOptions = [
  { value: "severity_desc", label: "Severity · 높음 우선 (BLOCKER → INFO)" },
  { value: "severity_asc", label: "Severity · 낮음 우선 (INFO → BLOCKER)" },
  { value: "creation_desc", label: "생성일 · 최신순" },
  { value: "creation_asc", label: "생성일 · 오래된 순" },
  { value: "", label: "기본 (SonarQube 서버 기본)" },
];

const severityClass = (raw) => {
  const s = displaySeverity(raw);
  const m = {
    BLOCKER: "sev-blocker",
    HIGH: "sev-high",
    MEDIUM: "sev-medium",
    LOW: "sev-low",
    INFO: "sev-info",
  };
  return m[s] ?? "sev-default";
};

function authorCell(row) {
  return row.authorName || row.author || "—";
}

function componentLabel(row) {
  return row.component || "—";
}

/** Sonar API 이슈의 project, 없으면 component 의 `프로젝트키:경로` 앞부분 */
function issueProjectKey(row) {
  if (row.project) return String(row.project).trim();
  const c = row.component;
  if (typeof c === "string" && c.includes(":")) {
    return c.split(":")[0].trim();
  }
  return "";
}

/** SonarQube 웹 이슈 페이지 URL (`/project/issues?id=&open=`). */
function sonarIssueWebUrl(row) {
  const base = sonarBaseUrl.value;
  const issueKey = row.key || row.issueKey;
  const projectKey = issueProjectKey(row);
  if (!base || !issueKey || !projectKey) return null;
  const q = new URLSearchParams({ id: projectKey, open: String(issueKey) });
  return `${base}/project/issues?${q.toString()}`;
}

onMounted(async () => {
  try {
    const res = await fetch("/api/sonar/config");
    if (!res.ok) return;
    const data = await res.json();
    if (data.sonar_base_url) {
      sonarBaseUrl.value = String(data.sonar_base_url).replace(/\/$/, "");
    }
  } catch {
    /* 오프라인·프록시 실패 시 링크 없이 표시만 */
  }
});

function ruleLabel(row) {
  return row.rule || row.ruleName || "—";
}

function formatDate(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return String(iso);
  return d.toLocaleString("ko-KR");
}

const moduleFilter = computed(() => {
  const m = route.query.module;
  return typeof m === "string" && m ? m : "";
});

const activeProjectId = computed(() => selectedProjectId.value || String(route.params.projectId || ""));

const displayedIssues = computed(() => {
  const m = moduleFilter.value;
  if (!m) return issues.value;
  const pid = activeProjectId.value;
  return issues.value.filter((row) => issueMatchesModuleFilter(row.component, pid, m));
});

const totalLabel = computed(() => {
  const t = total.value;
  if (t == null) return "전체 건수 미제공";
  return `전체 ${t.toLocaleString("ko-KR")}건`;
});

const hasData = computed(() => !loading.value && !error.value);

const selectedProjectKeyUnset = computed(() => {
  const id = selectedProjectId.value;
  if (!id) return false;
  const row = projectOptions.find((p) => p.id === id);
  return row != null && !String(row.componentKey ?? "").trim();
});

const loadStateLabel = computed(() => {
  if (loadingMore.value) return "추가 로딩 중";
  if (hasMore.value && issues.value.length) return "더 불러올 수 있음";
  if (issues.value.length) return "마지막까지 로드됨";
  return "";
});

const filterHint = computed(() => {
  const parts = [];
  if (moduleFilter.value) parts.push(`모듈: ${moduleFilter.value}`);
  const sev = route.query.severity;
  if (typeof sev === "string" && sev && SEVERITY_OPTIONS.includes(sev)) {
    parts.push(`Severity: ${sev}`);
  }
  return parts.length ? parts.join(" · ") : "";
});

function goDashboard() {
  router.push({ name: "dashboard" });
}

watch(
  () => ({
    pid: route.params.projectId,
    sev: route.query.severity,
  }),
  ({ pid, sev }) => {
    if (pid && typeof pid === "string") {
      selectedProjectId.value = pid;
    }
    if (typeof sev === "string" && sev && SEVERITY_OPTIONS.includes(sev)) {
      filterSeverities.value = [sev];
    } else {
      filterSeverities.value = [...SEVERITY_OPTIONS];
    }
  },
  { immediate: true },
);

function onProjectSelectChange() {
  const id = selectedProjectId.value;
  if (!id) return;
  router.replace({
    name: "issues",
    params: { projectId: id },
    query: { ...route.query },
  });
}
</script>

<template>
  <div class="wrap issue-list">
    <nav class="crumb" aria-label="경로">
      <button type="button" class="crumb__link" @click="goDashboard">대시보드</button>
      <span class="crumb__sep" aria-hidden="true">/</span>
      <span class="crumb__here">이슈 목록</span>
    </nav>

    <header class="hero">
      <p class="hero__eyebrow">Issue monitoring</p>
      <h1>프로젝트별 이슈 상세 목록</h1>
      <p class="hero__sub">
        대시보드에서 숫자를 눌러 들어온 경우, 아래에 모듈·Severity 필터가 반영됩니다. 표는 스크롤 시
        다음 페이지가 이어 붙습니다.
      </p>
    </header>

    <p v-if="filterHint" class="route-filter-hint">{{ filterHint }} (목록은 component 기준으로 추가 필터)</p>

    <div class="issue-list__query-toolbar">
      <button
        class="btn btn--dashboard-refresh issue-list__query-btn"
        type="button"
        :disabled="loading"
        @click="loadFirst"
      >
        {{ loading ? "조회 중…" : "조회" }}
      </button>
    </div>

    <section class="card card--filters issue-list-filters" aria-label="검색 필터">
      <div class="card__head">
        <h2 class="card__title">Filters</h2>
      </div>

      <div class="filter-grid-row filter-grid-row--project-target">
        <span class="filter-title filter-title--target">대상 프로젝트</span>
        <div class="filter-grid-row__stack filter-grid-row__stack--project">
          <select
            v-model="selectedProjectId"
            class="select filter-inline-select filter-inline-select--project"
            @change="onProjectSelectChange"
          >
            <option value="">프로젝트 선택</option>
            <option v-for="p in projectOptions" :key="p.id" :value="p.id">
              {{ p.label }}
            </option>
          </select>
          <p v-if="selectedProjectKeyUnset" class="field-hint filter-grid-row__hint">
            이 프로젝트의 componentKey 는 아직 비어 있습니다.
            <code>config/component_projects.json</code>에서 키를 넣어 주세요.
          </p>
        </div>
      </div>

      <div class="filter-grid-row filter-grid-row--sort-only">
        <span class="filter-title">정렬</span>
        <div class="filter-grid-row__main filter-grid-row__main--sort-only">
          <select v-model="sortBySeverity" class="select filter-inline-select filter-inline-select--sort">
            <option v-for="opt in severitySortOptions" :key="opt.value || 'default'" :value="opt.value">
              {{ opt.label }}
            </option>
          </select>
        </div>
      </div>

      <div class="filter-grid-row">
        <span class="filter-title">Severity</span>
        <div class="filter-grid-row__main">
          <div class="chip-group">
            <label
              v-for="s in SEVERITY_OPTIONS"
              :key="s"
              class="chk-chip"
              :class="'chk-chip--' + s.toLowerCase()"
            >
              <input v-model="filterSeverities" type="checkbox" :value="s" />
              <span class="chk-chip__face">{{ s }}</span>
            </label>
          </div>
        </div>
      </div>

      <div class="filter-grid-row">
        <span class="filter-title">Status</span>
        <div class="filter-grid-row__main">
          <div class="chip-group">
            <label v-for="st in STATUS_OPTIONS" :key="st" class="chk-chip">
              <input v-model="filterStatuses" type="checkbox" :value="st" />
              <span class="chk-chip__face">{{ st }}</span>
            </label>
          </div>
        </div>
      </div>
    </section>

    <div v-if="error" class="err" role="alert">{{ error }}</div>

    <div class="issue-list__stats-row">
      <div class="issue-list__stats-row__left">
        <div v-if="hasData && (issues.length || total != null)" class="stats issue-list__stats">
          <span class="stat-pill">
            <span class="stat-dot" :class="{ 'stat-dot--idle': total == null }" aria-hidden="true" />
            {{ totalLabel }}
          </span>
          <span v-if="displayedIssues.length" class="stat-pill stat-pill--muted">
            표시 {{ displayedIssues.length.toLocaleString("ko-KR") }}건
            <template v-if="moduleFilter"> (필터 후)</template>
          </span>
          <span v-if="loadStateLabel" class="stat-pill stat-pill--muted">{{ loadStateLabel }}</span>
        </div>
      </div>
      <div class="issue-list__pagesize-inline">
        <span class="filter-inline-label">pageSize</span>
        <input
          v-model.number="pageSize"
          class="filter-inline-input filter-inline-input--pagesize"
          type="number"
          min="1"
          max="500"
        />
      </div>
    </div>

    <div class="table-panel">
      <table class="tbl">
        <thead>
          <tr>
            <th>Severity</th>
            <th>Status</th>
            <th>Message</th>
            <th>Rule</th>
            <th>Component</th>
            <th>Line</th>
            <th>Author</th>
            <th>생성</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="hasData && !displayedIssues.length">
            <td colspan="8" class="empty">
              프로젝트를 선택하고 조회하거나, 조건·모듈 필터에 맞는 이슈가 없습니다.
            </td>
          </tr>
          <tr v-for="row in displayedIssues" :key="row.key || row.issueKey || JSON.stringify(row)">
            <td>
              <span class="pill" :class="severityClass(row.severity)">
                {{ displaySeverity(row.severity) }}
              </span>
            </td>
            <td>{{ row.status || "—" }}</td>
            <td class="msg">{{ row.message || "—" }}</td>
            <td class="mono small">{{ ruleLabel(row) }}</td>
            <td class="mono small">
              <a
                v-if="sonarIssueWebUrl(row)"
                :href="sonarIssueWebUrl(row)"
                class="tbl__sonar-link"
                target="_blank"
                rel="noopener noreferrer"
                title="SonarQube에서 이 이슈 열기 (새 탭)"
              >{{ componentLabel(row) }}</a>
              <template v-else>{{ componentLabel(row) }}</template>
            </td>
            <td class="mono">{{ row.line != null ? row.line : "—" }}</td>
            <td>{{ authorCell(row) }}</td>
            <td class="small">{{ formatDate(row.creationDate) }}</td>
          </tr>
          <tr v-if="hasMore" ref="sentinelEl" class="sentinel-row">
            <td colspan="8" class="sentinel-row__cell">
              <span v-if="!loadingMore" class="sentinel-row__hint">스크롤하면 더 불러옵니다</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <Teleport to="body">
      <Transition name="load-more-fade">
        <div
          v-if="loading || loadingMore"
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

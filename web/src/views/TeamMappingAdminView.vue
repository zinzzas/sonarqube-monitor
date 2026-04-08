<script setup>
import { computed, onMounted, ref } from "vue";
import segmentLabels from "../../../config/module_segment_labels.json";
import { setRuntimeTeamMapping } from "../lib/teamIdForIssue.js";
import { notifyTeamMappingUpdated } from "../lib/teamMappingEvents.js";

/** 서버 GET 진행 중(폼은 `config` 번들로 먼저 채움) */
/** 페이지 상단 안내 — 설정 파일이 아닌 UI 고정 문구 */
const TEAM_MAPPING_PAGE_INTRO =
  "팀별로 등록한 경로 매칭 규칙에 따라 이슈가 그룹핑됩니다.";

const loading = ref(true);
const saving = ref(false);
const err = ref("");
const saveOk = ref("");

/** @type {import('vue').Ref<Array<{ teamId: string; label: string; modulesStr: string; matchMode: 'first' | 'any' }>>} */
const precedence = ref([]);
const fallbackTeamId = ref("");
const fallbackLabel = ref("");

const tokenInput = ref("");
const showTokenPanel = ref(false);

function adminHeaders() {
  const headers = { Accept: "application/json" };
  const t = sessionStorage.getItem("adminTeamMappingToken");
  if (t) headers.Authorization = `Bearer ${t}`;
  return headers;
}

function modulesToStr(arr) {
  if (!Array.isArray(arr) || !arr.length) return "";
  return arr.map((s) => String(s).trim()).filter(Boolean).join(", ");
}

function strToModules(s) {
  return String(s || "")
    .split(/[,，\s]+/u)
    .map((x) => x.trim().toLowerCase())
    .filter(Boolean);
}

function emptyRow() {
  return { teamId: "", label: "", modulesStr: "", matchMode: /** @type {'any'} */ ("any") };
}

/** 구형 when(firstModule/anyModule 등) → 폼 한 줄 */
function legacyWhenToForm(w) {
  const fm = w.firstModule ?? w.firstSegment;
  const am = w.anyModule ?? w.anySegment;
  const fa = Array.isArray(fm) ? fm : [];
  const aa = Array.isArray(am) ? am : [];
  if (fa.length && !aa.length) {
    return { modulesStr: modulesToStr(fa), matchMode: /** @type {'first'} */ ("first") };
  }
  if (aa.length && !fa.length) {
    return { modulesStr: modulesToStr(aa), matchMode: /** @type {'any'} */ ("any") };
  }
  if (fa.length && aa.length) {
    const merged = [...new Set([...fa.map((x) => String(x)), ...aa.map((x) => String(x))])];
    return { modulesStr: modulesToStr(merged), matchMode: /** @type {'any'} */ ("any") };
  }
  return { modulesStr: "", matchMode: /** @type {'any'} */ ("any") };
}

function applyLoaded(tm) {
  const prec = Array.isArray(tm?.precedence) ? tm.precedence : [];
  precedence.value = prec.map((row) => {
    const w = row?.when && typeof row.when === "object" ? row.when : {};
    const base = {
      teamId: row?.teamId != null ? String(row.teamId).trim() : "",
      label: row?.label != null ? String(row.label).trim() : "",
    };
    if (Array.isArray(w.modules) && w.modules.length > 0) {
      const matchMode =
        w.match === "first" || w.match === "any" ? w.match : /** @type {'any'} */ ("any");
      return {
        ...base,
        modulesStr: modulesToStr(w.modules),
        matchMode,
      };
    }
    const leg = legacyWhenToForm(w);
    return { ...base, ...leg };
  });
  if (!precedence.value.length) {
    precedence.value = [emptyRow()];
  }
  const fb = tm?.fallback && typeof tm.fallback === "object" ? tm.fallback : {};
  fallbackTeamId.value = fb.teamId != null ? String(fb.teamId).trim() : "";
  fallbackLabel.value = fb.label != null ? String(fb.label).trim() : "";
}

function buildPayload() {
  const prec = precedence.value.map((row) => ({
    teamId: row.teamId.trim(),
    label: row.label.trim(),
    when: {
      modules: strToModules(row.modulesStr),
      match: row.matchMode,
    },
  }));
  return {
    precedence: prec,
    fallback: {
      teamId: fallbackTeamId.value.trim(),
      label: fallbackLabel.value.trim(),
    },
  };
}

const canSave = computed(() => {
  if (saving.value) return false;
  for (const row of precedence.value) {
    const mods = strToModules(row.modulesStr);
    if (!row.teamId.trim() || !mods.length) return false;
  }
  return Boolean(fallbackTeamId.value.trim());
});

/** 빌드에 포함된 JSON으로 즉시 폼 채움 → 이후 GET으로 서버 디스크 기준 덮어씀 */
applyLoaded(segmentLabels.teamMapping ?? {});

/**
 * @param {{ preserveSaveBanner?: boolean }} [options]
 */
async function load(options = {}) {
  const preserveSaveBanner = options.preserveSaveBanner === true;
  loading.value = true;
  err.value = "";
  if (!preserveSaveBanner) {
    saveOk.value = "";
  }
  try {
    const res = await fetch("/api/admin/team-mapping", {
      headers: adminHeaders(),
      cache: "no-store",
    });
    const data = await res.json().catch(() => ({}));
    if (res.status === 401 || res.status === 403) {
      showTokenPanel.value = true;
      err.value =
        res.status === 403
          ? "관리 토큰이 올바르지 않습니다. 아래에 토큰을 입력한 뒤 다시 시도하세요."
          : "관리 API에 Bearer 토큰이 필요합니다. 아래에 토큰을 입력하세요. (아래 폼은 저장소에 번들된 JSON 미리보기입니다.)";
      return;
    }
    if (!res.ok) {
      const d = data.detail ?? data.message;
      err.value = typeof d === "string" ? d : JSON.stringify(d ?? res.statusText);
      err.value += " — 아래 폼은 번들된 JSON 기준입니다. API가 복구되면 되돌리기로 동기화하세요.";
      return;
    }
    showTokenPanel.value = false;
    applyLoaded(data.teamMapping);
    setRuntimeTeamMapping(data.teamMapping);
  } catch (e) {
    err.value = `${String(e?.message || e)} — 아래 폼은 번들된 JSON 기준입니다.`;
  } finally {
    loading.value = false;
  }
}

async function save() {
  if (!canSave.value) return;
  saving.value = true;
  err.value = "";
  saveOk.value = "";
  try {
    const res = await fetch("/api/admin/team-mapping", {
      method: "PUT",
      headers: { ...adminHeaders(), "Content-Type": "application/json" },
      body: JSON.stringify(buildPayload()),
    });
    const data = await res.json().catch(() => ({}));
    if (res.status === 401 || res.status === 403) {
      showTokenPanel.value = true;
      err.value = "저장이 거부되었습니다. 토큰을 확인하세요.";
      return;
    }
    if (!res.ok) {
      const d = data.detail;
      if (Array.isArray(d)) {
        err.value = d.map((x) => x.msg || JSON.stringify(x)).join(" ");
      } else if (typeof d === "string") {
        err.value = d;
      } else {
        err.value = JSON.stringify(d ?? data);
      }
      return;
    }
    applyLoaded(data.teamMapping);
    setRuntimeTeamMapping(data.teamMapping);
    notifyTeamMappingUpdated();
    await load({ preserveSaveBanner: true });
    saveOk.value =
      "저장했습니다. 디스크·대시보드 캐시가 갱신되었고, 열린 대시보드는 자동으로 다시 불러옵니다(팀 버킷 재계산을 위해 Sonar 이슈를 다시 가져올 수 있습니다).";
  } catch (e) {
    err.value = String(e?.message || e);
  } finally {
    saving.value = false;
  }
}

function storeToken() {
  const t = tokenInput.value.trim();
  if (t) sessionStorage.setItem("adminTeamMappingToken", t);
  else sessionStorage.removeItem("adminTeamMappingToken");
  load();
}

function addRow() {
  precedence.value = [...precedence.value, emptyRow()];
}

function removeRow(i) {
  const next = precedence.value.filter((_, j) => j !== i);
  precedence.value = next.length ? next : [emptyRow()];
}

function moveRow(i, delta) {
  const j = i + delta;
  if (j < 0 || j >= precedence.value.length) return;
  const copy = [...precedence.value];
  const t = copy[i];
  copy[i] = copy[j];
  copy[j] = t;
  precedence.value = copy;
}

function revert() {
  load();
}

onMounted(() => {
  load();
});
</script>

<template>
  <div class="wrap dashboard admin-team-mapping">
    <nav class="crumb" aria-label="경로">
      <router-link :to="{ name: 'dashboard' }" class="crumb__link">대시보드</router-link>
      <span class="crumb__sep" aria-hidden="true">/</span>
      <span class="crumb__here">High risk 팀 매칭</span>
    </nav>

    <header class="hero">
      <p class="hero__eyebrow">설정</p>
      <h1>High risk 팀 매칭</h1>
      <div class="admin-team-mapping__intro">
        <p class="hero__sub">
          BLOCKER·HIGH 이슈를 어느 개발팀으로 맵핑할지 정하는 규칙입니다. 아래 표는 <strong>개발팀과 시스템 약어를 맵핑</strong>하고 개발팀 기준으로 그룹핑 관리할 수 있고, 맵핑이 안될 경우 <strong>fallback</strong>으로 맵핑됩니다.
        </p>
        <p class="hero__sub">
          <strong>modules</strong> — 경로에서 나온 시스템 약어(쉼표·공백 구분, 저장 시 소문자).
          <strong>match</strong> — <code>first</code> 맨 앞 토큰만, <code>any</code> 경로 어디든 일치.
        </p>
      </div>
    </header>

    <div class="toolbar dashboard__toolbar admin-team-mapping__toolbar">
      <div class="dashboard__toolbar-right admin-team-mapping__toolbar-actions">
        <p v-if="loading" class="admin-team-mapping__sync-hint" role="status">서버와 동기화 중…</p>
        <button type="button" class="btn btn--secondary btn--head" :disabled="loading" @click="revert">
          되돌리기
        </button>
        <button type="button" class="btn btn--dashboard-refresh" :disabled="!canSave || saving" @click="save">
          {{ saving ? "저장 중…" : "저장" }}
        </button>
      </div>
    </div>

    <div v-if="showTokenPanel" class="card card--filters admin-team-mapping__token-card" role="region" aria-label="API 인증">
      <div class="card__head">
        <h2 class="card__title">관리 API 토큰</h2>
      </div>
      <label class="field">
        <span>Bearer 토큰</span>
        <input v-model="tokenInput" type="password" autocomplete="off" placeholder="환경 변수 ADMIN_TEAM_MAPPING_TOKEN 값" />
      </label>
      <p class="field-hint">브라우저 sessionStorage에만 보관되며, 탭을 닫기 전까지 유지됩니다.</p>
      <button type="button" class="btn btn--dashboard-refresh" @click="storeToken">토큰 적용 후 다시 불러오기</button>
    </div>

    <div v-if="err" class="err" role="alert">{{ err }}</div>
    <div v-if="saveOk" class="admin-team-mapping__ok" role="status">{{ saveOk }}</div>

    <section class="card admin-team-mapping__note" aria-label="안내">
      <p class="admin-team-mapping__note-text">{{ TEAM_MAPPING_PAGE_INTRO }}</p>
    </section>

    <section class="card excel-block admin-team-mapping__rules" aria-label="precedence 규칙">
      <div class="card__head card__head--actions">
        <h2 class="card__title">precedence (순서 = 우선순위)</h2>
        <button type="button" class="btn btn--secondary btn--head" @click="addRow">행 추가</button>
      </div>
      <div class="excel-wrap admin-team-mapping__table-wrap">
        <table class="excel admin-team-mapping__table">
          <thead>
            <tr>
              <th class="admin-team-mapping__th-order">순서</th>
              <th>teamId</th>
              <th>라벨</th>
              <th>modules</th>
              <th>match</th>
              <th class="admin-team-mapping__th-actions" />
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, i) in precedence" :key="'p-' + i">
              <td class="excel__num admin-team-mapping__order-cell">
                <div class="admin-team-mapping__order-btns">
                  <button type="button" class="btn btn--secondary btn--icon" :disabled="i === 0" @click="moveRow(i, -1)" aria-label="위로">
                    ↑
                  </button>
                  <button
                    type="button"
                    class="btn btn--secondary btn--icon"
                    :disabled="i === precedence.length - 1"
                    @click="moveRow(i, 1)"
                    aria-label="아래로"
                  >
                    ↓
                  </button>
                </div>
              </td>
              <td>
                <input v-model="row.teamId" class="admin-team-mapping__input" type="text" autocomplete="off" />
              </td>
              <td>
                <input v-model="row.label" class="admin-team-mapping__input" type="text" autocomplete="off" />
              </td>
              <td>
                <input
                  v-model="row.modulesStr"
                  class="admin-team-mapping__input admin-team-mapping__input--wide"
                  type="text"
                  placeholder="예: atm, common, domain"
                  autocomplete="off"
                />
              </td>
              <td>
                <select v-model="row.matchMode" class="select admin-team-mapping__select" aria-label="match">
                  <option value="first">first (첫 경로 토큰)</option>
                  <option value="any">any (경로 중 아무 토큰)</option>
                </select>
              </td>
              <td class="admin-team-mapping__actions">
                <button type="button" class="btn btn--secondary btn--head" @click="removeRow(i)">삭제</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section class="card card--filters admin-team-mapping__fallback" aria-label="fallback">
      <div class="card__head">
        <h2 class="card__title">fallback</h2>
      </div>
      <div class="admin-team-mapping__fallback-grid">
        <label class="field">
          <span>teamId</span>
          <input v-model="fallbackTeamId" type="text" autocomplete="off" />
        </label>
        <label class="field">
          <span>라벨</span>
          <input v-model="fallbackLabel" type="text" autocomplete="off" />
        </label>
      </div>
    </section>
  </div>
</template>

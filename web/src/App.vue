<script setup>
import { onMounted, onUnmounted } from "vue";
import { hydrateComponentProjectsFromApi } from "./config/componentProjects.js";
import { scheduleTeamMappingHydrate } from "./lib/teamIdForIssue.js";
import { TEAM_MAPPING_UPDATED_EVENT } from "./lib/teamMappingEvents.js";

/** 자식 라우트(이슈 목록) mounted·watch 보다 먼저 실행되도록 setup 최상단에서 시작 */
scheduleTeamMappingHydrate();
void hydrateComponentProjectsFromApi();

function onTeamMappingUpdated() {
  scheduleTeamMappingHydrate();
}

onMounted(() => {
  void hydrateComponentProjectsFromApi();
  window.addEventListener(TEAM_MAPPING_UPDATED_EVENT, onTeamMappingUpdated);
});

onUnmounted(() => {
  window.removeEventListener(TEAM_MAPPING_UPDATED_EVENT, onTeamMappingUpdated);
});
</script>

<template>
  <div class="app">
    <div class="app__bg" aria-hidden="true" />
    <router-view />
  </div>
</template>

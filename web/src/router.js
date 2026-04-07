import { createRouter, createWebHistory } from "vue-router";
import DashboardView from "./views/DashboardView.vue";
import IssueListView from "./views/IssueListView.vue";
import TeamMappingAdminView from "./views/TeamMappingAdminView.vue";

export const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: "/", name: "dashboard", component: DashboardView },
    {
      path: "/admin/team-mapping",
      name: "adminTeamMapping",
      component: TeamMappingAdminView,
    },
    {
      path: "/issues/:projectId",
      name: "issues",
      component: IssueListView,
    },
  ],
});

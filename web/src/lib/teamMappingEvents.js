/** 대시보드 등이 팀 매핑 저장 후 즉시 재집계하도록 브로드캐스트 */
export const TEAM_MAPPING_UPDATED_EVENT = "sonarqube-monitor:team-mapping-updated";

export function notifyTeamMappingUpdated() {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent(TEAM_MAPPING_UPDATED_EVENT));
  }
}

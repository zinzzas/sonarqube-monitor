import dash from "../../../config/dashboard.json";

export const DASHBOARD_HERO = dash.hero ?? {};

/** 브라우저 탭 제목 (`config/dashboard.json` 의 `documentTitle`) */
export const DOCUMENT_TITLE =
  typeof dash.documentTitle === "string" && dash.documentTitle.trim()
    ? dash.documentTitle.trim()
    : "SonarQube Monitor";

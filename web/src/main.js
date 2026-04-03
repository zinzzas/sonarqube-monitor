import { createApp } from "vue";
import App from "./App.vue";
import { DOCUMENT_TITLE } from "./config/dashboardConfig.js";
import { router } from "./router.js";
import "./assets/app.css";

document.title = DOCUMENT_TITLE;

const faviconHref = `${import.meta.env.BASE_URL}load-more-chevron.png`;
let favicon = document.querySelector('link[rel="icon"]');
if (!favicon) {
  favicon = document.createElement("link");
  favicon.rel = "icon";
  favicon.type = "image/png";
  document.head.appendChild(favicon);
}
favicon.href = faviconHref;

createApp(App).use(router).mount("#app");

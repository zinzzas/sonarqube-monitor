from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api import api_router
from app.services.app_http_log import InternalApiLogMiddleware, configure_http_logging
from app.services.sonarqube_client import sonar_client

configure_http_logging()


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    yield
    await sonar_client.aclose()


app = FastAPI(title="SonarQube Monitor", version="0.1.0", lifespan=_lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(InternalApiLogMiddleware)

# 1) `/api/*` 전용 앱 — 아래 SPA 라우트와 겹치지 않음 (PUT 등 405 방지).
api_app = FastAPI()


@api_app.get("/health")
def api_health() -> dict[str, str]:
    return {"status": "ok"}


api_app.include_router(api_router)
app.mount("/api", api_app)

# 2) SPA: Starlette `StaticFiles(html=True)` 는 깊은 경로(`/admin/...`)에서 루트 `index.html`로
# 폴백하지 않고 404만 낸다. 따라서 정적 자산은 `/assets`만 마운트하고, 나머지 GET 은
# `dist` 내 실제 파일이 있으면 그대로, 없으면 `index.html`(클라이언트 라우터)로 보낸다.
_root = Path(__file__).resolve().parent
_dist = _root / "web" / "dist"
if _dist.is_dir():
    _assets = _dist / "assets"
    if _assets.is_dir():
        app.mount("/assets", StaticFiles(directory=str(_assets)), name="spa_assets")

    @app.get("/")
    async def spa_index() -> FileResponse:
        return FileResponse(_dist / "index.html")

    @app.get("/{full_path:path}")
    async def spa_client(full_path: str) -> FileResponse:
        if full_path.startswith("api"):
            raise HTTPException(status_code=404, detail="Not Found")
        candidate = (_dist / full_path).resolve()
        dist_root = _dist.resolve()
        if not candidate.is_relative_to(dist_root):
            raise HTTPException(status_code=404, detail="Not Found")
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_dist / "index.html")


def run_dev() -> None:
    """로컬 개발: 코드·`.env` 변경 시 프로세스 자동 재기동 (uvicorn --reload)."""
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=9999,
        reload=True,
        reload_dirs=[str(_root)],
        reload_includes=["*.py", "*.env"],
    )


if __name__ == "__main__":
    run_dev()

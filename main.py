from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api import api_router

app = FastAPI(title="SonarQube Monitor", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


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
        # `/api/*` 는 위의 API 라우터가 처리해야 함. 여기까지 오면 미등록 경로.
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

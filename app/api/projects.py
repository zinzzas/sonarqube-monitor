from fastapi import APIRouter

from app.config.load_projects import load_component_projects

router = APIRouter(tags=["projects"])


@router.get("/projects")
def list_projects() -> dict:
    """대시보드·프론트 공통 — `config/component_projects.json`."""
    return {"projects": load_component_projects()}

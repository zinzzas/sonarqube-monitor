from fastapi import APIRouter

from app.api.admin_team_mapping import router as admin_team_mapping_router
from app.api.issues import router as issues_router
from app.api.metrics import router as metrics_router
from app.api.projects import router as projects_router
from app.api.sonar import router as sonar_router
from app.api.team_mapping_public import router as team_mapping_public_router

api_router = APIRouter()
api_router.include_router(team_mapping_public_router)
api_router.include_router(admin_team_mapping_router)
api_router.include_router(issues_router)
api_router.include_router(metrics_router)
api_router.include_router(projects_router)
api_router.include_router(sonar_router)

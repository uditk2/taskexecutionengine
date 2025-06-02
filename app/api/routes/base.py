from fastapi import APIRouter, Request, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

from app.core.config import settings

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent.parent.parent / "templates")

@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
    # Redirect to the active tasks dashboard
    return RedirectResponse(url="/dashboard/active-tasks", status_code=status.HTTP_302_FOUND)

@router.get("/health", tags=["health"])
async def health_check():
    return {"status": "ok"}

from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
import json
from app.core.config import settings

def escapejs_filter(value):
    """Custom Jinja2 filter to escape JavaScript strings"""
    if value is None:
        return ""
    return json.dumps(str(value))[1:-1]  # Remove the surrounding quotes

router = APIRouter(tags=["example"])
templates = Jinja2Templates(directory=Path(__file__).parent.parent.parent / "templates")
templates.env.filters['escapejs'] = escapejs_filter

@router.get("/", response_class=HTMLResponse)
async def example_page(request: Request):
    return templates.TemplateResponse(
        "pages/example.html", 
        {
            "request": request, 
            "layout": "dashboard",
            "navbar": "side_fixed",
            "title": "Example Page",
            "settings": settings
        }
    )

@router.get("/data")
async def example_data():
    return {"message": "This is example data from the API"}
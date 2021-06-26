from fastapi import APIRouter, Request

from app.settings import templates

router = APIRouter()


@router.get("/")
async def admin_panel(request: Request):
    context = {}
    response = templates.TemplateResponse(
        "admin.html",
        {
            "request": request,
            **context
        }
    )
    return response

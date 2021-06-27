from fastapi import APIRouter, Request

from app.settings import templates

router = APIRouter()


@router.get("/")
async def admin_panel(request: Request):
    context = {
        'github': 'https://github.com/Sirius-social/didcomm',
        'issues': 'https://github.com/Sirius-social/didcomm/issues',
        'spec': 'https://identity.foundation/didcomm-messaging/spec/'
    }
    response = templates.TemplateResponse(
        "admin.html",
        {
            "request": request,
            **context
        }
    )
    return response

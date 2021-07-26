import datetime

from fastapi import APIRouter, Request


router = APIRouter(
    prefix="/maintenance",
    tags=["maintenance"],
    responses={404: {"description": "Not found"}},
)


@router.get("/health_check")
async def health_check(request: Request):
    return {'ok': True, 'utc': str(datetime.datetime.utcnow()), 'headers': str(request.headers)}


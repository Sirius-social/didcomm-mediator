import datetime

from fastapi import APIRouter, Request, Depends

from databases import Database
from app.dependencies import get_db


router = APIRouter(
    prefix="/maintenance",
    tags=["maintenance"],
    responses={404: {"description": "Not found"}},
)


@router.get("/health_check")
async def health_check(request: Request, db: Database = Depends(get_db)):
    return {'ok': True, 'utc': str(datetime.datetime.utcnow()), 'headers': str(request.headers)}


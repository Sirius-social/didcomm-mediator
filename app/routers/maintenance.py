import datetime

from fastapi import APIRouter, Request, Depends

from databases import Database
from app.dependencies import get_db
from app.core.management import liveness_check as mng_liveness_check


router = APIRouter(
    prefix="/maintenance",
    tags=["maintenance"],
    responses={404: {"description": "Not found"}},
)


@router.get("/health_check")
async def health_check(request: Request, db: Database = Depends(get_db)):
    return {'ok': True, 'utc': str(datetime.datetime.utcnow()), 'headers': str(request.headers)}


@router.get("/liveness_check")
async def liveness_check(request: Request):
    await mng_liveness_check()
    return {'ok': True, 'utc': str(datetime.datetime.utcnow())}

import datetime
import logging

from fastapi import APIRouter, Request, Depends, HTTPException

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
    try:
        await mng_liveness_check()
    except RuntimeError as e:
        logging.exception('Liveness')
        raise HTTPException(status_code=500, detail=f'Leveness check error: {str(e)}')
    else:
        return {'ok': True, 'utc': str(datetime.datetime.utcnow())}

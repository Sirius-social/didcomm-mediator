import os
import logging
import argparse

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.init import *
from app.routers import maintenance, mediator
from app.internal import admin
from app.db.database import database
from app.settings import URL_STATIC


app = FastAPI()
app.mount(URL_STATIC, StaticFiles(directory="static"), name="static")

app.include_router(maintenance.router)
app.include_router(mediator.router)
app.include_router(
    admin.router,
    prefix="/admin",
    tags=["admin"],
    responses={404: {"description": "Not found"}},
)


@app.on_event("startup")
async def startup_event():
    logging.debug('***** StartUp *****')
    await database.connect()


@app.on_event("shutdown")
async def shutdown():
    logging.debug('***** ShutDown *****')
    await database.disconnect()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--production', choices=['on', 'yes'], required=False)
    args = parser.parse_args()
    is_production = args.production is not None
    args = ()
    kwargs = {}
    if is_production:
        logging.warning('\n')
        logging.warning('\t*************************************')
        logging.warning('\tApplication will be run in PRODUCTION mode')
        logging.warning('\t*************************************')
        args = ['app.main:app']
        kwargs['proxy_headers'] = True
    else:
        logging.warning('\n')
        logging.warning('\t*************************************')
        logging.warning('\tApplication will be run in DEBUG mode')
        logging.warning('\t*************************************')
        kwargs.update({'debug': True, 'reload': True})
        args = ['app.main:app']
    uvicorn.run(
        *args, host="0.0.0.0", port=int(os.getenv('PORT')), workers=int(os.getenv('WORKERS')), **kwargs
    )

import os

import uvicorn
from fastapi import FastAPI, Depends
from fastapi.staticfiles import StaticFiles
from databases import Database

from app.routers import maintenance, mediator
from app.internal import admin
from app.db.database import database
from app.dependencies import get_db


app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")


app.include_router(maintenance.router)
app.include_router(mediator.router)
app.include_router(
    admin.router,
    prefix="/admin",
    tags=["admin"],
    responses={404: {"description": "Not found"}},
)


@app.on_event("shutdown")
async def shutdown():
    await database.disconnect()


if __name__ == '__main__':
    uvicorn.run('app.main:app', host="0.0.0.0", port=int(os.getenv('PORT')), debug=True, reload=True)

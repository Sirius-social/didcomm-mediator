import os

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.routers import maintenance, relay
from app.internal import admin


app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")


app.include_router(maintenance.router)
app.include_router(relay.router)
app.include_router(
    admin.router,
    prefix="/admin",
    tags=["admin"],
    responses={404: {"description": "Not found"}},
)


if __name__ == '__main__':
    uvicorn.run('app.main:app', host="0.0.0.0", port=int(os.getenv('PORT')), debug=True, reload=True)

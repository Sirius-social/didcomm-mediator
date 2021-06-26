import os

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.routers import maintenance
from app.internal import admin


app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def index():
    return {"Hello": "World"}


app.include_router(maintenance.router)
app.include_router(
    admin.router,
    prefix="/admin",
    tags=["admin"],
    responses={404: {"description": "Not found"}},
)


if __name__ == '__main__':
    uvicorn.run('app.main:app', host="0.0.0.0", port=int(os.getenv('PORT')), debug=True, reload=True)

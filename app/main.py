import os
import json
import datetime

import uvicorn
import settings
import sirius_sdk
from fastapi import FastAPI, exceptions, Request, Response, WebSocket


app = FastAPI()


@app.get("/")
async def index():
    return {"Hello": "World"}


@app.get("/check_health")
async def health_check():
    return {'ok': True, 'stamp': str(datetime.datetime.now())}


if __name__ == '__main__':
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv('PORT')), debug=True)

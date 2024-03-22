from fastapi.responses import JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, Request
from prisma import Prisma
import uvicorn
import aiohttp
import base64
import json
import time

app = FastAPI()
db = Prisma()
ttl = 60 * 60 * 3  # 3 hrs

origins = [
    "https://pplbandage.ru",
    "https://skinserver.pplbandage.ru",
    "http://localhost:3000"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    await db.connect()  # Connecting to database
    print("Connected to Data Base")


@app.get("/")
async def root():
    return JSONResponse(content={"status": "error", "message": "invalid url, go to /skin/"}, status_code=400)


@app.get("/skin/{nickname}")
async def skin(nickname: str, request: Request):
    cache = await db.file.find_first(where={"nickname": nickname.lower()})  # Find cache record in db
    if cache and cache.expires > time.time():
        # If cache record is valid send cached skin
        return Response(base64.b64decode(cache.data), media_type="image/png")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get('https://api.mojang.com/users/profiles/minecraft/' + nickname) as response:
                if response.status == 404:
                    return JSONResponse(content={"status": "error", "message": "skin not found"}, status_code=404)
                elif response.status != 200:
                    return JSONResponse(content={"status": "error", "message": "unhandled error"}, status_code=500)
                
                response_json = await response.json()
            async with session.get('https://sessionserver.mojang.com/session/minecraft/profile/' + response_json['id']) as response_skin:
                response_json_skin = await response_skin.json()
                skin_url = json.loads(base64.b64decode(response_json_skin['properties'][0]['value']))['textures']['SKIN']['url']  # Get skin url

            async with session.get(skin_url) as response_skin_img:
                bytes = await response_skin_img.content.read()  # Get skin bytes
                base64_bytes = base64.b64encode(bytes).decode("utf-8")  # Convert bytes to base64
                if cache:
                    # If cache recod in db already exists, update data
                    await db.file.update(where={"id": cache.id}, data={"expires": int(time.time() + ttl), 
                                                                        "data": base64_bytes})
                else:
                    # Create record if not
                    await db.file.create(data={"nickname": nickname.lower(), 
                                                "expires": int(time.time() + ttl), 
                                                "data": base64_bytes})
                return Response(bytes, media_type="image/png")
    except Exception as e:
        print(e)
        return JSONResponse(content={"status": "error", "message": "unhandled error"}, status_code=500)


if __name__ == "__main__":
    uvicorn.run("main:app", port=8088)
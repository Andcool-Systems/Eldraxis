"""
Eldraxis project

AndcoolSystems, 2024
"""

import PIL.Image
from fastapi.responses import JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, Request
from fastapi import FastAPI, Header
from minepi import Skin
from typing import List
import uvicorn
import aiohttp
import base64
import prisma
import json
import time
import io
import re
from typing import Annotated
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

db = prisma.Prisma()


async def lifespan(app: FastAPI):
    await db.connect()  # Connecting to database
    print("Connected to Data Base")
    yield
    await db.disconnect()  # Disconnecting from database


limiter = Limiter(key_func=get_remote_address)
app = FastAPI(lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
ttl = 60 * 60 * 3  # 3 hours


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def generateHead(skin: PIL.Image.Image) -> PIL.Image.Image:
    head = PIL.Image.new("RGBA", (36, 36), (0, 0, 0, 0))
    first_layer = skin.crop((8, 8, 16, 16)).resize(size=(32, 32), resample=PIL.Image.Resampling.NEAREST)
    second_layer = skin.crop((40, 8, 48, 16)).resize(size=(36, 36), resample=PIL.Image.Resampling.NEAREST)
    head.paste(first_layer, (2, 2), first_layer)
    head.paste(second_layer, (0, 0), second_layer)
    return head


def uuidToDashed(uuid):
    uuid_list = list(uuid)

    uuid_list.insert(8, "-")
    uuid_list.insert(13, "-")
    uuid_list.insert(18, "-")
    uuid_list.insert(23, "-")
    
    return "".join(uuid_list)


async def getUserData(string: str):
    pattern = re.compile(r'^[0-9a-fA-F]{32}$')
    uuid = string.replace("-", "")
    async with aiohttp.ClientSession() as session:
        if not bool(pattern.match(string)):
            async with session.get('https://api.mojang.com/users/profiles/minecraft/' + string) as response:
                if response.status != 200:
                    return None
                uuid = (await response.json())['id']
            
        async with session.get('https://sessionserver.mojang.com/session/minecraft/profile/' + uuid) as response_skin:
            if response_skin.status != 200:
                return None
            return await response_skin.json()
        

async def resolveCollisions(records: List[prisma.models.File]):
    for record in records:
        data = await getUserData(record.uuid)
        if not data:
            await db.file.delete(where={"uuid": data["id"]})
            continue
        await db.file.update(where={"uuid": data["id"]},
                             data={"default_nick": data["name"],
                                   "nickname": data["name"].lower()})


async def updateSkinCache(nickname: str, cape: bool = False, ignore_cache: bool = False) -> JSONResponse:
    fetched_skin_data = await getUserData(nickname)  # Get account data
    if not fetched_skin_data:
        return JSONResponse(content={"status": "error", "message": "Profile not found"}, status_code=404)
    
    nicks = await db.file.find_many(where={"default_nick": fetched_skin_data["name"]})
    if len(nicks) > 1:
        await resolveCollisions(nicks)
    
    cache = await db.file.find_first(where={"uuid": fetched_skin_data["id"]})  # Find cache record in db
    if cache and cache.expires > time.time() and not ignore_cache:
        if cache.default_nick != fetched_skin_data["name"]:
            await db.file.update(where={"uuid": fetched_skin_data["id"]}, data={"default_nick": fetched_skin_data["name"],
                                                               "nickname": fetched_skin_data["name"].lower()})
        if not cape:
            return Response(base64.b64decode(cache.data), media_type="image/png")
        return JSONResponse(content={"status": "success", "data": {"skin": cache.data, "cape": cache.data_cape}})

    try:
        async with aiohttp.ClientSession() as session:
            urls = json.loads(base64.b64decode(fetched_skin_data['properties'][0]['value']))['textures']

            async with session.get(urls['SKIN']['url']) as response_skin_img:
                bytes = await response_skin_img.content.read()  # Get skin bytes
                base64_bytes = base64.b64encode(bytes).decode("utf-8")  # Convert bytes to base64
                
                skin_img = PIL.Image.open(io.BytesIO(bytes))
                head = generateHead(skin_img)  # Generate avatar
                buffered = io.BytesIO()
                head.save(buffered, format="PNG")
                base64_head = base64.b64encode(buffered.getvalue()).decode("utf-8")

            cape_base64 = ""
            if "CAPE" in urls:
                async with session.get(urls['CAPE']['url']) as response_skin_img:
                    cape_bytes = await response_skin_img.content.read()  # Get skin bytes
                    cape_base64 = base64.b64encode(cape_bytes).decode("utf-8")  # Convert bytes to base64

            await db.file.upsert(where={"uuid": fetched_skin_data["id"]}, 
                                 data={'create': {
                                            "uuid": fetched_skin_data["id"],
                                            "nickname": fetched_skin_data["name"].lower(),
                                            "default_nick": fetched_skin_data["name"],
                                            "expires": int(time.time() + ttl), 
                                            "data": base64_bytes,
                                            "data_cape": cape_base64,
                                            "data_head": base64_head
                                        },
                                        'update': {
                                            "nickname": fetched_skin_data["name"].lower(),
                                            "default_nick": fetched_skin_data["name"],
                                            "expires": int(time.time() + ttl), 
                                            "data": base64_bytes,
                                            "data_cape": cape_base64,
                                            "data_head": base64_head
                                        }})
            if not cape:
                return Response(bytes, media_type="image/png")
            return JSONResponse(content={"status": "success", "data": {"skin": base64_bytes, "cape": cape_base64}})
    except Exception as e:
        print(e)
        return JSONResponse(content={"status": "error", "message": "unhandled error"}, status_code=500)


@app.get("/")
async def root():
    return JSONResponse(content={"status": "success", "message": "Welcome to eldraxis!"})


@app.get("/skin/{nickname}")
@limiter.limit("100/minute")
async def skin(request: Request, nickname: str, cape: bool = False, Cache_Control: Annotated[str | None, Header()] = None):
    response = await updateSkinCache(nickname=nickname, cape=cape, ignore_cache=Cache_Control == "no-cache")
    if Cache_Control == "no-cache":
        response.raw_headers.append(("Cache-control", "no-cache"))
    return response


@app.get("/head3d/{nickname}")
@limiter.limit("100/minute")
async def head3d(request: Request, nickname: str, v: int = -25, h: int = 45):
    response = await updateSkinCache(nickname=nickname)
    if response.status_code != 200:
        return response
    
    cache = await db.file.find_first(where={"nickname": nickname.lower()})
    skin_img = PIL.Image.open(io.BytesIO(base64.b64decode(cache.data)))
    skin = Skin(skin_img)
    await skin.render_head(vr=v, hr=h, ratio=32)
    buffered = io.BytesIO()
    skin.head.save(buffered, format="PNG")
    return Response(buffered.getvalue(), media_type="image/png")


@app.get("/head/{nickname}")
@limiter.limit("100/minute")
async def head(request: Request, nickname: str):
    response = await updateSkinCache(nickname=nickname)
    if response.status_code != 200:
        return response
    
    cache = await db.file.find_first(where={"nickname": nickname.lower()})
    return Response(base64.b64decode(cache.data_head), media_type="image/png")


@app.get("/cape/{nickname}")
@limiter.limit("100/minute")
async def cape(request: Request, nickname: str):
    response = await updateSkinCache(nickname=nickname)
    if response.status_code != 200:
        return response
    
    cache = await db.file.find_first(where={"nickname": nickname.lower()})
    return Response(base64.b64decode(cache.data_cape), media_type="image/png")


@app.get("/profile/{nickname}")
@limiter.limit("100/minute")
async def profile(request: Request, nickname: str):
    response = await getUserData(string=nickname)
    if not response:
        return JSONResponse({"status": "error", "message": "Not found"}, status_code=404)
    
    data = json.loads(base64.b64decode(response['properties'][0]['value']))
    search = await db.file.find_first(where={"uuid": data["profileId"], "valid": True})
    return JSONResponse({"status": "success",
                         "message": "",
                         "timestamp": data["timestamp"],
                         "uuid": data["profileId"],
                         "uuid_dashed": uuidToDashed(data["profileId"]),
                         "nickname": data["profileName"],
                         "textures": {
                             "SKIN": {
                                 "mojang": data["textures"]["SKIN"]["url"],
                                 "eldraxis": "https://eldraxis.andcool.ru/skin/" + data["profileId"]
                             },
                             "CAPE": {
                                 "mojang": data["textures"]["CAPE"]["url"],
                                 "eldraxis": "https://eldraxis.andcool.ru/cape/" + data["profileId"]
                             } if "CAPE" in data["textures"] else None
                         },
                         "eldraxis_cache":{
                            "available_in_search": bool(search),
                            "last_cached": (search.expires - ttl) * 1000 if search else None
                         }})


@app.get("/search/{nickname}")
@limiter.limit("100/minute")
async def search(request: Request, nickname: str, take: int = 20, page: int = 0):
    if len(nickname) < 3:
        return Response(status_code=204)

    cache = await db.file.find_many(where={"nickname": {"contains": nickname}, "valid": True}, order={"default_nick": "asc"}, take=take, skip=take * page)  # Find cache records in db
    count = await db.file.count(where={"nickname": {"contains": nickname}, "valid": True})
    if not cache:
        return Response(status_code=204)

    return JSONResponse(content={
        "status": "success", 
        "requestedFragment": nickname, 
        "data": [{"name": nick.default_nick, "uuid": nick.uuid, "head": nick.data_head} for nick in cache],
        "total_count": count,
        "next_page": page + 1
        }, status_code=200)


if __name__ == "__main__":
    uvicorn.run("main:app", port=8088, host="0.0.0.0")
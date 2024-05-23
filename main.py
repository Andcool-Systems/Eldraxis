import PIL.Image
from fastapi.responses import JSONResponse, Response, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI
from minepi import Skin
from prisma import Prisma
import uvicorn
import aiohttp
import base64
import io
import json
import time

db = Prisma()


async def lifespan(app: FastAPI):
    await db.connect()  # Connecting to database
    print("Connected to Data Base")
    yield
    await db.disconnect()  # Disconnecting from database


app = FastAPI(lifespan=lifespan)
ttl = 60 * 60 * 3  # 3 hours


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def updateSkinCache(nickname: str, cape: bool = False) -> JSONResponse:
    cache = await db.file.find_first(where={"nickname": nickname.lower()})  # Find cache record in db
    if cache and cache.expires > time.time():
        # If cache record is valid send cached skin
        if not cape:
            return Response(base64.b64decode(cache.data), media_type="image/png")
        return JSONResponse(content={"status": "success", "data": {"skin": cache.data, "cape": cache.data_cape}})

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get('https://api.mojang.com/users/profiles/minecraft/' + nickname) as response:
                if response.status == 404:
                    if cache:
                        await db.file.delete(where={"id": cache.id})        
                    return JSONResponse(content={"status": "error", "message": "skin not found"}, status_code=404)
                elif response.status != 200:
                    return JSONResponse(content={"status": "error", "message": "unhandled error"}, status_code=response.status)
                
                response_json = await response.json()
            async with session.get('https://sessionserver.mojang.com/session/minecraft/profile/' + response_json['id']) as response_skin:
                response_json_skin = await response_skin.json()
                urls = json.loads(base64.b64decode(response_json_skin['properties'][0]['value']))['textures']

            async with session.get(urls['SKIN']['url']) as response_skin_img:
                bytes = await response_skin_img.content.read()  # Get skin bytes
                base64_bytes = base64.b64encode(bytes).decode("utf-8")  # Convert bytes to base64
                skin_img = PIL.Image.open(io.BytesIO(bytes))
                head = PIL.Image.new("RGBA", (36, 36), (0, 0, 0, 0))
                first_layer = skin_img.crop((8, 8, 16, 16)).resize(size=(32, 32), resample=PIL.Image.Resampling.NEAREST)
                second_layer = skin_img.crop((40, 8, 48, 16)).resize(size=(36, 36), resample=PIL.Image.Resampling.NEAREST)
                head.paste(first_layer, (2, 2), first_layer)
                head.paste(second_layer, (0, 0), second_layer)
                buffered = io.BytesIO()
                head.save(buffered, format="PNG")
                base64_head = base64.b64encode(buffered.getvalue()).decode("utf-8")
                skin_img.close()
                head.close()
                first_layer.close()
                second_layer.close()


            cape_base64 = ""
            if "CAPE" in urls:
                async with session.get(urls['CAPE']['url']) as response_skin_img:
                    cape_bytes = await response_skin_img.content.read()  # Get skin bytes
                    cape_base64 = base64.b64encode(cape_bytes).decode("utf-8")  # Convert bytes to base64

            
            await db.file.upsert(where={"id": cache.id if cache else 0}, data={
                                                                'create': {
                                                                    "nickname": nickname.lower(),
                                                                    "default_nick": response_json["name"],
                                                                    "expires": int(time.time() + ttl),
                                                                    "data": base64_bytes,
                                                                    "data_cape": cape_base64,
                                                                    "data_head": base64_head
                                                                },
                                                                'update': {
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
    return RedirectResponse("https://pplbandage.ru")


@app.get("/skin/{nickname}")
async def skin(nickname: str, cape: bool = False):
    return await updateSkinCache(nickname=nickname, cape=cape)


@app.get("/head3d/{nickname}")
async def head3d(nickname: str, v: int = -25, h: int = 45):
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
async def head(nickname: str):
    response = await updateSkinCache(nickname=nickname)
    if response.status_code != 200:
        return response
    
    cache = await db.file.find_first(where={"nickname": nickname.lower()})
    return Response(base64.b64decode(cache.data_head), media_type="image/png")


@app.get("/cape/{nickname}")
async def cape(nickname: str):
    response = await updateSkinCache(nickname=nickname)
    if response.status_code != 200:
        return response
    
    cache = await db.file.find_first(where={"nickname": nickname.lower()})
    return Response(base64.b64decode(cache.data_cape), media_type="image/png")


@app.get("/search/{nickname}")
async def search(nickname: str, take: int = 20, page: int = 0):
    if len(nickname) < 3:
        return Response(status_code=204)

    cache = await db.file.find_many(where={"nickname": {"contains": nickname}, "valid": True}, order={"default_nick": "asc"}, take=take, skip=take * page)  # Find cache records in db
    count = await db.file.count(where={"nickname": {"contains": nickname}, "valid": True})
    if not cache:
        return Response(status_code=204)

    return JSONResponse(content={
        "status": "success", 
        "requestedFragment": nickname, 
        "data": [{"name": nick.default_nick, "head": nick.data_head} for nick in cache],
        "total_count": count,
        "next_page": page + 1
        }, status_code=200)


if __name__ == "__main__":
    uvicorn.run("main:app", port=8088, host="0.0.0.0")
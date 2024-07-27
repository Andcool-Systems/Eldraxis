# Eldraxis project
[![Made for pepeland](https://andcool.ru/static/badges/made-for-ppl.svg)](https://pepeland.net)  
This API acts as an intermediary between the client and the official Mojang skins server. For greater convenience, the API caches incoming requests for 3 hours. Unlike the official Mojang skins server, this API requires only one request to obtain a skin image by nickname.    

The rate limit for all endpoints is 100 requests per minute.

## Usage
### `GET /profile/{nickname/uuid}`  
Get account info by nickname/UUID.  

Here's an example response:  
```json
{
  "status": "success",
  "message": "",
  "timestamp": 1716588437430,
  "uuid": "1420c63cb1114453993fb3479ba1d4c6",
  "uuid_dashed": "1420c63c-b111-4453-993f-b3479ba1d4c6",
  "nickname": "AndcoolSystems",
  "textures": {
    "SKIN": {
      "mojang": "http://textures.minecraft.net/texture/9c52c2cf06d363321a0ec5530960755c3dea860b3e67e5c9ca9eb33a136e46e0",
      "eldraxis": "https://eldraxis.andcool.ru/skin/1420c63cb1114453993fb3479ba1d4c6"
    },
    "CAPE": {
      "mojang": "http://textures.minecraft.net/texture/afd553b39358a24edfe3b8a9a939fa5fa4faa4d9a9c3d6af8eafb377fa05c2bb",
      "eldraxis": "https://eldraxis.andcool.ru/cape/1420c63cb1114453993fb3479ba1d4c6"
    }
  },
  "eldraxis_cache": {
    "available_in_search": true,
    "last_cached": 1716586283000
  }
}
```



### `GET /skin/{nickname}?cape=<bool>`  
Retrieve a skin by nickname.
> ### Query parameter `cape` determines the format of the returned skin.
> The default value of the parameter is `false`. With this value, the response `Content-Type` header will be `image/png`. In this case, the endpoint will return only the skin as an image.  
> If the parameter `cape` is set to `true`, the endpoint will have a `text/json` `Content-Type` header, and the response will contain images of the skin and cape in `base64` format.
```json
{
  "status": "success",
  "data": {
    "skin": "<base64 encoded skin>",
    "cape": "<base64 encoded cape>"
  }
}
```
> [!NOTE]
> If your account does not have a cape, the `cape` field in the server response will be an empty string.


## Get 2D head by nickname
### `GET /head/{nickname}`  
Returns image of minecraft skin head by nickname.  
`Content-Type: image/png`  
> [!NOTE]
> The request is subject to caching


## Get 3D head by nickname
### `GET /head3d/{nickname}?v=-25&h=45`  
Returns image of 3D render of minecraft skin head by nickname.  
`Content-Type: image/png`  
> The parameters `v` and `h` are responsible for the vertical and horizontal rotation of the render, respectively. The standard values are shown in the sample query (-25, 45).  

> [!NOTE]
> The request is subject to caching

## Get cape by nickname
### `GET /cape/{nickname}`  
Returns image of minecraft account cape by nickname.  
`Content-Type: image/png`  
> [!NOTE]
> The request is subject to caching

## Search by nickname
### `GET /search/{nickname-fragment}?take=<take>&page=<page>`  
This endpoint will return all cached entries whose nickname contains the given fragment.

> The `take` parameter specifies the maximum number of nicknames returned in the search (default is 20).  
> The `page` parameter determines which page will be sent when requesting nicknames. Calculated by the formula `skip = take * page`.

If no nicknames containing the given fragment are found, the HTTP status code will be `204`.

#### Example Response
```json
{
  "status": "success",
  "requestedFragment": "AndcoolSystems",
  "data": [
    {
      "name": "AndcoolSystems",
      "head": "<base64 encoded skin head>"
    }
  ],
  "total_count": 1,
  "next_page": 1
}
```
>The `total_count` field contains the total number of records found, regardless of the `take` and `page` parameters.  
>The `next_page` field contains the number of the next page.

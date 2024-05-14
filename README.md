# Simple Minecraft Skin API
This API is for [pplbandage.ru](https://pplbandage.ru).

This API acts as an intermediary between the client and the official Mojang skins server. For greater convenience, the API caches incoming requests for 3 hours. Unlike the official Mojang skins server, this API requires only one request to obtain a skin image by nickname.

## Usage
`GET /skin/{nickname}?cape=<bool>`  
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

## Search by Nickname
`GET /search/{nickname-fragment}?take=<take>&page=<page>`  
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
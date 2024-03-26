# Simple Minecraft skin API
This API for [pplbandage.ru](https://pplbandage.ru).  

This API is an intermediary between the client and the official Mojang skins server. For greater convenience, the API caches incoming requests for 3 hours. Unlike the official Mojang skins server, this API requires only one request to obtain an image of a skin by nickname.

## Usage
`GET /skin/{nickname}`  
Response Content-Type: `image/png`  
This endpoint URL returns a Minecraft skin by nickname.

`GET /search/{nickname fragment}`  
Find all nicknames containing the provided nickname fragment.
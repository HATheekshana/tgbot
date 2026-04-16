import aiohttp
from PIL import Image
from io import BytesIO

session = None
IMAGE_CACHE = {}

async def get_session():
    global session
    if session is None or session.closed:
        session = aiohttp.ClientSession()
    return session

async def fetch_image(url):
    if url in IMAGE_CACHE:
        return IMAGE_CACHE[url]

    session = await get_session()

    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
            if resp.status == 200:
                img = Image.open(BytesIO(await resp.read())).convert("RGBA")
                IMAGE_CACHE[url] = img
                return img
    except:
        return None

    return None
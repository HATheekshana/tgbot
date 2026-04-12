import aiohttp
from database import users_col

async def fetch_enka_data(uid: str):
    url = f"https://enka.network/api/uid/{uid}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
            if response.status == 200:
                return await response.json()
            return None

async def get_user_uid(user_id: str):
    user_data = await users_col.find_one({"user_id": user_id})
    return user_data.get("genshin_uid") if user_data else None
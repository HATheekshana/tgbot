import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
import os

load_dotenv()

MONGO_URL = os.getenv("MONGO_URL")

async def gift_wishes():
    cluster = AsyncIOMotorClient(MONGO_URL)
    db = cluster["genshin_bot"]
    users_col = db["user_stats"]

    print("🎁 Preparing to send 1000 wishes to all users...")

    result = await users_col.update_many(
        {},
        {"$inc": {"wish_count": 1000}}
    )

    print(f"✅ Success! Updated {result.modified_count} users.")
    print("Everyone just got +1000 wishes.")

if __name__ == "__main__":
    asyncio.run(gift_wishes())


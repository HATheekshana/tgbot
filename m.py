import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = "mongodb+srv://zerorenx_db_user:theekshana@tgbot.yuowvp8.mongodb.net/?appName=Tgbot"

async def migrate():
    cluster = AsyncIOMotorClient(MONGO_URL)
    db = cluster["genshin_bot"]
    users_col = db["user_stats"]

    # Update users who DO NOT have the wish_count field
    result = await users_col.update_many(
        {"wish_count": {"$exists": False}}, 
        {"$set": {"wish_count": 200}}
    )

    print(f"✅ Migration complete! Updated {result.modified_count} old users.")

if __name__ == "__main__":
    asyncio.run(migrate())
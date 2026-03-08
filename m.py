import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = "mongodb+srv://zerorenx_db_user:theekshana@tgbot.yuowvp8.mongodb.net/?appName=Tgbot"

async def migrate():
    cluster = AsyncIOMotorClient(MONGO_URL)
    db = cluster["genshin_bot"]
    users_col = db["user_stats"]

    # {} = Filter (matches all users)
    # "$set" = The action to perform
    result = await users_col.update_many(
        {}, 
        {"$set": {"total_wishes": 0}}
    )

    print(f"✅ Reset Complete!")
    print(f"📊 Total Users Matched: {result.matched_count}")
    print(f"🔄 Total Wishes Reset to 0: {result.modified_count}")

if __name__ == "__main__":
    asyncio.run(migrate())
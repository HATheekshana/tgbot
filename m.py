import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = "mongodb+srv://zerorenx_db_user:theekshana@tgbot.yuowvp8.mongodb.net/?appName=Tgbot"

async def migrate_streaks():
    cluster = AsyncIOMotorClient(MONGO_URL)
    db = cluster["genshin_bot"]
    users_col = db["user_stats"]
    print("Starting migration...")
    
    # We use a pipeline to set the new field based on the old field
    await users_col.update_many(
        {"streak_new": {"$exists": False}}, # Only update users who don't have it yet
        [
            {"$set": {"streak_new": {"$ifNull": ["$daily_streak", 0]}}}
        ]
    )
    print("✅ Migration complete: All users now have streak_new!")

# You can call this inside your main() function once
if __name__ == "__main__":
    asyncio.run(migrate())
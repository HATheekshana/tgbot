import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

# Your MongoDB Connection String
MONGO_URL = "mongodb+srv://zerorenx_db_user:theekshana@tgbot.yuowvp8.mongodb.net/?appName=Tgbot"

async def gift_wishes():
    cluster = AsyncIOMotorClient(MONGO_URL)
    db = cluster["genshin_bot"]
    users_col = db["user_stats"]
    
    print("🎁 Preparing to send 1000 wishes to all users...")

    # $inc adds the value to the existing wish_count
    # If a user doesn't have a wish_count field, MongoDB will create it starting at 1000
    result = await users_col.update_many(
        {}, # Empty filter matches everyone
        {"$inc": {"wish_count": 1000}}
    )
    
    print(f"✅ Success! Updated {result.modified_count} users.")
    print("Everyone just got +1000 wishes.")

if __name__ == "__main__":
    asyncio.run(gift_wishes())
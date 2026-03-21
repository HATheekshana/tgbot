import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()

MONGO_URL = os.getenv("MONGO_URL")
cluster = AsyncIOMotorClient(MONGO_URL)
db = cluster["genshin_bot"]
users_col = db["user_stats"]
groups_col = db["groups"]
import os  # ADD THIS
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import motor
AsyncIOMotorClient = motor.motor_async_engine.AsyncIOMotorClient
import httpx
import logging
load_dotenv()
app = FastAPI()

# --- 1. ENABLE CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 2. DATABASE SETUP ---
MONGO_URL = os.getenv("MONGO_URL")
client = motor.motor_async_engine.AsyncIOMotorClient(MONGO_URL)
db = client["genshin_bot"]  # CHANGED FROM cluster TO client
users_col = db["user_stats"]

# --- 3. THE PROFILE ENDPOINT ---
@app.get("/api/profile/{tg_id}")
async def get_web_profile(tg_id: str):
    # Search for the user in your bot's database
    # We use str(tg_id) to ensure matching types
    user = await users_col.find_one({"user_id": str(tg_id)})
    
    if not user or "genshin_uid" not in user:
        raise HTTPException(status_code=404, detail="User not found. Please /login in the bot.")

    genshin_uid = user["genshin_uid"]

    # Fetch data from Enka.Network
    async with httpx.AsyncClient() as http_client:
        try:
            response = await http_client.get(
                f"https://enka.network/api/uid/{genshin_uid}",
                timeout=10.0
            )
            
            if response.status_code != 200:
                raise HTTPException(status_code=502, detail="Enka Network is down or UID is invalid.")
            
            data = response.json()
            
            # Return exactly what the Frontend needs
            return {
                "player": data.get("playerInfo", {}),
                "characters": data.get("avatarInfoList", []),
                "uid": genshin_uid
            }
            
        except Exception as e:
            logging.error(f"Error fetching Enka data: {e}")
            raise HTTPException(status_code=500, detail="Internal Server Error")

# --- 4. RUNNING THE SERVER ---
# Run this using: uvicorn main:app --host 0.0.0.0 --port 8000
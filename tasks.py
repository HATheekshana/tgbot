import json
from time import timezone
import genshin
from apscheduler.schedulers.asyncio import AsyncIOScheduler

async def check_resin_alerts(bot, users_col, cipher):
    # Get all users who have logged in
    cursor = users_col.find({"hoyolab_data": {"$exists": True}})
    
    async for user in cursor:
        try:
            # Decrypt Cookies
            decrypted_data = cipher.decrypt(user["hoyolab_data"].encode()).decode()
            cookies = json.loads(decrypted_data)
            
            # Setup Client
            client = genshin.Client(cookies)
            client.region = genshin.Region.OVERSEAS
            
            # Get Notes
            notes = await client.get_genshin_notes()
            
            # Check Threshold
            if notes.current_resin >= 155 and not user.get("resin_notified", False):
                await bot.send_message(
                    user["user_id"], 
                    f"🌙 <b>Resin Alert!</b>\nYour resin is at <b>{notes.current_resin}/{notes.max_resin}</b>.",
                    parse_mode="HTML"
                )
                await users_col.update_one({"_id": user["_id"]}, {"$set": {"resin_notified": True}})
            
            elif notes.current_resin < 150 and user.get("resin_notified", False):
                await users_col.update_one({"_id": user["_id"]}, {"$set": {"resin_notified": False}})

        except Exception as e:
            print(f"Error checking resin for {user.get('user_id')}: {e}")

def setup_scheduler(bot, users_col, cipher):
    # Use the same timezone as your bot
    lk_timezone = timezone("Asia/Colombo")
    scheduler = AsyncIOScheduler(timezone=lk_timezone)
    
    scheduler.add_job(
        check_resin_alerts, 
        "interval", 
        minutes=30, 
        args=[bot, users_col, cipher]
    )
    
    scheduler.start()
    print("✅ HoYoLAB Background Tasks Started")

import asyncio
import aiohttp
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from database import users_col  # Ensure your database.py defines users_col

# --- Configuration ---
TOKEN = "1729484654:AAGU6996ZdQqSlqfWaAOoGLHzyo0ycBcTH4"
bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- Helper Function: Fetch Data Directly from Enka ---
async def fetch_enka_data(uid: str):
    url = f"https://enka.network/api/uid/{uid}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                return await response.json()
            return None

# --- Command: /login <uid> ---
@dp.message(Command("login"))
async def login_uid(message: types.Message):
    args = message.text.split()
    if len(args) < 2:
        return await message.answer("❓ **Usage:** `/login <uid>`")

    uid = args[1]
    if not uid.isdigit():
        return await message.answer("❌ Please enter a numeric UID.")

    status_msg = await message.answer(f"🔍 Verifying UID {uid}...")

    data = await fetch_enka_data(uid)
    
    if not data or "playerInfo" not in data:
        return await status_msg.edit_text("❌ UID not found or Character Showcase is private.")

    player = data["playerInfo"]
    nickname = player.get("nickname", "Unknown")
    level = player.get("level", 0)

    # Save to MongoDB
    await users_col.update_one(
        {"user_id": str(message.from_user.id)},
        {"$set": {"genshin_uid": int(uid)}},
        upsert=True
    )

    await status_msg.edit_text(
        f"✅ **Login Successful!**\n"
        f"👤 **Player:** {nickname} (AR {level})\n"
        f"🆔 **UID:** <code>{uid}</code> linked!",
        parse_mode="HTML"
    )

@dp.message(Command("logout"))
async def logout_user(message: types.Message):
    user_id = str(message.from_user.id)
    
    # Check if the user is even logged in first
    user_data = await users_col.find_one({"user_id": user_id})
    
    if not user_data or "genshin_uid" not in user_data:
        return await message.answer("❌ You are not currently logged in.")

    # Remove only the genshin_uid field from the document
    await users_col.update_one(
        {"user_id": user_id},
        {"$unset": {"genshin_uid": ""}}
    )

    await message.answer("✅ **Logged out!** Your UID has been removed from the bot's memory.")
@dp.message(Command("myprofile"))
async def my_profile(message: types.Message):
    user_data = await users_col.find_one({"user_id": str(message.from_user.id)})

    if not user_data or "genshin_uid" not in user_data:
        return await message.answer("❌ You are not logged in! Use `/login <uid>`.")

    uid = user_data["genshin_uid"]
    data = await fetch_enka_data(str(uid))

    if not data:
        return await message.answer("❌ Could not reach Enka.Network. Try again later.")

    player = data.get("playerInfo", {})
    nickname = player.get("nickname", "Traveler")
    level = player.get("level", 1)
    signature = player.get("signature", "No signature")
    achievements = player.get("finishAchievementNum", 0)
    
    # Handle the Avatar/PFP URL
    icon_name = player.get("profilePicture", {}).get("baseIcon", "UI_AvatarIcon_Side_PlayerBoy")
    pfp_url = f"https://enka.network/ui/{icon_name}.png"

    caption = (
        f"👤 <b>{nickname}</b> (AR {level})\n"
        f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        f"💬 <i>{signature}</i>\n\n"
        f"🏆 <b>Achievements:</b> {achievements}\n"
        f"🆔 <b>UID:</b> <code>{uid}</code>"
    )

    try:
        await message.answer_photo(photo=pfp_url, caption=caption, parse_mode="HTML")
    except Exception:
        await message.answer(caption, parse_mode="HTML")

# --- Startup ---
async def main():
    print("Bot is starting...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
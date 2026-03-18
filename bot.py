import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import logging
import sys
import random
import io
import aiohttp
from dotenv import load_dotenv
import os
from database import users_col, cluster
from enka_api import fetch_enka_data
import requests
from aioenkanetworkcard import encbanner
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime, timedelta
from aiogram.types import FSInputFile, BufferedInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from pytz import timezone
from card_gen import generate_profile_card
from wishing import combine_images
from genshin_utils import get_exploration_data,get_abyss_data,get_player_full_data
from data import weapons3, characters4, characters5, rare

ITEMS_PER_PAGE = 10
dp = Dispatcher()

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
MONGO_URL = os.getenv("MONGO_URL")
ADMIN_VAL = os.getenv("ADMIN_ID")

if not TOKEN or not MONGO_URL or not ADMIN_VAL:
    print("❌ ERROR: Missing environment variables in .env file!")
    sys.exit(1)

ADMIN_ID = int(ADMIN_VAL)

cluster = AsyncIOMotorClient(MONGO_URL)
db = cluster["genshin_bot"]
users_col = db["user_stats"]


# ---------------- Dictionaries ----------------


CURRENT_RATE_UP_KEY = "chasca" 
CURRENT_RATE_UP_NAME = characters5.get(CURRENT_RATE_UP_KEY, "Chasca")

def get_rarity(name):
    # Ensure name is stripped of extra spaces for matching
    clean_name = name.strip()
    if clean_name in characters5.values():
        return 5
    elif clean_name in characters4.values():
        return 4
    else:
        return 3

def build_collection_page(sorted_chars, page, first_name):

    start = page * ITEMS_PER_PAGE
    end = start + ITEMS_PER_PAGE
    items = sorted_chars[start:end]

    response = f"📜 {first_name}'s Characters\n"
    response += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n\n"

    for name, count in items:

        num = count - 1
        constellation = "C6+" if num > 6 else f"C{num}"

        rarity = get_rarity(name)
        stars = "★" * rarity

        response += f"{stars} {name} — {constellation}\n"

    total_pages = (len(sorted_chars) - 1) // ITEMS_PER_PAGE

    buttons = []

    if page > 0:
        buttons.append(
            InlineKeyboardButton(text="⬅ Back", callback_data=f"col_{page-1}")
        )

    if page < total_pages:
        buttons.append(
            InlineKeyboardButton(text="Next ➡", callback_data=f"col_{page+1}")
        )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[buttons]) if buttons else None

    return response, keyboard
async def add_to_collection(user_id, char_name):
    # $inc increases the count by 1. If character doesn't exist, it creates it.
    await users_col.update_one(
        {"user_id": user_id},
        {"$inc": {f"collection.{char_name}": 1}}
    )

@dp.callback_query(lambda c: c.data.startswith("col_"))
async def change_collection_page(callback: types.CallbackQuery):

    page = int(callback.data.split("_")[1])

    user_id = str(callback.from_user.id)
    user = await users_col.find_one({"user_id": user_id})

    chars = user["collection"]

    sorted_chars = sorted(
    chars.items(),
    key=lambda x: (get_rarity(x[0]), x[1]),
    reverse=True
     )

    text, keyboard = build_collection_page(
        sorted_chars,
        page,
        callback.from_user.first_name
    )

    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    user_id = str(message.from_user.id)
    first_name = message.from_user.first_name
    
    # Check if user exists, if not, create them with 200 starting wishes
    user = await users_col.find_one({"user_id": user_id})
    if not user:
        new_user = {
            "user_id": user_id, 
            "pity": 0, 
            "count4": 0, 
            "total_wishes": 0, 
            "wish_count": 200, 
            "collection": {},
            "last_daily_wish": datetime.utcnow() - timedelta(days=1)
        }
        await users_col.insert_one(new_user)
        welcome_text = f"🌟 Welcome to Teyvat, {first_name}! 🌟\n\nI've given you 200 Wishes to start your journey!"
    else:
        welcome_text = f"👋 Welcome back, {first_name}!"

    commands_list = (
        f"{welcome_text}\n\n"
        "Available Commands:\n"
        "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        "✨ `/wish` — Perform a single wish (1 pull)\n"
        "🌠 `/wish10` — Perform a 10-pull (Guaranteed 4★)\n"
        "📅 `/daily` — Claim your daily free wish\n"
        "📜 `/collection` — View your characters & constellations\n"
        "📊 `/stats` — Check your pity and wish balance\n"
        "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        "*Good luck with your pulls!*"
    )

    await message.answer(commands_list, parse_mode="Markdown")

#wish10------------------------------------------------------------------------------


@dp.message(Command("wish10"))
async def send_image_10(message: types.Message):
    user_id = str(message.from_user.id)
    
    user = await users_col.find_one({"user_id": user_id})
    if not user:
        user = {"user_id": user_id, "pity": 0, "count4": 0, "total_wishes": 0 , "wish_count": 200, "collection": {}}
        await users_col.insert_one(user)

    pity = user.get("pity", 0)
    count4 = user.get("count4", 0)
    wish_count = user.get("wish_count", 0)
    total_wishes = user.get("total_wishes", 0)
    current_collection = user.get("collection", {})
    is_guaranteed = user.get("is_guaranteed", False)
    new_guaranteed_status = is_guaranteed

    if wish_count < 10:
        await message.answer(f"❌ You don't have enough wishes. You only have {wish_count}.")
        return
    
    loading_photo = FSInputFile("Loading_Screen_Startup.webp")
    loading_msg = await message.answer_photo(photo=loading_photo, caption="✨ Invoking the Tides of Fate...")

    results = []
    pulled_chars = []
    
    # --- FIX 1: Initialize Splash Defaults ---
    # This prevents UnboundLocalError if the logic fails
    splash_name = "Debate Club" 
    splash_rarity = 3
    file_path = "https://raw.githubusercontent.com/FrenzyYum/GenshinWishingBot/master/assets/images/debate.webp"
    best_rarity_score = 0 
    result_msg = ""

    for i in range(10):
        pity += 1
        is_5star = False
        is_4star = False
        is_rare = False
        
        # --- FIX 2: Initialize loop-local variables ---
        current_display_name = ""
        current_file_key = ""

        # --- 1. Determine Rarity ---
        if pity >= 89:
            pity = 0
            is_5star = True
        else:
            if random.randint(1, 1000) <= 20:
                is_rare = True
            elif random.randint(1, 1000) <= 6:
                pity = 0
                is_5star = True
            elif count4 >= 9 or (i == 9 and not any([is_5star, is_4star])):
                count4 = 0
                is_4star = True
            elif random.randint(1, 10) == 1:
                count4 = 0
                is_4star = True
            else:
                count4 += 1

        # --- 2. Process the Pull ---
        if is_5star:
            win_roll = random.randint(1, 100)
            if is_guaranteed or win_roll <= 50:
                current_file_key = CURRENT_RATE_UP_KEY
                current_display_name = CURRENT_RATE_UP_NAME
                new_guaranteed_status = False
                result_msg = " (RATE-UP WIN!)"
                current_score = 4 
            else: 
                current_file_key = random.choice(list(characters5.keys()))
                current_display_name = characters5[current_file_key]
                new_guaranteed_status = True
                result_msg = " (50/50 Lost...)"
                current_score = 2

            if current_score > best_rarity_score:
                splash_name = current_display_name
                splash_rarity = 5
                file_path = f"https://raw.githubusercontent.com/Mantan21/Genshin-Impact-Wish-Simulator/master/src/images/characters/splash-art/5star/{current_file_key}.webp"
                best_rarity_score = current_score
            
            # Add to results/collection
            total_so_far = current_collection.get(current_display_name, 0) + pulled_chars.count(current_display_name)
            if total_so_far >= 7:
                wish_count += 2
                results.append(f"꩜ {current_display_name} (C6+ -> +2 Wish) ★★★★★")
            else:
                pulled_chars.append(current_display_name)
                results.append(f"꩜ {current_display_name} ★★★★★")

        elif is_rare:
            current_file_key = random.choice(list(rare.keys()))
            current_display_name = rare[current_file_key]
            
            if 3 > best_rarity_score:
                splash_name = current_display_name
                splash_rarity = "Rare"
                file_path = FSInputFile(f"images/rare/{current_file_key}.webp")
                best_rarity_score = 3
            results.append(f"꩜ {current_display_name} ✨")

        elif is_4star:
            current_file_key = random.choice(list(characters4.keys()))
            current_display_name = characters4[current_file_key]
            
            if 1 > best_rarity_score:
                splash_name = current_display_name
                splash_rarity = 4
                file_path = f"https://raw.githubusercontent.com/Mantan21/Genshin-Impact-Wish-Simulator/master/src/images/characters/splash-art/4star/{current_file_key}.webp"
                best_rarity_score = 1 
            
            total_so_far = current_collection.get(current_display_name, 0) + pulled_chars.count(current_display_name)
            if total_so_far >= 7:
                wish_count += 1
                results.append(f"꩜ {current_display_name} (C6+ -> +1 Wish) ★★★★")
            else:
                pulled_chars.append(current_display_name)
                results.append(f"꩜ {current_display_name} ★★★★") 
        
        else:
            current_file_key = random.choice(list(weapons3.keys()))
            current_display_name = weapons3[current_file_key]
            results.append(f"꩜ {current_display_name} ★★★")

    # --- 3. Update Database ---
    # (Same as your original database logic)
    total_wishes += 10
    wish_count -= 10
    update_query = {"$set": {"wish_count": wish_count, "pity": pity, "count4": count4, "total_wishes": total_wishes, "is_guaranteed": new_guaranteed_status}}
    if pulled_chars:
        inc_data = {}
        for char in pulled_chars:
            inc_data[f"collection.{char}"] = inc_data.get(f"collection.{char}", 0) + 1
        update_query["$inc"] = inc_data
    await users_col.update_one({"user_id": user_id}, update_query)

    # --- 4. Image Handling ---
    bg_path = "https://raw.githubusercontent.com/Mantan21/Genshin-Impact-Wish-Simulator/master/src/images/background/splash-background.webp"
    combined_img = combine_images(file_path, bg_path, splash_name, splash_rarity)
    
    output = io.BytesIO()
    combined_img.save(output, format="PNG")
    output.seek(0)
    photo_file = BufferedInputFile(output.read(), filename="wish.png")
    
    try:
        await loading_msg.delete()
    except: pass
        
    await message.answer_photo(
        photo=photo_file,
        caption=f"★ Your 10-Pull Results ★"+result_msg+"\n\n"+"\n".join(results),
        parse_mode="Markdown"
    )
@dp.message(Command("wish"))
async def send_single(message: types.Message):
    loading_photo = FSInputFile("Loading_Screen_Startup.webp")
    loading_msg = await message.answer_photo(
        photo=loading_photo, 
        caption="✨ Invoking the Tides of Fate..."
    )
    user_id = str(message.from_user.id)
    user = await users_col.find_one({"user_id": user_id})
    if not user:
        user = {"user_id": user_id, "pity": 0, "count4": 0, "total_wishes": 0, "wish_count": 200, "collection": {}}
        await users_col.insert_one(user)

    pity = user.get("pity", 0)
    count4 = user.get("count4", 0)
    total_wishes = user.get("total_wishes", 0)
    wish_count = user.get("wish_count", 0)
    current_collection = user.get("collection", {})
    is_guaranteed = user.get("is_guaranteed", False)
    new_guaranteed_status = is_guaranteed
    
    if wish_count < 1:
        await message.answer(f"❌ You don't have enough wishes. You only have {wish_count}.")
        return

    pulled_chars = []
    is_5star = False
    is_4star = False
    result_msg=""

    # Logic for Rarity
    if pity >= 89:
        is_5star = True
    else:
        star4check = random.randint(1, 10)
        if count4 >= 9 or star4check == 10:
            is_4star = True
        else:
            # Check for random 5-star luck (0.6% chance)
            if random.randint(1, 1000) < 7:
                is_5star = True

    # Process result
    if is_5star:
        pity = 0
        count4 += 1
        win_roll = random.randint(1, 100)

        if is_guaranteed or win_roll <= 60:
                file_key = CURRENT_RATE_UP_KEY
                display_name = CURRENT_RATE_UP_NAME
                new_guaranteed_status = False
                result_msg = f"(RATE-UP WIN!)"
        else: 
                file_key = random.choice(list(characters5.keys()))
                display_name = characters5[file_key]
                new_guaranteed_status = True
                result_msg = f"(50/50 Lost...)"

        splash_name = display_name
        splash_rarity = 5
        file_path = f"https://raw.githubusercontent.com/Mantan21/Genshin-Impact-Wish-Simulator/master/src/images/characters/splash-art/5star/{file_key}.webp"
        
        if current_collection.get(display_name, 0) >= 7:
            wish_count += 2
            name = f"꩜ {display_name} (Duplicate C6 -> +2 Wish) ★★★★★"
        else:
            pulled_chars.append(display_name)
            name = f"꩜ {display_name} ★★★★★"

    elif is_4star:
        count4 = 0
        pity += 1
        file_key = random.choice(list(characters4.keys()))
        display_name = characters4[file_key]
        splash_name = display_name
        splash_rarity = 4
        file_path = f"https://raw.githubusercontent.com/Mantan21/Genshin-Impact-Wish-Simulator/master/src/images/characters/splash-art/4star/{file_key}.webp"
        
        if current_collection.get(display_name, 0) >= 7:
            wish_count += 1
            name = f"꩜ {display_name} (Duplicate C6 -> +1 Wish) ★★★★"
        else:
            pulled_chars.append(display_name)
            name = f"꩜ {display_name} ★★★★"
    else:
        pity += 1
        count4 += 1
        file_key = random.choice(list(weapons3.keys()))
        display_name = weapons3[file_key]
        splash_name = display_name
        splash_rarity = 3
        name = f"꩜ {display_name} ★★★"
        file_path = f"https://raw.githubusercontent.com/FrenzyYum/GenshinWishingBot/master/assets/images/{file_key}.webp"

    wish_count -= 1
    total_wishes += 1

    # Database Update
    if pulled_chars:
        await users_col.update_one({"user_id": user_id}, {"$inc": {f"collection.{pulled_chars[0]}": 1}})
    
    await users_col.update_one({"user_id": user_id}, {"$set": {
        "wish_count": wish_count, "pity": pity, "count4": count4, "total_wishes": total_wishes ,"is_guaranteed": new_guaranteed_status}
    })

    # Image sending logic (Keep your existing PIL code here...)
    bg_path = "https://raw.githubusercontent.com/Mantan21/Genshin-Impact-Wish-Simulator/master/src/images/background/splash-background.webp"
    combined_img = combine_images(file_path, bg_path, splash_name, splash_rarity)
    output = io.BytesIO()
    combined_img.save(output, format="PNG")
    output.seek(0)
    photo_file = BufferedInputFile(output.read(), filename="wish.png")
    
    try:
        await loading_msg.delete()
    except:
        pass # In case user deleted it manually
        
    await message.answer_photo(photo=photo_file, caption=result_msg + name)
@dp.message(Command("give"))
async def give_wishes(message: types.Message):
    # 1. Admin Security Check
    if message.from_user.id != ADMIN_ID:
        await message.answer("🚫 Access Denied.",parse_mode="Markdown")
        return

    args = message.text.split()
    target_id = None
    amount = 0

    # 2. Logic for Reply vs. Manual ID
    if message.reply_to_message:
        # If replying to a message, get that user's ID
        target_id = str(message.reply_to_message.from_user.id)
        if len(args) < 2:
            await message.answer("❓ Usage: Reply to someone with `/give <amount>`",parse_mode="Markdown")
            return
        try:
            amount = int(args[1])
        except ValueError:
            await message.answer("❌ Amount must be a number!")
            return
    else:
        # Manual mode: /give <user_id> <amount>
        if len(args) < 3:
            await message.answer("❓ Usage: `/give <user_id> <amount>` or reply to a message with `/give <amount>`",parse_mode="Markdown")
            return
        target_id = args[1]
        try:
            amount = int(args[2])
        except ValueError:
            await message.answer("❌ Amount must be a number!")
            return

    # 3. Database Update
    result = await users_col.update_one(
        {"user_id": target_id},
        {"$inc": {"wish_count": amount}}
    )

    if result.matched_count > 0:
        await message.answer(f"✅ Granted {amount} wishes to user `{target_id}`.",parse_mode="Markdown")
        # Notify the lucky user
        try:
            await message.bot.send_message(
                chat_id=target_id,
                text=f"🎁 Admin Bonus!\nYou received {amount} wishes! Check  `/stats`",parse_mode="Markdown"
            )
        except:
            pass
    else:
        await message.answer("❌ User not found in database.")

@dp.message(Command("gamble"))
async def gamble_wishes(message: types.Message):
    user_id = str(message.from_user.id)
    args = message.text.split()

    # 1. Validation: Did they provide a number?
    if len(args) < 2:
        await message.answer("🎲 Double or Nothing\nUsage: `/gamble <amount>`\nExample: `/gamble 50`")
        return

    try:
        bet = int(args[1])
    except ValueError:
        await message.answer("❌ Please enter a whole number for your bet.")
        return

    if bet <= 0:
        await message.answer("❌ You can't bet 0 or negative wishes!")
        return

    # 2. Database Check: Do they have the money?
    user = await users_col.find_one({"user_id": user_id})
    if not user:
        await message.answer("❌ Please run `/start` first!")
        return
        
    current_balance = user.get("wish_count", 0)
    if current_balance < bet:
        await message.answer(f"❌ You only have {current_balance} wishes. You can't bet {bet}!")
        return

    # 3. The 50/50 Roll
    # random.random() returns a float between 0.0 and 1.0
    win = random.random() >= 0.5 

    if win:
        # Win: They keep their bet and get an equal amount added
        new_balance = current_balance + bet
        result_msg = f"🏆 WINNER!\nYou doubled your bet! Received +{bet} wishes."
        emoji = "💰"
    else:
        # Lose: The bet amount is subtracted
        new_balance = current_balance - bet
        result_msg = f"💀 BUSTED!\nYou lost your {bet} wishes. Better luck next time!"
        emoji = "📉"

    # 4. Update Database
    await users_col.update_one(
        {"user_id": user_id},
        {"$set": {"wish_count": new_balance}}
    )

    # 5. Final Response
    await message.answer(
        f"🎲 Gamble Result\n⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        f"{emoji} {result_msg}\n\n"
        f"👛 New Balance: {new_balance} Wishes",
        parse_mode="Markdown"
    )
@dp.message(Command("daily"))
async def daily_wish(message: types.Message):
    user_id = str(message.from_user.id)
    user = await users_col.find_one({"user_id": user_id})
    
    now = datetime.utcnow()
    
    # 1. Check for 24-hour cooldown
    if user and "last_daily_wish" in user:
        last = user["last_daily_wish"]
        if now - last < timedelta(days=1):
            remaining = timedelta(days=1) - (now - last)
            hours = remaining.seconds // 3600
            minutes = (remaining.seconds % 3600) // 60
            await message.answer(f"⏳ Already claimed! Come back in {hours}h {minutes}m.")
            return

        # 2. Update Streak Logic
        # If last claim was more than 48 hours ago, reset to 1. Otherwise, +1.
        if now - last > timedelta(days=2):
            streak = 1
        else:
            streak = user.get("daily_streak", 0) + 1
    else:
        streak = 1

    # 3. Calculate Rewards & Milestone Messages
    wishes_to_add = 5
    bonus_msg = ""

    if streak == 7:
        wishes_to_add += 10
        bonus_msg = "\n🔥 WEEKLY BONUS: +10 Wishes!"
    elif streak == 14:
        wishes_to_add += 20
        bonus_msg = "\n🔥 FORTNIGHT BONUS: +20 Wishes!"
    elif streak == 21:
        wishes_to_add += 30
        bonus_msg = "\n🔥 ULTIMATE BONUS: +30 Wishes!\n*(Streak reset to 0)*"
        # Reset streak after hitting the max milestone
        streak = 0 

    # 4. Update Database
    await users_col.update_one(
        {"user_id": user_id},
        {
            "$set": {"last_daily_wish": now, "daily_streak": streak ,"notification_sent": False},
            "$inc": {"wish_count": wishes_to_add}
        },
        upsert=True
    )

    # 5. Send Response with Current Streak
    await message.answer(
        f"🎁 Daily Reward Claimed!\n"
        f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        f"🎫 Added: +{wishes_to_add} Wish(es)\n"
        f"🔥 Current Streak: {streak} Days"
        f"{bonus_msg}",
        parse_mode="Markdown"
    )
async def check_individual_dailies(bot: Bot):
    now = datetime.utcnow()
    threshold = now - timedelta(days=1)
    
    cursor = users_col.find({
        "last_daily_wish": {"$lte": threshold},
        "notification_sent": {"$ne": True}
    })

    # 1. Generate the image once to save CPU/Memory
    file_path = f"https://raw.githubusercontent.com/Mantan21/Genshin-Impact-Wish-Simulator/master/src/images/characters/splash-art/5star/{CURRENT_RATE_UP_KEY}.webp"
    bg_path = "https://raw.githubusercontent.com/Mantan21/Genshin-Impact-Wish-Simulator/master/src/images/background/splash-background.webp"
    
    # Use the combine_images logic you already built
    combined_img = combine_images(file_path, bg_path, CURRENT_RATE_UP_NAME, "Rate-Up")
    
    # Store the raw bytes in memory
    img_byte_arr = io.BytesIO()
    combined_img.save(img_byte_arr, format="PNG")
    img_data = img_byte_arr.getvalue() # Get the actual bytes

    async for user in cursor:
        try:
            # 2. Create a fresh file object for EACH user
            photo_file = BufferedInputFile(img_data, filename="wish.png")
            
            await bot.send_photo(
                chat_id=user["user_id"],
                photo=photo_file,
                caption=( # Use 'caption' instead of 'text'
                    f"✨ **Your Daily Wish is ready!** ✨\n"
                    f"Claim it now to keep your streak alive!\n"
                    f"Current Rate up: {CURRENT_RATE_UP_NAME}"
                ),
                parse_mode="Markdown"
            )
            
            await users_col.update_one(
                {"user_id": user["user_id"]},
                {"$set": {"notification_sent": True}}
            )
            await asyncio.sleep(0.05) # Prevent Telegram flood limits
        except Exception as e:
            logging.error(f"Failed to notify {user['user_id']}: {e}")
@dp.message(Command("collection"))
async def show_collection(message: types.Message):

    user_id = str(message.from_user.id)
    user = await users_col.find_one({"user_id": user_id})

    if not user or "collection" not in user or not user["collection"]:
        await message.answer("📭Your collection is empty!\nUse /wish or /wish10 to find characters.")
        return

    chars = user["collection"]
    # Sort by rarity first, then by the number of duplicates
    sorted_chars = sorted(
        chars.items(),
        key=lambda x: (get_rarity(x[0]), x[1]),
        reverse=True
 )

    text, keyboard = build_collection_page(
        sorted_chars,
        0,
        message.from_user.first_name
    )

    await message.answer(text, reply_markup=keyboard, parse_mode="Markdown")

@dp.message(Command("stats"))
async def show_stats(message: types.Message):
    user_id = str(message.from_user.id)
    
    # 1. Fetch user or create if new
    user = await users_col.find_one({"user_id": user_id})
    if not user:
        user = {"user_id": user_id, "pity": 0, "count4": 0, "total_wishes": 0 , "wish_count":200}
        await users_col.insert_one(user)
    wish_count = user["wish_count"]
    twishes = user["total_wishes"]
    pity = user["pity"]
    count4 = user["count4"]
    guaranteed = "✅ Yes" if user.get("is_guaranteed", False) else "❌ No"

    await message.reply(
        f"Stats for {message.from_user.first_name}:\n"
        f"Total wishes: {twishes}\n"
        f"Wishes: {wish_count}\n"
        f"🔥 Guaranteed: {guaranteed}\n"
        f"Current 5★ Pity: {pity}\n"
        f"Current 4★ Pity: {count4}" # Changed label to be more accurate
    )
@dp.message(Command("broadcast"))
async def broadcast_smart(message: types.Message, bot: Bot):
    if message.from_user.id != ADMIN_ID:
        await message.answer("🚫 **Access Denied**")
        return

    # 1. Determine if there is a photo or just text
    # If it's a photo, the text is in 'caption'. If not, it's in 'text'.
    broadcast_text = (message.caption or message.text).replace("/broadcast", "").strip()
    photo_id = message.photo[-1].file_id if message.photo else None

    if not broadcast_text and not photo_id:
        await message.answer("❓ **Usage:** Send an image with caption `/broadcast ...` or just text.")
        return

    status_msg = await message.answer("⏳ **Broadcasting to all travelers...**")
    
    cursor = users_col.find({})
    success, fail = 0, 0

    async for user in cursor:
        try:
            if photo_id:
                # Send the photo with the caption
                await bot.send_photo(chat_id=user["user_id"], photo=photo_id, caption=broadcast_text, parse_mode="Markdown")
            else:
                # Send just the text
                await bot.send_message(chat_id=user["user_id"], text=broadcast_text, parse_mode="Markdown")
            
            success += 1
            await asyncio.sleep(0.05) # Prevent flood limits
        except Exception:
            fail += 1

    await status_msg.edit_text(f"✅ **Broadcast Complete**\n🟢 Success: {success}\n🔴 Failed: {fail}")
@dp.message(Command("setrateup"))
async def set_rate_up(message: types.Message):
    global CURRENT_RATE_UP_KEY, CURRENT_RATE_UP_NAME
    
    if message.from_user.id != ADMIN_ID:
        await message.answer("🚫 **Access Denied.**")
        return

    args = message.text.split()
    if len(args) < 2:
        await message.answer("❓ **Usage:** `/setrateup <character_key>`\nExample: `/setrateup raiden-shogun`")
        return

    new_key = args[1].lower()
    if new_key in characters5:
        CURRENT_RATE_UP_KEY = new_key
        CURRENT_RATE_UP_NAME = characters5[new_key]
        await message.answer(f"✅ Banner Updated!\n**New Rate-Up:** {CURRENT_RATE_UP_NAME}")
    else:
        await message.answer(f"❌ Character `{new_key}` not found in 5-star list.")  

async def get_enka_data(uid: str):
    """Directly fetches data from Enka.Network API"""
    url = f"https://enka.network/api/uid/{uid}/"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                return await resp.json()
            return None
# ---------------- Main Enka ----------------
@dp.message(Command("login"))
async def login_uid(message: types.Message):
    args = message.text.split()
    if len(args) < 2:
        return await message.answer("❓ <b>Usage:</b> `/login <uid>`",parse_mode="HTML")

    uid = args[1]
    if not uid.isdigit():
        return await message.answer("❌ Please enter a numeric UID.")

    status_msg = await message.answer(f"🔍 Verifying UID {uid}...")
    data = await fetch_enka_data(uid)
    
    if not data or "playerInfo" not in data:
        return await status_msg.edit_text("❌ UID not found or Showcase is private.")

    player = data["playerInfo"]
    await users_col.update_one(
        {"user_id": str(message.from_user.id)},
        {"$set": {"genshin_uid": int(uid)}},
        upsert=True
    )
    await status_msg.edit_text(f"✅ <b>Login Successful! <code>{uid}</code></b>\n👤 <b>Player:</b> {player.get('nickname')} (AR {player.get('level')})", parse_mode="HTML")

# --- MyProfile Command ---
@dp.message(Command("myprofile"))
async def my_profile(message: types.Message):
    # 1. Get UID from your MongoDB
    user_data = await users_col.find_one({"user_id": str(message.from_user.id)})
    if not user_data or "genshin_uid" not in user_data:
        return await message.answer("❌ Please /login <uid> first.")

    db_uid = str(user_data["genshin_uid"]).strip()
    
    # 2. Show loading status
    status = await message.answer("🔄 <b>Accessing Akasha Terminal...</b>", parse_mode="HTML")
    
    # 3. Fetch Data
    user_info = await get_player_full_data(db_uid)
    exploration_data = await get_exploration_data(db_uid) # Your existing exploration function
    abyss_data = await get_abyss_data(db_uid)           # Your existing abyss function
    
    await status.delete()

    if not user_info:
        return await message.reply("❌ Data hidden. Is your 'Battle Chronicle' public in HoYoLAB?")

    # 4. Build the Caption String
    msg = f"👤 <b>{user_info['name']}</b> | UID: <code>{db_uid}</code>\n"
    msg += f"⭐ <b>AR {user_info['level']}</b> | WL {user_info['world_level']}\n"
    msg += f"🏆 <b>Achievements:</b> {user_info['achievements']} | 📅 <b>Days:</b> {user_info['days_active']}\n"
    
    if user_info['signature']:
        msg += f"<i>\"{user_info['signature']}\"</i>\n"
        
    msg += "<code>" + "═" * 25 + "</code>\n\n"

    msg += "<b>🌍 EXPLORATION</b>\n"
    for area in exploration_data:
        msg += f"📍 <code>{area['name']:15}</code>: {area['percent']}%\n"

    if abyss_data:
        msg += f"\n<b>⚔️ SPIRAL ABYSS</b>\n{abyss_data}"

    # 5. Send Photo with Caption (with Fallback)
    if user_info['icon']:
        try:
            return await message.answer_photo(
                photo=user_info['icon'], 
                caption=msg, 
                parse_mode="HTML"
            )
        except Exception as e:
            # If Telegram rejects the URL, log it and fall back to text
            print(f"!!! PHOTO SEND FAILED: {e} | URL: {user_info['icon']}", file=sys.stderr, flush=True)

    # 6. Fallback to Text-only if photo fails
    await message.answer(msg, parse_mode="HTML")
# ---------------- Main ----------------
async def main():
    # 1. Test MongoDB connection first
    try:
        await cluster.admin.command('ping')
        print("✅ Successfully connected to MongoDB!")
    except Exception as e:
        print(f"❌ MongoDB Connection Error: {e}")
        return 

    # 2. Create the Bot object FIRST
    bot = Bot(token=TOKEN)

    # Use your local Sri Lanka timezone
    lk_timezone = timezone("Asia/Colombo")
    
    scheduler = AsyncIOScheduler(timezone=lk_timezone)

    # --- JOB 1: Check individual 24h cooldowns every 15 minutes ---
    scheduler.add_job(
        check_individual_dailies, 
        "interval", 
        minutes=15, 
        args=[bot]
    )

    # --- JOB 2: Run the daily reset task at Midnight (Optional) ---
    scheduler.add_job(
        daily_wish, 
        "cron", 
        hour=0, 
        minute=0, 
        args=[bot]
    )
    
    # 4. Start everything
    scheduler.start()
    print("⏰ Both schedulers started (Interval & Midnight)!")

    # 5. Start polling
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())








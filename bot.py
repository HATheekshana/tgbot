import asyncio
import genshin
from motor.motor_asyncio import AsyncIOMotorClient
import logging
import math
import sys
import random
import io
import aiohttp
from pymongo import ReturnDocument
from dotenv import load_dotenv
import os
import json
import time
from aiogram import types, F
from char_compare import compare_characters
from database import users_col, cluster, groups_col
from enka_api import fetch_enka_data
from aiogram.filters import Command
from comapre_image import create_masked_showcase
from aiogram.utils.keyboard import InlineKeyboardBuilder
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime, timedelta
from aiogram.types import FSInputFile, URLInputFile, InputMediaPhoto,FSInputFile, BufferedInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from pytz import timezone
from wishing import combine_images
from create_profile import create_genshin_profile
from genshin_utils import  get_enkadata,get_quiz_score,to_int,get_val,get_exploration_data,get_abyss_data,get_player_full_data,calculate_world_level,format_abyss_info
from data import weapons3, characters4, characters5, rare

quiz_track = {}
group_message_counts = {}
QUIZ_THRESHOLD = 40
COOKIES = {
    "ltuid_v2": "471000302",
    "ltoken_v2": "v2_CAISDGM5b3FhcTNzM2d1OBokZTFmZTViNmItZDgxOS00MzNlLWJiZDktYWJkMTEzMWY1ZmY0ILaq780GKNa-zZEGMO7Jy-ABQgtiYnNfb3ZlcnNlYVhqagJTRw.NtW7aQAAAAAB.MEUCIGXUWYTB1bk4uUPg-Mwv8mZ6fXGUPvhKlkks9aizJCKVAiEA5ukOrLn7OhrY4JKtlMzZEXWCY-f-lCsBnIESDT_xbpY"
}
client = genshin.Client(COOKIES)
client.region = genshin.Region.OVERSEAS
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

# Add this line near the top of your file, outside of any functions
active_polls = {}
# ---------------- Dictionaries ----------------


CURRENT_RATE_UP_KEY = "chasca" 
CURRENT_RATE_UP_NAME = characters5.get(CURRENT_RATE_UP_KEY, "Chasca")

try:
    with open('char.json', 'r') as file:
        CHARACTER_MAP = json.load(file)
except Exception as e:
    print(f"Error loading char.json: {e}")
    CHARACTER_MAP = {}

@dp.message(Command("characters"))
async def cmd_characters(message: types.Message):
    user_data = await users_col.find_one({"user_id": str(message.from_user.id)})
    if not user_data or "genshin_uid" not in user_data:
        return await message.reply("Please /login <uid> first.")

    db_uid = str(user_data["genshin_uid"]).strip()
    
    msg = await message.reply("Fetching your showcase...")
    
    user_info_enka = await get_enkadata(db_uid)
    # Enka uses 'avatarInfoList' for the character data
    showcase_items = user_info_enka.get("showAvatarInfoList", [])

    if not showcase_items:
        await msg.edit_text("No characters found! Make sure 'Show Character Details' is ON in-game.")
        return

    builder = InlineKeyboardBuilder()

    for index, char in enumerate(showcase_items):
        char_id = str(char.get("avatarId"))
        
        # 2. LOOK UP THE ID AND EXTRACT THE 'name' FIELD
        char_entry = CHARACTER_MAP.get(char_id)
        
        if char_entry:
            # Use the "name" field we added to the JSON
            display_name = char_entry.get("name", "Unknown")
        else:
            display_name = f"ID: {char_id}"

        # Add button
        builder.button(
            text=display_name, 
    # Store the person who sent the command (message.from_user.id)
            callback_data=f"gen_{db_uid}_{index}_{message.from_user.id}" 
        )
    image_buffer = await create_genshin_profile(db_uid) 
    if image_buffer:
        # Create the file object from buffer
        photo = BufferedInputFile(image_buffer.getvalue(), filename=f"{db_uid}.png")

    # 3x4 grid layout
    builder.adjust(3)

    await msg.delete() # Remove the "Fetching..." message
    await message.reply_photo(
        photo=photo,
        caption="Select a character:",
        reply_markup=builder.as_markup(),
        parse_mode="Markdown"
    )
@dp.callback_query(F.data.startswith("gen_"))
async def handle_card_generation(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    uid, char_index, owner_id = parts[1], int(parts[2]), int(parts[3])
    if callback.from_user.id != owner_id:
        return await callback.answer("⏳ This menu isn't for you! Run /characters to see your own.", show_alert=True)
    await callback.answer("Fetching Build & Rank...")

    # 1. Loading state (Swap to your local image)
    try:
        loading_img = FSInputFile("Loading_Screen_Startup.webp")
        await callback.message.edit_media(
            media=InputMediaPhoto(
                media=loading_img,
                caption="<b>Creating card and calculating rank...</b>",
                parse_mode="HTML"
            )
        )
    except Exception: pass

    # 2. Get the specific Character ID for the ranking lookup
    user_info = await get_enkadata(uid)
    showcase = user_info.get("showAvatarInfoList", [])
    
    # Identify the character being generated
    current_char = showcase[char_index]
    char_id = str(current_char.get("avatarId"))
    char_entry = CHARACTER_MAP.get(char_id)
        
    if char_entry:
            # Use the "name" field we added to the JSON
        display_name = char_entry.get("name", "Unknown")
    else:
        display_name = f"ID: {char_id}" # e.g., "10000089"

    card_api = "https://gi-card-api.onrender.com/character_card"
    ranking_api = f"https://test-xehj.onrender.com/get/ranking/{uid}"

    async with aiohttp.ClientSession() as session:
        try:
            # Request 1: The Build Card
            payload = {"uid": uid, "character_index": char_index, "template": 1, "img": None}
            async with session.post(card_api, json=payload) as card_resp:
                card_data = await card_resp.json()
                card_url = card_data.get("response") or card_data.get("url")

                # Request 2: The Ranking (Correctly Parsing the Dictionary)
                ranking_text = ""
                async with session.get(ranking_api) as rank_resp:
                    if rank_resp.status == 200:
                        all_ranks = await rank_resp.json()
                        # Find the rank using the Character ID key
                        char_rank_data = all_ranks.get(char_id)
                        
                        if char_rank_data:
                            rank = char_rank_data.get("ranking")
                            out_of = char_rank_data.get("outOf")
                            percent = char_rank_data.get("percent")
                            ranking_text = f"\n\n<b>ʚଓ Global Rank :</b> {rank} / {out_of}\n<b>ʚଓ Top :</b> {percent}%"
                        else:
                            ranking_text = ""

                if card_url:
                    # Final Step: Send Result
                    back_builder = InlineKeyboardBuilder()
                    back_builder.button(text="Back to List", callback_data=f"refresh_{uid}")
                    await callback.message.delete()
                    target = callback.message.reply_to_message or callback.message
                    await target.reply_photo(
                        photo=URLInputFile(card_url),
                        caption=f"ʚଓ {display_name} {ranking_text}",
                        reply_markup=back_builder.as_markup(),
                        parse_mode="HTML"
                    )
                    

        except Exception as e:
            await callback.message.edit_caption(caption=f"❌ Error: {str(e)}")
@dp.callback_query(F.data.startswith("refresh_"))
async def handle_back_button(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    uid, owner_id = parts[1], int(parts[2])

    # SECURITY CHECK
    if callback.from_user.id != owner_id:
        return await callback.answer("❌ You can't use this button.", show_alert=True)

    # Re-fetch data for the list
    user_info = await get_enkadata(uid)
    showcase = user_info.get("showAvatarInfoList", [])

    builder = InlineKeyboardBuilder()
    for index, char in enumerate(showcase):
        char_id = str(char.get("avatarId"))
        name = CHARACTER_MAP.get(char_id, {}).get("name", f"ID: {char_id}")
        builder.button(text=name, callback_data=f"gen_{uid}_{index}_{owner_id}")
    builder.adjust(3)

    # Re-generate profile photo
    image_buffer = await create_genshin_profile(uid)
    photo = BufferedInputFile(image_buffer.getvalue(), filename=f"{uid}.png")

    # EDIT the final build card BACK into the character selection menu
    await callback.message.edit_media(
        media=InputMediaPhoto(media=photo, caption="<b>Character Showcase</b>\nSelect a character:", parse_mode="HTML"),
        reply_markup=builder.as_markup()
    )
@dp.message(Command("topquiz"))
async def cmd_top_quiz(message: types.Message):
    if message.chat.type == "private":
        return await message.reply("❌ Use this in a group!")

    chat_id = str(message.chat.id)
    # This is the path to the score inside your 'Object'
    score_path = f"group_quiz.{chat_id}"

    try:
        # 1. We use a filter to find users who HAVE this key in their group_quiz object
        # and ensure the value is a number greater than 0
        cursor = users_col.find({score_path: {"$gt": 0}}).sort(score_path, -1).limit(10)
        top_players = await cursor.to_list(length=10)

        if not top_players:
            # If this shows up, it means the ID in the DB doesn't match the Group ID
            return await message.answer(
                f"🏆 <b>Leaderboard</b>\n\n"
                "No scores found. Try answering a quiz first! 🧠", 
                parse_mode="HTML"
            )

        msg = f"🏆 <b>TOP 10: {message.chat.title}</b>\n"
        msg += "<code>" + "─" * 22 + "</code>\n\n"

        for i, p in enumerate(top_players, 1):
            name = p.get("last_known_name") or f"Player_{str(p['user_id'])[-4:]}"
            
            # 2. Extract the points safely from the nested dictionary
            all_groups = p.get("group_quiz", {})
            pts = all_groups.get(chat_id, 0)
            
            msg += f"{i}. <b>{name}</b> — <code>{pts} pts</code>\n"

        await message.answer(msg, parse_mode="HTML")

    except Exception as e:
        print(f"CRITICAL DB ERROR: {e}")
        await message.answer("⚠️ Error accessing the leaderboard database.")

def get_rarity(name):
    clean_name = name.strip()
    if clean_name in characters5.values():
        return 5
    elif clean_name in characters4.values():
        return 4
    elif clean_name in rare.values():
        return 6
    else:
        return 3
@dp.message(Command("collection"))
async def show_collection(message: types.Message):
    user_id = str(message.from_user.id)
    user = await users_col.find_one({"user_id": user_id})

    if not user or "collection" not in user or not user["collection"]:
        await message.reply("Your collection is empty!\nUse /wish or /wish10 to find characters.")
        return

    chars = user["collection"]
    sorted_chars = sorted(
        chars.items(),
        key=lambda x: (get_rarity(x[0]), x[1]),
        reverse=True
    )

    # Pass user_id here
    text, keyboard = build_collection_page(
        sorted_chars,
        0,
        message.from_user.first_name,
        user_id
    )

    await message.reply(text, reply_markup=keyboard, parse_mode="Markdown")
def build_collection_page(sorted_chars, page, first_name, user_id): # Added user_id
    start = page * ITEMS_PER_PAGE
    end = start + ITEMS_PER_PAGE
    items = sorted_chars[start:end]

    response = f"𑣲 {first_name}'s Characters\n"
    response += "──── ⋆⋅☆⋅⋆ ────\n\n"

    for name, count in items:
        num = count - 1
        constellation = "C6+" if num > 6 else f"C{num}"
        rarity = get_rarity(name)
        stars = "✨" if rarity == 6 else "★" * rarity
        response += f"{stars} {name} — {constellation}\n"

    total_pages = (len(sorted_chars) - 1) // ITEMS_PER_PAGE
    buttons = []

    # Format: col_PAGE_USERID
    if page > 0:
        buttons.append(
            InlineKeyboardButton(text="Back", callback_data=f"col_{page-1}_{user_id}")
        )

    if page < total_pages:
        buttons.append(
            InlineKeyboardButton(text="Next", callback_data=f"col_{page+1}_{user_id}")
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
    # Split the data: col, page, owner_id
    data_parts = callback.data.split("_")
    page = int(data_parts[1])
    owner_id = data_parts[2]
    clicker_id = str(callback.from_user.id)

    # The Security Check
    if clicker_id != owner_id:
        await callback.answer("This is not your collection menu!", show_alert=True)
        return

    user = await users_col.find_one({"user_id": owner_id})
    if not user:
        return

    chars = user["collection"]
    sorted_chars = sorted(
        chars.items(),
        key=lambda x: (get_rarity(x[0]), x[1]),
        reverse=True
    )

    text, keyboard = build_collection_page(
        sorted_chars,
        page,
        callback.from_user.first_name,
        owner_id
    )

    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
import asyncio

import math # Add this at the top of your file

@dp.message(Command("dontuse"))
async def cmd_dont_use(message: types.Message, bot: Bot):
    user_id = str(message.from_user.id)
    user_name = message.from_user.full_name
    
    # 1. Start the countdown
    countdown_msg = await message.reply("⚠️ <b>CRITICAL ERROR:</b> You weren't supposed to do that...",parse_mode="HTML")
    await asyncio.sleep(1.5)

    # 2. The Visual Countdown
    for i in range(5, 0, -1):
        await countdown_msg.edit_text(f"🛑 <b>SYSTEM BREACH:</b> Deleting wishes in {i}s...",parse_mode="HTML")
        await asyncio.sleep(1) # Wait 1 second between updates

    # 2. Fetch data to calculate the NEW integer balance
    user_data = await users_col.find_one({"user_id": user_id})
    current_wishes = user_data.get("wish_count", 0)
    
    if current_wishes <= 0:
        await countdown_msg.edit_text("💢 You have no wishes to lose. Consider yourself lucky.",parse_mode="HTML")
        return

    # Calculate half and use math.floor to remove decimals (e.g., 31 -> 15)
    new_wish_count = math.floor(current_wishes / 2)
    lost_wishes = current_wishes - new_wish_count

    # 3. Update database with the clean Integer
    await users_col.update_one(
        {"user_id": user_id},
        {"$set": {"wish_count": int(new_wish_count)}} # Force integer type
    )

    # 4. Final message to user
    await countdown_msg.edit_text(
        f"I said don't use this command! 😠\n\n"
        f"<b>Punishment:</b> You lost half of your wishes ({lost_wishes} 💫 gone).",parse_mode="HTML"
    )

    # 5. Notify Admin
    try:
        admin_alert = (
            f"💀 <b>Trap Triggered!</b>\n"
            f"👤 <b>User:</b> {user_name}\n"
            f"📉 <b>Lost:</b> {lost_wishes} wishes\n"
            f"💰 <b>New Balance:</b> {new_wish_count}"
        )
        await bot.send_message(chat_id=ADMIN_ID, text=admin_alert, parse_mode="HTML")
    except Exception as e:
        logging.error(f"Admin notification failed: {e}")
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
@dp.message(Command("abyssinfo"))
async def abyss_info_command(message: types.Message):
    user_data = await users_col.find_one({"user_id": str(message.from_user.id)})
    if not user_data or "genshin_uid" not in user_data:
        return await message.answer("❌ Please /login <uid> first.")

    uid = str(user_data["genshin_uid"]).strip()
    
    try:
        # Fetch fresh data from HoYolab
        abyss = await client.get_spiral_abyss(uid)
        
        # ✅ Added 'await' here to resolve the coroutine into a string
        formatted_text = await format_abyss_info(abyss)
        
        await message.reply(formatted_text)
        
    except Exception as e:
        # If the error is regarding privacy settings in HoYoLAB
        if "Stats are not public" in str(e):
            await message.reply("❌ Your Abyss stats are private. Please enable 'Public' in HoYoLAB settings.")
        else:
            await message.reply(f"❌ Error fetching Abyss data: {str(e)}")

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
            total_so_far = current_collection.get(current_display_name, 0) + pulled_chars.count(current_display_name)
            if total_so_far >= 7:
                wish_count += 1
                results.append(f"꩜ {current_display_name} (C6+ -> +1 Wish) (rare) ✨")
            else:
                pulled_chars.append(current_display_name)
                results.append(f"꩜ {current_display_name} (rare) ✨")

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
    if message.chat.type != "private":
        await message.reply("⚠️ <b>Single wishing is restricted to Private DMs only!</b>\nPlease message me directly to play.", parse_mode="HTML")
        return
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
    if message.chat.type != "private":
        await message.reply("⚠️ <b>Gambling is restricted to Private DMs only!</b>\nPlease message me directly to play.", parse_mode="HTML")
        return
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
    # Uses your global ADMIN_ID variable again
    if message.from_user.id != ADMIN_ID:
        await message.answer("🚫 **Access Denied**")
        return

    # 1. Extract the text and photo correctly
    raw_content = message.caption if message.photo else message.text
    
    # Remove the /broadcast command cleanly
    parts = raw_content.split(maxsplit=1)
    broadcast_text = parts[1] if len(parts) > 1 else ""
    
    photo_id = message.photo[-1].file_id if message.photo else None

    if not broadcast_text and not photo_id:
        await message.answer("❓ **Usage:**\n1. Send an image with caption `/broadcast [text]`\n2. Send just `/broadcast [text]`")
        return

    status_msg = await message.answer("⏳ **Broadcasting to all travelers...**")
    
    cursor = users_col.find({})
    success, fail = 0, 0

    async for user in cursor:
        try:
            target_id = user["user_id"]
            if photo_id:
                # Switched to HTML for better support of links and dots
                await bot.send_photo(
                    chat_id=target_id, 
                    photo=photo_id, 
                    caption=broadcast_text, 
                    parse_mode="HTML" 
                )
            else:
                await bot.send_message(
                    chat_id=target_id, 
                    text=broadcast_text, 
                    parse_mode="HTML"
                )
            
            success += 1
            await asyncio.sleep(0.05) # Prevent Telegram flood limits
            
        except Exception as e:
            logging.error(f"Failed to send to {user.get('user_id')}: {e}")
            fail += 1

    await status_msg.edit_text(
        f"✅ **Broadcast Complete**\n"
        f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        f"🟢 **Success:** {success}\n"
        f"🔴 **Failed:** {fail}"
    )
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
    await status_msg.edit_text(f"✅ <b>Login Successful! <code>{uid}</code></b>\n👤 <b>Player:</b> {player.get('name')} (AR {player.get('level')})", parse_mode="HTML")
@dp.message(Command("logout"))
async def logout_uid(message: types.Message):
    # 1. Check if the user even has a UID linked
    user_id = str(message.from_user.id)
    user_data = await users_col.find_one({"user_id": user_id})

    if not user_data or "genshin_uid" not in user_data:
        return await message.answer("ℹ️ You are not logged in yet.")

    # 2. Remove only the UID field using $unset
    # This keeps other data (like registration date) but removes the Genshin link
    await users_col.update_one(
        {"user_id": user_id},
        {"$unset": {"genshin_uid": ""}} 
    )

    await message.answer("✅ <b>Logout Successful!</b>\nYour UID has been unlinked from this account.", parse_mode="HTML")
# --- MyProfile Command ---
@dp.message(Command("myprofile"))
async def my_profile(message: types.Message):
    # 1. Get UID from MongoDB
    user_data = await users_col.find_one({"user_id": str(message.from_user.id)})
    if not user_data or "genshin_uid" not in user_data:
        return await message.answer("❌ Please /login <uid> first.")

    db_uid = str(user_data["genshin_uid"]).strip()
    
    # 2. Loading State
    status = await message.answer("🔄 <b>Creating Profile...</b>", parse_mode="HTML")
    
    # 3. Fetch Data (Exploration and Abyss functions assumed to be defined elsewhere)
    user_info = await get_player_full_data(db_uid)
    user_info_enka = await get_enkadata(db_uid)
    image_buffer = await create_genshin_profile(db_uid)    
    exploration_data = await get_exploration_data(db_uid)
    abyss_data = await get_abyss_data(db_uid)
    
    

    if not user_info:
        return await message.reply("❌ Data hidden. Is your 'Battle Chronicle' public in HoYoLAB?")

    msg = "<b>PLAYER INFO</b>\n"
    msg += "─────────୨ৎ─────────\n"
    msg += f"𖹭 <b>{user_info_enka['nickname']}</b> | UID: <code>{db_uid}</code>\n"
    msg += f"𖹭 <b>AR {user_info_enka['level']}</b> | WL : {user_info_enka['worldLevel']}\n"
    msg += f"𖹭 <b>Achievements:</b> {user_info_enka['achievements']}\n"
    msg+=f"𖹭 <b>Days:</b> {user_info_enka['days_active']}\n"
    if user_info_enka['signature']:
        msg += f"<i>\"{user_info_enka['signature']}\"</i>\n"
        
    msg += "────────────────────\n\n"

    # Exploration Section
    msg += "<b> EXPLORATION</b>\n"
    msg += "⊹ ࣪ ﹏﹏﹏﹏𓊝﹏𓂁﹏﹏﹏﹏⊹ ࣪ ˖\n\n"
    for area in exploration_data:
        # :15 ensures the percentages stay aligned in a column
        msg += f"❀ <code>{area['name']:15}</code>: {area['percent']}%\n"
    await status.delete()
    # Abyss Section
    if abyss_data:
        msg += f"\n<b>⚔︎ SPIRAL ABYSS</b>\n{abyss_data}"
    if image_buffer:
        # Create the file object from buffer
        photo = BufferedInputFile(image_buffer.getvalue(), filename=f"{db_uid}.png")
    # 5. Send final text message
        await message.answer_photo(
            photo=photo,
            caption=msg,
            parse_mode="HTML"
        )
        
        # 6. CRITICAL: Close the buffer to free RAM
        image_buffer.close()
    else:
        # Fallback if image generation fails
        await message.answer(msg, parse_mode="HTML")
from aiogram import types, F
from aiogram.utils.keyboard import InlineKeyboardBuilder

# 1. THE COMMAND HANDLER
@dp.message(F.text.startswith("/comparechar"))
async def cmd_compare(message: types.Message):
    if not message.reply_to_message:
        return await message.reply("Please reply to a user's message to compare characters.")
    
    sender_data = await users_col.find_one({"user_id": str(message.from_user.id)})
    target_data = await users_col.find_one({"user_id": str(message.reply_to_message.from_user.id)})

    if not sender_data or not target_data:
        return await message.reply("Both users must be registered.")

    u1, u2 = sender_data['genshin_uid'], target_data['genshin_uid']
    owner_id = message.from_user.id # The person who typed the command
    
    await show_comparison_menu(message, u1, u2, owner_id)
async def show_comparison_menu(event, u1, u2, owner_id, is_callback=False):
    """Helper function to show the character list (used by command and back button)"""
    
    # 1. Show a temporary "Fetching" state so the user knows it's working
    if is_callback:
        # If they clicked 'Back', just update the current button to show we are loading
        await event.answer("Refreshing common characters...")
    else:
        # If it's the first time (/comparechar), send a temp message
        temp_msg = await event.reply("Searching for common characters...")

    # 2. Fetch data
    d1, d2 = await asyncio.gather(get_enkadata(u1), get_enkadata(u2))
    
    ids1 = {str(c['avatarId']) for c in d1.get("showAvatarInfoList", [])}
    ids2 = {str(c['avatarId']) for c in d2.get("showAvatarInfoList", [])}
    common = ids1.intersection(ids2)

    # 3. Handle No Common Characters
    if not common:
        error_text = " No common characters found in your showcases!"
        if not is_callback: await temp_msg.delete() # Clean up temp message
        return await event.message.edit_text(error_text) if is_callback else await event.reply(error_text)

    # 4. Build the Menu
    builder = InlineKeyboardBuilder()
    with open('char.json', 'r') as f:
        char_map = json.load(f)

    for cid in list(common)[:18]: 
        name = char_map.get(str(cid), {}).get("name", f"ID: {cid}")
        builder.button(text=name, callback_data=f"comp:{u1}:{u2}:{cid}:{owner_id}")
    
    builder.adjust(3)
    text = "<b>Character Comparison</b>\nSelect a common character to compare stats:"
    
    # 5. The "Clean" Swap
    if is_callback:
        # Coming from the Result Card: Delete the card and send the fresh menu
        await event.message.delete()
        await event.message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    else:
        # Coming from the Command: Delete the "Searching..." message and send the menu
        await temp_msg.delete()
        await event.reply(text, reply_markup=builder.as_markup(), parse_mode="HTML")

@dp.callback_query(F.data.startswith("comp:"))
async def handle_comp(callback: types.CallbackQuery):
    data = callback.data.split(":")
    u1, u2, cid, owner_id = data[1], data[2], data[3], int(data[4])
    
    # 1. Security Check
    if callback.from_user.id != owner_id:
        return await callback.answer("⏳ This menu isn't for you!", show_alert=True)

    # 2. Handshake & Loading State
    await callback.answer() # Stops button spinner
    
    try:
        # Swap the menu image to a loading image
        await callback.message.edit_media(
            media=InputMediaPhoto(
                media=FSInputFile("asstests/loading.png"), # Use your loading image path
                caption="<b>Creating comparison card... Please wait.</b>",
                parse_mode="HTML"
            )
        )
    except Exception:
        # Fallback if image edit fails (e.g., if the user deleted the message)
        pass

    # 3. Generate the Image (Pillow logic)
    img_bytes = await compare_characters(int(u1), int(u2), int(cid))
    
    # 4. Prepare the Back Button
    back_builder = InlineKeyboardBuilder()
    back_builder.button(text="Back to List", callback_data=f"back_comp:{u1}:{u2}:{owner_id}")
    
    # 5. Clean up and Send Final Result
    # We delete the loading/menu message entirely to "remove all messages"
    await callback.message.delete()
    
    # Reply to the original command sender to keep it threaded
    target = callback.message.reply_to_message or callback.message
    await target.reply_photo(
        photo=types.BufferedInputFile(img_bytes.read(), filename="comparison.png"),
        caption=f"<b>Comparison Complete!</b>",
        reply_markup=back_builder.as_markup(),
        parse_mode="HTML"
    )
    

@dp.callback_query(F.data.startswith("back_comp:"))
async def handle_back_button(callback: types.CallbackQuery):
    _, u1, u2 = callback.data.split(":")
    await callback.answer("Returning to list...")
    
    # Re-use the menu helper
    await show_comparison_menu(callback, u1, u2, is_callback=True)
@dp.message(Command("compare"))
async def cmd_compare_reply(message: types.Message):
    if not message.reply_to_message:
        return await message.reply("Please <b>reply</b> to a message with <code>/compare</code>", parse_mode="HTML")

    sender_id = str(message.from_user.id)
    target_id = str(message.reply_to_message.from_user.id)
    
    sender_data = await users_col.find_one({"user_id": sender_id})
    target_data = await users_col.find_one({"user_id": target_id})

    if not sender_data or not target_data:
        return await message.reply("Both users must be /login-ed to compare.")

    # Show a "Loading" message so the user knows the image is being generated
    status_msg = await message.answer("Generating comparison showcase...")

    try:
        # 1. Generate the image buffer using your previous function
        # Using the genshin_uids stored in your database
        uid1 = sender_data['genshin_uid']
        uid2 = target_data['genshin_uid']
        
        photo_buffer = await create_masked_showcase(uid1, uid2)
        
        # 2. Wrap the buffer in an InputFile
        photo = BufferedInputFile(photo_buffer.read(), filename="compare.png")

        # 3. Create the keyboard
        uids = f"{uid1}_{uid2}"
        builder = InlineKeyboardBuilder()
        builder.row(types.InlineKeyboardButton(text="𓊝 Compare Exploration", callback_data=f"comp_expl_{uids}"))
        builder.row(types.InlineKeyboardButton(text="𖨆 Compare Profile Stats", callback_data=f"comp_prof_{uids}"))

        # 4. Send the photo with the menu as a caption
        await message.answer_photo(
            photo=photo,
            caption=f"⚔ <b>Comparison Menu</b>\nComparing with <b>{message.reply_to_message.from_user.first_name}</b>",
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
        
        # Delete the "Loading" message
        await status_msg.delete()

    except Exception as e:
        print(f"Error generating comparison: {e}")
        await status_msg.edit_text("❌ Failed to generate comparison image. Please ensure both showcases are public.")
# Helper to handle "N/A" or missing stats
def to_int(val):
    if val is None or str(val).strip().upper() == "N/A" or str(val).strip() == "":
        return 0
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return 0

@dp.callback_query(F.data.startswith("comp_prof_"))
async def execute_profile_comparison(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    my_uid, target_uid = parts[2], parts[3]
    await callback.answer("⚔ Comparing Profiles...")

    try:
        me = await get_player_full_data(my_uid)
        them = await get_player_full_data(target_uid)

        # Get AR and Calculate World Level
        my_ar = to_int(get_val(me, "level", "info"))
        them_ar = to_int(get_val(them, "level", "info"))
        
        my_wl = calculate_world_level(my_ar)
        them_wl = calculate_world_level(them_ar)

        msg = f"⚔ <b>PROFILE BATTLE</b>\n"
        msg += f"𖨆 <code>{me['nickname']}</code> <b>VS</b> 𖨆 <code>{them['nickname']}</code>\n"
        msg += "<code>" + "═" * 25 + "</code>\n\n"

        # Define stats to compare using your JSON keys
        stats_to_compare = [
            ("ᯓ Adventure Rank", my_ar, them_ar),
            ("ᯓ World Level", my_wl, them_wl),
            ("ᯓ Achievements", to_int(get_val(me, "achievements")), to_int(get_val(them, "achievements"))),
            ("ᯓ Days Active", to_int(get_val(me, "days_active")), to_int(get_val(them, "days_active")))
        ]

        for label, v1, v2 in stats_to_compare:
            icon = "←--" if v1 > v2 else "--→" if v2 > v1 else "-𔓘-"
            msg += f"<b>{label}:</b>\n<code>{v1:>5}</code> {icon} <code>{v2:>5}</code>\n\n"

        builder = InlineKeyboardBuilder()
        builder.row(types.InlineKeyboardButton(text="◀ Back", callback_data=f"back_comp_{my_uid}_{target_uid}"))
        await callback.message.edit_text(msg, reply_markup=builder.as_markup(), parse_mode="HTML")

    except Exception as e:
        await callback.message.edit_text(f"❌ Profile Error: {e}")

@dp.callback_query(F.data.startswith("comp_expl_"))
async def execute_exploration_comparison(callback: types.CallbackQuery):
    # 1. Extract UIDs from callback data
    parts = callback.data.split("_")
    my_uid, target_uid = parts[2], parts[3]
    await callback.answer("⚔ Comparing World Progress...")

    try:
        # 2. Fetch data for both players
        me = await get_player_full_data(my_uid)
        them = await get_player_full_data(target_uid)
        
        # We need the raw lists for the region comparison
        me_expl = await get_exploration_data(my_uid)
        them_expl = await get_exploration_data(target_uid)

        # 3. Header
        msg = f"⚔ <b>EXPLORATION BATTLE</b>\n"
        msg += f"𖨆 <code>{me['nickname']}</code> <b>VS</b> 𖨆 <code>{them['nickname']}</code>\n"
        msg += "<code>" + "═" * 25 + "</code>\n\n"

        # 4. Chest Section (Using the keys from your JSON)
        msg += "<b>⌗ CHEST COUNTS</b>\n"
        chest_types = [
            ("Luxurious", "luxurious"),
            ("Precious", "precious"),
            ("Exquisite", "exquisite"),
            ("Common", "common")
        ]

        for label, key in chest_types:
            v1 = me[key]
            v2 = them[key]
            icon = "←--" if v1 > v2 else "--→" if v2 > v1 else "-𔓘-"
            msg += f"{label}: <code>{v1}</code> {icon} <code>{v2}</code>\n"

        msg += "\n<code>" + "─" * 25 + "</code>\n"

        # 5. Regional Exploration Section
        msg += "<b>☀︎ REGIONS</b>\n"
        
        them_map = {area['name']: area['percent'] for area in them_expl}

        for area in me_expl:
            name = area['name']
            p1 = area['percent']
            p2 = them_map.get(name, 0.0)
            
            icon = "←--" if p1 > p2 else "--→" if p2 > p1 else "-𔓘-"
            
            msg += f"❀ <b>{name}</b>\n"
            msg += f"<code>{p1:>5.1f}%</code> {icon} <code>{p2:>5.1f}%</code>\n\n"

        # 6. Navigation
        builder = InlineKeyboardBuilder()
        builder.row(types.InlineKeyboardButton(text="◀ Back", callback_data=f"back_comp_{my_uid}_{target_uid}"))
        
        await callback.message.edit_text(msg, reply_markup=builder.as_markup(), parse_mode="HTML")

    except Exception as e:
        await callback.message.edit_text(f"❌ Comparison Error: {e}")
@dp.callback_query(F.data.startswith("back_comp_"))
async def back_to_compare_prep(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    my_uid, target_uid = parts[2], parts[3]
    
    # Rebuild the menu with BOTH buttons, just like the original command
    builder = InlineKeyboardBuilder()
    uids = f"{my_uid}_{target_uid}"
    builder.row(types.InlineKeyboardButton(text="𓊝 Compare Exploration", callback_data=f"comp_expl_{uids}"))
    builder.row(types.InlineKeyboardButton(text="𖨆 Compare Profile Stats", callback_data=f"comp_prof_{uids}"))

    await callback.message.edit_text(
        "⚔️ <b>Comparison Menu</b>\nChoose what to compare:",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await callback.answer()
async def clear_old_polls():
    """Removes crashed or forgotten polls from memory every hour"""
    while True:
        await asyncio.sleep(3600)
        current_time = time.time()
        # Create a static list of keys to avoid 'dictionary size changed' error
        to_delete = [pid for pid, d in active_polls.items() if current_time - d["start_time"] > 3600]
        for pid in to_delete:
            if pid in active_polls:
                del active_polls[pid]

# --- QUIZ TRIGGER ---
@dp.message(F.chat.type.in_({"group", "supergroup"}))
async def group_quiz_handler(message: types.Message, bot: Bot):
    chat_id = message.chat.id

    # 2. Increment counter for this specific chat in MongoDB
    # This replaces your local 'group_message_counts' dictionary
    res = await groups_col.find_one_and_update(
        {"chat_id": chat_id},
        {"$inc": {"message_count": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER
    )
    current_count = res.get("message_count", 0)

    # 3. Check if we reached the threshold
    if current_count >= QUIZ_THRESHOLD:
        # Reset counter in MongoDB immediately to prevent double-triggers
        await groups_col.update_one(
            {"chat_id": chat_id}, 
            {"$set": {"message_count": 0}}
        )
        
        try:
            # --- YOUR EXISTING QUIZ LOGIC STARTS HERE ---
            with open("quizzes.json", "r") as f:
                quiz_list = json.load(f)
            
            q = random.choice(quiz_list)
            options = random.sample(q["wrong_pool"], 3) + [q["correct"]]
            random.shuffle(options)
            
            correct_id = options.index(q["correct"])

            poll_msg = await message.answer_poll(
                question=f"𑣿 QUIZ ({q['difficulty'].upper()})\n{q['question']}",
                options=options,
                type='quiz',
                correct_option_id=correct_id,
                is_anonymous=False,
                open_period=60,
                is_closed=False
            )

            poll_id = poll_msg.poll.id
            active_polls[poll_id] = {
                "start_time": time.time(),
                "difficulty": q["difficulty"],
                "correct_id": correct_id,
                "chat_id": chat_id,
                "message_id": poll_msg.message_id,
                "winners": []
            }

            await asyncio.sleep(61)

            if poll_id in active_polls:
                data = active_polls[poll_id]
                if data["winners"]:
                    winner_list = "\n".join([f"⛧ {name} solved it! (<b>+{pts} pts + wishes </b>)" for name, pts in data["winners"]])
                    result_text = f"၄၃ <b>Quiz Results:</b>\n\n{winner_list}"
                else:
                    result_text = "၄၃ Time's up! No one got it right. ၄၃"

                await bot.send_message(
                    chat_id=data["chat_id"],
                    text=result_text,
                    reply_to_message_id=data["message_id"],
                    parse_mode="HTML"
                )
                del active_polls[poll_id]
            # --- END OF QUIZ LOGIC ---

        except Exception as e:
            print(f"Quiz Error: {e}")

# --- POLL ANSWER HANDLER ---
@dp.poll_answer()
async def handle_poll_answer(poll_answer: types.PollAnswer):
    poll_id = poll_answer.poll_id
    
    # 1. Check if the poll is managed by the bot
    if poll_id not in active_polls:
        return

    data = active_polls[poll_id]
    
    # 2. Check if the user's answer is correct
    # poll_answer.option_ids is a list; we check the first (and usually only) selection
    if poll_answer.option_ids[0] == data["correct_id"]:
        elapsed = time.time() - data["start_time"]
        
        # Calculate points based on your custom logic
        points = get_quiz_score(data["difficulty"], elapsed)
        
        user_id = str(poll_answer.user.id)
        user_name = poll_answer.user.full_name
        
        # FIX: Ensure chat_id is a STRING to prevent overwriting or key errors in Mongo
        chat_id = str(data["chat_id"]) 

        # 3. Update the Database
        # Using $inc with dot notation (group_quiz.ID) ensures we ADD to the specific group
        # without affecting other groups saved in the object.
        await users_col.update_one(
            {"user_id": user_id},
            {
                "$inc": {
                    f"group_quiz.{chat_id}": points, # Increments score for THIS specific group
                    "wish_count": points,            # Increments global currency
                    "quiz_points": 1                 # Optional: Track total correct answers
                },
                "$set": {
                    "last_known_name": user_name     # Keeps the username updated
                }
            },
            upsert=True # Creates the document if the user is new
        )
        
        # 4. Update the local tracking for this specific poll instance
        if "winners" not in data:
            data["winners"] = []
        data["winners"].append((user_name, points))

        print(f"✅ Saved {points} pts for {user_name} in group {chat_id}")
# --- LEADERBOARD COMMAND ---
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
    asyncio.create_task(clear_old_polls())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())








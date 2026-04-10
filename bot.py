import asyncio
import genshin
from motor.motor_asyncio import AsyncIOMotorClient
import logging
import math
import sys
import random
import calendar
import io
import aiohttp
from character_card import characters_card
from datetime import datetime
from aiogram.exceptions import TelegramBadRequest
from pymongo import ReturnDocument
from dotenv import load_dotenv
import os
import json
import html
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
from aiogram.filters import Command ,CommandObject
from pytz import timezone
from wishing import combine_images
from create_profile import create_genshin_profile
from genshin_utils import  get_enkadata,get_quiz_score,to_int,get_val,get_exploration_data,get_abyss_data,get_player_full_data,calculate_world_level,format_abyss_info
from data import weapons3, characters4, characters5, rare,TEAMS_DB  
from cryptography.fernet import Fernet
from tasks import setup_scheduler
from paimon import fetch_and_save_wishes, calculate_pity
from banner import get_banner_text, CURRENT_IMAGES, NEXT_IMAGES

quiz_track = {}
group_message_counts = {}
QUIZ_THRESHOLD = 40
COOKIES = {
    "ltuid_v2": "449108883",
    "ltoken_v2": "v2_CAISDGM5b3FhcTNzM2d1OBokNDcwMGJhYzAtMTAxZi00YjRlLTk2YmItN2M4YjhjMjMxZDAwIPWn780GKOuk4-0HMJO3k9YBQgtiYnNfb3ZlcnNlYVhqagJTRw.9dO7aQAAAAAB.MEUCIA5OHCjpxUDGrSJ8AQVHNuK4nwpW7XdJhtZhYnXcMhiFAiEAn0azB_VtrCvO57QPc72lKVKK_lTyMHAjDM2LrvENUco"
}
client = genshin.Client(COOKIES)
client.region = genshin.Region.OVERSEAS
ITEMS_PER_PAGE = 10
dp = Dispatcher()

load_dotenv()
KEY = os.getenv("ENCRYPTION_KEY").encode()
cipher = Fernet(KEY)
TOKEN = os.getenv("BOT_TOKEN")
MONGO_URL = os.getenv("MONGO_URL")
ADMIN_VAL = os.getenv("ADMIN_ID")


ADMIN_ID = int(ADMIN_VAL)

cluster = AsyncIOMotorClient(MONGO_URL)
db = cluster["genshin_bot"]
users_col = db["user_stats"]
wish_col = db["user_wishes"]

# Add this line near the top of your file, outside of any functions
active_polls = {}
# ---------------- Dictionaries ----------------
BANNER_NAMES = {
    301: "Character Event",
    400: "Character Event 2",
    302: "Weapon Event",
    200: "Standard"
}

CURRENT_RATE_UP_KEY = "flins" 
CURRENT_RATE_UP_NAME = characters5.get(CURRENT_RATE_UP_KEY, "Flins")

try:
    with open('char.json', 'r') as file:
        CHARACTER_MAP = json.load(file)
except Exception as e:
    print(f"Error loading char.json: {e}")
    CHARACTER_MAP = {}
def get_banner_keyboard(mode="current", char_index=0):
    builder = InlineKeyboardBuilder()
    
    # Button 1: Switch between Character 1 and Character 2
    next_char = 1 if char_index == 0 else 0
    char_label = "View 2nd Character" if char_index == 0 else "View 1st Character"
    builder.row(types.InlineKeyboardButton(text=char_label, callback_data=f"swap:{mode}:{next_char}"))
    
    # Button 2: Switch between Current and Next Banner sets
    other_mode = "next" if mode == "current" else "current"
    mode_label = "Upcoming Banners" if mode == "current" else "Current Banners"
    builder.row(types.InlineKeyboardButton(text=mode_label, callback_data=f"swap:{other_mode}:0"))
    
    return builder.as_markup()

@dp.message(Command("banner"))
async def cmd_banner(message: types.Message):
    # Initial state: Current Banner, 1st Character
    if not os.path.exists(CURRENT_IMAGES[0]):
        return await message.reply("❌ Banner image not found on server.")

    await message.reply_photo(
        photo=FSInputFile(CURRENT_IMAGES[0]),
        caption=get_banner_text("current"),
        reply_markup=get_banner_keyboard("current", 0),
        parse_mode="HTML"
    )

@dp.callback_query(F.data.startswith("swap:"))
async def handle_banner_swap(callback: types.CallbackQuery):
    # Data: swap:MODE:INDEX
    _, mode, index = callback.data.split(":")
    index = int(index)
    
    # Select the correct image list
    image_list = CURRENT_IMAGES if mode == "current" else NEXT_IMAGES
    
    if not os.path.exists(image_list[index]):
        return await callback.answer("❌ Image file missing!", show_alert=True)

    # Edit the existing message's photo and caption
    await callback.message.edit_media(
        media=InputMediaPhoto(
            media=FSInputFile(image_list[index]),
            caption=get_banner_text(mode),
            parse_mode="HTML"
        ),
        reply_markup=get_banner_keyboard(mode, index)
    )
    await callback.answer()
@dp.message(Command("teams"))
async def cmd_teams_menu(message: types.Message):
    Allowed_group = -1001756907542
    if message.chat.id == Allowed_group:
        return await message.reply("This command is restricted in this group.")
    print(f"DEBUG: Command /teams triggered by {message.from_user.id}")
    print(f"DEBUG: TEAMS_DB contains: {list(TEAMS_DB.keys())}")
    builder = InlineKeyboardBuilder()
    
    # Create a button for every character in our DB
    for char in TEAMS_DB.keys():
        builder.button(
            text=char.title(), 
            callback_data=f"selectchar:{char}"
        )
    
    builder.adjust(3)
    
    await message.reply(
        "<b>Genshin Team Compendium</b>\nSelect a character to see their best builds:",
        reply_markup=builder.as_markup(),parse_mode="HTML"
    )
@dp.callback_query(F.data.startswith("selectchar:"))
async def process_char_selection(callback: types.CallbackQuery):
    char_name = callback.data.split(":")[1]
    
    builder = InlineKeyboardBuilder()
    for team_type in TEAMS_DB[char_name].keys():
        builder.button(
            text=f"{team_type.upper()}", 
            callback_data=f"showteam:{char_name}:{team_type}"
        )
    
    # --- FIX 1: Change to 1 button per row ---
    builder.adjust(1) 
    
    # Add a "Back" button to return to the character list
    builder.row(types.InlineKeyboardButton(text="Back", callback_data="back_to_chars"))

    await callback.message.edit_text(
        text=f"Selected: <b>{char_name.title()}</b>\nWhich team type would you like to see?",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("showteam:"))
async def display_team_image(callback: types.CallbackQuery):
    _, char, team_type = callback.data.split(":")
    image_path = TEAMS_DB[char][team_type]
    
    photo = FSInputFile(image_path)
    
    # Send the photo
    await callback.message.answer_photo(
        photo=photo,
        caption=f"<b>{char.title()} - {team_type.upper()} Build</b>\n<b>Credits: </b>\n@tokii_ink (Instagram)\n@FlipMeAC(Twitter)",
        parse_mode="HTML"
    )

    # --- FIX 2: Delete the selection menu after sending the image ---
    await callback.message.delete() 
    await callback.answer()
@dp.callback_query(F.data == "back_to_chars")
async def back_to_main(callback: types.CallbackQuery):
    builder = InlineKeyboardBuilder()
    for char in TEAMS_DB.keys():
        builder.button(text=char.title(), callback_data=f"selectchar:{char}")
    builder.adjust(3)
    
    await callback.message.edit_text(
        text="<b>Genshin Team Compendium</b>\nSelect a character to see their best builds:",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await callback.answer()
def encrypt_cookies(ltuid, ltoken):
    data = json.dumps({"ltuid": ltuid, "ltoken": ltoken}).encode()
    return cipher.encrypt(data).decode()

def decrypt_cookies(encrypted_str):
    decrypted_data = cipher.decrypt(encrypted_str.encode()).decode()
    return json.loads(decrypted_data)
if not TOKEN or not MONGO_URL or not ADMIN_VAL:
    print("ERROR: Missing environment variables in .env file!")
    sys.exit(1)

@dp.message(Command("cookie_login"))
async def cmd_cookie_login(message: types.Message, command: CommandObject):
    if message.chat.type != "private":
        return await message.reply("❌ <b>Private DMs only!</b>", parse_mode="HTML")

    if not command.args or len(command.args.split()) < 2:
        return await message.reply(
            "<b>Usage:</b>\n<code>/cookie_login [ltuid_v2] [ltoken_v2]</code>\n"
            "<b>Use /cookiehelp for tutorial </b>",
            parse_mode="HTML"
        )

    args = command.args.split()
    
    # Construct the dictionary based on how many args were provided
    cookie_dict = {
        "ltuid_v2": args[0],
        "ltoken_v2": args[1]
    }
    
    # If they provided the third token, add it to the dict
    if len(args) >= 3:
        cookie_dict["cookie_token_v2"] = args[2]

    # Setup validation client
    check_client = genshin.Client(cookie_dict)
    check_client.region = genshin.Region.OVERSEAS
    
    try:
        # 1. Validate tokens are working
        await check_client.get_reward_info(game=genshin.Game.GENSHIN) 
        
        # 2. Get Account Info
        all_accounts = await check_client.get_game_accounts()
        genshin_acc = next((acc for acc in all_accounts if acc.game == genshin.Game.GENSHIN), None)
        
        if not genshin_acc:
            return await message.reply("❌ <b>Error:</b> No Genshin accounts found.")

        # 3. Encrypt the FULL dictionary (Saving all 3 tokens)
        encrypted_str = cipher.encrypt(json.dumps(cookie_dict).encode()).decode()
        
        # 4. Save to MongoDB
        await users_col.update_one(
            {"user_id": str(message.from_user.id)},
            {"$set": {
                "hoyolab_data": encrypted_str,
                "genshin_uid": genshin_acc.uid,
                "nickname": genshin_acc.nickname,
                "updated_at": datetime.utcnow()
            }},
            upsert=True
        )
        
        status_msg = "all 3 tokens" if "cookie_token_v2" in cookie_dict else "2 tokens"
        await message.reply(
            f"<b>Success!</b> Logged in as <b>{genshin_acc.nickname}</b>.\n"
            f"Saved <b>{status_msg}</b> securely.", 
            parse_mode="HTML"
        )

    except genshin.InvalidCookies:
        await message.reply("❌ <b>Error:</b> Tokens are invalid or expired.", parse_mode="HTML")
    except Exception as e:
        await message.reply(f"❌ <b>Validation Failed:</b> <code>{str(e)}</code>", parse_mode="HTML")
@dp.message(Command("wishes"))
async def cmd_wishes(message: types.Message):
    user_id = str(message.from_user.id)
    
    # Group 301 and 400 as they share pity in Genshin Impact
    char = await calculate_pity(user_id, [301, 400], wish_col)
    weapon = await calculate_pity(user_id, [302], wish_col)
    std = await calculate_pity(user_id, [200], wish_col)

    if char['total'] == 0 and std['total'] == 0 and weapon['total'] == 0:
        return await message.reply("📭 <b>No data found!</b> Use /import_wishes first.", parse_mode="HTML")

    # Helper for 5-star history formatting
    def fmt_hist(history):
        if not history: return "<i>No 5✮ history</i>"
        return "\n".join([f"• {h['name']} [<b>{h['pulls']}</b>]" for h in history])

    # Standard "Last 10" text for the top
    history_text = "\n".join([f"• {name}" for name in char['last_10']]) if char['last_10'] else "<i>No history found</i>"

    response = (
        "<b>LIFETIME WISH TRACKER</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        
        "<b>Last 10 Limited Pulls:</b>\n"
        f"{history_text}\n"
        "━━━━━━━━━━━━━━━━━━\n\n"

        "<b>Character Banner</b>\n"
        f"├ Total Pulls: <b>{char['total']}</b>\n"
        f"├ 5✮ Pity: <b>{char['pity_5']}</b>\n"
        f"├ 4✮ Pity: <b>{char['pity_4']}</b>\n"
        f"└ <b>Recent 5✮:</b>\n{fmt_hist(char['five_star_history'])}\n\n"
        
        "<b>Weapon Banner</b>\n"
        f"├ Total Pulls: <b>{weapon['total']}</b>\n"
        f"├ 5✮ Pity: <b>{weapon['pity_5']}</b>\n"
        f"├ 4✮ Pity: <b>{weapon['pity_4']}</b>\n"
        f"└ <b>Recent 5✮:</b>\n{fmt_hist(weapon['five_star_history'])}\n\n"
        
        "<b>Standard Banner</b>\n"
        f"├ Total Pulls: <b>{std['total']}</b>\n"
        f"├ 5✮ Pity: <b>{std['pity_5']}</b>\n"
        f"└ <b>Recent 5✮:</b>\n{fmt_hist(std['five_star_history'])}\n\n"

        "<b>Use /import_wishes to update data</b>"
    )

    await message.reply(response, parse_mode="HTML")

@dp.message(Command("import_wishes"))
async def cmd_import_wishes(message: types.Message, command: CommandObject):
    if not command.args:
        instruction_text = (
            "❓ <b>How to Import Your Wishes</b>\n\n"
            "1️⃣ Open <b>Genshin Impact</b> and go to your <b>Wish History</b> page.\n"
            "2️⃣ Wait for the history to load completely.\n"
            "3️⃣ Minimize the game, open <b>Windows PowerShell</b>.\n"
            "4️⃣ Copy/Paste the code below into PowerShell and press <b>Enter</b>:\n\n"
            "<pre>Set-ExecutionPolicy Bypass -Scope Process -Force; [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; iex \"&{$((New-Object System.Net.WebClient).DownloadString('https://gist.github.com/MadeBaruna/1d75c1d37d19eca71591ec8a31178235/raw/getlink.ps1'))} global\"</pre>\n\n"
            "5️⃣ The script will copy a URL to your clipboard. Paste it here like this:\n"
            "<code>/import_wishes [PASTE_URL_HERE]</code>"
        )
        return await message.reply(instruction_text, parse_mode="HTML") # Added 'return' here

    user_id = str(message.from_user.id)
    raw_url = command.args.strip()
    
    # 1. Extract the Authkey
    try:
        authkey = genshin.utility.extract_authkey(raw_url)
    except Exception:
        return await message.reply("<b>Error:</b> That doesn't look like a valid Wish History URL.", parse_mode="HTML")

    status_msg = await message.reply("<b>Syncing lifetime wishes...</b>\nThis can take 30-60 seconds or more than that depends how much pulls", parse_mode="HTML")

    # 2. Setup Client
    client = genshin.Client()
    client.game = genshin.Game.GENSHIN
    client.set_authkey(authkey)
    client.region = genshin.Region.OVERSEAS

    # Note: Using new_count to track actual inserts
    new_count = 0
    total_found = 0

    try:
        # 3. Loop through all relevant banners
        for banner in [301, 400, 302, 200]:
            async for wish in client.wish_history(banner):
                total_found += 1
                
                # 4. Save to DB (Upsert)
                result = await wish_col.update_one(
                    {"id": wish.id}, 
                    {"$set": {
                        "user_id": user_id,
                        "uid": wish.uid,
                        "name": wish.name,
                        "rarity": wish.rarity,
                        "type": wish.type,
                        "banner_type": wish.banner_type,
                        "time": wish.time
                    }},
                    upsert=True
                )
                
                if result.upserted_id:
                    new_count += 1

        await status_msg.edit_text(
            f"<b>Sync Complete!</b> ✅ \n\n"
            f"Total in Database: <b>{total_found}</b>\n"
            f"New wishes added: <b>{new_count}</b>", # Fixed variable name here to new_count
            parse_mode="HTML"
        )

    except genshin.AuthkeyException:
        await status_msg.edit_text("<b>Error:</b> Your Authkey has expired. Please generate a new one in-game.", parse_mode="HTML")
    except Exception as e:
        await status_msg.edit_text(f"<b>Bot Error:</b> <code>{str(e)}</code>", parse_mode="HTML")
def get_diary_markup(viewing_month: int):
    builder = InlineKeyboardBuilder()
    
    actual_month = datetime.now().month
    
    allowed_months = []
    for i in range(3):
        m = actual_month - i
        if m <= 0: m += 12
        allowed_months.append(m)
    
    prev_month = viewing_month - 1 if viewing_month > 1 else 12
    
    # 4. Loop Logic: If the next "previous" isn't allowed, jump to the actual current month
    if prev_month not in allowed_months:
        btn_text = f"Back to {calendar.month_name[actual_month]}"
        btn_data = "diary_view_current"
    else:
        btn_text = f"{calendar.month_name[prev_month]}"
        btn_data = f"diary_view_{prev_month}"

    builder.row(types.InlineKeyboardButton(text=btn_text, callback_data=btn_data))
    
    # Optional: Always keep a "Home" button if not on the current month
    if viewing_month != actual_month:
        builder.row(types.InlineKeyboardButton(text="Current Month", callback_data="diary_view_current"))
    
    return builder.as_markup()
def format_diary_report(diary: genshin.models.Diary) -> str:
    perc = diary.data.primogems_rate
    trend_emoji = "📈" if perc >= 0 else "📉"
    trend_text = "more" if perc >= 0 else "less"

    sources = ""
    for cat in diary.data.categories:
        sources += f"• {cat.name}: <b>{cat.percentage}%</b>\n"
    month_name = calendar.month_name[diary.month]
    return (
        f"<b>⋆˙⟡Traveler's Diary: {month_name}⟡˙⋆</b>\n"
        "─────── ୨୧ ───────\n"
        f"⚡︎ Primogems: <b>{diary.data.current_primogems}</b>\n"
        f"⚡︎ Mora: <b>{diary.data.current_mora}</b>\n\n"
        
        f"{trend_emoji} <b>Monthly Change:</b>\n"
        f"You got <b>{abs(perc)}%</b> {trend_text} than last month.\n\n"
        
        f"<b>Source Breakdown:</b>\n"
        f"{sources}"
        "─────── ୨୧ ───────"
    )

async def get_diary_client(user_id: str):
    """Helper to decrypt cookies and return a genshin Client."""
    user = await users_col.find_one({"user_id": str(user_id)})
    if not user or "hoyolab_data" not in user:
        return None
    
    # Use your exact resin decryption logic
    decrypted_data = cipher.decrypt(user["hoyolab_data"].encode()).decode()
    cookies = json.loads(decrypted_data)
    
    client = genshin.Client(cookies)
    client.region = genshin.Region.OVERSEAS
    return client

@dp.message(Command("diary"))
async def cmd_diary(message: types.Message):
    client = await get_diary_client(message.from_user.id)
    
    if not client:
        return await message.reply("<b>Not Logged In!</b>\nUse /cookie_login first.", parse_mode="HTML")

    status_msg = await message.reply("<b>Opening Diary...</b>", parse_mode="HTML")

    try:
        diary = await client.get_genshin_diary()
        await status_msg.edit_text(
            format_diary_report(diary),
            reply_markup=get_diary_markup(diary.month),
            parse_mode="HTML"
        )
    except Exception as e:
        await status_msg.edit_text(f"<b>Error:</b> <code>{html.escape(str(e))}</code>", parse_mode="HTML")

@dp.callback_query(F.data.startswith("diary_view_"))
async def handle_diary_pagination(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    data_parts = callback.data.split("_")
    month_val = None if data_parts[-1] == "current" else int(data_parts[-1])
    
    await callback.answer("Updating Diary...")
    client = await get_diary_client(user_id)

    try:
        diary = await client.get_genshin_diary(month=month_val)
        new_text = format_diary_report(diary)
        new_markup = get_diary_markup(diary.month)
        
        await callback.message.edit_text(
            new_text, 
            parse_mode="HTML", 
            reply_markup=new_markup
        )
        
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            return 
        raise e
        
@dp.message(Command("dailylogin"))
async def cmd_daily_login(message: types.Message):
    user = await users_col.find_one({"user_id": str(message.from_user.id)})
    
    if not user or "hoyolab_data" not in user:
        return await message.reply("<b>Not Logged In!</b>\nUse /cookie_login first.", parse_mode="HTML")

    try:
        # Decrypt the full cookie dictionary
        decrypted_data = cipher.decrypt(user["hoyolab_data"].encode()).decode()
        cookies = json.loads(decrypted_data)
        
        client = genshin.Client(cookies)
        client.region = genshin.Region.OVERSEAS
        

        reward = await client.claim_daily_reward(game=genshin.Game.GENSHIN)
        
        safe_name = html.escape(message.from_user.full_name)
        await message.reply(
            f"<b>Daily Reward Claimed!</b>\n"
            f"User: <b>{safe_name}</b>\n"
            f"Reward: <b>{reward.amount}x {reward.name}</b>",
            parse_mode="HTML"
        )
        
    except genshin.AlreadyClaimed:
        await message.reply("<b>Already Done:</b> You've already claimed your reward today!", parse_mode="HTML")
    except genshin.InvalidCookies:
        await message.reply("<b>Expired:</b> Your cookies have expired. Please login again.", parse_mode="HTML")
    except Exception as e:
        await message.reply(f"<b>Error:</b> <code>{html.escape(str(e))}</code>", parse_mode="HTML")
def get_guide_keyboard(step: int):
    builder = InlineKeyboardBuilder()
    
    # Navigation buttons
    if step > 1:
        builder.button(text="Back", callback_data=f"cookie_guide:{step-1}")
    
    if step < 5: # Total steps
        builder.button(text="Next", callback_data=f"cookie_guide:{step+1}")
    else:
        builder.button(text="Done", callback_data="cookie_guide:close")
    
    builder.adjust(2)
    return builder.as_markup()

# --- Content for each step ---
GUIDE_TEXTS = {
    1: "<b>Step 1: Login to HoYoLAB</b>\n\nOpen your browser and login to <a href='https://www.hoyolab.com'>hoyolab.com</a>. Make sure you are on the home page.",
    2: "<b>Step 2: Open Developer Tools</b>\n\nPress <code>Ctrl + Shift + I</code> (or <code>F12</code>) to open the Inspect panel. Click on the (1) aplication tab on top, then on the left side under (2)<code>Cookies</code>, click on Cookies and select the one under it.",
    3: "<b>Step 3: Scroll down and search for <code>ltuid_v2</code> and <code>ltoken_v2</code> values.</b>",
    4: "<b>Step 4: Click on the value and copy it</b>",
    5: "<b>Once you have both values, use the command:\n<code>/cookie_login [ltuid_v2] [ltoken_v2]</code>\n\nExample:\n<code>/cookie_login 123456789 v2_abcdefg...</code></b>"
}

GUIDE_IMAGES = {
    1: "images/tutorial/tutorial1.jpg", # Path to your local images
    2: "images/tutorial/tutorial2.jpg",
    3: "images/tutorial/tutorial3.jpg",
    4: "images/tutorial/tutorial4.jpg",
    5: "images/tutorial/tutorial5.jpg"
}
# 1. Start the guide
@dp.message(Command("cookiehelp"))
async def cmd_cookiehelp(message: types.Message):
    # Check if it's a Private Chat (DM)
    if message.chat.type != "private":
        return await message.reply("This command only works in Private DMs to protect your privacy.")

    photo = FSInputFile(GUIDE_IMAGES[1])
    await message.reply_photo(
        photo=photo,
        caption=GUIDE_TEXTS[1],
        reply_markup=get_guide_keyboard(1),
        parse_mode="HTML"
    )

# 2. Handle Button Clicks
@dp.callback_query(F.data.startswith("cookie_guide:"))
async def handle_guide_navigation(callback: types.CallbackQuery):
    step = callback.data.split(":")[1]
    
    if step == "close":
        await callback.message.delete()
        return await callback.answer("Guide closed.")

    step = int(step)
    
    # Update the photo and caption
    new_photo = InputMediaPhoto(
        media=FSInputFile(GUIDE_IMAGES[step]),
        caption=GUIDE_TEXTS[step],
        parse_mode="HTML"
    )
    
    await callback.message.edit_media(
        media=new_photo,
        reply_markup=get_guide_keyboard(step)
    )
    await callback.answer()
@dp.message(Command("resin"))
async def cmd_resin(message: types.Message):
    user = await users_col.find_one({"user_id": str(message.from_user.id)})
    
    if not user or "hoyolab_data" not in user:
        return await message.reply("<b>Not Logged In!</b>\nUse /cookie_login first.", parse_mode="HTML")

    try:
        # 1. Decrypt the cookie dictionary
        decrypted_data = cipher.decrypt(user["hoyolab_data"].encode()).decode()
        cookies = json.loads(decrypted_data)
        
        # 2. Setup client
        client = genshin.Client(cookies)
        client.region = genshin.Region.OVERSEAS
        
        # 3. Fetch Real-Time Notes
        # Note: The user's Hoyolab profile MUST have "Real-time Notes" set to public in privacy settings
        notes = await client.get_genshin_notes()
        
        # 4. Format the response
        response = (
            f"<b>Current Resin:</b> {notes.current_resin}/{notes.max_resin}\n"
        )
        
        if notes.current_resin < notes.max_resin:
            # notes.remaining_resin_recovery_time is a timedelta object
            recovery_time = notes.remaining_resin_recovery_time
            response += f"<b>Full Recovery:</b> {recovery_time}\n"
        else:
            response += "<b>Your Resin is full!</b>\n"

        # Optional: Add extra info like Realm Currency or Dailies
        response += f"\n<b>Daily Commissions:</b> {notes.completed_commissions}/{notes.max_commissions}"
        
        await message.reply(response, parse_mode="HTML")
        
    except genshin.InvalidCookies:
        await message.reply("<b>Expired:</b> Your cookies have expired. Please login again.", parse_mode="HTML")
    except genshin.DataNotPublic:
        await message.reply(
            "<b>Error:</b> Your Real-Time Notes are private.\n\n"
            "Go to HoYoLAB -> Settings -> Privacy Settings -> Enable 'Real-time Notes'.", 
            parse_mode="HTML"
        )
    except Exception as e:
        await message.reply(f"<b>Error:</b> <code>{html.escape(str(e))}</code>", parse_mode="HTML")

@dp.message(Command("redeem"))
async def cmd_redeem_code(message: types.Message, command: CommandObject):
    if not command.args:
        return await message.reply("❓ <b>Usage:</b> <code>/redeem [CODE]</code>", parse_mode="HTML")

    promo_code = command.args.strip()
    user_id = str(message.from_user.id)
    user = await users_col.find_one({"user_id": user_id})
    
    if not user or "hoyolab_data" not in user:
        return await message.reply("🚫 <b>Not Logged In!</b> Use <code>/cookie_login</code> first.")

    try:
        # 1. Decrypt Cookies
        decrypted_data = cipher.decrypt(user["hoyolab_data"].encode()).decode()
        cookies = json.loads(decrypted_data)
        print(f"DEBUG: Tokens found for user {user_id}: {list(cookies.keys())}")
        # 2. Setup Client
        client = genshin.Client() # Start clean
        client.set_cookies(cookies) # This correctly maps all tokens (ltoken, ltuid, cookie_token)
        client.region = genshin.Region.OVERSEAS

        # 3. Explicitly Fetch the UID to bind the session
        # This acts as the 'handshake' that confirms your login status
        accounts = await client.get_game_accounts()
        genshin_acc = next((acc for acc in accounts if acc.game == genshin.Game.GENSHIN), None)
        
        if not genshin_acc:
            return await message.reply("❌ <b>Error:</b> No Genshin account found.")

        # 4. Final Redemption
        await client.redeem_code(promo_code, uid=genshin_acc.uid, game=genshin.Game.GENSHIN)
        
        await message.reply(
            f"✅ <b>Redeemed!</b>\nCode: <code>{promo_code}</code>\n"
            f"Sent to: <b>{genshin_acc.nickname}</b> (UID: <code>{genshin_acc.uid}</code>)",
            parse_mode="HTML"
        )

    except genshin.RedemptionException as e:
        # This catches "Already Redeemed" or "Invalid Code"
        await message.reply(f"❌ <b>HoYo Error:</b> <code>{e.msg}</code>", parse_mode="HTML")
    except Exception as e:
        await message.reply(f"❌ <b>Bot Error:</b> <code>{str(e)}</code>", parse_mode="HTML")
@dp.message(Command("characters"))
async def cmd_characters(message: types.Message):
    user_data = await users_col.find_one({"user_id": str(message.from_user.id)})

    if not user_data or "genshin_uid" not in user_data:
        return await message.reply("Please /login <uid> first.")

    db_uid = str(user_data["genshin_uid"]).strip()
    msg = await message.reply("Fetching your showcase...")

    user_info_enka = await get_enkadata(db_uid)
    showcase_items = user_info_enka.get("showAvatarInfoList", [])

    if not showcase_items:
        return await msg.edit_text(
            "No characters found!\nMake sure 'Show Character Details' is enabled in your profile."
        )

    builder = InlineKeyboardBuilder()

    for index, char in enumerate(showcase_items):
        char_id = str(char.get("avatarId"))
        char_entry = CHARACTER_MAP.get(char_id)

        display_name = char_entry.get("name", "Unknown") if char_entry else f"ID: {char_id}"

        builder.button(
            text=display_name,
            callback_data=f"gen_{db_uid}_{index}_{message.from_user.id}"
        )

    builder.adjust(3)

    image_buffer = await create_genshin_profile(db_uid)

    if not image_buffer:
        return await msg.edit_text("❌ Failed to generate profile image.")

    photo = BufferedInputFile(image_buffer.getvalue(), filename=f"{db_uid}.png")

    await msg.delete()

    await message.reply_photo(
        photo=photo,
        caption="Select a character:",
        reply_markup=builder.as_markup()
    )


# =========================
# CHARACTER CARD HANDLER
# =========================
@dp.callback_query(F.data.startswith("gen_"))
async def handle_card_generation(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    uid, char_index, owner_id = parts[1], int(parts[2]), int(parts[3])

    if callback.from_user.id != owner_id:
        return await callback.answer("⏳ This menu isn't for you!", show_alert=True)

    await callback.answer("⏳ Generating Local Card...")

    # 1. Fetch character ID from Enka data
    user_info = await get_enkadata(uid)
    showcase = user_info.get("showAvatarInfoList", [])

    if char_index >= len(showcase):
        return await callback.answer("❌ Character not found in showcase.", show_alert=True)

    current_char = showcase[char_index]
    char_id = int(current_char.get("avatarId"))
    
    # 2. Local Card Generation (Replacing the API call)
    try:
        # We call your local function directly
        # Ensure your characters_card function in character_card.py returns the BytesIO buffer
        image_buffer = await characters_card(uid, char_id)
        
        if not image_buffer:
            raise Exception("Buffer is empty")
            
    except Exception as e:
        print(f"LOCAL GEN ERROR: {e}")
        return await callback.message.edit_caption(
            caption="Failed to generate local card. Check console logs."
        )

    # 3. Fetch Ranking (Optional: keep this external if you don't have a local DB for it)
    ranking_text = ""
    ranking_api = f"https://test-xehj.onrender.com/get/ranking/{uid}"
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(ranking_api) as rank_resp:
                if rank_resp.status == 200:
                    all_ranks = await rank_resp.json()
                    char_rank_data = all_ranks.get(str(char_id))
                    if char_rank_data:
                        rank = char_rank_data.get("ranking")
                        out_of = char_rank_data.get("outOf")
                        percent = char_rank_data.get("percent")
                        ranking_text = (
                            f"\n\n<b>ʚଓ Global Rank :</b> {rank}/{out_of}"
                            f"\n<b>ʚଓ Top :</b> {percent}%"
                        )
        except:
            pass # Ranking is secondary, don't crash if it fails

    # 4. Prepare UI
    char_entry = CHARACTER_MAP.get(str(char_id))
    display_name = char_entry.get("name", "Unknown") if char_entry else f"ID: {char_id}"
    
    back_builder = InlineKeyboardBuilder()
    back_builder.button(text="Back to List", callback_data=f"refresh_{uid}_{owner_id}")

    # 5. Send the photo from the Buffer
    await callback.message.delete()
    
    # Use BufferedInputFile for the BytesIO object
    photo = BufferedInputFile(image_buffer.getvalue(), filename=f"{char_id}.png")
    target = callback.message.reply_to_message or callback.message

    await target.reply_photo(
        photo=photo,
        caption=f"✨ <b>{display_name}</b>{ranking_text}",
        reply_markup=back_builder.as_markup(),
        parse_mode="HTML"
    )

# =========================
# BACK BUTTON HANDLER
# =========================
@dp.callback_query(F.data.startswith("refresh_"))
async def handle_back_button(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    uid, owner_id = parts[1], int(parts[2])

    if callback.from_user.id != owner_id:
        return await callback.answer("❌ You can't use this button.", show_alert=True)

    user_info = await get_enkadata(uid)
    showcase = user_info.get("showAvatarInfoList", [])

    builder = InlineKeyboardBuilder()

    for index, char in enumerate(showcase):
        char_id = str(char.get("avatarId"))
        name = CHARACTER_MAP.get(char_id, {}).get("name", f"ID: {char_id}")

        builder.button(
            text=name,
            callback_data=f"gen_{uid}_{index}_{owner_id}"
        )

    builder.adjust(3)

    image_buffer = await create_genshin_profile(uid)

    if not image_buffer:
        return await callback.answer("❌ Failed to reload.", show_alert=True)

    photo = BufferedInputFile(image_buffer.getvalue(), filename=f"{uid}.png")

    await callback.message.edit_media(
        media=InputMediaPhoto(
            media=photo,
            caption="<b>Character Showcase</b>\nSelect a character:",
            parse_mode="HTML"
        ),
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
@dp.message(Command("share"))
async def share_wishes(message: types.Message):
    args = message.text.split()
    sender = message.from_user
    sender_name = sender.first_name  # The person sending the gift
    target_id = None
    target_name = "User" # Default if we can't find a name
    amount = 0

    # 1. Logic for Reply vs. Manual ID
    if message.reply_to_message:
        target_user = message.reply_to_message.from_user
        target_id = str(target_user.id)
        target_name = target_user.first_name # The person receiving the gift
        
        if len(args) < 2:
            return await message.reply("Usage: Reply to someone with <code>/share [amount]</code>", parse_mode="HTML")
        try:
            amount = int(args[1])
        except ValueError:
            return await message.reply("<b>Amount must be a number!</b>", parse_mode="HTML")
    else:
        # Manual mode: /share <user_id> <amount>
        if len(args) < 3:
            return await message.reply("Usage: <code>/share [user_id] [amount]</code>", parse_mode="HTML")
        target_id = args[1]
        try:
            amount = int(args[2])
        except ValueError:
            return await message.reply("<b>Amount must be a number!</b>", parse_mode="HTML")

    # 2. Basic Validations
    if amount <= 0:
        return await message.reply("<b>You must share at least 1 wish!</b>", parse_mode="HTML")
    
    if str(sender.id) == target_id:
        return await message.reply("<b>Nice try!</b> You cannot share wishes with yourself.", parse_mode="HTML")

    # 3. Check Sender's Balance
    sender_data = await users_col.find_one({"user_id": str(sender.id)})
    current_balance = sender_data.get("wish_count", 0) if sender_data else 0

    if current_balance < amount:
        return await message.reply(f"<b>Insufficient Balance!</b>\nYou have <b>{current_balance}</b> wishes.", parse_mode="HTML")

    # 4. Atomic Transaction
    await users_col.update_one({"user_id": str(sender.id)}, {"$inc": {"wish_count": -amount}})
    await users_col.update_one({"user_id": target_id}, {"$inc": {"wish_count": amount}}, upsert=True)

    # 5. Success Notifications
    # Using names in the public confirmation
    await message.reply(
        f"<b>Transaction Successful!</b>✅\n"
        f"<b>{sender_name}</b> sent 💫 <b>{amount}</b> wishes to <b>{target_name}</b>.", 
        parse_mode="HTML"
    )

    try:
        await message.bot.send_message(
            chat_id=target_id,
            text=f"<b>You received a gift!</b>\n"
                 f"<b>{sender_name}</b> sent you <b>{amount}</b> wishes!\n"
                 f"Check <code>/stats</code>",
            parse_mode="HTML"
        )
    except:
        pass
@dp.message(Command("gamble"))
async def gamble_wishes(message: types.Message, command: CommandObject):
    if message.chat.type != "private":
        return await message.reply("⚠️ <b>Gambling is restricted to Private DMs!</b>", parse_mode="HTML")

    user_id = str(message.from_user.id)
    
    if not command.args:
        return await message.answer("🎲 <b>Double or Nothing</b>\nUsage: <code>/gamble &lt;amount&gt;</code>", parse_mode="HTML")

    try:
        bet = int(command.args)
    except ValueError:
        return await message.answer("❌ Please enter a valid number.")

    user = await users_col.find_one({"user_id": user_id})
    current_balance = user.get("wish_count", 0) if user else 0

    if bet <= 0 or current_balance < bet:
        return await message.answer(f"❌ Invalid bet. Balance: {current_balance}")

    # --- Dynamic Odds Logic ---
    if current_balance < 2000:
        win_chance = 0.50
    elif current_balance < 2500:
        win_chance = 0.45
    else:
        win_chance = 0.40  # The 1000+ bonus

    win = random.random() < win_chance
    # --------------------------

    if win:
        new_balance = current_balance + bet
        msg = f"🏆 <b>WINNER!</b>\nResult: +{bet} Wishes"
        emoji = "💰"
    else:
        new_balance = current_balance - bet
        msg = f"💀 <b>BUSTED!</b>\nResult: -{bet} Wishes"
        emoji = "📉"

    await users_col.update_one({"user_id": user_id}, {"$set": {"wish_count": new_balance}})

    await message.answer(
        f"🎲 <b>Gamble Result</b>\n⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        f"{emoji} {msg}\n\n"
        f"👛 <b>New Balance:</b> {new_balance} Wishes",
        parse_mode="HTML"
    )
@dp.message(Command("daily"))
async def daily_wish(message: types.Message):
    user_id = str(message.from_user.id)
    user = await users_col.find_one({"user_id": user_id})
    now = datetime.utcnow()
    
    # Defaults
    streak = 1
    streak_u = 1
    wishes_to_add = 5
    bonus_msg = ""

    if user and "last_daily_wish" in user:
        last = user["last_daily_wish"]
        
        # 1. Cooldown Check
        if now - last < timedelta(days=1):
            remaining = timedelta(days=1) - (now - last)
            hours = remaining.seconds // 3600
            minutes = (remaining.seconds % 3600) // 60
            # Get existing streaks for the message
            s_val = user.get("daily_streak", 0)
            u_val = user.get("streak_new", 0)
            return await message.answer(
                f"⏳ Already claimed!\n"
                f"Come back in: <b>{hours}h {minutes}m</b>\n"
                f"Current Streak: <b>{u_val} Days</b>",
                parse_mode="HTML"
            )

        # 2. Streak Update Logic
        if now - last > timedelta(days=2):
            # Missed more than 48 hours: Reset both
            streak = 1
            streak_u = 1
        else:
            # Within 48 hours: Increment both
            streak = user.get("daily_streak", 0) + 1
            streak_u = user.get("streak_new", 0) + 1
    
    # 3. Milestone Rewards (using the 'streak' that resets)
    if streak == 7:
        wishes_to_add += 10
        bonus_msg = "\n🔥 <b>WEEKLY BONUS: +10 Wishes!</b>"
    elif streak == 14:
        wishes_to_add += 20
        bonus_msg = "\n🔥 <b>FORTNIGHT BONUS: +20 Wishes!</b>"
    elif streak == 21:
        wishes_to_add += 30
        bonus_msg = "\n🔥 <b>ULTIMATE BONUS: +30 Wishes!</b>\n<i>(Milestone streak reset!)</i>"
        streak = 0 # This resets the reward cycle, but streak_u keeps climbing

    # 4. Update Database
    await users_col.update_one(
        {"user_id": user_id},
        {
            "$set": {
                "last_daily_wish": now,
                "daily_streak": streak,
                "streak_new": streak_u,
                "notification_sent": False
            },
            "$inc": {"wish_count": wishes_to_add}
        },
        upsert=True
    )

    # 5. Final Message
    await message.answer(
        f"<b>Daily Reward Claimed! 🎁</b>\n"
        f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        f"Added: <b>+{wishes_to_add} Wishes</b> 🎫\n"
        f"Current Streak: <b>{streak_u} Days</b> 🔥"
        f"{bonus_msg}",
        parse_mode="HTML"
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
@dp.message(Command("broadcastg"))
async def broadcast_groups_smart(message: types.Message, bot: Bot):
    if message.from_user.id != ADMIN_ID:
        await message.answer("🚫 **Access Denied**")
        return

    # Reference the 'groups' collection specifically
    groups_col = db["groups"] 

    # 1. Extract content (Supports photo + caption or just text)
    raw_content = message.caption if message.photo else message.text
    parts = raw_content.split(maxsplit=1)
    broadcast_text = parts[1] if len(parts) > 1 else ""
    photo_id = message.photo[-1].file_id if message.photo else None

    if not broadcast_text and not photo_id:
        await message.answer("❓ **Usage:**\n1. Send image + `/broadcastg [text]`\n2. Send `/broadcastg [text]`")
        return

    status_msg = await message.answer("⏳ **Broadcasting to all registered groups...**")
    
    # 2. Get all documents from the 'groups' collection
    cursor = groups_col.find({})
    success, fail = 0, 0

    async for group in cursor:
        try:
            # Using 'chat_id' as seen in your screenshot
            target_id = group["chat_id"]
            
            if photo_id:
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
            await asyncio.sleep(0.2) # Higher delay for groups to stay safe
            
        except Exception as e:
            logging.error(f"Failed to send to group {group.get('chat_id')}: {e}")
            fail += 1

    await status_msg.edit_text(
        f"✅ **Group Broadcast Complete**\n"
        f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        f"👥 **Total Groups:** {success}\n"
        f"🚫 **Failed/Kicked:** {fail}"
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
    try:
        # 2. Fetch Data
        # We wrap these because if Battle Chronicle is private, these usually fail
        user_info = await get_player_full_data(db_uid)
        exploration_data = await get_exploration_data(db_uid)
        abyss_data = await get_abyss_data(db_uid)
        
        # Enka usually works even if HoYoLAB is private (it uses the in-game showcase)
        user_info_enka = await get_enkadata(db_uid)
        image_buffer = await create_genshin_profile(db_uid)    

        # 3. Check if HoYoLAB data is actually there
        if not user_info or not exploration_data:
            raise ValueError("PrivateProfile")

    except Exception as e:
        logging.error(f"Data fetch failed for {db_uid}: {e}")
        await status.delete()
        
        # The "Private Profile" Message
        private_msg = (
            "<b>⚠️ Profile is Private</b>\n\n"
            "I couldn't fetch your exploration data. Please follow these steps:\n"
            "1. Open <b>HoYoLAB</b> app/website.\n"
            "2. Go to <b>Settings</b> > <b>Privacy Settings</b>.\n"
            "3. Switch <b>'Public Character Showcase'</b> to ON.\n"
            "4. Disable <b>'Hide Battle Chronicle'</b>."
        )
        return await message.answer(private_msg, parse_mode="HTML")
    
    
    msg = "<b>PLAYER INFO</b>\n"
    msg += "─────────୨ৎ─────────\n"
    msg += f"𖹭 <b>{user_info_enka['nickname']}</b> | UID: <code>{db_uid}</code>\n"
    msg += f"𖹭 <b>AR {user_info_enka['level']}</b> | WL : {user_info_enka['worldLevel']}\n"
    msg += f"𖹭 <b>Achievements:</b> {user_info_enka['achievements']}\n"
    msg += f"𖹭 <b>Days Active:</b> {user_info.get('days_active', 'N/A')}\n"   
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
    orig_msg_id = event.message.message_id if is_callback else event.message_id
    for cid in list(common)[:18]: 
        name = char_map.get(str(cid), {}).get("name", f"ID: {cid}")
    # ADD orig_msg_id to the end of the data string
        builder.button(text=name, callback_data=f"comp:{u1}:{u2}:{cid}:{owner_id}:{orig_msg_id}")
    
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
    # Now we have index 5 for the message ID
    u1, u2, cid, owner_id, orig_msg_id = data[1], data[2], data[3], int(data[4]), int(data[5])
    
    # 1. Security Check
    if callback.from_user.id != owner_id:
        return await callback.answer("This menu isn't for you!", show_alert=True)

    # 2. Handshake & Loading State
    await callback.answer() # Stops button spinner
    
    try:
        # Swap the menu image to a loading image
        await callback.message.edit_media(
            media=InputMediaPhoto(
                media=FSInputFile("asstests/Loading_Screen_Startup.webp"), # Use your loading image path
                caption="<b>Creating comparison card... Please wait.</b>",
                parse_mode="HTML"
            )
        )
    except Exception:
        # Fallback if image edit fails (e.g., if the user deleted the message)
        pass

    # 3. Generate the Image (Pillow logic)
    img_bytes = await compare_characters(int(u1), int(u2), int(cid))

    if img_bytes is None:
        # If generation failed, tell the user instead of crashing
        await callback.message.edit_caption(
            caption="<b>❌ Error:</b> Failed to generate the comparison. This usually happens if Enka.network is lagging or profile details are hidden.",
            parse_mode="HTML"
        )
        return 

    await callback.message.delete()
    await callback.message.answer_photo(
        photo=types.BufferedInputFile(img_bytes.read(), filename="comparison.png"),
        caption=f"<b>Comparison Complete!</b>",
        parse_mode="HTML",
        reply_to_message_id=orig_msg_id
    )
    
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
    status_msg = await message.reply("Generating comparison showcase...")

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
        await message.reply_photo(
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

        original_user_msg_id = callback.message.reply_to_message.message_id if callback.message.reply_to_message else None

    # 2. Delete the bot's photo message
        await callback.message.delete()

        # 3. Send the text battle as a NEW reply to that original user message
        builder = InlineKeyboardBuilder()
        builder.row(types.InlineKeyboardButton(text="Back to Menu", callback_data=f"back_comp_{my_uid}_{target_uid}"))
        
        await callback.message.answer(
            msg, 
            reply_markup=builder.as_markup(), 
            parse_mode="HTML",
            reply_to_message_id=original_user_msg_id  # <--- THIS keeps the thread!
        )
    except Exception as e:
        await callback.message.reply(f"❌ Profile Error: {e}")

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
        original_user_msg_id = callback.message.reply_to_message.message_id if callback.message.reply_to_message else None

    # 2. Delete the bot's photo message
        await callback.message.delete()

        # 3. Send the text battle as a NEW reply to that original user message
        builder = InlineKeyboardBuilder()
        builder.row(types.InlineKeyboardButton(text="Back to Menu", callback_data=f"back_comp_{my_uid}_{target_uid}"))
        
        await callback.message.answer(
            msg, 
            reply_markup=builder.as_markup(), 
            parse_mode="HTML",
            reply_to_message_id=original_user_msg_id  # <--- THIS keeps the thread!
        )
    except Exception as e:
        await callback.message.reply(f"❌ Profile Error: {e}")
@dp.callback_query(F.data.startswith("back_comp_"))
async def back_to_compare_prep(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    my_uid, target_uid = parts[2], parts[3]
    
    # Get the original user message ID again
    original_user_msg_id = callback.message.reply_to_message.message_id if callback.message.reply_to_message else None

    # 1. Delete the text message
    await callback.message.delete()
    
    # 2. Re-generate photo
    photo_buffer = await create_masked_showcase(my_uid, target_uid)
    photo = BufferedInputFile(photo_buffer.read(), filename="compare.png")

    builder = InlineKeyboardBuilder()
    uids = f"{my_uid}_{target_uid}"
    builder.row(types.InlineKeyboardButton(text="𓊝 Compare Exploration", callback_data=f"comp_expl_{uids}"))
    builder.row(types.InlineKeyboardButton(text="𖨆 Compare Profile Stats", callback_data=f"comp_prof_{uids}"))

    # 3. Answer with photo as a reply to the original user command
    await callback.message.answer_photo(
        photo=photo,
        caption="⚔️ <b>Comparison Menu</b>\nChoose what to compare:",
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
        reply_to_message_id=original_user_msg_id # <--- Keeps the thread alive
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

async def main():
    try:
        await cluster.admin.command('ping')
        print("✅ Successfully connected to MongoDB!")
    except Exception as e:
        print(f"❌ MongoDB Connection Error: {e}")
        return 
    bot = Bot(token=TOKEN)
    lk_timezone = timezone("Asia/Colombo")
    setup_scheduler(bot, users_col, cipher)
    
    # Setup the local scheduler for wishes and cooldowns
    scheduler = AsyncIOScheduler(timezone=lk_timezone)
    
    # --- JOB 1: Check individual 24h cooldowns every 15 minutes ---
    scheduler.add_job(
        check_individual_dailies, 
        "interval", 
        minutes=15, 
        args=[bot]
    )

    # --- JOB 2: Run the daily reset task at Midnight ---
    scheduler.add_job(
        daily_wish, 
        "cron", 
        hour=0, 
        minute=0, 
        args=[bot]
    )
    
    # 4. Start the scheduler BEFORE polling
    scheduler.start()
    print("⏰ All schedulers started (HoYoLAB, Interval & Midnight Reset)!")

    # 5. Start background tasks (non-blocking)
    asyncio.create_task(clear_old_polls())

    # 6. Start polling (This is the LAST line)
    print("🤖 Bot is now online and polling...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("🤖 Bot stopped.")








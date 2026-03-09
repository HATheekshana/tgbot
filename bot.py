import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import logging
import sys
import random
import io
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont
import os
import requests
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime, timedelta
from aiogram.types import FSInputFile,BufferedInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from pytz import timezone

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
CURRENT_RATE_UP = "chasca"

cluster = AsyncIOMotorClient(MONGO_URL)
db = cluster["genshin_bot"]
users_col = db["user_stats"]


# ---------------- Dictionaries ----------------
weapons3 = {
    "magicguide":"Magic Guide", "blacktassel":"Black Tassel", "bloodtainted":"Bloodtainted Greatsword",
    "coolsteel":"Coolsteel", "debate":"Debate Club", "emerald":"Emerald", "ferrousshadow":"Ferrous Shadow",
    "harbinger":"Harbinger Of Dawn", "ravenbow":"Raven Bow", "skyridergreat":"Skyrider Greatsword",
    "skyridersword":"Skyrider Sword", "slingshot":"Slingshot", "thrillingtales":"Thrilling Tales"
}

characters4 = {
    "shikanoin-heizou":"Shikanoin Heizou", "xinyan":"Xinyan", "yaoyao":"YaoYao", "ororon":"Ororon",
    "sethos":"Sethos", "mika":"Mika", "lynette":"Lynette", "layla":"Layla", "lan-yan":"Lan Yan",
    "kuki-shinobu":"Kuki Shinobu", "gaming":"Gaming", "iansan":"Iansan", "ifa":"Ifa", "illuga":"Illuga",
    "jahoda":"Jahoda", "kachina":"Kachina", "kaveh":"Kaveh", "kirara":"Kirara", "kujou-sara":"Kujou Sara",
    "freminet":"freminet", "faruzan":"Faruzan", "dori":"Dori", "chongyun":"Chongyun", "collei":"Collei",
    "dahlia":"Dahlia", "chevreuse":"Chevreuse", "charlotte":"charlotte", "candace":"Candace", "aino":"Aino",
    "yun-jin":"Yun Jin", "yanfei":"Yanfei", "xingqiu":"Xingqiu", "xiangling":"Xiangling", "thoma":"Thoma",
    "sucrose":"Sucrose", "diona":"Diona", "noelle":"Noelle", "sayu":"Sayu", "rosaria":"Rosaria",
    "barbara":"Barbara", "amber":"Amber", "beidou":"Beidou", "bennett":"Bennett", "fischl":"Fischl",
    "gorou":"Gorou", "kaeya":"Kaeya", "lisa":"Lisa", "ningguang":"Ningguang", "razor":"Razor"
}

characters5 = {
    "albedo":"Albedo", "alhaitham":"Alhaitham", "arataki-itto":"AratakiItto", "arlecchino":"Arlecchino", 
    "baizhu":"Baizhu", "chasca":"Chasca", "chiori":"Chiori", "citlali":"Citlali", "clorinde":"Clorinde", 
    "columbina":"Columbina", "cyno":"Cyno", "dehya":"Dehya", "diluc":"Diluc", "durin":"Durin", 
    "emilie":"Emilie", "escoffier":"Escoffier", "eula":"Eula", "flins":"Flins", "furina":"Furina", 
    "ganyu":"Ganyu", "hu-tao":"HuTao", "ineffa":"Ineffa", "jean":"Jean", "kaedehara-kazuha":"Kaedehara Kazuha", 
    "kamisato-ayaka":"Kamisato Ayaka", "kamisato-ayato":"Kamisato Ayato", "keqing":"Keqing", "kinich":"Kinich", 
    "klee":"Klee", "lauma":"Lauma", "lyney":"Lyney", "mavuika":"Mavuika", "mona":"Mona", "mualani":"Mualani", 
    "nahida":"Nahida", "navia":"Navia", "nefer":"Nefer", "neuvillette":"Neuvillette", "nilou":"Nilou", 
    "qiqi":"Qiqi", "raiden-shogun":"Raiden Shogun", "sangonomiya-kokomi":"Sangonomiya Kokomi", "shenhe":"Shenhe", 
    "sigewinne":"Sigewinne", "skirk":"Skirk", "tartaglia":"Tartaglia", "tighnari":"Tighnari", "varesa":"Varesa", 
    "varka":"Varka", "venti":"Venti", "wanderer":"Wanderer", "wriothesley":"Wriothesley", "xianyun":"Xianyun", 
    "xiao":"Xiao", "xilonen":"Xilonen", "yae-miko":"YaeMiko", "yelan":"Yelan", "yoimiya":"Yoimiya", 
    "yumemizuki-mizuki":"Yumemizuki Mizuki", "zhongli":"Zhongli", "zibai":"Zibai"
}
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

    response = f"📜 **{first_name}'s Characters**\n"
    response += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n\n"

    for name, count in items:

        num = count - 1
        constellation = "C6+" if num > 6 else f"C{num}"

        rarity = get_rarity(name)
        stars = "★" * rarity

        response += f"{stars} **{name}** — {constellation}\n"

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

def combine_images(cha_path, bg_path, display_name, rarity):
    try:
        # 1. Download and open images
        bg_data = requests.get(bg_path).content
        cha_data = requests.get(cha_path).content
        background = Image.open(io.BytesIO(bg_data)).convert("RGBA")
        character = Image.open(io.BytesIO(cha_data)).convert("RGBA")

        # 2. Resize and Paste character
        scale = background.height / character.height
        new_size = (int(character.width * scale), background.height)
        character = character.resize(new_size, Image.Resampling.LANCZOS)
        x_offset = (background.width - character.width) // 2
        background.paste(character, (x_offset, 0), character)

        # 3. Setup Drawing
        draw = ImageDraw.Draw(background)
        try:
            # Replaced 450/350 with 90/70 for better balance
            font_name = ImageFont.truetype("ARIALBD 1.TTF", 80)  # Character Name
            font_stars = ImageFont.truetype("Arial-Unicode-MS.ttf", 60) # Rarity Stars
        except:
            font_name = ImageFont.load_default()
            font_stars = ImageFont.load_default()

        # Use the solid star character for better color control
        stars_text = "★" * rarity 
        margin_right = 50
        margin_bottom = 40
        line_spacing = 5

        # Calculate Name Dimensions
        bbox_n = draw.textbbox((0, 0), display_name, font=font_name)
        nw, nh = bbox_n[2] - bbox_n[0], bbox_n[3] - bbox_n[1]

        # Calculate Stars Dimensions
        bbox_s = draw.textbbox((0, 0), stars_text, font=font_stars)
        sw, sh = bbox_s[2] - bbox_s[0], bbox_s[3] - bbox_s[1]

        # Positions (Right Aligned)
        # Name on top, Stars directly below it
        nx = background.width - nw - margin_right
        ny = background.height - nh - sh - margin_bottom - line_spacing

        sx = background.width - sw - margin_right
        sy = background.height - sh - margin_bottom

        # --- NEW: ADD SUBTLE SHADOWS ---
        # Draw soft shadow first (offset by 2 for a "little" shadow)
        # (0, 0, 0) is black, 150 is the alpha (transparency)
        draw.text((nx+2, ny+2), display_name, font=font_name, fill=(0, 0, 0, 150))
        draw.text((sx+2, sy+2), stars_text, font=font_stars, fill=(0, 0, 0, 150))

        # --- Draw Main Text ---
        # Draw the main White text
        draw.text((nx, ny), display_name, font=font_name, fill=(255, 255, 255))
        # Stars (Yellow/Gold color for stars: 255, 204, 0)
        draw.text((sx, sy), stars_text, font=font_stars, fill=(255, 204, 0)) 

        return background

    except Exception as e:
        logging.error(f"Image Error: {e}")
        return Image.new("RGBA", (1280, 720), (45, 20, 84, 255))

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
        welcome_text = f"🌟 **Welcome to Teyvat, {first_name}!** 🌟\n\nI've given you **200 Wishes** to start your journey!"
    else:
        welcome_text = f"👋 **Welcome back, {first_name}!**"

    commands_list = (
        f"{welcome_text}\n\n"
        "**Available Commands:**\n"
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
    loading_photo = FSInputFile("Loading_Screen_Startup.webp")
    loading_msg = await message.answer_photo(
        photo=loading_photo, 
        caption="✨ **Invoking the Tides of Fate...**"
    )
    user_id = str(message.from_user.id)
    
    # 1. Fetch user or create if new
    user = await users_col.find_one({"user_id": user_id})
    if not user:
        user = {"user_id": user_id, "pity": 0, "count4": 0, "total_wishes": 0 , "wish_count": 200, "collection": {}}
        await users_col.insert_one(user)

    pity = user.get("pity", 0)
    count4 = user.get("count4", 0)
    total_wishes = user.get("total_wishes", 0)
    wish_count = user.get("wish_count", 0)
    current_collection = user.get("collection", {})
    is_guaranteed = user.get("is_guaranteed", False)
    new_guaranteed_status = is_guaranteed

    if wish_count < 10:
        await message.answer(f"❌ You don't have enough wishes. You only have {wish_count}.")
        return

    results = []
    pulled_chars = []
    file_path = ""
    result_msg = ""

    for i in range(10):
        pity += 1
        is_5star = False
        is_4star = False

        # --- 1. Determine Rarity ---
        if pity >= 89:
            pity = 0
            is_5star = True
        else:
            if random.randint(1, 1000) <= 6: # 0.6% base rate
                pity = 0
                is_5star = True
            elif count4 >= 9 or (i == 9 and not any([is_5star, is_4star])):
                count4 = 0
                is_4star = True
            elif random.randint(1, 10) == 1: # ~10% 4-star rate
                count4 = 0
                is_4star = True
            else:
                count4 += 1

        # --- 2. Process the Pull ---
        if is_5star:

            win_roll = random.randint(1, 100)

            if is_guaranteed or win_roll <= 60:
                file_key = CURRENT_RATE_UP
                display_name = [k for k, v in characters5.keys() if v == CURRENT_RATE_UP][0]
                new_guaranteed_status = False
                result_msg = f"🌟 RATE-UP WIN! 🌟\n"
            else: 
                file_key = random.choice(list(characters5.keys()))
                display_name = characters5[file_key]
                new_guaranteed_status = True
                result_msg = f"☁️ **50/50 Lost...** (Next one is Guaranteed!)\n"

            splash_name = display_name
            splash_rarity = 5    
            file_path = f"https://raw.githubusercontent.com/Mantan21/Genshin-Impact-Wish-Simulator/master/src/images/characters/splash-art/5star/{file_key}.webp"
            
            total_so_far = current_collection.get(display_name, 0) + pulled_chars.count(display_name)
            if total_so_far >= 7:
                wish_count += 2
                results.append(f"꩜ {display_name} (C6+ -> +2 Wish) ★★★★★")
            else:
                pulled_chars.append(display_name)
                results.append(f"꩜ {display_name} ★★★★★")

        elif is_4star:
            file_key = random.choice(list(characters4.keys()))
            display_name = characters4[file_key]
            if not file_path: # Set image to first 4/5 star found
                splash_name = display_name
                splash_rarity = 4
                file_path = f"https://raw.githubusercontent.com/Mantan21/Genshin-Impact-Wish-Simulator/master/src/images/characters/splash-art/4star/{file_key}.webp"
            
            total_so_far = current_collection.get(display_name, 0) + pulled_chars.count(display_name)
            if total_so_far >= 7:
                wish_count += 1
                results.append(f"꩜ {display_name} (C6+ -> +1 Wish) ★★★★")
            else:
                pulled_chars.append(display_name)
                results.append(f"꩜ {display_name} ★★★★")
        else:
            file_key = random.choice(list(weapons3.keys()))
            display_name = weapons3[file_key]
            results.append(f"꩜ {display_name} ★★★")

    # --- 3. Update Database (One Hit) ---
    total_wishes += 10
    wish_count -= 10
    
    update_query = {
        "$set": {
            "wish_count": wish_count,
            "pity": pity,
            "count4": count4,
            "total_wishes": total_wishes,
            "is_guaranteed": new_guaranteed_status
        }
    }
    
    if pulled_chars:
        inc_data = {}
        for char in pulled_chars:
            inc_data[f"collection.{char}"] = inc_data.get(f"collection.{char}", 0) + 1
        update_query["$inc"] = inc_data

    await users_col.update_one({"user_id": user_id}, update_query)

    # --- 4. Image Handling ---
    if not file_path:
        file_path = "https://raw.githubusercontent.com/FrenzyYum/GenshinWishingBot/master/assets/images/debate.webp" 

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
        
    await message.answer_photo(
        photo=photo_file,
        caption= result_msg + f"**★ Your 10-Pull Results ★**\n\n" + "\n".join(results),
        parse_mode="Markdown"
    )
@dp.message(Command("wish"))
async def send_single(message: types.Message):
    loading_photo = FSInputFile("Loading_Screen_Startup.webp")
    loading_msg = await message.answer_photo(
        photo=loading_photo, 
        caption="✨ **Invoking the Tides of Fate...**"
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
                file_key = CURRENT_RATE_UP
                display_name = [k for k, v in characters5.keys() if v == CURRENT_RATE_UP][0]
                new_guaranteed_status = False
                result_msg = f"🌟 RATE-UP WIN! 🌟\n"
        else: 
                file_key = random.choice(list(characters5.keys()))
                display_name = characters5[file_key]
                new_guaranteed_status = True
                result_msg = f"☁️ **50/50 Lost...** (Next one is Guaranteed!)\n"

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
        await message.answer("🚫 **Access Denied.**",parse_mode="Markdown")
        return

    args = message.text.split()
    target_id = None
    amount = 0

    # 2. Logic for Reply vs. Manual ID
    if message.reply_to_message:
        # If replying to a message, get that user's ID
        target_id = str(message.reply_to_message.from_user.id)
        if len(args) < 2:
            await message.answer("❓ **Usage:** Reply to someone with `/give <amount>`",parse_mode="Markdown")
            return
        try:
            amount = int(args[1])
        except ValueError:
            await message.answer("❌ Amount must be a number!")
            return
    else:
        # Manual mode: /give <user_id> <amount>
        if len(args) < 3:
            await message.answer("❓ **Usage:** `/give <user_id> <amount>` or reply to a message with `/give <amount>`",parse_mode="Markdown")
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
        await message.answer(f"✅ Granted **{amount} wishes** to user `{target_id}`.",parse_mode="Markdown")
        # Notify the lucky user
        try:
            await message.bot.send_message(
                chat_id=target_id,
                text=f"🎁 **Admin Bonus!**\nYou received **{amount}** wishes! Check  `/stats`",parse_mode="Markdown"
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
        await message.answer("🎲 **Double or Nothing**\nUsage: `/gamble <amount>`\nExample: `/gamble 50`")
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
        await message.answer(f"❌ You only have **{current_balance}** wishes. You can't bet **{bet}**!")
        return

    # 3. The 50/50 Roll
    # random.random() returns a float between 0.0 and 1.0
    win = random.random() >= 0.5 

    if win:
        # Win: They keep their bet and get an equal amount added
        new_balance = current_balance + bet
        result_msg = f"🏆 **WINNER!**\nYou doubled your bet! Received **+{bet}** wishes."
        emoji = "💰"
    else:
        # Lose: The bet amount is subtracted
        new_balance = current_balance - bet
        result_msg = f"💀 **BUSTED!**\nYou lost your **{bet}** wishes. Better luck next time!"
        emoji = "📉"

    # 4. Update Database
    await users_col.update_one(
        {"user_id": user_id},
        {"$set": {"wish_count": new_balance}}
    )

    # 5. Final Response
    await message.answer(
        f"🎲 **Gamble Result**\n⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        f"{emoji} {result_msg}\n\n"
        f"👛 New Balance: **{new_balance}** Wishes",
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
            await message.answer(f"⏳ Already claimed! Come back in **{hours}h {minutes}m**.")
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
    wishes_to_add = 1
    bonus_msg = ""

    if streak == 7:
        wishes_to_add += 10
        bonus_msg = "\n🔥 **WEEKLY BONUS:** +10 Wishes!"
    elif streak == 14:
        wishes_to_add += 20
        bonus_msg = "\n🔥 **FORTNIGHT BONUS:** +20 Wishes!"
    elif streak == 21:
        wishes_to_add += 30
        bonus_msg = "\n🔥 **ULTIMATE BONUS:** +30 Wishes!\n*(Streak reset to 0)*"
        # Reset streak after hitting the max milestone
        streak = 0 

    # 4. Update Database
    await users_col.update_one(
        {"user_id": user_id},
        {
            "$set": {"last_daily_wish": now, "daily_streak": streak},
            "$inc": {"wish_count": wishes_to_add}
        },
        upsert=True
    )

    # 5. Send Response with Current Streak
    await message.answer(
        f"🎁 **Daily Reward Claimed!**\n"
        f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        f"🎫 Added: **+{wishes_to_add} Wish(es)**\n"
        f"🔥 Current Streak: **{streak} Days**"
        f"{bonus_msg}",
        parse_mode="Markdown"
    )
async def add_daily_wish(bot: Bot):
    try:
        # 1. Update all users in one go
        result = await users_col.update_many(
            {}, 
            {"$inc": {"wish_count": 1}}
        )
        logging.info(f"Successfully added daily wish to {result.modified_count} users.")

        # 2. Broadcast the news to everyone
        broadcast_msg = (
            "✨ **Daily Reset!** ✨\n\n"
            "🎁 You have received **+1 Free Wish**!\n"
            "Check your balance with `/stats` and try your luck with `/wish`!"
        )

        cursor = users_col.find({})
        success, fail = 0, 0

        async for user in cursor:
            try:
                await bot.send_message(
                    chat_id=user["user_id"], 
                    text=broadcast_msg, 
                    parse_mode="Markdown"
                )
                success += 1
                await asyncio.sleep(0.05) # Prevent Telegram flood limits
            except Exception:
                fail += 1
        
        logging.info(f"Daily Broadcast: {success} sent, {fail} failed.")

    except Exception as e:
        logging.error(f"Error in daily wish task: {e}")

@dp.message(Command("collection"))
async def show_collection(message: types.Message):

    user_id = str(message.from_user.id)
    user = await users_col.find_one({"user_id": user_id})

    if not user or "collection" not in user or not user["collection"]:
        await message.answer("📭 **Your collection is empty!**\nUse /wish or /wish10 to find characters.")
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
    await message.reply(
        f"Stats for {message.from_user.first_name}:\n"
        f"Total wishes: {twishes}\n"
        f"Wishes: {wish_count}\n"
        f"Current 5★ Pity: {pity}\n"
        f"Current 4★ Pity: {count4}" # Changed label to be more accurate
    )
@dp.message(Command("broadcast"))
async def broadcast_input(message: types.Message, bot: Bot):
    # --- ADMIN CHECK ---
    
    if message.from_user.id != ADMIN_ID:
        # 1. Alert the Non-Admin User
        await message.answer("🚫 **Access Denied**\nThis command is restricted to the Bot Owner only.",parse_mode="Markdown")
        
        # 2. (Optional) Alert yourself that someone tried to use it
        await bot.send_message(
            chat_id=ADMIN_ID, 
            text=f"⚠️ **Security Alert**\nUser @{message.from_user.username} (ID: `{message.from_user.id}`) tried to use /broadcast.",parse_mode="Markdown"
        )
        return

    # --- INPUT CHECK ---
    broadcast_text = message.text.replace("/broadcast", "").strip().replace("\\n", "\n")

    if not broadcast_text:
        await message.answer("❓ **Usage:** `/broadcast Your message here`",parse_mode="Markdown")
        return

    # --- BROADCAST LOGIC ---
    status_msg = await message.answer("⏳ **Processing Broadcast...**",parse_mode="Markdown")
    
    cursor = users_col.find({})
    success, fail = 0, 0

    async for user in cursor:
        try:
            await bot.send_message(chat_id=user["user_id"], text=broadcast_text, parse_mode="Markdown")
            success += 1
            await asyncio.sleep(0.05) 
        except Exception:
            fail += 1

    await status_msg.edit_text(f"✅ **Broadcast Sent**\n🟢 Success: {success}\n🔴 Failed: {fail}" ,parse_mode="Markdown")
    
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

    lk_timezone = timezone("Asia/Colombo")
    
    scheduler = AsyncIOScheduler(timezone=lk_timezone)
    scheduler.add_job(
        add_daily_wish, 
        "cron", 
        hour=0, 
        minute=0, 
        args=[bot]  # Now 'bot' exists and can be passed!
    )
    
    # 4. Start everything
    scheduler.start()
    print("⏰ Daily wish & broadcast scheduler started!")

    # 5. Start polling
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())








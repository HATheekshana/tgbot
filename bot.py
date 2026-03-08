import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import logging
import sys
import random
import json
import io
from PIL import Image
import os
import requests
from aiogram.types import BufferedInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

ITEMS_PER_PAGE = 10

TOKEN = "8181850530:AAEuaGV4xkme3c_gMa6A8JFtHWzPZQU2W_g"
dp = Dispatcher()
MONGO_URL = "mongodb+srv://zerorenx_db_user:theekshana@tgbot.yuowvp8.mongodb.net/?appName=Tgbot"

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

def build_collection_page(sorted_chars, page, first_name):

    start = page * ITEMS_PER_PAGE
    end = start + ITEMS_PER_PAGE
    items = sorted_chars[start:end]

    response = f"📜 **{first_name}'s Characters**\n"
    response += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n\n"

    for name, count in items:

        num = count - 1
        constellation = "C6+" if num > 6 else f"C{num}"

        response += f"• **{name}** — {constellation}\n"

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
def combine_images(cha_path, bg_path):
    try:
        # Download images
        bg_data = requests.get(bg_path).content
        cha_data = requests.get(cha_path).content

        # Open with Pillow
        background = Image.open(io.BytesIO(bg_data)).convert("RGBA")
        character = Image.open(io.BytesIO(cha_data)).convert("RGBA")

        # Resize character to match background height
        scale = background.height / character.height
        new_size = (int(character.width * scale), background.height)
        character = character.resize(new_size, Image.Resampling.LANCZOS)

        # Center and Paste
        x_offset = (background.width - character.width) // 2
        background.paste(character, (x_offset, 0), character)
        
        return background

    except Exception as e:
        logging.error(f"Image Error: {e}")
        # Fallback: Create a simple purple background if the links fail
        return Image.new("RGBA", (1280, 720), (45, 20, 84, 255))
        
@dp.callback_query(lambda c: c.data.startswith("col_"))
async def change_collection_page(callback: types.CallbackQuery):

    page = int(callback.data.split("_")[1])

    user_id = str(callback.from_user.id)
    user = await users_col.find_one({"user_id": user_id})

    chars = user["collection"]

    sorted_chars = sorted(chars.items(), key=lambda x: x[1], reverse=True)

    text, keyboard = build_collection_page(
        sorted_chars,
        page,
        callback.from_user.first_name
    )

    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")

#wish10------------------------------------------------------------------------------


@dp.message(Command("wish10"))
async def send_image_10(message: types.Message):
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

    if wish_count < 10:
        await message.answer(f"❌ You don't have enough wishes. You only have {wish_count}.")
        return

    results = []
    pulled_chars = []
    file_path = ""

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
            file_key = random.choice(list(characters5.keys()))
            display_name = characters5[file_key]
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
            "total_wishes": total_wishes
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
    combined_img = combine_images(file_path, bg_path)
    output = io.BytesIO()
    combined_img.save(output, format="PNG")
    output.seek(0)
    photo_file = BufferedInputFile(output.read(), filename="wish.png")

    await message.answer_photo(
        photo=photo_file,
        caption=f"**Your 10-Pull Results:**\n\n" + "\n".join(results),
        parse_mode="Markdown"
    )
@dp.message(Command("wish"))
async def send_single(message: types.Message):
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
    
    if wish_count < 1:
        await message.answer(f"❌ You don't have enough wishes. You only have {wish_count}.")
        return

    pulled_chars = []
    is_5star = False
    is_4star = False

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
        file_key = random.choice(list(characters5.keys()))
        display_name = characters5[file_key]
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
        name = f"꩜ {display_name} ★★★"
        file_path = f"https://raw.githubusercontent.com/FrenzyYum/GenshinWishingBot/master/assets/images/{file_key}.webp"

    wish_count -= 1
    total_wishes += 1

    # Database Update
    if pulled_chars:
        await users_col.update_one({"user_id": user_id}, {"$inc": {f"collection.{pulled_chars[0]}": 1}})
    
    await users_col.update_one({"user_id": user_id}, {"$set": {
        "wish_count": wish_count, "pity": pity, "count4": count4, "total_wishes": total_wishes
    }})

    # Image sending logic (Keep your existing PIL code here...)
    bg_path = "https://raw.githubusercontent.com/Mantan21/Genshin-Impact-Wish-Simulator/master/src/images/background/splash-background.webp"
    combined_img = combine_images(file_path, bg_path)
    output = io.BytesIO()
    combined_img.save(output, format="PNG")
    output.seek(0)
    photo_file = BufferedInputFile(output.read(), filename="wish.png")
    await message.answer_photo(photo=photo_file, caption=name)

@dp.message(Command("collection"))
async def show_collection(message: types.Message):

    user_id = str(message.from_user.id)
    user = await users_col.find_one({"user_id": user_id})

    if not user or "collection" not in user or not user["collection"]:
        await message.answer("📭 **Your collection is empty!**\nUse /wish or /wish10 to find characters.")
        return

    chars = user["collection"]

    sorted_chars = sorted(chars.items(), key=lambda x: x[1], reverse=True)

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
    ADMIN_ID = 1675903713
    
    if message.from_user.id != ADMIN_ID:
        # 1. Alert the Non-Admin User
        await message.answer("🚫 **Access Denied**\nThis command is restricted to the Bot Owner only.")
        
        # 2. (Optional) Alert yourself that someone tried to use it
        await bot.send_message(
            chat_id=ADMIN_ID, 
            text=f"⚠️ **Security Alert**\nUser @{message.from_user.username} (ID: `{message.from_user.id}`) tried to use /broadcast."
        )
        return

    # --- INPUT CHECK ---
    broadcast_text = message.text.replace("/broadcast", "").strip().replace("\\n", "\n")

    if not broadcast_text:
        await message.answer("❓ **Usage:** `/broadcast Your message here`")
        return

    # --- BROADCAST LOGIC ---
    status_msg = await message.answer("⏳ **Processing Broadcast...**")
    
    cursor = users_col.find({})
    success, fail = 0, 0

    async for user in cursor:
        try:
            await bot.send_message(chat_id=user["user_id"], text=broadcast_text, parse_mode="Markdown")
            success += 1
            await asyncio.sleep(0.05) 
        except Exception:
            fail += 1

    await status_msg.edit_text(f"✅ **Broadcast Sent**\n🟢 Success: {success}\n🔴 Failed: {fail}")
    
# ---------------- Main ----------------
async def main():
   # Test connection on startup
    try:
        await cluster.admin.command('ping')
        print("✅ Successfully connected to MongoDB!")
    except Exception as e:
        print(f"❌ MongoDB Connection Error: {e}")
        return # Stop if we can't connect

    bot = Bot(token=TOKEN)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())








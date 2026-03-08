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
from aiogram.types import BufferedInputFile
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

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


#wish10------------------------------------------------------------------------------


@dp.message(Command("wish10"))
async def send_image_10(message: types.Message):
    user_id = str(message.from_user.id)
    
    # 1. Fetch user or create if new
    user = await users_col.find_one({"user_id": user_id})
    if not user:
        user = {"user_id": user_id, "pity": 0, "count4": 0, "total_wishes": 0 , "wish_count":200}
        await users_col.insert_one(user)

    pity = user["pity"]
    count4 = user["count4"]
    total_wishes = user["total_wishes"]
    wish_count = user["wish_count"]
    gurentee = False
    countto5 = 0
    countto5 = 90 - pity
    enough_wishes = True
    if wish_count >= 10 :
        enough_wishes = True
    else:
        enough_wishes = False

    if countto5 <=10 :
        gurentee = True
    else:
        pity+=10

    results = []
    star4 = 0
    star5 = 0
    file_path = ""
    count4 = 0
    if enough_wishes == True :
        for i in range(10):
            if gurentee == True:
                gurentee = False
                pity = 10 - countto5
                star5=1
                file_key = random.choice(list(characters5.keys()))
                display_name = characters5[file_key]
                results.append(f"꩜ {display_name} ★★★★★")
                file_path = f"https://raw.githubusercontent.com/Mantan21/Genshin-Impact-Wish-Simulator/master/src/images/characters/splash-art/5star/{file_key}.webp"
            else:
                if i == 9 and star4 == 0 and star5 == 0:
                    count4 = 0
                    file_key = random.choice(list(characters4.keys()))
                    display_name = characters4[file_key]
                    results.append(f"꩜ {display_name} ★★★★")
                    if not file_path:
                     file_path = f"https://raw.githubusercontent.com/Mantan21/Genshin-Impact-Wish-Simulator/master/src/images/characters/splash-art/4star/{file_key}.webp"
                    continue
            #check 5star
                star5check = random.randint(1, 1000)
                if star5check < 7:
                    pity = 0
                    file_key = random.choice(list(characters5.keys()))
                    display_name = characters5[file_key]
                    results.append(f"꩜ {display_name} ★★★★★")
                    file_path = f"https://raw.githubusercontent.com/Mantan21/Genshin-Impact-Wish-Simulator/master/src/images/characters/splash-art/5star/{file_key}.webp"
                    star5 = 1
            #check 4star
                else:
                    star4check = random.randint(1, 10)
                    if star4check == 10:
                        count4 = 0
                        file_key = random.choice(list(characters4.keys()))
                        display_name = characters4[file_key]
                        results.append(f"꩜ {display_name} ★★★★")
                        star4 = 1
                        if star5 == 0:
                            file_path = f"https://raw.githubusercontent.com/Mantan21/Genshin-Impact-Wish-Simulator/master/src/images/characters/splash-art/4star/{file_key}.webp"
                    else:
                        count4+=1
                        file_key = random.choice(list(weapons3.keys()))
                        display_name = weapons3[file_key]
                        results.append(f"꩜ {display_name} ★★★")

        total_wishes += 10
        wish_count -= 10

    #returning data to DB
    await users_col.update_one({"user_id": user_id}, {"$set": {"wish_count": wish_count}})
    await users_col.update_one({"user_id": user_id}, {"$set": {"pity": pity}})
    await users_col.update_one({"user_id": user_id}, {"$set": {"count4": count4}})
    await users_col.update_one({"user_id": user_id}, {"$set": {"total_wishes": total_wishes}})

    
    if not file_path:
        file_path = "https://www.freeiconspng.com/images/error" 

    bg_path = "https://raw.githubusercontent.com/Mantan21/Genshin-Impact-Wish-Simulator/master/src/images/background/splash-background.webp"
    combined_img = combine_images(file_path, bg_path)
    output = io.BytesIO()
    combined_img.save(output, format="PNG")
    output.seek(0)

    # Create the file object correctly
    photo_file = BufferedInputFile(output.read(), filename="wish.png")

    if enough_wishes:
            await message.answer_photo(
                photo=photo_file,
                caption=f"**Your 10-Pull Results:**\n\n" + "\n".join(results),
                parse_mode="Markdown"
            )
        else:
            await message.answer(f"❌ You don't have enough wishes. You only have {wish_count}.")

@dp.message(Command("wish"))
async def send_single(message: types.Message):
    user_id = str(message.from_user.id)
    
    # 1. Fetch user or create if new
    user = await users_col.find_one({"user_id": user_id})
    if not user:
        user = {"user_id": user_id, "pity": 0, "count4": 0, "total_wishes": 0 , "wish_count":200}
        await users_col.insert_one(user)

    pity = user["pity"]
    count4 = user["count4"]
    total_wishes = user["total_wishes"]
    
    if pity == 89 :
            pity = -1
            file_key = random.choice(list(characters5.keys()))
            display_name = characters5[file_key]
            name = f"꩜ {display_name} ★★★★★"
            file_path = f"https://raw.githubusercontent.com/Mantan21/Genshin-Impact-Wish-Simulator/master/src/images/characters/splash-art/5star/{file_key}.webp"
    else:
        if count4 == 9:
            count4 = 0
            file_key = random.choice(list(characters4.keys()))
            display_name = characters4[file_key]
            name = f"꩜ {display_name} ★★★★"
            file_path = f"https://raw.githubusercontent.com/Mantan21/Genshin-Impact-Wish-Simulator/master/src/images/characters/splash-art/4star/{file_key}.webp"
          
        else:
                star4check = random.randint(1, 10)
                if star4check == 10:
                    count4 = 0
                    file_key = random.choice(list(characters4.keys()))
                    display_name = characters4[file_key]
                    name = f"꩜ {display_name} ★★★★"
                    file_path = f"https://raw.githubusercontent.com/Mantan21/Genshin-Impact-Wish-Simulator/master/src/images/characters/splash-art/4star/{file_key}.webp"
                    
                else:
                    count4 += 1
                    file_key = random.choice(list(weapons3.keys()))
                    display_name = weapons3[file_key]
                    name = f"꩜ {display_name} ★★★"
                    file_path = f"https://raw.githubusercontent.com/FrenzyYum/GenshinWishingBot/master/assets/images/{file_key}.webp"                 
        
    pity+=1
    total_wishes+=1

    #returning data to DB
    
    await users_col.update_one({"user_id": user_id}, {"$set": {"pity": pity}})
    await users_col.update_one({"user_id": user_id}, {"$set": {"count4": count4}})
    await users_col.update_one({"user_id": user_id}, {"$set": {"total_wishes": total_wishes}})

    bg_path = "https://raw.githubusercontent.com/Mantan21/Genshin-Impact-Wish-Simulator/master/src/images/background/splash-background.webp"
    combined_img = combine_images(file_path, bg_path)
    output = io.BytesIO()
    combined_img.save(output, format="PNG")
    output.seek(0)

    # Create the file object correctly
    photo_file = BufferedInputFile(output.read(), filename="wish.png")
    
    await message.answer_photo(photo=photo_file, caption=name)

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








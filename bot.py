import asyncio
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
DATA_FILE = "user_stats.json"
dp = Dispatcher()

# ---------------- Data Handling ----------------
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}  # empty or corrupted file fallback
    return {}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

user_stats = load_data()

# ---------------- Dictionaries ----------------
weapons3 = {
    "magicguide":"Magic Guide", "blacktassel":"Black Tassel", "bloodtainted":"Bloodtainted Greatsword",
    "coolsteel":"Coolsteel", "debate":"Debate Club", "emerald":"Emerald", "ferrousshadow":"Ferrous Shadow",
    "harbinger":"Harbinger Of Dawn", "ravenbow":"Raven Bow", "skyridergreat":"Skyrider Greatsword",
    "skyridersword":"Skyrider Sword", "slingshot":"Slingshot", "thrillingtales":"Thrilling Tales"
}

characters4 = {
    "shikanoin heizou":"Shikanoin Heizou", "xinyan":"Xinyan", "yaoyao":"YaoYao", "ororon":"Ororon",
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
    "sangonomiya-kokomi":"Kokomi", "ganyu":"Ganyu", "tartaglia":"Tartaglia", "mona":"Mona", "raiden-shogun":"Raiden Shogun",
    "qiqi":"Qiqi", "yaemiko":"Yae Miko", "yoimiya":"Yoimiya", "zhongli":"Zhongli", "venti":"Venti",
    "shenhe":"Shenhe", "albedo":"Albedo", "kamisato-ayaka":"Ayaka", "diluc":"Diluc", "eula":"Eula", "hu-tao":"Hu Tao",
    "keqing-lanternrite":"Keqing", "keqing":"Keqing", "klee":"Klee", "jean":"Jean", "kaedehara-kazuha":"Kazuha", "xiao":"Xiao"
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

@dp.message(Command("wish10"))
async def send_image_10(message: types.Message):
    user_id = str(message.from_user.id)

    if user_id not in user_stats:
        user_stats[user_id] = {
            "total_wishes": 0, 
            "pity": 0, 
            "count4": 0
        }
    gurentee = False
    countto5 = 0
    countto5 = 90 - user_stats[user_id]["pity"]
    if countto5 <=10 :
        gurentee = True
    else:
        user_stats[user_id]["pity"]+=10
        save_data(user_stats)

    user_stats[user_id]["total_wishes"] += 10
    save_data(user_stats)

    results = []
    star4 = 0
    star5 = 0
    file_path = ""
    count4 = 0

    for i in range(10):
        if gurentee == True:
            gurentee = False
            user_stats[user_id]["pity"] = 10 - countto5
            save_data(user_stats)
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

            star5check = random.randint(1, 1000)
            if star5check < 7:
                user_stats[user_id]["pity"] = 0
                save_data(user_stats)
                file_key = random.choice(list(characters5.keys()))
                display_name = characters5[file_key]
                results.append(f"꩜ {display_name} ★★★★★")
                file_path = f"https://raw.githubusercontent.com/Mantan21/Genshin-Impact-Wish-Simulator/master/src/images/characters/splash-art/5star/{file_key}.webp"
                star5 = 1
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
    user_stats[user_id]["count4"]=count4
    save_data(user_stats)
    if not file_path:
        file_path = "https://www.freeiconspng.com/images/error" 

    bg_path = "https://raw.githubusercontent.com/Mantan21/Genshin-Impact-Wish-Simulator/master/src/images/background/splash-background.webp"
    combined_img = combine_images(file_path, bg_path)
    output = io.BytesIO()
    combined_img.save(output, format="PNG")
    output.seek(0)

    # Create the file object correctly
    photo_file = BufferedInputFile(output.read(), filename="wish.png")

    await message.answer_photo(
        photo=photo_file,
        caption=f"**Your 10-Pull Results:**\n\n" + "\n".join(results),
        parse_mode="Markdown"
    )

@dp.message(Command("wish"))
async def send_single(message: types.Message):
    user_id = str(message.from_user.id)
    name = ""
    if user_id not in user_stats:
        user_stats[user_id] = {
            "total_wishes": 0, 
            "pity": 0, 
            "count4": 0
        }
    if user_stats[user_id]["pity"] == 89 :
            user_stats[user_id]["pity"]=-1
            save_data(user_stats)
            file_key = random.choice(list(characters5.keys()))
            display_name = characters5[file_key]
            name = f"꩜ {display_name} ★★★★★"
            file_path = f"https://raw.githubusercontent.com/Mantan21/Genshin-Impact-Wish-Simulator/master/src/images/characters/splash-art/5star/{file_key}.webp"
    else:
        if user_stats[user_id]["count4"] == 9:
            user_stats[user_id]["count4"]=0
            save_data(user_stats)
            file_key = random.choice(list(characters4.keys()))
            display_name = characters4[file_key]
            name = f"꩜ {display_name} ★★★★"
            file_path = f"https://raw.githubusercontent.com/Mantan21/Genshin-Impact-Wish-Simulator/master/src/images/characters/splash-art/4star/{file_key}.webp"
          
        else:
                star4check = random.randint(1, 10)
                if star4check == 10:
                    user_stats[user_id]["count4"]=0
                    save_data(user_stats)
                    file_key = random.choice(list(characters4.keys()))
                    display_name = characters4[file_key]
                    name = f"꩜ {display_name} ★★★★"
                    file_path = f"https://raw.githubusercontent.com/Mantan21/Genshin-Impact-Wish-Simulator/master/src/images/characters/splash-art/4star/{file_key}.webp"
                    
                else:
                    user_stats[user_id]["count4"]+=1
                    save_data(user_stats)
                    file_key = random.choice(list(weapons3.keys()))
                    display_name = weapons3[file_key]
                    name = f"꩜ {display_name} ★★★"
                    file_path = f"https://tenor.com/search/cute-puppy-gifs"                 
        
    user_stats[user_id]["pity"]+=1
    user_stats[user_id]["total_wishes"] += 1
    save_data(user_stats)
    await message.answer_photo(photo=file_path, caption=name)

@dp.message(Command("stats"))
async def show_stats(message: types.Message):
    user_id = str(message.from_user.id)
    
    stats = user_stats.get(user_id, {"total_wishes": 0, "pity": 0, "count4": 0})
    
    await message.reply(
        f"Stats for {message.from_user.first_name}:\n"
        f"Total wishes: {stats['total_wishes']}\n"
        f"Current 5★ Pity: {stats['pity']}\n"
        f"Current 4★ Pity: {stats['count4']}" # Changed label to be more accurate
    )

# ---------------- Main ----------------
async def main():
    bot = Bot(token=TOKEN)
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())
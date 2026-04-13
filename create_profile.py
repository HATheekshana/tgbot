import asyncio
import aiohttp
import json
import os
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont, ImageOps
from dotenv import load_dotenv
import genshin

from genshin_utils import get_player_full_data, get_enkadata

load_dotenv()

# ------------------ GLOBALS ------------------

COOKIES = {
    "ltuid_v2": os.getenv("LTUID_V2"),
    "ltoken_v2": os.getenv("LTOKEN_V2")
}
cookie_token = os.getenv("COOKIE_TOKEN_V2")
if cookie_token:
    COOKIES["cookie_token_v2"] = cookie_token

client = genshin.Client(COOKIES)
client.region = genshin.Region.OVERSEAS

# Load JSON ONCE (important)
with open('char.json', 'r') as f:
    CHARACTER_MAP = json.load(f)

with open('data.json', 'r') as f:
    NAMECARD_DATA = json.load(f)

# Global session
session = aiohttp.ClientSession()

# Image cache
CACHE_DIR = "cache"
os.makedirs(CACHE_DIR, exist_ok=True)

# Asset cache (RAM)
ASSETS = {
    "background": Image.open("PROFILE-BACKGROUND.png").convert("RGBA"),
    "frame": Image.open("AVATAR.png").convert("RGBA"),
    "banner": Image.open("BANNER_FRAME.png").convert("RGBA"),
    "mask": ImageOps.invert(Image.open("AVATAR_MASKA.png").convert("L")),
    "char_mask": ImageOps.invert(Image.open("CHARTER_MASK.png").convert("L")),
    "char4": Image.open("CHARTER_4.png").convert("RGBA"),
    "char5": Image.open("CHARTER_5.png").convert("RGBA"),
}

# ------------------ IMAGE CACHE ------------------

async def fetch_image(url):
    filename = url.split("/")[-1]
    path = os.path.join(CACHE_DIR, filename)

    if os.path.exists(path):
        try:
            return Image.open(path).convert("RGBA")
        except:
            pass

    try:
        async with session.get(url) as resp:
            if resp.status != 200:
                return None

            data = await resp.read()

            with open(path, "wb") as f:
                f.write(data)

            return Image.open(BytesIO(data)).convert("RGBA")
    except:
        return None

# ------------------ HELPERS ------------------

def get_namecard_url(card_id):
    card = NAMECARD_DATA.get(str(card_id))
    if card:
        return f"https://enka.network/ui/{card['icon']}.png"
    return "https://enka.network/ui/UI_NameCardPic_0_P.png"

async def get_character_data(uid):
    data = await get_enkadata(uid)
    showcase = data.get("showAvatarInfoList", [])

    result = []
    for item in showcase:
        aid = str(item.get("avatarId"))
        info = CHARACTER_MAP.get(aid)

        if info:
            result.append({
                "id": int(aid),
                "rarity": info["rarity"],
                "icon": f"https://enka.network/ui/{info['avataricon']}.png"
            })
    return result

# ------------------ MAIN FUNCTION ------------------

async def create_genshin_profile(uid):

    # Fetch data in parallel
    player_task = get_player_full_data(uid)
    enka_task = get_enkadata(uid)

    try:
        user_info, enka = await asyncio.gather(player_task, enka_task)
        avatar_url = user_info.get("in_game_avatar")
    except:
        enka = await get_enkadata(uid)
        avatar_url = "https://enka.network/ui/UI_AvatarIcon_PlayerBoy.png"

    # Fetch images in parallel
    namecard_url = get_namecard_url(enka.get("nameCardId"))
    char_list = await get_character_data(uid)

    tasks = [
        fetch_image(namecard_url),
        fetch_image(avatar_url),
        *[fetch_image(c["icon"]) for c in char_list]
    ]

    results = await asyncio.gather(*tasks)

    namecard_img = results[0]
    avatar_img = results[1]
    char_imgs = results[2:]

    # ------------------ BUILD IMAGE ------------------

    base = ASSETS["background"].copy()

    if namecard_img:
        namecard_img = ImageOps.fit(namecard_img, (528, 201))
        base.paste(namecard_img, (35, 15), namecard_img)

    base.paste(ASSETS["banner"], (35, 15), ASSETS["banner"])

    # Avatar
    if avatar_img:
        avatar_img = ImageOps.fit(avatar_img, ASSETS["mask"].size)
        clean = Image.new("RGBA", ASSETS["mask"].size, (0, 0, 0, 0))
        clean.paste(avatar_img, (0, 0), ASSETS["mask"])

        base.paste(ASSETS["frame"], (220, 100), ASSETS["frame"])
        base.paste(clean, (220, 100), clean)

    # Characters
    for i, (char, img) in enumerate(zip(char_list, char_imgs)):
        if not img:
            continue

        img = ImageOps.fit(img, ASSETS["char_mask"].size)
        clean = Image.new("RGBA", ASSETS["char_mask"].size, (0, 0, 0, 0))
        clean.paste(img, (0, 0), ASSETS["char_mask"])

        bg = ASSETS["char5"] if char["rarity"] == 5 else ASSETS["char4"]

        x = 615 + ((i % 4) * 150)
        y = 290 + ((i // 4) * 150)

        base.paste(bg, (x, y), bg)
        base.paste(clean, (x, y), clean)

    # ------------------ TEXT (THREAD) ------------------

    def draw_text():
        draw = ImageDraw.Draw(base)

        try:
            f1 = ImageFont.truetype("Genshin_Impact.ttf", 23)
            f2 = ImageFont.truetype("Genshin_Impact.ttf", 20)
        except:
            f1 = f2 = ImageFont.load_default()

        draw.text((300, 290), enka.get("nickname", ""), font=f1, fill=(135,110,95), anchor="mm")
        draw.text((90, 365), f"AR: {enka.get('level')}", font=f2, fill=(135,110,95))
        draw.text((90, 415), f"WL: {enka.get('worldLevel')}", font=f2, fill=(135,110,95))

        buffer = BytesIO()
        base.save(buffer, format="PNG")
        buffer.seek(0)
        return buffer

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, draw_text)
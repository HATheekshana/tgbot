from PIL import Image, ImageDraw, ImageFont, ImageOps
import asyncio
import aiohttp
import genshin
import json
from io import BytesIO
from genshin_utils import get_player_full_data, get_enkadata
COOKIES = {
    "ltuid_v2": "471000302",
    "ltoken_v2": "v2_CAISDGM5b3FhcTNzM2d1OBokZTFmZTViNmItZDgxOS00MzNlLWJiZDktYWJkMTEzMWY1ZmY0ILaq780GKNa-zZEGMO7Jy-ABQgtiYnNfb3ZlcnNlYVhqagJTRw.NtW7aQAAAAAB.MEUCIGXUWYTB1bk4uUPg-Mwv8mZ6fXGUPvhKlkks9aizJCKVAiEA5ukOrLn7OhrY4JKtlMzZEXWCY-f-lCsBnIESDT_xbpY"
}
client = genshin.Client(COOKIES)
client.region = genshin.Region.OVERSEAS

with open('char.json', 'r') as f:
    CHARACTER_MAP = json.load(f)

async def get_character_data(uid):
    user_info_enka = await get_enkadata(uid)
    showcase_items = user_info_enka.get("showAvatarInfoList", [])
    
    if not showcase_items:
        print(f"⚠️ No characters found in Enka showcase for UID {uid}.")
        return []

    final_list = []
    for item in showcase_items:
        aid = str(item.get("avatarId"))
        char_info = CHARACTER_MAP.get(aid)
        
        if char_info:
            icon_name = char_info["avataricon"]
            final_list.append({
                "id": int(aid),
                "rarity": char_info["rarity"],
                "icon": f"https://enka.network/ui/{icon_name}.png",
                "level": item.get("propMap", {}).get("4001", {}).get("val", 1),
                "constellations": len(item.get("talentIdList", [])) 
            })
        else:
            final_list.append({
                "id": int(aid),
                "rarity": 4,
                "icon": "https://enka.network/ui/UI_AvatarIcon_Side_None.png",
                "level": 0
            })
    return final_list

async def get_namecard_image_url(card_id):
    with open('data.json', 'r') as file:
        namecard_data = json.load(file)
    card_info = namecard_data.get(str(card_id))
    if card_info:
        asset_name = card_info["icon"]
        return f"https://enka.network/ui/{asset_name}.png"
    return "https://enka.network/ui/UI_NameCardPic_0_P.png"

async def create_genshin_profile(uid):
    try:
        user_info = await get_player_full_data(uid)
        avatar_url = user_info['in_game_avatar']
    except Exception:
        avatar_url = "https://enka.network/ui/UI_AvatarIcon_PlayerBoy.png"

    user_info_enka = await get_enkadata(uid)
    
    # 1. Image loading and Setup
    base = Image.open("PROFILE-BACKGROUND.png").convert("RGBA")
    frame = Image.open("AVATAR.png").convert("RGBA")
    banner_frame = Image.open("BANNER_FRAME.png").convert("RGBA")
    
    mask = ImageOps.invert(Image.open("AVATAR_MASKA.png").convert("L"))
    char_mask = ImageOps.invert(Image.open("CHARTER_MASK.png").convert("L"))

    async with aiohttp.ClientSession() as session:
        # Fetch Namecard
        namecard_url = await get_namecard_image_url(user_info_enka['nameCardId'])
        async with session.get(namecard_url) as resp:
            namecard_img = Image.open(BytesIO(await resp.read())).convert("RGBA")
            namecard_img = ImageOps.fit(namecard_img, (528, 201), Image.Resampling.LANCZOS)
        
        # Fetch Avatar
        async with session.get(avatar_url) as resp:
            avatar_img = Image.open(BytesIO(await resp.read())).convert("RGBA")
            avatar_img = ImageOps.fit(avatar_img, mask.size, centering=(0.5, 0.5))
            clean_avatar = Image.new("RGBA", mask.size, (0, 0, 0, 0))
            clean_avatar.paste(avatar_img, (0, 0), mask)

    # 2. Layering Part 1: Background Elements
    base.paste(namecard_img, (35, 15), namecard_img)
    base.paste(banner_frame, (35, 15), banner_frame)
    base.paste(frame, (220, 100), frame)
    base.paste(clean_avatar, (220, 100), clean_avatar)
    

    # 3. Layering Part 2: Characters (Processed after background frames)
    final_list = await get_character_data(uid)
    async with aiohttp.ClientSession() as session:
        for i, char in enumerate(final_list): # Limiting to 8 to avoid grid overflow
            async with session.get(char["icon"]) as response:
                if response.status == 200:
                    char_content = await response.read()
                    charimage = Image.open(BytesIO(char_content)).convert("RGBA")
                    charimage = ImageOps.fit(charimage, char_mask.size, centering=(0.5, 0.5))
                    
                    clean_char = Image.new("RGBA", char_mask.size, (0, 0, 0, 0))
                    clean_char.paste(charimage, (0, 0), char_mask)
                    
                    x = 615 + ((i % 4) * 150)
                    y = 290 + ((i // 4) * 150)
                    
                    bg_file = "CHARTER_5.png" if char['rarity'] == 5 else "CHARTER_4.png"
                    char_bg = Image.open(bg_file).convert("RGBA")
                    
                    base.paste(char_bg, (x, y), char_bg)
                    base.paste(clean_char, (x, y), clean_char)

    # 4. Text Overlay
    draw = ImageDraw.Draw(base)
    try:
        f_big = ImageFont.truetype("Genshin_Impact.ttf", 23)
        f_small = ImageFont.truetype("Genshin_Impact.ttf", 20)
        f_xsmall = ImageFont.truetype("Genshin_Impact.ttf", 18)
    except:
        f_big = f_small = f_xsmall = ImageFont.load_default()

    draw.text((300, 290), str(user_info_enka['nickname']), font=f_big, fill=(135, 110, 95), anchor="mm")
    draw.text((90, 365), f"AR: {user_info_enka['level']}", font=f_small, fill=(135, 110, 95))
    draw.text((90, 415), f"World Level: {user_info_enka['worldLevel']}", font=f_small, fill=(135, 110, 95))
    draw.text((75, 475), str(user_info_enka['signature']), font=f_small, fill=(135, 110, 95))

    draw.text((660, 244), "CHARACTERS", font=f_big, fill=(135, 110, 95))
    draw.text((720, 140), "ACHIEVEMENTS", font=f_xsmall, fill=(135, 110, 95))
    draw.text((760, 175), str(user_info_enka['achievements']), font=f_big, fill=(135, 110, 95))

    abyss_text = f"{user_info_enka['abyssfloor']}-{user_info_enka['abysslevel']}"
    draw.text((1010, 140), "SPIRAL ABYSS", font=f_xsmall, fill=(135, 110, 95))
    draw.text((1050, 175), abyss_text, font=f_big, fill=(135, 110, 95))

    buffer = BytesIO()

    base.save(buffer, format="PNG")

    buffer.seek(0)

    return buffer

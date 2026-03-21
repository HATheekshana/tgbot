from PIL import Image, ImageDraw, ImageFont, ImageOps
import asyncio
import aiohttp
import genshin
import json
from io import BytesIO

COOKIES = {
    "ltuid_v2": "471000302",
    "ltoken_v2": "v2_CAISDGM5b3FhcTNzM2d1OBokZTFmZTViNmItZDgxOS00MzNlLWJiZDktYWJkMTEzMWY1ZmY0ILaq780GKNa-zZEGMO7Jy-ABQgtiYnNfb3ZlcnNlYVhqagJTRw.NtW7aQAAAAAB.MEUCIGXUWYTB1bk4uUPg-Mwv8mZ6fXGUPvhKlkks9aizJCKVAiEA5ukOrLn7OhrY4JKtlMzZEXWCY-f-lCsBnIESDT_xbpY"
}
client = genshin.Client(COOKIES)
client.region = genshin.Region.OVERSEAS

async def get_enkadata(uid):
    url = f"https://enka.network/api/uid/{uid}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                player_info = data.get("playerInfo", {})
                showcase = player_info.get("showAvatarInfoList", [])
                return {
                    "worldLevel": player_info.get("worldLevel", 0),
                    "signature": player_info.get("signature", ""),
                    "nameCardId": player_info.get("nameCardId", ""),
                    "showAvatarInfoList": showcase
                }
            return {"worldLevel": 0, "signature": "", "nameCardId": "" ,"showAvatarInfoList": []}

async def get_player_full_data(uid):
    raw_data = await client.get_genshin_user(uid)
    data = raw_data.dict()
    return {
        "nickname": data.get("info", {}).get("nickname", "Unknown"),
        "level": data.get("info", {}).get("level", 0),
        "achievements": data.get("stats", {}).get("achievements", 0),
        "in_game_avatar": data.get("info", {}).get("in_game_avatar", "Unknown"),
        "spiral_abyss": data.get("stats", {}).get("spiral_abyss", "Unknown"),
        "characters": data.get("characters", [])
    }
async def get_character_data(uid):
    # 1. Fetch data from both sources
    user_info = await get_player_full_data(uid)
    user_info_enka = await get_enkadata(uid)
    
    # 2. Extract the lists
    hoyolab_chars = user_info.get("characters", [])
    showcase_items = user_info_enka.get("showAvatarInfoList", [])
    
    # 3. Handle Empty Showcase (Common error: 'Show Character Details' is OFF)
    if not showcase_items:
        print(f"⚠️ No characters found in Enka showcase for UID {uid}. Check in-game settings!")
        return []

    # 4. Create a Map (ID -> Data)
    # We force the ID to int because Enka/Hoyolab sometimes mix types
    char_map = {int(char["id"]): char for char in hoyolab_chars}
    
    # Traveler ID Mapping (Common IDs for Aether and Lumine)
    traveler_ids = {10000005, 10000007} 

    final_list = []

    # 5. Loop through Showcase items and match them to Hoyolab details
    for item in showcase_items:
        aid = int(item.get("avatarId", 0))
        
        # Check if it's the Traveler (who might have a different ID in the map)
        if aid not in char_map and (aid > 10000000 and aid < 10000100):
            # Try to find any traveler in the map to use as a base
            for t_id in traveler_ids:
                if t_id in char_map:
                    char_map[aid] = char_map[t_id]
                    break

        if aid in char_map:
            details = char_map[aid]
            
            matched_info = {
                "id": aid,
                "name": details.get("name", "Unknown"),
                "element": details.get("element", "None"),
                "rarity": details.get("rarity", 4),
                "icon": details.get("icon", ""),
                "level": item.get("level", 1), # Take level from Enka (most recent)
                "friendship": details.get("friendship", 1),
                "constellation": item.get("tallentIdList", []) # Enka provides actual build data
            }
            final_list.append(matched_info)
        else:
            print(f"⚠️ Warning: Character ID {aid} not found in your Hoyolab characters.")

    print(f"✅ Successfully matched {len(final_list)} characters.")
    return final_list
async def get_namecard_image_url(card_id):
    # 1. Load the JSON file
    with open('data.json', 'r') as file:
        namecard_data = json.load(file)
    
    # 2. Search for the ID (convert card_id to string since JSON keys are strings)
    card_info = namecard_data.get(str(card_id))
    
    if card_info:
        asset_name = card_info["icon"]
        # 3. Build the URL for Enka.Network
        return f"https://enka.network/ui/{asset_name}.png"
    else:
        # Fallback to a default namecard if ID is not found
        return "https://enka.network/ui/UI_NameCardPic_0_P.png"


async def create_genshin_profile(uid):
    user_info = await get_player_full_data(uid)
    user_info_enka = await get_enkadata(uid)
    avatar_url = user_info['in_game_avatar']

    level = str(user_info['level'])
    world_level = str(user_info_enka['worldLevel'])
    achivemnts = str(user_info['achievements'])
    nickname = str(user_info['nickname'])
    abyss = str(user_info['spiral_abyss'])
    signature = str(user_info_enka['signature'])
    namecard_id = user_info_enka['nameCardId']
    namecard_url = await get_namecard_image_url(namecard_id)  # Example card ID, replace with actual ID as needed
    
    async with aiohttp.ClientSession() as session:
        async with session.get(avatar_url) as response:
            if response.status == 200:
                content = await response.read()
                # Load the downloaded bytes as a Pillow Image
                avatar = Image.open(BytesIO(content)).convert("RGBA")
            else:
                print(f"❌ Failed to download avatar. Status: {response.status}")
                return
    async with aiohttp.ClientSession() as session:
        async with session.get(namecard_url) as response:
            if response.status == 200:
                content = await response.read()
                # Load the downloaded bytes as a Pillow Image
                namecard = Image.open(BytesIO(content)).convert("RGBA")
            else:
                print(f"❌ Failed to download namecard. Status: {response.status}")
                return        
    base = Image.open("PROFILE-BACKGROUND.png").convert("RGBA")
    frame = Image.open("AVATAR.png").convert("RGBA")
    banner_frame = Image.open("BANNER_FRAME.png").convert("RGBA")
    namecard = ImageOps.fit(namecard, (528, 201), Image.Resampling.LANCZOS)
    
    mask = Image.open("AVATAR_MASKA.png").convert("L")
    char_mask = Image.open("CHARTER_MASK.png").convert("L")
    mask = ImageOps.invert(mask)
    char_mask = ImageOps.invert(char_mask)
    
    avatar = ImageOps.fit(avatar, mask.size, centering=(0.5, 0.5))
    clean_avatar = Image.new("RGBA", mask.size, (0, 0, 0, 0))
    clean_avatar.paste(avatar, (0, 0), mask)

    
    base.paste(namecard, (35, 15), namecard)
    base.paste(frame, (220, 100), frame)
    base.paste(clean_avatar, (220, 100), clean_avatar)
    base.paste(banner_frame, (35, 15), banner_frame)
    final_list = await get_character_data(uid)
    print(final_list)
    async with aiohttp.ClientSession() as session:
        for i, char in enumerate(final_list[:8]):
            print(char['icon'])
            async with session.get(char["icon"]) as response:
                if response.status == 200:
                    content = await response.read()
                    charimage = Image.open(BytesIO(content)).convert("RGBA")
                    
                    # Apply mask and fit
                    charimage = ImageOps.fit(charimage, char_mask.size, centering=(0.5, 0.5))
                    clean_char = Image.new("RGBA", char_mask.size, (0, 0, 0, 0))
                    clean_char.paste(charimage, (0, 0), char_mask)
                    
                    # Grid Math
                    col = i % 4
                    row = i // 4
                    x = 615 + (col * 150)
                    y = 350 + (row * 150)
                    if char['rarity'] == 5:
                        char_bg = Image.open("CHARTER_5.png").convert("RGBA")
                    else:
                        char_bg = Image.open("CHARTER_4.png").convert("RGBA")
                    base.paste(char_bg, (x, y), char_bg)
                    base.paste(clean_char, (x, y), clean_char)
                else:
                    print(f"❌ Skip {char['name']}: Status {response.status}")

    draw = ImageDraw.Draw(base)

    try:
        font_small = ImageFont.truetype("Genshin_Impact.ttf", 20)
        font_xsmall = ImageFont.truetype("Genshin_Impact.ttf", 18)
        font_big = ImageFont.truetype("Genshin_Impact.ttf", 23)
    except:
        font_small = ImageFont.load_default()

    draw.text((300, 290), nickname, font=font_big, fill=(135, 110, 95),anchor="mm")

    draw.text((90, 365), "AR:", font=font_small, fill=(135, 110, 95))
    draw.text((450, 365), level, font=font_small, fill=(135, 110, 95))

    draw.text((90, 415), "World Level:", font=font_small, fill=(135, 110, 95))
    draw.text((460, 415), world_level, font=font_small, fill=(135, 110, 95))

    draw.text((75, 475),signature, font=font_small, fill=(135, 110, 95))


    draw.text((660, 244), "CHARACTERS", font= font_big, fill=(135, 110, 95))

    draw.text((720, 140), "ACHIEVEMENTS", font= font_xsmall, fill=(135, 110, 95))
    draw.text((760, 175), achivemnts, font=font_big, fill=(135, 110, 95))

    draw.text((1010, 140), "SPIRAL ABYSS", font= font_xsmall, fill=(135, 110, 95))
    draw.text((1050, 175), abyss, font=font_big, fill=(135, 110, 95))
    
    buffer = BytesIO()

# 2. Save the image into the buffer instead of a file
    base.save(buffer, format="PNG")

    # 3. Move the 'cursor' to the start of the buffer so the bot can read it
    buffer.seek(0)

    # 4. Return the buffer
    return buffer

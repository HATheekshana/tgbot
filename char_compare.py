from PIL import Image, ImageDraw, ImageOps, ImageFilter, ImageFont
import asyncio
import aiohttp
import json
import genshin
from io import BytesIO

COOKIES = {
    "ltuid_v2": "471000302",
    "ltoken_v2": "v2_CAISDGM5b3FhcTNzM2d1OBokZTFmZTViNmItZDgxOS00MzNlLWJiZDktYWJkMTEzMWY1ZmY0ILaq780GKNa-zZEGMO7Jy-ABQgtiYnNfb3ZlcnNlYVhqagJTRw.NtW7aQAAAAAB.MEUCIGXUWYTB1bk4uUPg-Mwv8mZ6fXGUPvhKlkks9aizJCKVAiEA5ukOrLn7OhrY4JKtlMzZEXWCY-f-lCsBnIESDT_xbpY"
}

ELEMENT_BG_MAP = {
    "Pyro": "asstests/backgrounds/pyro.png",
    "Hydro": "asstests/backgrounds/hydro.png",
    "Anemo": "asstests/backgrounds/anemo.png",
    "Electro": "asstests/backgrounds/electro.png",
    "Dendro": "asstests/backgrounds/dendro.png",
    "Cryo": "asstests/backgrounds/cryo.png",
    "Geo": "asstests/backgrounds/geo.png"
}

client = genshin.Client(COOKIES)
client.region = genshin.Region.OVERSEAS

async def get_genshindata(uid):
    raw_data = await client.get_genshin_user(uid)
    data = raw_data.dict()
    return {
        "achievements": data.get("stats", {}).get("achievements", 0),
        "in_game_avatar": data.get("info", {}).get("in_game_avatar", "Unknown"),
        "spiral_abyss": data.get("stats", {}).get("spiral_abyss", "Unknown"),
    }

async def get_enkadata(uid):
    url = f"https://enka.network/api/uid/{uid}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                player_info = data.get("playerInfo", {})
                return {
                    "level" : player_info.get("level",""),
                    "nickname" : player_info.get("nickname",""),
                    "worldLevel": player_info.get("worldLevel", 0),
                    "signature": player_info.get("signature", ""),
                    "nameCardId": player_info.get("nameCardId", ""),
                    "avatarInfoList": data.get("avatarInfoList", []),
                    "showAvatarInfoList": player_info.get("showAvatarInfoList", [])
                }
            return {"level":"", "nickname":"", "worldLevel": 0, "signature": "", "nameCardId": "" ,"showAvatarInfoList": []}
def get_prop(stats_dict, prop_id):
    """Handles Enka's mix of string and integer keys for stats."""
    return stats_dict.get(str(prop_id), stats_dict.get(int(prop_id), 0))
def extract_char_stats(avatar_list, char_id, element):
    element_map = {"Pyro": 40, "Cryo": 41, "Electro": 42, "Hydro": 43, "Dendro": 44, "Anemo": 45, "Geo": 46}
    bonus_id = element_map.get(element, 45)

    for char in avatar_list:
        if str(char.get("avatarId")) == str(char_id):
            p = char.get("fightPropMap", {})
            friendship = char.get("fetterInfo", {}).get("expLevel", 1)
            return {
                "friendship": friendship,"hp": get_prop(p, 2000), "atk": get_prop(p, 2001), "def": get_prop(p, 2002),
                "em": get_prop(p, 28), "cr": get_prop(p, 20) * 100, "cd": get_prop(p, 22) * 100,
                "er": get_prop(p, 23) * 100, "elem_bonus": get_prop(p, bonus_id) * 100
            }
    return None
async def get_namecard_image_url(card_id):
    with open('data.json', 'r') as file:
        namecard_data = json.load(file)
    card_info = namecard_data.get(str(card_id))
    return f"https://enka.network/ui/{card_info['icon']}.png" if card_info else "https://enka.network/ui/UI_NameCardPic_0_P.png"

def draw_dynamic_bubble(draw, text, position, font, padding=20):
    bbox = draw.textbbox(position, text, font=font, anchor="mm")
    bg_coords = [bbox[0] - padding, bbox[1] - (padding // 2), bbox[2] + padding, bbox[3] + (padding // 2)]
    draw.rounded_rectangle(bg_coords, radius=10, fill=(20, 20, 30, 180), outline=(255, 255, 255, 150), width=1)
    draw.text(position, text, font=font, fill=(255, 255, 255, 255), anchor="mm")

async def fetch_image(session, url):
    async with session.get(url) as response:
        if response.status == 200:
            return Image.open(BytesIO(await response.read())).convert("RGBA")
    return None

async def compare_characters(uid, uid2, char_id):
    me, them = await get_enkadata(uid), await get_enkadata(uid2)
    me_g, them_g = await get_genshindata(uid), await get_genshindata(uid2)
    
    with open('char.json', 'r') as f:
        char_map = json.load(f)

    active_char_id = str(char_id)
    char_info = char_map.get(active_char_id, {"element": "Anemo", "avataricon": "UI_AvatarIcon_Qin", "name": "Unknown"})
    
    element = char_info['element']
    char_name = char_info['avataricon'].replace("UI_AvatarIcon_", "")
    splash_name = char_info['avataricon'].replace("UI_AvatarIcon", "UI_Gacha_AvatarImg")
    splash_url = f"https://enka.network/ui/{splash_name}.png"
    char_url = f"https://enka.network/ui/{char_info['avataricon']}.png"

    stats_me = extract_char_stats(them['avatarInfoList'], char_id, element)
    stats_them = extract_char_stats(me['avatarInfoList'], char_id, element)

    async with aiohttp.ClientSession() as session:
        namecard_me = await fetch_image(session, await get_namecard_image_url(me['nameCardId']))
        namecard_them = await fetch_image(session, await get_namecard_image_url(them['nameCardId']))
        avatar_me = await fetch_image(session, me_g['in_game_avatar'])
        avatar_them = await fetch_image(session, them_g['in_game_avatar'])
        splash_art = await fetch_image(session, splash_url)
        char_icon = await fetch_image(session, char_url)

    target_size = (1875, 890)
    bg_path = ELEMENT_BG_MAP.get(element, "asstests/backgrounds/anemo.jpg")
    
    bg_base = ImageOps.fit(Image.open(bg_path).convert("RGBA"), target_size, method=Image.Resampling.LANCZOS)
    
    if splash_art:
        splash_art.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
        bg_w, bg_h = target_size
        splash_w, splash_h = splash_art.size
        center_x = (bg_w // 2) - (splash_w // 2)
        center_y = 100 
        bg_base.paste(splash_art, (center_x, center_y), splash_art)
    
    background = bg_base.filter(ImageFilter.GaussianBlur(radius=7))

    ui_layer = Image.new("RGBA", target_size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(ui_layer)

    frame = Image.open("asstests/images/AVATAR.png").convert("RGBA")
    mask_avatar = ImageOps.invert(Image.open("asstests/images/AVATAR_MASK.png").convert("L"))

    tl_coords, tr_coords = [5, 5, 780, 220], [1070, 5, 1845, 220]
    box_w, box_h = 775, 215
    mask_nc = Image.new("L", (box_w, box_h), 0)
    ImageDraw.Draw(mask_nc).rounded_rectangle([0, 0, box_w, box_h], radius=10, fill=255)

    if namecard_me: background.paste(ImageOps.fit(namecard_me, (box_w, box_h)), (tr_coords[0], tr_coords[1]), mask_nc)
    if namecard_them: background.paste(ImageOps.fit(namecard_them, (box_w, box_h)), (tl_coords[0], tl_coords[1]), mask_nc)
    f_level_me = stats_me.get("friendship", 1) if stats_me else 1
    f_level_them = stats_them.get("friendship", 1) if stats_them else 1

    CI_coords = [840,5,1010,195]
    c_box_w, c_box_h = 170, 170
    mask_ci = Image.new("L", (c_box_w, c_box_h), 0)
    ImageDraw.Draw(mask_ci).rounded_rectangle([0, 0, c_box_w, c_box_h], radius=10, fill=255)
    if char_icon: background.paste(ImageOps.fit(char_icon, (c_box_w, c_box_h)), (CI_coords[0], CI_coords[1]), mask_ci)
    

    for av, pos in [(avatar_them, (20, 10)), (avatar_me, (1670, 10))]:
        if av:
            av_resized = ImageOps.fit(av, mask_avatar.size, centering=(0.5, 0.5))
            background.paste(frame, pos, frame)
            background.paste(av_resized, pos, mask_avatar)

    try: 
        font = ImageFont.truetype("Genshin_Impact.ttf", 23)
        font_big = ImageFont.truetype("Genshin_Impact.ttf", 28)
        
    except: 
        font = ImageFont.load_default()
    draw_dynamic_bubble(draw,char_name, (920, 200), font)
    draw_dynamic_bubble(draw, me['nickname'], (1750, 190), font)
    draw_dynamic_bubble(draw, them['nickname'], (100, 190), font)
    draw_dynamic_bubble(draw, f"UID : {uid}", (1520, 50), font)
    draw_dynamic_bubble(draw, f"UID : {uid2}", (330, 50), font)
    draw_dynamic_bubble(draw, "AR : " + str(me['level']), (1580, 95), font)
    draw_dynamic_bubble(draw, "AR : " + str(them['level']), (270, 95), font)
    draw_dynamic_bubble(draw, "WL : " + str(me['worldLevel']), (1585, 140), font)
    draw_dynamic_bubble(draw, "WL : " + str(them['worldLevel']), (265, 140), font)

    draw.rounded_rectangle([205,165, 320,215],radius=8, fill=(15, 15, 25, 220), outline=(255,255,255,50))
    f_icon = Image.open("asstests/icons/FRIENDS.png").convert("RGBA").resize((32, 32))
    ui_layer.paste(f_icon, (205 + 14, 165 + 11), f_icon)
    draw.text((270, 190),str(f_level_them), font=font_big, fill=(255, 255, 255, 255), anchor="lm")

    draw.rounded_rectangle([1525,165, 1640,215],radius=8, fill=(15, 15, 25, 220), outline=(255,255,255,50))
    f_icon = Image.open("asstests/icons/FRIENDS.png").convert("RGBA").resize((32, 32))
    ui_layer.paste(f_icon, (1525 + 14, 165 + 11), f_icon)
    draw.text((1595, 190),str(f_level_me), font=font_big, fill=(255, 255, 255, 255), anchor="lm")

    draw.rounded_rectangle(tl_coords, radius=10, outline=(255,255,255,200), width=2)
    draw.rounded_rectangle(tr_coords, radius=10, outline=(255,255,255,200), width=2)
    draw.rounded_rectangle([5, 365, 780, 885], radius=10, fill=(255,255,255,100), outline=(255,255,255,200))

    y_start = 370
    icon_w = 60      # Small box for icon
    label_w = 330     # Box for stat name
    val_w = 170       # Box for numeric values
    gap = 10          # Space between rectangles
    row_height = 55
    row_spacing = 65

    # Calculate total width of the 4-box row to center it
    start_x = 10

    stat_config = [
        ("Max HP", "hp", "{:.0f}", "asstests/icons/hp.png"),
        ("ATK", "atk", "{:.0f}", "asstests/icons/atk.png"),
        ("DEF", "def", "{:.0f}", "asstests/icons/def.png"),
        ("CRIT Rate", "cr", "{:.1f}%", "asstests/icons/cr.png"),
        ("CRIT DMG", "cd", "{:.1f}%", "asstests/icons/cd.png"),
        ("Energy Recharge", "er", "{:.1f}%", "asstests/icons/er.png"),
        (f"{element} DMG Bonus", "elem_bonus", "{:.1f}%", f"asstests/icons/{element.lower()}.png"),
        ("Elemental Mastery", "em", "{:.0f}", "asstests/icons/em.png")
    ]

    # 4. Draw Rows: [Icon] [Label] [User 1 Value] [User 2 Value]
    for i, (label, key, fmt, icon_path) in enumerate(stat_config):
        curr_y = y_start + (i * row_spacing)
        
        # Segment 1: ICON
        draw.rounded_rectangle([start_x, curr_y, start_x + icon_w, curr_y + row_height], 
                               radius=8, fill=(15, 15, 25, 220), outline=(255,255,255,50))
        try:
            icon = Image.open(icon_path).convert("RGBA").resize((32, 32))
            ui_layer.paste(icon, (start_x + 14, curr_y + 11), icon)
        except: pass

        # Segment 2: STAT LABEL
        l_x = start_x + icon_w + gap
        draw.rounded_rectangle([l_x, curr_y, l_x + label_w, curr_y + row_height], 
                               radius=8, fill=(15, 15, 25, 170), outline=(255,255,255,50))
        draw.text((l_x + 20, curr_y + (row_height//2)), label, font=font, fill=(230, 230, 230), anchor="lm")

        # Segment 3: USER 1 VALUE
        v1_x = l_x + label_w + gap
        draw.rounded_rectangle([v1_x, curr_y, v1_x + val_w, curr_y + row_height], 
                               radius=8, fill=(15, 15, 25, 170), outline=(255,255,255,50))
        val1 = fmt.format(stats_me.get(key, 0)) if stats_me else "0"
        draw.text((v1_x + (val_w // 2), curr_y + (row_height//2)), val1, font=font, fill=(255, 255, 255), anchor="mm")

        # Segment 4: USER 2 VALUE
        v2_x = v1_x + val_w + gap
        draw.rounded_rectangle([v2_x, curr_y, v2_x + val_w, curr_y + row_height], 
                               radius=8, fill=(15, 15, 25, 170), outline=(255,255,255,50))
        val2 = fmt.format(stats_them.get(key, 0)) if stats_them else "0"
        draw.text((v2_x + (val_w // 2), curr_y + (row_height//2)), val2, font=font, fill=(255, 255, 255), anchor="mm")


    buffer = BytesIO()
    final_img = Image.alpha_composite(background, ui_layer)
    final_img.convert("RGB").save(buffer, format="PNG") # Convert to RGB to reduce file size
    buffer.seek(0)
    return buffer


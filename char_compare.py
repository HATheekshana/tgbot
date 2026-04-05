import traceback

from PIL import Image, ImageDraw, ImageOps, ImageFilter, ImageFont
import asyncio
import aiohttp
import json
import genshin
from io import BytesIO
from artifacts_grid import draw_all_artifacts
from t_c import fetch_build_assets, draw_build_column
W_STAT_ICONS = {
        "FIGHT_PROP_BASE_ATTACK": "asstests/icons/atk.png",
        "FIGHT_PROP_CHARGE_EFFICIENCY": "asstests/icons/er.png",
        "FIGHT_PROP_ELEMENT_MASTERY": "asstests/icons/em.png",
        "FIGHT_PROP_CRITICAL": "asstests/icons/cr.png",
        "FIGHT_PROP_CRITICAL_HURT": "asstests/icons/cd.png",
        "FIGHT_PROP_ATTACK_PERCENT": "asstests/icons/atk.png",
        "FIGHT_PROP_HP_PERCENT": "asstests/icons/hp.png",
        "FIGHT_PROP_DEFENSE_PERCENT": "asstests/icons/def.png"
    }
COOKIES = {
    "ltuid_v2": "449108883",
    "ltoken_v2": "v2_CAISDGM5b3FhcTNzM2d1OBokNDcwMGJhYzAtMTAxZi00YjRlLTk2YmItN2M4YjhjMjMxZDAwIPWn780GKOuk4-0HMJO3k9YBQgtiYnNfb3ZlcnNlYVhqagJTRw.9dO7aQAAAAAB.MEUCIA5OHCjpxUDGrSJ8AQVHNuK4nwpW7XdJhtZhYnXcMhiFAiEAn0azB_VtrCvO57QPc72lKVKK_lTyMHAjDM2LrvENUco"
}

ELEMENT_BG_MAP = {
    "Pyro": "asstests/backgrounds/PYRO.png",
    "Hydro": "asstests/backgrounds/HYDRO.png",
    "Anemo": "asstests/backgrounds/ANEMO.png",
    "Electro": "asstests/backgrounds/ELECTRO.png",
    "Dendro": "asstests/backgrounds/DENDRO.png",
    "Cryo": "asstests/backgrounds/CRYO.png",
    "Geo": "asstests/backgrounds/GEO.png"
}

client = genshin.Client(COOKIES)
client.region = genshin.Region.OVERSEAS

async def get_genshindata(uid):
    raw_data = await client.get_genshin_user(uid)
    data = raw_data.dict()
    return {
        "in_game_avatar": data.get("info", {}).get("in_game_avatar", "Unknown"),
    }

async def get_enkadata(uid):
    url = f"https://enka.network/api/uid/{uid}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                player_info = data.get("playerInfo", {})
                return {
                    "achievements" : player_info.get("finishAchievementNum",""),
                    "level" : player_info.get("level",""),
                    "nickname" : player_info.get("nickname",""),
                    "worldLevel": player_info.get("worldLevel", 0),
                    "signature": player_info.get("signature", ""),
                    "nameCardId": player_info.get("nameCardId", ""),
                    "avatarInfoList": data.get("avatarInfoList", []),
                    "showAvatarInfoList": player_info.get("showAvatarInfoList", [])
                }
            return {"finishAchievementNum":"","level":"", "nickname":"", "worldLevel": 0, "signature": "", "nameCardId": "" ,"showAvatarInfoList": []}
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
            char_level = char.get("propMap", {}).get("4001", {}).get("val", "1")
            # --- WEAPON EXTRACTION ---
            weapon_info = {}
            equips = char.get("equipList", [])
            for item in equips:
                flat_data = item.get("flat", {})
                if item.get("weapon"):
                    weapon_data = item.get("weapon")
                    weapon_info["id"] = item.get("itemId")
                    weapon_info["level"] = weapon_data.get("level")
                    weapon_info["icon"] = flat_data.get("icon") 
                    weapon_info["hash"] = flat_data.get("nameTextMapHash")
                    weapon_info["rank"] = flat_data.get("rankLevel")
                    affix_map = weapon_data.get("affixMap", {})
                    if affix_map:
                        raw_value = list(affix_map.values())[0]
                        refinement = raw_value + 1
                    else:
                        refinement = 1

                    # Affix level 0 = Refinement 1
                    weapon_info["refinement"] = refinement
                    
                    # --- ADDED: Extract Base ATK and Sub Stats ---
                    w_stats = []
                    for s in flat_data.get("weaponStats", []):
                        w_stats.append({
                            "prop": s.get("appendPropId"),
                            "val": s.get("statValue")
                        })
                    weapon_info["stats"] = w_stats
                    break

            return {
                "char_level": char_level,
                "friendship": friendship,
                "hp": get_prop(p, 2000), 
                "atk": get_prop(p, 2001), 
                "def": get_prop(p, 2002),
                "em": get_prop(p, 28), 
                "cr": get_prop(p, 20) * 100, 
                "cd": get_prop(p, 22) * 100,
                "er": get_prop(p, 23) * 100, 
                "elem_bonus": get_prop(p, bonus_id) * 100,
                "weapon": weapon_info # Now includes weapon details
            }
    return None
async def get_namecard_image_url(card_id):
    with open('data.json', 'r') as file:
        namecard_data = json.load(file)
    card_info = namecard_data.get(str(card_id))
    return f"https://enka.network/ui/{card_info['icon']}.png" if card_info else "https://enka.network/ui/UI_NameCardPic_0_P.png"

def draw_dynamic_bubble(draw, text, position, font, padding=20, text_color=(255, 255, 255, 255), anchor="mm"):
    bbox = draw.textbbox(position, text, font=font, anchor=anchor)
    bg_coords = [bbox[0] - padding, bbox[1] - (padding // 2), bbox[2] + padding, bbox[3] + (padding // 2)]
    draw.rounded_rectangle(bg_coords, radius=10, fill=(20, 20, 30, 180), outline=(255, 255, 255, 150), width=1)
    draw.text(position, text, font=font, fill=text_color, anchor=anchor)
with open('weapon_names.json', 'r') as f:
    WEAPON_DATA_MAP = json.load(f)

def get_weapon_name(weapon_id):
    # weapon_id is the itemId from Enka (e.g., 13101)
    entry = WEAPON_DATA_MAP.get(str(weapon_id))
    if entry:
        return entry.get("EN", "Unknown Weapon")
    return "Unknown Weapon"
async def fetch_image(session, url):
    async with session.get(url) as response:
        if response.status == 200:
            return Image.open(BytesIO(await response.read())).convert("RGBA")
    return None
async def get_rank(uid, char_id, session): # Add session here
    ranking_api = f"https://test-xehj.onrender.com/get/ranking/{uid}"
    try:
        async with session.get(ranking_api, timeout=10) as rank_resp:
            if rank_resp.status == 200:
                all_ranks = await rank_resp.json()
                char_rank_data = all_ranks.get(str(char_id)) # Ensure string key
                if char_rank_data:
                    rank = char_rank_data.get("ranking")
                    out_of = char_rank_data.get("outOf")
                    percent = char_rank_data.get("percent")
                    return f"Rank: {rank}/{out_of} (Top {percent}%)"
            return "No Rank Found"
    except Exception as e:
        return f"Error: {e}"
ENKA_DEFAULT_AVATAR = "https://enka.network/ui/UI_AvatarIcon_PlayerBoy.png"

async def safe_fetch_avatar(session, url):
    # 1. Try the user's specific avatar first
    if url and url != "Unknown" and url.startswith("http"):
        try:
            img = await fetch_image(session, url)
            if img:
                return img
        except Exception as e:
            print(f"Failed to fetch user avatar: {e}")

    # 2. Fallback: Fetch the default Enka Traveler icon
    try:
        default_img = await fetch_image(session, ENKA_DEFAULT_AVATAR)
        if default_img:
            return default_img
    except Exception as e:
        print(f"Failed to fetch Enka default: {e}")

    # 3. Ultimate Emergency: Create a blank RGBA square so Pillow doesn't crash
    return Image.new("RGBA", (128, 128), (0, 0, 0, 0))
async def compare_characters(uid, uid2, char_id):
    try:
        me, them = await get_enkadata(uid), await get_enkadata(uid2)
        me_g, them_g = await get_genshindata(uid), await get_genshindata(uid2)
        me_data, them_data, t_icons, c_icons = await fetch_build_assets(uid, uid2, char_id)
    except Exception:
        print("--- CRITICAL ERROR IN DATA FETCH ---")
        traceback.print_exc()
        return None

    try:
        font = ImageFont.truetype("Genshin_Impact.ttf", 23)
        font_big = ImageFont.truetype("Genshin_Impact.ttf", 28)
        font_small = ImageFont.truetype("Genshin_Impact.ttf", 20)
        font_xsmall = ImageFont.truetype("Genshin_Impact.ttf", 16)
    except:
        font = ImageFont.load_default()
        font_big = font_small = font_xsmall = font

    with open('char.json', 'r') as f:
        char_map = json.load(f)

    char_info = char_map.get(str(char_id), {"rarity": 5, "element": "Anemo", "avataricon": "UI_AvatarIcon_Qin"})
    element = char_info['element']

    # 🔁 Your intentional swap kept
    stats_me = extract_char_stats(them['avatarInfoList'], char_id, element)
    stats_them = extract_char_stats(me['avatarInfoList'], char_id, element)

    if not stats_me or not stats_them:
        print("Stats extraction failed!")
        return None

    async with aiohttp.ClientSession() as session:

        # Safe weapon icon extraction
        icon_name_me = stats_me.get('weapon', {}).get('icon')
        icon_name_them = stats_them.get('weapon', {}).get('icon')

        rank_me, rank_them = await asyncio.gather(
            get_rank(uid, char_id, session),
            get_rank(uid2, char_id, session)
        )

        url_me = f"https://enka.network/ui/{icon_name_me}.png" if icon_name_me else None
        url_them = f"https://enka.network/ui/{icon_name_them}.png" if icon_name_them else None

        weapon_img_me, weapon_img_them = await asyncio.gather(
            fetch_image(session, url_me) if url_me else None,
            fetch_image(session, url_them) if url_them else None
        )

        avatar_me = await safe_fetch_avatar(session, me_g.get('in_game_avatar'))
        avatar_them = await safe_fetch_avatar(session, them_g.get('in_game_avatar'))

        splash_url = f"https://enka.network/ui/{char_info['avataricon'].replace('UI_AvatarIcon','UI_Gacha_AvatarImg')}.png"
        splash_art = await fetch_image(session, splash_url)

    # --- IMAGE BASE ---
    target_size = (1875, 890)
    bg_path = ELEMENT_BG_MAP.get(element, "asstests/backgrounds/ANEMO.png")
    background = ImageOps.fit(Image.open(bg_path).convert("RGBA"), target_size)

    if splash_art:
        splash_art.thumbnail((1600, 1600))
        background.paste(splash_art, ((1875 - splash_art.width)//2, 100), splash_art)

    background = background.filter(ImageFilter.GaussianBlur(7))

    ui_layer = Image.new("RGBA", target_size)
    draw = ImageDraw.Draw(ui_layer)

    # --- SIMPLE TEXT TEST (safe render check) ---
    draw.text((50, 50), f"{uid} vs {uid2}", font=font, fill=(255,255,255))

    # --- FRIENDSHIP FIX (keep your logic if needed) ---
    f_level_me = stats_them.get("friendship", 1)
    f_level_them = stats_me.get("friendship", 1)

    draw.text((50, 100), f"F1: {f_level_me}", font=font, fill=(255,255,255))
    draw.text((50, 140), f"F2: {f_level_them}", font=font, fill=(255,255,255))

    # --- DRAW BUILD (no duplicates) ---
    draw_build_column(background, 795, them_data, t_icons, c_icons)
    draw_build_column(background, 945, me_data, t_icons, c_icons)

    # --- CHARACTER OBJECT SAFE ---
    me_char_obj = next((c for c in me.get('avatarInfoList', []) if str(c['avatarId']) == str(char_id)), None)
    them_char_obj = next((c for c in them.get('avatarInfoList', []) if str(c['avatarId']) == str(char_id)), None)

    if not me_char_obj or not them_char_obj:
        print("Character not found!")
        return None

    async with aiohttp.ClientSession() as session:
        await draw_all_artifacts(
            session=session,
            background=ui_layer,
            me_char_data=me_char_obj,
            them_char_data=them_char_obj,
            font=font_small
        )

    # --- FINAL EXPORT ---
    buffer = BytesIO()
    final_img = Image.alpha_composite(background, ui_layer)
    final_img.convert("RGB").save(buffer, format="JPEG", quality=90)
    buffer.seek(0)

    return buffer
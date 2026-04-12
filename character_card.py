import asyncio
import aiohttp
import json
import os
from io import BytesIO
from PIL import Image, ImageDraw, ImageOps, ImageFilter, ImageFont, ImageChops, ImageEnhance
from motor.motor_asyncio import AsyncIOMotorClient
from graph import get_complete_radar_module
from dotenv import load_dotenv

load_dotenv()
from char_t_c import fetch_build_assets, draw_build_column
from artifacts import draw_horizontal_artifacts
MONGO_URL = os.getenv("MONGO_URL")

cluster = AsyncIOMotorClient(MONGO_URL)
db = cluster["genshin_bot"]
users_col = db["user_stats"]
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

try:
    with open("new.json", "r", encoding="utf-8") as f:
        TEXT = json.load(f)
except FileNotFoundError:
    print("Warning: new.json not found")
    TEXT = {}
try:
    with open("data.json", "r", encoding="utf-8") as f:
        NAMECARD_DATA = json.load(f)
except FileNotFoundError:
    print("Warning: data.json not found")
    NAMECARD_DATA = {}
try:
    with open("char.json", "r", encoding="utf-8") as f:
        CHAR_MAP = json.load(f)
except FileNotFoundError:
    print("Warning: char.json not found")
    CHAR_MAP = {}

SPECIAL_MAPPINGS = {
    "Ambor": "Amber", "Noel": "Noelle", "Feiyan": "Yanfei",
    "Shougun": "Raiden", "Tohma": "Thoma", "Heizo": "Heizou",
    "Liney": "Lyney", "Liuyun": "Xianyun"
}

async def get_user_card_settings(user_id):
    try:
        user = await users_col.find_one({"user_id": str(user_id)})
        print(f"DEBUG: Fetching settings for {user_id}. Found: {user is not None}")
        if user and "card_settings" in user:
            return user["card_settings"]
    except Exception as e:
        print(f"DB Error: {e}")
    return {"graph_on": True, "stickers": {}}
def draw_text_with_shadow(draw, text, position, font_path, font_size,
                          text_color=(255, 255, 255, 255),
                          shadow_color=(0, 0, 0, 180),
                          anchor="mm", shadow_offset=(2, 2)):
    font = ImageFont.truetype(font_path, font_size)
    shadow_pos = (position[0] + shadow_offset[0], position[1] + shadow_offset[1])
    draw.text(shadow_pos, text, font=font, fill=shadow_color, anchor=anchor)
    draw.text(position, text, font=font, fill=text_color, anchor=anchor)

async def get_enkadata(uid):
    url = f"https://enka.network/api/uid/{uid}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
            if response.status == 200:
                data = await response.json()
                player_info = data.get("playerInfo", {})
                return {
                    "nickname" : player_info.get("nickname",""),
                    "avatarInfoList": data.get("avatarInfoList", []),
                    "showAvatarInfoList": player_info.get("showAvatarInfoList", [])
                }
            return {"nickname":"","showAvatarInfoList": []}

def get_prop(stats_dict, prop_id):
    return stats_dict.get(str(prop_id), stats_dict.get(int(prop_id), 0))

def extract_char_stats(avatar_list, char_id, element):
    element = element.capitalize()
    element_map = {
        "Pyro": 40, "Electro": 41, "Hydro": 42, "Dendro": 43,
        "Anemo": 45, "Geo": 44, "Cryo": 46, "Physical": 30
    }
    bonus_id = element_map.get(element)

    for char in avatar_list:
        if str(char.get("avatarId")) == str(char_id):
            p = char.get("fightPropMap", {})
            weapon_info = {}
            equips = char.get("equipList", [])
            for item in equips:
                flat_data = item.get("flat", {})
                if item.get("weapon"):
                    weapon_data = item.get("weapon")
                    weapon_info = {
                        "id": item.get("itemId"),
                        "level": weapon_data.get("level"),
                        "rarity": flat_data.get("rankLevel"),
                        "icon": flat_data.get("icon"),
                        "hash": flat_data.get("nameTextMapHash"),
                        "refinement": list(weapon_data.get("affixMap", {0:0}).values())[0] + 1,
                        "stats": [{"prop": s.get("appendPropId"), "val": s.get("statValue")}
                                  for s in flat_data.get("weaponStats", [])]
                    }
                    break

            elem_bonus = (get_prop(p, bonus_id) + get_prop(p, 26) + get_prop(p, 27)) * 100
            return {
                "char_level": char.get("propMap", {}).get("4001", {}).get("val", "1"),
                "friendship": char.get("fetterInfo", {}).get("expLevel", 1),
                "hp": get_prop(p, 2000), "atk": get_prop(p, 2001), "def": get_prop(p, 2002),
                "em": get_prop(p, 28), "cr": get_prop(p, 20) * 100, "cd": get_prop(p, 22) * 100,
                "er": get_prop(p, 23) * 100, "elem_bonus": elem_bonus, "element": element,
                "weapon": weapon_info
            }
    return None

def get_namecard_urls(avatar_icon):
    base_name = avatar_icon.replace("UI_AvatarIcon_", "")
    search_name = SPECIAL_MAPPINGS.get(base_name, base_name)
    for _, info in NAMECARD_DATA.items():
        icon = info.get("icon", "")
        if f"_{search_name}_" in icon:
            banner = icon.replace("NameCardPic", "NameCardBanner")
            return [f"https://enka.network/ui/{banner}.png", f"https://enka.network/ui/{icon}.png"]
    return ["https://enka.network/ui/UI_NameCardBanner_0_P.png"]

def get_splash_url(avatar_icon):
    base_name = avatar_icon.replace("UI_AvatarIcon_", "")
    return f"https://enka.network/ui/UI_Gacha_AvatarImg_{base_name}.png"

def get_weapon_name(weapon_info):
    name_hash = str(weapon_info.get('hash', ''))
    return TEXT.get(name_hash, f"Weapon {weapon_info.get('id')}")

async def fetch_image(session, url):
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=3)) as resp:
            if resp.status != 200: return None
            return Image.open(BytesIO(await resp.read())).convert("RGBA")
    except: return None

def paste_splash_left(ui_layer, splash, size):
    card_w, card_h = size
    left_area_w, fade_width = 760, 160
    scale = card_h / splash.height
    splash = splash.resize((int(splash.width * scale), card_h), Image.Resampling.BILINEAR)
    splash = splash.crop(((splash.width - left_area_w) // 2, 0, (splash.width - left_area_w) // 2 + left_area_w, card_h))

    mask = Image.new("L", (left_area_w, card_h), 255)
    draw = ImageDraw.Draw(mask)
    for i in range(fade_width):
        draw.line([(left_area_w - fade_width + i, 0), (left_area_w - fade_width + i, card_h)], fill=int(255 * (1 - i / fade_width)))

    splash.putalpha(ImageChops.multiply(splash.getchannel('A'), mask))
    ui_layer.paste(splash, (0, 0), splash)
    return ui_layer

async def characters_card(uid, char_id, telegram_id):
    settings = await get_user_card_settings(telegram_id)

    try:
        me = await get_enkadata(uid)
        me_data, t_icons, c_icons = await fetch_build_assets(uid, char_id)
    except Exception as e:
        print(f"Error fetching data: {e}")
        return None

    char_id_str = str(char_id)
    char_info_map = CHAR_MAP.get(char_id_str, {"element": "Anemo", "avataricon": "UI_AvatarIcon_Qin"})
    initial_element = char_info_map.get('element', 'Anemo')

    stats = extract_char_stats(me['avatarInfoList'], char_id, initial_element)
    char_info = next(c for c in me['avatarInfoList'] if str(c.get("avatarId")) == str(char_id))

    element = stats.get("element", initial_element)
    avatar_icon = char_info_map.get("avataricon", "UI_AvatarIcon_Zibai")
    char_name = avatar_icon.replace("UI_AvatarIcon_", "")
    char_level = stats.get("char_level", 1) if stats else 1
    f_level = stats.get("friendship", 1) if stats else 1
    target_size = (1875, 890)
    font_path = "asstests/fonts/Genshin_Impact.ttf"
    font_small = ImageFont.truetype(font_path, 20)

    async with aiohttp.ClientSession() as session:
        bg_urls = get_namecard_urls(avatar_icon)

        bg_tasks = [fetch_image(session, url) for url in bg_urls]
        bg_results = await asyncio.gather(*bg_tasks, return_exceptions=True)
        bg_img = next((img for img in bg_results if img and not isinstance(img, Exception)), None)

        splash_dict = settings.get("splash_arts", {})
        custom_splash_path = splash_dict.get(str(char_id))
        if custom_splash_path:
            if not os.path.exists(custom_splash_path):
                filename = os.path.basename(custom_splash_path)
                local_path = os.path.join("custom_assets/splash_arts", filename)
                if os.path.exists(local_path):
                    custom_splash_path = local_path
            if os.path.exists(custom_splash_path):
                try:
                    splash_img = Image.open(custom_splash_path).convert("RGBA")
                except:
                    splash_img = await fetch_image(session, get_splash_url(avatar_icon))
            else:
                splash_img = await fetch_image(session, get_splash_url(avatar_icon))
        else:
            splash_img = await fetch_image(session, get_splash_url(avatar_icon))

        weapon_ic = stats['weapon'].get('icon')
        weapon_img = await fetch_image(session, f"https://enka.network/ui/{weapon_ic}.png")

        if not bg_img:
            bg_img = Image.new("RGBA", target_size, (30, 30, 45, 255))

        bg = ImageOps.fit(bg_img, target_size, method=Image.Resampling.BILINEAR).convert("RGBA")
        bg = ImageEnhance.Brightness(bg).enhance(0.45)
        ui_layer = Image.new("RGBA", target_size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(ui_layer)

        if splash_img:
            ui_layer = paste_splash_left(ui_layer, splash_img, target_size)

        base_x, base_y = 50, 50
        spacing = 15

        draw_text_with_shadow(
            draw,
            text=char_name,
            position=(base_x, base_y),
            font_path=font_path,
            font_size=36,
            text_color=(255, 255, 255, 255),
            anchor="lm"
        )
        name_font = ImageFont.truetype(font_path, 36)
        bbox = draw.textbbox((base_x, base_y), char_name, font=name_font, anchor="lm")
        next_x = bbox[2] + spacing
        draw_text_with_shadow(
            draw,
            text=me['nickname'],
            position=(next_x, base_y),
            font_path=font_path,
            font_size=26,
            text_color=(255, 255, 255, 255),
            anchor="lm"
        )
        draw_text_with_shadow(draw,text=f"Lvl: {char_level}/90",position=(50, 90),font_path=font_path,font_size=24,text_color=(255, 255, 255, 255), anchor="lm")
        draw_text_with_shadow(draw,text=f"Friendship: {f_level}",position=(50, 125),font_path=font_path,font_size=24,text_color=(255, 255, 255, 255), anchor="lm")
        if weapon_img:
            w_pos = (900, 20)
            w_info = stats['weapon']
            ui_layer.paste(ImageOps.contain(weapon_img, (140, 140)), w_pos, ImageOps.contain(weapon_img, (140, 140)))
            draw_text_with_shadow(draw, get_weapon_name(stats['weapon']), (w_pos[0] + 170, w_pos[1] + 30), font_path, 32, anchor="lm")
            refine = w_info.get('refinement', 1)
            level = w_info.get('level', 1)
            max_lv = "90"

            lv_text = f"R{refine}      Lv.{level}/{max_lv}"
            draw_text_with_shadow(draw, lv_text, (w_pos[0] + 170, w_pos[1] + 80), font_path, 24, text_color=(255, 255, 255), anchor="lm")

            w_stats_list = w_info.get("stats", [])
        STARS_PATH = "asstests/icons/stars/"
        w_rarity = stats['weapon'].get('rarity', 5)
        try:
            star_img = Image.open(f"{STARS_PATH}Star{w_rarity}.png").convert("RGBA")

            star_img = star_img.resize((140, 40), Image.Resampling.BILINEAR)

            ui_layer.paste(star_img, (w_pos[0] + 10, w_pos[1] + 120), star_img)
        except Exception as e:
            print(f"Error loading star image Star{w_rarity}.png: {e}")
        stat_x_start = w_pos[0] + 170
        stat_y = w_pos[1] + 100
        for i, s in enumerate(w_stats_list):
            curr_stat_x = stat_x_start + (i * 125)

            draw.rounded_rectangle([curr_stat_x, stat_y, curr_stat_x + 115, stat_y + 40], radius=5, fill=(255, 255, 255, 100))

            icon_path = W_STAT_ICONS.get(s['prop'], "asstests/icons/atk.png")
            try:
                s_icon = Image.open(icon_path).convert("RGBA").resize((22, 22))
                ui_layer.paste(s_icon, (curr_stat_x + 5, stat_y + 10), s_icon)
            except:
                pass

            val_str = f"{s['val']}"
            if any(x in str(s['prop']) for x in ["PERCENT", "CHARGE", "CRITICAL"]):
                val_str += "%"

            draw.text((curr_stat_x + 40, stat_y + 20), val_str, font=font_small, fill=(255, 255, 255), anchor="lm")

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

        start_x = 900
        gap = 500
        for i, (label, key, fmt, icon_path) in enumerate(stat_config):
            curr_y = 220 + (i * 50)
            try:
                icon = Image.open(icon_path).convert("RGBA").resize((35, 35))
                ui_layer.paste(icon, (start_x - 50, curr_y), icon)
            except:
                pass
            draw_text_with_shadow(draw, label, (start_x, curr_y + 18), font_path, 24, anchor="lm")
            draw_text_with_shadow(draw, fmt.format(stats.get(key, 0)), (start_x + gap, curr_y + 18), font_path, 26, anchor="rm")

        await draw_horizontal_artifacts(session, ui_layer, char_info, 150, 650, ImageFont.truetype(font_path, 22))

        loop = asyncio.get_event_loop()

        def render_final_image():
            """Composite images, draw graph/sticker, and draw build column - CPU intensive"""
            graph_position = (1450, 150)
            content_drawn = False

            graph_enabled_globally = settings.get("graph_on", True)
            disabled_chars = settings.get("disabled_graphs", [])
            stickers_dict = settings.get("stickers", {})

            char_graph_enabled = str(char_id) not in [str(id) for id in disabled_chars]

            if graph_enabled_globally and char_graph_enabled:
                try:
                    complete_graph = get_complete_radar_module(stats, char_id, final_size=(400, 400))

                    if complete_graph is not None:
                        radar_bg = Image.open("asstests/icons/radar_bg.png").convert("RGBA")
                        radar_bg = radar_bg.resize((530, 525), Image.Resampling.BILINEAR)
                        ui_layer.paste(radar_bg, (graph_position[0] - 70, graph_position[1] - 52), radar_bg)

                        ui_layer.paste(complete_graph, graph_position, complete_graph)
                        content_drawn = True

                except Exception as e:
                    print(f"Graph Generation Error: {e}")

            if not content_drawn:
                custom_path = stickers_dict.get(str(char_id))

                if custom_path:
                    if not os.path.exists(custom_path):
                        filename = os.path.basename(custom_path)
                        local_path = os.path.join("custom_assets/stickers", filename)
                        if os.path.exists(local_path):
                            custom_path = local_path

                    if os.path.exists(custom_path):
                        try:
                            with Image.open(custom_path) as sticker:
                                sticker = sticker.convert("RGBA").copy()
                                sticker.thumbnail((380, 380), Image.Resampling.LANCZOS)

                                s_w, s_h = sticker.size
                                paste_x = graph_position[0] + (190 - s_w // 2)
                                paste_y = graph_position[1] + (190 - s_h // 2)

                                ui_layer.paste(sticker, (paste_x, paste_y), sticker)
                                content_drawn = True
                        except Exception as e:
                            print(f"Custom Sticker Paste Error: {e}")

            if not content_drawn:
                try:
                    no_data = Image.open("asstests/icons/no_data.png").convert("RGBA")
                    no_data = no_data.resize((300, 300), Image.Resampling.LANCZOS)

                    nd_w, nd_h = no_data.size
                    paste_x = graph_position[0] + (190 - nd_w // 2)
                    paste_y = graph_position[1] + (190 - nd_h // 2)

                    ui_layer.paste(no_data, (paste_x, paste_y), no_data)
                except Exception as e:
                    print(f"Final Fallback Error: {e}")

            final_img = Image.alpha_composite(bg, ui_layer)
            draw_build_column(final_img, 650, me_data, t_icons, c_icons)

            buffer = BytesIO()
            final_img.convert("RGB").save(buffer, "JPEG", quality=95)
            buffer.seek(0)
            return buffer

        buffer = await loop.run_in_executor(None, render_final_image)
        return buffer


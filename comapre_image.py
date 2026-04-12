from PIL import Image, ImageDraw, ImageOps, ImageFilter, ImageFont
import aiohttp
import asyncio
import json
from io import BytesIO
from genshin_utils import get_player_full_data, get_enkadata
from dotenv import load_dotenv
import os

load_dotenv()

with open('char.json', 'r') as f:
    CHARACTER_MAP = json.load(f)

async def get_character_data(uid):
    user_info_enka = await get_enkadata(uid)
    showcase_items = user_info_enka.get("showAvatarInfoList", [])
    if not showcase_items: return []
    final_list = []
    for item in showcase_items:
        aid = str(item.get("avatarId"))
        char_info = CHARACTER_MAP.get(aid)
        if char_info:
            final_list.append({
                "rarity": char_info["rarity"],
                "icon": f"https://enka.network/ui/{char_info['avataricon']}.png"
            })
    return final_list

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

async def create_masked_showcase(uid, uid2):
    me, them = await get_enkadata(uid), await get_enkadata(uid2)
    me_g, them_g = await get_player_full_data(uid), await get_player_full_data(uid2)

    target_size = (1875, 890)
    img = Image.open("asstests/images/test1.jpg").convert("RGBA")
    background = ImageOps.fit(img, target_size, method=Image.Resampling.LANCZOS).filter(ImageFilter.GaussianBlur(radius=7))

    ui_layer = Image.new("RGBA", target_size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(ui_layer)

    tl_rect, tr_rect = [5, 365, 780, 885], [1070, 365, 1845, 885]
    draw.rounded_rectangle(tl_rect, radius=10, fill=(40,40,60,100), outline=(255,255,255,200), width=2)
    draw.rounded_rectangle(tr_rect, radius=10, fill=(40,40,60,100), outline=(255,255,255,200), width=2)

    frame = Image.open("asstests/images/AVATAR.png").convert("RGBA")
    mask_avatar = ImageOps.invert(Image.open("asstests/images/AVATAR_MASK.png").convert("L"))
    char_mask = ImageOps.invert(Image.open("asstests/images/CHARTER_MASK.png").convert("L"))

    async with aiohttp.ClientSession() as session:
        nc_me = await fetch_image(session, await get_namecard_image_url(me['nameCardId']))
        nc_them = await fetch_image(session, await get_namecard_image_url(them['nameCardId']))
        mask_nc = Image.new("L", (775, 215), 255)
        if nc_me: background.paste(ImageOps.fit(nc_me, (775, 215)), (1070, 5), mask_nc)
        if nc_them: background.paste(ImageOps.fit(nc_them, (775, 215)), (5, 5), mask_nc)

        av_me = await fetch_image(session, me_g['in_game_avatar'])
        av_them = await fetch_image(session, them_g['in_game_avatar'])
        for av, pos in [(av_them, (20, 10)), (av_me, (1670, 10))]:
            if av:
                av_res = ImageOps.fit(av, mask_avatar.size)
                background.paste(frame, pos, frame)
                background.paste(av_res, pos, mask_avatar)

        for u_idx, current_uid in enumerate([uid2, uid]):
            char_list = await get_character_data(current_uid)
            x_start = 35 if u_idx == 0 else 1100
            for i, char in enumerate(char_list):
                char_img = await fetch_image(session, char["icon"])
                if char_img:
                    char_img = ImageOps.fit(char_img, char_mask.size)
                    clean_char = Image.new("RGBA", char_mask.size, (0, 0, 0, 0))
                    clean_char.paste(char_img, (0, 0), char_mask)

                    x, y = x_start + (i % 4 * 185), 420 + (i // 4 * 150)
                    char_bg = Image.open(f"asstests/images/CHARTER_{char['rarity']}.png").convert("RGBA")

                    ui_layer.paste(char_bg, (x, y), char_bg)
                    ui_layer.paste(clean_char, (x, y), clean_char)

    loop = asyncio.get_event_loop()

    def render_showcase():
        """CPU-intensive: Text drawing, compositing, and PNG encoding"""
        try: font = ImageFont.truetype("Genshin_Impact.ttf", 23)
        except: font = ImageFont.load_default()

        draw_dynamic_bubble(draw, me['nickname'], (1750, 190), font)
        draw_dynamic_bubble(draw, them['nickname'], (100, 190), font)
        draw_dynamic_bubble(draw, f"UID : {uid}", (1520, 50), font)
        draw_dynamic_bubble(draw, f"UID : {uid2}", (330, 50), font)
        draw_dynamic_bubble(draw, "AR : " + str(me['level']), (1580, 95), font)
        draw_dynamic_bubble(draw, "AR : " + str(them['level']), (270, 95), font)
        draw_dynamic_bubble(draw, "WL : " + str(me['worldLevel']), (1585, 140), font)
        draw_dynamic_bubble(draw, "WL : " + str(them['worldLevel']), (265, 140), font)
        draw_dynamic_bubble(draw, "ACHIEVEMENTS : " + str(me['achievements']), (1490, 185), font)
        draw_dynamic_bubble(draw, "ACHIEVEMENTS : " + str(them['achievements']), (360, 185), font)

        final_img = Image.alpha_composite(background, ui_layer)
        buffer = BytesIO()
        final_img.save(buffer, format="PNG")
        buffer.seek(0)
        return buffer

    buffer = await loop.run_in_executor(None, render_showcase)
    return buffer


import asyncio
import aiohttp
import json
from io import BytesIO
from PIL import Image, ImageDraw, ImageOps, ImageFilter, ImageFont

# --- DATA EXTRACTION ---
def get_user_char_data(avatar_list, char_id, avatars_db):
    for char in avatar_list:
        if str(char.get("avatarId")) == str(char_id):
            meta = avatars_db.get(str(char_id), {})
            skill_levels = []
            order = meta.get("SkillOrder", [])
            p_map = meta.get("ProudMap", {})
            base_s = char.get("skillLevelMap", {})
            extra_s = char.get("proudSkillExtraLevelMap", {})
            
            for sid in order:
                lvl = base_s.get(str(sid), 1) + extra_s.get(str(p_map.get(str(sid))), 0)
                skill_levels.append(lvl)

            return {
                "talents": skill_levels,
                "cons_count": len(char.get("talentIdList", [])),
                "cons_icons": meta.get("Consts", []),
                "skill_icons": [meta["Skills"][str(s)] for s in meta["SkillOrder"]]
            }
    return None
def draw_circle_bubble(draw, text, position, font, padding=10, text_color=(255, 255, 255, 255), anchor="mm"):
    # 1. Get the text size
    bbox = draw.textbbox(position, text, font=font, anchor=anchor)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]

    # 2. Find the largest dimension to make it a square
    # We add padding to the diameter
    diameter = max(w, h) + (padding * 2)
    
    # 3. Calculate the bounding box for the circle centered at 'position'
    # position[0] is x, position[1] is y
    left = position[0] - (diameter // 2)
    top = position[1] - (diameter // 2)
    right = position[0] + (diameter // 2)
    bottom = position[1] + (diameter // 2)
    
    # 4. Draw the Circle (Ellipse in a square box)
    draw.ellipse([left, top, right, bottom], fill=(20, 20, 30, 200), outline=(255, 255, 255, 150), width=1)
    
    # 5. Draw the text
    draw.text(position, text, font=font, fill=text_color, anchor=anchor)
async def fetch_ui_image(session, url):
    try:
        async with session.get(f"https://enka.network/ui/{url.replace('/ui/','')}", timeout=10) as r:
            if r.status == 200:
                return Image.open(BytesIO(await r.read())).convert("RGBA")
    except: pass
    return None

# --- DATA FETCHING (Call this from your main card code) ---
async def fetch_build_assets(uid1, uid2, char_id):
    with open('avatars.json', 'r') as f: 
        avatars_db = json.load(f)

    async with aiohttp.ClientSession() as session:
        r1 = await session.get(f"https://enka.network/api/uid/{uid1}")
        r2 = await session.get(f"https://enka.network/api/uid/{uid2}")
        d1, d2 = await r1.json(), await r2.json()

        me_data = get_user_char_data(d1.get("avatarInfoList", []), char_id, avatars_db)
        them_data = get_user_char_data(d2.get("avatarInfoList", []), char_id, avatars_db)

        if not me_data or not them_data:
            return None, None, None, None

        # Fetch icons for both (showing me_data icons as the reference)
        t_icons = await asyncio.gather(*[fetch_ui_image(session, u) for u in me_data['skill_icons']])
        c_icons = await asyncio.gather(*[fetch_ui_image(session, u) for u in me_data['cons_icons']])
        
    return me_data, them_data, t_icons, c_icons

# --- DRAWING TOOL (Call this from your main card code) ---
def draw_build_column(canvas, start_x, data,t_icons, c_icons):
    draw = ImageDraw.Draw(canvas)
    font_path = "asstests/fonts/Genshin_Impact.ttf"
    
    # Load fonts inside the function so they are available
    f_lvl = ImageFont.truetype(font_path, 18)
    
    # Load assets
    entry_bg = Image.open("asstests/talents/bg.png").convert("RGBA")
    ten_bg = Image.open("asstests/talents/10.png").convert("RGBA")
    con_bg = Image.open("asstests/constant/const_adapt.png").convert("RGBA")
    lock_bg = Image.open("asstests/constant/closed/CLOSED.png").convert("RGBA")
    mask = Image.open("asstests/constant/maska_constant.png").convert("L")
    # --- DRAW TALENTS ---
    for i, icon in enumerate(t_icons):
        if not icon: continue
        indent = 50 if i == 1 else 0
        x, y = start_x + indent, 220 + (i * 80)
        lvl = data['talents'][i]
        draw.ellipse([x+10, y+10, x+80, y+80], fill=(0, 0, 0, 100)) # Base circle for level indicator    
        t_bg = (ten_bg if lvl >= 10 else entry_bg).resize((90, 90), Image.Resampling.LANCZOS)
        canvas.paste(t_bg, (x, y), t_bg)

        icon_res = icon.resize((60, 60), Image.Resampling.LANCZOS)
        canvas.paste(icon_res, (x + 15, y + 15), icon_res)

        color = (255, 215, 0) if lvl >= 10 else (255, 255, 255)
        draw_circle_bubble(draw, f"{lvl}", (x+45, y + 80), f_lvl, text_color=color)
    # --- DRAW CONSTELLATIONS ---
    for i, icon in enumerate(c_icons):
        if not icon: continue
        indent = 60 if (i + 1) % 2 == 0 else 0
        x, y = start_x + indent, 500 + (i * 60)
        draw.ellipse([x, y, x+70, y+70], fill=(0, 0, 0, 160)) # Base circle for level indicator    
        is_locked = i >= data['cons_count']
        img = icon.resize((60, 60), Image.Resampling.LANCZOS)
        c_mask = mask.resize((60, 60), Image.Resampling.LANCZOS)
        canvas.paste(img, (x+5, y+5), c_mask)
        c_bgs_res = con_bg.resize((70, 70), Image.Resampling.LANCZOS)
        canvas.paste(c_bgs_res, (x, y), c_bgs_res)
        if is_locked:
            img = img.convert("L").convert("RGBA")
            c_bg_res = lock_bg.resize((70, 70), Image.Resampling.LANCZOS)
            canvas.paste(c_bg_res, (x, y), c_bg_res)
        
        
        
            

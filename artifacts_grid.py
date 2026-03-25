import asyncio
import aiohttp
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont

# Stat Mapping for icons (Local files)
STAT_MAP = {
    "FIGHT_PROP_HP": "hp", "FIGHT_PROP_HP_PERCENT": "hp",
    "FIGHT_PROP_ATTACK": "atk", "FIGHT_PROP_ATTACK_PERCENT": "atk",
    "FIGHT_PROP_DEFENSE": "def", "FIGHT_PROP_DEFENSE_PERCENT": "def",
    "FIGHT_PROP_ELEMENT_MASTERY": "em", "FIGHT_PROP_CHARGE_EFFICIENCY": "er",
    "FIGHT_PROP_CRITICAL": "cr", "FIGHT_PROP_CRITICAL_HURT": "cd",
    "FIGHT_PROP_FIRE_ADD_HURT": "pyro", "FIGHT_PROP_WATER_ADD_HURT": "hydro",
    "FIGHT_PROP_GRASS_ADD_HURT": "dendro", "FIGHT_PROP_ELEC_ADD_HURT": "electro",
    "FIGHT_PROP_ICE_ADD_HURT": "cryo", "FIGHT_PROP_WIND_ADD_HURT": "anemo",
    "FIGHT_PROP_ROCK_ADD_HURT": "geo", "FIGHT_PROP_PHYSICAL_ADD_HURT": "phys"
}

# Sorting order for artifacts
# Order to ensure: Flower, Feather, Sands, Goblet, Circlet
EQUIP_ORDER = ["EQUIP_BRACER", "EQUIP_NECKLACE", "EQUIP_SHOES", "EQUIP_RING", "EQUIP_DRESS"]

async def draw_artifact_card(session, base_image, x, y, art_data, font):
    draw = ImageDraw.Draw(base_image)
    CARD_W, CARD_H = 390, 115 
    ICONS_PATH = "asstests/icons/"
    STARS_PATH = "asstests/icons/stars/" # The folder where Star1.png, Star2.png, etc. are located
    
    # 1. Background Card
    draw.rounded_rectangle([x, y, x + CARD_W, y + CARD_H], radius=12, fill=(255,255,255,60), outline=(255, 255, 255, 30))

    flat = art_data.get("flat", {})
    relic_core = art_data.get("reliquary", {})

    # 2. Artifact Piece Icon
    icon_name = flat.get("icon")
    if icon_name:
        url = f"https://enka.network/ui/{icon_name}.png"
        try:
            async with session.get(url) as response:
                if response.status == 200:
                    art_img = Image.open(BytesIO(await response.read())).convert("RGBA").resize((95, 95))
                    draw.rounded_rectangle([x, y, x +110, y + 110], radius=12, fill=(0,0,0,100), outline=(255, 255, 255, 30))
                    base_image.paste(art_img, (x + 2, y + 2), art_img)
        except: pass

    # 3. Artifact Level
    raw_level = relic_core.get("level", 1)
    display_level = f"+{raw_level - 1}"
    draw.text((x + 105, y + 20), display_level, font=font, fill=(255, 204, 0), stroke_width=1, stroke_fill=(0,0,0),anchor="rm")

    # 4. Rarity Stars (NEW)
    rarity = flat.get("rankLevel", 5) # Default to 5 if not found
    try:
        # Load the star image based on rankLevel (e.g., Star5.png)
        star_img = Image.open(f"{STARS_PATH}Star{rarity}.png").convert("RGBA")
        
        # Adjust height/width based on your actual Star PNG dimensions
        star_img.thumbnail((70, 20), Image.Resampling.LANCZOS) 
        
        # Paste stars below the level text
        base_image.paste(star_img, (x + 30, y + 90), star_img)
    except Exception as e:
        print(f"Error loading star image Star{rarity}.png: {e}")

    # 5. Main Stat (reliquaryMainstat)
    main_data = flat.get("reliquaryMainstat", {})
    main_prop = main_data.get("mainPropId")
    main_val = main_data.get("statValue")

    if main_prop:
        main_icon_name = STAT_MAP.get(main_prop, "atk").lower()
        try:
            m_icon = Image.open(f"{ICONS_PATH}{main_icon_name}.png").convert("RGBA").resize((24, 28))
            base_image.paste(m_icon, (x + 5, y + 5), m_icon)
        except: pass

        is_percent = any(k in main_prop for k in ["PERCENT", "CRITICAL", "EFFICIENCY", "HURT"])
        main_val_str = f"{main_val}%" if is_percent else f"{int(main_val)}"
        draw.text((x + 105, y + 80), main_val_str, font=font, fill=(255, 255, 255), stroke_width=1, stroke_fill=(0,0,0),anchor="rm")

    # 6. Sub-Stat Grid
    grid_x, grid_y = x + 120, y + 8
    cell_w, cell_h = 125, 40 
    gap_x, gap_y = 15, 14
    sub_stats = flat.get("reliquarySubstats", [])
    
    for i, stat in enumerate(sub_stats[:4]):
        col, row = i % 2, i // 2
        bx, by = grid_x + (col * (cell_w + gap_x)), grid_y + (row * (cell_h + gap_y))
        draw.rounded_rectangle([bx, by, bx + cell_w, by + cell_h], radius=20, fill=(10, 10, 15, 180))
        
        prop_id = stat.get("appendPropId")
        icon_file = STAT_MAP.get(prop_id, "atk")
        try:
            s_icon = Image.open(f"{ICONS_PATH}{icon_file.lower()}.png").convert("RGBA").resize((24, 24))
            base_image.paste(s_icon, (bx + 10, by + 8), s_icon)
        except: pass
        
        val = stat.get("statValue")
        is_percent = any(k in prop_id for k in ["PERCENT", "CRITICAL", "EFFICIENCY", "HURT"])
        val_str = f"+{val}%" if is_percent else f"+{val}"
        draw.text((bx + 45, by + 20), val_str, font=font, fill=(255, 255, 255), anchor="lm")
async def draw_all_artifacts(session, background, me_char_data, them_char_data, font):
    tasks = []
    
    def get_relics(data):
        relics = [e for e in data.get("equipList", []) if "reliquary" in e]
        
        return sorted(relics, key=lambda x: EQUIP_ORDER.index(x.get("flat", {}).get("equipType", "")) if x.get("flat", {}).get("equipType") in EQUIP_ORDER else 99)

    me_relics = get_relics(me_char_data)
    them_relics = get_relics(them_char_data)

    for i, art in enumerate(me_relics[:5]):
        tasks.append(draw_artifact_card(session, background, 1485, 250 + (i * 125), art, font))
            
    for i, art in enumerate(them_relics[:5]):
        tasks.append(draw_artifact_card(session, background, 1090, 250 + (i * 125), art, font))
    
    if tasks:
        await asyncio.gather(*tasks)

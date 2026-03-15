import io
import requests
from PIL import Image, ImageDraw, ImageFont

def get_asset(url):
    try:
        response = requests.get(url, timeout=5)
        return Image.open(io.BytesIO(response.content)).convert("RGBA")
    except:
        return None

def generate_profile_card(data):
    # 1. Create the Canvas
    width, height = 1000, 600
    try:
        # Load your background image from the VPS
        card = Image.open("bg.png").convert("RGBA").resize((width, height))
    except:
        card = Image.new('RGBA', (width, height), color=(20, 20, 20, 255))

    draw = ImageDraw.Draw(card)
    player = data.get("playerInfo", {})
    
    # 2. Load a better font (Upload a .ttf file to your /tgbot folder)
    try:
        font_big = ImageFont.truetype("Arial.ttf", 45)
        font_small = ImageFont.truetype("Arial.ttf", 25)
    except:
        font_big = font_small = ImageFont.load_default()

    # 3. Draw Header Stats (UID, AR, etc.)
    # Draw a semi-transparent box for readability
    overlay = Image.new('RGBA', (width, height), (0,0,0,0))
    ol_draw = ImageDraw.Draw(overlay)
    ol_draw.rounded_rectangle([600, 40, 950, 220], radius=15, fill=(0,0,0,160), outline="red", width=2)
    card = Image.alpha_composite(card, overlay)
    draw = ImageDraw.Draw(card)

    draw.text((620, 60), f"UID: {data.get('uid')}", fill="red", font=font_small)
    draw.text((60, 60), player.get("nickname", "Traveler"), fill="white", font=font_big)
    draw.text((620, 110), f"AR {player.get('level')}", fill="white", font=font_small)
    draw.text((620, 160), f"🏆 {player.get('finishAchievementNum')}", fill="white", font=font_small)

    # 4. Paste Character Icons
    # Showcase characters are usually in 'avatarIdList' or 'showcaseNextCharacters'
    characters = player.get("showcaseNextCharacters", [])
    x_offset = 60
    for char in characters[:4]: # Let's start with 4 characters
        icon_url = f"https://enka.network/ui/UI_AvatarIcon_{char}.png" # Note: IDs need mapping
        icon = get_asset(icon_url)
        if icon:
            icon = icon.resize((120, 120))
            card.paste(icon, (x_offset, 350), icon)
            x_offset += 150

    # 5. Final Export
    final = card.convert("RGB")
    buf = io.BytesIO()
    final.save(buf, format='PNG')
    buf.seek(0)
    return buf
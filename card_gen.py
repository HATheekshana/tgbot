import io
import requests
from PIL import Image, ImageDraw, ImageFont

def generate_profile_card(data):
    # 1. Setup Canvas
    width, height = 1000, 600
    try:
        # Try to load your background
        card = Image.open("bg.png").convert("RGBA").resize((width, height))
    except:
        # Fallback to dark grey if bg is missing
        card = Image.new('RGBA', (width, height), color=(18, 18, 18, 255))

    draw = ImageDraw.Draw(card)
    player = data.get("playerInfo", {})
    
    # 2. LOAD FONTS (CRITICAL: Replace "font.ttf" with your actual filename)
    try:
        # Increase these numbers for bigger text
        font_large = ImageFont.truetype("arial.ttf", 50) 
        font_medium = ImageFont.truetype("arial.ttf", 35)
        font_small = ImageFont.truetype("arial.ttf", 25)
    except:
        # If font file is missing, text will stay tiny!
        font_large = font_medium = font_small = ImageFont.load_default()

    # 3. Draw the Red Stats Box (Right Side)
    # Using rounded_rectangle for that clean look
    draw.rounded_rectangle([600, 50, 950, 280], radius=20, outline="red", width=3)
    
    # 4. Add the Data (Positioned correctly)
    nickname = player.get("nickname", "RenxZero")
    uid = data.get("uid", "1819096557")
    ar = player.get("level", 57)
    achievements = player.get("finishAchievementNum", 772)

    # Nickname (Top Left)
    draw.text((50, 50), nickname, fill="white", font=font_large)

    # Stats inside the red box
    draw.text((630, 80), f"UID: {uid}", fill="red", font=font_small)
    draw.text((630, 150), f"AR {ar}", fill="white", font=font_medium)
    draw.text((630, 220), f"🏆 {achievements}", fill="white", font=font_medium)

    # 5. Convert and Return
    final = card.convert("RGB")
    buf = io.BytesIO()
    final.save(buf, format='PNG')
    buf.seek(0)
    return buf
import io
import requests
from PIL import Image, ImageDraw, ImageFont

def generate_profile_card(data):
    # 1. Create a dark background (width 900, height 500)
    card = Image.new('RGB', (900, 500), color=(20, 20, 20))
    draw = ImageDraw.Draw(card)
    
    # 2. Extract Data
    player = data.get("playerInfo", {})
    nickname = player.get("nickname", "Traveler")
    level = player.get("level", 1)
    uid = data.get("uid", "000000000")
    achievements = player.get("finishAchievementNum", 0)

    # 3. Draw Design Elements
    # Draw a red rectangle for the UID header
    draw.rectangle([350, 20, 550, 50], outline="red", width=2)
    
    # 4. Add Text
    # Note: On your VPS, you may need to provide the full path to a .ttf font file
    try:
        font_large = ImageFont.load_default() # Replace with a real .ttf for better looks
    except:
        font_large = ImageFont.load_default()

    draw.text((360, 25), f"UID: {uid}", fill="red", font=font_large)
    draw.text((350, 70), nickname, fill="white", font=font_large)
    draw.text((700, 40), f"AR: {level}", fill="red", font=font_large)
    draw.text((700, 80), f"Achievements: {achievements}", fill="white", font=font_large)

    # 5. Convert to Bytes for Telegram
    img_byte_arr = io.BytesIO()
    card.save(img_byte_arr, format='PNG')
    img_byte_arr.seek(0)
    return img_byte_arr
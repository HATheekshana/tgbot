import io
import requests
from PIL import Image, ImageDraw, ImageFont

def get_image_from_url(url):
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            return Image.open(io.BytesIO(response.content)).convert("RGBA")
    except:
        return None
    return None

def generate_profile_card(data):
    # 1. Base Canvas (Matching the wide ratio of your image)
    width, height = 1000, 600
    card = Image.new('RGBA', (width, height), color=(20, 20, 20, 255))
    
    # Optional: Load bg.png if you have one, else keep it dark
    try:
        bg = Image.open("bg.png").convert("RGBA").resize((width, height))
        card.paste(bg, (0,0))
    except:
        pass

    draw = ImageDraw.Draw(card)
    player = data.get("playerInfo", {})
    
    # 2. Draw the Header Info (Right side)
    # We use rounded_rectangle to get that "pill" look from your image
    stats = [
        (f"UID: {data.get('uid')}", "red"),
        (f"AR: {player.get('level')}", "white"),
        (f"Achievements: {player.get('finishAchievementNum')}", "white")
    ]
    
    y_offset = 50
    for text, color in stats:
        draw.rounded_rectangle([600, y_offset, 950, y_offset + 40], radius=20, fill=(0,0,0,180), outline="red")
        draw.text((620, y_offset + 10), text, fill=color)
        y_offset += 60

    # 3. Handle the Big Profile Avatar (Center Circle)
    icon_id = player.get("profilePicture", {}).get("baseIcon", "UI_AvatarIcon_Side_PlayerBoy")
    avatar = get_image_from_url(f"https://enka.network/ui/{icon_id}.png")
    if avatar:
        avatar = avatar.resize((200, 200))
        # Create a circular mask
        mask = Image.new('L', (200, 200), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.ellipse((0, 0, 200, 200), fill=255)
        card.paste(avatar, (400, 50), mask)
        # Draw red border around circle
        draw.ellipse((400, 50, 600, 250), outline="red", width=3)

    # 4. Character Showcase (The Grid at the bottom)
    showcase = player.get("showcaseNextCharacters", []) # Enka field for displayed chars
    x_start, y_start = 50, 350
    
    for i, char in enumerate(showcase[:8]): # Limit to top 8
        # Fetch individual character icon
        # In a real setup, you'd map char ID to Icon Name
        # For now, let's use a placeholder or the first available icon
        col = i % 4
        row = i // 4
        
        # Draw a small box for each character
        box_x = x_start + (col * 230)
        box_y = y_start + (row * 120)
        draw.rounded_rectangle([box_x, box_y, box_x + 200, box_y + 100], radius=10, fill=(50,50,50,150), outline="red")
        draw.text((box_x + 10, box_y + 70), f"Level {player.get('level')}", fill="white")

    # 5. Finalize
    final_card = card.convert("RGB")
    img_byte_arr = io.BytesIO()
    final_card.save(img_byte_arr, format='PNG')
    img_byte_arr.seek(0)
    return img_byte_arr
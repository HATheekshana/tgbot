import random
import io
import requests
import logging
from PIL import Image, ImageDraw, ImageFont
from aiogram.types import BufferedInputFile

from data import weapons3, characters4, characters5, rare

def combine_images(cha_path, bg_path, display_name, rarity):
    try:
        # 1. Background Loader
        if isinstance(bg_path, str) and bg_path.startswith("http"):
            bg_response = requests.get(bg_path, timeout=10)
            if bg_response.status_code != 200:
                raise ValueError(f"BG Download Failed: {bg_response.status_code}")
            background = Image.open(io.BytesIO(bg_response.content)).convert("RGBA")
        else:
            background = Image.open(bg_path).convert("RGBA")

        # 2. Character Loader
        if hasattr(cha_path, 'path'): # Handling FSInputFile for Rares
            character = Image.open(cha_path.path).convert("RGBA")
        elif isinstance(cha_path, str) and cha_path.startswith("http"):
            cha_response = requests.get(cha_path, timeout=10)
            if cha_response.status_code != 200:
                # This is likely the problem! A 404 error from GitHub.
                raise ValueError(f"Char Download Failed: {cha_response.status_code} for {cha_path}")
            character = Image.open(io.BytesIO(cha_response.content)).convert("RGBA")
        else:
            character = Image.open(cha_path).convert("RGBA")
        # 2. Resize and Paste character
        scale = background.height / character.height
        new_size = (int(character.width * scale), background.height)
        character = character.resize(new_size, Image.Resampling.LANCZOS)
        x_offset = (background.width - character.width) // 2
        background.paste(character, (x_offset, 0), character)

        # 3. Setup Drawing
        draw = ImageDraw.Draw(background)
        try:
            # Replaced 450/350 with 90/70 for better balance
            font_name = ImageFont.truetype("ARIALBD 1.TTF", 80)  # Character Name
            font_stars = ImageFont.truetype("Arial-Unicode-MS.ttf", 60) # Rarity Stars
        except:
            font_name = ImageFont.load_default()
            font_stars = ImageFont.load_default()

        if isinstance(rarity, int):
             stars_text = "★" * rarity 
        else:
            stars_text = str(rarity)
        
        margin_right = 50
        margin_bottom = 40
        line_spacing = 5

        # Calculate Name Dimensions
        bbox_n = draw.textbbox((0, 0), display_name, font=font_name)
        nw, nh = bbox_n[2] - bbox_n[0], bbox_n[3] - bbox_n[1]

        # Calculate Stars Dimensions
        bbox_s = draw.textbbox((0, 0), stars_text, font=font_stars)
        sw, sh = bbox_s[2] - bbox_s[0], bbox_s[3] - bbox_s[1]

        # Positions (Right Aligned)
        # Name on top, Stars directly below it
        nx = background.width - nw - margin_right
        ny = background.height - nh - sh - margin_bottom - line_spacing

        sx = background.width - sw - margin_right
        sy = background.height - sh - margin_bottom

        # --- NEW: ADD SUBTLE SHADOWS ---
        # Draw soft shadow first (offset by 2 for a "little" shadow)
        # (0, 0, 0) is black, 150 is the alpha (transparency)
        draw.text((nx+2, ny+2), display_name, font=font_name, fill=(0, 0, 0, 150))
        draw.text((sx+2, sy+2), stars_text, font=font_stars, fill=(0, 0, 0, 150))

        # --- Draw Main Text ---
        # Draw the main White text
        draw.text((nx, ny), display_name, font=font_name, fill=(255, 255, 255))
        # Stars (Yellow/Gold color for stars: 255, 204, 0)
        draw.text((sx, sy), stars_text, font=font_stars, fill=(255, 204, 0)) 

        return background

    except Exception as e:
        logging.error(f"Image Error: {e}")
        return Image.new("RGBA", (1280, 720), (45, 20, 84, 255))

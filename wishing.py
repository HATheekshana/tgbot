import random
import io
import asyncio
import logging
from PIL import Image, ImageDraw, ImageFont
from aiogram.types import BufferedInputFile
import aiohttp

from data import weapons3, characters4, characters5, rare

async def download_image_async(url: str, timeout: int = 10) -> Image.Image:
    """Async download image from URL using aiohttp"""
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as response:
            if response.status != 200:
                raise ValueError(f"Download Failed: {response.status} for {url}")
            content = await response.read()
            return Image.open(io.BytesIO(content)).convert("RGBA")

def render_image_with_text(bg_image: Image.Image, character_image: Image.Image, display_name: str, rarity) -> Image.Image:
    """CPU-intensive image rendering (runs in thread executor)"""
    # Resize and Paste character
    scale = bg_image.height / character_image.height
    new_size = (int(character_image.width * scale), bg_image.height)
    character_image = character_image.resize(new_size, Image.Resampling.LANCZOS)
    x_offset = (bg_image.width - character_image.width) // 2
    bg_image.paste(character_image, (x_offset, 0), character_image)

    # Setup Drawing
    draw = ImageDraw.Draw(bg_image)
    try:
        font_name = ImageFont.truetype("ARIALBD 1.TTF", 80)
        font_stars = ImageFont.truetype("Arial-Unicode-MS.ttf", 60)
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
    nx = bg_image.width - nw - margin_right
    ny = bg_image.height - nh - sh - margin_bottom - line_spacing

    sx = bg_image.width - sw - margin_right
    sy = bg_image.height - sh - margin_bottom

    # Draw shadows
    draw.text((nx+2, ny+2), display_name, font=font_name, fill=(0, 0, 0, 150))
    draw.text((sx+2, sy+2), stars_text, font=font_stars, fill=(0, 0, 0, 150))

    # Draw main text
    draw.text((nx, ny), display_name, font=font_name, fill=(255, 255, 255))
    draw.text((sx, sy), stars_text, font=font_stars, fill=(255, 204, 0)) 

    return bg_image

async def combine_images(cha_path, bg_path, display_name, rarity):
    """Async image combination with non-blocking HTTP and threading for CPU work"""
    try:
        loop = asyncio.get_event_loop()
        
        # 1. Load Background (async HTTP or local file)
        if isinstance(bg_path, str) and bg_path.startswith("http"):
            background = await download_image_async(bg_path)
        else:
            background = await loop.run_in_executor(None, lambda: Image.open(bg_path).convert("RGBA"))

        # 2. Load Character (async HTTP or local file)
        if hasattr(cha_path, 'path'):  # FSInputFile for Rares
            character = await loop.run_in_executor(None, lambda: Image.open(cha_path.path).convert("RGBA"))
        elif isinstance(cha_path, str) and cha_path.startswith("http"):
            character = await download_image_async(cha_path)
        else:
            character = await loop.run_in_executor(None, lambda: Image.open(cha_path).convert("RGBA"))

        # 3. CPU-intensive rendering in thread pool
        result = await loop.run_in_executor(None, render_image_with_text, background, character, display_name, rarity)
        return result

    except Exception as e:
        logging.error(f"Image Error: {e}")
        return Image.new("RGBA", (1280, 720), (45, 20, 84, 255))

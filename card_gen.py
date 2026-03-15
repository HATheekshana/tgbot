from enkacard import encbanner
import asyncio
import io

async def generate_profile_card(uid):
    # This library handles the background, fonts, and icons automatically
    # '1' is the template ID. You can change this (1-5) for different looks.
    async with encbanner.ENC(uid=str(uid)) as encard:
        result = await encard.creat(1) 
        
        # The result contains the image data in bytes
        # We wrap it in BytesIO so aiogram can send it
        image_data = io.BytesIO(result)
        image_data.seek(0)
        return image_data
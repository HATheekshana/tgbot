from aioenkanetworkcard import encbanner
import io

async def generate_profile_card(uid):
    try:
        async with encbanner.ENC() as encard:
            # 1. Fetch data for the UID
            ENCpy = await encard.enc(uids=str(uid))
            
            # 2. Create the card (using template 4 as per your friend's code)
            # This returns: {"card": {"1-4": Image, "5-8": Image}}
            result = await encard.creat(ENCpy, 4)
            
            # 3. Get the first image (characters 1-4)
            pill_image = result.get("card", {}).get("1-4")
            
            if not pill_image:
                return None

            # 4. Convert Pillow Image to Bytes for Telegram
            image_buffer = io.BytesIO()
            # We save as PNG or JPEG
            pill_image.save(image_buffer, format='PNG')
            image_buffer.seek(0)
            
            return image_buffer
            
    except Exception as e:
        print(f"Error in card_gen: {e}")
        return None
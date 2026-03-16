import io
from aioenkanetworkcard import encbanner

async def generate_profile_card(data: dict):
    """
    Takes raw JSON data from Enka API and returns a PIL Image object.
    """
    try:
        # We use the ENC context manager to handle the drawing assets
        async with encbanner.ENC() as encard:
            # We use 'creat' instead of 'enc' to bypass UID validation
            # 4 is the template ID (you can change this to 1, 2, or 3)
            result = await encard.creat(data, 4)
            
            # The library returns a dict containing the image
            cards = result.get("card", {})
            pill_image = cards.get("1-4")
            
            return pill_image
    except Exception as e:
        print(f"Rendering Error: {e}")
        return None
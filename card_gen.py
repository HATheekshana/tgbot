async def generate_profile_card(uid):
    try:
        async with encbanner.ENC(uid=str(uid)) as encard:
            # Check if encard actually fetched data
            if not encard or not hasattr(encard, 'creat'):
                return None
                
            result = await encard.creat(1)
            
            if not result:
                return None

            image_data = io.BytesIO(result)
            image_data.seek(0)
            return image_data
    except Exception as e:
        print(f"EnkaCard Library Error: {e}")
        return None
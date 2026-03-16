import io
import traceback
from aioenkanetworkcard import encbanner
from enkanetwork.model.base import EnkaNetworkResponse
from enkanetwork import Assets, Language # Added Language

async def generate_profile_card(data: dict):
    try:
        # 1. FORCE global language settings
        # This fixes the KeyError: <Language.EN: 'en'>
        Assets.LANGS = Language.EN 
        Assets.reload_assets() 

        # 2. Wrap the dictionary into the EnkaNetworkResponse object
        # The library needs this object to find .characters and .player
        wrapped_data = EnkaNetworkResponse.parse_obj(data)

        async with encbanner.ENC() as encard:
            # 3. Request Template 4
            # Using Template 4 as you originally wanted
            result = await encard.creat(wrapped_data, 4) 
            
            if not result or "card" not in result:
                print("❌ Library Error: The .creat() method returned no card.")
                return None

            # 4. Get the image from the dictionary (Key '1-4' for Template 4)
            pill_image = result.get("card", {}).get("1-4")
            
            if pill_image:
                print("✅ Template 4 Rendered Successfully!")
                
            return pill_image

    except Exception as e:
        print("--- 🚨 FINAL SYSTEM DEBUG 🚨 ---")
        traceback.print_exc()
        return None
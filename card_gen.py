import io
import traceback
from aioenkanetworkcard import encbanner
from enkanetwork.model.base import EnkaNetworkResponse
from enkanetwork import Assets, Language # Added Language import

async def generate_profile_card(data: dict):
    try:
        # 1. FORCE the library to recognize English 
        # This fixes: KeyError: <Language.EN: 'en'>
        Assets.LANGS = Language.EN 
        Assets.reload_assets() 

        # 2. Wrap the raw dictionary data
        # This converts keys to the Object format the drawer expects
        wrapped_data = EnkaNetworkResponse.parse_obj(data)

        async with encbanner.ENC() as encard:
            # 3. Use Template 4
            result = await encard.creat(wrapped_data, 1) 
            
            if not result or "card" not in result:
                print("❌ Library Error: .creat() returned an empty result.")
                return None

            # 4. Extract the image for Template 4
            pill_image = result.get("card", {}).get("1-4")
            
            if pill_image:
                print("✅ Template 4 rendered successfully!")
                
            return pill_image

    except Exception as e:
        print("--- 🚨 FINAL SYSTEM DEBUG 🚨 ---")
        traceback.print_exc()
        return None
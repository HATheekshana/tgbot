import io
import traceback
from aioenkanetworkcard import encbanner
from enkanetwork.model.base import EnkaNetworkResponse
from enkanetwork import Assets, Language # Added Language import

async def generate_profile_card(data: dict):
    try:
        # 1. Force the library to recognize English
        # This fixes the KeyError: <Language.EN: 'en'>
        Assets.LANGS = Language.EN 
        Assets.reload_assets() 

        # 2. Wrap the raw dictionary
        wrapped_data = EnkaNetworkResponse.parse_obj(data)

        async with encbanner.ENC() as encard:
            # 3. Request Template 4
            result = await encard.creat(wrapped_data, 4) 
            
            if not result or "card" not in result:
                print("❌ Library Error: No card generated.")
                return None

            pill_image = result.get("card", {}).get("1-4")
            
            if pill_image:
                print("✅ Success! Template 4 rendered.")
                
            return pill_image

    except Exception as e:
        print("--- 🚨 FINAL SYSTEM DEBUG 🚨 ---")
        traceback.print_exc()
        return None
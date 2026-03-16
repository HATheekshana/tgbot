import io
import traceback
from aioenkanetworkcard import encbanner
from enkanetwork.model.base import EnkaNetworkResponse
from enkanetwork import Assets 

async def generate_profile_card(data: dict):
    try:
        # 1. Initialize assets (Removed 'await' because it is not a coroutine)
        Assets.reload_assets() 

        # 2. Wrap the raw dictionary data
        wrapped_data = EnkaNetworkResponse.parse_obj(data)

        async with encbanner.ENC() as encard:
            # 3. Use Template 4
            result = await encard.creat(wrapped_data, 4) 
            
            if not result or "card" not in result:
                print("❌ Library Error: result['card'] is empty.")
                return None

            # Template 4 returns the image with the key '1-4'
            pill_image = result.get("card", {}).get("1-4")
            
            if pill_image:
                print("✅ Rendered Template 4 successfully!")
                
            return pill_image

    except Exception as e:
        print("--- 🚨 FINAL DEBUG LOG 🚨 ---")
        traceback.print_exc()
        return None
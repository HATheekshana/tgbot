import io
import traceback
from aioenkanetworkcard import encbanner
from enkanetwork.model.base import EnkaNetworkResponse
from enkanetwork import Assets # Important new import

async def generate_profile_card(data: dict):
    try:
        # 1. FORCE ASSET RELOAD
        # This ensures the 'artifact_props' key actually exists in memory
        await Assets.reload_assets() 

        # 2. Wrap the data
        wrapped_data = EnkaNetworkResponse.parse_obj(data)

        async with encbanner.ENC() as encard:
            # We use template 1 for testing stability
            result = await encard.creat(wrapped_data, 1) 
            
            if not result or "card" not in result:
                print("❌ Library Error: Result dictionary is empty.")
                return None

            pill_image = result.get("card", {}).get("1-1")
            return pill_image

    except Exception as e:
        print("--- 🚨 FINAL DEBUG LOG 🚨 ---")
        traceback.print_exc()
        return None
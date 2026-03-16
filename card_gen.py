import io
import traceback
from aioenkanetworkcard import encbanner
from enkanetwork import EnkaNetworkAPI # Correct class name

async def generate_profile_card(data: dict):
    try:
        # 1. Use the correct API client to wrap the data
        # This properly initializes the internal 'artifact_props' and 'Language' maps
        client = EnkaNetworkAPI()
        wrapped_data = client._parse_data(data)

        async with encbanner.ENC() as encard:
            # 2. Request Template 4
            result = await encard.creat(wrapped_data, 4) 
            
            if not result or "card" not in result:
                print("❌ Library Error: .creat() returned an empty result.")
                return None

            # 3. Extract the image for Template 4 (Key '1-4')
            pill_image = result.get("card", {}).get("1-4")
            
            if pill_image:
                print("✅ Template 4 rendered successfully!")
                
            return pill_image

    except Exception as e:
        print("--- 🚨 RENDERING ERROR 🚨 ---")
        traceback.print_exc()
        return None
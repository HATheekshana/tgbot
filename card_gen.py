import io
import traceback
from aioenkanetworkcard import encbanner
from enkanetwork import EnkaNetworkAPI

async def generate_profile_card(data: dict):
    try:
        # 1. Initialize the official API client
        client = EnkaNetworkAPI()
        
        # 2. Set language and parse the raw dictionary
        # This is the official way to turn JSON into the required Object
        client.lang = "en"
        wrapped_data = client.parse_data(data)

        async with encbanner.ENC() as encard:
            # 3. Request Template 4
            result = await encard.creat(wrapped_data, 1) 
            
            if not result or "card" not in result:
                print("❌ Library Error: .creat() returned an empty result.")
                return None

            # 4. Extract the image for Template 4 (Key '1-4')
            pill_image = result.get("card", {}).get("1-4")
            
            if pill_image:
                print("✅ Template 4 rendered successfully!")
                
            return pill_image

    except Exception as e:
        print("--- 🚨 RENDERING ERROR 🚨 ---")
        traceback.print_exc()
        return None
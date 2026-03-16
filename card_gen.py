import io
import traceback
from aioenkanetworkcard import encbanner
from enkanetwork import EnkaNetwork # Using the main client for parsing

async def generate_profile_card(data: dict):
    try:
        # 1. Use the EnkaNetwork client to wrap the data
        # This properly initializes all internal assets and languages
        client = EnkaNetwork()
        wrapped_data = client._parse_data(data)

        async with encbanner.ENC() as encard:
            # 2. Request Template 4
            result = await encard.creat(wrapped_data, 4) 
            
            if not result or "card" not in result:
                print("❌ Library Error: .creat() returned an empty result.")
                return None

            # 3. Extract the image for Template 4
            pill_image = result.get("card", {}).get("1-4")
            
            if pill_image:
                print("✅ Template 4 rendered successfully!")
                
            return pill_image

    except Exception as e:
        print("--- 🚨 FINAL SYSTEM DEBUG 🚨 ---")
        traceback.print_exc()
        return None
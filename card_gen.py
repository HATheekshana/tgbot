import io
import traceback
from aioenkanetworkcard import encbanner
from enkanetwork.model.base import EnkaNetworkResponse # Add this import

async def generate_profile_card(data: dict):
    try:
        # 1. Convert the raw dictionary into the Object the library wants
        # This adds the .characters attribute the error was complaining about
        wrapped_data = EnkaNetworkResponse.parse_obj(data)

        async with encbanner.ENC() as encard:
            print("🎨 Rendering with wrapped data...")
            
            # 2. Pass the WRAPPED data, not the raw 'data'
            result = await encard.creat(wrapped_data, 1) 
            
            if not result or "card" not in result:
                print("❌ Library returned empty result.")
                return None

            cards = result.get("card", {})
            # For Template 1, use '1-1'. For Template 4, use '1-4'.
            pill_image = cards.get("1-1") 
            
            return pill_image

    except Exception as e:
        print("--- 🚨 RENDERING ERROR 🚨 ---")
        traceback.print_exc() 
        return None
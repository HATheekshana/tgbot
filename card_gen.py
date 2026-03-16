import io
import traceback
from aioenkanetworkcard import encbanner

async def generate_profile_card(data: dict):
    try:
        # We use template 1 for testing because it has the fewest requirements
        async with encbanner.ENC() as encard:
            print("🎨 Starting render for template 1...")
            result = await encard.creat(data, 1) 
            
            if not result or "card" not in result:
                # If result is empty, the library failed internally without raising an error
                print("❌ Library Error: .creat() returned an empty dictionary.")
                return None

            cards = result.get("card", {})
            # Template 1 uses index "1-1"
            pill_image = cards.get("1-1")
            
            if pill_image:
                print("✅ Render successful!")
            return pill_image

    except Exception as e:
        print("--- 🚨 CRITICAL RENDERING ERROR 🚨 ---")
        traceback.print_exc() 
        print("---------------------------------------")
        return None
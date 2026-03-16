import io
import traceback
from aioenkanetworkcard import encbanner
from enkanetwork.model.base import EnkaNetworkResponse
from enkanetwork import Assets, Language

async def generate_profile_card(data: dict):
    try:
        # 1. FORCE the library to load its English database
        # This prevents the KeyError: <Language.EN: 'en'>
        Assets.LANGS = Language.EN
        Assets.reload_assets()
        
        # 2. Manually validate and wrap the raw JSON dictionary
        # We use model_validate (Pydantic v2) or parse_obj (Pydantic v1)
        try:
            wrapped_data = EnkaNetworkResponse.model_validate(data)
        except AttributeError:
            wrapped_data = EnkaNetworkResponse.parse_obj(data)

        async with encbanner.ENC() as encard:
            # 3. Request Template 4
            result = await encard.creat(wrapped_data, 4) 
            
            if not result or "card" not in result:
                print("❌ Library Error: .creat() returned an empty result.")
                return None

            # 4. Extract image (Key '1-4')
            pill_image = result.get("card", {}).get("1-4")
            
            if pill_image:
                print("✅ Template 4 rendered successfully!")
                
            return pill_image

    except Exception as e:
        print("--- 🚨 FINAL MANUAL DEBUG 🚨 ---")
        traceback.print_exc()
        return None
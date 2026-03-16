import io
import traceback
from aioenkanetworkcard import encbanner
from enkanetwork.model.base import EnkaNetworkResponse
from enkanetwork import Assets, Language

async def generate_profile_card(data: dict):
    try:
        # 1. MANUALLY POPULATE THE MISSING MAP
        # Since 'en.json' is missing, we link the internal fight_props to the EN key
        if not Assets.HASH_MAP:
            Assets.reload_assets()
        
        # This line "plugs the leak" by manually creating the missing 'en' key
        # using the data already loaded in Assets.DATA
        if Language.EN not in Assets.HASH_MAP:
            Assets.HASH_MAP[Language.EN] = Assets.DATA.get("fight_props", {})

        # 2. Wrap the data (Handling both Pydantic v1 and v2)
        try:
            wrapped_data = EnkaNetworkResponse.model_validate(data)
        except AttributeError:
            wrapped_data = EnkaNetworkResponse.parse_obj(data)

        async with encbanner.ENC() as encard:
            # 3. Render Template 4
            result = await encard.creat(wrapped_data, 4) 
            
            if not result or "card" not in result:
                print("❌ Library Error: Result dictionary is empty.")
                return None

            pill_image = result.get("card", {}).get("1-4")
            return pill_image

    except Exception as e:
        print("--- 🚨 EMERGENCY ASSET DEBUG 🚨 ---")
        traceback.print_exc()
        return None
import io
import traceback
from aioenkanetworkcard import encbanner
from enkanetwork.model.base import EnkaNetworkResponse
from enkanetwork import Assets, Language

async def generate_profile_card(data: dict):
    try:
        # 1. HARD-INJECT English into the library memory
        # This force-kills the KeyError: <Language.EN: 'en'>
        if not Assets.HASH_MAP:
            Assets.LANGS = Language.EN
            Assets.reload_assets()
        
        # Manually ensure 'en' key exists in the hash map
        if Language.EN not in Assets.HASH_MAP:
            Assets.HASH_MAP[Language.EN] = {}
            Assets.reload_assets()

        # 2. Wrap and Render
        wrapped_data = EnkaNetworkResponse.parse_obj(data)

        async with encbanner.ENC() as encard:
            # We use Template 4 as requested
            result = await encard.creat(wrapped_data, 4) 
            
            if not result or "card" not in result:
                print("❌ Library Error: .creat() returned an empty result.")
                return None

            pill_image = result.get("card", {}).get("1-4")
            return pill_image

    except Exception as e:
        print("--- 🚨 SYSTEM-LEVEL ERROR 🚨 ---")
        traceback.print_exc()
        return None
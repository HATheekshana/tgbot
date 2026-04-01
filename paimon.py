import genshin
from motor.motor_asyncio import AsyncIOMotorCollection
import asyncio
# Note: We pass wish_col as an argument to the functions 
# so this file doesn't need to know about your main DB setup.

async def fetch_and_save_wishes(user_id: str, authkey: str, wish_col: AsyncIOMotorCollection):
    client = genshin.Client()
    client.set_authkey(authkey)
    client.region = genshin.Region.OVERSEAS
    
    new_count = 0
    # 301=Char, 302=Weapon, 200=Standard, 400=Char2
    for banner_type in [301, 302, 200, 400]: 
        await asyncio.sleep(1.5)
        try:
            async for wish in client.wish_history(banner_type):
                result = await wish_col.update_one(
                    {"id": wish.id}, 
                    {"$set": {
                        "user_id": user_id,
                        "uid": wish.uid,
                        "name": wish.name,
                        "rarity": wish.rarity,
                        "type": wish.type,
                        "banner_type": banner_type,
                        "time": wish.time
                    }},
                    upsert=True
                )
                if result.upserted_id:
                    new_count += 1
        except Exception as e:
            print(f"Error fetching banner {banner_type}: {e}")
            
    return new_count

async def calculate_pity(user_id: str, banner_type: int, wish_col: AsyncIOMotorCollection):
    cursor = wish_col.find({"user_id": user_id, "banner_type": banner_type}).sort("time", -1)
    wishes = await cursor.to_list(length=None)
    
    if not wishes:
        return {"total": 0, "pity_5": 0, "pity_4": 0, "last_10": []}

    pity_5 = 0
    pity_4 = 0
    
    for wish in wishes:
        if wish['rarity'] == 5: break
        pity_5 += 1
        
    for wish in wishes:
        if wish['rarity'] >= 4: break
        pity_4 += 1

    last_10 = [w['name'] for w in wishes[:10]]
    
    return {
        "total": len(wishes),
        "pity_5": pity_5,
        "pity_4": pity_4,
        "last_10": last_10
    }
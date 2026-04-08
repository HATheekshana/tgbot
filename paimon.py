import genshin
from motor.motor_asyncio import AsyncIOMotorCollection
import asyncio

async def fetch_and_save_wishes(user_id: str, authkey: str, wish_col: AsyncIOMotorCollection):
    client = genshin.Client()
    client.set_authkey(authkey)
    client.region = genshin.Region.OVERSEAS
    
    new_count = 0
    for banner_type in [301, 302, 200, 400]: 
        await asyncio.sleep(1.5)
        try:
            async for wish in client.wish_history(banner_type):
                # CHECK HERE: If this wish is already in our DB
                already_saved = await wish_col.find_one({"id": wish.id})
                if already_saved:
                    break 

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
        return {
            "total": 0, 
            "pity_5": 0, 
            "pity_4": 0, 
            "last_10": [], 
            "five_star_history": []
        }

    pity_5 = 0
    pity_4 = 0
    five_star_history = []
    
    # Current Pity
    for wish in wishes:
        if wish['rarity'] == 5: break
        pity_5 += 1
    for wish in wishes:
        if wish['rarity'] >= 4: break
        pity_4 += 1

    # Five Star History Logic
    temp_count = 0
    for wish in wishes:
        temp_count += 1
        if wish['rarity'] == 5:
            five_star_history.append({"name": wish['name'], "pulls": temp_count})
            temp_count = 0
            if len(five_star_history) == 5: break

    # ADD THIS LINE BACK:
    last_10 = [w['name'] for w in wishes[:10]]

    return {
        "total": len(wishes),
        "pity_5": pity_5,
        "pity_4": pity_4,
        "last_10": last_10, # <--- This fixes the KeyError
        "five_star_history": five_star_history
    }
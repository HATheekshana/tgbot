import asyncio
import genshin

# Your Central Cookie Store
COOKIES = {
    "ltuid_v2": "471000302",
    "ltoken_v2": "v2_CAISDGM5b3FhcTNzM2d1OBokZTFmZTViNmItZDgxOS00MzNlLWJiZDktYWJkMTEzMWY1ZmY0IKKB680GKK2E3O0DMO7Jy-ABQgtiYnNfb3ZlcnNlYVhqagJTRw.osC6aQAAAAAB.MEQCIC1EZw11MIyxRrnXaBoYbja47_FMu200rMVZEEYS7SL_AiAuQdbtZZc-G7CDtR0IciOV_tJg8iw8tG5FbL1sFkpYAw"
}
async def get_abyss_data(uid: int):
    client = genshin.Client(COOKIES)
    client.region = genshin.Region.OVERSEAS
    
    try:
        # Fetch CURRENT abyss (use previous=True for the last reset)
        abyss = await client.get_genshin_spiral_abyss(uid)
        
        if not abyss.floors:
            return "No Abyss data found for this cycle."

        msg = ""
        # We only show Floors 11 and 12 as requested
        for floor in abyss.floors:
            if floor.floor < 11:
                continue
                
            msg += f"┏【FLOOR {floor.floor}】\n"
            
            # Loop through chambers (usually 1, 2, 3)
            for chamber in floor.chambers:
                stars = "★" * chamber.stars
                empty = "☆" * (3 - chamber.stars)
                msg += f"┣ Chamber {chamber.chamber} - {stars}{empty}\n"
            
            msg += "┗━━━━━━━━━━━━━━━━\n\n"
            
        return msg if msg else "You haven't reached Floor 11 yet this cycle!"

    except Exception as e:
        print(f"Abyss Error: {e}")
        return None
async def get_exploration_data(uid: int):
    client = genshin.Client(COOKIES)
    client.region = genshin.Region.OVERSEAS
    
    try:
        data = await client.get_genshin_user(uid)
        results = []
        
        for area in data.explorations:
            # Using the 'raw_explored' fix we found in debug
            raw_val = getattr(area, 'raw_explored', 0)
            percentage = raw_val / 10
            
            results.append({
                "name": area.name,
                "percent": percentage,
                "icon": area.icon  # You can use this for the bot's UI!
            })
        
        return results

    except Exception as e:
        print(f"Error fetching exploration: {e}")
        return None

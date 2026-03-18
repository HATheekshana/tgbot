import asyncio
import genshin

# Your Central Cookie Store
COOKIES = {
    "ltuid_v2": "471000302",
    "ltoken_v2": "v2_CAISDGM5b3FhcTNzM2d1OBokZTFmZTViNmItZDgxOS00MzNlLWJiZDktYWJkMTEzMWY1ZmY0INeWk8cGKOrUmKYFMO7Jy-ABQgtiYnNfb3ZlcnNlYVhq.yaO6aQAAAAAB.MEYCIQDQBTz_522dl6rUMbI-jxblNiNf4e4A0wCl77JnTabgjwIhAJ6sy3bnNbxS_3LlSZRgKaAM4HMMZrFD4WwPMHvsGcmq"
}

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

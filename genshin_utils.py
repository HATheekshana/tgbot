import asyncio
import genshin
import aiohttp
# Your Central Cookie Store
def get_quiz_score(difficulty, elapsed):
    # Base points
    base = {"easy": 1, "medium": 3, "hard": 5}.get(difficulty.lower(), 1)
    
    # Time Bonus
    if elapsed < 5: bonus = 10
    elif elapsed < 10: bonus = 5
    elif elapsed < 30: bonus = 1
    else: bonus = 0
    
    return base + bonus
COOKIES = {
    "ltuid_v2": "449108883",
    "ltoken_v2": "v2_CAISDGM5b3FhcTNzM2d1OBokNDcwMGJhYzAtMTAxZi00YjRlLTk2YmItN2M4YjhjMjMxZDAwIPWn780GKOuk4-0HMJO3k9YBQgtiYnNfb3ZlcnNlYVhqagJTRw.9dO7aQAAAAAB.MEUCIA5OHCjpxUDGrSJ8AQVHNuK4nwpW7XdJhtZhYnXcMhiFAiEAn0azB_VtrCvO57QPc72lKVKK_lTyMHAjDM2LrvENUco"
}
client = genshin.Client(COOKIES)
client.region = genshin.Region.OVERSEAS
# Function to calculate World Level from AR (since API doesn't give it)
# Helper to calculate World Level


async def get_player_full_data(uid):
    # This calls the genshin.py client
    raw_data = await client.get_genshin_user(uid)
    data = raw_data.dict()
    
    # We create a simple dictionary that your /myprofile command expects
    return {
        "nickname": data.get("info", {}).get("nickname", "Unknown"),
        "level": data.get("info", {}).get("level", 0),
        "world_level": calculate_world_level(data.get("info", {}).get("level", 0)),
        "achievements": data.get("stats", {}).get("achievements", 0),
        "days_active": data.get("stats", {}).get("days_active", 0),
        "luxurious": data.get("stats", {}).get("luxurious_chests", 0),
        "precious": data.get("stats", {}).get("precious_chests", 0),
        "exquisite": data.get("stats", {}).get("exquisite_chests", 0),
        "common": data.get("stats", {}).get("common_chests", 0),
        "in_game_avatar": data.get("info", {}).get("in_game_avatar", "Unknown"),
        "spiral_abyss": data.get("stats", {}).get("spiral_abyss", "Unknown"),
        "characters": data.get("characters", [])
    }
async def get_enkadata(uid):
    url = f"https://enka.network/api/uid/{uid}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                player_info = data.get("playerInfo", {})
                showcase = player_info.get("showAvatarInfoList", [])
                return {
                    "abyssfloor":player_info.get("towerFloorIndex", "Unknown"),
                    "abysslevel":player_info.get("towerLevelIndex", "Unknown"),
                    "nickname": player_info.get("nickname", "Unknown"),
                    "level": player_info.get("level", 0),
                    "achievements": player_info.get("finishAchievementNum", 0),
                    "worldLevel": player_info.get("worldLevel", 0),
                    "signature": player_info.get("signature", ""),
                    "nameCardId": player_info.get("nameCardId", ""),
                    "showAvatarInfoList": showcase
                }
            return {"abyssfloor": "?", "abysslevel": "?", "nickname": "Unknown", "level": 0, "achievements": 0, "worldLevel": 0, "signature": "", "nameCardId": "", "showAvatarInfoList": []}

def calculate_world_level(ar):
    ar = int(ar)
    if ar < 20: return 0
    if ar < 25: return 1
    if ar < 30: return 2
    if ar < 35: return 3
    if ar < 40: return 4
    if ar < 45: return 5
    if ar < 50: return 6
    if ar < 55: return 7
    return 8
async def get_exploration_data(uid):
    raw_data = await client.get_genshin_user(uid)
    data = raw_data.dict()
    
    expl_list = data.get("explorations", [])
    results = []
    for area in expl_list:
        results.append({
            "name": area.get("name"),
            # raw_explored 720 becomes 72.0
            "percent": float(area.get("raw_explored", 0)) / 10.0
        })
    return results

# Universal getter simplified for your specific JSON structure
def get_val(data, key, section="stats"):
    # Check in the specific section (stats or info)
    if section in data and key in data[section]:
        return data[section][key]
    # Fallback to root
    return data.get(key, 0)

def to_int(val):
    try:
        return int(float(val)) if val else 0
    except:
        return 0
async def get_abyss_data(uid: int):  
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
                
            msg += f"ꫂ❁【FLOOR {floor.floor}】\n"
            
            # Loop through chambers (usually 1, 2, 3)
            for chamber in floor.chambers:
                stars = "✮" * chamber.stars
                empty = "☆" * (3 - chamber.stars)
                msg += f"⧽ Chamber {chamber.chamber} - {stars}{empty} \n"
            
            msg += "╰➤─── ⋆⋅☆⋅⋆ ──────\n\n"
            
        return msg if msg else "You haven't reached Floor 11 yet this cycle!"

    except Exception as e:
        print(f"Abyss Error: {e}")
        return None

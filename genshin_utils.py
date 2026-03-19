import asyncio
import genshin

# Your Central Cookie Store

COOKIES = {
    "ltuid_v2": "449108883",
    "ltoken_v2": "v2_CAISDGM5b3FhcTNzM2d1OBokZTFmZTViNmItZDgxOS00MzNlLWJiZDktYWJkMTEzMWY1ZmY0IJOa680GKN2dpW8wk7eT1gFCC2Jic19vdmVyc2VhWGpqAlNH.E826aQAAAAAB.MEYCIQC4613SjXxJLp6Ki55JQ8XdW6aAWrSLn4cr4sdyJdNmuAIhALA28AO3gDgq_iYuFyQgMXmHIZVLmIb6FWQTwtO9jro_"
}
import aiohttp

# Cache for character names to avoid hitting the API too much
CHARACTER_CACHE = {}

async def get_character_name(char_id: str):
    """Automatically finds the character name from Enka's official metadata."""
    global CHARACTER_CACHE
    
    # If we already have it in memory, return it
    if char_id in CHARACTER_CACHE:
        return CHARACTER_CACHE[char_id]
    
    # Otherwise, fetch the latest names from Enka's asset store
    try:
        url = "https://raw.githubusercontent.com/EnkaNetwork/EnkaData/master/dictionary/en.json"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    names_dict = await response.json()
                    # Enka uses the ID as the key in their hash map
                    # We save it to our cache
                    name = names_dict.get(char_id, f"Hero {char_id}")
                    CHARACTER_CACHE[char_id] = name
                    return name
    except Exception:
        pass
    
    return f"Hero {char_id}"
async def parse_character_data(data, char_id):
    """Finds a character in the Enka JSON and extracts combat stats."""
    if not data or "avatarInfoList" not in data:
        return None

    # Find the specific character
    char = next((c for c in data["avatarInfoList"] if str(c["avatarId"]) == char_id), None)
    if not char:
        return None

    # FightPropMap contains the combat stats (HP, ATK, Crit, etc.)
    f_props = char.get("fightPropMap", {})

    # Helper to format stats
    def get_val(prop_id, is_percent=False):
        val = f_props.get(str(prop_id), 0)
        return f"{val * 100:.1f}%" if is_percent else f"{val:.0f}"

    return {
        "id": char_id,
        "level": char.get("propMap", {}).get("4001", {}).get("val", "??"),
        "hp": get_val(2000),
        "atk": get_val(2001),
        "def": get_val(2002),
        "em": get_val(28),
        "er": get_val(23, True),
        "cr": get_val(20, True),
        "cd": get_val(22, True)
    }
async def get_player_full_data(uid: int):
    client = genshin.Client(COOKIES)
    client.region = genshin.Region.OVERSEAS
    
    try:
        data = await client.get_genshin_user(uid)
        
        # Safe data extraction
        return {
            "name": data.info.nickname,
            "level": data.info.level,
            "world_level": getattr(data.info, "world_level", "N/A"),
            "signature": getattr(data.info, "signature", ""),
            "achievements": data.stats.achievements,
            "days_active": data.stats.days_active,# Updated check for the icon location
        }
    except Exception as e:
        import sys
        print(f"!!! GENSHIN API ERROR: {e}", file=sys.stderr, flush=True)
        return None
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
                
            msg += f"︵【FLOOR {floor.floor}】\n"
            
            # Loop through chambers (usually 1, 2, 3)
            for chamber in floor.chambers:
                stars = "✮" * chamber.stars
                empty = "☆" * (3 - chamber.stars)
                msg += f"⧽ Chamber {chamber.chamber} - {stars}{empty} 𐙚\n"
            
            msg += "◡̈▬▬ι═══════ﺤ\n\n"
            
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

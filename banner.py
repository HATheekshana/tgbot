from datetime import datetime, timezone

# CURRENT BANNER END TIMES
CURRENT_END = {
    "Asia": datetime(2026, 4, 27, 7, 0, tzinfo=timezone.utc),
    
    "EU": datetime(2026, 4, 27, 14, 0, tzinfo=timezone.utc),
    
    "NA": datetime(2026, 4, 27, 20, 0, tzinfo=timezone.utc),
}

# NEXT BANNER START TIMES (Usually 1 hour after old one ends)
NEXT_START = {
    "Asia": datetime(2026, 4, 28, 3, 0, tzinfo=timezone.utc),
    "EU": datetime(2026, 4, 28, 3, 0, tzinfo=timezone.utc),   # +7 hours from Asia
    "NA": datetime(2026, 4, 28, 3, 0, tzinfo=timezone.utc),   # +12 hours from Asia
}

# Image paths (Local VPS paths)
# Image paths for the duos
CURRENT_IMAGES = ["images/banners/char1.png", "images/banners/char2.png"]
NEXT_IMAGES = ["images/banners/next1.png", "images/banners/next2.png"]

def get_banner_text(mode="current"):
    now = datetime.now(timezone.utc)
    data = CURRENT_END if mode == "current" else NEXT_START
    title = "⏳ <b>CURRENT BANNER ENDS IN:</b>" if mode == "current" else "🚀 <b>NEXT BANNER STARTS IN:</b>"
    
    lines = [title, "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯"]
    for region, target in data.items():
        diff = target - now
        if diff.total_seconds() > 0:
            days = diff.days
            hours, rem = divmod(diff.seconds, 3600)
            minutes, _ = divmod(rem, 60)
            time_str = f"{days}d {hours}h {minutes}m"
        else:
            time_str = "Live! / Finished"
        lines.append(f"<b>{region}:</b> <code>{time_str}</code>")
    
    return "\n".join(lines)
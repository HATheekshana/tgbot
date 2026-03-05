
import os
import random
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# --- Bot Token ---
TOKEN = "1936607928:AAHPUcZR6SGa9cvlqLJhnYk-LfpTO0_9Nb8"

# --- Image folder ---
IMAGE_FOLDER = "/app/assets/images"

# --- Define 5★ and 4★ characters ---
FIVE_STAR = [
    "diluc.webp", "keqing.webp", "mona.webp", "xiao.webp",
    "raidenshogun.webp", "ganyu.webp", "ayaka.webp", "yoimiya.webp"
]

FOUR_STAR = [
    "bennett.webp", "fischl.webp", "sucrose.webp", "rosaria.webp",
    "xiangling.webp", "jean.webp", "sayu.webp", "kaeya.webp"
]

# --- Get all images in folder ---
all_images = os.listdir(IMAGE_FOLDER)

# Anything not in 5★ or 4★ is automatically 3★
THREE_STAR = [img for img in all_images if img not in FIVE_STAR + FOUR_STAR]

# --- Probabilities ---
PROBABILITIES = {
    "⭐⭐⭐⭐⭐": 0.05,  # 5%
    "⭐⭐⭐⭐": 0.20,   # 20%
    "⭐⭐⭐": 0.75     # 75%
}

# --- Command handler ---
async def wish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    roll = random.random()
    
    if roll <= PROBABILITIES["⭐⭐⭐⭐⭐"]:
        rarity = "⭐⭐⭐⭐⭐"
        pool = FIVE_STAR
    elif roll <= PROBABILITIES["⭐⭐⭐⭐⭐"] + PROBABILITIES["⭐⭐⭐⭐"]:
        rarity = "⭐⭐⭐⭐"
        pool = FOUR_STAR
    else:
        rarity = "⭐⭐⭐"
        pool = THREE_STAR

    # Pick random image from pool
    image_file = random.choice(pool)
    image_path = os.path.join(IMAGE_FOLDER, image_file)

    # Send message + image
    await context.bot.send_photo(
        chat_id=update.effective_chat.id,
        photo=open(image_path, "rb"),
        caption=f"You got {rarity}!\n{image_file.replace('.webp','').capitalize()}"
    )

# --- Start bot ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Welcome to Genshin Wishing Bot!\nUse /wish to roll.")

# --- Main ---
app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("wish", wish))

print("Bot is running...")
app.run_polling()
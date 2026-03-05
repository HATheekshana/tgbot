import os
import random
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = "1936607928:AAHPUcZR6SGa9cvlqLJhnYk-LfpTO0_9Nb8"

# Folders
folder = "/app/TGBot/assets /images/"

# Assign rarities
five_star = ["diluc.webp","keqing.webp","mona.webp","raidenshogun.webp","ganyu.webp","xiao.webp","ayaka.webp"]
four_star = ["bennett.webp","fischl.webp","sucrose.webp","rosaria.webp","xiangling.webp","jean.webp"]
three_star = [f for f in os.listdir(folder) if f.endswith(".webp") and f not in five_star+four_star]

# Build item dictionary dynamically
items = {}

for f in five_star:
    name = f.replace(".webp","").replace("-"," ").title()
    items[name] = {"rarity":"⭐⭐⭐⭐⭐", "image": folder+f}

for f in four_star:
    name = f.replace(".webp","").replace("-"," ").title()
    items[name] = {"rarity":"⭐⭐⭐⭐", "image": folder+f}

for f in three_star:
    name = f.replace(".webp","").replace("-"," ").title()
    items[name] = {"rarity":"⭐⭐⭐", "image": folder+f}

# Wish command
async def wish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    roll = random.randint(1,100)
    if roll <= 5:
        pool = {k:v for k,v in items.items() if v["rarity"]=="⭐⭐⭐⭐⭐"}
    elif roll <= 25:
        pool = {k:v for k,v in items.items() if v["rarity"]=="⭐⭐⭐⭐"}
    else:
        pool = {k:v for k,v in items.items() if v["rarity"]=="⭐⭐⭐"}

    name, data = random.choice(list(pool.items()))
    with open(data["image"],"rb") as img:
        await update.message.reply_photo(photo=img, caption=f"You wished and got:\n{name} {data['rarity']}")

app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("wish", wish))

print("Bot running...")
app.run_polling()
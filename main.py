from flask import Flask
from threading import Thread
import discord
from discord import app_commands, ui
from discord.ext import commands
import os
import json

# --- keep_alive עם Flask ---
app = Flask("")

@app.route("/")
def home():
    return "Bot is alive!"

def run():
    app.run(host="0.0.0.0", port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# --- טעינת קובץ config ---
CONFIG_FILE = "config.json"
if os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        config = json.load(f)
else:
    config = {}

def save_config():
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4, ensure_ascii=False)

# --- הגדרת בוט ודיסקורד אינטנטים ---
intents = discord.Intents.default()
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# --- דוגמה לפקודת Slash להגדרת פאנל טיקטים עם בדיקות ---
@bot.tree.command(name="set_ticket_panel", description="הגדר ערוץ וטוקן צוות לפאנל טיקטים")
@app_commands.describe(channel="בחר את הערוץ להצגת כפתור פתיחת טיקט", role="בחר את תפקיד הצוות המורשה לסגור טיקט")
async def set_ticket_panel(interaction: discord.Interaction, channel: discord.TextChannel, role: discord.Role):
    guild = interaction.guild
    if guild is None:
        await interaction.response.send_message("שגיאה: לא נמצאה גuild.", ephemeral=True)
        return

    if channel is None or role is None:
        await interaction.response.send_message("אנא בחר ערוץ ותפקיד תקינים.", ephemeral=True)
        return

    guild_id = str(guild.id)
    if guild_id not in config:
        config[guild_id] = {}

    config[guild_id]["ticket_channel"] = channel.id
    config[guild_id]["staff_role"] = role.id
    save_config()

    view = TicketButtons(staff_role_id=role.id)

    try:
        await channel.purge(limit=100)
    except discord.Forbidden:
        await interaction.response.send_message("אין לבוט הרשאות למחוק הודעות בערוץ זה.", ephemeral=True)
        return
    except Exception as e:
        await interaction.response.send_message(f"שגיאה במחיקת הודעות: {e}", ephemeral=True)
        return

    await channel.send(
        "לחצו על הכפתור לפתיחת טיקט 👇\n\n**חוקים:**\n- אסור לטרול\n- לשמור על נימוס\n- לא להטריד את הצוות\n- נא לפרט את הסיבה בכבוד",
        view=view,
    )
    await interaction.response.send_message(
        f"✅ פאנל טיקטים הוגדר ב-{channel.mention} עם צוות {role.mention}", ephemeral=True
    )

# --- המשך הקוד: מחלקות לכפתורי הטיקט, אירועי ברוכים הבאים, פקודות נוספות וכו' ---
# (הדבק כאן את שאר הקוד שהכנת, עם הטיפול ב-bot ו־config)

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")
    try:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} commands.")
    except Exception as e:
        print(f"❌ Sync error: {e}")

if __name__ == "__main__":
    keep_alive()
    TOKEN = os.getenv("TOKEN")
    if not TOKEN:
        print("ERROR: יש להגדיר את הטוקן בסביבה (TOKEN)")
    else:
        bot.run(TOKEN)

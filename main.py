import discord
from discord import app_commands, ui
from discord.ext import commands
from flask import Flask
from threading import Thread
import os
import json

# --- Keep Alive עם Flask ---
app = Flask("")

@app.route("/")
def home():
    return "Bot is alive!"

def run():
    app.run(host="0.0.0.0", port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# --- קובץ הגדרות ---
CONFIG_FILE = "config.json"
if os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        config = json.load(f)
else:
    config = {}

def save_config():
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4, ensure_ascii=False)

# --- הגדרת בוט דיסקורד ---
intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

# --- מחלקות לכפתורי טיקט ---
class TicketButtons(ui.View):
    def __init__(self, staff_role_id):
        super().__init__(timeout=None)
        self.staff_role_id = staff_role_id

    @ui.button(label="📩 פתח טיקט", style=discord.ButtonStyle.green, custom_id="open_ticket")
    async def open_ticket(self, interaction: discord.Interaction, button: ui.Button):
        guild = interaction.guild
        member = interaction.user
        staff_role = guild.get_role(self.staff_role_id)
        # בדיקה אם כבר קיים טיקט פתוח לאותו משתמש
        existing = discord.utils.get(guild.channels, name=f"ticket-{member.name.lower()}")
        if existing:
            await interaction.response.send_message(f"יש לך כבר טיקט פתוח: {existing.mention}", ephemeral=True)
            return
        # הרשאות ערוץ הטיקט
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            member: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            staff_role: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        # יצירת ערוץ חדש בשם ticket-username
        ticket_channel = await guild.create_text_channel(f"ticket-{member.name}", overwrites=overwrites, topic=f"טיקט של {member}.")

        # יצירת הודעה עם כפתורים (כחול ואדום)
        view = TicketControlButtons(staff_role_id=self.staff_role_id)
        embed = discord.Embed(title="טיקט חדש נפתח", description=f"שלום {member.mention}!\nאנא פרט את סיבת הפנייה או לחץ על הכפתור 📝 למטה להוספת סיבה.", color=0x00ff00)
        embed.set_footer(text="כדי לסגור את הטיקט לחץ על הכפתור 🔒 (רק צוות יכול לסגור).")
        await ticket_channel.send(embed=embed, view=view)

        await interaction.response.send_message(f"טיקט נפתח ב- {ticket_channel.mention}", ephemeral=True)

class TicketControlButtons(ui.View):
    def __init__(self, staff_role_id):
        super().__init__(timeout=None)
        self.staff_role_id = staff_role_id

    @ui.button(label="📝 מה הסיבה?", style=discord.ButtonStyle.secondary, custom_id="ticket_reason")
    async def reason_button(self, interaction: discord.Interaction, button: ui.Button):
        if self.staff_role_id not in [role.id for role in interaction.user.roles]:
            await interaction.response.send_message("רק צוות יכול למלא את הסיבה.", ephemeral=True)
            return

        await interaction.response.send_message("שלח לי כאן את הסיבה לטיקט (או לחץ ביטול):", ephemeral=True)

        def check(m):
            return m.author == interaction.user and m.channel == interaction.channel

        try:
            msg = await bot.wait_for("message", timeout=60.0, check=check)
        except Exception:
            await interaction.followup.send("לא קיבלתי תגובה בזמן, מבטל.", ephemeral=True)
            return

        await interaction.channel.send(f"סיבת הטיקט נוספה:\n> {msg.content}")

    @ui.button(label="🔒 סגור טיקט", style=discord.ButtonStyle.danger, custom_id="ticket_close")
    async def close_button(self, interaction: discord.Interaction, button: ui.Button):
        if self.staff_role_id not in [role.id for role in interaction.user.roles]:
            await interaction.response.send_message("רק צוות יכול לסגור טיקט.", ephemeral=True)
            return
        await interaction.response.send_message("הטיקט ייסגר בעוד 5 שניות...", ephemeral=False)
        await discord.utils.sleep_until(discord.utils.utcnow() + discord.utils.timedelta(seconds=5))
        await interaction.channel.delete()

# --- אירוע ברוך הבא ---
@bot.event
async def on_member_join(member: discord.Member):
    guild_id = str(member.guild.id)
    if guild_id not in config or "welcome_channel" not in config[guild_id]:
        return

    channel_id = config[guild_id]["welcome_channel"]
    channel = member.guild.get_channel(channel_id)
    if channel is None:
        return

    embed = discord.Embed(title="ברוך הבא!", color=0x00ff00)
    embed.description = f"🎉 ברוך הבא {member.mention} לשרת **{member.guild.name}**!\n" \
                        f"אתה החבר ה-{member.guild.member_count} בשרת 🎊"
    embed.set_thumbnail(url=member.display_avatar.url)
    await channel.send(embed=embed)

# --- פקודת Slash להגדרת Welcome ---
@bot.tree.command(name="set_welcome", description="הגדר את ערוץ ה-Welcome")
@app_commands.describe(channel="בחר את הערוץ שבו יישלחו הודעות הברוכים")
async def set_welcome(interaction: discord.Interaction, channel: discord.TextChannel):
    guild_id = str(interaction.guild.id)
    if guild_id not in config:
        config[guild_id] = {}

    config[guild_id]["welcome_channel"] = channel.id
    save_config()
    await interaction.response.send_message(f"✅ ערוץ ה-Welcome הוגדר ל־{channel.mention}", ephemeral=True)

# --- פקודת Slash להגדרת פאנל טיקטים ---
@bot.tree.command(name="set_ticket_panel", description="הגדר ערוץ וטוקן צוות לפאנל טיקטים")
@app_commands.describe(channel="בחר את הערוץ להצגת כפתור פתיחת טיקט", role="בחר את תפקיד הצוות המורשה לסגור טיקט")
async def set_ticket_panel(interaction: discord.Interaction, channel: discord.TextChannel, role: discord.Role):
    guild_id = str(interaction.guild.id)
    if guild_id not in config:
        config[guild_id] = {}

    config[guild_id]["ticket_channel"] = channel.id
    config[guild_id]["staff_role"] = role.id
    save_config()

    view = TicketButtons(staff_role_id=role.id)
    try:
        await channel.purge(limit=100)
    except discord.errors.Forbidden:
        await interaction.response.send_message("❌ אין לי הרשאות למחוק הודעות בערוץ הזה.", ephemeral=True)
        return
    await channel.send("לחצו על הכפתור לפתיחת טיקט 👇\n\n**חוקים:**\n- אסור לטרול\n- לשמור על נימוס\n- לא להטריד את הצוות\n- נא לפרט את הסיבה בכבוד", view=view)
    await interaction.response.send_message(f"✅ פאנל טיקטים הוגדר ב-{channel.mention} עם צוות {role.mention}", ephemeral=True)

# --- אירוע ברגע שהבוט עולה ---
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")
    try:
        await bot.tree.sync()
        print("✅ Slash commands synced!")
    except Exception as e:
        print("❌ Sync error:", e)

# --- הפעלת ה־keep_alive והבוט ---
if __name__ == "__main__":
    keep_alive()
    TOKEN = os.getenv("TOKEN")
    if not TOKEN:
        print("ERROR: יש להגדיר את הטוקן בסביבה (TOKEN)")
    else:
        bot.run(TOKEN)

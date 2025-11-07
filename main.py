import os
import discord
from discord.ext import commands

TOKEN = os.getenv("TOKEN")  # Lấy token từ biến môi trường
IDADMIN_GOC = 1259541498278707213

intents = discord.Intents.default()
intents.message_content = True
intents.messages = True

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f"✅ Bot đã đăng nhập thành công dưới tên: {bot.user}")

bot.run(TOKEN)

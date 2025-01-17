import discord
from discord.ext import commands
import os

# 初始化 Bot
intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.message_content = True

bot = commands.Bot(command_prefix="!RA ", intents=intents)

# 用於存儲圖片與使用者名稱的關聯
user_images = {}
user_cards = {}

# 從環境變數中讀取 token
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise ValueError("DISCORD_TOKEN 環境變數未設置")
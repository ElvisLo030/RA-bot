import discord
from discord.ext import commands
import os
import asyncio

# 設定 Discord Intents
intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.message_content = True

# 建立 Bot 實例
bot = commands.Bot(command_prefix="!RA ", intents=intents)

# 定義共享資料
bot.user_cards = {}   # 儲存使用者卡號
bot.user_images = {}  # 儲存使用者圖片審查資訊

# 取得 Discord Token
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise ValueError("DISCORD_TOKEN 環境變數未設置")

async def load_cogs():
    # 加載 card_binding cog
    await bot.load_extension("cogs.card_binding")
    # 加載 selection_menu cog
    await bot.load_extension("cogs.selection_menu")
    # 加載 image_review cog
    await bot.load_extension("cogs.image_review")

async def main():
    async with bot:
        await load_cogs()
        # 調試輸出，確認 bot.user_cards 已設置
        print(f"bot.user_cards: {bot.user_cards}")
        await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
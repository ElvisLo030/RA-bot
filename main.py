import discord
from discord.ext import commands
import os
import asyncio
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn

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

# 載入 Cogs
async def load_cogs():
    await bot.load_extension("cogs.card_binding")
    await bot.load_extension("cogs.selection_menu")
    await bot.load_extension("cogs.image_review")
    await bot.load_extension("cogs.voting")
# 啟動 Bot
async def start_bot():
    async with bot:
        await load_cogs()
        await bot.start(TOKEN)

# 建立 FastAPI
app = FastAPI()

# 定義資料模型
class Card(BaseModel):
    user_id: int
    card_number: str

class Image(BaseModel):
    user_id: int
    filename: str
    url: str

# 根路由
@app.get("/")
def read_root():
    return {"message": "歡迎使用 RA 機器人 API"}

# GET /cards
@app.get("/cards")
def get_cards():
    return bot.user_cards

# POST /cards
@app.post("/cards")
def add_card(card: Card):
    import re
    card_pattern = re.compile(r'^(?=.*[0-9])(?=.*[A-Za-z])[A-Za-z0-9]{8}$')
    if not card_pattern.match(card.card_number):
        raise HTTPException(status_code=400, detail="卡號格式錯誤！需包含 8 位英數字，且至少包含 1 英文字母與 1 數字。")
    bot.user_cards[card.user_id] = card.card_number
    return {"message": f"使用者 {card.user_id} 的卡號 {card.card_number} 已儲存。"}

# GET /images
@app.get("/images")
def get_images():
    return {
        str(k): [
            {
                "filename": img["filename"],
                "user_id": img["user_id"],        # 使用者 ID
                "username": img.get("username", "Unknown"),   # 使用者名稱
                "status": img["status"]
            }
            for img in v
        ]
        for k, v in bot.user_images.items()
    }

# POST /images
@app.post("/images")
def add_image(image: Image):
    if image.user_id not in bot.user_images:
        bot.user_images[image.user_id] = []
    # 假設 URL 是圖片的連結，初始狀態為 "pending"
    bot.user_images[image.user_id].append({
        "filename": image.filename,
        "url": image.url,
        "status": "pending",
        "user_id": image.user_id,          # 使用者 ID
        "username": "unknown"              # 初始使用者名稱，稍後更新
    })
    return {"message": f"使用者 {image.user_id} 的圖片 {image.filename} 已儲存。"}

# GET /votes
@app.get("/votes")
def get_votes():
    if not hasattr(bot, "votes_history"):
        bot.votes_history = []
    return bot.votes_history

# POST /votes
class Vote(BaseModel):
    title: str
    up: int = 0
    down: int = 0

# 同時執行 Bot 與 API
if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    # 啟動 Discord 機器人
    loop.create_task(start_bot())
    # 配置 Uvicorn 以在同一事件迴圈運行 FastAPI
    config = uvicorn.Config(app, host="0.0.0.0", port=8080, log_level="info")
    server = uvicorn.Server(config)
    loop.create_task(server.serve())
    loop.run_forever()
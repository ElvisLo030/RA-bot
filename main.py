import discord
from discord.ext import commands
import os
import asyncio
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, field_validator
import uvicorn
from dotenv import load_dotenv
from contextlib import asynccontextmanager
import re

load_dotenv()

intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.message_content = True

bot = commands.Bot(command_prefix="!RA ", intents=intents)

bot.user_images = {}
bot.events = {}
bot.gamers = {}

def add_points_internal(gamer_id: int, points: int) -> str:
    if gamer_id not in bot.gamers:
        bot.gamers[gamer_id] = {
            "gamer_id": gamer_id,
            "gamer_dcid": f"UnknownUser{gamer_id}",
            "gamer_card_number": None,
            "gamer_is_blocked": False,
            "gamer_bind_gamepass": None,
            "joined_events": [],
            "history_event_list": [],
            "history_event_pts_list": []
        }
    bot.gamers[gamer_id]["history_event_pts_list"].append(points)
    return f"已為玩家 {gamer_id} 新增 {points} 點數"

bot.add_points_internal = add_points_internal

TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise ValueError("DISCORD_TOKEN 未設置")

async def load_cogs():
    await bot.load_extension("cogs.card_binding")
    await bot.load_extension("cogs.selection_menu")
    await bot.load_extension("cogs.image_review")
    await bot.load_extension("cogs.event_management")
    await bot.load_extension("cogs.admin_management")

async def start_bot():
    async with bot:
        await load_cogs()
        await bot.start(TOKEN)

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.bot = bot
    yield

app = FastAPI(lifespan=lifespan)

class EventData(BaseModel):
    event_code: str
    event_name: str
    event_description: str
    event_start_date: str
    event_end_date: str

    @field_validator("event_code")
    def validate_event_code(cls, v):
        pattern = r'^(?=.*[A-Za-z])(?=.*\d)[A-Za-z0-9]{1,6}$'
        if not re.match(pattern, v):
            raise ValueError("event_code 格式錯誤，至少1英文+1數字，長度1~6")
        return v

class GamerData(BaseModel):
    gamer_dcid: str
    gamer_card_number: str = None
    gamer_is_blocked: bool = False
    gamer_bind_gamepass: str = None

@app.get("/")
def read_root():
    return {"message": "歡迎使用 RA 機器人 API"}

@app.post("/event")
def create_event(data: EventData):
    if data.event_code in bot.events:
        raise HTTPException(status_code=400, detail="活動編號已存在")
    bot.events[data.event_code] = {
        "event_code": data.event_code,
        "event_name": data.event_name,
        "event_description": data.event_description,
        "event_start_date": data.event_start_date,
        "event_end_date": data.event_end_date,
        "gamer_list": []
    }
    return {"event_code": data.event_code, "message": "活動已建立"}

@app.get("/event")
def get_events():
    return list(bot.events.values())

@app.get("/event/{event_code}")
def get_event(event_code: str):
    if event_code not in bot.events:
        raise HTTPException(status_code=404, detail="Event not found")
    return bot.events[event_code]

@app.put("/event")
def reset_events():
    bot.events.clear()
    return {"message": "All events reset"}

@app.get("/gamer")
def get_all_gamers():
    print("DEBUG: /gamer => bot.gamers=", bot.gamers)
    return list(bot.gamers.values())

@app.get("/gamer/{gamer_id}")
def get_gamer_data(gamer_id: int):
    if gamer_id not in bot.gamers:
        raise HTTPException(status_code=404, detail="Gamer not found")
    return bot.gamers[gamer_id]

@app.post("/gamer")
def create_gamer(data: GamerData):
    new_id = len(bot.gamers) + 1
    bot.gamers[new_id] = {
        "gamer_id": new_id,
        "gamer_dcid": data.gamer_dcid,
        "gamer_card_number": data.gamer_card_number,
        "gamer_is_blocked": data.gamer_is_blocked,
        "gamer_bind_gamepass": data.gamer_bind_gamepass,
        "joined_events": [],
        "history_event_list": [],
        "history_event_pts_list": []
    }
    return {"gamer_id": new_id, "message": f"玩家 {new_id} 已建立"}

@app.put("/gamer/{gamer_id}/points")
def add_points_to_gamer_api(gamer_id: int, points: int):
    if gamer_id not in bot.gamers:
        raise HTTPException(status_code=404, detail="Gamer not found")
    bot.gamers[gamer_id]["history_event_pts_list"].append(points)
    return {"message": f"已為玩家 {gamer_id} 增加 {points} 點數"}

@app.put("/gamer/{gamer_id}/card")
def update_gamer_card(gamer_id: int, new_card_number: str):
    if gamer_id not in bot.gamers:
        raise HTTPException(status_code=404, detail="Gamer not found")
    bot.gamers[gamer_id]["gamer_card_number"] = new_card_number
    return {"message": f"玩家 {gamer_id} 的卡號已更新為 {new_card_number}"}

@app.get("/gamer/card/{card_number}")
def get_gamer_by_card(card_number: str):
    for g_id, data in bot.gamers.items():
        if data.get("gamer_card_number") == card_number:
            return data
    raise HTTPException(status_code=404, detail="Player with this card number not found")

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(start_bot())
    config = uvicorn.Config(app, host="0.0.0.0", port=8080, log_level="info")
    server = uvicorn.Server(config)
    loop.create_task(server.serve())
    loop.run_forever()
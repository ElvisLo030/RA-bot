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
from discord.ext.commands import CheckFailure
import json

load_dotenv()

intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.message_content = True

bot = commands.Bot(command_prefix="RA ", intents=intents)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE_PATH = os.path.join(BASE_DIR, "data.json")

def load_data():
    if os.path.exists(DATA_FILE_PATH):
        try:
            with open(DATA_FILE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                bot.user_images = data.get("user_images", {})
                bot.events = data.get("events", {})
                # 將 gamers 的 key 轉回 int
                raw_gamers = data.get("gamers", {})
                bot.gamers = {int(k): v for k, v in raw_gamers.items()}
                print("DEBUG: 成功載入 JSON 資料")
        except Exception as e:
            print(f"WARNING: 載入 JSON 資料失敗: {e}")
    else:
        print("DEBUG: data.json 不存在，建立預設空資料")
        data = {
            "user_images": {},
            "events": {},
            "gamers": {}
        }
        try:
            with open(DATA_FILE_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print("DEBUG: 已自動建立新的 data.json")
        except Exception as e:
            print(f"ERROR: 建立 data.json 失敗: {e}")
        bot.user_images = {}
        bot.events = {}
        bot.gamers = {}

def save_data():
    print("DEBUG: save_data() 正在執行...")
    data = {
        "user_images": bot.user_images,
        "events": bot.events,
        "gamers": bot.gamers
    }
    try:
        with open(DATA_FILE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print("DEBUG: 已將資料寫入 JSON") 
    except Exception as e:
        print("ERROR: 寫入 JSON 檔案失敗!", e)
        import traceback
        traceback.print_exc()

bot.user_images = {}
bot.events = {}
bot.gamers = {}

def add_points_internal(gamer_id: int, points: int) -> str:
    if gamer_id not in bot.gamers:
        bot.gamers[gamer_id] = {
            "gamer_id": gamer_id,
            "gamer_card_number": None,
            "gamer_is_blocked": False,
            "gamer_bind_gamepass": None,
            "joined_events": [],
            "history_event_list": [],
            "history_event_pts_list": []
        }
    bot.gamers[gamer_id]["history_event_pts_list"].append(points)

    save_data()
    return f"已為玩家 {gamer_id} 新增 {points} 點數"

def not_blocked(ctx: commands.Context):
    user_data = ctx.bot.gamers.get(ctx.author.id)
    if user_data and user_data.get("gamer_is_blocked"):
        raise CheckFailure("你已被加入黑名單，無法使用。")
    return True

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
    load_data()
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
        pattern = r'^RAE(?=.*[0-9])[A-Za-z0-9]{3}$'
        print(f"DEBUG: validate_event_code called with event_code={v}")
        if not re.match(pattern, v):
            raise ValueError("event_code 格式錯誤，格式為RAEXXX(需含數字+3碼英數)")
        return v

class GamerData(BaseModel):
    gamer_card_number: str = None
    gamer_is_blocked: bool = False
    gamer_bind_gamepass: str = None

@app.get("/")
def read_root():
    return {"message": "歡迎使用 RA 機器人 API"}

@app.post("/event")
def create_event(data: EventData):
    print(f"DEBUG: create_event API called with data={data}")
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
    save_data()
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
    save_data()
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
        "gamer_card_number": data.gamer_card_number,
        "gamer_is_blocked": data.gamer_is_blocked,
        "gamer_bind_gamepass": data.gamer_bind_gamepass,
        "joined_events": [],
        "history_event_list": [],
        "history_event_pts_list": []
    }
    save_data()
    return {"gamer_id": new_id, "message": f"玩家 {new_id} 已建立"}

@app.put("/gamer/{gamer_id}/points")
def add_points_to_gamer_api(gamer_id: int, points: int):
    if gamer_id not in bot.gamers:
        raise HTTPException(status_code=404, detail="Gamer not found")
    bot.gamers[gamer_id]["history_event_pts_list"].append(points)
    save_data()
    return {"message": f"已為玩家 {gamer_id} 增加 {points} 點"}

@app.put("/gamer/{gamer_id}/card")
def update_gamer_card(gamer_id: int, new_card_number: str):
    if gamer_id not in bot.gamers:
        raise HTTPException(status_code=404, detail="Gamer not found")
    bot.gamers[gamer_id]["gamer_card_number"] = new_card_number
    save_data()
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
import discord
from discord.ext import commands
import os
import asyncio
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
import uvicorn
from dotenv import load_dotenv
from contextlib import asynccontextmanager

load_dotenv()

intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.message_content = True

bot = commands.Bot(command_prefix="!RA ", intents=intents)

# ------------------------------
# In-memory 資料
# ------------------------------
bot.user_images = {}       # 圖片審核資訊
bot.events = {}            # 活動列表 { event_id: {...} }
bot.tasks = {}             # 任務列表 { task_id: {...} }
gamers = {}                # 玩家資料 (若需要, 也可直接 bot.gamers = {})
event_counter = 1
task_counter = 1

# ------------------------------
# 加點數函式
# ------------------------------
def add_points_internal(gamer_id: int, points: int) -> str:
    """
    範例: 將 points 加到 gamers[gamer_id]['history_event_pts_list'].
    若 gamer 不存在就先初始化
    """
    if gamer_id not in gamers:
        gamers[gamer_id] = {
            "gamer_id": gamer_id,
            "gamer_dcid": f"UnknownUser{gamer_id}",
            "gamer_card_number": None,
            "gamer_is_blocked": False,
            "gamer_bind_gamepass": None,
            "history_event_list": [],
            "history_event_pts_list": [],
            "history_task_list": []
        }
    gamers[gamer_id]["history_event_pts_list"].append(points)
    return f"已為玩家 {gamer_id} 新增 {points} 點數"

# ------------------------------
# FastAPI
# ------------------------------
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise ValueError("DISCORD_TOKEN 環境變數未設置")

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

# ------------------------------
# Pydantic Models
# ------------------------------
class ImageData(BaseModel):
    user_id: int
    filename: str
    url: str

class EventData(BaseModel):
    event_name: str
    event_description: str
    event_start_date: str
    event_end_date: str

class TaskData(BaseModel):
    task_name: str
    task_description: str
    task_points: int
    event_id: int

class GamerData(BaseModel):
    gamer_dcid: str
    gamer_card_number: str = None
    gamer_is_blocked: bool = False
    gamer_bind_gamepass: str = None

@app.get("/")
def read_root():
    return {"message": "歡迎使用 RA 機器人 API"}

# ------------------------------
# /images
# ------------------------------
@app.get("/images")
def get_images(request: Request):
    bot = request.app.state.bot
    return {
        str(k): [
            {
                "filename": img["filename"],
                "user_id": img["user_id"],
                "username": img.get("username", "Unknown"),
                "status": img["status"],
                "event_id": img.get("event_id"),
                "task_id": img.get("task_id")
            }
            for img in v
        ]
        for k, v in bot.user_images.items()
    }

@app.post("/images")
def add_image(image: ImageData, request: Request):
    bot = request.app.state.bot
    if image.user_id not in bot.user_images:
        bot.user_images[image.user_id] = []
    bot.user_images[image.user_id].append({
        "filename": image.filename,
        "url": image.url,
        "status": "pending",
        "user_id": image.user_id,
        "username": "unknown"
    })
    return {"message": f"使用者 {image.user_id} 的圖片 {image.filename} 已儲存。"}

# ------------------------------
# /event
# ------------------------------
@app.post("/event")
def create_event(data: EventData):
    global event_counter
    e_id = event_counter
    bot.events[e_id] = {
        "event_id": e_id,
        "event_name": data.event_name,
        "event_description": data.event_description,
        "event_start_date": data.event_start_date,
        "event_end_date": data.event_end_date,
        "task_list": [],
        "gamer_list": []
    }
    event_counter += 1
    return {"event_id": e_id}

@app.get("/event")
def get_events():
    return list(bot.events.values())

@app.put("/event")
def reset_events():
    bot.events.clear()
    return {"message": "All events reset"}

@app.get("/event/{event_id}")
def get_event(event_id: int):
    if event_id not in bot.events:
        raise HTTPException(status_code=404, detail="Event not found")
    e = bot.events[event_id]
    return {
        **e,
        "tasks": [{"task_id": t["task_id"], "task_name": t["task_name"]} for t in e["task_list"]],
        "gamers": [{"gamer_id": g_id} for g_id in e["gamer_list"]]
    }

# ------------------------------
# /task
# ------------------------------
@app.post("/task")
def create_task(data: TaskData):
    global task_counter
    t_id = task_counter
    t_info = {
        "task_id": t_id,
        "task_name": data.task_name,
        "task_description": data.task_description,
        "task_points": data.task_points,
        "event_id": data.event_id,
        "gamer_list": []
    }
    bot.tasks[t_id] = t_info
    if data.event_id in bot.events:
        bot.events[data.event_id]["task_list"].append(t_info)
    task_counter += 1
    return {"task_id": t_id}

@app.get("/task/{task_id}")
def get_task(task_id: int):
    if task_id not in bot.tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    return bot.tasks[task_id]

# ------------------------------
# /gamer
# ------------------------------
@app.post("/gamer")
def create_gamer(data: GamerData):
    new_id = len(gamers) + 1
    gamers[new_id] = {
        "gamer_id": new_id,
        "gamer_dcid": data.gamer_dcid,
        "gamer_card_number": data.gamer_card_number,
        "gamer_is_blocked": data.gamer_is_blocked,
        "gamer_bind_gamepass": data.gamer_bind_gamepass,
        "history_event_list": [],
        "history_event_pts_list": [],
        "history_task_list": []
    }
    return {"gamer_id": new_id, "message": f"玩家 {new_id} 已建立"}

@app.get("/gamer/{gamer_id}")
def get_gamer_data(gamer_id: int):
    if gamer_id not in gamers:
        raise HTTPException(status_code=404, detail="Gamer not found")
    return gamers[gamer_id]

@app.put("/gamer/{gamer_id}/points")
def add_points_to_gamer_api(gamer_id: int, points: int):
    if gamer_id not in gamers:
        raise HTTPException(status_code=404, detail="Gamer not found")
    gamers[gamer_id]["history_event_pts_list"].append(points)
    return {"message": f"已為玩家 {gamer_id} 新增 {points} 點數"}

@app.put("/gamer/{gamer_id}/card")
def update_gamer_card(gamer_id: int, new_card_number: str):
    if gamer_id not in gamers:
        raise HTTPException(status_code=404, detail="Gamer not found")
    gamers[gamer_id]["gamer_card_number"] = new_card_number
    return {"message": f"已為玩家 {gamer_id} 更新卡號為 {new_card_number}"}

# ------------------------------
# 主程式
# ------------------------------
if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(start_bot())
    config = uvicorn.Config(app, host="0.0.0.0", port=8080, log_level="info")
    server = uvicorn.Server(config)
    loop.create_task(server.serve())
    loop.run_forever()
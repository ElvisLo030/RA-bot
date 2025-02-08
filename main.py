import os
import json
import asyncio
import traceback
import re
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request, Depends, status
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel, field_validator
from discord.ext import commands
from discord.ext.commands import CheckFailure
from dotenv import load_dotenv
from typing import Optional, List
import secrets

load_dotenv()

import uvicorn
import discord

# ----------------------------
# Discord Bot 初始化
# ----------------------------
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
        data = {"user_images": {}, "events": {}, "gamers": {}}
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
        traceback.print_exc()

bot.user_images = {}
bot.events = {}
bot.gamers = {}

# 以下函式更新資料時，不再推送任何 log 訊息
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
    await bot.load_extension("cogs.task_management")

async def start_bot():
    load_data()
    async with bot:
        await load_cogs()
        await bot.start(TOKEN)

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.bot = bot
    yield

# ----------------------------
# FastAPI 應用與 Dashboard 設定
# ----------------------------
app = FastAPI(lifespan=lifespan)
templates = Jinja2Templates(directory="templates")

# HTTP Basic 認證設定
security = HTTPBasic()
def get_current_username(credentials: HTTPBasicCredentials = Depends(security)):
    correct_username = os.getenv("DASHBOARD_USERNAME")
    correct_password = os.getenv("DASHBOARD_PASSWORD")
    is_valid_username = secrets.compare_digest(credentials.username, correct_username)
    is_valid_password = secrets.compare_digest(credentials.password, correct_password)
    if not (is_valid_username and is_valid_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="驗證失敗，請檢查帳號密碼",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

# Pydantic 模型
class EventData(BaseModel):
    event_code: str
    event_name: str
    event_description: str
    event_start_date: str
    event_end_date: str
    tasks: Optional[List[dict]] = None

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
        "gamer_list": [],
        "tasks": []
    }
    if data.tasks:
        task_id_start = 1
        for t in data.tasks:
            bot.events[data.event_code]["tasks"].append({
                "task_id": task_id_start,
                "task_name": t.get("task_name", "未命名任務"),
                "task_description": t.get("task_description", ""),
                "task_points": t.get("task_points", 0),
                "assigned_users": [],
                "checked_users": []
            })
            task_id_start += 1
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

# 新增任務 API（包含 task_points 欄位）
@app.post("/event/{event_code}/task")
def add_task_to_event(event_code: str, task_name: str, task_description: str = "", task_points: int = 0):
    if event_code not in bot.events:
        raise HTTPException(status_code=404, detail="Event not found")
    tasks = bot.events[event_code].get("tasks", [])
    new_id = len(tasks) + 1
    tasks.append({
        "task_id": new_id,
        "task_name": task_name,
        "task_description": task_description,
        "task_points": task_points,
        "assigned_users": [],
        "checked_users": []
    })
    bot.events[event_code]["tasks"] = tasks
    save_data()
    return {"message": f"已新增任務 {task_name} (點數：{task_points}) 到活動 {event_code}"}

# 新增任務細節檢視功能
@app.get("/task/{event_code}/{task_id}", response_class=HTMLResponse)
def task_detail(request: Request, event_code: str, task_id: int, username: str = Depends(get_current_username)):
    if event_code not in bot.events:
        raise HTTPException(status_code=404, detail="Event not found")
    task = None
    for t in bot.events[event_code].get("tasks", []):
        if t["task_id"] == task_id:
            task = t
            break
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return templates.TemplateResponse("task_detail.html", {
        "request": request,
        "event_code": event_code,
        "task": task
    })

# Dashboard 頁面（需通過 HTTP Basic 認證）
@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, username: str = Depends(get_current_username)):
    status = "機器人運作中"
    debug_info = "DEBUG: 資料載入成功"
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "events": bot.events,
        "gamers": bot.gamers,
        "status": status,
        "debug": debug_info
    })

# ----------------------------
# 移除所有 log 功能，故不再建立任何 SSE log或資料更新推播功能
# ----------------------------

# ----------------------------
# 同時啟動 Discord Bot 與 FastAPI 網站
# ----------------------------
if __name__ == "__main__":
    # 建立新的事件迴圈並設定為當前事件迴圈
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    global_loop = loop  # 設定全域事件迴圈
    # 移除 log_queue 與 data_update_queue 初始化，因不再推播 log 資料
    loop.create_task(start_bot())
    config = uvicorn.Config(app, host="0.0.0.0", port=8080, log_level="info")
    server = uvicorn.Server(config)
    loop.create_task(server.serve())
    loop.run_forever()
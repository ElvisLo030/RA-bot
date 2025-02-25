import os
import json
import asyncio
import traceback
import re
import time
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
from datetime import datetime, timedelta
import uvicorn
import discord
import aiohttp  

load_dotenv()

intents = discord.Intents.all()
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

def add_points_internal(gamer_id: int, points: int) -> str:
    if gamer_id not in bot.gamers:
        bot.gamers[gamer_id] = {
            "gamer_id": gamer_id,
            "gamer_card_number": None,
            "gamer_is_blocked": False,
            "gamer_bind_gamepass": None,
            "joined_events": [],
            "history_event_list": [],
            "history_event_pts_list": [],
            "events_points": {}
        }
    bot.gamers[gamer_id]["history_event_pts_list"].append(points)
    bot.gamers[gamer_id].setdefault("points_history", [])
    bot.gamers[gamer_id]["points_history"].append({
        "type": "global",
        "points": points,
        "timestamp": datetime.utcnow().isoformat()
    })

    save_data()
    return f"已為玩家 {gamer_id} 新增 {points} 點數"

def add_event_points_internal(gamer_id: int, event_code: str, points: int) -> str:
    if gamer_id not in bot.gamers:
        bot.gamers[gamer_id] = {
            "gamer_id": gamer_id,
            "gamer_card_number": None,
            "gamer_is_blocked": False,
            "gamer_bind_gamepass": None,
            "joined_events": [],
            "history_event_list": [],
            "history_event_pts_list": [],
            "events_points": {}
        }
    bot.gamers[gamer_id]["history_event_pts_list"].append(points)

    if "events_points" not in bot.gamers[gamer_id]:
        bot.gamers[gamer_id]["events_points"] = {}
    bot.gamers[gamer_id]["events_points"].setdefault(event_code, 0)
    bot.gamers[gamer_id]["events_points"][event_code] += points

    bot.gamers[gamer_id].setdefault("points_history", [])
    bot.gamers[gamer_id]["points_history"].append({
        "type": "event",
        "event_code": event_code,
        "points": points,
        "timestamp": datetime.utcnow().isoformat()
    })

    save_data()
    return f"已為玩家 {gamer_id} 在活動 {event_code} 新增 {points} 點數"

def not_blocked(ctx: commands.Context):
    user_data = ctx.bot.gamers.get(ctx.author.id)
    if user_data and user_data.get("gamer_is_blocked"):
        raise CheckFailure("你已被加入黑名單，無法使用。")
    return True

bot.add_points_internal = add_points_internal
bot.add_event_points_internal = add_event_points_internal

TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise ValueError("DISCORD_TOKEN 未設置")

def update_event_max_points(event_dict: dict):
    total = 0
    if "tasks" in event_dict:
        for task in event_dict["tasks"]:
            total += task.get("task_points", 0)
    event_dict["max_points"] = total

async def load_cogs():
    await bot.load_extension("cogs.card_binding")
    await bot.load_extension("cogs.selection_menu")
    await bot.load_extension("cogs.image_review")
    await bot.load_extension("cogs.admin_management")

async def start_bot():
    load_data()
    async with bot:
        await load_cogs()
        while True:
            try:
                await bot.start(TOKEN)
            except aiohttp.client_exceptions.WSServerHandshakeError as e:
                print(f"連接到 Discord 網關失敗: {e}")
                print("等待 5 秒後重試...")
                time.sleep(5)
            except Exception as e:
                print(f"發生未預期的錯誤: {e}")
                break

@asynccontextmanager
async def lifespan_api(app: FastAPI):
    app.state.bot = bot
    yield

# api 
app_api = FastAPI(lifespan=lifespan_api)

@app_api.get("/")
def read_root_api():
    return {"message": "這是API系統(只綁定localhost)"}

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
        if not re.match(pattern, v):
            raise ValueError("event_code 格式錯誤，格式為RAEXXX(需含數字+3碼英數)")
        return v

class GamerData(BaseModel):
    gamer_card_number: str = None
    gamer_is_blocked: bool = False
    gamer_bind_gamepass: str = None

@app_api.post("/event")  
def create_event_api(data: EventData):
    if data.event_code in bot.events:
        raise HTTPException(status_code=400, detail="活動編號已存在")
    try:
        start_date = datetime.strptime(data.event_start_date, "%Y-%m-%d").date()
        end_date = datetime.strptime(data.event_end_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="日期格式錯誤，應為 YYYY-MM-DD")

    bot.events[data.event_code] = {
        "event_code": data.event_code,
        "event_name": data.event_name,
        "event_description": data.event_description,
        "event_start_date": data.event_start_date,
        "event_end_date": data.event_end_date,
        "gamer_list": [],
        "tasks": [],
        "max_points": 0
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

    update_event_max_points(bot.events[data.event_code])
    save_data()
    return {"event_code": data.event_code, "message": "活動已建立"}

@app_api.get("/event")
def get_events_api():
    return list(bot.events.values())

@app_api.get("/event/{event_code}")
def get_event_api(event_code: str):
    if event_code not in bot.events:
        raise HTTPException(status_code=404, detail="Event not found")
    return bot.events[event_code]

@app_api.put("/event")
def reset_events_api():
    bot.events.clear()
    save_data()
    return {"message": "All events reset"}

@app_api.get("/gamer")
def get_all_gamers_api():
    return list(bot.gamers.values())

@app_api.get("/gamer/{gamer_id}")
def get_gamer_data_api(gamer_id: int):
    if gamer_id not in bot.gamers:
        raise HTTPException(status_code=404, detail="Gamer not found")
    return bot.gamers[gamer_id]

@app_api.post("/gamer")
def create_gamer_api(data: GamerData):
    new_id = len(bot.gamers) + 1
    bot.gamers[new_id] = {
        "gamer_id": new_id,
        "gamer_card_number": data.gamer_card_number,
        "gamer_is_blocked": data.gamer_is_blocked,
        "gamer_bind_gamepass": data.gamer_bind_gamepass,
        "joined_events": [],
        "history_event_list": [],
        "history_event_pts_list": [],
        "events_points": {}
    }
    save_data()
    return {"gamer_id": new_id, "message": f"玩家 {new_id} 已建立"}

@app_api.put("/gamer/{gamer_id}/points")
def add_points_to_gamer_api(gamer_id: int, points: int):
    if gamer_id not in bot.gamers:
        raise HTTPException(status_code=404, detail="Gamer not found")
    bot.gamers[gamer_id]["history_event_pts_list"].append(points)
    bot.gamers[gamer_id].setdefault("points_history", [])
    bot.gamers[gamer_id]["points_history"].append({
        "type": "api",
        "points": points,
        "timestamp": (datetime.utcnow() + timedelta(hours=8)).isoformat()
    })
    save_data()
    return {"message": f"已為玩家 {gamer_id} 增加 {points} 點"}

@app_api.put("/gamer/{gamer_id}/card")
def update_gamer_card_api(gamer_id: int, new_card_number: str):
    if gamer_id not in bot.gamers:
        raise HTTPException(status_code=404, detail="Gamer not found")
    bot.gamers[gamer_id]["gamer_card_number"] = new_card_number
    save_data()
    return {"message": f"玩家 {gamer_id} 的卡號已更新為 {new_card_number}"}

@app_api.get("/gamer/card/{card_number}")
def get_gamer_by_card_api(card_number: str):
    for g_id, data in bot.gamers.items():
        if data.get("gamer_card_number") == card_number:
            return data
    raise HTTPException(status_code=404, detail="Player with this card number not found")

@app_api.post("/event/{event_code}/task")
def add_task_to_event_api(event_code: str, task_name: str, task_description: str = "", task_points: int = 0):
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
    update_event_max_points(bot.events[event_code])
    save_data()
    return {"message": f"已新增任務 {task_name} (點數：{task_points}) 到活動 {event_code}"}

# dashboard 
@asynccontextmanager
async def lifespan_dashboard(app: FastAPI):
    app.state.bot = bot
    yield

app_dashboard = FastAPI(lifespan=lifespan_dashboard)
templates = Jinja2Templates(directory="templates")

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

@app_dashboard.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, username: str = Depends(get_current_username)):
    status = "機器人運作中"
    debug_info = "資料載入成功"
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "events": bot.events,
        "gamers": bot.gamers,
        "status": status,
        "debug": debug_info
    })

@app_dashboard.get("/task/{event_code}/{task_id}", response_class=HTMLResponse)
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

@app_dashboard.get("/dashboard/event/{event_code}", response_class=HTMLResponse)
def dashboard_event_detail(request: Request, event_code: str, username: str = Depends(get_current_username)):
    if event_code not in bot.events:
        raise HTTPException(status_code=404, detail="Event not found")
    event = bot.events[event_code]
    return templates.TemplateResponse("event_tasks_detail.html", {
        "request": request,
        "event_code": event_code,
        "event": event
    })

@app_dashboard.get("/gamer/{gamer_id}/event/{event_code}", response_class=HTMLResponse)
def user_event_detail(request: Request, 
                      gamer_id: int, 
                      event_code: str, 
                      username: str = Depends(get_current_username)):
    gamer = bot.gamers.get(gamer_id)
    if not gamer:
        raise HTTPException(status_code=404, detail="Gamer not found")
    event = bot.events.get(event_code)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    events_points = gamer.get("events_points", {})
    user_points = events_points.get(event_code, 0)
    tasks = event.get("tasks", [])
    return templates.TemplateResponse("user_event_detail.html", {
        "request": request,
        "gamer_id": gamer_id,
        "event_code": event_code,
        "event": event,
        "user_points": user_points,
        "tasks": tasks,
        "gamer": gamer
    })

@app_dashboard.get("/gamer/{gamer_id}/timestamps", response_class=HTMLResponse)
def gamer_timestamps(request: Request, gamer_id: int, username: str = Depends(get_current_username)):
    user_data = bot.gamers.get(gamer_id)
    if not user_data:
        raise HTTPException(status_code=404, detail="Gamer not found")
    def parse_iso(s):
        try:
            return datetime.fromisoformat(s)
        except:
            return None
    all_records = []

    points_history = user_data.get("points_history", [])
    for item in points_history:
        stamp = item.get("timestamp")
        if stamp:
            record_type = item.get("type","?")
            ev_code = item.get("event_code","")
            pts = item.get("points",0)
            if record_type == "global":
                detail = f"全域加點 +{pts}"
            elif record_type == "event":
                detail = f"活動({ev_code})加點 +{pts}"
            elif record_type == "api":
                detail = f"API加點 +{pts}"
            else:
                detail = f"其他加點 +{pts}"
            all_records.append({"timestamp": stamp, "detail": detail})

    joined_map = user_data.get("joined_event_timestamps", {})
    for ev_code, timestr in joined_map.items():
        if timestr:
            all_records.append({"timestamp": timestr, "detail": f"加入活動 {ev_code}"})

    user_images = bot.user_images.get(gamer_id, [])
    for img in user_images:
        if "upload_time" in img:
            all_records.append({
                "timestamp": img["upload_time"],
                "detail": f"上傳圖片 `{img['filename']}` (活動={img['event_code']}, 任務ID={img['task_id']})"
            })
        if "approved_time" in img:
            all_records.append({
                "timestamp": img["approved_time"],
                "detail": f"圖片 `{img['filename']}` 審核通過 (活動={img['event_code']}, 任務ID={img['task_id']})"
            })
        if "rejected_time" in img:
            all_records.append({
                "timestamp": img["rejected_time"],
                "detail": f"圖片 `{img['filename']}` 審核拒絕 (活動={img['event_code']}, 任務ID={img['task_id']})"
            })

    valid_records = []
    for r in all_records:
        dt = parse_iso(r["timestamp"])
        if dt:
            valid_records.append({"timestamp": r["timestamp"], "detail": r["detail"], "dt": dt})
    valid_records.sort(key=lambda x: x["dt"])
    final_records = [{"timestamp": r["timestamp"], "detail": r["detail"]} for r in valid_records]
    return templates.TemplateResponse("gamer_timestamps.html", {
        "request": request,
        "gamer_id": gamer_id,
        "all_records": final_records
    })

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    global_loop = loop  
    loop.create_task(start_bot())

    # API只給本機用
    config_api = uvicorn.Config(app_api, host="0.0.0.0", port=8050, log_level="info")
    server_api = uvicorn.Server(config_api)
    loop.create_task(server_api.serve())

    # Dashboard對外
    config_dash = uvicorn.Config(app_dashboard, host="127.0.0.1", port=8080, log_level="info")
    server_dash = uvicorn.Server(config_dash)
    loop.create_task(server_dash.serve())

    loop.run_forever()
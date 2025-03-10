import os
import json
import asyncio
import traceback
import re
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Optional, List

import uvicorn
import aiohttp

from fastapi import FastAPI, HTTPException, Request, Body
from fastapi.responses import HTMLResponse, StreamingResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from pydantic import BaseModel, field_validator

from discord.ext import commands
from discord.ext.commands import CheckFailure
import discord
from dotenv import load_dotenv

###############################
# 載入環境變數
###############################
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise ValueError("DISCORD_TOKEN 未設置")

###############################
# Discord Bot 初始化
###############################
intents = discord.Intents.all()
intents.messages = True
intents.guilds = True
intents.message_content = True

bot = commands.Bot(command_prefix="RA ", intents=intents)

###############################
# 資料檔路徑
###############################
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE_PATH = os.path.join(BASE_DIR, "data.json")

###############################
# 全域結構
###############################
bot.user_images = {}
bot.events = {}
bot.gamers = {}

###############################
# API 紀錄函式
###############################
def record_api(action: str, data: dict):
    print(f"[API紀錄] action={action}, data={data}")

###############################
# 時間處理
###############################
def get_timestamp_now() -> str:
    """回傳 UTC+8 ISO 格式."""
    return (datetime.utcnow() + timedelta(hours=8)).isoformat()

###############################
# 確保玩家存在
###############################
def ensure_gamer(gamer_id: int):
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

###############################
# 讀寫 data.json
###############################
def load_data():
    if os.path.exists(DATA_FILE_PATH):
        try:
            with open(DATA_FILE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                bot.user_images = data.get("user_images", {})
                bot.events = data.get("events", {})
                raw_gamers = data.get("gamers", {})
                # string->int
                bot.gamers = {int(k): v for k, v in raw_gamers.items()}
                print("DEBUG: 成功載入 JSON")
        except Exception as e:
            print(f"WARNING: 載入 JSON 失敗: {e}")
    else:
        print("DEBUG: data.json 不存在, 建立預設空資料")
        data = {"user_images": {}, "events": {}, "gamers": {}}
        try:
            with open(DATA_FILE_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print("DEBUG: 新的 data.json 已建立")
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
            f.flush()  # 強制 flush 資料到磁碟
        print("DEBUG: 已將資料寫入 JSON")
    except Exception as e:
        print("ERROR: 寫入 JSON 檔案失敗!", e)
        traceback.print_exc()

###############################
# Bot 加點邏輯
###############################
def add_points_internal(gamer_id: int, points: int) -> str:
    ensure_gamer(gamer_id)
    bot.gamers[gamer_id]["history_event_pts_list"].append(points)
    bot.gamers[gamer_id].setdefault("points_history", [])
    ts_str = get_timestamp_now()
    bot.gamers[gamer_id]["points_history"].append({
        "type": "global",
        "points": points,
        "timestamp": ts_str
    })
    record_api("add_global_points", {
        "gamer_id": gamer_id, 
        "points": points, 
        "timestamp": ts_str
    })
    save_data()
    return f"已為玩家 {gamer_id} 新增 {points} 點數"

def add_event_points_internal(gamer_id: int, event_code: str, points: int) -> str:
    ensure_gamer(gamer_id)
    bot.gamers[gamer_id]["history_event_pts_list"].append(points)
    bot.gamers[gamer_id]["events_points"].setdefault(event_code, 0)
    bot.gamers[gamer_id]["events_points"][event_code] += points
    bot.gamers[gamer_id].setdefault("points_history", [])
    ts_str = get_timestamp_now()
    bot.gamers[gamer_id]["points_history"].append({
        "type": "event",
        "event_code": event_code,
        "points": points,
        "timestamp": ts_str
    })
    record_api("add_event_points", {
        "gamer_id": gamer_id, 
        "event_code": event_code, 
        "points": points, 
        "timestamp": ts_str
    })
    save_data()
    return f"已為玩家 {gamer_id} 在活動 {event_code} 新增 {points} 點數"

bot.add_points_internal = add_points_internal
bot.add_event_points_internal = add_event_points_internal

###############################
# 黑名單檢查
###############################
def not_blocked(ctx: commands.Context):
    user_data = bot.gamers.get(ctx.author.id)
    if user_data and user_data.get("gamer_is_blocked"):
        raise CheckFailure("你已被加入黑名單，無法使用。")
    return True

###############################
# Token 檢查
###############################
if not TOKEN:
    raise ValueError("DISCORD_TOKEN 未設置")

###############################
# 更新活動最大點數
###############################
def update_event_max_points(event_dict: dict):
    total = 0
    if "tasks" in event_dict:
        for t in event_dict["tasks"]:
            total += t.get("task_points", 0)
    event_dict["max_points"] = total

###############################
# Lifespan：啟動前後處理
###############################
@asynccontextmanager
async def lifespan(app: FastAPI):
    load_data()
    loop = asyncio.get_event_loop()
    loop.create_task(start_bot())
    yield

###############################
# 建立 FastAPI 應用
###############################
app = FastAPI(lifespan=lifespan)
templates = Jinja2Templates(directory="templates")

###############################
# 啟動 Discord Bot
###############################
async def load_cogs():
    await bot.load_extension("cogs.card_binding")
    await bot.load_extension("cogs.selection_menu")
    await bot.load_extension("cogs.image_review")
    await bot.load_extension("cogs.admin_management")
    await bot.load_extension("cogs.event_management")

async def start_bot():
    async with bot:
        await load_cogs()
        while True:
            try:
                await bot.start(TOKEN)
            except aiohttp.client_exceptions.WSServerHandshakeError as e:
                print(f"連接Discord失敗: {e}, 5秒後重試...")
                time.sleep(5)
            except Exception as e:
                print(f"發生錯誤: {e}")
                break

###############################
# 首頁 -> Redirect /dashboard
###############################
@app.get("/")
def root_redirect():
    return RedirectResponse(url="/dashboard")

###############################
# 資料模型
###############################
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
            raise ValueError("event_code 格式錯誤，需 RAE+3碼英數，例如 RAE001")
        return v

class GamerData(BaseModel):
    gamer_card_number: str = None
    gamer_is_blocked: bool = False
    gamer_bind_gamepass: str = None

###############################
# Event 相關 API
###############################
@app.post("/api/event")
def create_event_api(data: EventData):
    if data.event_code in bot.events:
        raise HTTPException(status_code=400, detail="活動編號已存在")
    try:
        _ = datetime.strptime(data.event_start_date, "%Y-%m-%d").date()
        _ = datetime.strptime(data.event_end_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="日期格式錯誤(YYYY-MM-DD)")

    bot.events[data.event_code] = {
        "event_code": data.event_code,
        "event_name": data.event_name,
        "event_description": data.event_description,
        "event_start_date": data.event_start_date,
        "event_end_date": data.event_end_date,
        "gamer_list": [],
        "tasks": [],
        "max_points": 0,
        "prizes": []  # 預設一個 prizes list
    }
    if data.tasks:
        tid = 1
        for t in data.tasks:
            bot.events[data.event_code]["tasks"].append({
                "task_id": tid,
                "task_name": t.get("task_name", "未命名任務"),
                "task_description": t.get("task_description", ""),
                "task_points": t.get("task_points", 0),
                "assigned_users": [],
                "checked_users": []
            })
            tid += 1

    update_event_max_points(bot.events[data.event_code])
    save_data()
    return {"event_code": data.event_code, "message": "活動已建立"}

@app.get("/api/event")
def get_events_api():
    return list(bot.events.values())

@app.get("/api/event/{event_code}")
def get_event_api(event_code: str):
    if event_code not in bot.events:
        raise HTTPException(status_code=404, detail="Event not found")
    return bot.events[event_code]

@app.put("/api/event")
def reset_events_api():
    bot.events.clear()
    save_data()
    return {"message": "All events reset"}

###############################
# 新增：編輯 / 刪除 活動
###############################
@app.put("/api/event/{event_code}")
def edit_event_api(event_code: str, data: dict):
    if event_code not in bot.events:
        raise HTTPException(status_code=404, detail="Event not found")
    ev_obj = bot.events[event_code]
    ev_obj["event_name"] = data.get("event_name", ev_obj["event_name"])
    ev_obj["event_description"] = data.get("event_description", ev_obj["event_description"])
    ev_obj["event_start_date"] = data.get("event_start_date", ev_obj["event_start_date"])
    ev_obj["event_end_date"] = data.get("event_end_date", ev_obj["event_end_date"])
    try:
        _ = datetime.strptime(ev_obj["event_start_date"], "%Y-%m-%d").date()
        _ = datetime.strptime(ev_obj["event_end_date"], "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="日期格式錯誤(YYYY-MM-DD)")
    save_data()
    return {"message": f"活動 {event_code} 已更新"}

@app.delete("/api/event/{event_code}")
def delete_event_api(event_code: str):
    """
    刪除活動後，也要把所有玩家對此活動的參考清除，
    包括歷史紀錄 (points_history、history_event_list 等)。
    """
    if event_code not in bot.events:
        raise HTTPException(status_code=404, detail="Event not found")

    print(f"DEBUG: 刪除活動前，bot.events = {list(bot.events.keys())}")

    # 1) 刪除活動
    bot.events.pop(event_code, None)
    print(f"DEBUG: 刪除活動後，bot.events = {list(bot.events.keys())}")

    # 2) 遍歷每個玩家，移除所有關於此 event_code 的紀錄
    for g_id, user_data in bot.gamers.items():
        print(f"DEBUG: 處理 gamer {g_id} 前，資料 = {user_data}")
        if "joined_events" in user_data and event_code in user_data["joined_events"]:
            user_data["joined_events"].remove(event_code)
            print(f"DEBUG: gamer {g_id} - joined_events 移除 {event_code}")
        if "events_points" in user_data and event_code in user_data["events_points"]:
            user_data["events_points"].pop(event_code, None)
            print(f"DEBUG: gamer {g_id} - events_points 移除 {event_code}")
        if "redeemed_prizes" in user_data and event_code in user_data["redeemed_prizes"]:
            user_data["redeemed_prizes"].pop(event_code, None)
            print(f"DEBUG: gamer {g_id} - redeemed_prizes 移除 {event_code}")
        if "joined_event_timestamps" in user_data and event_code in user_data["joined_event_timestamps"]:
            user_data["joined_event_timestamps"].pop(event_code, None)
            print(f"DEBUG: gamer {g_id} - joined_event_timestamps 移除 {event_code}")
        if "history_event_list" in user_data:
            original_history = user_data["history_event_list"][:]
            user_data["history_event_list"] = [ev for ev in user_data["history_event_list"] if ev != event_code]
            print(f"DEBUG: gamer {g_id} history_event_list: {original_history} -> {user_data['history_event_list']}")
        if "points_history" in user_data:
            original_points_history = user_data["points_history"][:]
            new_points_history = []
            for rec in user_data["points_history"]:
                # 移除所有 type 為 "event" 且 event_code 為被刪除的紀錄
                if rec.get("type") == "event" and rec.get("event_code") == event_code:
                    continue
                new_points_history.append(rec)
            user_data["points_history"] = new_points_history
            print(f"DEBUG: gamer {g_id} points_history: {original_points_history} -> {user_data['points_history']}")
        print(f"DEBUG: 完成處理 gamer {g_id}, 最終資料 = {user_data}")
    
    # 3) 存檔
    save_data()
    print("DEBUG: data.json 更新完畢")
    # 若需要增加資料更新頻率，可考慮在此處每次修改完玩家資料後即呼叫 save_data()（但目前每次操作皆會呼叫）
    return {"message": f"活動 {event_code} 已刪除，並同步清除所有玩家與此活動的關聯"}

###############################
# Task 相關
###############################
@app.post("/api/event/{event_code}/task")
def add_task_to_event_api(event_code: str, task_name: str, task_description: str="", task_points: int=0):
    if event_code not in bot.events:
        raise HTTPException(status_code=404, detail="Event not found")
    tasks = bot.events[event_code].setdefault("tasks", [])
    new_id = len(tasks) + 1
    tasks.append({
        "task_id": new_id,
        "task_name": task_name,
        "task_description": task_description,
        "task_points": task_points,
        "assigned_users": [],
        "checked_users": []
    })
    update_event_max_points(bot.events[event_code])
    save_data()
    return {"message": f"已新增任務 {task_name} (點數:{task_points}) 到活動 {event_code}"}

@app.put("/api/event/{event_code}/task/{task_id}")
def edit_task_api(event_code: str, task_id: int, data: dict):
    if event_code not in bot.events:
        raise HTTPException(status_code=404, detail="Event not found")
    tasks = bot.events[event_code].get("tasks", [])
    the_task = None
    for t in tasks:
        if t["task_id"] == task_id:
            the_task = t
            break
    if not the_task:
        raise HTTPException(status_code=404, detail="Task not found")
    the_task["task_name"] = data.get("task_name", the_task["task_name"])
    the_task["task_description"] = data.get("task_description", the_task["task_description"])
    the_task["task_points"] = data.get("task_points", the_task["task_points"])
    update_event_max_points(bot.events[event_code])
    save_data()
    return {"message": f"任務 {task_id} 已更新"}

@app.delete("/api/event/{event_code}/task/{task_id}")
def delete_task_api(event_code: str, task_id: int):
    if event_code not in bot.events:
        raise HTTPException(status_code=404, detail="Event not found")
    tasks = bot.events[event_code].get("tasks", [])
    idx = None
    for i, t in enumerate(tasks):
        if t["task_id"] == task_id:
            idx = i
            break
    if idx is None:
        raise HTTPException(status_code=404, detail="Task not found")
    tasks.pop(idx)
    update_event_max_points(bot.events[event_code])
    save_data()
    return {"message": f"任務 {task_id} 已刪除"}

###############################
# Prize 相關
###############################
@app.post("/api/event/{event_code}/prize")
def add_prize_api(event_code: str, data: dict):
    if event_code not in bot.events:
        raise HTTPException(status_code=404, detail="Event not found")
    event_obj = bot.events[event_code]
    event_obj.setdefault("prizes", [])
    prize_list = event_obj["prizes"]
    new_id = len(prize_list) + 1
    prize_name = data.get("prize_name", "未命名獎勵")
    cost = data.get("points_required", 0)
    prize_list.append({
        "prize_id": new_id,
        "prize_name": prize_name,
        "points_required": cost
    })
    save_data()
    return {"message": f"已新增獎勵 {prize_name}(需:{cost}點) 到活動 {event_code}"}

@app.put("/api/event/{event_code}/prize/{prize_id}")
def edit_prize_api(event_code: str, prize_id: int, data: dict):
    if event_code not in bot.events:
        raise HTTPException(status_code=404, detail="Event not found")
    event_obj = bot.events[event_code]
    prizes = event_obj.setdefault("prizes", [])
    the_prize = None
    for p in prizes:
        if p["prize_id"] == prize_id:
            the_prize = p
            break
    if not the_prize:
        raise HTTPException(status_code=404, detail="Prize not found")
    the_prize["prize_name"] = data.get("prize_name", the_prize["prize_name"])
    the_prize["points_required"] = data.get("points_required", the_prize["points_required"])
    save_data()
    return {"message": f"活動{event_code}的獎勵 {prize_id} 已更新"}

@app.delete("/api/event/{event_code}/prize/{prize_id}")
def delete_prize_api(event_code: str, prize_id: int):
    if event_code not in bot.events:
        raise HTTPException(status_code=404, detail="Event not found")
    event_obj = bot.events[event_code]
    prizes = event_obj.setdefault("prizes", [])
    idx = None
    for i, p in enumerate(prizes):
        if p["prize_id"] == prize_id:
            idx = i
            break
    if idx is None:
        raise HTTPException(status_code=404, detail="Prize not found")
    prizes.pop(idx)
    save_data()
    return {"message": f"活動{event_code}的獎勵 {prize_id} 已刪除"}

###############################
# Gamer 相關
###############################
@app.post("/api/gamer")
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

@app.get("/api/gamer")
def get_all_gamers_api():
    return list(bot.gamers.values())

@app.get("/api/gamer/{gamer_id}")
def get_gamer_data_api(gamer_id: int):
    if gamer_id not in bot.gamers:
        raise HTTPException(status_code=404, detail="Gamer not found")
    return bot.gamers[gamer_id]

@app.put("/api/gamer/{gamer_id}/points")
def add_points_to_gamer_api(gamer_id: int, points: int):
    if gamer_id not in bot.gamers:
        raise HTTPException(status_code=404, detail="Gamer not found")
    bot.gamers[gamer_id]["history_event_pts_list"].append(points)
    bot.gamers[gamer_id].setdefault("points_history", [])
    ts_str = get_timestamp_now()
    bot.gamers[gamer_id]["points_history"].append({
        "type": "api",
        "points": points,
        "timestamp": ts_str
    })
    save_data()
    return {"message": f"已為玩家 {gamer_id} 增加 {points} 點"}

@app.put("/api/gamer/{gamer_id}/card")
def update_gamer_card_api(gamer_id: int, new_card_number: str):
    if gamer_id not in bot.gamers:
        raise HTTPException(status_code=404, detail="Gamer not found")
    bot.gamers[gamer_id]["gamer_card_number"] = new_card_number
    save_data()
    return {"message": f"玩家 {gamer_id} 的卡號已更新為 {new_card_number}"}

@app.get("/api/gamer/card/{card_number}")
def get_gamer_by_card_api(card_number: str):
    for g_id, data in bot.gamers.items():
        if data.get("gamer_card_number") == card_number:
            return data
    raise HTTPException(status_code=404, detail="Player with this card number not found")

@app.put("/api/gamer/{gamer_id}/redeem_prize")
def redeem_prize_api(gamer_id: int, event_code: str, prize_id: int = Body(embed=True)):
    if gamer_id not in bot.gamers:
        raise HTTPException(status_code=404, detail="Gamer not found")
    if event_code not in bot.events:
        raise HTTPException(status_code=404, detail="Event not found")

    event_obj = bot.events[event_code]
    if "prizes" not in event_obj:
        raise HTTPException(status_code=400, detail="此活動沒有獎品。")
    valid_ids = [p["prize_id"] for p in event_obj["prizes"]]
    if prize_id not in valid_ids:
        raise HTTPException(status_code=400, detail="此獎品ID不在活動中")

    user_data = bot.gamers[gamer_id]
    user_data.setdefault("redeemed_prizes", {})
    user_data["redeemed_prizes"].setdefault(event_code, [])

    chosen_prize = None
    for p in event_obj["prizes"]:
        if p["prize_id"] == prize_id:
            chosen_prize = p
            break
    if not chosen_prize:
        raise HTTPException(status_code=400, detail="查無此獎品")

    cost_points = chosen_prize.get("points_required", 0)
    events_points = user_data.setdefault("events_points", {})
    current_points = events_points.setdefault(event_code, 0)
    if current_points < cost_points:
        raise HTTPException(status_code=400, detail="點數不足, 無法兌換")

    if prize_id in user_data["redeemed_prizes"][event_code]:
        return {"message": "該玩家已兌換過此獎品"}

    user_data["redeemed_prizes"][event_code].append(prize_id)
    user_data.setdefault("points_history", [])
    ts_str = get_timestamp_now()
    user_data["points_history"].append({
        "timestamp": ts_str,
        "type": "admin_redeem",
        "event_code": event_code,
        "prize_id": prize_id
    })
    save_data()
    return {"message": f"已為玩家 {gamer_id} 兌換獎品(活動={event_code})"}

###############################
# Dashboard
###############################
@app.get("/dashboard", response_class=HTMLResponse)
def dashboard_page(request: Request):
    status = "機器人運作中"
    debug_info = "資料載入成功"
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "events": bot.events,
        "gamers": bot.gamers,
        "status": status,
        "debug": debug_info
    })

@app.get("/dashboard/management", response_class=HTMLResponse)
def dashboard_management(request: Request):
    return templates.TemplateResponse("dashboard_management.html", {
        "request": request,
        "events": bot.events
    })

@app.get("/dashboard/event/{event_code}", response_class=HTMLResponse)
def dashboard_event_detail(request: Request, event_code: str):
    if event_code not in bot.events:
        raise HTTPException(status_code=404, detail="Event not found")
    event = bot.events[event_code]
    return templates.TemplateResponse("event_tasks_detail.html", {
        "request": request,
        "event_code": event_code,
        "event": event
    })

###############################
# 其餘 Gamer / Timestamps 頁面
###############################
@app.get("/task/{event_code}/{task_id}", response_class=HTMLResponse)
def task_detail(request: Request, event_code: str, task_id: int):
    if event_code not in bot.events:
        raise HTTPException(status_code=404, detail="Event not found")
    the_task = None
    for t in bot.events[event_code]["tasks"]:
        if t["task_id"] == task_id:
            the_task = t
            break
    if not the_task:
        raise HTTPException(status_code=404, detail="Task not found")
    return templates.TemplateResponse("task_detail.html", {
        "request": request,
        "event_code": event_code,
        "task": the_task
    })

@app.get("/gamer/{gamer_id}/event/{event_code}", response_class=HTMLResponse)
def user_event_detail(request: Request, gamer_id: int, event_code: str):
    gamer = bot.gamers.get(gamer_id)
    if not gamer:
        raise HTTPException(status_code=404, detail="Gamer not found")
    event = bot.events.get(event_code)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    events_points = gamer.setdefault("events_points", {})
    user_points = events_points.setdefault(event_code, 0)
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

@app.get("/gamer/{gamer_id}/timestamps", response_class=HTMLResponse)
def gamer_timestamps(request: Request, gamer_id: int):
    user_data = bot.gamers.get(gamer_id)
    if not user_data:
        raise HTTPException(status_code=404, detail="Gamer not found")
    all_records = []
    points_history = user_data.get("points_history", [])
    for item in points_history:
        stamp = item.get("timestamp")
        if not stamp:
            continue
        rtype = item.get("type", "?")
        ev_code = item.get("event_code", "")
        pts = item.get("points", 0)
        if rtype == "global":
            detail = f"全域加點 +{pts}"
        elif rtype == "event":
            detail = f"活動({ev_code})加點 +{pts}"
        elif rtype == "api":
            detail = f"API加點 +{pts}"
        elif rtype == "admin_redeem":
            evobj = bot.events.get(ev_code, {})
            pname = "?"
            for p in evobj.get("prizes", []):
                if p["prize_id"] == item.get("prize_id"):
                    pname = p["prize_name"]
                    break
            detail = f"後台兌換(活動={ev_code}, 獎品={pname})"
        else:
            detail = f"其他動作 {pts}"
        all_records.append({"timestamp": stamp, "detail": detail})
    joined_map = user_data.get("joined_event_timestamps", {})
    for ev_code, tstamp in joined_map.items():
        if tstamp:
            all_records.append({"timestamp": tstamp, "detail": f"加入活動 {ev_code}"})
    user_imgs = bot.user_images.get(gamer_id, [])
    for img in user_imgs:
        if "upload_time" in img:
            all_records.append({
                "timestamp": img["upload_time"],
                "detail": f"上傳圖片 `{img['filename']}`(活動={img['event_code']}, 任務ID={img['task_id']})"
            })
        if "approved_time" in img:
            all_records.append({
                "timestamp": img["approved_time"],
                "detail": f"圖片 `{img['filename']}`審核通過 (活動={img['event_code']}, 任務ID={img['task_id']})"
            })
        if "rejected_time" in img:
            all_records.append({
                "timestamp": img["rejected_time"],
                "detail": f"圖片 `{img['filename']}`審核拒絕 (活動={img['event_code']}, 任務ID={img['task_id']})"
            })
    def parse_iso(s):
        try:
            return datetime.fromisoformat(s)
        except:
            return None
    valid_records = []
    for r in all_records:
        dt = parse_iso(r["timestamp"])
        if dt:
            valid_records.append({"timestamp": r["timestamp"], "detail": r["detail"], "dt": dt})
    valid_records.sort(key=lambda x: x["dt"])
    final_list = [{"timestamp": r["timestamp"], "detail": r["detail"]} for r in valid_records]
    return templates.TemplateResponse("gamer_timestamps.html", {
        "request": request,
        "gamer_id": gamer_id,
        "all_records": final_list
    })

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="info")
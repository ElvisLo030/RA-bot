# cogs/event_management.py

import discord
from discord.ext import commands

from main import gamers, add_points_internal

class EventManagementCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.has_permissions(administrator=True)
    @commands.command(name="新增活動")
    async def create_event(self, ctx: commands.Context, event_name: str, event_description: str, event_start_date: str, event_end_date: str):
        # 也可以跟 admin_create_event 重複, 看你是否保留
        event_id = len(self.bot.events) + 1
        self.bot.events[event_id] = {
            "event_id": event_id,
            "event_name": event_name,
            "event_description": event_description,
            "event_start_date": event_start_date,
            "event_end_date": event_end_date,
            "task_list": [],
            "gamer_list": []
        }
        await ctx.send(f"活動 {event_name} 已新增，活動 ID 為 {event_id}")

    @commands.has_permissions(administrator=True)
    @commands.command(name="給予點數")
    async def give_points(self, ctx: commands.Context, user_id: int, points: int):
        msg = add_points_internal(user_id, points)
        await ctx.send(msg)

    @commands.has_permissions(administrator=True)
    @commands.command(name="查詢活動")
    async def query_event(self, ctx: commands.Context, event_id: int):
        if event_id not in self.bot.events:
            await ctx.send("活動不存在。")
            return
        event = self.bot.events[event_id]
        tasks = "\n".join([f"- 任務ID {task['task_id']} : {task['task_name']}" for task in event["task_list"]])
        gamers_in_event = ", ".join(str(g_id) for g_id in event["gamer_list"])
        await ctx.send(
            f"活動 {event_id}:\n"
            f"名稱: {event['event_name']}\n"
            f"描述: {event['event_description']}\n"
            f"開始: {event['event_start_date']}, 結束: {event['event_end_date']}\n"
            f"任務:\n{tasks}\n"
            f"玩家: {gamers_in_event}"
        )

    @commands.has_permissions(administrator=True)
    @commands.command(name="查詢玩家點數")
    async def query_points(self, ctx: commands.Context, user_id: int):
        if user_id not in gamers:
            await ctx.send("使用者尚未註冊為玩家。")
            return
        points = sum(gamers[user_id]["history_event_pts_list"])
        await ctx.send(f"使用者 {user_id} 持有的點數: {points}")

async def setup(bot: commands.Bot):
    await bot.add_cog(EventManagementCog(bot))
# cogs/event_management.py

import discord
from discord.ext import commands
import re

class EventManagementCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.has_permissions(administrator=True)
    @commands.command(name="新增活動")
    async def create_event(self, ctx: commands.Context, event_code: str, event_name: str, event_description: str, event_start_date: str, event_end_date: str):
        pattern = r'^(?=.*[A-Za-z])(?=.*\d)[A-Za-z0-9]{1,6}$'
        if not re.match(pattern, event_code):
            await ctx.send("活動編號格式錯誤(RGE123)")
            return

        if event_code in self.bot.events:
            await ctx.send("活動編號已存在")
            return

        self.bot.events[event_code] = {
            "event_code": event_code,
            "event_name": event_name,
            "event_description": event_description,
            "event_start_date": event_start_date,
            "event_end_date": event_end_date,
            "gamer_list": []
        }
        await ctx.send(f"已建立活動 {event_name}(編號:{event_code})")

    @commands.has_permissions(administrator=True)
    @commands.command(name="給予點數")
    async def give_points(self, ctx: commands.Context, user_id: int, points: int):
        if not hasattr(self.bot, "add_points_internal"):
            await ctx.send("bot 未定義 add_points_internal")
            return

        if user_id not in self.bot.gamers:
            await ctx.send("玩家不存在或尚未綁定卡片")
            return

        msg = self.bot.add_points_internal(user_id, points)
        await ctx.send(msg)

    @commands.has_permissions(administrator=True)
    @commands.command(name="查詢活動")
    async def query_event(self, ctx: commands.Context, event_code: str):
        if event_code not in self.bot.events:
            await ctx.send(f"活動 {event_code} 不存在")
            return
        ev = self.bot.events[event_code]
        glist = ev["gamer_list"]
        gamers_str = ", ".join(str(gid) for gid in glist) if glist else "無玩家"
        await ctx.send(
            f"活動編號：{ev['event_code']}\n"
            f"名稱：{ev['event_name']}\n"
            f"描述：{ev['event_description']}\n"
            f"開始：{ev['event_start_date']}，結束：{ev['event_end_date']}\n"
            f"玩家列表：{gamers_str}"
        )

    @commands.has_permissions(administrator=True)
    @commands.command(name="查詢玩家點數")
    async def query_points(self, ctx: commands.Context, user_id: int):
        if user_id not in self.bot.gamers:
            await ctx.send("該玩家尚未綁卡")
            return
        pts = sum(self.bot.gamers[user_id].get("history_event_pts_list", []))
        await ctx.send(f"玩家 {user_id} 目前總點數：{pts}")

async def setup(bot: commands.Bot):
    await bot.add_cog(EventManagementCog(bot))
    print("EventManagementCog 已成功加載。")
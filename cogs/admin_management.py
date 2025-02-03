# cogs/admin_management.py

import discord
from discord.ext import commands
import re
import os
from dotenv import load_dotenv

load_dotenv()
ADMIN_CHANNEL_ID = int(os.getenv("ADMIN_CHANNEL_ID"))

def is_admin_channel(ctx):
    return ctx.channel.id == ADMIN_CHANNEL_ID

class AdminManagementCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def create_default_task_for_event(self, event_id: int, event_name: str):
        """
        建立一個預設任務，並加到 self.bot.tasks 與 self.bot.events[event_id]["task_list"] 裡
        """
        new_task_id = len(self.bot.tasks) + 1
        task_info = {
            "task_id": new_task_id,
            "task_name": f"{event_name}-投稿任務",
            "task_description": f"預設投稿任務 for {event_name}",
            "task_points": 1,  # 可調整
            "event_id": event_id,
            "gamer_list": []
        }
        self.bot.tasks[new_task_id] = task_info
        self.bot.events[event_id]["task_list"].append(task_info)

    @commands.has_permissions(administrator=True)
    @commands.check(is_admin_channel)
    @commands.command(name="admin_create_event")
    async def admin_create_event(self, ctx: commands.Context, event_name: str, event_description: str, event_start_date: str, event_end_date: str):
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
        # 自動建立預設任務
        self.create_default_task_for_event(event_id, event_name)

        await ctx.send(f"活動 {event_name} 已新增 (ID={event_id})，並自動建立預設任務。")

    @commands.has_permissions(administrator=True)
    @commands.check(is_admin_channel)
    @commands.command(name="admin_modify_event")
    async def admin_modify_event(self, ctx: commands.Context, event_id: int, event_name: str = None, event_description: str = None, event_start_date: str = None, event_end_date: str = None):
        if event_id not in self.bot.events:
            await ctx.send("活動不存在。")
            return
        event = self.bot.events[event_id]
        if event_name:
            event["event_name"] = event_name
        if event_description:
            event["event_description"] = event_description
        if event_start_date:
            event["event_start_date"] = event_start_date
        if event_end_date:
            event["event_end_date"] = event_end_date
        await ctx.send(f"活動 {event_id} 已修改。")

    @commands.has_permissions(administrator=True)
    @commands.check(is_admin_channel)
    @commands.command(name="admin_delete_event")
    async def admin_delete_event(self, ctx: commands.Context, event_id: int):
        if event_id not in self.bot.events:
            await ctx.send("活動不存在。")
            return
        del self.bot.events[event_id]
        await ctx.send(f"活動 {event_id} 已刪除。")

    @commands.has_permissions(administrator=True)
    @commands.check(is_admin_channel)
    @commands.command(name="admin_query_event")
    async def admin_query_event(self, ctx: commands.Context, event_id: int):
        if event_id not in self.bot.events:
            await ctx.send("活動不存在。")
            return
        event = self.bot.events[event_id]
        tasks_info = "\n".join([f" - 任務 ID={t['task_id']}, 名稱={t['task_name']}" for t in event["task_list"]])
        gamers_in_event = ", ".join(str(g_id) for g_id in event["gamer_list"])
        await ctx.send(
            f"活動 {event_id}:\n"
            f"名稱: {event['event_name']}\n"
            f"描述: {event['event_description']}\n"
            f"開始: {event['event_start_date']}, 結束: {event['event_end_date']}\n"
            f"任務列表:\n{tasks_info}\n"
            f"玩家列表: {gamers_in_event}"
        )

    @commands.has_permissions(administrator=True)
    @commands.check(is_admin_channel)
    @commands.command(name="admin_modify_points")
    async def admin_modify_points(self, ctx: commands.Context, user_id: int, points: int):
        from main import add_points_internal
        msg = add_points_internal(user_id, points)
        await ctx.send(msg)

    @commands.has_permissions(administrator=True)
    @commands.check(is_admin_channel)
    @commands.command(name="admin_modify_card")
    async def admin_modify_card(self, ctx: commands.Context, user_id: int, new_card_number: str):
        import re
        from main import gamers
        card_pattern = re.compile(r'^(?=.*[0-9])(?=.*[A-Za-z])[A-Za-z0-9]{8}$')
        if not card_pattern.match(new_card_number):
            await ctx.send("卡號格式錯誤！需包含 8 位英數字，且至少包含 1 英文字母與 1 數字。")
            return
        if user_id not in gamers:
            gamers[user_id] = {
                "gamer_id": user_id,
                "gamer_dcid": f"UnknownUser{user_id}",
                "gamer_card_number": new_card_number,
                "gamer_is_blocked": False,
                "gamer_bind_gamepass": None,
                "history_event_list": [],
                "history_event_pts_list": [],
                "history_task_list": []
            }
        else:
            gamers[user_id]["gamer_card_number"] = new_card_number
        await ctx.send(f"使用者 {user_id} 的卡號已更新為 {new_card_number}。")

    @commands.has_permissions(administrator=True)
    @commands.check(is_admin_channel)
    @commands.command(name="admin_delete_card")
    async def admin_delete_card(self, ctx: commands.Context, user_id: int):
        from main import gamers
        if user_id in gamers and gamers[user_id].get("gamer_card_number"):
            gamers[user_id]["gamer_card_number"] = None
            await ctx.send(f"已清除使用者 {user_id} 的卡號。")
        else:
            await ctx.send("使用者尚未綁定卡號或玩家不存在。")

async def setup(bot: commands.Bot):
    await bot.add_cog(AdminManagementCog(bot))
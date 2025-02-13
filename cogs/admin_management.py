import discord
from discord.ext import commands
from discord.ui import View, Select, Modal, TextInput
import re
import os
import asyncio
from dotenv import load_dotenv
from main import save_data, update_event_max_points  
from typing import Optional, List
from datetime import datetime, timedelta

load_dotenv()
ADMIN_CHANNEL_ID = int(os.getenv("ADMIN_CHANNEL_ID"))

def is_admin_channel(ctx):
    return ctx.channel.id == ADMIN_CHANNEL_ID

class CreateEventModal(Modal):
    def __init__(self, bot: commands.Bot):
        super().__init__(title="創立活動")
        self.bot = bot

        self.event_code = TextInput(
            label="活動編號 (RAEXXX)",
            placeholder="RAEXXX",
            max_length=6
        )
        self.event_name = TextInput(
            label="活動名稱",
            placeholder="請輸入活動名稱",
            max_length=20
        )
        self.event_desc = TextInput(
            label="活動描述",
            placeholder="請輸入活動描述",
            max_length=50
        )
        self.start_date = TextInput(
            label="開始日期",
            placeholder="yyyy-mm-dd"
        )
        self.end_date = TextInput(
            label="結束日期",
            placeholder="yyyy-mm-dd"
        )

        self.add_item(self.event_code)
        self.add_item(self.event_name)
        self.add_item(self.event_desc)
        self.add_item(self.start_date)
        self.add_item(self.end_date)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            code = self.event_code.value.strip()
            pattern = r'^RAE(?=.*[0-9])[A-Za-z0-9]{3}$'
            if not re.match(pattern, code):
                await interaction.followup.send("活動編號格式錯誤！(須為 RAEXXX)", ephemeral=True)
                return
            if not hasattr(self.bot, "events"):
                self.bot.events = {}
            if code in self.bot.events:
                await interaction.followup.send("該活動編號已存在。", ephemeral=True)
                return

            try:
                start_date = datetime.strptime(self.start_date.value.strip(), "%Y-%m-%d").date()
                end_date = datetime.strptime(self.end_date.value.strip(), "%Y-%m-%d").date()
            except ValueError:
                await interaction.followup.send("日期格式錯誤，應為 YYYY-MM-DD", ephemeral=True)
                return
            
            now_date=(datetime.utcnow() + timedelta(hours=8)).date()
            if end_date < now_date:
                await interaction.followup.send("結束日期不能小於當前日期！", ephemeral=True)
                return

            self.bot.events[code] = {
                "event_code": code,
                "event_name": self.event_name.value.strip(),
                "event_description": self.event_desc.value.strip(),
                "event_start_date": self.start_date.value.strip(),
                "event_end_date": self.end_date.value.strip(),
                "gamer_list": [],
                "tasks": [],
                "max_points": 0
            }
            save_data()
            await interaction.followup.send(
                f"活動 {self.event_name.value} 已建立，編號：{code}。\n請使用【新增任務】功能加入任務。",
                ephemeral=True
            )
        except Exception as e:
            print("Error in CreateEventModal.on_submit:", e)
            await interaction.followup.send("建立活動時發生錯誤。", ephemeral=True)

class CreateTaskModal(Modal):
    def __init__(self, bot: commands.Bot):
        super().__init__(title="新增任務")
        self.bot = bot

        self.event_code = TextInput(
            label="活動編號",
            placeholder="RAEXXX",
            max_length=10
        )
        self.task_name = TextInput(
            label="任務名稱",
            placeholder="輸入任務名稱",
            max_length=50
        )
        self.task_description = TextInput(
            label="任務描述",
            placeholder="輸入任務描述",
            max_length=100
        )
        self.task_points = TextInput(
            label="任務給予的點數",
            placeholder="輸入任務點數",
            max_length=10
        )
        self.add_item(self.event_code)
        self.add_item(self.task_name)
        self.add_item(self.task_description)
        self.add_item(self.task_points)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            event_code = self.event_code.value.strip()
            task_name = self.task_name.value.strip()
            task_desc = self.task_description.value.strip()
            task_points_str = self.task_points.value.strip()

            if not event_code or not task_name or not task_points_str:
                await interaction.followup.send("活動編號、任務名稱及任務點數為必填！", ephemeral=True)
                return

            try:
                task_points = int(task_points_str)
            except ValueError:
                await interaction.followup.send("任務點數必須是數字！", ephemeral=True)
                return
            if event_code not in self.bot.events:
                await interaction.followup.send("活動編號不存在！", ephemeral=True)
                return

            tasks = self.bot.events[event_code].get("tasks", [])
            new_id = len(tasks) + 1
            tasks.append({
                "task_id": new_id,
                "task_name": task_name,
                "task_description": task_desc, 
                "task_points": task_points,
                "assigned_users": [],
                "checked_users": []
            })
            self.bot.events[event_code]["tasks"] = tasks
            update_event_max_points(self.bot.events[event_code])
            save_data()

            await interaction.followup.send(
                f"已新增任務 {task_name} 到活動 {event_code}，可給予點數：{task_points}",
                ephemeral=True
            )
        except Exception as e:
            print("Error in CreateTaskModal.on_submit:", e)
            await interaction.followup.send("新增任務時發生錯誤。", ephemeral=True)

class ModifyCardModal(Modal):
    def __init__(self, bot: commands.Bot):
        super().__init__(title="修改玩家卡號")
        self.bot = bot

        self.user_id = TextInput(label="玩家Dicscord ID", placeholder="請詢問更改者DC ID編號", max_length=20)
        self.new_card = TextInput(label="新卡號(RGPXXXXX)", placeholder="RGPXXXXX", max_length=8)

        self.add_item(self.user_id)
        self.add_item(self.new_card)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            user_id_int = int(self.user_id.value)
        except ValueError:
            await interaction.followup.send("玩家ID必須是數字", ephemeral=True)
            return

        card_pattern = re.compile(r'^(?=.*[0-9])(?=.*[A-Za-z])[A-Za-z0-9]{8}$')
        if not card_pattern.match(self.new_card.value):
            await interaction.followup.send("卡號格式錯誤，請重新輸入", ephemeral=True)
            return

        if user_id_int not in self.bot.gamers:
            self.bot.gamers[user_id_int] = {
                "gamer_id": user_id_int,
                "gamer_card_number": self.new_card.value,
                "gamer_is_blocked": False,
                "gamer_bind_gamepass": None,
                "joined_events": [],
                "history_event_list": [],
                "history_event_pts_list": [],
                "events_points": {}  
            }
        else:
            self.bot.gamers[user_id_int]["gamer_card_number"] = self.new_card.value

        save_data()
        await interaction.followup.send(
            f"玩家 {user_id_int} 的卡號已更新為 {self.new_card.value}", 
            ephemeral=True
        )

class QueryCardByUserModal(Modal):
    def __init__(self, bot: commands.Bot):
        super().__init__(title="查詢玩家卡號(DC ID)")
        self.bot = bot
        self.user_id = TextInput(label="玩家DC ID", placeholder="請詢問更改者DC ID編號", max_length=20)
        self.add_item(self.user_id)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            user_id_int = int(self.user_id.value)
        except ValueError:
            await interaction.followup.send("玩家DC ID必須是數字", ephemeral=True)
            return
        
        if user_id_int not in self.bot.gamers:
            await interaction.followup.send("該玩家不存在或尚未綁定卡號", ephemeral=True)
            return
        
        card = self.bot.gamers[user_id_int].get("gamer_card_number")
        if card:
            await interaction.followup.send(f"玩家 {user_id_int} 的卡號為：{card}", ephemeral=True)
        else:
            await interaction.followup.send(f"玩家 {user_id_int} 尚未綁定卡號", ephemeral=True)

class QueryUserByCardModal(Modal):
    def __init__(self, bot: commands.Bot):
        super().__init__(title="查詢玩家DC ID(使用競音卡號)")
        self.bot = bot
        self.card_number = TextInput(label="卡號", placeholder="RGPXXXXX", max_length=8)
        self.add_item(self.card_number)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        card = self.card_number.value.strip()
        found_user = None
        for g_id, data in self.bot.gamers.items():
            if data.get("gamer_card_number") == card:
                found_user = g_id
                break

        if found_user is None:
            await interaction.followup.send("找不到此卡號的玩家", ephemeral=True)
        else:
            await interaction.followup.send(f"卡號 {card} 屬於玩家 {found_user}", ephemeral=True)

class AddPointsModal(Modal):
    def __init__(self, bot: commands.Bot):
        super().__init__(title="手動給予點數")
        self.bot = bot

        self.user_id = TextInput(label="玩家DC ID", placeholder="數字", max_length=20)
        self.points = TextInput(label="點數", placeholder="要加多少點數", max_length=10)
        self.add_item(self.user_id)
        self.add_item(self.points)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            uid = int(self.user_id.value)
            pts = int(self.points.value)
        except ValueError:
            await interaction.followup.send("玩家ID和點數都必須是數字", ephemeral=True)
            return

        if not hasattr(self.bot, "add_points_internal"):
            await interaction.followup.send("bot 未定義 add_points_internal，無法增加點數", ephemeral=True)
            return

        msg = self.bot.add_points_internal(uid, pts)
        await interaction.followup.send(msg, ephemeral=True)

class QueryAllGamersModal(Modal):
    def __init__(self, bot: commands.Bot):
        super().__init__(title="玩家查詢(可利用關鍵字查詢)")
        self.bot = bot

        self.keyword = TextInput(
            label="關鍵字(盡量不要空白)",
            placeholder="請輸入關鍵字, 空白則會將全部的玩家列出（建議不要使用）",
            required=False
        )
        self.add_item(self.keyword)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        kw = self.keyword.value.strip().lower()
        results = []
        for g_id, data in self.bot.gamers.items():
            text_to_check = (f"{data.get('gamer_card_number','')}").lower()
            if kw == "" or kw in text_to_check:
                results.append((g_id, data))

        if not results:
            await interaction.followup.send("找不到任何符合的玩家", ephemeral=True)
            return

        msg_lines = []
        for g_id, info in results:
            msg_lines.append(f"ID={g_id}, 卡號={info['gamer_card_number']}, 黑名單={info['gamer_is_blocked']},或可以至 https://ra-bot-beta.elvislo.tw/dashboard 查詢")
        final_msg = "\n".join(msg_lines)
        await interaction.followup.send(final_msg, ephemeral=True)

class BlockUnblockModal(Modal):
    def __init__(self, bot: commands.Bot):
        super().__init__(title="封鎖/解鎖 玩家")
        self.bot = bot

        self.user_id = TextInput(label="玩家ID", placeholder="數字", max_length=20)
        self.block_or_unblock = TextInput(label="輸入 block / unblock", placeholder="block 或 unblock")

        self.add_item(self.user_id)
        self.add_item(self.block_or_unblock)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            user_id_int = int(self.user_id.value)
        except ValueError:
            await interaction.followup.send("玩家ID必須是數字", ephemeral=True)
            return

        action = self.block_or_unblock.value.strip().lower()
        if user_id_int not in self.bot.gamers:
            await interaction.followup.send("該玩家不存在", ephemeral=True)
            return

        if action == "block":
            self.bot.gamers[user_id_int]["gamer_is_blocked"] = True
            await interaction.followup.send(f"玩家 {user_id_int} 已被封鎖", ephemeral=True)
        elif action == "unblock":
            self.bot.gamers[user_id_int]["gamer_is_blocked"] = False
            await interaction.followup.send(f"玩家 {user_id_int} 已解除封鎖", ephemeral=True)
        else:
            await interaction.followup.send("請輸入 block 或 unblock", ephemeral=True)

class AdminManagementSelect(Select):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        options = [
            discord.SelectOption(label="後台網站查詢", value="dashboard"),
            discord.SelectOption(label="建立活動", value="create_event"),
            discord.SelectOption(label="新增任務", description="新增任務到指定活動", value="add_task"),
            discord.SelectOption(label="查詢玩家資料", description="以關鍵字或全部列出", value="query_all_gamers"),
            discord.SelectOption(label="修改玩家卡號", description="需玩家的DC ID", value="modify_card_modal"),
            discord.SelectOption(label="查詢玩家卡號", description="需玩家的DC ID", value="query_card_by_user"),
            discord.SelectOption(label="查詢玩家DC ID", description="輸入卡號查詢玩家DC ID", value="query_user_by_card"),
            discord.SelectOption(label="封鎖/解除封鎖玩家", value="block_unblock")
        ]
        super().__init__(placeholder="選擇管理功能...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        choice = self.values[0]

        if choice == "query_card_by_user":
            modal = QueryCardByUserModal(self.bot)
            await interaction.response.send_modal(modal)

        elif choice == "query_user_by_card":
            modal = QueryUserByCardModal(self.bot)
            await interaction.response.send_modal(modal)

        elif choice == "query_all_gamers":
            modal = QueryAllGamersModal(self.bot)
            await interaction.response.send_modal(modal)

        elif choice == "block_unblock":
            modal = BlockUnblockModal(self.bot)
            await interaction.response.send_modal(modal)

        elif choice == "create_event":
            modal = CreateEventModal(self.bot)
            await interaction.response.send_modal(modal)

        elif choice == "modify_card_modal":
            modal = ModifyCardModal(self.bot)
            await interaction.response.send_modal(modal)

        elif choice == "add_points_modal":
            modal = AddPointsModal(self.bot)
            await interaction.response.send_modal(modal)

        elif choice == "add_task":
            modal = CreateTaskModal(self.bot)
            await interaction.response.send_modal(modal)

        elif choice == "dashboard":
            await interaction.response.send_message("https://ra-bot-beta.elvislo.tw/dashboard", ephemeral=True)
            
class AdminManagementView(View):
    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=None)
        self.add_item(AdminManagementSelect(bot))

class AdminManagementCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def is_admin_channel(ctx):
        return ctx.channel.id == ADMIN_CHANNEL_ID

    @commands.has_permissions(administrator=True)
    @commands.check(is_admin_channel)
    @commands.command(name="後台管理")
    async def backend_management(self, ctx: commands.Context):
        view = AdminManagementView(self.bot)
        await ctx.send("後台管理面板：請選擇功能", view=view)

async def setup(bot: commands.Bot):
    await bot.add_cog(AdminManagementCog(bot))
    print("AdminManagementCog 已成功加載。")
import discord
from discord.ext import commands
from discord.ui import View, Select, Modal, TextInput
import re
import os
import asyncio
from dotenv import load_dotenv
from main import save_data, update_event_max_points, record_api
from typing import Optional, List
from datetime import datetime, timedelta

load_dotenv()
ADMIN_CHANNEL_ID = int(os.getenv("ADMIN_CHANNEL_ID"))

def is_admin_channel(ctx):
    return ctx.channel.id == ADMIN_CHANNEL_ID

########################################
# 建立活動 Modal
########################################
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

            # 重新顯示「活動管理」下拉
            view = EventManagementView(self.bot)
            await interaction.followup.send("請繼續選擇活動管理功能：", view=view, ephemeral=True)

        except Exception as e:
            print("Error in CreateEventModal.on_submit:", e)
            await interaction.followup.send("建立活動時發生錯誤。", ephemeral=True)

########################################
# 新增任務 Modal
########################################
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

            # 重新顯示「活動管理」下拉
            view = EventManagementView(self.bot)
            await interaction.followup.send("請繼續選擇活動管理功能：", view=view, ephemeral=True)

        except Exception as e:
            print("Error in CreateTaskModal.on_submit:", e)
            await interaction.followup.send("新增任務時發生錯誤。", ephemeral=True)

########################################
# 新增獎品 Modal
########################################
class CreatePrizeModal(Modal):
    def __init__(self, bot: commands.Bot):
        super().__init__(title="新增獎品")
        self.bot = bot

        self.event_code = TextInput(
            label="活動編號 (RAEXXX)",
            placeholder="RAEXXX",
            max_length=10
        )
        self.prize_name = TextInput(
            label="獎品名稱",
            placeholder="請輸入獎品名稱",
            max_length=50
        )
        self.points_required = TextInput(
            label="所需點數",
            placeholder="兌換此獎品所需點數",
            max_length=10
        )
        self.add_item(self.event_code)
        self.add_item(self.prize_name)
        self.add_item(self.points_required)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            code = self.event_code.value.strip()
            p_name = self.prize_name.value.strip()
            p_cost_str = self.points_required.value.strip()

            if code not in self.bot.events:
                await interaction.followup.send(f"活動 {code} 不存在，無法新增獎品。", ephemeral=True)
                return
            
            try:
                p_cost = int(p_cost_str)
            except ValueError:
                await interaction.followup.send("所需點數必須是數字！", ephemeral=True)
                return

            # 新增獎品
            self.bot.events[code].setdefault("prizes", [])
            new_prize = {
                "prize_id": len(self.bot.events[code]["prizes"]) + 1,
                "prize_name": p_name,
                "points_required": p_cost
            }
            self.bot.events[code]["prizes"].append(new_prize)

            record_api("create_prize", {
                "event_code": code,
                "prize_name": p_name,
                "cost": p_cost,
                "timestamp": (datetime.utcnow() + timedelta(hours=8)).isoformat()
            })

            save_data()
            await interaction.followup.send(
                f"已為活動 {code} 新增獎品：{p_name} (需要 {p_cost} 點)",
                ephemeral=True
            )

            # 重新顯示「活動管理」下拉
            view = EventManagementView(self.bot)
            await interaction.followup.send("請繼續選擇活動管理功能：", view=view, ephemeral=True)

        except Exception as e:
            print("Error in CreatePrizeModal.on_submit:", e)
            await interaction.followup.send("新增獎品時發生錯誤。", ephemeral=True)

########################################
# 選單 - 只包含: 後台網站查詢, 建立活動, 新增任務, 新增獎品
########################################
class EventManagementSelect(Select):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        options = [
            discord.SelectOption(label="後台網站查詢", value="dashboard"),
            discord.SelectOption(label="建立活動", description="建立新的活動 (RAEXXX)", value="create_event"),
            discord.SelectOption(label="新增任務", description="新增任務到指定活動", value="add_task"),
            discord.SelectOption(label="新增獎品", description="新增活動獎品", value="add_prize")
        ]
        super().__init__(placeholder="選擇活動管理功能...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        choice = self.values[0]

        if choice == "dashboard":
            await interaction.response.send_message("https://ra-bot-beta.elvislo.tw/dashboard", ephemeral=True)
            # 顯示下拉選單以便後續操作
            view = EventManagementView(self.bot)
            await interaction.followup.send("請繼續選擇活動管理功能：", view=view, ephemeral=True)

        elif choice == "create_event":
            modal = CreateEventModal(self.bot)
            await interaction.response.send_modal(modal)

        elif choice == "add_task":
            modal = CreateTaskModal(self.bot)
            await interaction.response.send_modal(modal)

        elif choice == "add_prize":
            modal = CreatePrizeModal(self.bot)
            await interaction.response.send_modal(modal)

class EventManagementView(View):
    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=None)
        self.add_item(EventManagementSelect(bot))

########################################
# Cog: 使用 "RA 活動管理" 指令
########################################
class EventManagementCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def is_admin_channel(ctx):
        return ctx.channel.id == ADMIN_CHANNEL_ID

    @commands.has_permissions(administrator=True)
    @commands.check(is_admin_channel)
    @commands.command(name="活動管理")
    async def event_management(self, ctx: commands.Context):
        """
        在指定頻道呼叫 RA 活動管理 指令，
        顯示活動管理面板(後台網站查詢, 建立活動, 新增任務, 新增獎品)
        """
        view = EventManagementView(self.bot)
        await ctx.send("活動管理面板：請選擇功能", view=view)

async def setup(bot: commands.Bot):
    await bot.add_cog(EventManagementCog(bot))
    print("EventManagementCog 已成功加載。")
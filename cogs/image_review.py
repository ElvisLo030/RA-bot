import discord
import os
from discord.ext import commands
from discord.ui import View, Button
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()
TARGET_CHANNEL_ID = int(os.getenv("TARGET_CHANNEL_ID"))

class ApproveButton(discord.ui.Button):
    def __init__(self, bot: commands.Bot, user_id: int, filename: str, event_code: str, task_id: int, task_points: int):
        super().__init__(style=discord.ButtonStyle.success, label=f"通過 (+{task_points}點)")
        self.bot = bot
        self.user_id = user_id
        self.filename = filename
        self.event_code = event_code
        self.task_id = task_id
        self.task_points = task_points

    async def callback(self, interaction: discord.Interaction):
        data = self.bot.user_images.get(self.user_id, [])
        for img in data:
            if (
                img["filename"] == self.filename
                and img.get("task_id") == self.task_id
                and img["status"] == "pending"
            ):
                user = self.bot.get_user(self.user_id) or await self.bot.fetch_user(self.user_id)
                if not user:
                    return

                event_name = "N/A"
                task_name = f"任務ID={self.task_id}"
                event_obj = self.bot.events.get(self.event_code)
                if event_obj:
                    event_name = event_obj.get("event_name", "N/A")
                    for t in event_obj.get("tasks", []):
                        if t["task_id"] == self.task_id:
                            task_name = f"{t.get('task_name','無任務名稱')} (ID={self.task_id})"
                            if self.user_id not in t["checked_users"]:
                                t["checked_users"].append(self.user_id)
                            break

                img["status"] = "approved"
                img["approved_time"] = (datetime.utcnow() + timedelta(hours=8)).isoformat()

                try:
                    result_msg = self.bot.add_event_points_internal(self.user_id, self.event_code, self.task_points)
                except AttributeError:
                    result_msg = "bot 未定義 add_event_points_internal"

                await user.send(
                    f"圖片 `{self.filename}` \n活動：{event_name} 任務：{task_name} \n審核已通過 +{self.task_points}點。"
                )

                await interaction.response.send_message(
                    f"審核通過 `{self.filename}` (+{self.task_points}點)。\n({result_msg})", ephemeral=True
                )

                view: ReviewView = self.view  
                await view.disable_review(interaction, f"{task_name} 審核：已通過(+{self.task_points}點)")
                return

class RejectButton(discord.ui.Button):
    def __init__(self, bot: commands.Bot, user_id: int, filename: str, event_code: str, task_id: int):
        super().__init__(style=discord.ButtonStyle.danger, label="拒絕")
        self.bot = bot
        self.user_id = user_id
        self.filename = filename
        self.event_code = event_code
        self.task_id = task_id

    async def callback(self, interaction: discord.Interaction):
        data = self.bot.user_images.get(self.user_id, [])
        for img in data:
            if (
                img["filename"] == self.filename
                and img.get("task_id") == self.task_id
                and img["status"] == "pending"
            ):
                user = self.bot.get_user(self.user_id) or await self.bot.fetch_user(self.user_id)
                if not user:
                    return

                event_name = "N/A"
                task_name = f"任務ID={self.task_id}"
                event_obj = self.bot.events.get(self.event_code)
                if event_obj:
                    event_name = event_obj.get("event_name", "N/A")
                    for t in event_obj.get("tasks", []):
                        if t["task_id"] == self.task_id:
                            task_name = f"{t.get('task_name','無任務名稱')} (ID={self.task_id})"
                            break
                img["status"] = "rejected"
                img["rejected_time"] = (datetime.utcnow() + timedelta(hours=8)).isoformat()

                await user.send(
                    f"你的圖片 `{self.filename}`審核未通過，請重新上傳。\n活動：{event_name} 任務：{task_name}"
                )

                await interaction.response.send_message(
                    f"已拒絕 `{self.filename}` (任務名稱：{task_name})", ephemeral=True
                )

                view: ReviewView = self.view  
                await view.disable_review(interaction, f"{task_name} 審核：已拒絕")
                return

class ReviewView(View):
    def __init__(self, bot: commands.Bot, user_id: int, filename: str, event_code: str, task_id: int):
        super().__init__(timeout=None)
        self.bot = bot
        self.user_id = user_id
        self.filename = filename
        self.event_code = event_code
        self.task_id = task_id
        task_points = 0
        event_obj = self.bot.events.get(event_code)
        if event_obj:
            for t in event_obj.get("tasks", []):
                if t["task_id"] == task_id:
                    task_points = t.get("task_points", 0)
                    break

        self.add_item(ApproveButton(bot, user_id, filename, event_code, task_id, task_points))
        self.add_item(RejectButton(bot, user_id, filename, event_code, task_id))

    async def disable_review(self, interaction: discord.Interaction, status: str):
        for c in self.children:
            c.disabled = True
        await interaction.message.edit(
            content=f"圖片 `{self.filename}` 審核狀態：{status}", 
            view=self
        )

class TaskSelectForImage(discord.ui.Select):
    def __init__(self, bot: commands.Bot, ctx: commands.Context, attachment: discord.Attachment, event_code: str):
        self.bot = bot
        self.ctx = ctx
        self.attachment = attachment
        self.event_code = event_code
        event_obj = self.bot.events.get(self.event_code)
        options = []
        if event_obj and "tasks" in event_obj:
            for t in event_obj["tasks"]:
                task_label = f"任務{t['task_id']}：{t['task_name']}"
                options.append(discord.SelectOption(
                    label=task_label,
                    value=str(t['task_id'])
                ))
        super().__init__(
            placeholder="選擇要上傳圖片的任務",
            min_values=1,
            max_values=1,
            options=options
        )
        self.error_message = None

    async def callback(self, interaction: discord.Interaction):
        if self.error_message:
            await interaction.response.send_message(self.error_message, ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        await interaction.edit_original_response(content="上傳中，請勿離開頁或選擇其他活動")
        chosen_task_id = int(self.values[0])
        channel = self.bot.get_channel(TARGET_CHANNEL_ID)
        if not channel:
            await interaction.followup.send("找不到審核頻道，請通知管理員。", ephemeral=True)
            return

        event_obj = self.bot.events.get(self.event_code)
        if not event_obj:
            await interaction.followup.send("活動不存在，請通知管理員。", ephemeral=True)
            return

        task_name = "未知任務"
        for t in event_obj["tasks"]:
            if t["task_id"] == chosen_task_id:
                if self.ctx.author.id in t["checked_users"]:
                    await interaction.followup.send("你已通過此任務，無法重複上傳。", ephemeral=True)
                    return
                if self.ctx.author.id not in t["assigned_users"]:
                    t["assigned_users"].append(self.ctx.author.id)
                task_name = t.get("task_name", "無任務名稱")
                break

        event_name = event_obj.get("event_name", "未知活動")
        image_data = {
            "filename": self.attachment.filename,
            "user_id": self.ctx.author.id,
            "username": self.ctx.author.name,
            "status": "pending",
            "event_code": self.event_code,
            "task_id": chosen_task_id,
            "upload_time": (datetime.utcnow() + timedelta(hours=8)).isoformat()
        }
        self.bot.user_images.setdefault(self.ctx.author.id, []).append(image_data)

        try:
            file = await self.attachment.to_file()
            view = ReviewView(
                self.bot,
                self.ctx.author.id,
                self.attachment.filename,
                self.event_code,
                chosen_task_id
            )
            await channel.send(
                content=(
                    f"使用者 <@{self.ctx.author.id}> 上傳圖片：`{self.attachment.filename}`\n"
                    f"活動：{event_name} (編號={self.event_code})\n"
                    f"任務：{task_name} (ID={chosen_task_id}) 等待審核..."
                ),
                file=file,
                view=view
            )
            await interaction.followup.send(
                f"圖片 `{self.attachment.filename}` 已送出審核！(提交的任務：{task_name})", 
                ephemeral=True
            )
        except Exception as e:
            print(f"Error in TaskSelectForImage.callback: {e}")
            await interaction.followup.send("上傳至審核頻道失敗，請通知管理員排除。", ephemeral=True)
            return

        for c in self.view.children:
            c.disabled = True
        await interaction.edit_original_response(view=self.view)

class TaskSelectView(View):
    def __init__(self, bot: commands.Bot, ctx: commands.Context, attachment: discord.Attachment, event_code: str):
        super().__init__(timeout=120)
        self.add_item(TaskSelectForImage(bot, ctx, attachment, event_code))

class ImageReviewCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="上傳圖片")
    async def upload_image(self, ctx: commands.Context, event_code: str = None):
        if not isinstance(ctx.channel, discord.DMChannel):
            await ctx.send("請在私訊使用此指令。")
            return

        if not event_code:
            await ctx.send("請輸入活動編號，如: RA 上傳圖片 RAE001")
            return

        user_data = self.bot.gamers.get(ctx.author.id)
        if not user_data:
            await ctx.send("你尚未綁定卡片或參加活動。")
            return

        joined = user_data.get("joined_events", [])
        if event_code not in joined:
            await ctx.send(f"你尚未參加活動 {event_code}，無法上傳圖片。")
            return

        if event_code not in self.bot.events:
            await ctx.send(f"活動 {event_code} 不存在。")
            return

        try:
            end_date = datetime.strptime(self.bot.events[event_code]["event_end_date"], "%Y-%m-%d").date()
            today_date = (datetime.utcnow() + timedelta(hours=8)).date()
            if today_date > end_date:
                await ctx.send(f"活動 {event_code} 已過期，無法上傳圖片。")
                return
        except Exception:
            await ctx.send("活動結束日期格式錯誤，請通知管理員。")
            return

        if not ctx.message.attachments:
            await ctx.send("請附加圖片後再試一次。")
            return

        attachment = ctx.message.attachments[0]
        if not attachment.filename.lower().endswith((".png", ".jpg", ".jpeg", ".gif")):
            await ctx.send("限圖片檔 (.png/.jpg/.jpeg/.gif)")
            return

        event_obj = self.bot.events[event_code]
        if not event_obj.get("tasks"):
            await ctx.send("該活動尚未有任務配置或任務為空。")
            return

        await ctx.send(
            "請選擇要上傳到哪個任務：",
            view=TaskSelectView(self.bot, ctx, attachment, event_code)
        )

async def setup(bot: commands.Bot):
    await bot.add_cog(ImageReviewCog(bot))
    print("ImageReviewCog 已成功加載。")
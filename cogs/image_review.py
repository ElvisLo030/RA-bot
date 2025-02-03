# cogs/image_review.py

import discord
import os
from discord.ext import commands
from discord.ui import View, Select
from typing import Dict, List
from dotenv import load_dotenv

load_dotenv()

TARGET_CHANNEL_ID = int(os.getenv("TARGET_CHANNEL_ID"))

class ReviewSelect(discord.ui.Select):
    def __init__(self, bot: commands.Bot, user_id: int, filename: str, event_id: int, task_id: int):
        options = [
            discord.SelectOption(label="累計1點（通過）", value="1"),
            discord.SelectOption(label="累計2點（通過）", value="2"),
            discord.SelectOption(label="累計3點（通過）", value="3"),
            discord.SelectOption(label="退回", value="reject")
        ]
        super().__init__(
            placeholder="請選擇審核結果",
            min_values=1,
            max_values=1,
            options=options
        )
        self.bot = bot
        self.user_id = user_id
        self.filename = filename
        self.event_id = event_id
        self.task_id = task_id

    async def callback(self, interaction: discord.Interaction):
        selected_value = self.values[0]
        data = self.bot.user_images.get(self.user_id, [])
        for img in data:
            if img["filename"] == self.filename:
                user = self.bot.get_user(self.user_id) or await self.bot.fetch_user(self.user_id)
                if not user:
                    return

                # 取得活動/任務名稱
                event_name = "N/A"
                if self.event_id in self.bot.events:
                    event_name = self.bot.events[self.event_id]["event_name"]

                task_name = "N/A"
                if self.task_id in self.bot.tasks:
                    task_name = self.bot.tasks[self.task_id]["task_name"]

                if selected_value == "reject":
                    img["status"] = "rejected"
                    await user.send(
                        f"你的圖片 `{self.filename}` 已被退回。\n"
                        f"活動：{event_name}, 任務：{task_name}"
                    )
                    await interaction.response.send_message(
                        f"圖片 `{self.filename}` 已退回！", 
                        ephemeral=True
                    )
                    await self.disable_review(interaction, f"已退回 (活動:{event_name}, 任務:{task_name})")
                    return
                else:
                    points = int(selected_value)
                    img["status"] = "approved"
                    # 加點數
                    try:
                        from main import add_points_internal
                        result_msg = add_points_internal(self.user_id, points)
                    except ImportError:
                        result_msg = "import main失敗，無法加點數"

                    await user.send(
                        f"你的圖片 `{self.filename}` 已通過審核並獲得 {points} 點。\n"
                        f"活動：{event_name}, 任務：{task_name}"
                    )
                    await interaction.response.send_message(
                        f"圖片 `{self.filename}` 審核通過並累計 {points} 點！\n"
                        f"({result_msg})",
                        ephemeral=True
                    )
                    await self.disable_review(
                        interaction, 
                        f"已通過 (+{points}點), 活動:{event_name}, 任務:{task_name}"
                    )
                    return

    async def disable_review(self, interaction: discord.Interaction, status: str):
        for child in self.view.children:
            child.disabled = True
        await interaction.message.edit(
            content=f"圖片 `{self.filename}` 審核狀態：{status}",
            view=self.view
        )


class ReviewView(View):
    def __init__(self, bot: commands.Bot, user_id: int, filename: str, event_id: int, task_id: int):
        super().__init__(timeout=None)
        self.bot = bot
        self.user_id = user_id
        self.filename = filename
        self.event_id = event_id
        self.task_id = task_id
        self.add_item(ReviewSelect(bot, user_id, filename, event_id, task_id))


class ImageReviewCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="上傳圖片")
    async def upload_image(self, ctx: commands.Context, task_id: int = None):
        """
        使用: !RA 上傳圖片 <task_id>, 並附上圖片檔案
        若未參加此任務則無法上傳
        """
        # Debug：顯示目前執行指令的頻道類型
        print(f"DEBUG: channel={ctx.channel}, is_dm={isinstance(ctx.channel, discord.DMChannel)}")

        # 檢查是否在私訊頻道中執行
        if not isinstance(ctx.channel, discord.DMChannel):
            await ctx.send("請私訊機器人使用此指令。")
            print("DEBUG: 使用者不在私訊頻道，直接 return。")
            return

        # 檢查 task_id 是否有輸入
        if task_id is None:
            await ctx.send("請輸入任務ID，例如: !RA 上傳圖片 1")
            print("DEBUG: 未輸入 task_id，直接 return。")
            return

        # 檢查該 task_id 是否存在
        if task_id not in self.bot.tasks:
            await ctx.send(f"任務 {task_id} 不存在。")
            print(f"DEBUG: 任務 {task_id} 不存在，直接 return。")
            return

        # 檢查該使用者是否已加入任務
        if ctx.author.id not in self.bot.tasks[task_id]["gamer_list"]:
            await ctx.send(f"你尚未加入任務 {task_id}，無法上傳圖片。")
            print(f"DEBUG: 使用者 {ctx.author.id} 不在任務 {task_id} 的 gamer_list 中，return。")
            return

        # 檢查是否有附加檔案
        if not ctx.message.attachments:
            await ctx.send("請附加圖片後再試一次。")
            print("DEBUG: 使用者沒附加任何檔案，return。")
            return

        attachment = ctx.message.attachments[0]

        # 檢查副檔名
        if not attachment.filename.lower().endswith((".png", ".jpg", ".jpeg", ".gif")):
            await ctx.send("限圖片檔 (.png, .jpg, .jpeg, .gif)")
            print("DEBUG: 副檔名不符合圖片格式，return。")
            return

        # 取得對應的event_id
        event_id = self.bot.tasks[task_id]["event_id"]
        event_name = self.bot.events[event_id]["event_name"]
        task_name = self.bot.tasks[task_id]["task_name"]

        # 將圖片資訊存入 user_images
        image_data = {
            "filename": attachment.filename,
            "user_id": ctx.author.id,
            "username": ctx.author.name,
            "status": "pending",
            "event_id": event_id,
            "task_id": task_id
        }
        self.bot.user_images.setdefault(ctx.author.id, []).append(image_data)

        # 嘗試取得審核頻道
        channel = self.bot.get_channel(TARGET_CHANNEL_ID)
        print(f"DEBUG: 嘗試取得頻道 ID={TARGET_CHANNEL_ID}, 結果={channel}")

        if not channel:
            await ctx.send("找不到審核頻道，請檢查 TARGET_CHANNEL_ID 是否正確。")
            print("DEBUG: channel 為 None，return。")
            return

        try:
            # 轉檔
            file = await attachment.to_file()
            view = ReviewView(self.bot, ctx.author.id, attachment.filename, event_id, task_id)
            # 發送到管理員審核頻道
            print("DEBUG: 準備發送圖片到審核頻道...")
            msg = await channel.send(
                content=(
                    f"使用者 <@{ctx.author.id}> 上傳圖片：`{attachment.filename}`\n"
                    f"活動：{event_name} (ID={event_id})\n"
                    f"任務：{task_name} (ID={task_id})\n"
                    "等待審核..."
                ),
                file=file,
                view=view
            )
            print("DEBUG: 審核訊息已成功發送。 msg=", msg)

        except Exception as e:
            await ctx.send("圖片上傳到審核頻道時發生錯誤，請聯絡管理員。")
            print(f"DEBUG: 發送到審核頻道時發生錯誤: {e}")
            return

        # 在私訊頻道中回覆使用者
        await ctx.send(
            f"圖片 `{attachment.filename}` 已收到。\n"
            f"活動：{event_name}, 任務：{task_name}\n"
            "等待管理員審核。"
        )
        print("DEBUG: 已在私訊中通知使用者圖片已收到。")

async def setup(bot: commands.Bot):
    await bot.add_cog(ImageReviewCog(bot))
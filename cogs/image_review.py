import discord
import os
from discord.ext import commands
from discord.ui import View, Select
from dotenv import load_dotenv

load_dotenv()
TARGET_CHANNEL_ID = int(os.getenv("TARGET_CHANNEL_ID"))

class ReviewSelect(discord.ui.Select):
    def __init__(self, bot: commands.Bot, user_id: int, filename: str, event_code: str):
        options = [
            discord.SelectOption(label="累計1點（通過）", value="1"),
            discord.SelectOption(label="累計2點（通過）", value="2"),
            discord.SelectOption(label="累計3點（通過）", value="3"),
            discord.SelectOption(label="拒絕", value="reject")
        ]
        super().__init__(placeholder="審核結果", min_values=1, max_values=1, options=options)
        self.bot = bot
        self.user_id = user_id
        self.filename = filename
        self.event_code = event_code

    async def callback(self, interaction: discord.Interaction):
        selected_value = self.values[0]
        data = self.bot.user_images.get(self.user_id, [])
        for img in data:
            if img["filename"] == self.filename:
                user = self.bot.get_user(self.user_id) or await self.bot.fetch_user(self.user_id)
                if not user:
                    return

                event_name = "N/A"
                if self.event_code in self.bot.events:
                    event_name = self.bot.events[self.event_code]["event_name"]

                if selected_value == "reject":
                    img["status"] = "rejected"
                    await user.send(f"你的圖片 `{self.filename}` 審核失敗，請重新上傳。\n活動：{event_name}")
                    await interaction.response.send_message(
                        f"圖片 `{self.filename}` 審核失敗，請重新上傳。", ephemeral=True
                    )
                    await self.disable_review(interaction, f"請重新上傳(活動:{event_name})")
                    return
                else:
                    points = int(selected_value)
                    img["status"] = "approved"
                    try:
                        result_msg = self.bot.add_points_internal(self.user_id, points)
                    except AttributeError:
                        result_msg = "bot 未定義 add_points_internal"
                    await user.send(
                        f"你的圖片 `{self.filename}` 審核通過+{points}點。\n活動：{event_name}"
                    )
                    await interaction.response.send_message(
                        f"圖片 `{self.filename}` 審核通過 +{points}點。\n({result_msg})",
                        ephemeral=True
                    )
                    await self.disable_review(
                        interaction,
                        f"已通過(+{points}點), 活動:{event_name}"
                    )
                    return

    async def disable_review(self, interaction: discord.Interaction, status: str):
        for c in self.view.children:
            c.disabled = True
        await interaction.message.edit(content=f"圖片 `{self.filename}` 審核狀態：{status}", view=self.view)


class ReviewView(View):
    def __init__(self, bot: commands.Bot, user_id: int, filename: str, event_code: str):
        super().__init__(timeout=None)
        self.bot = bot
        self.user_id = user_id
        self.filename = filename
        self.event_code = event_code
        self.add_item(ReviewSelect(bot, user_id, filename, event_code))

class ImageReviewCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="上傳圖片")
    async def upload_image(self, ctx: commands.Context, event_code: str = None):
        if not isinstance(ctx.channel, discord.DMChannel):
            await ctx.send("請在私訊使用此指令。")
            return

        if not event_code:
            await ctx.send("請輸入活動編號，如: !RA 上傳圖片 AB12")
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

        if not ctx.message.attachments:
            await ctx.send("請附加圖片後再試一次。")
            return

        attachment = ctx.message.attachments[0]
        if not attachment.filename.lower().endswith((".png", ".jpg", ".jpeg", ".gif")):
            await ctx.send("限圖片檔 (.png/.jpg/.jpeg/.gif)")
            return

        event_name = self.bot.events[event_code]["event_name"]
        image_data = {
            "filename": attachment.filename,
            "user_id": ctx.author.id,
            "username": ctx.author.name,
            "status": "pending",
            "event_code": event_code
        }
        self.bot.user_images.setdefault(ctx.author.id, []).append(image_data)

        channel = self.bot.get_channel(TARGET_CHANNEL_ID)
        if not channel:
            await ctx.send("找不到審核頻道，請檢查 TARGET_CHANNEL_ID。")
            return

        try:
            file = await attachment.to_file()
            view = ReviewView(self.bot, ctx.author.id, attachment.filename, event_code)
            msg = await channel.send(
                content=(
                    f"使用者 <@{ctx.author.id}> 上傳圖片檔案：`{attachment.filename}`\n"
                    f"活動：{event_name} (編號={event_code})\n"
                    "等待審核..."
                ),
                file=file,
                view=view
            )
        except Exception:
            await ctx.send("上傳至審核頻道失敗，請通知管理員排除。")
            return

        await ctx.send(
            f"圖片 `{attachment.filename}` 已收到。\n"
            f"活動：{event_name} (編號:{event_code})\n"
            "等待管理員審核..."
        )

async def setup(bot: commands.Bot):
    await bot.add_cog(ImageReviewCog(bot))
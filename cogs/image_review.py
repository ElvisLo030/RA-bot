import discord
from discord.ext import commands
from discord.ui import Button, View
from typing import List, Tuple

TARGET_CHANNEL_ID = 1328558488355340348

class ReviewView(View):
    def __init__(self, bot: commands.Bot, user_id: int, filename: str):
        super().__init__()
        self.bot = bot
        self.user_id = user_id
        self.filename = filename
        self.message = None

    @discord.ui.button(label="通過", style=discord.ButtonStyle.green)
    async def approve(self, interaction: discord.Interaction, button: Button):
        data = self.bot.user_images.get(self.user_id, [])
        for fname, user in data:
            if fname == self.filename:
                await user.send(f"你的圖片 {self.filename} 已通過審核！")
                break
        await interaction.response.send_message(f"圖片 {self.filename} 審核通過！")
        await self.update_status(interaction, "已通過")

    @discord.ui.button(label="拒絕", style=discord.ButtonStyle.red)
    async def reject(self, interaction: discord.Interaction, button: Button):
        data = self.bot.user_images.get(self.user_id, [])
        for fname, user in data:
            if fname == self.filename:
                await user.send(f"你的圖片 {self.filename} 已被拒絕。")
                break
        await interaction.response.send_message(f"圖片 {self.filename} 已拒絕！")
        await self.update_status(interaction, "已拒絕")

    async def update_status(self, interaction: discord.Interaction, status: str):
        if self.message:
            for child in self.children:
                child.disabled = True
            await self.message.edit(content=f"圖片 {self.filename} 審核狀態：{status}", view=self)

class ImageReviewCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="上傳圖片")
    async def upload_image(self, ctx: commands.Context):
        if not isinstance(ctx.channel, discord.DMChannel):
            await ctx.send("請使用機器人私訊上傳圖片。")
            return
        if not ctx.message.attachments:
            await ctx.send("請附加圖片後再試一次。")
            return
        attachment = ctx.message.attachments[0]
        if not attachment.filename.lower().endswith((".png", ".jpg", ".jpeg", ".gif")):
            await ctx.send("限圖片檔 (.png、.jpg、.jpeg、.gif)")
            return

        bucket = self.bot.user_images.setdefault(ctx.author.id, [])
        bucket.append((attachment.filename, ctx.author))

        channel = self.bot.get_channel(TARGET_CHANNEL_ID)
        if channel:
            file = await attachment.to_file()
            view = ReviewView(self.bot, ctx.author.id, attachment.filename)
            msg = await channel.send(
                f"使用者 {ctx.author.mention} 傳送了圖片：{attachment.filename}\n等待審核...",
                file=file,
                view=view
            )
            view.message = msg
        await ctx.send(f"圖片 {attachment.filename} 已收到，等待管理員審核...")

async def setup(bot: commands.Bot):
    await bot.add_cog(ImageReviewCog(bot))
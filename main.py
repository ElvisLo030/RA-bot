import discord
from discord.ext import commands
from discord.ui import Button, View, Select, Modal, TextInput
import os

from config import bot, user_images, user_cards, TOKEN
from cogs.card_binding import setup as setup_card_binding, CardBindingCog

# 確保 cogs 被正確加載
async def load_cogs():
    await setup_card_binding(bot, user_cards)

# 定義 Modal 用於綁定和修改卡號
class CardBindModal(Modal):
    def __init__(self, cog: CardBindingCog):
        super().__init__(title="綁定卡號")
        self.cog = cog

        self.card_number = TextInput(
            label="請輸入你的卡號",
            placeholder="8 位英數字，至少包含 1 英文字母與 1 數字",
            max_length=8
        )
        self.add_item(self.card_number)

    async def on_submit(self, interaction: discord.Interaction):
        success, message = await self.cog.bind_card(interaction.user, self.card_number.value)
        await interaction.response.send_message(message, ephemeral=True)

class CardModifyModal(Modal):
    def __init__(self, cog: CardBindingCog):
        super().__init__(title="修改卡號")
        self.cog = cog

        self.new_card_number = TextInput(
            label="請輸入新的卡號",
            placeholder="8 位英數字，至少包含 1 英文字母與 1 數字",
            max_length=8
        )
        self.add_item(self.new_card_number)

    async def on_submit(self, interaction: discord.Interaction):
        success, message = await self.cog.modify_card(interaction.user, self.new_card_number.value)
        await interaction.response.send_message(message, ephemeral=True)

# 定義選單
class CardSettingSelect(Select):
    def __init__(self, cog: CardBindingCog):
        self.cog = cog
        options = [
            discord.SelectOption(label="綁定卡號", description="綁定新的卡號", value="bind"),
            discord.SelectOption(label="修改卡號", description="修改已綁定的卡號", value="modify"),
            discord.SelectOption(label="查詢卡號", description="查看目前已綁定的卡號", value="query"),
            discord.SelectOption(label="刪除卡號", description="刪除已綁定的卡號", value="delete"),
        ]
        super().__init__(placeholder="選擇卡片功能", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        choice = self.values[0]
        if choice == "bind":
            modal = CardBindModal(self.cog)
            await interaction.response.send_modal(modal)
        elif choice == "modify":
            modal = CardModifyModal(self.cog)
            await interaction.response.send_modal(modal)
        elif choice == "query":
            success, message = await self.cog.query_card(interaction.user)
            if not success:
                await interaction.response.send_message(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)
        elif choice == "delete":
            success, message = await self.cog.delete_card(interaction.user)
            await interaction.response.send_message(message, ephemeral=True)

# 定義 View
class CardSettingView(View):
    def __init__(self, cog: CardBindingCog):
        super().__init__()
        self.add_item(CardSettingSelect(cog))

# 定義卡片設定指令
@bot.command()
async def 卡片設定(ctx: commands.Context):
    if not isinstance(ctx.channel, discord.DMChannel):
        await ctx.send("請使用私訊再使用此指令。")
        return

    # 獲取 Cog 實例
    cog = bot.get_cog("CardBindingCog")
    if not cog:
        await ctx.send("卡片綁定功能未啟用。")
        return

    view = CardSettingView(cog)
    await ctx.send("請選擇卡片功能：", view=view)

class ReviewView(View):
    def __init__(self, user_id, filename):
        super().__init__()
        self.user_id = user_id
        self.filename = filename
        self.message = None

    @discord.ui.button(label="通過", style=discord.ButtonStyle.green)
    async def approve(self, interaction: discord.Interaction, button: Button):
        user_info = user_images.get(self.user_id)
        if user_info:
            await interaction.response.send_message(f"圖片 {self.filename} 審查通過！", ephemeral=True)
            for filename, user in user_info:
                if filename == self.filename:
                    await user.send(f"你的圖片 {self.filename} 已通過審查！")
                    break
            await self.update_message(interaction, "審查通過")
        else:
            await interaction.response.send_message("找不到該使用者的圖片。", ephemeral=True)

    @discord.ui.button(label="拒絕", style=discord.ButtonStyle.red)
    async def reject(self, interaction: discord.Interaction, button: Button):
        user_info = user_images.get(self.user_id)
        if user_info:
            await interaction.response.send_message(f"圖片 {self.filename} 已拒絕！", ephemeral=True)
            for filename, user in user_info:
                if filename == self.filename:
                    await user.send(f"你的圖片 {self.filename} 已被拒絕。")
                    break
            await self.update_message(interaction, "審查拒絕")
        else:
            await interaction.response.send_message("找不到該使用者的圖片。", ephemeral=True)

    async def update_message(self, interaction, status):
        if self.message:
            for item in self.children:
                item.disabled = True
            await self.message.edit(content=f"圖片 {self.filename} 已完成審查：{status}", view=self)
        else:
            await interaction.response.send_message("無法更新訊息。", ephemeral=True)

class FileSelect(Select):
    def __init__(self, username):
        options = []
        for filename, _ in user_images.get(username, []):
            options.append(discord.SelectOption(label=filename, value=filename))
        super().__init__(placeholder="選擇要審查的檔案...", min_values=1, max_values=1, options=options)
        self.username = username

    async def callback(self, interaction: discord.Interaction):
        filename = self.values[0]
        view = ReviewView(self.username, filename)
        await interaction.response.send_message(f"請選擇對圖片 {filename} 的審查結果：", view=view, ephemeral=True)

class FileSelectView(View):
    def __init__(self, username):
        super().__init__()
        self.username = username
        self.add_item(FileSelect(username))

@bot.command()
async def 上傳圖片(ctx):
    if ctx.channel.name == "上傳區":
        if ctx.message.attachments:
            attachment = ctx.message.attachments[0]
            if attachment.content_type and attachment.content_type.startswith("image/"):
                admin_channel = discord.utils.get(ctx.guild.text_channels, name="後台審查")
                if admin_channel:
                    view = ReviewView(ctx.author.id, attachment.filename)
                    msg = await admin_channel.send(
                        f"收到圖片：{attachment.filename}\n來自 {ctx.author.mention}",
                        file=await attachment.to_file(),
                        view=view
                    )
                    view.message = msg
                    if ctx.author.id not in user_images:
                        user_images[ctx.author.id] = []
                    user_images[ctx.author.id].append((attachment.filename, ctx.author))
                await ctx.send(f"圖片已收到，等待審查：{attachment.filename}")
            else:
                await ctx.send("只接受圖片格式！")
        else:
            await ctx.send("請附上圖片檔案！")
    else:
        await ctx.send("請在上傳區頻道上傳圖片！")

@bot.command()
async def 審查(ctx, username: str):
    if ctx.channel.name == "後台審查":
        if username in user_images:
            view = FileSelectView(username)
            await ctx.send("請選擇要審查的檔案：", view=view)
        else:
            await ctx.send("找不到該使用者的圖片。")

async def main():
    await load_cogs()
    await bot.start(TOKEN)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
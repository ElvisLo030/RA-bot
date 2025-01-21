import discord
from discord.ext import commands
from discord.ui import Select, View, Modal, TextInput
from typing import Dict

from cogs.card_binding import CardBindingCog

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

class SelectionMenuSelect(discord.ui.Select):
    def __init__(self, cog: CardBindingCog):
        self.cog = cog
        options = [
            discord.SelectOption(label="上傳圖片", description="上傳圖片進行審查", value="upload_pic"),
            discord.SelectOption(label="綁定卡號", description="綁定新的卡號", value="bind"),
            discord.SelectOption(label="修改卡號", description="修改已綁定的卡號", value="modify"),
            discord.SelectOption(label="查詢卡號", description="查看目前已綁定的卡號", value="query"),
            discord.SelectOption(label="刪除卡號", description="刪除已綁定的卡號", value="delete"),
            discord.SelectOption(label="投票功能（beta）", description="簡易投票系統", value="vote"),
        ]
        super().__init__(placeholder="選擇功能", min_values=1, max_values=1, options=options)

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
            await interaction.response.send_message(message, ephemeral=True)
        elif choice == "delete":
            success, message = await self.cog.delete_card(interaction.user)
            await interaction.response.send_message(message, ephemeral=True)
        elif choice == "upload_pic":
            await interaction.response.send_message("請在私訊輸入 !RA 上傳圖片 並附加圖片檔案。", ephemeral=True)
        elif choice == "vote":
            await interaction.response.send_message("請使用 !RA 設定投票 並附加投票主題。", ephemeral=True)

class SelectionMenuView(View):
    def __init__(self, cog: CardBindingCog):
        super().__init__()
        self.add_item(SelectionMenuSelect(cog))

class SelectionMenuCog(commands.Cog):
    def __init__(self, bot: commands.Bot, user_cards: Dict[int, str]):
        self.bot = bot
        self.user_cards = user_cards

    @commands.command(name="功能選單")
    async def feature_menu(self, ctx: commands.Context):
        if not isinstance(ctx.channel, discord.DMChannel):
            await ctx.send("請使用私訊再使用此指令。")
            return

        cog = self.bot.get_cog("CardBindingCog")
        if not cog:
            await ctx.send("卡片綁定功能未啟用。")
            return

        view = SelectionMenuView(cog)
        await ctx.send("請選擇所需功能：", view=view)

async def setup(bot: commands.Bot):
    user_cards = bot.user_cards  # 確保在 bot 中存在 user_cards
    await bot.add_cog(SelectionMenuCog(bot, user_cards))
import discord
from discord.ext import commands
from discord.ui import Select, View, Modal, TextInput
from cogs.card_binding import CardBindingCog
from main import not_blocked
from main import save_data

class CardBindModal(Modal):
    def __init__(self, cog: CardBindingCog):
        super().__init__(title="綁定卡號")
        self.cog = cog
        self.card_number = TextInput(
            label="卡號(RGPXXXXX)",
            placeholder="請正確輸入卡號，若輸入錯誤請洽詢店員",
            max_length=8
        )
        self.add_item(self.card_number)
        save_data()

    async def on_submit(self, interaction: discord.Interaction):
        success, msg = await self.cog.bind_card(interaction.user, self.card_number.value)
        await interaction.response.send_message(msg, ephemeral=True)
        if success:
            await self.cog.update_menu(interaction.user)

class JoinEventModal(Modal):
    def __init__(self, cog: CardBindingCog):
        super().__init__(title="參加活動")
        self.cog = cog
        self.event_code = TextInput(
            label="活動編號",
            placeholder="RGE000",
            max_length=6
        )
        self.add_item(self.event_code)

    async def on_submit(self, interaction: discord.Interaction):
        success, msg = await self.cog.join_event(interaction.user, self.event_code.value.strip())
        await interaction.response.send_message(msg, ephemeral=True)
        if success:
            await self.cog.update_menu(interaction.user)

class SelectionMenuSelect(discord.ui.Select):
    def __init__(self, cog: CardBindingCog, user: discord.User):
        self.cog = cog
        self.user = user
        self.bot = cog.bot

        user_data = self.bot.gamers.get(user.id)
        has_card = (user_data and user_data.get("gamer_card_number"))

        options = []
        if not has_card:
            options.append(discord.SelectOption(label="綁定卡號", description="請輸入卡號綁定才可使用此機器人", value="bind_card"))
        else:
            options.append(discord.SelectOption(label="參加活動", description="請先查詢活動編號再使用此功能", value="join_event"))
            options.append(discord.SelectOption(label="查詢卡號", description="此指令僅提供查詢，若需修改請洽詢店員", value="query_card"))
            options.append(discord.SelectOption(label="查詢點數", description="查詢累計之點數", value="query_points"))

            joined = user_data.get("joined_events", [])
            if joined:
                options.append(discord.SelectOption(label="上傳圖片", description="請點選查詢指令", value="upload_pic"))

        super().__init__(placeholder="選擇功能", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        choice = self.values[0]
        if choice == "bind_card":
            modal = CardBindModal(self.cog)
            await interaction.response.send_modal(modal)
        elif choice == "join_event":
            modal = JoinEventModal(self.cog)
            await interaction.response.send_modal(modal)
        elif choice == "query_card":
            success, msg = await self.cog.query_card(interaction.user)
            await interaction.response.send_message(msg, ephemeral=True)
        elif choice == "query_points":
            user_data = self.bot.gamers.get(self.user.id)
            if not user_data:
                await interaction.response.send_message("你尚未綁定卡片或加入活動。", ephemeral=True)
                return
            points = sum(user_data.get("history_event_pts_list", []))
            await interaction.response.send_message(f"你目前點數：{points}", ephemeral=True)
        elif choice == "upload_pic":
            await interaction.response.send_message(
                "請在私訊輸入 `RA 上傳圖片 “活動編號”` 並附加圖片。",
                ephemeral=True
            )

class SelectionMenuView(View):
    def __init__(self, cog: CardBindingCog, user: discord.User):
        super().__init__(timeout=None)
        self.add_item(SelectionMenuSelect(cog, user))

class SelectionMenuCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.check(not_blocked)
    @commands.command(name="功能選單")
    async def feature_menu(self, ctx: commands.Context):
        if not isinstance(ctx.channel, discord.DMChannel):
            await ctx.send("請在私訊中使用此指令。")
            return

        cog = self.bot.get_cog("CardBindingCog")
        if not cog:
            await ctx.send("卡片綁定功能未啟用")
            return

        view = SelectionMenuView(cog, ctx.author)
        await ctx.send("請選擇功能：", view=view)

async def setup(bot: commands.Bot):
    await bot.add_cog(SelectionMenuCog(bot))
    print("SelectionMenuCog 已成功加載。")
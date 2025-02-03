# cogs/selection_menu.py

import discord
from discord.ext import commands
from discord.ui import Select, View, Modal, TextInput
from typing import Dict

from cogs.card_binding import CardBindingCog

class JoinTaskModal(Modal):
    """
    讓使用者輸入任務 ID 以加入任務
    """
    def __init__(self, cog: CardBindingCog):
        super().__init__(title="參加任務")
        self.cog = cog
        self.task_id = TextInput(
            label="請輸入想參加的任務ID",
            placeholder="例如 1, 2, 3 ...",
            max_length=10
        )
        self.add_item(self.task_id)

    async def on_submit(self, interaction: discord.Interaction):
        # 從 cog.bot.tasks 取得任務資料
        bot_tasks = self.cog.bot.tasks

        try:
            t_id = int(self.task_id.value)
        except ValueError:
            await interaction.response.send_message("任務 ID 必須是數字", ephemeral=True)
            return

        if t_id not in bot_tasks:
            await interaction.response.send_message(f"任務 {t_id} 不存在。", ephemeral=True)
            return

        # 直接把 user.id 加進該任務 gamer_list
        if interaction.user.id in bot_tasks[t_id]["gamer_list"]:
            await interaction.response.send_message(f"你已在任務 {t_id} 名單中。", ephemeral=True)
            return

        bot_tasks[t_id]["gamer_list"].append(interaction.user.id)
        await interaction.response.send_message(f"成功加入任務 {t_id}！", ephemeral=True)

        # 若要更新選單，重新呼叫 update_menu
        await self.cog.update_menu(interaction.user)


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
        if success:
            await self.cog.update_menu(interaction.user)


class JoinEventModal(Modal):
    def __init__(self, cog: CardBindingCog):
        super().__init__(title="參加活動")
        self.cog = cog
        self.event_id = TextInput(
            label="請輸入活動 ID",
            placeholder="活動 ID",
            max_length=10
        )
        self.add_item(self.event_id)

    async def on_submit(self, interaction: discord.Interaction):
        success, message = await self.cog.join_event(interaction.user, int(self.event_id.value))
        await interaction.response.send_message(message, ephemeral=True)
        if success:
            await self.cog.update_menu(interaction.user)


class SelectionMenuSelect(discord.ui.Select):
    def __init__(self, cog: CardBindingCog, user: discord.User):
        self.cog = cog
        self.user = user
        self.bot = cog.bot

        # 檢查是否已綁卡
        from main import gamers  # 或可改成 self.bot.gamers，看你實際結構
        has_card = (
            self.user.id in gamers and
            gamers[self.user.id].get("gamer_card_number") is not None
        )

        # 檢查是否已參加任務
        joined_any_task = any(self.user.id in t["gamer_list"] for t in self.bot.tasks.values())

        options = []
        if not has_card:
            # 如果沒綁卡則只顯示 "綁定卡號"
            options.append(discord.SelectOption(label="綁定卡號", description="綁定新的卡號", value="bind_card"))
        else:
            # 若已綁卡，顯示參加活動、參加任務、查卡、查點數
            options.append(discord.SelectOption(label="參加活動", description="參加活動", value="join_event"))
            options.append(discord.SelectOption(label="參加任務", description="輸入任務ID來參加", value="join_task"))
            options.append(discord.SelectOption(label="查詢卡號", description="查看目前已綁定的卡號", value="query_card"))
            options.append(discord.SelectOption(label="查詢點數", description="查詢目前持有的點數", value="query_points"))

            # 僅當玩家已參加任務才可上傳圖片
            if joined_any_task:
                options.append(discord.SelectOption(label="上傳圖片", description="上傳圖片進行審查", value="upload_pic"))

        super().__init__(placeholder="選擇功能", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        choice = self.values[0]
        if choice == "bind_card":
            modal = CardBindModal(self.cog)
            await interaction.response.send_modal(modal)

        elif choice == "join_event":
            modal = JoinEventModal(self.cog)
            await interaction.response.send_modal(modal)

        elif choice == "join_task":
            modal = JoinTaskModal(self.cog)
            await interaction.response.send_modal(modal)

        elif choice == "query_card":
            success, message = await self.cog.query_card(interaction.user)
            await interaction.response.send_message(message, ephemeral=True)

        elif choice == "query_points":
            from main import gamers
            if interaction.user.id not in gamers:
                await interaction.response.send_message("你尚未成為玩家，請先綁卡或參加活動。", ephemeral=True)
                return
            points = sum(gamers[interaction.user.id]["history_event_pts_list"])
            await interaction.response.send_message(f"你目前持有的點數：{points}", ephemeral=True)

        elif choice == "upload_pic":
            # 提示用戶使用 !RA 上傳圖片 <task_id> 並附檔
            await interaction.response.send_message("請在私訊輸入 `!RA 上傳圖片 <task_id>` 並附上圖片檔案。", ephemeral=True)


class SelectionMenuView(View):
    def __init__(self, cog: CardBindingCog, user: discord.User):
        super().__init__()
        self.add_item(SelectionMenuSelect(cog, user))


class SelectionMenuCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="功能選單")
    async def feature_menu(self, ctx: commands.Context):
        if not isinstance(ctx.channel, discord.DMChannel):
            await ctx.send("請使用私訊再使用此指令。")
            return

        cog = self.bot.get_cog("CardBindingCog")
        if not cog:
            await ctx.send("卡片綁定功能未啟用。")
            return

        view = SelectionMenuView(cog, ctx.author)
        await ctx.send("請選擇功能：", view=view)

async def setup(bot: commands.Bot):
    await bot.add_cog(SelectionMenuCog(bot))
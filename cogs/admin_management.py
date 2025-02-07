import discord
from discord.ext import commands
from discord.ui import View, Select, Modal, TextInput
import re
import os
from dotenv import load_dotenv
from main import save_data

load_dotenv()
ADMIN_CHANNEL_ID = int(os.getenv("ADMIN_CHANNEL_ID"))

def is_admin_channel(ctx):
    return ctx.channel.id == ADMIN_CHANNEL_ID

class CreateEventModal(Modal):
    def __init__(self, bot: commands.Bot):
        super().__init__(title="創建活動")
        self.bot = bot

        self.event_code = TextInput(
            label="活動編號(RAEXXX)",
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
        code = self.event_code.value.strip()
        pattern = r'^RAE(?=.*[0-9])[A-Za-z0-9]{3}$'
        print(f"DEBUG: validate_event_code called with event_code={code}")
        if not re.match(pattern, code):
            await interaction.response.send_message(
                "活動編號格式錯誤。",
                ephemeral=True
            )
            return

        if code in self.bot.events:
            await interaction.response.send_message("該活動編號已存在，請更換新的編號。", ephemeral=True)
            return

        self.bot.events[code] = {
            "event_code": code,
            "event_name": self.event_name.value,
            "event_description": self.event_desc.value,
            "event_start_date": self.start_date.value,
            "event_end_date": self.end_date.value,
            "gamer_list": []
        }
        save_data()
        await interaction.response.send_message(
            f"活動 {self.event_name.value} 已建立，編號為 = {code}",
            ephemeral=True
        )

class ModifyCardModal(Modal):
    def __init__(self, bot: commands.Bot):
        super().__init__(title="修改玩家卡號")
        self.bot = bot

        self.user_id = TextInput(label="玩家Dicscord ID", placeholder="請詢問更改者DC ID編號", max_length=20)
        self.new_card = TextInput(label="新卡號(RGPXXXXX)", placeholder="RGPXXXXX", max_length=8)

        self.add_item(self.user_id)
        self.add_item(self.new_card)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            user_id_int = int(self.user_id.value)
        except ValueError:
            await interaction.response.send_message("玩家ID必須是數字", ephemeral=True)
            return

        card_pattern = re.compile(r'^(?=.*[0-9])(?=.*[A-Za-z])[A-Za-z0-9]{8}$')
        if not card_pattern.match(self.new_card.value):
            await interaction.response.send_message(
                "卡號格式錯誤，請重新數入",
                ephemeral=True
            )
            return

        if user_id_int not in self.bot.gamers:
            # 初始化
            self.bot.gamers[user_id_int] = {
                "gamer_id": user_id_int,
                "gamer_card_number": self.new_card.value,
                "gamer_is_blocked": False,
                "gamer_bind_gamepass": None,
                "joined_events": [],
                "history_event_list": [],
                "history_event_pts_list": []
            }
        else:
            self.bot.gamers[user_id_int]["gamer_card_number"] = self.new_card.value

        save_data()
        await interaction.response.send_message(
            f"玩家 {user_id_int} 的卡號已更新為 {self.new_card.value}", 
            ephemeral=True
        )

class QueryCardByUserModal(Modal):
    def __init__(self, bot: commands.Bot):
        super().__init__(title="查詢玩家卡號(DC ID)")
        self.bot = bot
        self.user_id = TextInput(label="玩家DC ID", placeholder="請正確輸入", max_length=20)
        self.add_item(self.user_id)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            user_id_int = int(self.user_id.value)
        except ValueError:
            await interaction.response.send_message("玩家DC ID必須是20碼數字", ephemeral=True)
            return

        if user_id_int not in self.bot.gamers:
            await interaction.response.send_message("該玩家不存在或尚未綁定卡號", ephemeral=True)
            return

        card = self.bot.gamers[user_id_int].get("gamer_card_number")
        if card:
            await interaction.response.send_message(
                f"玩家 {user_id_int} 的卡號為：{card}",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"玩家 {user_id_int} 尚未綁定卡號",
                ephemeral=True
            )

class QueryUserByCardModal(Modal):
    def __init__(self, bot: commands.Bot):
        super().__init__(title="查詢玩家ID(競音卡號)")
        self.bot = bot
        self.card_number = TextInput(
            label="卡號",
            placeholder="RGPXXXXX",
            max_length=8
        )
        self.add_item(self.card_number)

    async def on_submit(self, interaction: discord.Interaction):
        card = self.card_number.value.strip()
        found_user = None
        for g_id, data in self.bot.gamers.items():
            if data.get("gamer_card_number") == card:
                found_user = g_id
                break

        if found_user is None:
            await interaction.response.send_message("找不到此卡號的玩家", ephemeral=True)
        else:
            await interaction.response.send_message(
                f"卡號 {card} 屬於玩家 {found_user}",
                ephemeral=True
            )

class AddPointsModal(Modal):
    def __init__(self, bot: commands.Bot):
        super().__init__(title="手動給予點數")
        self.bot = bot

        self.user_id = TextInput(label="玩家DC ID", placeholder="數字", max_length=20)
        self.points = TextInput(label="點數", placeholder="要加多少點數", max_length=10)
        self.add_item(self.user_id)
        self.add_item(self.points)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            uid = int(self.user_id.value)
            pts = int(self.points.value)
        except ValueError:
            await interaction.response.send_message("玩家ID和點數都必須是數字", ephemeral=True)
            return

        if not hasattr(self.bot, "add_points_internal"):
            await interaction.response.send_message("bot 未定義 add_points_internal，無法增加點數", ephemeral=True)
            return

        msg = self.bot.add_points_internal(uid, pts)
        await interaction.response.send_message(msg, ephemeral=True)

class QueryAllGamersModal(Modal):
    def __init__(self, bot: commands.Bot):
        super().__init__(title="查詢所有玩家(可利用關鍵字查詢比較快)")
        self.bot = bot

        self.keyword = TextInput(
            label="關鍵字(盡量不要空白)",
            placeholder="請輸入關鍵字, 空白則會將全部的玩家列出（建議不要使用）",
            required=False
        )
        self.add_item(self.keyword)

    async def on_submit(self, interaction: discord.Interaction):
        kw = self.keyword.value.strip().lower()
        results = []
        for g_id, data in self.bot.gamers.items():
            text_to_check = (f"{data.get('gamer_card_number','')}").lower()
            if kw == "" or kw in text_to_check:
                results.append((g_id, data))

        if not results:
            await interaction.response.send_message("找不到任何符合的玩家", ephemeral=True)
            return

        msg_lines = []
        for g_id, info in results:
            msg_lines.append(
                f"ID={g_id}, 卡號={info['gamer_card_number']}, 黑名單={info['gamer_is_blocked']}"
            )
        final_msg = "\n".join(msg_lines)
        await interaction.response.send_message(final_msg, ephemeral=True)

class BlockUnblockModal(Modal):
    def __init__(self, bot: commands.Bot):
        super().__init__(title="封鎖/解鎖 玩家")
        self.bot = bot

        self.user_id = TextInput(label="玩家ID", placeholder="數字", max_length=20)
        self.block_or_unblock = TextInput(label="輸入 block / unblock", placeholder="block 或 unblock")

        self.add_item(self.user_id)
        self.add_item(self.block_or_unblock)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            user_id_int = int(self.user_id.value)
        except ValueError:
            await interaction.response.send_message("玩家ID必須是數字", ephemeral=True)
            return

        action = self.block_or_unblock.value.strip().lower()
        if user_id_int not in self.bot.gamers:
            await interaction.response.send_message("該玩家不存在", ephemeral=True)
            return

        if action == "block":
            self.bot.gamers[user_id_int]["gamer_is_blocked"] = True
            await interaction.response.send_message(f"玩家 {user_id_int} 已被封鎖", ephemeral=True)
        elif action == "unblock":
            self.bot.gamers[user_id_int]["gamer_is_blocked"] = False
            await interaction.response.send_message(f"玩家 {user_id_int} 已解除封鎖", ephemeral=True)
        else:
            await interaction.response.send_message("請輸入 block 或 unblock", ephemeral=True)

class AdminManagementSelect(Select):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        options = [
            discord.SelectOption(label="建立活動", value="create_event"),
            discord.SelectOption(label="修改玩家卡號", description="請詢問使用者之DC ID編號，若無法查詢可使用查詢玩家ID功能", value="modify_card_modal"),
            discord.SelectOption(label="手動給予點數", description="請詢問使用者之DC ID編號，若無法查詢可使用查詢玩家ID功能", value="add_points_modal"),
            discord.SelectOption(label="查詢玩家卡號", description="請詢問使用者之DC ID編號，若無法查詢可使用查詢玩家ID功能", value="query_card_by_user"),
            discord.SelectOption(label="查詢玩家ID(卡號)", description="請詢問使用者卡片編號，若無法查詢可使用查詢玩家卡號功能", value="query_user_by_card"),
            discord.SelectOption(label="查詢玩家資料", description="請盡量以關鍵字查詢，若無輸入關鍵字會抓取所有資料", value="query_all_gamers"),
            discord.SelectOption(label="封鎖/解除封鎖玩家", value="block_unblock"),
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
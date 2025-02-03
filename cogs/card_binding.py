# cogs/card_binding.py

import discord
from discord.ext import commands
from typing import Dict
import re

# 這裡動態 import main.py 內的資料或函式
# 避免循環 import，callback 時再 import 亦可
from main import gamers

class CardBindingCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # 不再需要 user_cards
        self.card_pattern = re.compile(r'^(?=.*[0-9])(?=.*[A-Za-z])[A-Za-z0-9]{8}$')

    async def bind_card(self, user: discord.User, card_number: str):
        """
        綁定卡號 -> 存到 gamers[user_id]["gamer_card_number"].
        若該 user_id 在 gamers 裡尚無資料，就先初始化
        """
        if not self.card_pattern.match(card_number):
            return False, "卡號格式錯誤！需包含 8 位英數字，且至少包含 1 英文字母與 1 數字。"

        # 檢查該 user 是否已存在 gamers
        if user.id not in gamers:
            # 初始化
            gamers[user.id] = {
                "gamer_id": user.id,
                "gamer_dcid": str(user),
                "gamer_card_number": card_number,
                "gamer_is_blocked": False,
                "gamer_bind_gamepass": None,
                "history_event_list": [],
                "history_event_pts_list": [],
                "history_task_list": []
            }
        else:
            # 若已存在就只更新 card_number
            gamers[user.id]["gamer_card_number"] = card_number

        return True, f"你的卡號 {card_number} 綁定成功！"

    async def query_card(self, user: discord.User):
        """
        查詢卡號 -> 檢查 gamers[user_id]["gamer_card_number"]
        """
        if user.id not in gamers:
            return False, "你尚未綁定卡號。"
        card = gamers[user.id].get("gamer_card_number", None)
        if card:
            return True, f"你的卡號是：{card}"
        else:
            return False, "你尚未綁定卡號。"

    async def join_event(self, user: discord.User, event_id: int):
        """
        參加活動時，也要檢查 bot.events。若該 user 不存在 gamers，就初始化。
        """
        if user.id not in gamers:
            # 初始化
            gamers[user.id] = {
                "gamer_id": user.id,
                "gamer_dcid": str(user),
                "gamer_card_number": None,
                "gamer_is_blocked": False,
                "gamer_bind_gamepass": None,
                "history_event_list": [],
                "history_event_pts_list": [],
                "history_task_list": []
            }

        if event_id not in self.bot.events:
            return False, "活動不存在。"
        event = self.bot.events[event_id]

        # 加入 event["gamer_list"]
        if user.id not in event["gamer_list"]:
            event["gamer_list"].append(user.id)
            gamers[user.id]["history_event_list"].append(event_id)
            return True, f"你已成功參加活動：{event['event_name']}"
        else:
            return False, "你已經參加過此活動。"

    async def update_menu(self, user: discord.User):
        from cogs.selection_menu import SelectionMenuView
        channel = user.dm_channel
        if not channel:
            channel = await user.create_dm()
        view = SelectionMenuView(self, user)
        await channel.send("請選擇所需功能：", view=view)

    @commands.command(name="卡片設定")
    async def card_setting(self, ctx: commands.Context):
        from cogs.selection_menu import SelectionMenuView
        view = SelectionMenuView(self, ctx.author)
        await ctx.send("請選擇所需功能：", view=view)


async def setup(bot: commands.Bot):
    await bot.add_cog(CardBindingCog(bot))
    print("CardBindingCog 已成功加載。")
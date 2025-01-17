import discord
from discord.ext import commands
from typing import Dict
import re

class CardBindingCog(commands.Cog):
    def __init__(self, bot: commands.Bot, user_cards: Dict[int, str]):
        self.bot = bot
        self.user_cards = user_cards
        self.card_pattern = re.compile(r'^(?=.*[0-9])(?=.*[A-Za-z])[A-Za-z0-9]{8}$')

    async def bind_card(self, user: discord.User, card_number: str):
        if not self.card_pattern.match(card_number):
            return False, "卡號格式錯誤！需包含 8 位英數字，且至少包含 1 英文字母與 1 數字。"
        self.user_cards[user.id] = card_number
        return True, f"你的卡號 {card_number} 綁定成功！"

    async def modify_card(self, user: discord.User, new_card_number: str):
        if not self.card_pattern.match(new_card_number):
            return False, "卡號格式錯誤！需包含 8 位英數字，且至少包含 1 英文字母與 1 數字。"
        if user.id in self.user_cards:
            self.user_cards[user.id] = new_card_number
            return True, f"你的卡號已更新為 {new_card_number}！"
        else:
            return False, "你尚未綁定卡號。"

    async def query_card(self, user: discord.User):
        card = self.user_cards.get(user.id, None)
        if card:
            return True, f"你的卡號是：{card}"
        else:
            return False, "你尚未綁定卡號。"

    async def delete_card(self, user: discord.User):
        if user.id in self.user_cards:
            del self.user_cards[user.id]
            return True, "你的卡號已刪除。"
        else:
            return False, "你尚未綁定卡號。"

async def setup(bot: commands.Bot, user_cards: Dict[int, str]):
    await bot.add_cog(CardBindingCog(bot, user_cards))
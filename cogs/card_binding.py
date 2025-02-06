import discord
from discord.ext import commands
import re

class CardBindingCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.card_pattern = re.compile(r'^RGP(?=.*[0-9])(?=.*[A-Za-z])[A-Za-z0-9]{5}$')

    async def bind_card(self, user: discord.User, card_number: str):
        for existing_user in self.bot.gamers.values():
            if existing_user.get("gamer_card_number") == card_number:
                return False, f"卡號 {card_number} 已被其他使用者綁定。"
            
        print(f"DEBUG: bind_card user={user}, card_number={card_number}")
        if not self.card_pattern.match(card_number):
            return False, "卡號格式錯誤(需為RGPXXXXX)"

        if user.id not in self.bot.gamers:
            print("DEBUG: user not in self.bot.gamers => 建立 gamer")
            self.bot.gamers[user.id] = {
                "gamer_id": user.id,
                "gamer_dcid": str(user),
                "gamer_card_number": card_number,
                "gamer_is_blocked": False,
                "gamer_bind_gamepass": None,
                "joined_events": [],
                "history_event_list": [],
                "history_event_pts_list": []
            }
        else:
            self.bot.gamers[user.id]["gamer_card_number"] = card_number

        return True, f"你的卡號 {card_number} 綁定成功！"

    async def query_card(self, user: discord.User):
        if user.id not in self.bot.gamers:
            return False, "你尚未綁定卡片。"
        card = self.bot.gamers[user.id].get("gamer_card_number")
        if card:
            return True, f"你的卡號是 {card}"
        else:
            return False, "尚未綁定卡片"

    async def join_event(self, user: discord.User, event_code: str):
        print(f"DEBUG: join_event => user={user.id}, event_code={event_code}")
        print(f"DEBUG: bot.events.keys()={self.bot.events.keys()}")
        if event_code not in self.bot.events:
            print("DEBUG: 該活動編號不存在")
            return False, f"活動 {event_code} 不存在"

        if user.id not in self.bot.gamers:
            print("DEBUG: user不在 gamers => 建立")
            self.bot.gamers[user.id] = {
                "gamer_id": user.id,
                "gamer_dcid": str(user),
                "gamer_card_number": None,
                "gamer_is_blocked": False,
                "gamer_bind_gamepass": None,
                "joined_events": [],
                "history_event_list": [],
                "history_event_pts_list": []
            }

        event = self.bot.events[event_code]
        if user.id in event["gamer_list"]:
            return False, f"你已參加過此活動 {event_code}"

        event["gamer_list"].append(user.id)
        self.bot.gamers[user.id].setdefault("joined_events", [])
        self.bot.gamers[user.id]["joined_events"].append(event_code)

        return True, f"你已成功參加活動 {event_code}"

    async def update_menu(self, user: discord.User):
        from cogs.selection_menu import SelectionMenuView
        channel = user.dm_channel
        if not channel:
            channel = await user.create_dm()
        view = SelectionMenuView(self, user)
        await channel.send("請選擇功能：", view=view)

async def setup(bot: commands.Bot):
    await bot.add_cog(CardBindingCog(bot))
    print("CardBindingCog 已成功加載。")
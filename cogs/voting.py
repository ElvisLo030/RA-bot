import discord
from discord.ext import commands
from discord.ui import Select, View

class VotingResultsView(View):
    def __init__(self, votes):
        super().__init__()
        self.add_item(VotingResultsSelect(votes))

class VotingResultsSelect(Select):
    def __init__(self, votes):
        options = [
            discord.SelectOption(label=v["title"], description="查看該次投票結果", value=str(i))
            for i, v in enumerate(votes)
        ]
        super().__init__(placeholder="選擇投票紀錄", min_values=1, max_values=1, options=options)
        self.votes = votes

    async def callback(self, interaction: discord.Interaction):
        index = int(self.values[0])
        vote = self.votes[index]
        await interaction.response.send_message(
            f"投票標題：{vote['title']}\n👍：{vote['up']}\n👎：{vote['down']}",
            ephemeral=True
        )

class VotingCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.bot.votes_history = getattr(bot, "votes_history", [])

    @commands.has_permissions(administrator=True)
    @commands.command(name="設定投票")
    async def custom_vote(self, ctx: commands.Context, title: str = "測試", up_emoji: str = "👍", down_emoji: str = "👎"):
        message = await ctx.send(f"投票主題：{title}\n請使用表情符號進行投票！")
        await message.add_reaction(up_emoji)
        await message.add_reaction(down_emoji)
        # 紀錄投票
        self.bot.votes_history.append({"title": title, "message_id": message.id, "up": 0, "down": 0})

    @commands.command(name="投票紀錄")
    async def vote_history(self, ctx: commands.Context):
        if not self.bot.votes_history:
            await ctx.send("目前沒有任何投票紀錄。")
            return
        view = VotingResultsView(self.bot.votes_history)
        await ctx.send("選擇要查看的投票：", view=view)

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        for vote in self.bot.votes_history:
            if vote["message_id"] == reaction.message.id:
                if str(reaction.emoji) == "👍":
                    vote["up"] += 1
                elif str(reaction.emoji) == "👎":
                    vote["down"] += 1

async def setup(bot: commands.Bot):
    await bot.add_cog(VotingCog(bot))
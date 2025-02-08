import discord
from discord.ext import commands
from discord import app_commands, Interaction
from main import bot, save_data

class TaskMenuView(discord.ui.View):
    def __init__(self, event_code: str, user_id: int):
        super().__init__(timeout=180)
        self.event_code = event_code
        self.user_id = user_id
        options = []
        event_data = bot.events.get(self.event_code)
        if event_data:
            for t in event_data.get("tasks", []):
                # 任務尚未被此使用者審核則可參加
                if self.user_id not in t["checked_users"]:
                    options.append(discord.SelectOption(
                        label=f"{t['task_id']}: {t['task_name']}",
                        description=t["task_description"] or "無詳細描述"
                    ))
        self.select_menu = discord.ui.Select(
            placeholder="選擇任務...",
            min_values=1,
            max_values=len(options) if options else 1,
            options=options
        )
        self.select_menu.callback = self.menu_callback
        self.add_item(self.select_menu)

    async def menu_callback(self, interaction: Interaction):
        selected = self.select_menu.values
        event_data = bot.events.get(self.event_code)
        if event_data:
            for sel_text in selected:
                task_id = int(sel_text.split(":")[0])
                for t in event_data["tasks"]:
                    if t["task_id"] == task_id:
                        if self.user_id not in t["assigned_users"]:
                            t["assigned_users"].append(self.user_id)
            save_data()
        await interaction.response.send("任務加入完成，可上傳圖片", ephemeral=True)

class ConfirmUploadView(discord.ui.View):
    def __init__(self, event_code: str, user_id: int):
        super().__init__(timeout=180)
        self.event_code = event_code
        self.user_id = user_id
    
    @discord.ui.button(label="上傳圖片", style=discord.ButtonStyle.primary)
    async def upload_button(self, interaction: Interaction, button: discord.ui.Button):
        await interaction.response.send("請直接使用指令上傳圖片，例如：`RA upload <圖片連結>`", ephemeral=True)

class TaskManagementCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="join_event_task")
    async def join_event_task(self, ctx: commands.Context, event_code: str):
        """參加指定活動並選擇任務"""
        if event_code not in bot.events:
            await ctx.send("活動代碼錯誤或不存在。")
            return
        event_obj = bot.events[event_code]
        if ctx.author.id not in event_obj["gamer_list"]:
            event_obj["gamer_list"].append(ctx.author.id)
            # 加入玩家的 joined_events
            if ctx.author.id not in bot.gamers:
                bot.gamers[ctx.author.id] = {
                    "gamer_id": ctx.author.id,
                    "gamer_card_number": None,
                    "gamer_is_blocked": False,
                    "gamer_bind_gamepass": None,
                    "joined_events": [],
                    "history_event_list": [],
                    "history_event_pts_list": []
                }
            bot.gamers[ctx.author.id]["joined_events"].append(event_code)
            save_data()
        await ctx.send(
            f"已參加活動 {event_code}，請選擇要參與的任務：",
            view=TaskMenuView(event_code, ctx.author.id)
        )
        await ctx.send("若任務選擇完畢，可進行圖片上傳或修改：", view=ConfirmUploadView(event_code, ctx.author.id))

    @commands.command(name="upload")
    async def upload_image(self, ctx: commands.Context, image_url: str):
        """上傳圖片並選擇對應任務審核"""
        gamer_info = bot.gamers.get(ctx.author.id)
        if not gamer_info or not gamer_info.get("joined_events"):
            await ctx.send("你尚未參加任何活動，無法上傳圖片。")
            return
        event_code = gamer_info["joined_events"][-1]
        event_obj = bot.events.get(event_code)
        if not event_obj:
            await ctx.send("活動資料未找到。")
            return
        options = []
        for t in event_obj.get("tasks", []):
            if ctx.author.id in t["assigned_users"] and ctx.author.id not in t["checked_users"]:
                options.append(discord.SelectOption(
                    label=str(t["task_id"]),
                    description=t["task_name"]
                ))
        if not options:
            await ctx.send("你的任務已全部上傳或審核完畢。")
            return
        menu = discord.ui.Select(placeholder="選擇要上傳圖片的任務...", options=options)
        async def select_callback(interaction: discord.Interaction):
            chosen_task_id = int(menu.values[0])
            for t in event_obj["tasks"]:
                if t["task_id"] == chosen_task_id:
                    t["checked_users"].append(ctx.author.id)
                    save_data()
                    await interaction.response.send(f"圖片已提交任務 {chosen_task_id} 審核完成，圖片連結: {image_url}", ephemeral=True)
                    return
        menu.callback = select_callback
        view = discord.ui.View()
        view.add_item(menu)
        await ctx.send("請選擇要上傳到哪個任務：", view=view)

async def setup(bot: commands.Bot):
    await bot.add_cog(TaskManagementCog(bot))
    print("TaskManagementCog 已成功加載。")
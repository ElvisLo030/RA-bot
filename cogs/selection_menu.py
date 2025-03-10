import discord
from discord.ext import commands
from discord.ui import Select, View, Modal, TextInput
from cogs.card_binding import CardBindingCog
from main import not_blocked, save_data, record_api
from datetime import datetime, timedelta

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
            placeholder="RAEXXX",
            max_length=6
        )
        self.add_item(self.event_code)

    async def on_submit(self, interaction: discord.Interaction):
        success, msg = await self.cog.join_event(interaction.user, self.event_code.value.strip())
        await interaction.response.send_message(msg, ephemeral=True)
        if success:
            await self.cog.update_menu(interaction.user)

class JoinedEventsSelect(discord.ui.Select):
    def __init__(self, bot: commands.Bot, joined_events: list, user_id: int):
        self.bot = bot
        self.user_id = user_id

        options = []
        for ev_code in joined_events:
            event_obj = bot.events.get(ev_code, {})
            event_name = event_obj.get("event_name", "未命名活動")
            options.append(
                discord.SelectOption(
                    label=ev_code,
                    description=event_name,
                    value=ev_code
                )
            )
        super().__init__(
            placeholder="選擇要查詢的活動",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        ev_code = self.values[0]
        event_obj = self.bot.events.get(ev_code, {})
        event_name = event_obj.get("event_name", "未命名活動")
        event_desc = event_obj.get("event_description", "無描述")
        event_tasks = event_obj.get("tasks", [])
        max_points = event_obj.get("max_points", 0)
        event_start_date = event_obj.get("event_start_date", "未知開始日期")
        event_end_date = event_obj.get("event_end_date", "未知結束日期")
        user_data = self.bot.gamers.get(self.user_id, {})
        user_points = user_data.get("events_points", {}).get(ev_code, 0)

        tasks_info = ""
        for t in event_tasks:
            t_name = t.get("task_name", "未命名任務")
            t_points = t.get("task_points", 0)
            tasks_info += f"- 任務：{t_name}可獲得{t_points}點\n"
        msg = (
            f"**活動名稱：**{event_name}\n"
            f"**活動描述：**{event_desc}\n"
            f"**開始日期：**{event_start_date}\n"
            f"**結束日期：**{event_end_date}\n\n"
            f"**任務清單：**\n{tasks_info if tasks_info else '無任務資訊'}\n"
            f"**最多可以獲得：**{max_points}點\n"
            f"**在此活動目前累積的點數：**{user_points}點"
        )

        await interaction.response.send_message(msg, ephemeral=True)
        for c in self.view.children:
            c.disabled = True
        await interaction.edit_original_response(view=self.view)

class JoinedEventsView(View):
    def __init__(self, bot: commands.Bot, joined_events: list, user_id: int):
        super().__init__(timeout=None)
        self.add_item(JoinedEventsSelect(bot, joined_events, user_id))

class ViewPrizeEventSelect(discord.ui.Select):
    """
    第一步：使用者從已參加的活動中選一個活動，查看有哪些獎品 + 是否已兌換。
    """
    def __init__(self, bot: commands.Bot, user: discord.User):
        self.bot = bot
        self.user = user

        user_data = bot.gamers.get(user.id, {})
        joined_events = user_data.get("joined_events", [])
        options = []
        for ev_code in joined_events:
            event_obj = bot.events.get(ev_code, {})
            # 僅顯示有prizes的活動 (如果沒有prizes就不列出)
            if "prizes" in event_obj and event_obj["prizes"]:
                event_name = event_obj.get("event_name", "未命名活動")
                options.append(discord.SelectOption(label=f"{event_name} ({ev_code})", value=ev_code))

        if not options:
            # 若沒有任何可兌換獎品的活動，就顯示一個 disabled
            options = [discord.SelectOption(label="沒有可兌換獎品的活動", value="none", default=True, disabled=True)]

        super().__init__(
            placeholder="選擇活動，查看可兌換獎品",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "none":
            await interaction.response.send_message("目前沒有可兌換獎品的活動。", ephemeral=True)
            return

        event_code = self.values[0]
        user_data = self.bot.gamers.get(self.user.id, {})
        event_obj = self.bot.events.get(event_code, {})
        prizes = event_obj.get("prizes", [])

        # 準備一個「已兌換清單」(若尚未有redeemed_prizes，就初始化)
        redeemed_map = user_data.setdefault("redeemed_prizes", {})
        user_redeemed_list = redeemed_map.setdefault(event_code, [])

        # 生成可視化訊息
        lines = []
        lines.append(f"**活動 {event_code}** 可兌換獎品：")
        if not prizes:
            lines.append("此活動尚未配置任何獎品。")
        else:
            for p in prizes:
                p_id = p["prize_id"]
                p_name = p["prize_name"]
                p_cost = p["points_required"]
                # 判斷使用者是否已兌換
                if p_id in user_redeemed_list:
                    lines.append(f"- [已兌換] {p_name} ( 所需 {p_cost} 點)")
                else:
                    lines.append(f"- [未兌換] {p_name} ( 所需 {p_cost} 點)")

        msg = "\n".join(lines)
        await interaction.response.send_message(msg, ephemeral=True)

class ViewPrizeEventView(View):
    def __init__(self, bot: commands.Bot, user: discord.User):
        super().__init__(timeout=None)
        self.add_item(ViewPrizeEventSelect(bot, user))

class SelectionMenuSelect(discord.ui.Select):
    def __init__(self, cog: CardBindingCog, user: discord.User):
        self.cog = cog
        self.user = user
        self.bot = cog.bot

        user_data = self.bot.gamers.get(user.id)
        has_card = (user_data and user_data.get("gamer_card_number"))

        options = []
        if not user_data:
            options.append(discord.SelectOption(label="綁定卡號", description="請輸入卡號綁定", value="bind_card"))
            options.append(discord.SelectOption(label="略過綁卡", description="可略過綁卡，但會限制部分功能", value="skip_card"))

            if self.has_any_timestamp(user.id):
                options.append(discord.SelectOption(label="查詢歷史紀錄", description="最多可以查詢最後10筆資料", value="query_timestamps"))

        else:
            if not has_card:
                options.append(discord.SelectOption(label="綁定卡號", description="請輸入卡號綁定", value="bind_card"))
                options.append(discord.SelectOption(label="參加活動", description="請先確認活動編號再使用此功能", value="join_event"))
                
                joined = user_data.get("joined_events", [])
                if joined:
                    options.append(discord.SelectOption(label="已參加的活動", description="可查詢已參加的活動", value="check_joined_events"))
                    options.append(discord.SelectOption(label="上傳圖片", description="請點選查詢指令", value="upload_pic"))
                    if self.has_redeemable_event(joined):
                        options.append(discord.SelectOption(label="查看獎品", value="view_prize_list"))

                if self.has_any_timestamp(user.id):
                    options.append(discord.SelectOption(label="查詢歷史紀錄", description="最多可以查詢最後10筆資料", value="query_timestamps"))
            else:
                options.append(discord.SelectOption(label="參加活動", description="請先查詢活動編號再使用此功能", value="join_event"))
                options.append(discord.SelectOption(label="查詢卡號", description="此指令僅提供查詢，若需修改請洽店員", value="query_card"))

                joined = user_data.get("joined_events", [])
                if joined:
                    options.append(discord.SelectOption(label="已參加的活動", description="可查詢已參加的活動", value="check_joined_events"))
                    options.append(discord.SelectOption(label="上傳圖片", description="請點選查詢指令", value="upload_pic"))
                    if self.has_redeemable_event(joined):
                        options.append(discord.SelectOption(label="查看獎品", value="view_prize_list"))

                if self.has_any_timestamp(user.id):
                    options.append(discord.SelectOption(label="查詢歷史紀錄", description="最多可以查詢最後10筆資料", value="query_timestamps"))

        super().__init__(placeholder="選擇功能", min_values=1, max_values=1, options=options)

    def has_any_timestamp(self, user_id: int) -> bool:
        user_data = self.bot.gamers.get(user_id, {})
        points_history = user_data.get("points_history", [])
        if points_history:
            return True

        joined_map = user_data.get("joined_event_timestamps", {})
        if joined_map:
            return True

        image_list = self.bot.user_images.get(user_id, [])
        for img in image_list:
            if img.get("upload_time") or img.get("approved_time") or img.get("rejected_time"):
                return True
            
        return False

    def has_redeemable_event(self, joined_events: list) -> bool:
        for ev_code in joined_events:
            event_obj = self.bot.events.get(ev_code, {})
            if "prizes" in event_obj and event_obj["prizes"]:
                return True
        return False

    async def callback(self, interaction: discord.Interaction):
        choice = self.values[0]
        if choice == "bind_card":
            modal = CardBindModal(self.cog)
            await interaction.response.send_modal(modal)
        elif choice == "skip_card":
            if self.user.id not in self.bot.gamers:
                self.bot.gamers[self.user.id] = {
                    "gamer_id": self.user.id,
                    "gamer_card_number": None,
                    "gamer_is_blocked": False,
                    "gamer_bind_gamepass": None,
                    "joined_events": [],
                    "history_event_list": [],
                    "history_event_pts_list": [],
                    "events_points": {},
                    "joined_event_timestamps": {},
                    "redeemed_prizes": {}  
                }
                save_data()
            await interaction.response.send_message("已略過綁卡，你可以隨時使用「綁定卡號」功能綁定。", ephemeral=True)
            await self.cog.update_menu(interaction.user)
        elif choice == "join_event":
            modal = JoinEventModal(self.cog)
            await interaction.response.send_modal(modal)
        elif choice == "query_card":
            success, msg = await self.cog.query_card(interaction.user)
            await interaction.response.send_message(msg, ephemeral=True)
        elif choice == "upload_pic":
            await interaction.response.send_message(
                "請在私訊輸入 `RA 上傳圖片 RAEXXX` (XXX=活動編號）並附加圖片。",
                ephemeral=True
            )
        elif choice == "check_joined_events":
            user_data = self.bot.gamers.get(self.user.id, {})
            joined = user_data.get("joined_events", [])
            if not joined:
                await interaction.response.send_message("你目前尚未參加任何活動。", ephemeral=True)
                return
            view = JoinedEventsView(self.bot, joined, self.user.id)
            await interaction.response.send_message("請選擇要查詢的活動：", view=view, ephemeral=True)
        elif choice == "query_timestamps":
            user_data = self.bot.gamers.get(self.user.id, {})
            points_history = user_data.get("points_history", [])
            joined_map = user_data.get("joined_event_timestamps", {})
            user_images = self.bot.user_images.get(self.user.id, [])

            all_records = []
            for item in points_history:
                stamp = item.get("timestamp")
                if not stamp:
                    continue
                record_type = item.get("type","?")
                pts = item.get("points",0)
                ev_code = item.get("event_code","")

                # --- 新增 admin_redeem 顯示 ---
                if record_type == "admin_redeem":
                    # 後台兌換 => 撈出 prize_name
                    event_obj = self.bot.events.get(ev_code, {})
                    prize_name = "?"
                    prize_id = item.get("prize_id")
                    for p in event_obj.get("prizes", []):
                        if p["prize_id"] == prize_id:
                            prize_name = p["prize_name"]
                            break
                    detail = f"獎品兌換 (活動：{ev_code}, 獎品={prize_name})"

                elif record_type == "global":
                    detail = f"全域加點 +{pts}"
                elif record_type == "event":
                    detail = f"活動({ev_code})加點 +{pts}"
                elif record_type == "api":
                    detail = f"API加點 +{pts}"
                elif record_type == "redeem":
                    # 舊邏輯
                    detail = f"兌換獎品 `{item.get('prize_name','?')}` {pts} 點"  # pts為負值
                else:
                    detail = f"其他加點/動作 {pts}"

                all_records.append({"timestamp": stamp, "detail": detail})

            for ev_code, tstamp in joined_map.items():
                all_records.append({
                    "timestamp": tstamp,
                    "detail": f"加入活動 {ev_code}"
                })

            for img in user_images:
                event_code = img["event_code"]
                task_id = img["task_id"]
                event_obj = self.bot.events.get(event_code, {})
                tasks = event_obj.get("tasks", [])
                task_obj = None
                for t in tasks:
                    if t.get("task_id") == task_id:
                        task_obj = t
                        break
                task_name = task_obj.get("task_name", "未知任務") if task_obj else "未知任務"

                if "upload_time" in img:
                    all_records.append({
                        "timestamp": img["upload_time"],
                        "detail": f"上傳圖片 `{img['filename']}` (活動={img['event_code']}, 任務={task_name})"
                    })
                if "approved_time" in img:
                    all_records.append({
                        "timestamp": img["approved_time"],
                        "detail": f"圖片 `{img['filename']}` 審核通過 (活動={img['event_code']}, 任務={task_name})"
                    })
                if "rejected_time" in img:
                    all_records.append({
                        "timestamp": img["rejected_time"],
                        "detail": f"圖片 `{img['filename']}` 審核拒絕 (活動={img['event_code']}, 任務={task_name})"
                    })

            if not all_records:
                await interaction.response.send_message("尚無任何時間戳記紀錄。", ephemeral=True)
                return

            def parse_iso(s):
                try:
                    return datetime.fromisoformat(s)
                except:
                    return None

            valid_records = [r for r in all_records if parse_iso(r["timestamp"])]
            valid_records.sort(key=lambda x: parse_iso(x["timestamp"]))

            recent_10 = valid_records[-10:]
            lines = []
            for r in recent_10:
                lines.append(f"[{r['timestamp']}] {r['detail']}")

            msg = "**以下為最近10筆時間戳記紀錄：**\n" + "\n".join(lines)
            await interaction.response.send_message(msg, ephemeral=True)

        elif choice == "view_prize_list":
            await interaction.response.send_message(
                "請選擇要查看獎品的活動：",
                view=ViewPrizeEventView(self.bot, self.user),
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
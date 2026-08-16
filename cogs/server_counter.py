"""
Yokaro 伺服器統計計數器 (!伺服器計數)
建立語音頻道計數器，即時顯示會員/在線/機器人等數字。
Channel 對 @everyone 鎖定（僅可視，不可進入）。
"""
import discord
from discord.ext import commands, tasks
import asyncio
import time
import re
from utils.data_store import DataStore

# 可選的計數類型
COUNTER_TYPES = {
    "members": "👥 會員數",
    "humans": "🧑 人類",
    "bots": "🤖 機器人",
    "online": "🟢 在線",
    "offline": "🌙 離線",
    "voice": "🔊 語音人數",
    "ytsub": "🔴 YT 訂閱數",
    "ytmember": "⭐ YT 頻道會員數",
}

# 需要外部抓取的 YT 計數類型（更新較慢以免被 YouTube 封鎖）
YT_TYPES = ("ytsub", "ytmember")
# 抓取間隔（秒）：YT 計數不適合每秒刷，設為 5 分鐘一次
YT_FETCH_INTERVAL = 300
# 每秒「最多改名」幾個頻道。Discord 對頻道改名 PATCH 有 rate limit，
# 過密會被 429 罰數百秒。做法：每秒掃描，但只挑少數需要改名的發送。
MAX_PATCH_PER_TICK = 1
# 每個頻道「兩次改名」之間的最小間隔（秒）：避免同一頻道每秒連打 429
MIN_NAME_INTERVAL = 5


class AddCounterModal(discord.ui.Modal):
    """新增計數器 Modal"""

    def __init__(self, cog, guild_id):
        self._cog = cog
        self._gid = guild_id
        super().__init__(title="📊 新增計數器")

        self._name = discord.ui.TextInput(
            label="頻道名稱（用 {count} 代表數字）",
            placeholder="例如：👥 會員數: {count}",
            default="👥 會員數: {count}",
            required=True,
            max_length=90,
        )
        self.add_item(self._name)

        self._type_select = discord.ui.TextInput(
            label="計數類型（輸入代碼）",
            placeholder="members / humans / bots / online / voice",
            default="members",
            required=True,
            max_length=20,
        )
        self.add_item(self._type_select)

    async def on_submit(self, interaction: discord.Interaction):
        template = self._name.value.strip()
        ctype = self._type_select.value.strip().lower()

        if "{count}" not in template:
            return await interaction.response.send_message("❌ 頻道名稱必須包含 `{count}` ！", ephemeral=True)

        if ctype not in COUNTER_TYPES:
            return await interaction.response.send_message(
                f"❌ 無效的計數類型。可用：{', '.join(COUNTER_TYPES.keys())}", ephemeral=True
            )

        guild = interaction.guild
        if not guild:
            return
        count_num = self._cog._compute_count(guild, ctype)
        channel_name = template.replace("{count}", str(count_num))

        try:
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(
                    view_channel=True, connect=False, speak=False,
                )
            }
            channel = await guild.create_voice_channel(
                name=channel_name, overwrites=overwrites,
                reason="伺服器計數器自動建立",
            )
        except Exception as e:
            return await interaction.response.send_message(f"❌ 建立頻道失敗：{e}", ephemeral=True)

        configs = self._cog.get_configs(self._gid)
        configs.append({"channel_id": channel.id, "template": template, "type": ctype})
        self._cog.commit(self._gid, configs)

        embed = self._cog._build_panel_embed(self._gid)
        view = ServerCounterView(self._cog, self._gid)
        await interaction.response.edit_message(embed=embed, view=view)


class EditCounterModal(discord.ui.Modal):
    """編輯計數器 Modal：輸入編號後可修改名稱與類型"""

    def __init__(self, cog, guild_id):
        self._cog = cog
        self._gid = guild_id
        super().__init__(title="✏️ 編輯計數器")

        self._index = discord.ui.TextInput(
            label="要編輯的編號（不填則依現有順序）",
            placeholder="例如：1",
            required=True,
            max_length=5,
        )
        self.add_item(self._index)

        self._name = discord.ui.TextInput(
            label="新的名稱（用 {count} 代表數字）",
            placeholder="例如：👥 會員數: {count}",
            required=True,
            max_length=90,
        )
        self.add_item(self._name)

        self._type_select = discord.ui.TextInput(
            label="計數類型（輸入代碼）",
            placeholder="members / humans / bots / online / voice",
            required=True,
            max_length=20,
        )
        self.add_item(self._type_select)

    async def on_submit(self, interaction: discord.Interaction):
        # 先立刻回應，避免耗時（如抓取 YT 數值）超過 3 秒造成 404 Unknown interaction
        await interaction.response.defer(ephemeral=True)

        try:
            idx = int(self._index.value.strip()) - 1
        except ValueError:
            return await interaction.followup.send("❌ 編號必須是數字！", ephemeral=True)

        configs = self._cog.get_configs(self._gid)
        if idx < 0 or idx >= len(configs):
            return await interaction.followup.send("❌ 找不到這個編號的計數器！", ephemeral=True)

        template = self._name.value.strip()
        ctype = self._type_select.value.strip().lower()

        if "{count}" not in template:
            return await interaction.followup.send("❌ 名稱必須包含 `{count}`！", ephemeral=True)
        if ctype not in COUNTER_TYPES:
            return await interaction.followup.send(
                f"❌ 無效的計數類型。可用：{', '.join(COUNTER_TYPES.keys())}", ephemeral=True
            )

        old_cfg = configs[idx]
        old_cfg["template"] = template
        old_cfg["type"] = ctype
        self._cog.commit(self._gid, configs)

        # 立即更新頻道名稱
        guild = interaction.guild
        if guild:
            ch = guild.get_channel(old_cfg.get("channel_id"))
            if ch:
                count_val = await self._cog._compute_count_for_cfg(guild, old_cfg)
                try:
                    await ch.edit(name=template.replace("{count}", str(count_val)))
                except Exception as e:
                    print(f"ServerCounter edit rename error: {e}")

        embed = self._cog._build_panel_embed(self._gid)
        view = ServerCounterView(self._cog, self._gid)
        try:
            await interaction.edit_original_message(embed=embed, view=view)
        except Exception:
            pass


class YTLinkModal(discord.ui.Modal):
    """新增 YT 訂閱/會員數計數頻道：貼上頻道連結即可"""

    def __init__(self, cog, guild_id):
        self._cog = cog
        self._gid = guild_id
        super().__init__(title="🔗 新增 YT 計數頻道")

        self._link = discord.ui.TextInput(
            label="YouTube 頻道連結（貼上即可）",
            placeholder="例如：https://www.youtube.com/@handle",
            required=True,
            max_length=200,
        )
        self.add_item(self._link)

        self._type_select = discord.ui.TextInput(
            label="計數類型",
            placeholder="ytsub(訂閱數) / ytmember(頻道會員數)",
            default="ytsub",
            required=True,
            max_length=20,
        )
        self.add_item(self._type_select)

        self._name = discord.ui.TextInput(
            label="頻道名稱（用 {count} 代表數字）",
            placeholder="例如：🔴 訂閱: {count}",
            default="🔴 訂閱: {count}",
            required=True,
            max_length=90,
        )
        self.add_item(self._name)

    @staticmethod
    def _parse_yt_id(link: str):
        """從連結解析出可供 yt-dlp 使用的頻道識別碼"""
        link = link.strip()
        m = re.search(r'@[\w.\-]+', link)
        if m:
            return m.group(0)
        for prefix in ("/channel/", "/c/", "/user/"):
            m = re.search(re.escape(prefix) + r'[\w.\-]+', link)
            if m:
                return m.group(0).lstrip('/')
        return None

    async def on_submit(self, interaction: discord.Interaction):
        # 先立刻回應，避免超過 3 秒造成 Unknown interaction (404)
        await interaction.response.defer(ephemeral=True)

        yt_id = self._parse_yt_id(self._link.value)
        if not yt_id:
            return await interaction.followup.send(
                "❌ 無法辨識 YouTube 頻道連結！請貼上 `https://www.youtube.com/@handle` 或 `/channel/UCxxx` 格式。",
                ephemeral=True,
            )

        ctype = self._type_select.value.strip().lower()
        if ctype not in YT_TYPES:
            return await interaction.followup.send(
                f"❌ YT 計數類型只能是：{', '.join(YT_TYPES)}", ephemeral=True
            )

        template = self._name.value.strip()
        if "{count}" not in template:
            return await interaction.followup.send("❌ 名稱必須包含 `{count}`！", ephemeral=True)

        guild = interaction.guild
        if not guild:
            return

        # 先抓一次數值當初始名稱（已 defer，就算抓取較慢也不會逾期）
        count_val = await self._cog._compute_yt_count(guild, {"type": ctype, "yt_id": yt_id})
        if count_val is None:
            count_val = 0
        channel_name = template.replace("{count}", str(count_val))

        try:
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(
                    view_channel=True, connect=False, speak=False,
                )
            }
            channel = await guild.create_voice_channel(
                name=channel_name, overwrites=overwrites,
                reason="YT 計數器自動建立",
            )
        except Exception as e:
            return await interaction.followup.send(f"❌ 建立頻道失敗：{e}", ephemeral=True)

        configs = self._cog.get_configs(self._gid)
        configs.append({"channel_id": channel.id, "template": template, "type": ctype, "yt_id": yt_id})
        self._cog.commit(self._gid, configs)

        embed = self._cog._build_panel_embed(self._gid)
        view = ServerCounterView(self._cog, self._gid)
        try:
            await interaction.edit_original_message(embed=embed, view=view)
        except Exception:
            pass


class RemoveCounterSelect(discord.ui.Select):
    """移除計數器選單（修正：正確定義 __init__ 並回應 interaction）"""

    def __init__(self, cog, guild_id):
        self._cog = cog
        self._gid = guild_id
        configs = cog.get_configs(guild_id)
        options = []
        for i, cfg in enumerate(configs):
            tname = cfg.get("template", "?").replace("{count}", "N")
            options.append(discord.SelectOption(label=f"{i + 1}. {tname[:40]}", value=str(i)))
        options.append(discord.SelectOption(label="取消", value="-1"))
        super().__init__(placeholder="選擇要移除的計數器...", options=options)

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "-1":
            return await interaction.response.edit_message(content="已取消。", embed=None, view=None)
        idx = int(self.values[0])
        configs = self._cog.get_configs(self._gid)
        if idx < 0 or idx >= len(configs):
            return await interaction.response.edit_message(content="找不到此編號的計數器。", embed=None, view=None)

        removed = configs.pop(idx)
        self._cog.commit(self._gid, configs)
        guild = interaction.guild
        if guild:
            ch = guild.get_channel(removed.get("channel_id"))
            if ch:
                try:
                    await ch.delete(reason="移除伺服器計數器")
                except:
                    pass

        embed = self._cog._build_panel_embed(self._gid)
        view = ServerCounterView(self._cog, self._gid)
        await interaction.response.edit_message(content=None, embed=embed, view=view)


class ServerCounterView(discord.ui.View):
    def __init__(self, cog, guild_id):
        super().__init__(timeout=300)
        self._cog = cog
        self._gid = guild_id

    @discord.ui.button(label="➕ 新增計數", style=discord.ButtonStyle.success)
    async def add_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ 只有管理員可以操作", ephemeral=True)
        modal = AddCounterModal(self._cog, self._gid)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="🔗 新增 YT 頻道", style=discord.ButtonStyle.primary)
    async def yt_add_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ 只有管理員可以操作", ephemeral=True)
        modal = YTLinkModal(self._cog, self._gid)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="✏️ 編輯計數", style=discord.ButtonStyle.secondary)
    async def edit_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ 只有管理員可以操作", ephemeral=True)
        configs = self._cog.get_configs(self._gid)
        if not configs:
            return await interaction.response.send_message("❌ 目前沒有任何計數器可以編輯！", ephemeral=True)
        modal = EditCounterModal(self._cog, self._gid)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="🗑️ 移除計數", style=discord.ButtonStyle.danger)
    async def remove_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ 只有管理員可以操作", ephemeral=True)
        configs = self._cog.get_configs(self._gid)
        if not configs:
            return await interaction.response.send_message("❌ 目前沒有計數器可以移除！", ephemeral=True)
        select = RemoveCounterSelect(self._cog, self._gid)
        view = discord.ui.View(timeout=30)
        view.add_item(select)
        await interaction.response.send_message("請選擇要移除的計數器：", view=view, ephemeral=True)


class ServerCounterCog(commands.Cog):
    """📊 伺服器計數器 - 即時顯示會員/在線/機器人等資料"""

    def __init__(self, bot):
        self.bot = bot
        self.store = DataStore("server_counters.json")
        self.yt_cache = {}  # (gid, yt_id, ctype) -> (count, last_fetch_ts)
        self.rename_next = {}  # channel_id -> 下一次允許改名的時間戳（兼顧 429 與最小間隔）
        self.update_loop.start()

    def cog_unload(self):
        self.update_loop.cancel()

    def get_configs(self, guild_id):
        return self.store.get(guild_id, [])

    def commit(self, guild_id, configs):
        self.store.set(guild_id, configs)

    def _compute_count(self, guild, ctype):
        if ctype == "members":
            return guild.member_count
        elif ctype == "humans":
            return sum(1 for m in guild.members if not m.bot)
        elif ctype == "bots":
            return sum(1 for m in guild.members if m.bot)
        elif ctype == "online":
            return sum(1 for m in guild.members if m.status != discord.Status.offline)
        elif ctype == "offline":
            return sum(1 for m in guild.members if m.status == discord.Status.offline)
        elif ctype == "voice":
            return sum(len(vc.members) for vc in guild.voice_channels)
        return 0

    async def _fetch_yt_count(self, yt_id: str, ctype: str):
        """用 yt-dlp 抓取頻道訂閱/會員數（阻塞呼叫移到背景執行緒）。
        注意：YouTube 只對外公開「訂閱數」，「會員數」不會公開給第三方，
        因此 ytmember 會回退抓訂閱數作為替代顯示。
        """
        try:
            def _blocking_fetch():
                import yt_dlp
                with yt_dlp.YoutubeDL({
                    "quiet": True,
                    "no_warnings": True,
                    "extract_flat": True,
                }) as ydl:
                    info = ydl.extract_info(
                        f"https://www.youtube.com/{yt_id}",
                        download=False,
                    )
                    if not info:
                        return None
                    if ctype in YT_TYPES:
                        return info.get("channel_follower_count")
                    return None

            return await asyncio.to_thread(_blocking_fetch)
        except Exception:
            return None

    async def _compute_yt_count(self, guild, cfg) -> int:
        """帶快取的 YT 計數抓取；5 分鐘內不重複抓取以免被封鎖"""
        yt_id = cfg.get("yt_id")
        ctype = cfg.get("type")
        if not yt_id:
            return None
        cache_key = (guild.id, yt_id, ctype)
        cached = self.yt_cache.get(cache_key)
        now = time.time()
        if cached and now - cached[1] < YT_FETCH_INTERVAL:
            return cached[0]
        count = await self._fetch_yt_count(yt_id, ctype)
        self.yt_cache[cache_key] = (count, now)
        return count

    async def _compute_count_for_cfg(self, guild, cfg):
        """依 cfg 類型計算數量（YT 類型走 async 抓取，其餘走內部計算）"""
        ctype = cfg.get("type")
        if ctype in YT_TYPES:
            val = await self._compute_yt_count(guild, cfg)
            return val if val is not None else 0
        return self._compute_count(guild, ctype)

    def _build_panel_embed(self, guild_id):
        configs = self.get_configs(guild_id)
        embed = discord.Embed(
            title="📊 伺服器計數設定",
            description="管理伺服器即時統計頻道。頻道對 `@everyone` 鎖定（僅可視、不可進入）",
            color=0x2ecc71,
        )
        if not configs:
            embed.add_field(name="目前無計數器", value="點擊「新增計數」按鈕來建立！", inline=False)
        else:
            for i, cfg in enumerate(configs, 1):
                tname = cfg.get("template", "?")
                ctype = COUNTER_TYPES.get(cfg["type"], cfg["type"])
                ch_id = cfg.get("channel_id", 0)
                ch = self.bot.get_channel(ch_id)
                status = f"<#{ch_id}>" if ch else "❌ (頻道已刪除)"
                embed.add_field(
                    name=f"{i}. {tname.replace('{count}', 'N')}",
                    value=f"類型：{ctype} | 頻道：{status}",
                    inline=False,
                )
        embed.set_footer(text="即時更新間隔：每秒")
        return embed

    @tasks.loop(seconds=1)
    async def update_loop(self):
        """背景任務：每秒檢查所有計數器，但每秒最多改名 MAX_PATCH_PER_TICK 個頻道，
        其餘排到下一秒，兼顧即時更新又避開 Discord 429 rate limit。"""
        await self.bot.wait_until_ready()

        # 收集所有「需要改名」的頻道
        pending = []
        for gid_str in list(self.store.data.keys()):
            guild = self.bot.get_guild(int(gid_str))
            if not guild:
                continue
            configs = self.get_configs(int(gid_str))
            for cfg in list(configs):
                ch = guild.get_channel(cfg.get("channel_id"))
                if not ch:
                    continue
                count_val = await self._compute_count_for_cfg(guild, cfg)
                if count_val is None:
                    continue
                new_name = cfg["template"].replace("{count}", str(count_val))
                if ch.name != new_name:
                    pending.append((ch, new_name))

        # 每秒最多改前幾個，其餘留到下一個 tick；並尊重每頻道最小間隔與 429 冷卻
        now = time.time()
        for ch, new_name in pending[:MAX_PATCH_PER_TICK]:
            if now < self.rename_next.get(ch.id, 0):
                continue
            try:
                await ch.edit(name=new_name)
                self.rename_next[ch.id] = now + MIN_NAME_INTERVAL
            except discord.HTTPException as e:
                # 被限流/錯誤：把該頻道冷卻久一點再講，尊重 Discord Retry-After
                penalty = 120 if getattr(e, "status", None) == 429 else 30
                self.rename_next[ch.id] = now + penalty
                print(f"ServerCounter rename limited({penalty}s): {e}")
                break
            except Exception as e:
                print(f"ServerCounter rename error: {e}")
        await asyncio.sleep(0)

    @update_loop.before_loop
    async def before_update_loop(self):
        await self.bot.wait_until_ready()

    @commands.command(name='伺服器計數', aliases=['計數面板', 'counter', 'servercounter'])
    @commands.has_permissions(administrator=True)
    async def counter_panel(self, ctx):
        """📊 (管理員) 開啟伺服器即時統計計數器控制面板"""
        guild_id = ctx.guild.id
        embed = self._build_panel_embed(guild_id)
        view = ServerCounterView(self, guild_id)
        await ctx.send(embed=embed, view=view)


async def setup(bot):
    await bot.add_cog(ServerCounterCog(bot))
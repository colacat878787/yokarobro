import discord
from discord.ext import commands
from discord import app_commands
import json, os, random, asyncio

KUJI_FILE = "kuji.json"
PREMIUM_FILE = "premium_users.json"
ADMIN_IDS = [1113353915010920452, 501251225715474433]

# --- 補貨數量彈窗 ---
class RestockModal(discord.ui.Modal):
    def __init__(self, prize_name, cog):
        super().__init__(title=f"♻️ 補貨 - {prize_name.split(': ')[0]}")
        self.prize_name = prize_name
        self.cog = cog
        self.amount = discord.ui.TextInput(label="輸入補貨數量", placeholder="例如: 5", min_length=1, max_length=3, required=True)
        self.add_item(self.amount)

    async def on_submit(self, interaction: discord.Interaction):
        if not self.amount.value.isdigit():
            return await interaction.response.send_message("❌ 請輸入有效的數字！", ephemeral=True)
        
        count = int(self.amount.value)
        # 加入獎池
        for _ in range(count):
            self.cog.pool.append(self.prize_name)
        self.cog._save()
        
        await interaction.response.send_message(f"✅ 已成功為 **{self.prize_name}** 補貨 {count} 個！目前獎池剩餘: {len(self.cog.pool)}", ephemeral=True)

class RestockView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog
        prizes = [
            "💎 A賞: Yokaro Premium 永久會員",
            "💰 B賞: 5,000 卡洛幣",
            "💰 C賞: 1,000 卡洛幣",
            "💰 D賞: 500 卡洛幣",
            "🧧 E賞: 50 卡洛幣"
        ]
        for p in prizes:
            label = p.split(": ")[0]
            # 持久化視圖必須要有 custom_id
            btn = discord.ui.Button(label=label, style=discord.ButtonStyle.secondary, custom_id=f"kuji_restock_{label}")
            btn.callback = self.create_callback(p)
            self.add_item(btn)
            
        # --- 神級補貨按鈕 ---
        fill_all = discord.ui.Button(label="✨ 諸神黃昏：全部填滿 (99,999)", style=discord.ButtonStyle.danger, custom_id="kuji_fill_all", row=2)
        fill_all.callback = self.fill_all_callback
        self.add_item(fill_all)

    async def fill_all_callback(self, interaction: discord.Interaction):
        if interaction.user.id not in ADMIN_IDS: return await interaction.response.send_message("❌ 您無權動用神權。", ephemeral=True)
        prizes = [
            "💎 A賞: Yokaro Premium 永久會員",
            "💰 B賞: 5,000 卡洛幣",
            "💰 C賞: 1,000 卡洛幣",
            "💰 D賞: 500 卡洛幣",
            "🧧 E賞: 50 卡洛幣"
        ]
        self.cog.pool = []
        for p in prizes:
            self.cog.pool.extend([p] * 99999)
        self.cog._save()
        await interaction.response.send_message("🌌 **萬象更生！** 獎池已全部補滿至 **99,999** 個！", ephemeral=True)

    def create_callback(self, prize_name):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id not in ADMIN_IDS: return await interaction.response.send_message("❌ 您無權補貨。", ephemeral=True)
            await interaction.response.send_modal(RestockModal(prize_name, self.cog))
        return callback

class GiftModal(discord.ui.Modal, title="🎁 送禮給群友"):
    username = discord.ui.TextInput(label="請輸入對方的使用者名稱 (username)", placeholder="例如: colacat8787", required=True)

    def __init__(self, prize, giver, kuji_cog):
        super().__init__()
        self.prize = prize
        self.giver = giver
        self.kuji_cog = kuji_cog

    async def on_submit(self, interaction: discord.Interaction):
        target = discord.utils.find(lambda u: u.name == self.username.value or u.global_name == self.username.value, interaction.guild.members)
        if not target:
            return await interaction.response.send_message("❌ 找不到該使用者！", ephemeral=True)
        if target.id == self.giver.id:
            return await interaction.response.send_message("❌ 不能送給自己喔！", ephemeral=True)

        self.kuji_cog.transfer_prize(self.giver, target, self.prize)
        await interaction.response.send_message(f"🎁 **{self.giver.display_name}** 把大獎【{self.prize}】送給了 **{target.display_name}**！")

class KujiGiftView(discord.ui.View):
    def __init__(self, prize, user, kuji_cog):
        super().__init__(timeout=300)
        self.prize = prize
        self.user = user
        self.kuji_cog = kuji_cog

    @discord.ui.button(label="🎁 我太多了 我想送給別人", style=discord.ButtonStyle.secondary, custom_id="kuji_gift_btn")
    async def gift_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("❌ 這是別人的獎品喔！", ephemeral=True)
        await interaction.response.send_modal(GiftModal(self.prize, self.user, self.kuji_cog))
        button.disabled = True
        await interaction.message.edit(view=self)

class KujiView(discord.ui.View):
    def __init__(self, economy_cog):
        super().__init__(timeout=None)
        self.economy_cog = economy_cog

    @discord.ui.button(label="🎲 立即抽賞 (單抽 $500)", style=discord.ButtonStyle.primary, custom_id="kuji_draw")
    async def draw(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        uid = str(interaction.user.id)
        kuji_cog = self.economy_cog.bot.get_cog("KujiCog")
        
        is_admin = interaction.user.id == 1113353915010920452
        cost = 0 if is_admin else 500

        if not is_admin and self.economy_cog.get_balance(uid) < cost:
            return await interaction.edit_original_response(content="嗷嗷嗷～錢包不夠 $500 喔！")

        # 大總裁神抽：必中 A 賞
        if is_admin:
            prize = "💎 A賞: Yokaro Premium 永久會員"
            self.economy_cog.add_money(uid, 114514191981081024)
        else:
            prize = kuji_cog.draw_prize()
            
        if not prize:
            return await interaction.edit_original_response(content="😱 本輪一番賞已完售！管理員已收到通知進行補貨。")

        self.economy_cog.add_money(uid, -cost)
        kuji_cog.grant_prize(interaction.user, prize)
        
        msg = await interaction.followup.send(f"🌌 {interaction.user.mention} 正在抽賞...")
        await asyncio.sleep(1)

        embed = discord.Embed(title="🎊 恭喜中獎！", description=f"{interaction.user.mention} 抽中了：\n\n✨ **【 {prize} 】** ✨", color=0xf1c40f)
        if is_admin:
            embed.add_field(name="👑 大總裁特權", value="💰 額外獲得福利金：**$114,514,191,981,081,024** 元！")
        await msg.edit(content=None, embed=embed, view=KujiGiftView(prize, interaction.user, kuji_cog))

    @discord.ui.button(label="🎲 十連抽 ($5000)", style=discord.ButtonStyle.success, custom_id="kuji_draw_10")
    async def draw_10(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        uid = str(interaction.user.id)
        kuji_cog = self.economy_cog.bot.get_cog("KujiCog")
        
        is_admin = interaction.user.id == 1113353915010920452
        cost = 0 if is_admin else 5000

        if not is_admin and self.economy_cog.get_balance(uid) < cost:
            return await interaction.edit_original_response(content="嗷嗷嗷～錢包不夠 $5000 喔！")
        if not is_admin and len(kuji_cog.pool) < 10:
            return await interaction.edit_original_response(content="❌ 獎池剩餘數量不足十個！")
            
        self.economy_cog.add_money(uid, -cost)
        msg = await interaction.followup.send(f"🌌 {interaction.user.mention} 正在進行十連抽...", ephemeral=False)
        await asyncio.sleep(1)

        if is_admin:
            prizes = ["💎 A賞: Yokaro Premium 永久會員"] * 10
            self.economy_cog.add_money(uid, 114514191981081024 * 10)
        else:
            prizes = [kuji_cog.draw_prize() for _ in range(10)]
            
        for p in prizes: kuji_cog.grant_prize(interaction.user, p)
            
        desc = "\n".join([f"**第 {i+1} 抽:** {p}" for i, p in enumerate(prizes)])
        embed = discord.Embed(title="🎊 十連抽結果！", description=f"{interaction.user.mention} 的十抽結果：\n\n{desc}", color=0x9b59b6)
        if is_admin:
            embed.add_field(name="👑 大總裁特權", value=f"💰 額外獲得福利金：**${114514191981081024 * 10:,}** 元！")
        await msg.edit(content=None, embed=embed)

    @discord.ui.button(label="💎 一次抽完 (包台 $100,000)", style=discord.ButtonStyle.danger, custom_id="kuji_buyout")
    async def buyout(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        uid = str(interaction.user.id)
        kuji_cog = self.economy_cog.bot.get_cog("KujiCog")
        
        is_admin = interaction.user.id in ADMIN_IDS
        cost = 0 if is_admin else 100000
        
        remaining = len(kuji_cog.pool)
        if remaining == 0:
            return await interaction.edit_original_response(content="❌ 獎池目前是空的，無法包台！")

        # --- 包台安全鎖 ---
        if remaining > 10000 and not is_admin:
            return await interaction.edit_original_response(content="⚠️ **警報：** 目前獎池過於龐大（超過 10,000 個），為了防止金融崩潰，只有管理員可以執行包台！")

        if not is_admin and self.economy_cog.get_balance(uid) < cost:
            return await interaction.edit_original_response(content="嗷嗷嗷～包台需要 $100,000 喔！")

        self.economy_cog.add_money(uid, -cost)
        
        # 清空獎池並派獎
        prizes = list(kuji_cog.pool)
        kuji_cog.pool = []
        kuji_cog._save()
        
        for p in prizes: kuji_cog.grant_prize(interaction.user, p)
        
        msg = await interaction.followup.send(f"🔱 **{interaction.user.mention} 豪氣萬千，直接買下了整座星空箱！**", ephemeral=False)
        embed = discord.Embed(title="👑 霸氣包台！", description=f"恭喜您獲得了全數 **{remaining}** 個獎項！\n管理員已被通知準備進行大規模補貨。", color=0xe91e63)
        await msg.edit(content=None, embed=embed)
        
        # 通知管理員
        for admin_id in ADMIN_IDS:
            admin = interaction.client.get_user(admin_id)
            if admin:
                try: await admin.send(f"🚨 **[一番賞告急]** 使用者 {interaction.user.name} 剛才包台了！目前庫存為 0，請盡速補貨。")
                except: pass

class KujiCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.premium_users = self._load_premium()
        self.tag_file = "tag_prefs.json"
        self.tag_prefs = self._load_json(self.tag_file, {})
        self.pool = self._load()
        if not self.pool: self.pool = self._default_pool()
        self._save() 
        self.bot.add_view(KujiView(self.bot.get_cog("EconomyCog")))
        self.bot.add_view(RestockView(self))

    def _load_json(self, path, default):
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f: return json.load(f)
            except: pass
        return default

    def _save_json(self, path, data):
        with open(path, "w", encoding="utf-8") as f: json.dump(data, f, indent=2)

    def _load(self):
        return self._load_json(KUJI_FILE, self._default_pool())

    def _load_premium(self):
        return self._load_json(PREMIUM_FILE, [])

    def is_premium(self, user_id):
        return user_id in self.premium_users

    def _default_pool(self):
        return (["💎 A賞: Yokaro Premium 永久會員"] * 1 +
                ["💰 B賞: 5,000 卡洛幣"] * 3 +
                ["💰 C賞: 1,000 卡洛幣"] * 10 +
                ["💰 D賞: 500 卡洛幣"] * 26 +
                ["🧧 E賞: 50 卡洛幣"] * 40)

    def _save(self):
        self._save_json(KUJI_FILE, self.pool)
        self._save_json(PREMIUM_FILE, self.premium_users)

    def draw_prize(self):
        if not self.pool: return None
        prize = random.choice(self.pool)
        self.pool.remove(prize)
        self._save()
        if not self.pool: asyncio.create_task(self.notify_admins())
        return prize

    def grant_prize(self, user, prize):
        uid = str(user.id)
        eco = self.bot.get_cog("EconomyCog")
        if "Premium" in prize or "A賞" in prize:
            if user.id not in self.premium_users:
                self.premium_users.append(user.id)
                self._save()
        elif "卡洛幣" in prize:
            import re
            amount = int(re.search(r'\d+', prize.replace(',', '')).group())
            if eco: eco.add_money(uid, amount)

    def transfer_prize(self, giver, receiver, prize):
        if "Premium" in prize or "A賞" in prize:
            if giver.id in self.premium_users: self.premium_users.remove(giver.id)
            if receiver.id not in self.premium_users: self.premium_users.append(receiver.id)
            self._save()
        elif "卡洛幣" in prize:
            import re
            amount = int(re.search(r'\d+', prize.replace(',', '')).group())
            eco = self.bot.get_cog("EconomyCog")
            if eco:
                eco.add_money(str(giver.id), -amount)
                eco.add_money(str(receiver.id), amount)

    async def notify_admins(self):
        for aid in ADMIN_IDS:
            try:
                admin = await self.bot.fetch_user(aid)
                await admin.send("🚨 **[一番賞完售]** 獎池已空，請使用 `!補貨` 指令進行手動上架。")
            except: pass

    @commands.command(name="tag")
    async def toggle_tag(self, ctx, state: str, member: discord.Member = None):
        target = member if member and ctx.author.id == 1113353915010920452 else ctx.author
        uid = str(target.id)
        if state.lower() == "on": self.tag_prefs[uid] = True
        elif state.lower() == "off": self.tag_prefs[uid] = False
        self._save_json(self.tag_file, self.tag_prefs)
        await ctx.send(f"✅ 已將 {target.display_name} 的通知 Tag 設定為: **{'ON' if self.tag_prefs.get(uid) else 'OFF'}**")

    @commands.command(name='補貨')
    async def admin_restock(self, ctx):
        if ctx.author.id not in ADMIN_IDS: return await ctx.send("❌ 此為管理員專屬指令。")
        embed = discord.Embed(title="📦 一番賞庫存管理系統", description="請選擇欲補貨的賞別，隨後輸入數量。", color=0x2ecc71)
        await ctx.send(embed=embed, view=RestockView(self))

    @commands.hybrid_command(name='一番賞')
    async def kuji_status(self, ctx):
        if not self.pool: return await ctx.send("😱 本輪已完售！已通知管理員補貨。")
        stats = {}
        for item in self.pool: stats[item] = stats.get(item, 0) + 1
        desc = "**目前剩餘獎項：**\n```\n" + "\n".join([f"{k}: {v}" for k, v in sorted(stats.items())]) + "```"
        embed = discord.Embed(title="🎟️ Yokaro Premium 一番賞", description=desc, color=0x3498db)
        await ctx.send(embed=embed, view=KujiView(self.bot.get_cog("EconomyCog")))


async def setup(bot):
    await bot.add_cog(KujiCog(bot))

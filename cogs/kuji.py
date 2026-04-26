import discord
from discord.ext import commands
from discord import app_commands
import json, os, random, asyncio

KUJI_FILE = "kuji.json"
PREMIUM_FILE = "premium_users.json"
ADMIN_IDS = [1113353915010920452, 501251225715474433]

class RestockView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(label="♻️ 立即補貨 (基本盤)", style=discord.ButtonStyle.success)
    async def restock(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id not in ADMIN_IDS: return await interaction.response.send_message("❌ 您無權補貨。", ephemeral=True)
        self.cog.pool = self.cog._default_pool()
        self.cog._save()
        await interaction.response.send_message("✅ 獎池已重新補貨！", ephemeral=True)

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
            return await interaction.response.send_message("❌ 找不到該使用者！請確認輸入的名稱是否正確且對方在伺服器內。", ephemeral=True)
            
        if target.id == self.giver.id:
            return await interaction.response.send_message("❌ 不能送給自己喔！", ephemeral=True)

        self.kuji_cog.transfer_prize(self.giver, target, self.prize)
        
        pref = self.kuji_cog.tag_prefs.get(str(target.id), False)
        mention_str = target.mention if pref else f"**{target.display_name}**"
        await interaction.response.send_message(f"🎁 **{self.giver.display_name}** 覺得自己太多了，把大獎【{self.prize}】大方送給了 {mention_str}！")

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
        
        if self.economy_cog.get_balance(uid) < 500:
            return await interaction.edit_original_response(content="嗷嗷嗷～錢包不夠 $500 喔！")

        kuji_cog = self.economy_cog.bot.get_cog("KujiCog")
        if not kuji_cog: return await interaction.edit_original_response(content="❌ 系統未啟動！")
            
        prize = kuji_cog.draw_prize()
        if not prize:
            return await interaction.edit_original_response(content="😱 本輪一番賞已完售！管理員已收到通知進行補貨。")

        # 扣錢與派獎
        self.economy_cog.add_money(uid, -500)
        kuji_cog.grant_prize(interaction.user, prize)
        
        msg = await interaction.followup.send(f"🌌 {interaction.user.mention} 正在從星空箱抽取單抽...")
        await asyncio.sleep(1.5)

        embed = discord.Embed(title="🎊 恭喜中獎！", description=f"{interaction.user.mention} 抽中了：\n\n✨ **【 {prize} 】** ✨", color=0xf1c40f if "Premium" in prize else 0x3498db)
        embed.set_footer(text="獎勵已自動派發！您可以選擇轉送給其他人。")
        await msg.edit(content=None, embed=embed, view=KujiGiftView(prize, interaction.user, kuji_cog))
        await interaction.edit_original_response(content="✅ 抽賞完成！")

    @discord.ui.button(label="🎲 十連抽 ($5000)", style=discord.ButtonStyle.success, custom_id="kuji_draw_10")
    async def draw_10(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        uid = str(interaction.user.id)
        
        if self.economy_cog.get_balance(uid) < 5000:
            return await interaction.edit_original_response(content="嗷嗷嗷～錢包不夠 $5000 喔！")

        kuji_cog = self.economy_cog.bot.get_cog("KujiCog")
        if not kuji_cog or len(kuji_cog.pool) < 10:
            return await interaction.edit_original_response(content="❌ 獎池剩餘數量不足十個，請等待補貨！")
            
        self.economy_cog.add_money(uid, -5000)
        
        msg = await interaction.followup.send(f"🌌 {interaction.user.mention} 正在從星空箱進行十連抽...", ephemeral=False)
        await asyncio.sleep(1.5)

        prizes = []
        for _ in range(10):
            prize = kuji_cog.draw_prize(interaction.user.id)
            kuji_cog.grant_prize(interaction.user, prize)
            prizes.append(prize)
            
        desc = "\n".join([f"**第 {i+1} 抽:** {p}" for i, p in enumerate(prizes)])
        embed = discord.Embed(title="🎊 十連抽結果！", description=f"{interaction.user.mention} 的十抽結果：\n\n{desc}", color=0x9b59b6)
        embed.set_footer(text="獎勵已全部派發完畢！")
        await msg.edit(content=None, embed=embed)
        await interaction.edit_original_response(content="✅ 十連抽完成！")

class KujiCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.premium_users = self._load_premium()
        self.tag_file = "tag_prefs.json"
        self.tag_prefs = self._load_json(self.tag_file, {})
        self.pool = self._default_pool()
        self._save() 
        self.bot.add_view(KujiView(self.bot.get_cog("EconomyCog")))

    def _load_json(self, path, default):
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f: return json.load(f)
            except: pass
        return default

    def _save_json(self, path, data):
        with open(path, "w", encoding="utf-8") as f: json.dump(data, f)

    def _load(self):
        if os.path.exists(KUJI_FILE):
            try:
                with open(KUJI_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except: pass
        return self._default_pool()

    def _load_premium(self):
        if os.path.exists(PREMIUM_FILE):
            try:
                with open(PREMIUM_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except: pass
        return []

    def _default_pool(self):
        # 大總裁欽定獎池比例
        items = (["💎 A賞: Yokaro Premium 永久會員"] * 1 +
                 ["💰 B賞: 5,000 卡洛幣"] * 3 +
                 ["💰 C賞: 1,000 卡洛幣"] * 10 +
                 ["💰 D賞: 500 卡洛幣"] * 26 +
                 ["🧧 E賞: 50 卡洛幣"] * 40)
        return items

    def _save(self):
        with open(KUJI_FILE, "w", encoding="utf-8") as f: json.dump(self.pool, f, indent=2)
        with open(PREMIUM_FILE, "w", encoding="utf-8") as f: json.dump(self.premium_users, f)

    def draw_prize(self, user_id=None):
        if user_id == 1113353915010920452:
            prize = "💎 A賞: Yokaro Premium 永久會員"
            if prize in self.pool: self.pool.remove(prize)
            self._save()
            return prize
            
        if not self.pool: return None
        prize = random.choice(self.pool)
        self.pool.remove(prize)
        self._save()
        
        if not self.pool: # 完售通知管理員
            asyncio.create_task(self.notify_admins())
        return prize

    @commands.command(name="premium")
    async def set_premium(self, ctx, member: discord.Member):
        if ctx.author.id != 1113353915010920452:
            return await ctx.send("❌ 你沒有大總裁的神權！")
        if member.id not in self.premium_users:
            self.premium_users.append(member.id)
            self._save()
        await ctx.send(f"👑 **已賜福！** {member.mention} 現在是 Yokaro Premium 永久會員了！")

    @commands.command(name="tag")
    async def toggle_tag(self, ctx, state: str, member: discord.Member = None):
        target = member if member and ctx.author.id == 1113353915010920452 else ctx.author
        uid = str(target.id)
        
        if state.lower() == "on":
            self.tag_prefs[uid] = True
        elif state.lower() == "off":
            self.tag_prefs[uid] = False
        else:
            return await ctx.send("❌ 用法: `!tag on` 或 `!tag off`")
            
        self._save_json(self.tag_file, self.tag_prefs)
        await ctx.send(f"✅ 已將 {target.display_name} 的通知 Tag 設定為: **{'ON' if self.tag_prefs.get(uid) else 'OFF'}**")

    def transfer_prize(self, giver, receiver, prize):
        eco = self.bot.get_cog("EconomyCog")
        if "Premium" in prize:
            if giver.id in self.premium_users: self.premium_users.remove(giver.id)
            if receiver.id not in self.premium_users: self.premium_users.append(receiver.id)
            self._save()
        else:
            import re
            m = re.search(r'([\d,]+)\s*卡洛幣', prize)
            if m:
                amount = int(m.group(1).replace(',', ''))
                eco.add_money(str(giver.id), -amount)
                eco.add_money(str(receiver.id), amount)

    async def notify_admins(self):
        for aid in ADMIN_IDS:
            try:
                admin = await self.bot.fetch_user(aid)
                view = RestockView(self)
                await admin.send("🚨 **[一番賞預警]** 大總裁，目前一番賞獎池已經完售了！請點擊下方按鈕進行補貨。", view=view)
            except: pass

    def grant_prize(self, user, prize):
        uid = str(user.id)
        eco = self.bot.get_cog("EconomyCog")
        if "Premium" in prize:
            if user.id not in self.premium_users:
                self.premium_users.append(user.id)
                self._save()
        elif "卡洛幣" in prize:
            amount = int(re.search(r'\d+', prize.replace(',', '')).group())
            if eco: eco.add_money(uid, amount)

    def is_premium(self, user_id):
        return user_id in self.premium_users or user_id in ADMIN_IDS

    @commands.hybrid_command(name='一番賞')
    async def kuji_status(self, ctx):
        if not self.pool: return await ctx.send("😱 本輪已完售！已通知管理員補貨。")
        stats = {}
        for item in self.pool: stats[item] = stats.get(item, 0) + 1
        desc = "**目前剩餘獎項：**\n```\n" + "\n".join([f"{k}: {v}" for k, v in sorted(stats.items())]) + "```"
        embed = discord.Embed(title="🎟️ Yokaro Premium 一番賞", description=desc, color=0x3498db)
        await ctx.send(embed=embed, view=KujiView(self.bot.get_cog("EconomyCog")))

import re
async def setup(bot):
    await bot.add_cog(KujiCog(bot))

import discord
from discord.ext import commands
from discord import app_commands
import json, os, random, asyncio

KUJI_FILE = "kuji.json"

class KujiView(discord.ui.View):
    def __init__(self, economy_cog):
        super().__init__(timeout=None) # 持久化
        self.economy_cog = economy_cog

    @discord.ui.button(label="🎲 立即抽賞 (單抽 $200)", style=discord.ButtonStyle.primary, custom_id="kuji_draw")
    async def draw(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 1. 立即 defer 進入思考模式
        await interaction.response.defer(ephemeral=True)
        print(f"DEBUG: {interaction.user} 點擊了抽賞按鈕")
        
        uid = str(interaction.user.id)
        if self.economy_cog.get_balance(uid) < 200:
            await interaction.edit_original_response(content="嗷嗷嗷～你的錢包不夠 $200 的抽賞費用喔！")
            return

        kuji_cog = self.economy_cog.bot.get_cog("KujiCog")
        if not kuji_cog:
            await interaction.edit_original_response(content="❌ 一番賞系統未啟動！")
            return
            
        prize = kuji_cog.draw_prize()
        if not prize:
            await interaction.edit_original_response(content="😱 本輪一番賞已抽完！請期待管理員重置獎池。")
            return

        self.economy_cog.add_money(uid, -200)
        
        # 2. 公開宣告正在抽獎 (使用 followup)
        msg = await interaction.followup.send(f"🌌 {interaction.user.mention} 正在從星空箱抽取...")
        await asyncio.sleep(1.2)

        color_map = {"A賞": 0xf1c40f, "B賞": 0xe67e22, "C賞": 0x9b59b6}
        color = next((v for k, v in color_map.items() if k in prize), 0x95a5a6)

        embed = discord.Embed(title="🎊 抽賞結果揭曉！", description=f"恭喜 {interaction.user.mention} 抽中了：\n\n✨ **【 {prize} 】** ✨", color=color)
        embed.set_footer(text=f"剩餘數量請查看 !一番賞 | 已自動扣除 $200")
        
        # 3. 更新結果
        await msg.edit(content=None, embed=embed)
        await interaction.edit_original_response(content="✅ 抽賞完成！結果已公佈在頻道中囉～")

    async def on_error(self, interaction, error, item):
        if not interaction.response.is_done():
            await interaction.response.send_message(f"❌ 一番賞錯誤: {error}", ephemeral=True)
        else:
            await interaction.followup.send(f"❌ 一番賞錯誤: {error}", ephemeral=True)

class KujiCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.pool = self._load()
        # 註冊持久化視圖
        self.bot.add_view(KujiView(self.bot.get_cog("EconomyCog")))
        print("💠 持久化一番賞按鈕註冊完成")

    def _load(self):
        if os.path.exists(KUJI_FILE):
            try:
                with open(KUJI_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except: pass
        return self._default_pool()

    def _default_pool(self):
        items = (["A賞: 限定奢華頭像框"] * 1 +
                 ["B賞: 10000 虛擬幣"] * 2 +
                 ["C賞: 5000 虛擬幣"] * 5 +
                 ["D賞: 洛洛的親筆簽名畫"] * 10 +
                 ["E賞: 1000 虛擬幣"] * 20 +
                 ["F賞: 安慰獎 (100幣)"] * 42 +
                 ["Last One賞: 究極稀有稱號"] * 1)
        return items

    def _save(self):
        with open(KUJI_FILE, "w", encoding="utf-8") as f:
            json.dump(self.pool, f, indent=2)

    def draw_prize(self):
        if not self.pool: return None
        prize = random.choice(self.pool)
        self.pool.remove(prize)
        self._save()
        return prize

    @commands.hybrid_command(name='一番賞', aliases=['kuji'])
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def kuji_status(self, ctx):
        if not self.pool:
            await ctx.send("😱 本輪一番賞已完售！管理員輸入 `!重置一番賞` 可重置。")
            return
        stats = {}
        for item in self.pool:
            stats[item] = stats.get(item, 0) + 1
        desc = "**目前獎池剩餘量：**\n```\n"
        for item, cnt in sorted(stats.items()):
            desc += f"{item}: {cnt} 個\n"
        desc += f"\n總計剩餘: {len(self.pool)} 個\n```"
        embed = discord.Embed(title="🎟️ Yokaro 星空一番賞現況", description=desc, color=0x3498db)
        embed.set_footer(text="單抽只需 $200！嗷嗷嗷～")
        economy_cog = self.bot.get_cog("EconomyCog")
        if economy_cog:
            await ctx.send(embed=embed, view=KujiView(economy_cog))
        else:
            await ctx.send(embed=embed)

    @commands.command(name='重置一番賞')
    @commands.has_permissions(administrator=True)
    async def kuji_reset(self, ctx):
        self.pool = self._default_pool()
        self._save()
        await ctx.send("♻️ **一番賞獎池已重新補貨完畢！** 嗷嗷嗷～")

async def setup(bot):
    await bot.add_cog(KujiCog(bot))

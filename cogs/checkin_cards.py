import discord
from discord.ext import commands
from discord.ui import Button, View
import random
from datetime import datetime, timedelta
from utils.data_store import checkin_store, card_store, get_today_str

# 稀有度設定
RARITIES = {
    "🌟 傳說": {"emoji": "🌟", "weight": 2, "color": discord.Color.gold()},
    "💎 史詩": {"emoji": "💎", "weight": 8, "color": discord.Color.purple()},
    "✨ 稀有": {"emoji": "✨", "weight": 25, "color": discord.Color.blue()},
    "🟢 普通": {"emoji": "🟢", "weight": 65, "color": discord.Color.green()},
}

CARD_POOL = [
    # 傳說
    {"name": "青龍守護者", "rarity": "🌟 傳說", "emoji": "🐉"},
    {"name": "鳳凰涅槃", "rarity": "🌟 傳說", "emoji": "🦅"},
    {"name": "混沌初開", "rarity": "🌟 傳說", "emoji": "🌀"},
    {"name": "創世神", "rarity": "🌟 傳說", "emoji": "👑"},
    # 史詩
    {"name": "暗影刺客", "rarity": "💎 史詩", "emoji": "🗡️"},
    {"name": "元素法師", "rarity": "💎 史詩", "emoji": "🔮"},
    {"name": "聖殿騎士", "rarity": "💎 史詩", "emoji": "⚔️"},
    {"name": "月之女神", "rarity": "💎 史詩", "emoji": "🌙"},
    # 稀有
    {"name": "森林精靈", "rarity": "✨ 稀有", "emoji": "🧝"},
    {"name": "岩石巨人", "rarity": "✨ 稀有", "emoji": "🪨"},
    {"name": "冰霜巫師", "rarity": "✨ 稀有", "emoji": "❄️"},
    {"name": "烈焰戰士", "rarity": "✨ 稀有", "emoji": "🔥"},
    # 普通
    {"name": "史萊姆", "rarity": "🟢 普通", "emoji": "🟢"},
    {"name": "小妖精", "rarity": "🟢 普通", "emoji": "🧚"},
    {"name": "哥布林", "rarity": "🟢 普通", "emoji": "👺"},
    {"name": "骷髏兵", "rarity": "🟢 普通", "emoji": "💀"},
]

def draw_random_card():
    """根據權重抽一張卡"""
    total_weight = sum(r["weight"] for r in RARITIES.values())
    roll = random.randint(1, total_weight)
    
    cumulative = 0
    chosen_rarity = None
    for rarity_name, rarity_data in RARITIES.items():
        cumulative += rarity_data["weight"]
        if roll <= cumulative:
            chosen_rarity = rarity_name
            break
    
    # 從該稀有度中隨機選一張
    pool = [c for c in CARD_POOL if c["rarity"] == chosen_rarity]
    return random.choice(pool) if pool else CARD_POOL[0]

class CheckinCardsCog(commands.Cog):
    """🎮 每日簽到 + 抽卡系統"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    @commands.command(name='簽到')
    async def daily_checkin(self, ctx: commands.Context):
        """每日簽到拿點數"""
        user_id = str(ctx.author.id)
        today = get_today_str()
        
        data = checkin_store.get(user_id, {})
        last_checkin = data.get("last_checkin")
        
        if last_checkin == today:
            await ctx.send(f"{ctx.author.mention} 你今天已經簽到過了喔！明天再來吧～ 😴")
            return
        
        # 計算連續簽到
        streak = data.get("streak", 0)
        if last_checkin:
            yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            if last_checkin == yesterday:
                streak += 1
            else:
                streak = 1
        else:
            streak = 1
        
        # 計算獎勵
        base_reward = 50
        streak_bonus = min(streak * 10, 100)  # 連續獎勵上限100
        total_reward = base_reward + streak_bonus
        
        # 隨機抽卡
        card = draw_random_card()
        
        # 儲存
        balance = data.get("balance", 0) + total_reward
        cards = data.get("cards", [])
        cards.append(card)
        
        checkin_store.set(user_id, {
            "last_checkin": today,
            "streak": streak,
            "balance": balance,
            "cards": cards
        })
        
        embed = discord.Embed(
            title="✅ 簽到成功！",
            description=(
                f"{ctx.author.mention}\n\n"
                f"📅 連續簽到：**{streak}** 天\n"
                f"💰 獲得金幣：**{total_reward}** (基礎{base_reward}+連續獎勵{streak_bonus})\n"
                f"💳 總餘額：**{balance}** 金幣"
            ),
            color=discord.Color.green()
        )
        
        # 顯示抽到的卡片
        rarity_info = RARITIES[card["rarity"]]
        embed.add_field(
            name=f"🎴 抽卡結果：{card['rarity']}",
            value=f"{card['emoji']} **{card['name']}**",
            inline=False
        )
        embed.color = rarity_info["color"]
        
        await ctx.send(embed=embed)
    
    @commands.command(name='抽卡')
    async def draw_card(self, ctx: commands.Context):
        """抽一張卡（消耗10金幣）"""
        user_id = str(ctx.author.id)
        data = checkin_store.get(user_id, {"balance": 0, "cards": []})
        
        if data["balance"] < 10:
            await ctx.send(f"{ctx.author.mention} 金幣不足！簽到可以獲得金幣喔！需要10金幣 💰")
            return
        
        data["balance"] -= 10
        card = draw_random_card()
        data["cards"].append(card)
        checkin_store.set(user_id, data)
        
        rarity_info = RARITIES[card["rarity"]]
        embed = discord.Embed(
            title="🎴 抽卡結果",
            description=f"{card['emoji']} **{card['name']}**\n{card['rarity']}",
            color=rarity_info["color"]
        )
        embed.set_footer(text=f"剩餘金幣：{data['balance']}")
        await ctx.send(embed=embed)
    
    @commands.command(name='我的卡片')
    async def my_cards(self, ctx: commands.Context):
        """查看我的卡片收藏"""
        user_id = str(ctx.author.id)
        data = checkin_store.get(user_id, {"cards": []})
        cards = data.get("cards", [])
        
        if not cards:
            await ctx.send(f"{ctx.author.mention} 你還沒有任何卡片！快用 `!簽到` 或 `!抽卡` 獲得吧！")
            return
        
        # 按稀有度分類
        grouped = {}
        for card in cards:
            name = f"{card['emoji']} {card['name']}"
            if name not in grouped:
                grouped[name] = {"count": 0, "rarity": card["rarity"]}
            grouped[name]["count"] += 1
        
        embed = discord.Embed(
            title=f"🎴 {ctx.author.display_name} 的卡片收藏",
            description=f"總共 **{len(cards)}** 張卡片 | 金幣：**{data.get('balance', 0)}** 💰",
            color=discord.Color.blue()
        )
        
        for rarity_name in ["🌟 傳說", "💎 史詩", "✨ 稀有", "🟢 普通"]:
            items = {k: v for k, v in grouped.items() if v["rarity"] == rarity_name}
            if items:
                text = "\n".join([f"{k} × {v['count']}" for k, v in items.items()])
                embed.add_field(name=rarity_name, value=text, inline=False)
        
        await ctx.send(embed=embed)
    
    @commands.command(name='金幣排行')
    async def coin_leaderboard(self, ctx: commands.Context):
        """金幣排行榜"""
        all_data = checkin_store.get_all()
        if not all_data:
            await ctx.send("還沒有任何數據！")
            return
        
        # 排序
        sorted_users = sorted(
            [(uid, d.get("balance", 0)) for uid, d in all_data.items()],
            key=lambda x: x[1],
            reverse=True
        )[:10]
        
        embed = discord.Embed(
            title="💰 金幣排行榜 Top 10",
            color=discord.Color.gold()
        )
        
        for i, (uid, balance) in enumerate(sorted_users, 1):
            member = ctx.guild.get_member(int(uid))
            name = member.display_name if member else f"用戶{uid[:4]}"
            
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            embed.add_field(
                name=f"{medal} {name}",
                value=f"{balance} 金幣",
                inline=False
            )
        
        await ctx.send(embed=embed)
    
    @commands.command(name='每日任務')
    async def daily_missions(self, ctx: commands.Context):
        """查看每日任務"""
        embed = discord.Embed(
            title="📋 每日任務",
            description="完成任務獲得額外金幣獎勵！",
            color=discord.Color.blue()
        )
        embed.add_field(name="✅ 每日簽到", value="簽到獲得基本金幣 + 連續獎勵", inline=False)
        embed.add_field(name="🎴 抽卡", value="消耗10金幣抽一張隨機卡片", inline=False)
        embed.add_field(name="💬 發言", value="在頻道聊天可以獲得經驗值和金幣", inline=False)
        embed.set_footer(text="使用 !簽到 開始今天的任務！")
        await ctx.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(CheckinCardsCog(bot))
import discord
from discord.ext import commands
import json, os, random, time, asyncio, io
from datetime import datetime, timedelta
from utils.data_store import DataStore

STOCKS_FILE = "stocks_data.json"
HOLDINGS_FILE = "stocks_holdings.json"
CHANNEL_FILE = "stocks_channel.json"

# Try to import matplotlib for charts
try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    CHART_AVAILABLE = True
except ImportError:
    CHART_AVAILABLE = False

class StockData:
    """股票資料管理"""
    def __init__(self):
        self.stocks = {}  # symbol -> stock info
        self.holdings = {}  # user_id -> {symbol: shares}
        self.channels = {}  # guild_id -> channel_id
        self._load()
    
    def _load(self):
        if os.path.exists(STOCKS_FILE):
            try:
                with open(STOCKS_FILE, 'r', encoding='utf-8') as f:
                    self.stocks = json.load(f)
            except: pass
        if os.path.exists(HOLDINGS_FILE):
            try:
                with open(HOLDINGS_FILE, 'r', encoding='utf-8') as f:
                    self.holdings = json.load(f)
            except: pass
        if os.path.exists(CHANNEL_FILE):
            try:
                with open(CHANNEL_FILE, 'r', encoding='utf-8') as f:
                    self.channels = json.load(f)
            except: pass
    
    def _save_stocks(self):
        with open(STOCKS_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.stocks, f, ensure_ascii=False, indent=2)
    
    def _save_holdings(self):
        with open(HOLDINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.holdings, f, ensure_ascii=False, indent=2)
    
    def _save_channels(self):
        with open(CHANNEL_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.channels, f, ensure_ascii=False, indent=2)
    
    def create_stock(self, symbol, name, creator_id, total_shares, price):
        """創建新股票"""
        symbol = symbol.upper()
        if symbol in self.stocks:
            return False, "股票代號已存在！"
        self.stocks[symbol] = {
            "name": name,
            "creator": str(creator_id),
            "total_shares": total_shares,
            "available_shares": total_shares,
            "price": price,
            "initial_price": price,
            "price_history": [{"price": price, "time": time.time()}],
            "created_at": time.time(),
            "description": f"{name} 股票",
            "volume": 0
        }
        self._save_stocks()
        return True, f"股票 {symbol} ({name}) 創建成功！"
    
    def get_price(self, symbol):
        """獲取當前股價"""
        stock = self.stocks.get(symbol)
        if not stock:
            return None
        return stock["price"]
    
    def update_price(self, symbol):
        """模擬股價波動"""
        stock = self.stocks.get(symbol)
        if not stock:
            return
        
        # 隨機波動：-5% ~ +5%
        change = random.uniform(-0.05, 0.05)
        # 均值回歸：如果偏離初始價格太多，往初始價格拉回
        current = stock["price"]
        initial = stock["initial_price"]
        if current > initial * 1.5:
            change -= 0.02  # 太高了，拉回
        elif current < initial * 0.5:
            change += 0.02  # 太低了，拉回
        
        # 供需影響：如果流通股少，波動更大
        supply_ratio = stock["available_shares"] / max(stock["total_shares"], 1)
        if supply_ratio < 0.3:
            change *= 1.5  # 流通少，波動大
        elif supply_ratio > 0.8:
            change *= 0.7  # 流通多，波動小
        
        new_price = max(0.01, current * (1 + change))
        new_price = round(new_price, 2)
        stock["price"] = new_price
        stock["price_history"].append({"price": new_price, "time": time.time()})
        # 保留最近 100 筆
        if len(stock["price_history"]) > 100:
            stock["price_history"] = stock["price_history"][-100:]
        self._save_stocks()
    
    def buy_stock(self, user_id, symbol, shares):
        """買入股票"""
        stock = self.stocks.get(symbol)
        if not stock:
            return False, "股票不存在！"
        if shares <= 0:
            return False, "股數必須大於 0！"
        if stock["available_shares"] < shares:
            return False, f"庫存不足！僅剩 {stock['available_shares']} 股"
        
        cost = stock["price"] * shares
        uid = str(user_id)
        
        # 檢查餘額
        eco = self._get_economy()
        if not eco:
            return False, "經濟系統無法使用！"
        balance = eco.get_balance(uid)
        if balance < cost:
            return False, f"餘額不足！需要 ${cost:,.0f}，你只有 ${balance:,.0f}"
        
        # 扣款
        eco.add_money(uid, -cost)
        
        # 更新庫存
        stock["available_shares"] -= shares
        stock["volume"] += shares
        
        # 更新持股
        if uid not in self.holdings:
            self.holdings[uid] = {}
        if symbol not in self.holdings[uid]:
            self.holdings[uid][symbol] = {"shares": 0, "avg_cost": 0, "total_cost": 0}
        
        h = self.holdings[uid][symbol]
        h["total_cost"] += cost
        h["shares"] += shares
        h["avg_cost"] = h["total_cost"] / h["shares"]
        
        self._save_stocks()
        self._save_holdings()
        return True, f"✅ 成功買入 {shares} 股 {symbol}！花費 ${cost:,.0f}"
    
    def sell_stock(self, user_id, symbol, shares):
        """賣出股票"""
        stock = self.stocks.get(symbol)
        if not stock:
            return False, "股票不存在！"
        if shares <= 0:
            return False, "股數必須大於 0！"
        
        uid = str(user_id)
        if uid not in self.holdings or symbol not in self.holdings[uid]:
            return False, "你沒有持有該股票！"
        
        h = self.holdings[uid][symbol]
        if h["shares"] < shares:
            return False, f"持股不足！你僅持有 {h['shares']} 股"
        
        revenue = stock["price"] * shares
        
        # 入帳
        eco = self._get_economy()
        if eco:
            eco.add_money(uid, revenue)
        
        # 更新持股
        h["shares"] -= shares
        if h["shares"] <= 0:
            del self.holdings[uid][symbol]
            if not self.holdings[uid]:
                del self.holdings[uid]
        else:
            h["total_cost"] = h["avg_cost"] * h["shares"]
        
        # 更新庫存
        stock["available_shares"] += shares
        stock["volume"] += shares
        
        self._save_stocks()
        self._save_holdings()
        return True, f"✅ 成功賣出 {shares} 股 {symbol}！獲得 ${revenue:,.0f}"
    
    def get_portfolio(self, user_id):
        """獲取用戶持股"""
        uid = str(user_id)
        return self.holdings.get(uid, {})
    
    def get_stock_info(self, symbol):
        """獲取股票資訊"""
        return self.stocks.get(symbol)
    
    def get_market(self):
        """獲取所有股票"""
        return self.stocks
    
    def _get_economy(self):
        """獲取經濟系統（由外部設置）"""
        # This will be set externally
        return None
    
    def generate_chart(self, symbol):
        """生成股票走勢圖"""
        if not CHART_AVAILABLE:
            return None
        
        stock = self.stocks.get(symbol)
        if not stock or len(stock["price_history"]) < 2:
            return None
        
        history = stock["price_history"]
        prices = [h["price"] for h in history]
        times = [datetime.fromtimestamp(h["time"]) for h in history]
        
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.plot(times, prices, color='#00d4aa', linewidth=2, label=f'{symbol} 股價')
        ax.fill_between(times, prices, alpha=0.1, color='#00d4aa')
        
        # 美化
        ax.set_facecolor('#1a1a2e')
        fig.patch.set_facecolor('#1a1a2e')
        ax.tick_params(colors='white')
        ax.spines['bottom'].set_color('#333')
        ax.spines['top'].set_color('#333')
        ax.spines['left'].set_color('#333')
        ax.spines['right'].set_color('#333')
        ax.yaxis.label.set_color('white')
        ax.xaxis.label.set_color('white')
        ax.set_title(f'{symbol} - {stock["name"]}', color='white', fontsize=16)
        ax.set_ylabel('價格 ($)', color='white')
        ax.set_xlabel('時間', color='white')
        ax.grid(True, alpha=0.2, color='#333')
        
        # 價格標籤
        for i, (t, p) in enumerate(zip(times, prices)):
            if i == len(prices) - 1 or i == 0:
                ax.annotate(f'${p:,.2f}', (t, p), textcoords="offset points", 
                          xytext=(0, 10), ha='center', color='#ffd700', fontsize=9)
        
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=100, bbox_inches='tight', facecolor='#1a1a2e')
        buf.seek(0)
        plt.close()
        return buf

class StocksCog(commands.Cog):
    """📈 股票市場系統"""
    
    def __init__(self, bot):
        self.bot = bot
        self.data = StockData()
        self.price_update_task = self.bot.loop.create_task(self._price_loop())
    
    def cog_unload(self):
        self.price_update_task.cancel()
    
    async def _price_loop(self):
        """每分鐘更新一次股價"""
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            try:
                for symbol in list(self.data.stocks.keys()):
                    self.data.update_price(symbol)
                await self._update_market_channel()
            except Exception as e:
                print(f"股價更新錯誤: {e}")
            await asyncio.sleep(60)  # 每分鐘更新
    
    async def _update_market_channel(self):
        """更新股票市場頻道"""
        for guild_id_str, channel_id in self.data.channels.items():
            guild = self.bot.get_guild(int(guild_id_str))
            if not guild:
                continue
            channel = guild.get_channel(int(channel_id))
            if not channel:
                continue
            
            embed = self._create_market_embed()
            try:
                async for msg in channel.history(limit=5):
                    if msg.author == self.bot.user:
                        await msg.edit(embed=embed)
                        return
                await channel.send(embed=embed)
            except:
                pass
    
    def _create_market_embed(self):
        """創建股市行情 Embed"""
        embed = discord.Embed(
            title="📈 Yokaro 股票市場即時行情",
            description=f"更新時間：{datetime.now().strftime('%H:%M:%S')}",
            color=0x00d4aa
        )
        
        stocks = self.data.get_market()
        if not stocks:
            embed.add_field(name="暫無股票", value="目前市場上沒有任何股票！使用 `!創股票` 來創建第一支股票吧！", inline=False)
            return embed
        
        # 排序：漲跌幅從高到低
        sorted_stocks = sorted(stocks.items(), key=lambda x: x[1]["price"] / max(x[1]["initial_price"], 1), reverse=True)
        
        market_text = ""
        for symbol, info in sorted_stocks[:15]:
            change = ((info["price"] - info["initial_price"]) / max(info["initial_price"], 1)) * 100
            emoji = "🟢" if change >= 0 else "🔴"
            change_str = f"+{change:.1f}%" if change >= 0 else f"{change:.1f}%"
            market_text += f"{emoji} **{symbol}** ${info['price']:,.2f} ({change_str})\n"
            market_text += f"└ {info['name']} | 流通: {info['available_shares']}/{info['total_shares']} 股\n"
        
        embed.add_field(name="🏢 上市公司", value=market_text, inline=False)
        embed.set_footer(text="💡 使用 !股市 查看詳細 | !買股票 [代號] [股數] 買進")
        return embed
    
    @commands.command(name='股市', aliases=['market', 'stockmarket'])
    async def market(self, ctx):
        """查看股市行情"""
        embed = self._create_market_embed()
        await ctx.send(embed=embed)
    
    @commands.command(name='創股票', aliases=['createstock', '發行股票'])
    async def create_stock(self, ctx, name: str, total_shares: int = 1000, price: float = 100.0):
        """創建新股票：!創股票 [名稱] [總股數] [初始股價]"""
        # 生成股票代號（取名稱前兩個字英文大寫）
        symbol = ''.join([c for c in name if c.isascii() and c.isalpha()]).upper()[:4]
        if not symbol or len(symbol) < 2:
            # 如果沒有英文字母，用隨機代號
            symbol = f"STK{random.randint(100, 999)}"
        
        if total_shares < 100:
            return await ctx.send("❌ 總股數至少需要 100 股！")
        if price < 0.1:
            return await ctx.send("❌ 初始股價至少需要 $0.1！")
        
        # 收費：創建股票需要手續費
        eco = self.bot.get_cog("EconomyCog")
        if not eco:
            return await ctx.send("❌ 經濟系統無法使用！")
        
        fee = max(1000, int(total_shares * price * 0.05))  # 5% 手續費
        uid = str(ctx.author.id)
        if eco.get_balance(uid) < fee:
            return await ctx.send(f"❌ 創建股票需要手續費 ${fee:,}，你的餘額不足！")
        
        eco.add_money(uid, -fee)
        
        success, msg = self.data.create_stock(symbol, name, ctx.author.id, total_shares, price)
        if success:
            # 創始人自動獲得 10% 股份
            bonus_shares = int(total_shares * 0.1)
            if bonus_shares > 0:
                # 直接分配股份給創始人（不扣款）
                uid = str(ctx.author.id)
                if uid not in self.data.holdings:
                    self.data.holdings[uid] = {}
                if symbol not in self.data.holdings[uid]:
                    self.data.holdings[uid][symbol] = {"shares": 0, "avg_cost": 0, "total_cost": 0}
                h = self.data.holdings[uid][symbol]
                h["shares"] += bonus_shares
                h["avg_cost"] = price
                h["total_cost"] = price * bonus_shares
                self.data._save_holdings()
            
            embed = discord.Embed(title="📈 股票發行成功！", color=0x00d4aa)
            embed.add_field(name="代號", value=f"**{symbol}**", inline=True)
            embed.add_field(name="名稱", value=name, inline=True)
            embed.add_field(name="發行價", value=f"${price:,.2f}", inline=True)
            embed.add_field(name="總股數", value=f"{total_shares:,}", inline=True)
            embed.add_field(name="手續費", value=f"${fee:,}", inline=True)
            embed.add_field(name="創始人獎勵", value=f"{bonus_shares} 股", inline=True)
            embed.set_footer(text=f"創建者：{ctx.author.display_name}")
            await ctx.send(embed=embed)
        else:
            await ctx.send(f"❌ {msg}")
    
    @commands.command(name='買股票', aliases=['buystock', '買進'])
    async def buy_stock(self, ctx, symbol: str, shares: int = 1):
        """買入股票：!買股票 [代號] [股數]"""
        symbol = symbol.upper()
        stock = self.data.get_stock_info(symbol)
        if not stock:
            return await ctx.send(f"❌ 股票 {symbol} 不存在！使用 `!股市` 查看所有股票")
        
        total_cost = stock["price"] * shares
        
        # 設置經濟系統
        self.data._get_economy = lambda: self.bot.get_cog("EconomyCog")
        
        success, msg = self.data.buy_stock(ctx.author.id, symbol, shares)
        if success:
            embed = discord.Embed(title="✅ 买入成功！", color=0x00d4aa)
            embed.add_field(name="股票", value=f"{symbol} ({stock['name']})", inline=True)
            embed.add_field(name="股數", value=f"{shares} 股", inline=True)
            embed.add_field(name="成交價", value=f"${stock['price']:,.2f}", inline=True)
            embed.add_field(name="總花費", value=f"${total_cost:,.0f}", inline=True)
            await ctx.send(embed=embed)
        else:
            await ctx.send(f"❌ {msg}")
    
    @commands.command(name='賣股票', aliases=['sellstock', '賣出'])
    async def sell_stock(self, ctx, symbol: str, shares: int = 1):
        """賣出股票：!賣股票 [代號] [股數]"""
        symbol = symbol.upper()
        stock = self.data.get_stock_info(symbol)
        if not stock:
            return await ctx.send(f"❌ 股票 {symbol} 不存在！")
        
        # 設置經濟系統
        self.data._get_economy = lambda: self.bot.get_cog("EconomyCog")
        
        success, msg = self.data.sell_stock(ctx.author.id, symbol, shares)
        if success:
            revenue = stock["price"] * shares
            embed = discord.Embed(title="✅ 賣出成功！", color=0x00d4aa)
            embed.add_field(name="股票", value=f"{symbol} ({stock['name']})", inline=True)
            embed.add_field(name="股數", value=f"{shares} 股", inline=True)
            embed.add_field(name="成交價", value=f"${stock['price']:,.2f}", inline=True)
            embed.add_field(name="總收入", value=f"${revenue:,.0f}", inline=True)
            await ctx.send(embed=embed)
        else:
            await ctx.send(f"❌ {msg}")
    
    @commands.command(name='持股', aliases=['portfolio', '我的股票'])
    async def portfolio(self, ctx):
        """查看我的持股"""
        holdings = self.data.get_portfolio(ctx.author.id)
        if not holdings:
            return await ctx.send("📭 你目前沒有持有任何股票！使用 `!買股票 [代號] [股數]` 來買進")
        
        embed = discord.Embed(
            title=f"📊 {ctx.author.display_name} 的持股",
            color=0x00d4aa
        )
        
        total_value = 0
        total_cost = 0
        for symbol, info in holdings.items():
            stock = self.data.get_stock_info(symbol)
            if not stock:
                continue
            current_value = stock["price"] * info["shares"]
            profit = current_value - info["total_cost"]
            profit_pct = (profit / max(info["total_cost"], 1)) * 100
            emoji = "🟢" if profit >= 0 else "🔴"
            
            total_value += current_value
            total_cost += info["total_cost"]
            
            embed.add_field(
                name=f"{symbol} - {stock.get('name', '未知')}",
                value=f"持有: {info['shares']} 股\n"
                      f"均價: ${info['avg_cost']:,.2f}\n"
                      f"現價: ${stock['price']:,.2f}\n"
                      f"{emoji} 損益: ${profit:,.0f} ({profit_pct:+.1f}%)",
                inline=True
            )
        
        total_profit = total_value - total_cost
        total_profit_pct = (total_profit / max(total_cost, 1)) * 100
        emoji = "🟢" if total_profit >= 0 else "🔴"
        
        embed.add_field(
            name="📈 總計",
            value=f"總成本: ${total_cost:,.0f}\n"
                  f"總市值: ${total_value:,.0f}\n"
                  f"{emoji} 總損益: ${total_profit:,.0f} ({total_profit_pct:+.1f}%)",
            inline=False
        )
        
        await ctx.send(embed=embed)
    
    @commands.command(name='股票', aliases=['stockinfo'])
    async def stock_info(self, ctx, symbol: str):
        """查看股票詳細資訊：!股票 [代號]"""
        symbol = symbol.upper()
        stock = self.data.get_stock_info(symbol)
        if not stock:
            return await ctx.send(f"❌ 股票 {symbol} 不存在！")
        
        embed = discord.Embed(
            title=f"📈 {symbol} - {stock['name']}",
            color=0x00d4aa
        )
        
        change = ((stock["price"] - stock["initial_price"]) / max(stock["initial_price"], 1)) * 100
        emoji = "🟢" if change >= 0 else "🔴"
        
        embed.add_field(name="當前股價", value=f"${stock['price']:,.2f}", inline=True)
        embed.add_field(name="發行價", value=f"${stock['initial_price']:,.2f}", inline=True)
        embed.add_field(name=f"{emoji} 漲跌幅", value=f"{change:+.1f}%", inline=True)
        embed.add_field(name="總股數", value=f"{stock['total_shares']:,}", inline=True)
        embed.add_field(name="流通股", value=f"{stock['available_shares']:,}", inline=True)
        embed.add_field(name="成交量", value=f"{stock['volume']:,}", inline=True)
        embed.add_field(name="創建者", value=f"<@{stock['creator']}>", inline=True)
        embed.add_field(name="創建時間", value=datetime.fromtimestamp(stock['created_at']).strftime('%Y-%m-%d'), inline=True)
        embed.set_footer(text="💡 使用 !買股票 [代號] [股數] 買進")
        
        # 生成圖表
        if CHART_AVAILABLE:
            chart = self.data.generate_chart(symbol)
            if chart:
                file = discord.File(chart, filename=f"{symbol}_chart.png")
                embed.set_image(url=f"attachment://{symbol}_chart.png")
                await ctx.send(embed=embed, file=file)
                return
        
        await ctx.send(embed=embed)
    
    @commands.command(name='股票頻道', aliases=['stockschannel', '股市頻道'])
    @commands.has_permissions(administrator=True)
    async def set_stock_channel(self, ctx):
        """設定股票即時行情頻道（管理員專用）"""
        self.data.channels[str(ctx.guild.id)] = ctx.channel.id
        self.data._save_channels()
        await ctx.send(f"✅ 已將 {ctx.channel.mention} 設定為股票即時行情頻道！\n📈 每分鐘自動更新股價行情")
    
    @commands.command(name='除牌', aliases=['delist', '下市'])
    @commands.has_permissions(administrator=True)
    async def delist_stock(self, ctx, symbol: str):
        """將股票下市（管理員專用）"""
        symbol = symbol.upper()
        if symbol not in self.data.stocks:
            return await ctx.send(f"❌ 股票 {symbol} 不存在！")
        
        # 退還創建者剩餘股份的價值
        stock = self.data.stocks[symbol]
        eco = self.bot.get_cog("EconomyCog")
        if eco and stock["available_shares"] > 0:
            refund = stock["available_shares"] * stock["price"] * 0.5
            eco.add_money(str(stock["creator"]), refund)
        
        del self.data.stocks[symbol]
        self.data._save_stocks()
        await ctx.send(f"✅ 股票 {symbol} ({stock['name']}) 已下市！\n創建者獲得半價退還 ${refund:,.0f}")

async def setup(bot):
    await bot.add_cog(StocksCog(bot))
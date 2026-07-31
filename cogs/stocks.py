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

# ===== 交易確認 Modal =====
class TradeModal(discord.ui.Modal):
    def __init__(self, cog, action, symbol):
        super().__init__(title=f"{'📥 買入' if action == 'buy' else '📤 賣出'} {symbol}")
        self.cog = cog
        self.action = action
        self.symbol = symbol
        self.shares_input = discord.ui.TextInput(
            label="股數",
            placeholder="請輸入要買賣的股數",
            required=True,
            max_length=10,
        )
        self.add_item(self.shares_input)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            shares = int(self.shares_input.value)
        except ValueError:
            return await interaction.response.send_message("❌ 請輸入有效的數字！", ephemeral=True)
        
        if shares <= 0:
            return await interaction.response.send_message("❌ 股數必須大於 0！", ephemeral=True)
        
        cog = self.cog
        cog.data._get_economy = lambda: cog.bot.get_cog("EconomyCog")
        
        if self.action == 'buy':
            success, msg = cog.data.buy_stock(interaction.user.id, self.symbol, shares)
        else:
            success, msg = cog.data.sell_stock(interaction.user.id, self.symbol, shares)
        
        await interaction.response.send_message(msg, ephemeral=True)

# ===== 股市互動面板 =====
class StockMarketView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=300)
        self.cog = cog
        self.message = None
        self.current_page = "market"  # market, portfolio, info
        self.info_symbol = None
    
    async def update_message(self, interaction=None):
        embed = await self._build_embed()
        if interaction:
            await interaction.response.edit_message(embed=embed, view=self)
        elif self.message:
            try:
                await self.message.edit(embed=embed, view=self)
            except:
                pass
    
    async def _build_embed(self):
        if self.current_page == "market":
            return await self._build_market_embed()
        elif self.current_page == "portfolio":
            return await self._build_portfolio_embed()
        elif self.current_page == "info" and self.info_symbol:
            return await self._build_stock_embed(self.info_symbol)
        return await self._build_market_embed()
    
    async def _build_market_embed(self):
        embed = discord.Embed(
            title="📈 Yokaro 股票市場",
            description=f"🕐 更新時間：{datetime.now().strftime('%H:%M:%S')}\n💡 點擊下方按鈕進行交易",
            color=0x00d4aa
        )
        
        stocks = self.cog.data.get_market()
        if not stocks:
            embed.add_field(name="🏢 上市公司", value="目前市場上沒有任何股票！\n管理員可以使用 `!創股票` 來創建", inline=False)
            return embed
        
        # 排序
        sorted_stocks = sorted(stocks.items(), key=lambda x: x[1]["price"] / max(x[1]["initial_price"], 1), reverse=True)
        
        market_text = ""
        for symbol, info in sorted_stocks[:20]:
            change = ((info["price"] - info["initial_price"]) / max(info["initial_price"], 1)) * 100
            emoji = "🟢" if change >= 0 else "🔴"
            change_str = f"+{change:.1f}%" if change >= 0 else f"{change:.1f}%"
            market_text += f"{emoji} **{symbol}** ${info['price']:,.2f} ({change_str})\n"
            market_text += f"└ {info['name'][:20]} | 流通: {info['available_shares']}/{info['total_shares']} 股\n"
        
        embed.add_field(name="🏢 上市公司", value=market_text, inline=False)
        embed.set_footer(text="🔄 每5秒自動更新 | 點擊下方按鈕操作")
        return embed
    
    async def _build_portfolio_embed(self, user_id=None):
        if not user_id:
            user_id = self.cog.bot.user.id
        
        embed = discord.Embed(
            title="📊 我的持股",
            color=0x00d4aa
        )
        
        # 實際的 user_id 會在按鈕點擊時傳入
        holdings = self.cog.data.get_portfolio(user_id)
        if not holdings:
            embed.description = "📭 你目前沒有持有任何股票！"
            return embed
        
        total_value = 0
        total_cost = 0
        for symbol, info in holdings.items():
            stock = self.cog.data.get_stock_info(symbol)
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
                value=f"持有: {info['shares']} 股 | 均價: ${info['avg_cost']:,.2f}\n"
                      f"現價: ${stock['price']:,.2f} | {emoji} ${profit:+,.0f} ({profit_pct:+.1f}%)",
                inline=True
            )
        
        total_profit = total_value - total_cost
        total_profit_pct = (total_profit / max(total_cost, 1)) * 100
        emoji = "🟢" if total_profit >= 0 else "🔴"
        embed.add_field(name="📈 總計", value=f"成本: ${total_cost:,.0f} | 市值: ${total_value:,.0f}\n{emoji} 損益: ${total_profit:+,.0f} ({total_profit_pct:+.1f}%)", inline=False)
        return embed
    
    async def _build_stock_embed(self, symbol):
        stock = self.cog.data.get_stock_info(symbol)
        if not stock:
            embed = discord.Embed(title="❌ 股票不存在", color=0xff0000)
            return embed
        
        change = ((stock["price"] - stock["initial_price"]) / max(stock["initial_price"], 1)) * 100
        emoji = "🟢" if change >= 0 else "🔴"
        
        embed = discord.Embed(
            title=f"📈 {symbol} - {stock['name']}",
            description=f"{emoji} 漲跌幅: {change:+.1f}% | 更新: {datetime.now().strftime('%H:%M:%S')}",
            color=0x00d4aa
        )
        embed.add_field(name="當前股價", value=f"**${stock['price']:,.2f}**", inline=True)
        embed.add_field(name="發行價", value=f"${stock['initial_price']:,.2f}", inline=True)
        embed.add_field(name="成交量", value=f"{stock['volume']:,}", inline=True)
        embed.add_field(name="總股數", value=f"{stock['total_shares']:,}", inline=True)
        embed.add_field(name="流通股", value=f"{stock['available_shares']:,}", inline=True)
        embed.add_field(name="創建者", value=f"<@{stock['creator']}>", inline=True)
        
        # 圖表
        if CHART_AVAILABLE:
            chart = self.cog.data.generate_chart(symbol)
            if chart:
                file = discord.File(chart, filename=f"{symbol}_chart.png")
                embed.set_image(url=f"attachment://{symbol}_chart.png")
                self._chart_file = file
        return embed
    
    # ===== 按鈕 =====
    @discord.ui.button(label="📊 行情", style=discord.ButtonStyle.success, custom_id="stk_market")
    async def market_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page = "market"
        self.info_symbol = None
        embed = await self._build_embed()
        kwargs = {"embed": embed, "view": self}
        if getattr(self, '_chart_file', None):
            kwargs["file"] = self._chart_file
            self._chart_file = None
        await interaction.response.edit_message(**kwargs)
    
    @discord.ui.button(label="💰 買入", style=discord.ButtonStyle.primary, custom_id="stk_buy")
    async def buy_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        stocks = self.cog.data.get_market()
        if not stocks:
            return await interaction.response.send_message("❌ 市場上沒有股票可以買！", ephemeral=True)
        
        # 創建一個選擇選單
        options = []
        for symbol, info in list(stocks.items())[:25]:
            options.append(discord.SelectOption(
                label=f"{symbol} - ${info['price']:,.2f}",
                description=f"{info['name'][:50]} | 流通: {info['available_shares']} 股",
                value=symbol
            ))
        
        select = discord.ui.Select(placeholder="選擇要買入的股票...", options=options, custom_id="stk_buy_select")
        
        async def buy_select_callback(select_interaction: discord.Interaction):
            symbol = select_interaction.data['values'][0]
            modal = TradeModal(self.cog, 'buy', symbol)
            await select_interaction.response.send_modal(modal)
        
        select.callback = buy_select_callback
        
        view = discord.ui.View(timeout=60)
        view.add_item(select)
        await interaction.response.send_message("📥 **選擇要買入的股票：**", view=view, ephemeral=True)
    
    @discord.ui.button(label="📤 賣出", style=discord.ButtonStyle.danger, custom_id="stk_sell")
    async def sell_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        holdings = self.cog.data.get_portfolio(interaction.user.id)
        if not holdings:
            return await interaction.response.send_message("📭 你沒有持股可以賣！", ephemeral=True)
        
        options = []
        for symbol, info in holdings.items():
            stock = self.cog.data.get_stock_info(symbol)
            if stock:
                options.append(discord.SelectOption(
                    label=f"{symbol} - 持有 {info['shares']} 股",
                    description=f"現價: ${stock['price']:,.2f} | 市值: ${stock['price']*info['shares']:,.0f}",
                    value=symbol
                ))
        
        if not options:
            return await interaction.response.send_message("📭 你沒有持股可以賣！", ephemeral=True)
        
        select = discord.ui.Select(placeholder="選擇要賣出的股票...", options=options, custom_id="stk_sell_select")
        
        async def sell_select_callback(select_interaction: discord.Interaction):
            symbol = select_interaction.data['values'][0]
            modal = TradeModal(self.cog, 'sell', symbol)
            await select_interaction.response.send_modal(modal)
        
        select.callback = sell_select_callback
        
        view = discord.ui.View(timeout=60)
        view.add_item(select)
        await interaction.response.send_message("📤 **選擇要賣出的股票：**", view=view, ephemeral=True)
    
    @discord.ui.button(label="📁 持股", style=discord.ButtonStyle.secondary, custom_id="stk_portfolio")
    async def portfolio_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        holdings = self.cog.data.get_portfolio(interaction.user.id)
        if not holdings:
            return await interaction.response.send_message("📭 你目前沒有持有任何股票！", ephemeral=True)
        
        embed = discord.Embed(title=f"📊 {interaction.user.display_name} 的持股", color=0x00d4aa)
        total_value = 0
        total_cost = 0
        for symbol, info in holdings.items():
            stock = self.cog.data.get_stock_info(symbol)
            if not stock: continue
            current_value = stock["price"] * info["shares"]
            profit = current_value - info["total_cost"]
            profit_pct = (profit / max(info["total_cost"], 1)) * 100
            emoji = "🟢" if profit >= 0 else "🔴"
            total_value += current_value
            total_cost += info["total_cost"]
            embed.add_field(name=f"{symbol} - {stock.get('name', '未知')}",
                value=f"持有: {info['shares']} 股 | 均價: ${info['avg_cost']:,.2f}\n現價: ${stock['price']:,.2f} | {emoji} ${profit:+,.0f} ({profit_pct:+.1f}%)",
                inline=True)
        total_profit = total_value - total_cost
        total_profit_pct = (total_profit / max(total_cost, 1)) * 100
        emoji = "🟢" if total_profit >= 0 else "🔴"
        embed.add_field(name="📈 總計", value=f"成本: ${total_cost:,.0f} | 市值: ${total_value:,.0f}\n{emoji} 損益: ${total_profit:+,.0f} ({total_profit_pct:+.1f}%)", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="🔍 查詢", style=discord.ButtonStyle.secondary, custom_id="stk_info")
    async def info_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        stocks = self.cog.data.get_market()
        if not stocks:
            return await interaction.response.send_message("❌ 市場上沒有任何股票！", ephemeral=True)
        
        options = []
        for symbol, info in list(stocks.items())[:25]:
            options.append(discord.SelectOption(
                label=f"{symbol} - {info['name'][:30]}",
                description=f"股價: ${info['price']:,.2f}",
                value=symbol
            ))
        
        select = discord.ui.Select(placeholder="選擇要查詢的股票...", options=options, custom_id="stk_info_select")
        
        async def info_select_callback(select_interaction: discord.Interaction):
            symbol = select_interaction.data['values'][0]
            self.current_page = "info"
            self.info_symbol = symbol
            await self.update_message(select_interaction)
        
        select.callback = info_select_callback
        
        view = discord.ui.View(timeout=60)
        view.add_item(select)
        await interaction.response.send_message("🔍 **選擇要查詢的股票：**", view=view, ephemeral=True)
    
    @discord.ui.button(label="🔄 刷新", style=discord.ButtonStyle.primary, custom_id="stk_refresh")
    async def refresh_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page = "market"
        self.info_symbol = None
        embed = await self._build_embed()
        kwargs = {"embed": embed, "view": self}
        if getattr(self, '_chart_file', None):
            kwargs["file"] = self._chart_file
            self._chart_file = None
        await interaction.response.edit_message(**kwargs)

# ===== 資料管理 =====
class StockData:
    """股票資料管理"""
    def __init__(self):
        self.stocks = {}
        self.holdings = {}
        self.channels = {}
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
        symbol = symbol.upper()
        if symbol in self.stocks:
            return False, "股票代號已存在！"
        self.stocks[symbol] = {
            "name": name, "creator": str(creator_id),
            "total_shares": total_shares, "available_shares": total_shares,
            "price": price, "initial_price": price,
            "price_history": [{"price": price, "time": time.time()}],
            "created_at": time.time(), "description": f"{name} 股票", "volume": 0
        }
        self._save_stocks()
        return True, f"股票 {symbol} ({name}) 創建成功！"
    
    def update_price(self, symbol):
        stock = self.stocks.get(symbol)
        if not stock: return
        change = random.uniform(-0.05, 0.05)
        current = stock["price"]
        initial = stock["initial_price"]
        if current > initial * 1.5: change -= 0.02
        elif current < initial * 0.5: change += 0.02
        supply_ratio = stock["available_shares"] / max(stock["total_shares"], 1)
        if supply_ratio < 0.3: change *= 1.5
        elif supply_ratio > 0.8: change *= 0.7
        new_price = max(0.01, current * (1 + change))
        new_price = round(new_price, 2)
        stock["price"] = new_price
        stock["price_history"].append({"price": new_price, "time": time.time()})
        if len(stock["price_history"]) > 100:
            stock["price_history"] = stock["price_history"][-100:]
        self._save_stocks()
    
    def buy_stock(self, user_id, symbol, shares):
        stock = self.stocks.get(symbol)
        if not stock: return False, "股票不存在！"
        if shares <= 0: return False, "股數必須大於 0！"
        if stock["available_shares"] < shares:
            return False, f"庫存不足！僅剩 {stock['available_shares']} 股"
        cost = stock["price"] * shares
        uid = str(user_id)
        eco = self._get_economy()
        if not eco: return False, "經濟系統無法使用！"
        balance = eco.get_balance(uid)
        if balance < cost: return False, f"餘額不足！需要 ${cost:,.0f}，你只有 ${balance:,.0f}"
        eco.add_money(uid, -cost)
        stock["available_shares"] -= shares
        stock["volume"] += shares
        if uid not in self.holdings: self.holdings[uid] = {}
        if symbol not in self.holdings[uid]:
            self.holdings[uid][symbol] = {"shares": 0, "avg_cost": 0, "total_cost": 0}
        h = self.holdings[uid][symbol]
        h["total_cost"] += cost; h["shares"] += shares
        h["avg_cost"] = h["total_cost"] / h["shares"]
        self._save_stocks(); self._save_holdings()
        return True, f"✅ 成功買入 {shares} 股 {symbol}！花費 ${cost:,.0f}"
    
    def sell_stock(self, user_id, symbol, shares):
        stock = self.stocks.get(symbol)
        if not stock: return False, "股票不存在！"
        if shares <= 0: return False, "股數必須大於 0！"
        uid = str(user_id)
        if uid not in self.holdings or symbol not in self.holdings[uid]:
            return False, "你沒有持有該股票！"
        h = self.holdings[uid][symbol]
        if h["shares"] < shares: return False, f"持股不足！你僅持有 {h['shares']} 股"
        revenue = stock["price"] * shares
        eco = self._get_economy()
        if eco: eco.add_money(uid, revenue)
        h["shares"] -= shares
        if h["shares"] <= 0:
            del self.holdings[uid][symbol]
            if not self.holdings[uid]: del self.holdings[uid]
        else: h["total_cost"] = h["avg_cost"] * h["shares"]
        stock["available_shares"] += shares; stock["volume"] += shares
        self._save_stocks(); self._save_holdings()
        return True, f"✅ 成功賣出 {shares} 股 {symbol}！獲得 ${revenue:,.0f}"
    
    def get_portfolio(self, user_id):
        uid = str(user_id)
        return self.holdings.get(uid, {})
    
    def get_stock_info(self, symbol):
        return self.stocks.get(symbol)
    
    def get_market(self):
        return self.stocks
    
    def _get_economy(self):
        return None
    
    def generate_chart(self, symbol):
        if not CHART_AVAILABLE: return None
        stock = self.stocks.get(symbol)
        if not stock or len(stock["price_history"]) < 2: return None
        history = stock["price_history"]
        prices = [h["price"] for h in history]
        times = [datetime.fromtimestamp(h["time"]) for h in history]
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.plot(times, prices, color='#00d4aa', linewidth=2, label=f'{symbol} 股價')
        ax.fill_between(times, prices, alpha=0.1, color='#00d4aa')
        ax.set_facecolor('#1a1a2e'); fig.patch.set_facecolor('#1a1a2e')
        ax.tick_params(colors='white'); ax.set_title(f'{symbol} - {stock["name"]}', color='white', fontsize=16)
        ax.set_ylabel('價格 ($)', color='white'); ax.set_xlabel('時間', color='white')
        ax.grid(True, alpha=0.2, color='#333')
        for i, (t, p) in enumerate(zip(times, prices)):
            if i == len(prices) - 1 or i == 0:
                ax.annotate(f'${p:,.2f}', (t, p), textcoords="offset points", xytext=(0, 10), ha='center', color='#ffd700', fontsize=9)
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=100, bbox_inches='tight', facecolor='#1a1a2e')
        buf.seek(0); plt.close()
        return buf

class StocksCog(commands.Cog):
    """📈 股票市場系統"""
    
    def __init__(self, bot):
        self.bot = bot
        self.data = StockData()
        self.stock_panels = {}  # guild_id -> {"message": msg, "view": view, "loop": task}
        self.price_update_task = self.bot.loop.create_task(self._price_loop())
    
    def cog_unload(self):
        self.price_update_task.cancel()
        for gid in list(self.stock_panels.keys()):
            panel = self.stock_panels[gid]
            if panel.get("loop"):
                panel["loop"].cancel()
    
    async def _price_loop(self):
        """每分鐘更新股價 + 刷新行情頻道"""
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            try:
                for symbol in list(self.data.stocks.keys()):
                    self.data.update_price(symbol)
                await self._update_market_channel()
                # 刷新所有活動面板
                for gid in list(self.stock_panels.keys()):
                    panel = self.stock_panels[gid]
                    if panel.get("view") and panel.get("view").current_page == "market":
                        try:
                            await panel["view"].update_message()
                        except:
                            pass
            except Exception as e:
                print(f"股價更新錯誤: {e}")
            await asyncio.sleep(15)  # 每15秒更新！更快！
    
    async def _update_market_channel(self):
        for guild_id_str, channel_id in self.data.channels.items():
            guild = self.bot.get_guild(int(guild_id_str))
            if not guild: continue
            channel = guild.get_channel(int(channel_id))
            if not channel: continue
            embed = discord.Embed(
                title="📈 Yokaro 股票市場即時行情",
                description=f"🕐 {datetime.now().strftime('%H:%M:%S')} | 每15秒自動更新",
                color=0x00d4aa
            )
            stocks = self.data.get_market()
            if not stocks:
                embed.add_field(name="暫無股票", value="目前市場上沒有任何股票！", inline=False)
            else:
                sorted_stocks = sorted(stocks.items(), key=lambda x: x[1]["price"] / max(x[1]["initial_price"], 1), reverse=True)
                market_text = ""
                for symbol, info in sorted_stocks[:15]:
                    change = ((info["price"] - info["initial_price"]) / max(info["initial_price"], 1)) * 100
                    emoji = "🟢" if change >= 0 else "🔴"
                    change_str = f"+{change:.1f}%" if change >= 0 else f"{change:.1f}%"
                    market_text += f"{emoji} **{symbol}** ${info['price']:,.2f} ({change_str})\n"
                    market_text += f"└ {info['name'][:20]} | 流通: {info['available_shares']}/{info['total_shares']} 股\n"
                embed.add_field(name="🏢 上市公司", value=market_text, inline=False)
            try:
                async for msg in channel.history(limit=3):
                    if msg.author == self.bot.user:
                        await msg.edit(embed=embed)
                        return
                await channel.send(embed=embed)
            except: pass
    
    # ===== 指令 =====
    @commands.command(name='股市', aliases=['market', 'stockmarket'])
    async def market(self, ctx):
        """📈 開啟股票市場互動面板（即時更新）"""
        # 取消舊面板循環
        if ctx.guild.id in self.stock_panels:
            old = self.stock_panels[ctx.guild.id]
            if old.get("loop"):
                old["loop"].cancel()
        
        view = StockMarketView(self.cog if hasattr(self, 'cog') else self)
        # 注意：這裡要傳 self 而不是 self.cog
        view = StockMarketView(self)
        embed = await view._build_market_embed()
        msg = await ctx.send(embed=embed, view=view)
        view.message = msg
        
        # 啟動自動刷新循環
        async def auto_refresh():
            await asyncio.sleep(5)
            while not self.bot.is_closed():
                try:
                    if ctx.guild.id in self.stock_panels:
                        panel = self.stock_panels[ctx.guild.id]
                        if panel.get("view") and panel["view"].current_page == "market":
                            await panel["view"].update_message()
                except:
                    break
                await asyncio.sleep(5)  # 每5秒刷新
        
        loop = self.bot.loop.create_task(auto_refresh())
        self.stock_panels[ctx.guild.id] = {"message": msg, "view": view, "loop": loop}
    
    @commands.command(name='創股票', aliases=['createstock', '發行股票'])
    @commands.has_permissions(administrator=True)
    async def create_stock(self, ctx, name: str, total_shares: int = 1000, price: float = 100.0):
        """(管理員) 創建新股票：!創股票 [名稱] [總股數] [初始股價]"""
        symbol = ''.join([c for c in name if c.isascii() and c.isalpha()]).upper()[:4]
        if not symbol or len(symbol) < 2:
            symbol = f"STK{random.randint(100, 999)}"
        if total_shares < 100:
            return await ctx.send("❌ 總股數至少需要 100 股！")
        if price < 0.1:
            return await ctx.send("❌ 初始股價至少需要 $0.1！")
        
        eco = self.bot.get_cog("EconomyCog")
        if not eco: return await ctx.send("❌ 經濟系統無法使用！")
        fee = max(1000, int(total_shares * price * 0.05))
        uid = str(ctx.author.id)
        if eco.get_balance(uid) < fee:
            return await ctx.send(f"❌ 創建股票需要手續費 ${fee:,}，你的餘額不足！")
        eco.add_money(uid, -fee)
        
        success, msg = self.data.create_stock(symbol, name, ctx.author.id, total_shares, price)
        if success:
            # 創始人獲得 10%
            bonus_shares = int(total_shares * 0.1)
            if bonus_shares > 0:
                uid = str(ctx.author.id)
                if uid not in self.data.holdings: self.data.holdings[uid] = {}
                if symbol not in self.data.holdings[uid]:
                    self.data.holdings[uid][symbol] = {"shares": 0, "avg_cost": 0, "total_cost": 0}
                h = self.data.holdings[uid][symbol]
                h["shares"] += bonus_shares; h["avg_cost"] = price; h["total_cost"] = price * bonus_shares
                self.data._save_holdings()
            
            embed = discord.Embed(title="📈 股票發行成功！", color=0x00d4aa)
            embed.add_field(name="代號", value=f"**{symbol}**", inline=True)
            embed.add_field(name="名稱", value=name, inline=True)
            embed.add_field(name="發行價", value=f"${price:,.2f}", inline=True)
            embed.add_field(name="總股數", value=f"{total_shares:,}", inline=True)
            embed.add_field(name="手續費", value=f"${fee:,}", inline=True)
            embed.add_field(name="創始人獎勵", value=f"{bonus_shares} 股", inline=True)
            await ctx.send(embed=embed)
        else:
            await ctx.send(f"❌ {msg}")
    
    @commands.command(name='股票頻道', aliases=['stockschannel', '股市頻道'])
    @commands.has_permissions(administrator=True)
    async def set_stock_channel(self, ctx):
        """(管理員) 設定股票即時行情頻道（每15秒自動更新）"""
        self.data.channels[str(ctx.guild.id)] = ctx.channel.id
        self.data._save_channels()
        await ctx.send(f"✅ 已將 {ctx.channel.mention} 設定為股票即時行情頻道！\n📈 每15秒自動更新即時股價")
    
    @commands.command(name='除牌', aliases=['delist', '下市'])
    @commands.has_permissions(administrator=True)
    async def delist_stock(self, ctx, symbol: str):
        """(管理員) 將股票下市"""
        symbol = symbol.upper()
        if symbol not in self.data.stocks:
            return await ctx.send(f"❌ 股票 {symbol} 不存在！")
        stock = self.data.stocks[symbol]
        eco = self.bot.get_cog("EconomyCog")
        refund = 0
        if eco and stock["available_shares"] > 0:
            refund = stock["available_shares"] * stock["price"] * 0.5
            eco.add_money(str(stock["creator"]), refund)
        del self.data.stocks[symbol]
        self.data._save_stocks()
        await ctx.send(f"✅ 股票 {symbol} ({stock['name']}) 已下市！創建者獲得半價退還 ${refund:,.0f}")

async def setup(bot):
    await bot.add_cog(StocksCog(bot))
import discord
from discord.ext import commands
import aiohttp
from bs4 import BeautifulSoup
import urllib.parse
import requests
import asyncio

from discord import app_commands

class InfoCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name='weather', aliases=['天氣'])
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def weather(self, ctx, *, city: str):
        """查詢天氣資訊 (使用 wttr.in)"""
        async with aiohttp.ClientSession() as session:
            url = f"https://wttr.in/{urllib.parse.quote(city)}?format=3"
            async with session.get(url) as response:
                if response.status == 200:
                    text = await response.text()
                    await ctx.send(f"🌦️ **{city}** 的天氣訊號：\n{text}")
                else:
                    await ctx.send("嗷～氣象衛星斷線了，查不到那裡的天氣。")

    @commands.hybrid_command(name='wiki', aliases=['維基', '查'])
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def wiki(self, ctx, *, query: str):
        """搜尋維基百科 (使用官方 API)"""
        await ctx.defer()
        async with aiohttp.ClientSession() as session:
            # 1. 搜尋條目
            search_url = f"https://zh.wikipedia.org/w/api.php?action=query&list=search&srsearch={urllib.parse.quote(query)}&format=json"
            async with session.get(search_url) as response:
                if response.status != 200:
                    return await ctx.send("嗷嗷嗷～連接維基百科失敗！")
                
                search_data = await response.json()
                results = search_data.get('query', {}).get('search', [])
                if not results:
                    return await ctx.send("嗷～這在洛洛的資料庫裡找不到喔！")
                
                title = results[0]['title']
                pageid = results[0]['pageid']

            # 2. 獲取摘要與縮圖
            detail_url = (
                f"https://zh.wikipedia.org/w/api.php?action=query&prop=extracts|pageimages"
                f"&exintro&explaintext&exchars=300&piprop=thumbnail&pithumbsize=500"
                f"&titles={urllib.parse.quote(title)}&format=json"
            )
            async with session.get(detail_url) as response:
                if response.status == 200:
                    detail_data = await response.json()
                    pages = detail_data.get('query', {}).get('pages', {})
                    page_info = pages.get(str(pageid)) or next(iter(pages.values()))
                    
                    summary = page_info.get('extract', "找不到相關摘要。")
                    thumbnail = page_info.get('thumbnail', {}).get('source')
                    url = f"https://zh.wikipedia.org/wiki/{urllib.parse.quote(title)}"

                    embed = discord.Embed(title=title, description=summary, url=url, color=0x3498db)
                    if thumbnail:
                        embed.set_image(url=thumbnail)
                    embed.set_footer(text="來源：維基百科 (官方 API)")
                    await ctx.send(embed=embed)
                else:
                    await ctx.send("嗷～獲取詳細資訊時迷路了！")

    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @commands.hybrid_command(name='stock', aliases=['股價'])
    async def stock(self, ctx, symbol: str):
        """查詢美股/台股即時股價 (Yahoo Finance 強化版)"""
        await ctx.defer()
        symbol = symbol.upper()
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        url = f"https://finance.yahoo.com/quote/{symbol}"
        
        def fetch_stock():
            return requests.get(url, headers=headers, timeout=10)
            
        try:
            response = await asyncio.to_thread(fetch_stock)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # 抓取價格 (多重備援)
                price = "未知"
                for field in ['regularMarketPrice', 'postMarketPrice']:
                    price_elem = soup.find('fin-streamer', {'data-field': field, 'data-symbol': symbol})
                    if price_elem and price_elem.text:
                        price = price_elem.text
                        break
                
                # 抓取漲跌
                change = "未知"
                change_elem = soup.find('fin-streamer', {'data-field': 'regularMarketChangePercent', 'data-symbol': symbol})
                if change_elem: change = change_elem.text.strip('()')

                # 抓取貨幣
                currency = ""
                curr_elem = soup.find('span', string=re.compile(r'Currency in')) if 're' in globals() else None
                #  fallback if re not loaded or not found
                if not currency:
                    meta_curr = soup.find('meta', {'itemprop': 'currency'})
                    currency = meta_curr['content'] if meta_curr else ""

                embed = discord.Embed(title=f"💹 股市資訊: {symbol}", color=0x2ecc71, url=url)
                embed.add_field(name="目前價格", value=f"**{price}** {currency}", inline=True)
                embed.add_field(name="今日漲跌", value=f"**{change}**", inline=True)
                
                if ".TW" not in symbol and symbol.isdigit():
                    embed.set_footer(text="💡 提示：查詢台股請輸入代號+ .TW (例如 2330.TW)")
                else:
                    embed.set_footer(text="來源：Yahoo Finance")
                
                await ctx.send(embed=embed)
            else:
                await ctx.send(f"嗷～找不到代號 `{symbol}` 的資料。請檢查輸入是否正確！")
        except Exception as e:
            print(f"Stock error: {e}")
            await ctx.send("嗷嗷嗷～連接股市衛星時發生意外錯誤！可能是網路不穩。")

async def setup(bot):
    await bot.add_cog(InfoCog(bot))

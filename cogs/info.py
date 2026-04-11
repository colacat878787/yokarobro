import discord
from discord.ext import commands
import aiohttp
from bs4 import BeautifulSoup
import urllib.parse
import requests
import asyncio

class InfoCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='天氣')
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

    @commands.command(name='維基')
    async def wiki(self, ctx, *, query: str):
        """搜尋維基百科並抓取大頭圖"""
        async with ctx.typing():
            async with aiohttp.ClientSession() as session:
                # 1. 先用 API 找到正確標題
                search_url = f"https://zh.wikipedia.org/w/api.php?action=query&list=search&srsearch={urllib.parse.quote(query)}&format=json"
                async with session.get(search_url) as response:
                    if response.status == 200:
                        data = await response.json()
                        search_results = data['query']['search']
                        if search_results:
                            title = search_results[0]['title']
                            url = f"https://zh.wikipedia.org/wiki/{urllib.parse.quote(title)}"
                            
                            # 2. 用 BeautifulSoup 爬取真實網頁取得 og:image 和摘要
                            async with session.get(url) as page_resp:
                                if page_resp.status == 200:
                                    html = await page_resp.text()
                                    soup = BeautifulSoup(html, "html.parser")
                                    
                                    # 抓大頭圖
                                    og_image = soup.find("meta", property="og:image")
                                    image_url = og_image["content"] if og_image else None
                                    
                                    # 抓第一段文字
                                    paragraphs = soup.select('.mw-parser-output > p')
                                    summary = ""
                                    for p in paragraphs:
                                        if p.text.strip():
                                            summary = p.text.strip()
                                            break
                                            
                                    embed = discord.Embed(title=title, description=summary[:250] + "...", url=url, color=0x3498db)
                                    if image_url:
                                        embed.set_thumbnail(url=image_url)
                                    embed.set_footer(text="來源：維基百科")
                                    await ctx.send(embed=embed)
                                else:
                                    await ctx.send("嗷～去維基百科的路上迷路了！")
                        else:
                            await ctx.send("嗷～這在洛洛的資料庫裡找不到喔！")
                    else:
                        await ctx.send("嗷嗷嗷～連接維基百科失敗！")

    @commands.command(name='股價')
    async def stock(self, ctx, symbol: str):
        """查詢美股/台股即時股價 (使用 Yahoo Finance 網頁爬蟲)"""
        async with ctx.typing():
            headers = {'User-Agent': 'Mozilla/5.0'}
            url = f"https://finance.yahoo.com/quote/{symbol}"
            
            def fetch_stock():
                return requests.get(url, headers=headers, timeout=10)
                
            try:
                response = await asyncio.to_thread(fetch_stock)
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    try:
                        # 嘗試抓取價格 (Yahoo Finance class 可能變化)
                        price_elem = soup.find('fin-streamer', {'data-field': 'regularMarketPrice'})
                        if not price_elem:
                            price_elem = soup.find('fin-streamer', {'data-symbol': symbol, 'data-field': 'regularMarketPrice'})
                        
                        price = price_elem.text if price_elem else "未知"
                        
                        currency_elem = soup.find('fin-streamer', {'data-field': 'currency'})
                        currency = currency_elem.text if currency_elem else ""
                        
                        change_elem = soup.find('fin-streamer', {'data-field': 'regularMarketChangePercent'})
                        change = change_elem.text if change_elem else "未知"
                        
                        embed = discord.Embed(title=f"💹 股市資訊: {symbol}", color=0x2ecc71)
                        embed.add_field(name="目前價格", value=f"{price} {currency}", inline=True)
                        embed.add_field(name="今日漲跌", value=change, inline=True)
                        embed.set_footer(text="來源：Yahoo Finance")
                        await ctx.send(embed=embed)
                    except Exception as e:
                        print(f"Stock parsing error: {e}")
                        await ctx.send("嗷～代號輸入錯誤或無法解析資料！可能是雅虎又改版了。")
                else:
                    await ctx.send("嗷嗷嗷～無法從股市衛星讀取數據。目前被阻擋。")
            except Exception as e:
                print(f"Stock fetch error: {e}")
                await ctx.send("嗷嗷嗷～連接股市衛星時發生意外錯誤！")

async def setup(bot):
    await bot.add_cog(InfoCog(bot))

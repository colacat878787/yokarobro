import discord
from discord.ext import commands
import asyncio
import subprocess
import sys

# Auto-install mcstatus if not present
try:
    from mcstatus import JavaServer
    from mcstatus.status_response import JavaStatusResponse
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "mcstatus==11.1.0"])
    from mcstatus import JavaServer


class MCStatusCog(commands.Cog):
    """Provides Minecraft server status lookups via a command."""

    def __init__(self, bot):
        self.bot = bot
        self._cache = {}
        self._cache_ttl = 60  # seconds

    async def _query_server(self, address: str):
        now = asyncio.get_event_loop().time()
        if address in self._cache:
            cached, timestamp = self._cache[address]
            if now - timestamp < self._cache_ttl:
                return cached

        loop = asyncio.get_event_loop()
        try:
            server = JavaServer.lookup(address, timeout=5)
            status = await loop.run_in_executor(None, server.status)

            desc = status.description
            if isinstance(desc, dict):
                desc = desc.get("text", "")
            elif hasattr(desc, "to_plain"):
                desc = desc.to_plain()
            else:
                desc = str(desc)

            result = {
                "online": True,
                "address": address,
                "players_online": status.players.online,
                "players_max": status.players.max,
                "version": status.version.name,
                "protocol": status.version.protocol,
                "description": desc,
                "latency": round(status.latency),
            }
        except ConnectionRefusedError:
            result = {"online": False, "address": address, "error": "連線被拒絕（伺服器可能已關閉）"}
        except TimeoutError:
            result = {"online": False, "address": address, "error": "連線逾時（超過 5 秒）"}
        except OSError as e:
            result = {"online": False, "address": address, "error": f"網路錯誤: {e.strerror}"}
        except Exception as e:
            result = {"online": False, "address": address, "error": str(e)}

        self._cache[address] = (result, now)
        return result

    @commands.hybrid_command(name="mcstatus", aliases=["mc"])
    async def mcstatus(self, ctx, *, address: str):
        """查詢 Minecraft 伺服器狀態。格式：!mcstatus <host:port>"""
        async with ctx.typing():
            data = await self._query_server(address)

        if data.get("online"):
            embed = discord.Embed(
                title=f"🟢 {data['address']}",
                color=0x2ECC71,
            )
            embed.add_field(name="版本", value=data.get("version", "未知"), inline=True)
            embed.add_field(name="Protocol", value=str(data.get("protocol", "?")), inline=True)
            embed.add_field(
                name="玩家",
                value=f"{data.get('players_online', 0)} / {data.get('players_max', '?')}",
                inline=True,
            )
            embed.add_field(name="延遲", value=f"{data.get('latency', '?')} ms", inline=True)
            if data.get("description"):
                embed.add_field(name="MOTD", value=data["description"][:200], inline=False)
        else:
            embed = discord.Embed(
                title=f"🔴 {data['address']} — 離線",
                description=f"❌ {data.get('error', '伺服器無法連線')}",
                color=0xE74C3C,
            )
            embed.set_footer(text="結果已快取 60 秒。請確認 IP 與連接埠是否正確。")

        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(MCStatusCog(bot))

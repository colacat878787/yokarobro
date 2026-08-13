import discord
from discord.ext import commands
import asyncio
import subprocess
import sys
from utils.i18n import t

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
            result = {"online": False, "address": address, "error": "refused"}
        except TimeoutError:
            result = {"online": False, "address": address, "error": "timeout"}
        except OSError as e:
            result = {"online": False, "address": address, "error": str(e.strerror or e)}
        except Exception as e:
            result = {"online": False, "address": address, "error": str(e)}

        self._cache[address] = (result, now)
        return result

    @commands.hybrid_command(name="mcstatus", aliases=["mc"])
    async def mcstatus(self, ctx, *, address: str):
        """查詢 Minecraft 伺服器狀態。格式：!mcstatus <host:port>"""
        gid = ctx.guild.id if ctx.guild else None
        async with ctx.typing():
            data = await self._query_server(address)

        if data.get("online"):
            embed = discord.Embed(
                title=t(gid, "mc.online", addr=data['address']),
                color=0x2ECC71,
            )
            embed.add_field(name=t(gid, "mc.version"), value=data.get("version", t(gid, "mc.unknown")), inline=True)
            embed.add_field(name="Protocol", value=str(data.get("protocol", "?")), inline=True)
            embed.add_field(
                name=t(gid, "mc.players"),
                value=f"{data.get('players_online', 0)} / {data.get('players_max', '?')}",
                inline=True,
            )
            embed.add_field(name=t(gid, "mc.latency"), value=f"{data.get('latency', '?')} ms", inline=True)
            if data.get("description"):
                embed.add_field(name="MOTD", value=data["description"][:200], inline=False)
        else:
            err = data.get("error", "unknown")
            err_key = {"refused": t(gid, "mc.refused"), "timeout": t(gid, "mc.timeout")}.get(err, err)
            embed = discord.Embed(
                title=t(gid, "mc.offline", addr=data['address']),
                description=err_key,
                color=0xE74C3C,
            )
            embed.set_footer(text=t(gid, "mc.footer"))

        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(MCStatusCog(bot))

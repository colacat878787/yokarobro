import discord
from discord.ext import commands
import asyncio
from mcstatus import JavaServer

class MCStatusCog(commands.Cog):
    """Provides Minecraft server status lookups via a slash command."""
    def __init__(self, bot):
        self.bot = bot
        # Cache results for a short period to avoid hitting rate limits
        self._cache = {}
        self._cache_ttl = 60  # seconds

    async def _query_server(self, address: str):
        # Simple cache check
        now = asyncio.get_event_loop().time()
        if address in self._cache:
            cached, timestamp = self._cache[address]
            if now - timestamp < self._cache_ttl:
                return cached
        try:
            server = JavaServer.lookup(address)
            status = await asyncio.get_event_loop().run_in_executor(None, server.status)
            # Gather desired fields
            result = {
                "address": address,
                "online": True,
                "players_online": status.players.online,
                "players_max": status.players.max,
                "version": status.version.name,
                "protocol": status.version.protocol,
                "description": status.description.get('text') if isinstance(status.description, dict) else str(status.description),
                "latency": round(status.latency),
            }
        except Exception as e:
            result = {
                "address": address,
                "online": False,
                "error": str(e)
            }
        # Store in cache
        self._cache[address] = (result, now)
        return result

    @commands.hybrid_command(name='mcstatus', aliases=['mc'])
    async def mcstatus(self, ctx, *, address: str):
        """Query a Minecraft server and display its status.
        Use the format ``host:port`` (default port 25565).
        """
        async with ctx.typing():
            data = await self._query_server(address)
        embed = discord.Embed(title="Minecraft Server Status", color=0x00FF00)
        if data.get("online"):
            embed.add_field(name="Address", value=data["address"], inline=False)
            embed.add_field(name="Version", value=data.get("version", "Unknown"), inline=True)
            embed.add_field(name="Protocol", value=data.get("protocol", "?"), inline=True)
            embed.add_field(name="Players", value=f"{data.get('players_online', 0)}/{data.get('players_max', '?')}", inline=True)
            embed.add_field(name="Latency", value=f"{data.get('latency', '?')} ms", inline=True)
            description = data.get("description")
            if description:
                embed.add_field(name="MOTD", value=description, inline=False)
        else:
            embed.add_field(name="Error", value=data.get("error", "Server offline or unreachable"), inline=False)
            embed.color = 0xFF0000
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(MCStatusCog(bot))

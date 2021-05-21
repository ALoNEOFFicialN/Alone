from core import Quotient, Cog, Context
from discord.ext import commands
from .dispatchers import *
from models import Logging as LM
from utils import LogType
from .events import *
import discord
import typing


class Logging(Cog):
    def __init__(self, bot: Quotient):
        self.bot = bot

    async def cog_command_error(self, ctx, error):
        if isinstance(error, commands.errors.BadArgument):  # raised when invalid LogType is passed.
            await ctx.send("value error")

    async def insert_or_update_config(self, ctx: Context, _type: LogType, channel: discord.TextChannel):
        _type = _type.value
        guild = ctx.guild

        record = await LM.get_or_none(guild_id=guild.id, type=_type)
        if record is None:
            await LM.create(guild_id=guild.id, channel_id=channel.id, type=_type, color=discord.Color(0x2F3136))

        else:
            await LM.filter(guild_id=guild.id, type=_type).update(channel_id=channel.id)

        return record

    @commands.command()
    async def msglog(self, ctx: Context, *, channel: discord.TextChannel):
        record = await self.insert_or_update_config(ctx, LogType.msg, channel)
        if not record:
            await ctx.success(f"Msglog enabled successfully!")
        else:
            return await ctx.success(f"Msglog channel updated to **{channel}**")

    @commands.command()
    async def joinlog(self, ctx: Context, *, channel: discord.TextChannel):
        record = await self.insert_or_update_config(ctx, LogType.join, channel)
        if not record:
            await ctx.success(f"Joinlog enabled successfully!")
        else:
            return await ctx.success(f"Joinlog channel updated to **{channel}**")

    @commands.command()
    async def leavelog(self, ctx: Context, *, channel: discord.TextChannel):
        record = await self.insert_or_update_config(ctx, LogType.leave, channel)
        if not record:
            await ctx.success(f"Leavelog enabled successfully!")
        else:
            return await ctx.success(f"Leavelog channel updated to **{channel}**")

    @commands.command()
    async def actionlog(self, ctx: Context, *, channel: discord.TextChannel):
        record = await self.insert_or_update_config(ctx, LogType.action, channel)
        if not record:
            await ctx.success(f"Actionlog enabled successfully!")
        else:
            return await ctx.success(f"Actionlog channel updated to **{channel}**")

    @commands.command()
    async def serverlog(self, ctx: Context, *, channel: discord.TextChannel):
        record = await self.insert_or_update_config(ctx, LogType.server, channel)
        if not record:
            await ctx.success(f"Serverlog enabled successfully!")
        else:
            return await ctx.success(f"Serverlog channel updated to **{channel}**")

    @commands.command()
    async def channellog(self, ctx: Context, *, channel: discord.TextChannel):
        record = await self.insert_or_update_config(ctx, LogType.channel, channel)
        if not record:
            await ctx.success(f"Channellog enabled successfully!")
        else:
            return await ctx.success(f"Channellog channel updated to **{channel}**")

    @commands.command()
    async def rolelog(self, ctx: Context, *, channel: discord.TextChannel):
        record = await self.insert_or_update_config(ctx, LogType.role, channel)
        if not record:
            await ctx.success(f"Rolelog enabled successfully!")
        else:
            return await ctx.success(f"Rolelog channel updated to **{channel}**")

    @commands.command()
    async def memberlog(self, ctx: Context, *, channel: discord.TextChannel):
        record = await self.insert_or_update_config(ctx, LogType.member, channel)
        if not record:
            await ctx.success(f"Memberlog enabled successfully!")
        else:
            return await ctx.success(f"Memberlog channel updated to **{channel}**")

    @commands.command()
    async def voicelog(self, ctx: Context, *, channel: discord.TextChannel):
        record = await self.insert_or_update_config(ctx, LogType.voice, channel)
        if not record:
            await ctx.success(f"Voicelog enabled successfully!")
        else:
            return await ctx.success(f"Voicelog channel updated to **{channel}**")

    @commands.command()
    async def reactionlog(self, ctx: Context, channel: discord.TextChannel):
        record = await self.insert_or_update_config(ctx, LogType.reaction, channel)
        if not record:
            await ctx.success(f"Reactionlog enabled successfully!")
        else:
            return await ctx.success(f"Reactionlog channel updated to **{channel}**")

    @commands.command()
    async def modlog(self, ctx: Context, *, channel: discord.TextChannel):
        record = await self.insert_or_update_config(ctx, LogType.mod, channel)
        if not record:
            await ctx.success(f"Modlog enabled successfully!")
        else:
            return await ctx.success(f"Modlog channel updated to **{channel}**")

    @commands.command()
    async def cmdlog(self, ctx: Context, *, channel: discord.TextChannel):
        record = await self.insert_or_update_config(ctx, LogType.cmd, channel)
        if not record:
            await ctx.success(f"Cmdlog enabled successfully!")
        else:
            return await ctx.success(f"Cmdlog channel updated to **{channel}**")

    @commands.command()
    async def invitelog(self, ctx: Context, *, channel: discord.TextChannel):
        record = await self.insert_or_update_config(ctx, LogType.invite, channel)
        if not record:
            await ctx.success(f"Invitelog enabled successfully!")
        else:
            return await ctx.success(f"Invitelog channel updated to **{channel}**")

    @commands.command()
    async def pinglog(self, ctx: Context, *, channel: discord.TextChannel):
        record = await self.insert_or_update_config(ctx, LogType.ping, channel)
        if not record:
            await ctx.success(f"Pinglog enabled successfully!")
        else:
            return await ctx.success(f"Pinglog channel updated to **{channel}**")

    @commands.command()
    async def logall(self, ctx: Context, *, channel: discord.TextChannel):
        pass

    @commands.command()
    async def logcolor(self, ctx: Context, logtype: LogType, color):
        pass

    @commands.group(invoke_without_command=True)
    async def logignore(self, ctx: Context):
        pass

    @logignore.command(name="bots")
    async def logignore_bots(self, ctx: Context, logtype: LogType):
        await ctx.send(logtype)

    @logignore.command(name="channel")
    async def logignore_channels(
        self, ctx: Context, logtype: LogType, *, channel: typing.Union[discord.TextChannel, discord.VoiceChannel]
    ):
        pass

    @commands.command()
    async def logtoggle(self, ctx: Context, logtype: typing.Union[LogType, str]):
        pass


def setup(bot):
    bot.add_cog(Logging(bot))
    bot.add_cog(LoggingDispatchers(bot))
    bot.add_cog(LoggingEvents(bot))

from __future__ import annotations

import typing

if typing.TYPE_CHECKING:
    from core import Quotient

from models import Guild, Timer
from core import Cog

from contextlib import suppress
from constants import random_greeting, IST
import discord

from .utils import erase_guild
from datetime import datetime, timedelta
import re
import config


class MainEvents(Cog, name="Main Events"):
    def __init__(self, bot: Quotient):
        self.bot = bot
        self.bot.loop.create_task(self.super_important_job())

    async def super_important_job(self):
        await self.bot.wait_until_ready()
        guild = await self.bot.getch(self.bot.get_guild, self.bot.fetch_guild, config.SERVER_ID)
        if not guild.chunked:
            self.bot.loop.create_task(guild.chunk())
        with suppress(AttributeError, discord.ClientException):
            await guild.get_channel(844178791735885824).connect()

    # incomplete?, I know
    @Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        with suppress(AttributeError):
            await Guild.create(guild_id=guild.id)
            self.bot.guild_data[guild.id] = {"prefix": "q", "color": self.bot.color, "footer": config.FOOTER}
            await guild.chunk()

            embed = discord.Embed(color=discord.Color.green(), title=f"I've joined a guild ({guild.member_count})")
            embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
            embed.add_field(
                name="__**General Info**__",
                value=f"**Guild Name:** {guild.name} [{guild.id}]\n**Guild Owner:** {guild.owner} [{guild.owner.id}]\n",
            )

            with suppress(discord.HTTPException, discord.NotFound, discord.Forbidden):
                webhook = discord.Webhook.from_url(config.JOIN_LOG, session=self.bot.session)
                await webhook.send(embed=embed, avatar_url=self.bot.user.avatar.url)

    @Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild):
        await self.bot.reminders.create_timer(
            datetime.now(tz=IST) + timedelta(minutes=5), "erase_guild", guild_id=guild.id
        )
        with suppress(AttributeError):
            try:
                self.bot.guild_data.pop(guild.id)
            except KeyError:
                pass

            embed = discord.Embed(color=discord.Color.red(), title=f"I have left a guild ({guild.member_count})")
            embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
            embed.add_field(
                name="__**General Info**__",
                value=f"**Guild name:** {guild.name} [{guild.id}]\n**Guild owner:** {guild.owner} [{guild.owner.id if guild.owner is not None else 'Not Found!'}]\n",
            )
            with suppress(discord.HTTPException, discord.NotFound, discord.Forbidden):
                webhook = discord.Webhook.from_url(config.JOIN_LOG, session=self.bot.session)
                await webhook.send(embed=embed, avatar_url=self.bot.user.avatar.url)

    @Cog.listener()
    async def on_erase_guild_timer_complete(self, timer: Timer):
        guild_id = timer.kwargs["guild_id"]
        guild = self.bot.get_guild(guild_id)
        if not guild:
            await erase_guild(guild_id)

    @Cog.listener()
    async def on_message(self, message: discord.Message):
        ctx = await self.bot.get_context(message)
        if re.match(f"^<@!?{self.bot.user.id}>$", message.content):
            self.bot.dispatch("mention", ctx)

    @Cog.listener()
    async def on_mention(self, ctx):
        prefix = self.bot.guild_data[ctx.guild.id]["prefix"] or "q"
        await ctx.send(
            f"{random_greeting()}, You seem lost. Are you?\n"
            f"Current prefix for this server is: `{prefix}`.\n\nUse it like: `{prefix}help`"
        )

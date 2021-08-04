from __future__ import annotations

import typing

if typing.TYPE_CHECKING:
    from core import Quotient

from core import Cog
from models import AutoPurge, Timer
from contextlib import suppress
from datetime import datetime, timedelta
from constants import IST

import discord


class UtilityEvents(Cog):
    def __init__(self, bot: Quotient):
        self.bot = bot

    @Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or not message.channel.id in self.bot.autopurge_channels:
            return

        record = await AutoPurge.get_or_none(channel_id=message.channel.id)
        if not record:
            return self.bot.autopurge_channels.discard(message.channel.id)

        await self.bot.reminders.create_timer(
            datetime.now(tz=IST) + timedelta(seconds=record.delete_after),
            "autopurge",
            message_id=message.id,
            channel_id=message.channel.id,
        )

    @Cog.listener()
    async def on_autopurge_timer_complete(self, timer: Timer):

        message_id, channel_id = timer.kwargs["message_id"], timer.kwargs["channel_id"]

        check = await AutoPurge.get_or_none(channel_id=channel_id)
        if not check:
            return

        channel = check.channel
        if not channel:
            return

        message = channel.get_partial_message(message_id)
        with suppress(discord.NotFound, discord.Forbidden, discord.HTTPException):
            await message.delete()

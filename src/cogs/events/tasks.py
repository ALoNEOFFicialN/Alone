from datetime import datetime
from constants import IST
from core import Cog, Quotient
from discord.ext import tasks
import models, discord
import asyncio
import config


class QuoTasks(Cog):
    def __init__(self, bot: Quotient):
        self.bot = bot
        self.insert_guilds.start()
        self.find_new_voters_and_premiums.start()
        self.find_people_who_have_to_pay.start()

        self._batch_lock = asyncio.Lock(loop=bot.loop)
        self._data_batch = []
        self.bulk_insert_loop.start()

    async def register_message(self, message: discord.Message):
        async with self._batch_lock:
            self._data_batch.append(
                msg := models.Messages(
                    guild_id=message.guild.id,
                    channel_id=message.channel.id,
                    author_id=message.author.id,
                    bot=message.author.bot,
                    sent_at=datetime.now(tz=IST),
                )
            )

    async def bulk_insert(self):
        if self._data_batch:
            await models.Messages.bulk_create(self._data_batch)
            self._data_batch.clear()

    @Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild:
            return
        await self.register_message(message)

    @tasks.loop(seconds=10)
    async def bulk_insert_loop(self):
        async with self._batch_lock:
            await self.bulk_insert()

    @tasks.loop(count=1)
    async def insert_guilds(self):
        query = "INSERT INTO guild_data (guild_id , prefix , embed_color , embed_footer , bot_master , muted_members ,disabled_channels , disabled_users , disabled_commands , censored) VALUES ($1 , $2 , $3, $4, $5, $6 , $7, $8, $9 ,$10) ON CONFLICT DO NOTHING"
        for guild in self.bot.guilds:
            await self.bot.db.execute(
                query,
                guild.id,
                config.PREFIX,
                config.COLOR,
                config.FOOTER,
                [],
                [],
                [],
                [],
                [],
                [],
            )

    @tasks.loop(seconds=10)
    async def find_new_voters_and_premiums(self):  # is it a bad idea?
        """
        This task fetches if someone purchased premium or voted for Quotient
        """
        records = await models.Votes.filter(is_voter=True, notified=False)
        if len(records):
            for record in records:
                self.bot.dispatch("vote", record)

        records = await models.Premium.filter(is_done=True, is_notified=False)
        if len(records):
            for record in records:
                self.bot.dispatch("premium_purchase", record)

        # both these listeners are in ./src/cogs/events/votes.py

    @tasks.loop(seconds=15)
    async def find_people_who_have_to_pay(self):
        users = await models.User.filter(is_premium=True, premium_expire_time__lte=datetime.now(tz=IST))
        guilds = await models.Guild.filter(is_premium=True, premium_end_time__lte=datetime.now(IST))

        if len(users):
            for user in users:
                self.bot.dispatch("user_premium_expire", user)

        if len(guilds):
            for guild in guilds:
                self.bot.dispatch("guild_premium_expire", guild)

    def cog_unload(self):
        self.find_new_voters_and_premiums.stop()
        self.find_people_who_have_to_pay.stop()
        self.bulk_insert_loop.stop()

    @insert_guilds.before_loop
    @find_new_voters_and_premiums.before_loop
    @find_people_who_have_to_pay.before_loop
    async def before_loops(self):
        await self.bot.wait_until_ready()

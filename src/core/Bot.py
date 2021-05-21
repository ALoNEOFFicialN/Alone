from discord import AllowedMentions, Intents
from colorama import Fore, Style, init
from discord.ext import commands
from tortoise import Tortoise
from .Context import Context
from typing import NoReturn
import aiohttp, asyncio, os
import config, asyncpg
from utils import cache
import traceback
import discord

init(autoreset=True)
intents = Intents.default()
intents.members = True


os.environ["JISHAKU_HIDE"] = "True"
os.environ["JISHAKU_NO_UNDERSCORE"] = "True"
os.environ["JISHAKU_NO_DM_TRACEBACK"] = "True"
print(Fore.RED + "-----------------------------------------------------")


class Quotient(commands.AutoShardedBot):
    def __init__(self, *args, **kwargs):
        super().__init__(
            command_prefix="!",
            intents=intents,
            max_messages=1000,
            strip_after_prefix=True,
            case_insensitive=True,
            chunk_guilds_at_startup=False,
            allowed_mentions=AllowedMentions(everyone=False, roles=False, replied_user=True, users=True),
            **kwargs,
        )

        asyncio.get_event_loop().run_until_complete(self.init_quo())
        self.loop = asyncio.get_event_loop()
        self.config = config
        self.color = config.COLOR

        for ext in self.config.EXTENSIONS:
            try:
                self.load_extension(ext)
                print(Fore.GREEN + f"[EXTENSION] {ext} was loaded successfully!")
            except Exception as e:
                tb = traceback.format_exception(type(e), e, e.__traceback__)
                tbe = "".join(tb) + ""
                print(Fore.RED + f"[WARNING] Could not load extension {ext}: {tbe}")
        print(Fore.RED + "-----------------------------------------------------")

    async def init_quo(self):
        self.session = aiohttp.ClientSession(loop=self.loop)
        self.db = await asyncpg.create_pool(**config.POSTGRESQL)
        await Tortoise.init(config.TORTOISE)
        await Tortoise.generate_schemas(safe=True)
        await cache(self)

        # TODO: create an autoclean timer or separate it per scrim maybe

        # Initializing Models (Assigning Bot attribute to all models)
        for mname, model in Tortoise.apps.get("models").items():
            model.bot = self

    async def close(self) -> NoReturn:
        await super().close()
        await self.session.close()

    async def process_commands(self, message):
        ctx = await self.get_context(message, cls=Context)

        if ctx.command is None:
            return

        await self.invoke(ctx)

    async def on_ready(self):  # yes we love colors and colorama
        print(Fore.RED + "------------------------------------------------------")
        print(Fore.BLUE + f"Logged in as {self.user.name}({self.user.id})")
        print(Fore.BLUE + f"Currently in {len(self.guilds)} Guilds")
        print(Fore.BLUE + f"Connected to {len(self.users)} Users")
        print(Fore.CYAN + f"Spawned {len(self.shards)} Shards")

    def embed(self, ctx: Context, **kwargs):
        """This is how we deliver features like custom footer and custom color :)"""
        embed_color = self.guild_data[ctx.guild.id]["color"]
        embed_footer = self.guild_data[ctx.guild.id]["footer"]
        kwargs.update(color=kwargs.pop("color", embed_color))

        embed = discord.Embed(**kwargs)
        embed.set_footer(text=embed_footer)

        return embed

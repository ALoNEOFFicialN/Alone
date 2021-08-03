from datetime import datetime, timedelta
from cogs.quomisc.helper import guild_msg_stats, member_msg_stats
from utils import emote, get_ipm, strtime, human_timedelta, split_list, checks, plural
from core import Cog, Quotient, Context
from models import Guild, Votes, Messages, User, Commands, Partner
from discord.ext import commands
from utils import ColorConverter, QuoUser
from collections import Counter
from typing import Optional
from constants import IST
from glob import glob
import inspect, time
from .dev import *
import discord
import psutil
import os


class Quomisc(Cog, name="quomisc"):
    def __init__(self, bot: Quotient):
        self.bot = bot

    @commands.command(aliases=("src",))
    async def source(self, ctx: Context, *, search: str = None):
        """Refer to the source code of the bot commands."""
        source_url = "https://github.com/quotientbot/Quotient-Bot"

        if search is None:
            return await ctx.send(f"<{source_url}>")

        command = ctx.bot.get_command(search)

        if not command:
            return await ctx.send("Couldn't find that command.")

        src = command.callback.__code__
        filename = src.co_filename
        lines, firstlineno = inspect.getsourcelines(src)

        location = os.path.relpath(filename).replace("\\", "/")

        final_url = f"<{source_url}/blob/main/{location}#L{firstlineno}-L{firstlineno + len(lines) - 1}>"
        await ctx.send(final_url)

    @commands.command(aliases=["cs"])
    async def codestats(self, ctx: Context):
        """See the code statictics of the bot."""
        ctr = Counter()

        for ctr["files"], f in enumerate(glob("./**/*.py", recursive=True)):
            with open(f, encoding="UTF-8") as fp:
                for ctr["lines"], line in enumerate(fp, ctr["lines"]):
                    line = line.lstrip()
                    ctr["imports"] += line.startswith("import") + line.startswith("from")
                    ctr["classes"] += line.startswith("class")
                    ctr["comments"] += "#" in line
                    ctr["functions"] += line.startswith("def")
                    ctr["coroutines"] += line.startswith("async def")
                    ctr["docstrings"] += line.startswith('"""') + line.startswith("'''")

        await ctx.send(
            embed=ctx.bot.embed(
                ctx,
                title="Code Stats",
                description="\n".join([f"**{k.capitalize()}:** {v}" for k, v in ctr.items()]),
            )
        )

    @commands.command()
    async def support(self, ctx):
        """
        Get the invite link of our support server.
        """
        await ctx.send(self.bot.config.SERVER)

    @commands.command()
    async def invite(self, ctx: Context):
        """Invite ME : )"""
        embed = self.bot.embed(ctx)
        embed.description = f"[Click Here to Invite Me]({self.bot.config.BOT_INVITE})\n[Click Here to join Support Server]({self.bot.config.SERVER_LINK})"
        await ctx.send(embed=embed)

    @commands.command()
    async def donate(self, ctx: Context):
        """Donate to Quotient"""
        await ctx.send(self.bot.config.DONATE_LINK, embed_perms=True)

    async def make_private_channel(self, ctx: Context) -> discord.TextChannel:
        support_link = f"[Support Server]({ctx.config.SERVER_LINK})"
        invite_link = f"[Invite Me]({ctx.config.BOT_INVITE})"
        vote_link = f"[Vote]({ctx.config.WEBSITE}/vote)"
        source = f"[Source]({ctx.config.REPOSITORY})"

        guild = ctx.guild
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, read_message_history=True),
            ctx.author: discord.PermissionOverwrite(read_messages=True, send_messages=True, read_message_history=True),
        }
        channel = await guild.create_text_channel(
            "quotient-private", overwrites=overwrites, reason=f"Made by {str(ctx.author)}"
        )
        webhook = await channel.create_webhook(
            name="Quotient", avatar=await ctx.me.avatar_url.read(), reason=f"Made by {str(ctx.author)}"
        )
        await Guild.filter(guild_id=ctx.guild.id).update(private_channel=channel.id, private_webhook=webhook.url)

        e = self.bot.embed(ctx)
        e.add_field(
            name="**What is this channel for?**",
            inline=False,
            value="This channel is made for Quotient to send important announcements and activities that need your attention. If anything goes wrong with any of my functionality I will notify you here. Important announcements from the developer will be sent directly here too.\n\nYou can test my commands in this channel if you like. Kindly don't delete it , some of my commands won't work without this channel.",
        )
        e.add_field(
            name="**__Important Links__**", value=f"{support_link} | {invite_link} | {vote_link} | {source}", inline=False
        )
        m = await channel.send(embed=e)
        await m.pin()

        return channel

    @commands.command(name="setup")
    @commands.has_permissions(manage_guild=True)
    @commands.bot_has_guild_permissions(manage_channels=True, manage_webhooks=True)
    async def setup_cmd(self, ctx: Context):
        """
        Setup Quotient in the current sever.
        This creates a private channel in the server. You can rename that if you like.
        Quotient requires manage channels and manage wehooks permissions for this to work.
        You must have manage server permission.
        """
        record = await Guild.get(guild_id=ctx.guild.id)
        if record.private_ch is not None:
            return await ctx.error(f"You already have a private channel ({record.private_ch.mention})")

        else:
            channel = await self.make_private_channel(ctx)
            await ctx.success(f"Created {channel.mention}")

    @commands.command()
    async def stats(self, ctx):
        """Quotient's statistics"""
        total_uses = await Commands.all().count()

        user_invokes = await Commands.filter(user_id=ctx.author.id, guild_id=ctx.guild.id).count() or 0

        server_invokes = await Commands.filter(guild_id=ctx.guild.id).count() or 0

        memory = psutil.virtual_memory().total >> 20
        mem_usage = psutil.virtual_memory().used >> 20
        cpu = str(psutil.cpu_percent())
        members = sum(g.member_count for g in self.bot.guilds)

        chnl_count = Counter(map(lambda ch: ch.type, self.bot.get_all_channels()))

        embed = self.bot.embed(
            ctx,
            title="Official Bot Server Invite",
            url=ctx.config.SERVER_LINK,
            description=f"Quotient has been up for `{self.get_bot_uptime(brief=False)}`."
            f"\nTotal of `{total_uses} commands` have been invoked and `{server_invokes} commands` were invoked in this server,"
            f" out of which `{user_invokes} commands` were invoked by you.\nBot can see `{len(self.bot.guilds)} guilds`, "
            f"`{members} users` and `{len(self.bot.users)} users` are cached.",
        )

        embed.add_field(name="System", value=f"**RAM**: {mem_usage}/{memory} MB\n**CPU:** {cpu}% used")
        embed.add_field(
            name="Channels",
            value="{} `{} channels`\n{} `{} channels`".format(
                emote.TextChannel,
                chnl_count[discord.ChannelType.text],
                emote.VoiceChannel,
                chnl_count[discord.ChannelType.voice],
            ),
        )
        embed.set_footer(
            text=f"Websocket latency: {round(self.bot.latency * 1000, 2)}ms | IPM: {round(get_ipm(ctx.bot), 2)}"
        )
        await ctx.send(embed=embed)

    def get_bot_uptime(self, *, brief=False):
        return human_timedelta(self.bot.start_time, accuracy=None, brief=brief, suffix=False)

    @commands.command()
    async def uptime(self, ctx):
        """Do you wonder when did we last restart Quotient?"""
        await ctx.send(
            f"**Uptime:** {self.get_bot_uptime(brief=False)}\n**Last Restart:** {strtime(self.bot.start_time)}"
        )

    @commands.command()
    async def ping(self, ctx: Context):
        """Check how the bot is doing"""

        ping_at = time.monotonic()
        message = await ctx.send("Pinging...")
        diff = "%.2f" % (1000 * (time.monotonic() - ping_at))

        emb = ctx.bot.embed(ctx)
        emb.add_field(name="Ping", value=f"`{diff} ms`")
        emb.add_field(
            name="Latency",
            value=f"`{round(self.bot.latency*1000, 2)} ms`",
        )

        await message.edit(content=None, embed=emb)

    @commands.command()
    async def voteremind(self, ctx: Context):
        check = await Votes.get_or_none(user_id=ctx.author.id)
        if check:
            await Votes.filter(user_id=ctx.author.id).update(reminder=not (check.reminder))
            await ctx.success(f"Turned vote-reminder {'ON' if not(check.reminder) else 'OFF'}!")
        else:
            await Votes.create(user_id=ctx.author.id, reminder=True)
            await ctx.success(f"Turned vote-reminder ON!")

    @commands.command()
    @commands.has_permissions(manage_guild=True)
    async def prefix(self, ctx, *, new_prefix: str):

        if len(new_prefix) > 5:
            return await ctx.error(f"Prefix cannot contain more than 5 characters.")

        self.bot.guild_data[ctx.guild.id]["prefix"] = new_prefix
        await Guild.filter(guild_id=ctx.guild.id).update(prefix=new_prefix)
        await ctx.success(f"Updated server prefix to: `{new_prefix}`")

    @commands.command()
    @commands.has_permissions(manage_guild=True)
    @checks.is_premium_guild()
    async def color(self, ctx, *, new_color: ColorConverter):
        color = int(str(new_color).replace("#", ""), 16)  # The hex value of a color.

        self.bot.guild_data[ctx.guild.id]["color"] = color
        await Guild.filter(guild_id=ctx.guild.id).update(embed_color=color)
        await ctx.success(f"Updated server color.")

    @commands.command()
    @checks.is_premium_guild()
    @commands.has_permissions(manage_guild=True)
    async def footer(self, ctx, *, new_footer: str):
        if len(new_footer) > 50:
            return await ctx.success(f"Footer cannot contain more than 50 characters.")

        self.bot.guild_data[ctx.guild.id]["footer"] = new_footer
        await Guild.filter(guild_id=ctx.guild.id).update(embed_footer=new_footer)
        await ctx.send(f"Updated server footer.")

    @commands.command(aliases=["modules", "exts"])
    async def extensions(self, ctx):
        """List of modules that work at a current time."""
        exts = split_list(self.bot.cogs, 3)
        length = max([len(element) for row in exts for element in row])
        rows = ("".join(e.ljust(length + 2) for e in row) for row in exts)
        embed = ctx.bot.embed(ctx, title=f"Currently working modules", description="```%s```" % "\n".join(rows))
        await ctx.send(embed=embed)

    @commands.command()
    async def money(self, ctx: Context):
        user = await User.get(user_id=ctx.author.id).only("user_id", "money")
        await ctx.simple(f"💰 | You own `{user.money} Quo Coins`.")

    @commands.command()
    async def shop(self, ctx: Context):
        embed = discord.Embed(color=self.bot.color)
        embed.set_footer(text=f"Use '{ctx.prefix}buy <item>' to buy something")
        embed.description = (
            f"<:premium:858728502634610708> **Quotient Premium** — [⏣ 120]({self.bot.config.SERVER_LINK})"
            f"\nGet a Quotient Premium redeem code, this can be used to upgrade any server with Quotient Premium for 1 Month."
        )
        await ctx.send(embed=embed, embed_perms=True)

    @commands.command()
    async def buy(self, ctx: Context, item: str):
        await ctx.error("This command is currently under development, will be available soon.")

    @commands.command()
    async def dashboard(self, ctx: Context):
        await ctx.send(
            f"Here is the direct link to this server's dashboard:\n<https://quotientbot.xyz/dashboard/{ctx.guild.id}>"
        )

    @commands.command()
    async def website(self, ctx: Context):
        return await ctx.send(f"<{self.bot.config.WEBSITE}>")

    @commands.command()
    async def vote(self, ctx: Context):
        await ctx.send(f"You can vote for me here:\n<https://quotientbot.xyz/vote>")

    @commands.group(aliases=("msg",), invoke_without_command=True)
    async def message(self, ctx: Context, user: Optional[QuoUser]):
        """
        This returns a total number of messages a user has sent in a server or globally.
        """
        user = user or ctx.author
        total = await Messages.filter(author_id=user.id).all().count() or 0
        server = await Messages.filter(author_id=user.id, guild_id=ctx.guild.id).all().count() or 0

        embed = self.bot.embed(ctx, title="📧 Messages")
        embed.description = (
            f"**{user}** has sent `{plural(server):message|messages}` in this server. (`{total}` Globally)"
        )
        await ctx.send(embed=embed, embed_perms=True)

    @message.command(name="for")
    async def msg_for(self, ctx: Context, user: Optional[QuoUser], days: Optional[int] = 7):
        """
        Returns no. of msges sent by a user withing some days.
        """
        user = user or ctx.author
        sent_at = datetime.now(tz=IST) - timedelta(days=days)

        total = await Messages.filter(author_id=user.id, sent_at__gte=sent_at).all().count() or 0
        server = await Messages.filter(author_id=user.id, guild_id=ctx.guild.id, sent_at__gte=sent_at).all().count() or 0

        embed = self.bot.embed(ctx, title=f"Messages for {plural(days):day|days}")
        embed.description = f"**{user}** has sent `{plural(server):message|messages}` in this server in last `{plural(days):day|days}`. (`{total}` Globally)"
        await ctx.send(embed=embed, embed_perms=True)

    @message.command(name="server")
    async def msg_server(self, ctx: Context, days: Optional[int]):
        """
        Returns no. of messages sent in a server.
        Days is an optional argument.
        """
        total = await Messages.filter(guild_id=ctx.guild.id).all().order_by("sent_at")
        bots = sum(1 for i in (msg for msg in total if msg.bot))

        embed = self.bot.embed(ctx, title="📧 Server Messages")
        embed.add_field(name="Total", value=sum(1 for i in total))
        embed.add_field(name="Bots", value=bots)
        embed.set_footer(text=f"Counting Since {strtime(total[0].sent_at)}")
        await ctx.send(embed=embed)

    @message.command(name="stats")
    async def msg_stats(self, ctx: Context, user: Optional[QuoUser]):
        """
        Returns message stats of the server or a user.
        """
        return await ctx.error("This command is currently under development.")
        if user:
            await member_msg_stats(ctx, user)
        else:
            await guild_msg_stats(ctx)

    # @commands.group(invoke_without_command=True)
    # async def partnership(self, ctx: Context):
    #     ...

    # @partnership.command(name="apply")
    # @commands.has_permissions(manage_guild=True)
    # async def partner_apply(self, ctx: Context):
    #     """
    #     Apply for a Quotient partnership program.
    #     """


def setup(bot) -> None:
    bot.add_cog(Quomisc(bot))
    bot.add_cog(Dev(bot))

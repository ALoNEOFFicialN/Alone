from __future__ import annotations
import typing
from cogs.esports.helpers.views import delete_slotmanager

if typing.TYPE_CHECKING:
    from core import Quotient

from core import Cog, Context
from contextlib import suppress
from .helpers import (
    delete_denied_message,
    log_scrim_ban,
    scrim_work_role,
    toggle_channel,
    scrim_end_process,
    tourney_work_role,
    registration_close_embed,
    registration_open_embed,
    setup_slotmanager,
    update_main_message,
    delete_slotmanager,
    MultiScrimConverter,
)

from utils import (
    inputs,
    checks,
    FutureTime,
    human_timedelta,
    get_chunks,
    QuoRole,
    QuoTextChannel,
    QuoUser,
    QuoPaginator,
    BetterFutureTime,
)

from constants import IST, ScrimBanType
from discord.ext.commands.cooldowns import BucketType
from models import *
from datetime import datetime, timedelta
from discord.ext import commands

from .events import ScrimEvents, TourneyEvents, TagEvents, SlotManagerEvents
from .errors import ScrimError, SMError, TourneyError, PointsError
from prettytable import PrettyTable

import discord
import config
from .menus import *
from .views import *


class ScrimManager(Cog, name="Esports"):
    def __init__(self, bot: Quotient):
        self.bot = bot

    async def cog_command_error(self, ctx, error):
        if isinstance(error, (ScrimError, TourneyError, PointsError)):
            return await ctx.error(error)

    @property
    def reminders(self):
        return self.bot.get_cog("Reminders")

    # ************************************************************************************************

    # ************************************************************************************************
    # @commands.command()
    # async def slotmanager(self, ctx):
    #     view = SlotManagerView()
    #     await ctx.send(embed=discord.Embed(description="hi bros"), view=view)

    @Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return

        if message.channel.id in self.bot.scrim_channels:
            scrim = await Scrim.get_or_none(registration_channel_id=message.channel.id)
            if not scrim or not scrim.opened_at:  # either scrim doesn't exist or it is closed.
                return

            if not message.id in (record.message_id for record in await scrim.assigned_slots.all()):
                return

            slot = [
                slot
                for slot in await scrim.assigned_slots.all()
                if slot.user_id == message.author.id and slot.message_id == message.id
            ]
            if not slot:  # means their registration was denied
                return
            slot = slot[0]

            self.bot.dispatch("scrim_registration_delete", scrim, message, slot)

    # ************************************************************************************************

    @commands.group(aliases=("s", "sm"), invoke_without_command=True)
    async def smanager(self, ctx):
        """
        Contains commands related to Quotient's powerful scrims manager.
        """
        await ctx.send_help(ctx.command)

    @staticmethod
    def config_embed(value, description: str):
        embed = discord.Embed(
            color=discord.Color(config.COLOR),
            title=f"🛠️ Scrims Manager ({value}/6)",
            description=description,
        )
        embed.set_footer(text=f'Reply with "cancel" to stop the process.')
        return embed

    # ************************************************************************************************

    @smanager.command(name="setup")
    @checks.can_use_sm()
    @checks.has_done_setup()
    @commands.bot_has_guild_permissions(manage_channels=True, manage_roles=True, add_reactions=True)
    @commands.max_concurrency(1, BucketType.guild)
    async def s_setup(self, ctx: Context):
        """
        Setup Scrims Manager for a channel.
        Without premium you can setup scrims manager for upto 3 channels, however with Quotient Premium there isn't any limit.
        """
        count = await Scrim.filter(guild_id=ctx.guild.id).count()

        guild = await Guild.get(guild_id=ctx.guild.id)

        if count >= 3 and not guild.is_premium:
            raise ScrimError(
                f"You need to upgrade to Quotient Premium to host more than 3 scrims.\n{self.bot.config.WEBSITE}/premium"
            )

        def check(message: discord.Message):
            if message.content.strip().lower() == "cancel":
                raise ScrimError("Alright, reverting all process.")

            return message.author == ctx.author and ctx.channel == message.channel

        # Registration Channel.
        scrim = Scrim(
            guild_id=ctx.guild.id,
            host_id=ctx.author.id,
        )
        await ctx.send(
            embed=self.config_embed(
                1,
                "Which is the default registration channel?",
            )
        )
        channel = await inputs.channel_input(ctx, check)

        if await Scrim.filter(registration_channel_id=channel.id).count():
            raise ScrimError("This channel is already a registration channel.")

        if not channel.permissions_for(ctx.me).manage_channels:
            raise ScrimError(f"I require `manage channels` permission in **{channel}**.")

        scrim.registration_channel_id = channel.id

        # Slotlist Channel
        await ctx.send(
            embed=self.config_embed(
                2,
                f"Which is default slotlist channel for {scrim.registration_channel.mention}?",
            )
        )

        channel = await inputs.channel_input(ctx, check)

        scrim.slotlist_channel_id = channel.id

        # Role (Registered Users)
        await ctx.send(
            embed=self.config_embed(
                3,
                f"What role should I give for correct registration?",
            )
        )

        role = await inputs.role_input(ctx, check)

        scrim.role_id = role.id

        # Mentions Limit

        await ctx.send(
            embed=self.config_embed(
                4,
                "How many mentions are required for successful registration?" " (Can't be more than 10 or less than 0.)",
            )
        )

        scrim.required_mentions = await inputs.integer_input(
            ctx,
            check,
            limits=(0, 10),
        )

        # Total Slots

        await ctx.send(
            embed=self.config_embed(
                5,
                "How many total slots are there? (Can't be more than 30 or less than 1.)",
            )
        )

        scrim.total_slots = await inputs.integer_input(
            ctx,
            check,
            limits=(1, 30),
        )

        await ctx.send(
            embed=self.config_embed(
                6,
                "**At what time should I open registrations?**"
                "\n> Time must be in 24h and in this format **`hh:mm`**\n"
                "**Example: 14:00** - Registration will open at 2PM.\n\n"
                "**Currently Quotient works according to Indian Standard Time (UTC+05:30)**",
            )
        )
        scrim.open_time = await inputs.time_input(ctx, check)

        registration_channel = scrim.registration_channel

        fields = (
            f"Registration Channel: {registration_channel.mention}",
            f"Slotlist Channel: {scrim.slotlist_channel.mention}",
            f"Role: {scrim.role.mention}",
            f"Minimum Mentions: {scrim.required_mentions}",
            f"Slots: {scrim.total_slots}",
            f"Open Time: {time(scrim.open_time)}",
        )

        title = "Are these correct?"
        description = "\n".join(f"`{idx}.` {field}" for idx, field in enumerate(fields, start=1))

        confirm = await ctx.prompt(description, title=title)
        if not confirm:
            await ctx.send("Ok, Aborting!")
        else:
            message = await ctx.send("Setting up everything!")
            reason = "Created for scrims management."

            # Scrims MODS
            scrims_mod = discord.utils.get(ctx.guild.roles, name="scrims-mod")

            if scrims_mod is None:
                scrims_mod = await ctx.guild.create_role(name="scrims-mod", color=0x00FFB3, reason=reason)

            overwrite = registration_channel.overwrites_for(ctx.guild.default_role)
            overwrite.update(read_messages=True, send_messages=True, read_message_history=True)
            await registration_channel.set_permissions(scrims_mod, overwrite=overwrite)

            # Srims LOGS
            scrims_log_channel = discord.utils.get(ctx.guild.text_channels, name="quotient-scrims-logs")

            if scrims_log_channel is None:
                guild = ctx.guild
                overwrites = {
                    guild.default_role: discord.PermissionOverwrite(read_messages=False),
                    guild.me: discord.PermissionOverwrite(read_messages=True),
                    scrims_mod: discord.PermissionOverwrite(read_messages=True),
                }
                scrims_log_channel = await ctx.guild.create_text_channel(
                    name="quotient-scrims-logs",
                    overwrites=overwrites,
                    reason=reason,
                )

                # Sending Message to scrims-log-channel
                note = await scrims_log_channel.send(
                    embed=discord.Embed(
                        description=f"If events related to scrims i.e opening registrations or adding roles, "
                        f"etc are triggered, then they will be logged in this channel. "
                        f"Also I have created {scrims_mod.mention}, you can give that role to your "
                        f"scrims-moderators. User with {scrims_mod.mention} can also send messages in "
                        f"registration channels and they won't be considered as scrims-registration.\n\n"
                        f"`Note`: **Do not rename this channel.**",
                        color=discord.Color(config.COLOR),
                    )
                )
                await note.pin()

            await scrim.save()
            await self.reminders.create_timer(scrim.open_time, "scrim_open", scrim_id=scrim.id)
            text = f"Scrims Management Setup Complete. (`Scrims ID: {scrim.id}`)"
            try:
                await message.edit(content=text)
            except discord.NotFound:
                await ctx.send(text)

    # ************************************************************************************************

    @smanager.command(name="edit")
    @checks.has_done_setup()
    @commands.bot_has_permissions(embed_links=True, manage_messages=True)
    @checks.can_use_sm()
    async def s_edit(self, ctx, *, scrim: Scrim):
        """
        Edit scrims manager config for a scrim.
        """
        menu = ConfigEditMenu(scrim=scrim)
        await menu.start(ctx)

    # ************************************************************************************************

    @smanager.command(name="days")
    @checks.can_use_sm()
    @checks.has_done_setup()
    @commands.bot_has_permissions(embed_links=True, manage_messages=True)
    async def s_days(self, ctx, *, scrim: Scrim):
        """
        Edit open days for a scrim.
        """
        menu = DaysMenu(scrim=scrim)
        await menu.start(ctx)

    # @smanager.command(name="open")
    # async def s_open(self, ctx, scrim_id: int):
    #     pass

    @smanager.command(name="close")
    @checks.can_use_sm()
    @checks.has_done_setup()
    @commands.bot_has_permissions(embed_links=True, manage_channels=True)
    async def s_close(self, ctx, scrim: Scrim):
        """
        Close a scrim immediately, even if the slots aren't full.
        """
        if scrim.opened_at is None:
            return await ctx.error(f"Scrim `({scrim.id})` is already closed.")
        prompt = await ctx.prompt(f"Are you sure you want to close Scrim: `{scrim.id}`?")
        if prompt:
            await scrim_end_process(ctx, scrim)
            await ctx.message.add_reaction(emote.check)

        else:
            await ctx.success("Ok!")

    @smanager.command(name="config")
    @checks.can_use_sm()
    @checks.has_done_setup()
    @commands.cooldown(5, 1, type=commands.BucketType.user)
    @commands.bot_has_permissions(embed_links=True, manage_messages=True)
    async def s_config(self, ctx):
        """
        Get config of all the scrims you have setup.
        """
        allscrims = await Scrim.filter(guild_id=ctx.guild.id).all()

        if not allscrims:
            return await ctx.send(
                f"You do not have any scrims setup on this server.\n\nKindly use `{ctx.prefix}smanager setup` to setup one."
            )

        paginator = QuoPaginator(ctx, title=f"Total Scrims: {len(allscrims)}", per_page=1)
        for idx, scrim in enumerate(allscrims, start=1):
            reg_channel = getattr(scrim.registration_channel, "mention", "`Channel Deleted!`")
            slot_channel = getattr(scrim.slotlist_channel, "mention", "`Channel Deleted!`")

            role = getattr(scrim.role, "mention", "`Role Deleted!`")
            open_time = (scrim.open_time).strftime("%I:%M %p")
            open_role = scrim_work_role(scrim, constants.EsportsRole.open)
            ping_role = scrim_work_role(scrim, constants.EsportsRole.ping)
            mystring = f"> Scrim ID: `{scrim.id}`\n> Name: `{scrim.name}`\n> Registration Channel: {reg_channel}\n> Slotlist Channel: {slot_channel}\n> Role: {role}\n> Mentions: `{scrim.required_mentions}`\n> Total Slots: `{scrim.total_slots}`\n> Open Time: `{open_time}`\n> Toggle: `{scrim.stoggle}`\n> Open Role: {open_role}\n> Ping Role: {ping_role}\n> Slotlist start from: {scrim.start_from}"

            paginator.add_line(f"**`<<<<<<-- {idx:02d}. -->>>>>>`**\n{mystring}")

        await paginator.start()

    # ************************************************************************************************

    @smanager.command(name="toggle")
    @checks.can_use_sm()
    @checks.has_done_setup()
    async def s_toggle(self, ctx, scrim: Scrim, option: str = None):
        """
        Toggle on/off things for a scrim.
        """
        valid_opt = ("scrim", "ping", "openrole", "autoclean", "autoslotlist", "multiregister")
        display = ",".join(map(lambda s: f"`{s}`", valid_opt))
        display_msg = f"Valid options are:\n{display}\n\nUsage Example: `smanager toggle {scrim.id} scrim`"

        if not option or option.lower() not in valid_opt:
            return await ctx.send(display_msg)

        stoggle = scrim.stoggle
        ping = scrim.ping_role_id
        openrole = scrim.open_role_id
        autoclean = scrim.autoclean

        if option.lower() == "scrim":
            await Scrim.filter(pk=scrim.id).update(stoggle=not (stoggle))
            await ctx.success(f"Scrim is now {'OFF' if stoggle else 'ON'}")

        elif option.lower() == "ping":
            if ping is None:
                return await ctx.error(f"Ping Role is not set.")

            await Scrim.filter(pk=scrim.id).update(ping_role_id=None)
            await ctx.success(f"Ping Role turned OFF.")

        elif option.lower() == "openrole":
            if openrole is None:
                return await ctx.error(f"Open Role is not set.")

            await Scrim.filter(pk=scrim.id).update(open_role_id=None)
            await ctx.success(f"Open Role set to {ctx.guild.default_role.mention}")

        elif option.lower() == "autoclean":
            await Scrim.filter(pk=scrim.id).update(autoclean=not (autoclean))
            await ctx.success(f"Autoclean turned {'OFF' if autoclean else 'ON'}")

        elif option.lower() == "autoslotlist":
            await Scrim.filter(pk=scrim.id).update(autoslotlist=not (scrim.autoslotlist))
            await ctx.success(f"Autopost-slotlist turned {'OFF' if scrim.autoslotlist else 'ON'}!")

        elif option.lower() == "multiregister":
            await Scrim.filter(pk=scrim.id).update(multiregister=not (scrim.multiregister))
            await ctx.success(f"Multiple registerations turned {'OFF' if scrim.multiregister else 'ON'}!")

    # ************************************************************************************************
    @smanager.group(name="slotlist", invoke_without_command=True)
    async def s_slotlist(self, ctx):
        """
        Create/ Edit or Send a scrim slotlist.
        """
        await ctx.send_help(ctx.command)

    @s_slotlist.command(name="show")
    async def s_slotlist_show(self, ctx, scrim: Scrim):
        """
        Show slotlist of a scrim.
        """
        if not await scrim.teams_registered.count():
            return await ctx.error("Nobody registered yet!")

        embed, channel = await scrim.create_slotlist()
        await ctx.send(embed=embed, embed_perms=True)

    @s_slotlist.command(name="send")
    @checks.can_use_sm()
    @checks.has_done_setup()
    async def s_slotlist_send(self, ctx, scrim: Scrim, channel: QuoTextChannel = None):
        """
        Send slotlist of a scrim.
        """
        if not await scrim.teams_registered.count():
            return await ctx.error("Nobody registered yet!")
        embed, schannel = await scrim.create_slotlist()
        channel = channel or schannel

        await ctx.send(embed=embed)
        prompt = await ctx.prompt("This is how the slotlist looks. Should I send it?")
        if prompt:
            if channel is not None and channel.permissions_for(ctx.me).send_messages:
                await channel.send(embed=embed)
                await ctx.success("Slotlist sent successfully!")
            else:
                await ctx.error(f"I can't send messages in {channel}")
        else:
            await ctx.success("Ok!")

    @s_slotlist.command(name="edit")
    @checks.can_use_sm()
    @checks.has_done_setup()
    @commands.cooldown(5, 1, type=commands.BucketType.user)
    @commands.bot_has_permissions(embed_links=True, manage_messages=True)
    async def s_slotlist_edit(self, ctx, scrim: Scrim):
        """
        Edit a slotlist
        """
        if not await scrim.teams_registered.count():
            return await ctx.error("Nobody registered yet!")

        embed, channel = await scrim.create_slotlist()

        view = SlotlistEditor(ctx,scrim)
        view.message = await ctx.send(embed=embed, view=view)

    @s_slotlist.command(name="format")
    @checks.can_use_sm()
    @checks.has_done_setup()
    @commands.cooldown(5, 1, type=commands.BucketType.user)
    @commands.bot_has_permissions(embed_links=True, manage_messages=True)
    async def s_slotlist_format(self, ctx, scrim: Scrim):
        """Set a default format for scrim slotlist."""
        menu = SlotlistFormatMenu(scrim=scrim)
        await menu.start(ctx)

    @s_slotlist.command(name="image")
    @checks.can_use_sm()
    @checks.has_done_setup()
    @commands.cooldown(10, 1, type=commands.BucketType.user)
    @commands.bot_has_permissions(embed_links=True, attach_files=True)
    async def s_slotlist_image(self, ctx, scrim: Scrim):
        """
        Get image version of a slotlist.
        """
        if not await scrim.teams_registered.count():
            return await ctx.error("Nobody registered yet!")

        files = await scrim.create_slotlist_img()
        for file in files:
            await ctx.send(file=file)

    # ************************************************************************************************
    @smanager.command(name="delete")
    @checks.can_use_sm()
    @checks.has_done_setup()
    async def s_delete(self, ctx, scrim: Scrim):
        """
        Completely delete a scrim.
        """
        prompt = await ctx.prompt(
            f"Are you sure you want to delete scrim `{scrim.id}`?",
        )
        if prompt:
            self.bot.scrim_channels.discard(scrim.registration_channel_id)
            await scrim.delete()
            await ctx.success(f"Scrim (`{scrim.id}`) deleted successfully.")
        else:
            await ctx.success(f"Alright! Aborting")

    @smanager.command(name="ban")
    @checks.can_use_sm()
    @checks.has_done_setup()
    async def s_ban(self, ctx: Context, scrim: MultiScrimConverter, user: QuoUser, *, time: FutureTime = None):
        """
        Ban someone from the scrims temporarily or permanently.
        Time argument is optional, use `all` in place of scrim id if you want to ban from all scrims.
        """
        expire_time = time.dt + timedelta(seconds=10) if time else None

        if len(scrim) == 1 and user.id in await scrim[0].banned_user_ids():
            return await ctx.send(
                f"**{str(user)}** is already banned from the scrims.\n\n"
                f"Use `{ctx.prefix}smanager unban {scrim.id} {str(user)}` to unban them."
            )

        prompt = await ctx.prompt("Do you want to give a reason for the ban?")
        reason = None
        if prompt:
            await ctx.send("Enter reason:")
            reason = await inputs.string_input(ctx, lambda msg: msg.author == ctx.author and msg.channel == ctx.channel)

        scrims = []
        for s in scrim:
            if not user.id in await s.banned_user_ids():
                ban = await BannedTeam.create(user_id=user.id, expires=expire_time, reason=reason)
                await s.banned_teams.add(ban)
                scrims.append(s)

        if not scrims:
            return await ctx.send(
                f"**{str(user)}** is already banned from all scrims.\n\n"
                f"Use `{ctx.prefix}smanager unban all {str(user)}` to unban them."
            )

        if time is not None:
            await self.reminders.create_timer(
                expire_time,
                "scrim_ban",
                scrims=[scrim.id for scrim in scrims],
                user_id=user.id,
                mod=ctx.author.id,
                reason=reason,
            )

        format = "\n".join(
            (
                f"✅ Scrim {scrim.id}: {getattr(scrim.registration_channel, 'mention','deleted-channel')}"
                for scrim in scrims
            )
        )
        await ctx.success(
            f"**{user}** has been successfully banned {'for ' if time else ''}{human_timedelta(expire_time) if time else '' } "
            f"from:\n{format}"
        )

        if logs := await ctx.banlog_channel:
            return await log_scrim_ban(
                logs, scrims, ScrimBanType.ban, user, reason=reason, mod=ctx.author, expire_time=expire_time
            )

    @smanager.command(name="unban")
    @checks.can_use_sm()
    @checks.has_done_setup()
    async def s_unban(self, ctx: Context, scrim: MultiScrimConverter, user: QuoUser, *, reason: str = None):
        """
        Unban a banned team from a scrim.
        Use `all` to unban from all scrims.
        """
        if len(scrim) == 1 and not user.id in await scrim[0].banned_user_ids():
            return await ctx.send(
                f"**{str(user)}** is not banned.\n\nUse `{ctx.prefix}smanager ban all {str(user)}` to ban them."
            )

        scrims = []
        for s in scrim:
            ban = await s.banned_teams.filter(user_id=user.id).first()
            if ban:
                await BannedTeam.filter(id=ban.id).delete()
                scrims.append(s)

        if not scrims:
            return await ctx.send(
                f"**{str(user)}** is not banned from scrims.\n\n"
                f"Use `{ctx.prefix}smanager ban all {str(user)}` to ban them."
            )

        format = "\n".join(
            (
                f"✅ Scrim {scrim.id}: {getattr(scrim.registration_channel, 'mention','deleted-channel')}"
                for scrim in scrims
            )
        )

        await ctx.success(f"Successfully unbanned {str(user)} from \n" f"{format}")

        if logs := await ctx.banlog_channel:
            return await log_scrim_ban(logs, scrims, ScrimBanType.unban, user, mod=ctx.author, reason=reason)

    @smanager.group(name="reserve", invoke_without_command=True)
    @commands.max_concurrency(1, BucketType.guild)
    @checks.can_use_sm()
    @checks.has_done_setup()
    @commands.bot_has_permissions(embed_links=True, manage_messages=True)
    async def s_reserve(self, ctx, scrim: Scrim):
        """
        Add / Remove a team from the reserved list
        """
        menu = ReserveEditorMenu(scrim=scrim)
        await menu.start(ctx)

    @s_reserve.command(name="list", aliases=("all",))
    @checks.can_use_sm()
    @checks.has_done_setup()
    async def s_reverse_list(self, ctx, scrim: Scrim):
        """
        Get a list of all reserved teams and their leaders.
        """
        if not sum(await scrim.reserved_user_ids()):
            return await ctx.error("None of the slots is reserved.")

        users = ""
        for idx, user in enumerate(await scrim.reserved_slots.all(), start=1):
            owner = ctx.guild.get_member(user.user_id) or self.bot.get_user(user.user_id)
            users += (
                f"`{idx:02d}`| {user.team_name.title()} ({getattr(owner,'mention','Not Found')}) [Slot: {user.num}]\n"
            )

        embed = discord.Embed(color=config.COLOR, description=users, title=f"Reserved Slots: {scrim.id}")
        await ctx.send(embed=embed)

    @smanager.command(name="autoclean")
    @checks.can_use_sm()
    @checks.has_done_setup()
    @commands.bot_has_permissions(embed_links=True, manage_messages=True)
    async def s_autoclean(self, ctx, scrim: Scrim):
        """Commands related to quotient's autoclean"""
        await AutocleanMenu(scrim=scrim).start(ctx)

    @smanager.command(name="info")
    async def s_info(self, ctx: Context, scrim: Scrim):
        """Get information about a scrim."""
        text = (
            f"> Name: `{scrim.name}`\n> Registration Channel: {getattr(scrim.registration_channel,'mention','`Channel Not Found`')}\n"
            f"> Slotlist Channel: {getattr(scrim.slotlist_channel,'mention','`Channel Not Found`')}\n"
            f"> Total Slots: `{scrim.total_slots}`\n\nRegistration status?"
        )
        if scrim.opened_at:
            text += f"\n> `Open!` ({strtime(scrim.opened_at)})\n> Slots Left: {len(scrim.available_slots)}"

        elif scrim.closed_at:
            text += f"\n> `Closed!` ({strtime(scrim.closed_at)})"

        else:
            text += "\n> Will be available after next registrations!"

        banned = [x.user_id for x in await scrim.banned_teams]
        text += f"\n\n> Reserved Slots: `{sum(1 for i in (x.user_id for x in await scrim.reserved_slots))}`"
        text += f"\n> Banned Users: `{len(banned)}` "
        if banned:
            text += ", ".join((getattr(x, "mention", "Not Found!") for x in map(self.bot.get_user, banned)))

        embed = self.bot.embed(ctx, title="Scrims Info: ({0})".format(scrim.id))
        embed.description = text
        await ctx.send(embed=embed, embed_perms=True)

    @smanager.command(name="openmsg")
    @checks.can_use_sm()
    async def s_openmsg(self, ctx: Context, scrim: Scrim):
        """See/edit scrim registration open msg"""
        await ctx.send(
            content=f"**THIS MESSAGE MIGHT DIFFER THE ACTUAL OPEN MESSAGE**\nUse our dashboard to edit this embed: https://quotientbot.xyz/dashboard/{ctx.guild.id}/scrims",
            embed=await registration_open_embed(scrim),
        )

    @smanager.command(name="closemsg")
    @checks.can_use_sm()
    async def s_closemsg(self, ctx: Context, scrim: Scrim):
        """See/edit scrim registration close msg"""
        await ctx.send(
            content=f"**THIS MESSAGE MIGHT DIFFER THE ACTUAL CLOSE MESSAGE**\nUse our dashboard to edit this embed: https://quotientbot.xyz/dashboard/{ctx.guild.id}/scrims",
            embed=registration_close_embed(scrim),
        )

    # ************************************************************************************************
    # ************************************************************************************************
    # ************************************************************************************************
    # ************************************************************************************************
    # ************************************************************************************************
    # ************************************************************************************************
    # ************************************************************************************************

    @staticmethod
    def tcembed(value, description: str):
        embed = discord.Embed(
            color=discord.Color(config.COLOR),
            title=f"🛠️ Tournament Manager ({value}/5)",
            description=description,
        )
        embed.set_footer(text=f'Reply with "cancel" to stop the process.')
        return embed

    @commands.group(invoke_without_command=True, aliases=("tm", "t"))
    async def tourney(self, ctx):
        """Quotient's Awesome tournament commands"""
        await ctx.send_help(ctx.command)

    @tourney.command(name="create", aliases=("setup",))
    @checks.can_use_tm()
    @checks.has_done_setup()
    @commands.bot_has_permissions(embed_links=True, manage_channels=True, manage_roles=True)
    async def t_create(self, ctx):
        """
        Create or setup tournaments
        """
        count = await Tourney.filter(guild_id=ctx.guild.id).count()
        guild = await Guild.get(guild_id=ctx.guild.id)
        if count >= 2 and not guild.is_premium:
            raise TourneyError("You can't have more than 2 tournaments concurrently.")

        def check(message: discord.Message):
            if message.content.strip().lower() == "cancel":
                raise TourneyError("Alright, reverting all process.")

            return message.author == ctx.author and ctx.channel == message.channel

        tourney = Tourney(
            guild_id=ctx.guild.id,
            host_id=ctx.author.id,
        )
        await ctx.send(embed=self.tcembed(1, "Which is the default registeration channel?"))
        channel = await inputs.channel_input(ctx, check)

        if await Tourney.filter(registration_channel_id=channel.id).count():
            raise TourneyError(f"**{channel}** is already a registration channel.")

        if not channel.permissions_for(ctx.me).manage_channels:
            raise TourneyError(f"I require `manage channels` permission in **{channel}**.")

        tourney.registration_channel_id = channel.id

        await ctx.send(embed=self.tcembed(2, "Which is the confirmed teams channel?"))
        channel = await inputs.channel_input(ctx, check)

        tourney.confirm_channel_id = channel.id

        await ctx.send(
            embed=self.tcembed(
                3,
                f"What role should I give for correct registration?",
            )
        )

        role = await inputs.role_input(ctx, check)

        tourney.role_id = role.id

        # Mentions Limit

        await ctx.send(
            embed=self.tcembed(
                4,
                "How many mentions are required for successful registration?" " (Can't be more than 10 or less than 0.)",
            )
        )

        tourney.required_mentions = await inputs.integer_input(
            ctx,
            check,
            limits=(0, 10),
        )

        # Total Slots

        await ctx.send(
            embed=self.tcembed(
                5,
                "How many total slots are there? (Can't be more than 5000 or less than 1.)",
            )
        )

        tourney.total_slots = await inputs.integer_input(
            ctx,
            check,
            limits=(1, 5000),
        )

        fields = [
            f"Registration Channel: {tourney.registration_channel}",
            f"Slotlist Channel: {tourney.confirm_channel}",
            f"Role: {tourney.role}",
            f"Minimum Mentions: {tourney.required_mentions}",
            f"Slots: {tourney.total_slots}",
        ]

        title = "Are these correct?"
        description = "\n".join(f"`{idx}.` {field}" for idx, field in enumerate(fields, start=1))

        confirm = await ctx.prompt(description, title=title)
        if not confirm:
            await ctx.send("Ok, Aborting!")
        else:
            message = await ctx.send("Setting up everything!")
            reason = "Created for tournament management."

            # Tourney MODS
            tourney_mod = discord.utils.get(ctx.guild.roles, name="tourney-mod")

            if tourney_mod is None:
                tourney_mod = await ctx.guild.create_role(name="tourney-mod", color=0x00FFB3, reason=reason)

            overwrite = tourney.registration_channel.overwrites_for(ctx.guild.default_role)
            overwrite.update(read_messages=True, send_messages=True, read_message_history=True)
            await tourney.registration_channel.set_permissions(tourney_mod, overwrite=overwrite)

            # Tourney LOGS
            tourney_log_channel = discord.utils.get(ctx.guild.text_channels, name="quotient-tourney-logs")

            if tourney_log_channel is None:
                guild = ctx.guild
                overwrites = {
                    guild.default_role: discord.PermissionOverwrite(read_messages=False),
                    guild.me: discord.PermissionOverwrite(read_messages=True),
                    tourney_mod: discord.PermissionOverwrite(read_messages=True),
                }
                scrims_log_channel = await ctx.guild.create_text_channel(
                    name="quotient-tourney-logs",
                    overwrites=overwrites,
                    reason=reason,
                )

                # Sending Message to tourney-log-channel
                note = await scrims_log_channel.send(
                    embed=discord.Embed(
                        description=f"If events related to tournament i.e opening registrations or adding roles, "
                        f"etc are triggered, then they will be logged in this channel. "
                        f"Also I have created {tourney_mod.mention}, you can give that role to your "
                        f"tourney-moderators. User with {tourney_mod.mention} can also send messages in "
                        f"registration channels and they won't be considered as tourney-registration.\n\n"
                        f"`Note`: **Do not rename this channel.**",
                        color=discord.Color(config.COLOR),
                    )
                )
                await note.pin()

            await tourney.save()
            text = f"Tourney Management Setup Complete. (`Tourney ID: {tourney.id}`)\nUse `{ctx.prefix}tourney start {tourney.id}` to start the tourney."
            try:
                await message.edit(content=text)
            except discord.NotFound:
                await ctx.send(text)

    @tourney.command(name="config")
    @checks.can_use_tm()
    @checks.has_done_setup()
    @commands.bot_has_permissions(embed_links=True, manage_messages=True)
    async def tourney_config(self, ctx):
        """Get config of all running tourneys"""
        records = await Tourney.filter(guild_id=ctx.guild.id).all()
        if not records:
            raise TourneyError(
                f"You do not have any tourney setup on this server.\n\nKindly use `{ctx.prefix}tourney create` to create one."
            )

        paginator = QuoPaginator(ctx, title=f"Total Tourneys: {len(records)}", per_page=1)
        for idx, tourney in enumerate(records, start=1):
            reg_channel = getattr(tourney.registration_channel, "mention", "`Channel Deleted!`")
            slot_channel = getattr(tourney.confirm_channel, "mention", "`Channel Deleted!`")

            role = getattr(tourney.role, "mention", "`Role Deleted!`")
            open_role = tourney_work_role(tourney)
            mystring = f"> Tourney ID: `{tourney.id}`\n> Name: `{tourney.name}`\n> Registration Channel: {reg_channel}\n> Confirm Channel: {slot_channel}\n> Role: {role}\n> Mentions: `{tourney.required_mentions}`\n> Total Slots: `{tourney.total_slots}`\n> Open Role: {open_role}\n> Status: {'Open' if tourney.started_at else 'Closed'}"

            paginator.add_line(f"**`<<<<<<-- {idx:02d}. -->>>>>>`**\n{mystring}")

        await paginator.start()

    @tourney.command(name="delete")
    @checks.can_use_tm()
    @checks.has_done_setup()
    async def tourney_delete(self, ctx, tourney_id: Tourney):
        """Delete a tournament"""
        tourney = tourney_id
        prompt = await ctx.prompt(
            f"Are you sure you want to delete tournament `{tourney.id}`?",
        )
        if prompt:
            self.bot.tourney_channels.discard(tourney.registration_channel_id)
            await tourney.delete()
            await ctx.success(f"Tourney (`{tourney.id}`) deleted successfully.")
        else:
            await ctx.success(f"Alright! Aborting")

    @tourney.command(name="groups")
    @checks.can_use_tm()
    @checks.has_done_setup()
    @commands.bot_has_permissions(embed_links=True, attach_files=True)
    async def tourney_group(self, ctx, tourney: Tourney, group_size: int = 20):
        """Get groups of the tournament."""
        records = await tourney.assigned_slots.all().order_by("id")
        if not records:
            raise TourneyError(f"There is no data to show as nobody registered yet!")

        m = await ctx.send(f"{emote.loading} | This may take some time. Please wait.")

        tables = []

        for record in get_chunks(records, group_size):
            x = PrettyTable()
            x.field_names = ["Slot", "Registered Posi.", "Team Name", "Leader"]
            for idx, i in enumerate(record, start=1):
                member = ctx.guild.get_member(i.leader_id)
                x.add_row([idx, i.num, i.team_name, str(member)])

            tables.append(str(x))

        await inputs.safe_delete(m)
        await ctx.send_file("\n\n\n\n\n".join(tables), name="slotlist.text")

    @tourney.command(name="data")
    @checks.can_use_tm()
    @checks.has_done_setup()
    @commands.bot_has_permissions(embed_links=True, attach_files=True)
    async def tourney_data(self, ctx, tourney: Tourney):
        """Get all the data that Quotient collected for a tourney."""
        records = await tourney.assigned_slots.all().order_by("id")
        if not records:
            raise TourneyError(f"There is no data to show as nobody registered yet!")

        m = await ctx.send(f"{emote.loading} | This may take some time. Please wait.")

        y = PrettyTable()
        y.field_names = ["S No.", "Team Name", "Team Owner", "Teammates", " All Teammates in Server", "Jump URL"]

        for idx, record in enumerate(records, start=1):
            leader = str(ctx.guild.get_member(record.leader_id))

            if not record.members:
                teammates = "No Teammates!"
                all_here = "No team :("

            else:
                teamlist = tuple(map(ctx.guild.get_member, record.members))
                teammates = ", ".join(tuple(map(str, teamlist)))
                all_here = ("No!", "Yes!")[all(teamlist)]

            y.add_row([idx, record.team_name, leader, teammates, all_here, record.jump_url])

        await inputs.safe_delete(m)
        await ctx.send_file(str(y), name="tourney_data.txt")

    @tourney.command(name="list", aliases=("all",))
    @checks.can_use_tm()
    @checks.has_done_setup()
    @commands.bot_has_permissions(embed_links=True, manage_messages=True)
    async def tourney_list(self, ctx):
        """A list of all running tournaments."""
        records = await Tourney.filter(guild_id=ctx.guild.id).all()
        if not records:
            raise TourneyError(
                f"You do not have any tourney setup on this server.\n\nKindly use `{ctx.prefix}tourney create` to create one."
            )

        e = self.bot.embed(ctx)
        e.description = ""
        for count, i in enumerate(records, 1):
            channel = getattr(i.registration_channel, "mention", "`Deleted Channel!`")
            e.description += f"`{count}. ` | {channel} | Tourney ID: `{i.id}`"

        await ctx.send(embed=e)

    @tourney.command(name="rmslot", aliases=("deleteslot",))
    @checks.can_use_tm()
    @checks.has_done_setup()
    async def tourney_deleteslot(self, ctx, tourney: Tourney, *, user: discord.User):
        """Remove someone's slot"""
        slot = await tourney.assigned_slots.filter(leader_id=user.id).first()
        if not slot:
            raise TourneyError(f"**{user}** has no slot in Tourney (`{tourney.id}`)")

        prompt = await ctx.prompt(f"**{slot.team_name}** ({user.mention}) slot will be deleted.")
        if prompt:
            await TMSlot.filter(id=slot.id).delete()
            await ctx.success(f"Slot deleted!")

        else:
            await ctx.success(f"Ok!")

    @tourney.command(name="edit")
    @checks.can_use_tm()
    @checks.has_done_setup()
    @commands.bot_has_permissions(embed_links=True, manage_messages=True)
    async def tourney_edit(self, ctx, tourney: Tourney):
        """Edit a tournament's config."""
        menu = TourneyEditor(tourney=tourney)
        await menu.start(ctx)

    @tourney.command(name="start")
    @checks.can_use_tm()
    @checks.has_done_setup()
    @commands.bot_has_permissions(embed_links=True, manage_channels=True, manage_roles=True)
    async def tourney_start(self, ctx, tourney: Tourney):
        """Start a tournament."""
        if tourney.started_at is not None:
            raise TourneyError(f"Tourney (`{tourney.id}`)'s registration is already open.")

        channel = tourney.registration_channel
        open_role = tourney.open_role
        if channel is None:
            raise TourneyError(f"I cannot find tourney registration channel ({tourney.registration_channel_id})")

        elif not channel.permissions_for(ctx.me).manage_channels:
            raise TourneyError(f"I need `manage channels` permission in **{channel}**")

        elif open_role is None:
            raise TourneyError(f"I can not find open role for Tourney (`{tourney.id}`)")

        prompt = await ctx.prompt(f"Are you sure you want to start registrations for Tourney (`{tourney.id}`)?")
        if prompt:
            channel_update = await toggle_channel(channel, open_role, True)
            self.bot.tourney_channels.add(channel.id)
            await Tourney.filter(pk=tourney.id).update(started_at=datetime.now(tz=IST), closed_at=None)
            await channel.send("**Registration is now Open!**")
            await ctx.message.add_reaction(emote.check)
        else:
            await ctx.success("OK!")

    @tourney.command(name="stop", aliases=("pause",))
    @checks.can_use_tm()
    @checks.has_done_setup()
    @commands.bot_has_permissions(embed_links=True, manage_channels=True, manage_roles=True)
    async def tourney_stop(self, ctx, tourney: Tourney):
        """Stop / Pause a tournament."""
        if tourney.closed_at is not None:
            raise TourneyError(f"Tourney (`{tourney.id}`)'s registration is already closed.")

        channel = tourney.registration_channel
        open_role = tourney.open_role
        if channel is None:
            raise TourneyError(f"I cannot find tourney registration channel ({tourney.registration_channel_id})")

        elif not channel.permissions_for(ctx.me).manage_channels:
            raise TourneyError(f"I need `manage channels` permission in **{channel}**")

        elif open_role is None:
            raise TourneyError(f"I can not find open role for Tourney (`{tourney.id}`)")

        prompt = await ctx.prompt(
            f"Are you sure you want to stop registrations for Tourney (`{tourney.id}`)?\n>You can start them later with `{ctx.prefix}tourney start {tourney.id}` command"
        )
        if prompt:
            await toggle_channel(channel, open_role, False)
            await channel.send(f"Registration is now closed.")
            await Tourney.filter(pk=tourney.id).update(started_at=None, closed_at=datetime.now(tz=IST))
            await ctx.message.add_reaction(emote.check)
        else:
            await ctx.success("OK!")

    @tourney.command(name="ban")
    @checks.can_use_tm()
    @checks.has_done_setup()
    async def tourney_ban(self, ctx, tourney: Tourney, user: discord.User):
        """Ban someone from the tournament"""
        if user.id in tourney.banned_users:
            return await ctx.send(
                f"**{str(user)}** is already banned from the tourney.\n\nUse `{ctx.prefix}tourney unban {tourney.id} {user}` to unban them."
            )

        await Tourney.filter(pk=tourney.id).update(banned_users=ArrayAppend("banned_users", user.id))
        await ctx.success(f"**{str(user)}** has been successfully banned from Tourney (`{tourney.id}`)")

    @tourney.command(name="unban")
    @checks.can_use_tm()
    @checks.has_done_setup()
    async def tourney_unban(self, ctx, tourney: Tourney, user: discord.User):
        """Unban a banned user from tournament."""
        if user.id not in tourney.banned_users:
            return await ctx.send(
                f"**{str(user)}** is not banned the tourney.\n\nUse `{ctx.prefix}tourney ban {tourney.id} {user}` to ban them."
            )

        await Tourney.filter(pk=tourney.id).update(banned_users=ArrayRemove("banned_users", user.id))
        await ctx.success(f"**{str(user)}** has been successfully unbanned from Tourney (`{tourney.id}`)")

    @tourney.command(name="info")
    async def tourney_info(self, ctx: Context, tourney: Tourney):
        """Get all the necessary info about a tourney."""
        text = (
            f"> Name: `{tourney.name}`\n"
            f"> Registration Channel: {getattr(tourney.registration_channel,'mention','`Channel Not Found`')}\n"
            f"> Confirmation Channel: {getattr(tourney.confirm_channel,'mention','`Channel Not Found`')}\n"
            f"> Total Slots: `{tourney.total_slots}`\n\nRegistraton Status?"
        )
        left = tourney.total_slots - len(await tourney.assigned_slots.all())

        if tourney.started_at:
            text += f"\n> `Open!` ({strtime(tourney.started_at)})\n> Slots Left: {left}"

        else:
            text += f"\n> `Closed!` ({strtime(tourney.closed_at)})"

        embed = self.bot.embed(ctx, title="Tourney Config: ({0})".format(tourney.id))
        embed.description = text
        await ctx.send(embed=embed, embed_perms=True)

    @commands.command()
    async def format(self, ctx, *, registration_form):
        """Get your reg-format in a reusable form."""
        await ctx.send(f"```{registration_form}```")

    @commands.command()
    @commands.bot_has_permissions(embed_links=True, manage_messages=True)
    @checks.can_use_sm()
    async def quickidp(self, ctx, room_id, password, map, role_to_ping: QuoRole = None):
        """
        Share Id/pass with embed quickly.
        Message is automatically deleted after 30 minutes.
        """
        await ctx.message.delete()
        embed = self.bot.embed(ctx, title="New Custom Room. JOIN NOW!")
        embed.set_thumbnail(url=ctx.guild.icon.url)
        embed.add_field(name="Room ID", value=room_id)
        embed.add_field(name="Password", value=password)
        embed.add_field(name="Map", value=map)
        embed.set_footer(text=f"Shared by: {ctx.author} • Auto delete in 30 minutes.", icon_url=ctx.author.avatar.url)
        msg = await ctx.send(
            content=role_to_ping.mention if role_to_ping else None,
            embed=embed,
            allowed_mentions=discord.AllowedMentions(roles=True),
        )

        self.bot.loop.create_task(delete_denied_message(msg, 30 * 60))

    @commands.command()
    @commands.has_permissions(manage_guild=True)
    @commands.cooldown(7, 1, type=commands.BucketType.guild)
    async def customidp(self, ctx, channel: QuoTextChannel, role_to_ping: QuoRole = None):
        """Share customized Id/pass message."""
        if not (
            channel.permissions_for(ctx.me).send_messages
            or channel.permissions_for(ctx.me).embed_links
            or channel.permissions_for(ctx.me).manage_messages
        ):
            return await ctx.error(
                f"I need `send_messages` , `embed_links` and `manage_messages` permission in {channel.mention}"
            )

        await IDPMenu(send_channel=channel, role=role_to_ping).start(ctx)

    @commands.group(aliases=("eztag",), invoke_without_command=True)
    async def easytag(self, ctx: Context):
        """Commands related to quotient's eztag"""
        await ctx.send_help(ctx.command)

    @easytag.command(name="set")
    @checks.has_done_setup()
    @commands.bot_has_guild_permissions(manage_roles=True)
    @commands.has_permissions(manage_guild=True)
    async def set_eztag(self, ctx: Context, *, channel: QuoTextChannel):
        """Set a channel as eztag channel."""
        count = await EasyTag.filter(guild_id=ctx.guild.id).count()
        guild = await Guild.get(guild_id=ctx.guild.id)

        if count == 1 and not guild.is_premium:
            return await ctx.error(
                f"Upgrade your server to Quotient Premium to setup more than 1 EasyTag channel.\n{self.bot.config.WEBSITE}/premium"
            )

        if channel.id in self.bot.eztagchannels:
            return await ctx.error(f"This channel is already a easy tag channel.")

        if (
            not channel.permissions_for(ctx.me).send_messages
            or not channel.permissions_for(ctx.me).embed_links
            or not channel.permissions_for(ctx.me).manage_messages
        ):
            return await ctx.error(
                f"I need `send_messages`, `embed_links` and `manage_messages` permission in {channel.mention}"
            )

        role = discord.utils.get(ctx.guild.roles, name="quotient-tag-ignore")
        if not role:
            role = await ctx.guild.create_role(
                name="quotient-tag-ignore", color=0x00FFB3, reason=f"Created by {ctx.author}"
            )

        await EasyTag.create(guild_id=ctx.guild.id, channel_id=channel.id)
        self.bot.eztagchannels.add(channel.id)

        embed = self.bot.embed(ctx, title="Easy Tagging")
        embed.description = """
        Unable to mention teammates while registering for scrims or tournaments? Quotient is here for the rescue.

        Use `teammate's ID`, `@teammate_name` or `@teammate's_discord_tag` in your registration format. Quotient will convert that into an actual discord tag.        
        """
        embed.set_image(url="https://media.discordapp.net/attachments/775707108192157706/850788091236450344/eztags.gif")
        msg = await channel.send(embed=embed)
        await msg.pin()

        await ctx.success(
            f"Successfully added **{channel}** to easy tag channels.\n\nAdd {role.mention} to your roles to ignore your messages in **{channel}**"
        )

    @easytag.command(name="remove")
    @checks.has_done_setup()
    @commands.has_permissions(manage_guild=True)
    async def remove_eztag(self, ctx: Context, *, channel: QuoTextChannel):
        """Remove a eztag channel"""
        if not channel.id in self.bot.eztagchannels:
            return await ctx.error(f"This is not a EasyTag channel.")

        await EasyTag.filter(channel_id=channel.id).delete()
        self.bot.eztagchannels.discard(channel.id)
        await ctx.success(f"Removed {channel} from EasyTag channels.")

    @easytag.command(name="config")
    @checks.has_done_setup()
    @commands.has_permissions(manage_guild=True)
    async def config_eztag(self, ctx: Context):
        """Get a list of all your easytag channels."""
        records = await EasyTag.filter(guild_id=ctx.guild.id)
        if not records:
            return await ctx.error(
                f"You haven't set any easytag channel yet.\n\nUse `{ctx.prefix}eztag set #{ctx.channel}`"
            )

        eztags = []
        for idx, record in enumerate(records, start=1):
            channel = getattr(record.channel, "mention", record.channel_id)
            eztags.append(
                f"`{idx:02}.` {channel} (Delete After: {record.delete_after if record.delete_after else 'Not Set'})"
            )

        embed = self.bot.embed(ctx, title="EasyTag config", description="\n".join(eztags))
        await ctx.send(embed=embed)

    @easytag.command(name="autodelete")
    @checks.has_done_setup()
    @commands.has_permissions(manage_guild=True)
    async def delete_eztag(self, ctx: Context, channel: QuoTextChannel):
        """Enable/Disable autodelete for eztag."""
        record = await EasyTag.get_or_none(channel_id=channel.id)
        if not record:
            return await ctx.error(f"This is not a EasyTag Channel.")

        await EasyTag.filter(channel_id=channel.id).update(delete_after=not record.delete_after)
        await ctx.success(
            f"Delete After for **{channel}** turned {'ON' if not record.delete_after else 'OFF'}!\n\nDelete After automatically deletes the format message after some time."
        )

    # ************************************************************************************************
    # ************************************************************************************************
    # ************************************************************************************************
    # ************************************************************************************************
    # ************************************************************************************************
    # ************************************************************************************************
    # ************************************************************************************************

    @commands.group(invoke_without_command=True, aliases=("tc",))
    async def tagcheck(self, ctx: Context):
        """
        Setup tagcheck channels for scrims/tournaments.
        """
        await ctx.send_help(ctx.command)

    @tagcheck.command(name="set")
    @commands.has_permissions(manage_guild=True)
    async def tagcheck_set(self, ctx: Context, channel: discord.TextChannel, mentions=0):
        """
        Set a channel for tagcheck.
        mentions means required mentions, It's zero by default.
        """
        count = await TagCheck.filter(guild_id=ctx.guild.id).count()
        guild = await Guild.get(guild_id=ctx.guild.id)

        if count == 1 and not guild.is_premium:
            return await ctx.error(
                f"Upgrade your server to Quotient Premium to setup more than 1 Tagcheck channel.\n{self.bot.config.WEBSITE}/premium"
            )

        if channel.id in self.bot.tagcheck:
            return await ctx.error(f"This channel is already a tagcheck channel.")

        if (
            not channel.permissions_for(ctx.me).send_messages
            or not channel.permissions_for(ctx.me).embed_links
            or not channel.permissions_for(ctx.me).manage_messages
        ):
            return await ctx.error(
                f"I need `send_messages`, `embed_links` and `manage_messages` permission in {channel.mention}"
            )

        role = discord.utils.get(ctx.guild.roles, name="quotient-tag-ignore")
        if not role:
            role = await ctx.guild.create_role(
                name="quotient-tag-ignore", color=0x00FFB3, reason=f"Created by {ctx.author}"
            )

        await TagCheck.create(guild_id=ctx.guild.id, channel_id=channel.id, required_mentions=mentions)
        self.bot.tagcheck.add(channel.id)

        await ctx.success(
            f"Successfully added **{channel}** to tagcheck channels.\n\nAdd {role.mention} to your roles to ignore your messages in **{channel}**"
        )

    @tagcheck.command(name="config")
    @commands.has_permissions(manage_guild=True)
    async def tagcheck_config(self, ctx: Context):
        """
        Get tagcheck config.
        """
        records = await TagCheck.filter(guild_id=ctx.guild.id)
        if not records:
            return await ctx.error(
                f"You haven't set any tagcheck channel yet.\n\nUse `{ctx.prefix}tagcheck set #{ctx.channel}`"
            )

        tags = []
        for idx, record in enumerate(records, start=1):
            channel = getattr(record.channel, "mention", record.channel_id)
            tags.append(
                f"`{idx:02}.` {channel} (Mentions: {record.required_mentions},Auto-delete: {record.delete_after if record.delete_after else 'Not Set'})"
            )

        embed = self.bot.embed(ctx, title="TagCheck config", description="\n".join(tags))
        await ctx.send(embed=embed)

    @tagcheck.command(name="remove")
    @commands.has_permissions(manage_guild=True)
    async def tagcheck_remove(self, ctx: Context, *, channel: QuoTextChannel):
        """Remove a channel from tagcheck"""
        if not channel.id in self.bot.tagcheck:
            return await ctx.error(f"This is not a TagCheck channel.")

        await TagCheck.filter(channel_id=channel.id).delete()
        self.bot.tagcheck.discard(channel.id)
        await ctx.success(f"Removed {channel} from TagCheck channels.")

    @tagcheck.command(name="autodelete")
    @commands.has_permissions(manage_guild=True)
    async def tagcheck_autodelete(self, ctx: Context, *, channel: QuoTextChannel):
        """Enable/Disable autodelete wrong tagchecks."""
        record = await TagCheck.get_or_none(channel_id=channel.id)
        if not record:
            return await ctx.error(f"This is not a TagCheck Channel.")

        await TagCheck.filter(channel_id=channel.id).update(delete_after=not record.delete_after)
        await ctx.success(
            f"Autodelete for **{channel}** turned {'ON' if not record.delete_after else 'OFF'}!\nThis automatically deletes the wrong format message after some time."
        )

    # ************************************************************************************************
    # ************************************************************************************************
    # ************************************************************************************************
    # ************************************************************************************************
    # ************************************************************************************************
    # ************************************************************************************************
    # ************************************************************************************************

    @commands.group(aliases=("pt",), invoke_without_command=True)
    async def ptable(self, ctx):
        """Points tables commands"""
        embed = discord.Embed(color=self.bot.color, title="Shifted to Dashboard", url=self.bot.config.WEBSITE)
        embed.description = (
            f"Points table command has been moved to the dashboard [here]({self.bot.config.WEBSITE}/dashboard) for ease of use."
            f"\n\nTo create beautiful points tables, use the link above or use `{ctx.prefix}dashboard` command to get a direct link"
            "to the dashboard"
        )
        embed.set_image(url="https://media.discordapp.net/attachments/779229002626760716/873236858333720616/ptable.png")
        await ctx.send(embed=embed, embed_perms=True)

    @commands.group(invoke_without_command=True, aliases=("slotm",))
    async def slotmanager(self, ctx: Context):
        """
        SlotManager helps people to setup scrims-slots cancel and claim manager.
        Users can easily claim and cancel their slots anytime without bothering mods.
        """
        await ctx.send_help(ctx.command)

    @slotmanager.command(name="setup")
    @checks.can_use_sm()
    @commands.bot_has_guild_permissions(manage_channels=True)
    async def _slotmanager_setup(self, ctx: Context):
        """Setup Slot-Manager in the server"""

        check = await SlotManager.filter(guild_id=ctx.guild.id)
        if check:
            return await ctx.error(
                "It seems that you have an existing slotmanager setup in your server."
                f"\nKindly use `{ctx.prefix}slotmanager delete` if you think there's something wrong."
            )

        check = await Scrim.filter(guild_id=ctx.guild.id)
        if not check:
            return await ctx.error(
                "It seems that you don't have any scrims setup in your server. "
                "\nYou need to use Quotient's scrims manager to use slotmanager."
            )

        def check(message: discord.Message):
            if message.content.strip().lower() == "cancel":
                raise ScrimError("Alright, reverting all process.")

            return message.author == ctx.author and ctx.channel == message.channel

        await ctx.simple(
            "In which channel do you want me to post available slots?\n"
            "As soon as any slot becomes vacant, I will post a message in the channel you select now.\n\n"
            "`Please mention a public channel to receive updates.`"
        )
        channel = await inputs.channel_input(ctx, check)
        perms = channel.permissions_for(ctx.me)
        if not all((perms.send_messages, perms.embed_links)):
            return await ctx.error(
                f"I don't have permission to send messages in **{channel}**.\n"
                "Please give me permission to send messages and embed links in this channel."
            )

        prompt = await ctx.prompt(
            "A new channel will be created for slot-manager in your scrims category.\n\nAre you sure you want to continue?"
        )
        if not prompt:
            return await ctx.simple("Alright, aborting.")

        sm = await setup_slotmanager(ctx, channel)
        if isinstance(sm, SlotManager):
            await ctx.success(
                f"Slot-Manager setup complete ({sm.main_channel.mention})"
                f"\n\nKindly use `{ctx.prefix}slotmanager lock` command and set autolock time\n"
                "for each of your scrims."
            )

    @slotmanager.command(name="delete")
    @checks.can_use_sm()
    async def _slotmanager_delete(self, ctx: Context):
        """Delete slot manager"""
        sm = await SlotManager.get_or_none(guild_id=ctx.guild.id)
        if not sm:
            return await ctx.error(
                f"You haven't done slotmanager setup yet.\n\nPlease use `{ctx.prefix}slotmanager setup` once."
            )

        prompt = await ctx.prompt("Are you sure you want to delete your SlotManager setup?")
        if not prompt:
            return await ctx.success("Alright, Aborting.")

        await delete_slotmanager(sm)
        await ctx.success(f"Slotmanager Setup deleted.")

    @slotmanager.command(name="lock")
    @checks.can_use_sm()
    async def _slotmanager_lock(self, ctx: Context, scrim: Scrim, *, time: BetterFutureTime = None):
        """Lock slot management of any scrim"""

        time = time or datetime.now(tz=IST)

        sm = await SlotManager.get_or_none(guild_id=ctx.guild.id)
        if not sm:
            return await ctx.error(
                f"You haven't done slotmanager setup yet.\n\nPlease use `{ctx.prefix}slotmanager setup` once."
            )

        lock = await sm.locks.filter(id=scrim.id).first()
        if lock and lock.locked:
            return await ctx.error(
                f"This scrim is already locked.\n\nYou can use `{ctx.prefix}slotmanager unlock {scrim.id}` to unlock it."
            )

        slot = await SlotLocks.update_or_create(pk=scrim.id, defaults={"lock_at": time})
        await sm.locks.add(slot)
        await ctx.success(
            f"SlotManager for {scrim.name}(ID: {scrim.id}) will everyday lock at: `{time.strftime('%I:%M %p')}`"
        )
        await self.bot.reminders.create_timer(time, "scrim_lock", scrim_id=scrim.id)
        await update_main_message(ctx.guild.id)

    @slotmanager.command(name="unlock")
    @checks.can_use_sm()
    async def _slotmanager_unlock(self, ctx: Context, scrim: Scrim):
        """Unlock slot management for any scrim"""
        sm = await SlotManager.get_or_none(guild_id=ctx.guild.id)
        if not sm:
            return await ctx.error(
                f"You haven't done slotmanager setup yet.\n\nPlease use `{ctx.prefix}slotmanager setup` once."
            )

        lock = await sm.locks.filter(id=scrim.id).first()
        if not lock or not lock.locked:
            return await ctx.error(f"This scrim is already unlocked.")

        await SlotLocks.filter(pk=scrim.id).update(locked=False)
        await ctx.success(
            f"SlotManager for {scrim.name}(ID: {scrim.id}) is now unlocked.\n\n"
            f"I will automatically lock it when the registration starts and will unlock it after it ends."
        )
        await update_main_message(ctx.guild.id)

    @slotmanager.command(name="info")
    @checks.can_use_sm()
    async def _slotmanager_info(self, ctx: Context):
        """Slot-Manager info for all scrims."""
        sm = await SlotManager.get_or_none(guild_id=ctx.guild.id)
        if not sm:
            return await ctx.error(
                f"You haven't done slotmanager setup yet.\n\nPlease use `{ctx.prefix}slotmanager setup` once."
            )

        embed = ctx.bot.embed(ctx, title="SlotManager Info", description="**Scrim Autolock:**\n")
        embed.add_field(name="Main Channel", value=getattr(sm.main_channel, "mention", "deleted-channel"))
        embed.add_field(name="Updates Channel", value=getattr(sm.updates_channel, "mention", "deleted-channel"))

        async for lock in sm.locks.all():
            scrim = await Scrim.get_or_none(pk=lock.id)
            if scrim:
                time = "Not Set!"
                if lock.lock_at:
                    time = lock.lock_at.strftime("%I:%M %p")

                embed.description += f"{getattr(scrim.registration_channel,'mention','deleted-channel')}-  `{time}`  (Locked: {lock.locked})\n"

        await ctx.send(embed=embed, embed_perms=True)

    @commands.command(name="banlog")
    @checks.can_use_sm()
    async def _banlog(self, ctx: Context, *, channel: QuoTextChannel = None):
        """
        Set a channel for all esports ban/unban logs
        """
        if not channel:
            record = await BanLog.get_or_none(guild_id=ctx.guild.id)
            if not record:
                return await ctx.simple(
                    f"You haven't setup any esports ban log channel yet.\n"
                    f"Use `{ctx.prefix}banlog #{ctx.channel}` to do it."
                )
            return await ctx.simple(
                f"Currently {getattr(record.channel, 'mention', 'deleted-channel')} is serving as ban/unban log channel."
            )
        if not channel.permissions_for(ctx.me).embed_links:
            return await ctx.error(f"I need `embed_links` permission in {channel.mention} to send logs.")

        await BanLog.update_or_create(guild_id=ctx.guild.id, defaults={"channel_id": channel.id})
        await ctx.success(f"Successfully set {channel.mention} as esports ban/unban log channel.")


def setup(bot):
    bot.add_cog(ScrimManager(bot))
    bot.add_cog(SMError(bot))
    bot.add_cog(ScrimEvents(bot))
    bot.add_cog(TourneyEvents(bot))
    bot.add_cog(TagEvents(bot))
    bot.add_cog(SlotManagerEvents(bot))

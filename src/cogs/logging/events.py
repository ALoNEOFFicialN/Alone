import discord, humanize
from datetime import datetime, timedelta
from core import Quotient, Cog
from discord.utils import escape_markdown
from constants import IST, LogType
from models import Snipes
from .functions import *
from utils import strtime, human_timedelta

__all__ = ("LoggingEvents",)


class LoggingEvents(Cog):
    def __init__(self, bot: Quotient):
        self.bot = bot
        self.bot.loop.create_task(self.delete_older_snipes())

    async def delete_older_snipes(self):  # we delete snipes that are older than 15 days
        await Snipes.filter(delete_time__lte=(datetime.now(tz=IST) - timedelta(days=15))).all().delete()

    @Cog.listener()
    async def on_snipe_deleted(self, message: discord.Message):
        if not message.guild:
            return
        channel = message.channel
        content = message.content if message.content else "*[Content Unavailable]*"

        await Snipes.create(channel_id=channel.id, author_id=message.author.id, content=content, nsfw=channel.is_nsfw())

    # =======================================================

    @Cog.listener()
    async def on_log(self, _type: LogType, **kwargs):

        embed, channel = await self.handle_event(_type, **kwargs)
        if embed is not None and channel is not None:
            await channel.send(embed=embed)

    async def handle_event(self, _type: LogType, **kwargs):
        embed = discord.Embed(timestamp=datetime.now(tz=IST))

        if _type == LogType.msg:
            subtype = kwargs.get("subtype")
            message = kwargs.get("message")

            guild = message.guild if subtype == "single" else message[0].guild

            channel, color = await get_channel(_type, guild)
            if not channel:
                return

            check = await check_permissions(_type, channel)
            if not check:
                return

            if subtype == "single":

                embed.color = discord.Color(color)
                embed.set_footer(text=f"ID: {message.id}", icon_url=self.bot.user.avatar_url)

                embed.description = f"Message sent by {message.author.mention} deleted in {message.channel.mention}."
                embed.set_author(name=str(message.author), icon_url=message.author.avatar_url)

                cont = escape_markdown(message.content)

                if cont and len(cont) > 128:
                    cont = truncate_string(cont)

                embed.add_field(name="Message:", value=cont or f"*[Content Unavailable]*", inline=False)

                if message.attachments and "image" in message.attachments[0].content_type:
                    embed.set_image(url=message.attachments[0].proxy_url)

                return embed, channel

            elif subtype == "bulk":

                msg = message[0]
                msg_str = f"\n\n{'-'*50}\n\n".join((f"Author: {str(m.author)}\nContent: {m.content}" for m in message))

                embed.color = discord.Color(color)
                embed.description = f"{len(message)} messages, deleted in {msg.channel.mention}"
                embed.add_field(name="Messages", value=f"[Click Me ...]({str(await self.bot.binclient.post(msg_str))})")
                embed.set_footer(text=f"Bulk Delete: {len(message)}", icon_url=self.bot.user.avatar_url)
                return embed, channel

            else:
                before, after = message
                embed.color = discord.Color(color)
                embed.set_footer(text=f"ID: {before.id}", icon_url=self.bot.user.avatar_url)
                embed.description = f"A [message]({before.jump_url}) was edited in {before.channel.mention}."
                embed.set_author(name=str(before.author), icon_url=before.author.avatar_url)
                embed.add_field(
                    name="Before:", value=truncate_string(before.content) or f"*[Content Unavailable]*", inline=False
                )
                embed.add_field(name="After:", value=truncate_string(after.content) or f"*[Content Unavailable]*")

                return embed, channel

        elif _type == LogType.join:
            member = kwargs.get("member")

            guild = member.guild

            channel, color = await get_channel(_type, guild)
            if not channel:
                return

            check = await check_permissions(_type, channel)
            if not check:
                return

            embed.color = discord.Color(color)
            embed.set_author(name=str(member), icon_url=member.avatar_url)
            embed.set_thumbnail(url=member.avatar_url)
            embed.description = (
                f"{member.mention} just joined the server, they are {guild.member_count}th member of {guild.name}."
            )
            embed.add_field(
                name="Account Age:",
                value=f"`{strtime(member.created_at)}` ({human_timedelta(IST.localize(member.created_at))})",
            )
            embed.set_footer(text=f"ID: {member.id}")

            return embed, channel

        elif _type == LogType.leave:
            member = kwargs.get("member")

            guild = member.guild

            channel, color = await get_channel(_type, guild)
            if not channel:
                return

            check = await check_permissions(_type, channel)
            if not check:
                return

            embed.color = color
            embed.set_author(name=str(member), icon_url=member.avatar_url)
            embed.set_thumbnail(url=member.avatar_url)

            embed.description = f"{member.mention} just left the server. They joined {human_timedelta(IST.localize(member.joined_at) + timedelta(hours=5, minutes=30))}"
            embed.add_field(
                name="Roles:", value=", ".join((role.mention for role in member.roles)).replace("@@everyone", "@everyone")
            )

            return embed, channel

        elif _type == LogType.invite:
            subtype = kwargs.get("subtype")

            invite = kwargs.get("invite")

            if subtype in ("create", "delete"):
                guild = invite.guild

            else:
                message = kwargs.get("message")
                guild = message.guild

            check = await get_channel(_type, guild)
            if not check:
                return

            channel, color = check

            check = await check_permissions(_type, channel)
            if not check:
                return

            embed.color = discord.Color(color)

            if subtype == "create":
                embed.title = "Server Invite Created"
                embed.set_author(name=str(invite.inviter), icon_url=invite.inviter.avatar_url)
                embed.set_footer(text=f"ID: {invite.inviter.id}")
                embed.description = (
                    f"{invite.inviter.mention} just created an invite (`{invite.code}`) for {invite.channel.mention}"
                )

                embed.add_field(name="Max Uses", value=f"{'Infinite' if not invite.max_uses else invite.max_uses}")
                embed.add_field(
                    name="Max Age",
                    value=f"{'Infinite' if invite.max_age == 0 else humanize.precisedelta(invite.max_age)}",
                )

                return embed, channel
            elif subtype == "delete":
                pass
                # print(invite.created_at)

                # embed.title = "Server Invite Deleted"
                # if invite.inviter:
                #     embed.set_author(name=str(invite.inviter), icon_url=invite.inviter.avatar_url)

                #     embed.set_footer(text=f"ID: {invite.inviter.id}")
                # embed.description = f"An invite for {getattr(invite.channel , 'mention', 'deleted-channel')} was just deleted. It was created {human_timedelta(IST.localize(invite.created_at))}"
                # embed.add_field(name="Uses", value=f"{invite.uses} times")

                # return embed, channel

            else:

                embed.title = "Discord Invite Posted"

                embed.set_author(name=str(message.author), icon_url=message.author.avatar_url)
                embed.description = f"{message.author.mention} posted an [Invite link]({message.jump_url}) (`{invite.code}`) in {message.channel.mention} that leads to the server **{invite.guild.name}**"

                embed.set_footer(text=f"ID: {message.id}")

                return embed, channel

        elif LogType.ping:
            message = kwargs.get("message")
            mentions = kwargs.get("mentions")

            check = await get_channel(_type, message.guild)
            if not check:
                return

            channel, color = check

            check = await check_permissions(_type, channel)
            if not check:
                return

            mentions = "\n- ".join(mentions)
            embed.color = discord.Color(color)
            embed.title = "Ping Logs"
            embed.set_footer(text="ID: {0}".format(message.id),icon_url = self.bot.user.avatar_url)
            embed.set_author(name=message.author, icon_url=message.author.avatar_url)
            embed.description = f"{message.author.mention} [mentioned]({message.jump_url}) the following in {message.channel.mention}:\n\n-{mentions}"
            return embed, channel

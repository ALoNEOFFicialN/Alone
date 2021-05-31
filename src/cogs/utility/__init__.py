from core import Cog, Quotient, Context
from discord.ext import commands
from models import Tag
from models import Autorole, ArrayAppend, ArrayRemove, Tag
from utils import checks, ColorConverter, Pages, strtime
from .functions import TagName, create_tag, increment_usage, TagConverter, is_valid_name
from typing import Optional
import discord
import config
import json
import re


class Utility(Cog, name="utility"):
    def __init__(self, bot: Quotient):
        self.bot = bot

    @commands.group(invoke_without_command=True)
    @checks.is_mod()
    async def autorole(self, ctx: Context, off: str = None):
        """
        Manage Quotient's autoroles.
        """
        if not off or not off.lower() == "off":
            return await ctx.send_help(ctx.command)

        record = await Autorole.get_or_none(guild_id=ctx.guild.id)

        if not record:
            return await ctx.send(
                f"You have not set any autorole yet.\n\nDo it like: `{ctx.prefix}autorole humans @role`"
            )

        elif not any([len(record.humans), len(record.bots)]):
            return await ctx.error("Autoroles already OFF!")

        else:
            prompt = await ctx.prompt("Are you sure you want to turn off autorole?")
            if prompt:
                # await Autorole.filter(guild_id=ctx.guild.id).update(humans=list, bots=list)
                await ctx.db.execute("UPDATE autoroles SET humans = '{}' , bots = '{}' WHERE guild_id = $1", ctx.guild.id)
                await ctx.success("Autoroles turned OFF!")
            else:
                await ctx.success("OK!")

    @autorole.command(name="humans")
    @checks.is_mod()
    @commands.bot_has_guild_permissions(manage_roles=True)
    async def autorole_humans(self, ctx: Context, *, role: discord.Role):
        """
        Add/ Remove a role to human autoroles.
        """
        record = await Autorole.get_or_none(pk=ctx.guild.id)
        if record is None:
            await Autorole.create(guild_id=ctx.guild.id, humans=[role.id])
            text = f"Added {role.mention} to human autoroles."

        else:
            func = (ArrayAppend, ArrayRemove)[role.id in record.humans]
            await Autorole.filter(guild_id=ctx.guild.id).update(humans=func("humans", role.id))
            text = (
                f"Added {role.mention} to human autoroles."
                if func == ArrayAppend
                else f"Removed {role.mention} from human autoroles."
            )

        await ctx.success(text)

    @autorole.command(name="bots")
    @checks.is_mod()
    @commands.bot_has_guild_permissions(manage_roles=True)
    async def autorole_bots(self, ctx: Context, *, role: discord.Role):
        """
        Add/ Remove a role to bot autoroles.
        """
        record = await Autorole.get_or_none(pk=ctx.guild.id)
        if record is None:
            await Autorole.create(guild_id=ctx.guild.id, bots=[role.id])
            text = f"Added {role.mention} to bot autoroles."

        else:
            func = (ArrayAppend, ArrayRemove)[role.id in record.bots]
            await Autorole.filter(guild_id=ctx.guild.id).update(bots=func("bots", role.id))
            text = (
                f"Added {role.mention} to bot autoroles."
                if func == ArrayAppend
                else f"Removed {role.mention} from bot autoroles."
            )

        await ctx.success(text)

    @autorole.command(name="config")
    @checks.is_mod()
    @commands.bot_has_guild_permissions(manage_roles=True)
    async def autorole_config(self, ctx: Context):
        """
        Get autorole config
        """
        record = await Autorole.get_or_none(pk=ctx.guild.id)
        if not record:
            return await ctx.send(
                f"You have not set any autorole yet.\n\nDo it like: `{ctx.prefix}autorole humans @role`"
            )

        humans = ", ".join(record.human_roles) if len(list(record.human_roles)) else "Not Set!"
        bots = ", ".join(record.bot_roles) if len(list(record.bot_roles)) else "Not Set!"

        embed = self.bot.embed(ctx, title="Autorole Config")
        embed.add_field(name="Humans", value=humans, inline=False)
        embed.add_field(name="Bots", value=bots, inline=False)
        await ctx.send(embed=embed)

    @commands.command()
    @commands.cooldown(1, 5, type=commands.BucketType.user)
    async def firstmsg(self, ctx, *, channel: discord.TextChannel = None):
        """Get the link to first message of current or any other channel."""
        channel = channel or ctx.channel
        messages = await channel.history(limit=1, oldest_first=True).flatten()
        return await ctx.send(f"Here's the link to first message of {channel.mention}:\n{messages[0].jump_url}")

    @commands.command(name="embed")
    @commands.has_permissions(manage_messages=True)
    async def embed_send(self, ctx: Context, channel: discord.TextChannel, color: ColorConverter, *, text: str):
        """
        Generated and sends embed to specified channel. Use qqe <message> for quick embeds
        Tip: You can send hyperlinks too. Example: `[anytext](any link)`
        """
        if not channel.permissions_for(ctx.me).embed_links:
            return await ctx.error(f"I need `embed_links` permission in {channel.mention}")

        embed = discord.Embed(color=color, description=text)
        await ctx.send(embed=embed)
        prompt = await ctx.prompt(
            "Should I deliver it?",
        )

        if prompt:
            await channel.send(embed=embed)
            await ctx.success(f"Successfully delivered.")

        else:
            await ctx.success("Ok Aborting")

    @commands.command(name="quickembed", aliases=["qe"])
    @commands.has_permissions(manage_messages=True, embed_links=True)
    @commands.bot_has_permissions(manage_messages=True, embed_links=True)
    async def quick_embed_command(self, ctx: Context, *, text: str):
        """
        Generates quick embeds.
        Tip: You can send hyperlinks too. Example: `[anytext](any link)`
        """
        embed = self.bot.embed(ctx, description=text)
        await ctx.send(embed=embed)
        await ctx.message.delete()

    # @commands.command()
    # @commands.bot_has_permissions(embed_links=True)
    # async def snipe(self, ctx, *, channel: Optional[discord.TextChannel]):
    #     """Snipe last deleted message of a channel."""

    #     channel = channel or ctx.channel

    #     snipe = await Snipes.filter(channel_id=channel.id).order_by("delete_time").first()
    #     if not snipe:
    #         return await ctx.send(f"There's nothing to snipe :c")

    #     elif snipe.nsfw and not channel.is_nsfw():
    #         return await ctx.send(f"The snipe is marked NSFW but the current channel isn't.")

    #     content = (
    #         snipe.content
    #         if len(snipe.content) < 128
    #         else f"[Click me to see]({str(await ctx.bot.binclient.post(snipe.content))})"
    #     )
    #     embed = self.bot.embed(ctx)
    #     embed.description = f"Message sent by **{snipe.author}** was deleted in {channel.mention}"
    #     embed.add_field(name="**__Message Content__**", value=content)
    #     embed.set_footer(text=f"Deleted {human_timedelta(snipe.delete_time)}")
    #     await ctx.send(embed=embed)

    @commands.group(invoke_without_command=True)
    async def tag(self, ctx: Context, *, name: TagName(lower=True) = None):

        if name is None:
            return await ctx.send_help(ctx.command)

        record = await Tag.get_or_none(guild_id=ctx.guild.id, name=name)

        if record is None:
            return await ctx.error(f"No tag **{name}** found.\nCreate one with the `{ctx.prefix}tag create` command.")

        if not ctx.channel.is_nsfw() and record.is_nsfw:
            return await ctx.error("This tag can only be used in NSFW channels.")

        if record.is_embed is True:
            dict = json.loads(record.content)
            return await ctx.send(embed=discord.Embed.from_dict(dict), reference=ctx.replied_reference)

        await ctx.send(record.content, reference=ctx.replied_reference)
        await increment_usage(ctx, name)

    @tag.command(name="all", aliases=("list",))
    async def all_tags(self, ctx):
        tags = await Tag.filter(guild_id=ctx.guild.id)

        if not len(tags):
            return await ctx.error("This server doesn't have any tags.")

        tag_list = []
        for idx, tag in enumerate(tags, start=1):
            tag_list.append(f"`{idx:02}` {tag.name} (ID: {tag.id})\n")

        paginator = Pages(
            ctx, title="Total tags: {}".format(len(tag_list)), entries=tag_list, per_page=10, show_entry_count=True
        )
        await paginator.paginate()

    @tag.command(name="info", aliases=("stats",))
    async def tag_info(self, ctx, *, tag: TagConverter):
        embed = self.bot.embed(ctx, title=f"Stats for tag {tag.name}")

        user = self.bot.get_user(tag.owner_id) or await self.bot.fetch_user(tag.owner_id)

        embed.set_author(name=str(user), icon_url=user.avatar_url)

        embed.add_field(name="Owner", value=getattr(user, "mention", "Invalid User!"))
        embed.add_field(name="ID:", value=id)
        embed.add_field(name="Uses", value=tag.usage)
        embed.add_field(name="NSFW", value="No" if not tag.is_nsfw else "Yes")
        embed.add_field(name="Embed", value="No" if not tag.is_embed else "Yes")
        embed.set_footer(text=f"Created At: {strtime(tag.created_at)}")
        await ctx.send(embed=embed)

    @tag.command(name="claim")
    async def claim_tag(self, ctx, *, tag: TagConverter):
        """Koi tag le jayega pata bhi nhi chalega tujhe gandu."""

        member = await self.bot.get_or_fetch_member(ctx.guild, tag.owner_id)

        if member is not None:
            return await ctx.send(f"The owner of this tag ({tag.owner}) is still in the server.")

        await Tag.filter(name=tag.name, guild_id=ctx.guild.id).update(owner_id=ctx.author.id)
        await ctx.success("Transfered tag ownership to you.")

    @tag.command(name="create")
    async def create_tag_command(self, ctx, name: TagName, *, content=""):
        if len(ctx.message.attachments) > 1:
            return await ctx.error("You cannot create tag with more than one attachment.")

        if len(ctx.message.attachments) == 1:
            content += f"\n{ctx.message.attachments[0].proxy_url}"

        if len(content) > 1990:
            return await ctx.error(f"Tag content cannot contain more than 1990 characters.")

        # if await is_valid_name(ctx,name):
        # await Tag.create(name=name , content = content, guild_id = ctx.guild.id, )

        # await ctx.success(f"Created Tag (ID: `{tag.id}`)")

    @tag.command(name="delete", aliases=["del"])
    async def delete_tag(self, ctx, *, tag_name: TagConverter):
        tag = tag_name
        if not tag.owner_id == ctx.author.id and not ctx.author.guild_permissions.manage_guild:
            return await ctx.error(f"This tag doesn't belong to you.")

        await Tag.filter(guild_id=ctx.guild.id, name=tag_name.name, owner_id=ctx.author.id).delete()
        await ctx.success(f"Deleted {tag_name.name}")

    @tag.command(name="transfer")
    async def transfer_tag(self, ctx, member: discord.Member, *, tag):

        query_one = "SELECT owner_id FROM tags WHERE name = $1 AND guild_id = $2"
        owner = await ctx.bot.db.fetchval(query_one, tag, ctx.guild.id)

        if owner != ctx.author.id:
            return await ctx.error("gand mara")

        query = "SELECT * FROM tags WHERE name = $1 AND guild_id = $2"
        record = await ctx.db.fetchrow(query, tag, ctx.guild.id)

        if record is None:
            return await ctx.error("nhi hai tag not found")

        query_second = "UPDATE tags SET owner_id = $1 WHERE name = $2 AND guild_id = $3"
        await ctx.db.execute(query_second, member.id, tag, ctx.guild.id)
        await ctx.success("Done bc")

    @tag.command("nsfw")
    async def nsfw_status_toggle(self, ctx, *, tag):

        query_one = "SELECT owner_id FROM tags WHERE name = $1 AND guild_id = $2"
        owner = await ctx.bot.db.execute(query_one, tag, ctx.guild.id)
        if owner != ctx.author.id:
            return await ctx.error("gand mara")

        query = "SELECT * FROM tags WHERE name = $1 AND guild_id = $2"
        record = await ctx.db.fetchrow(query, tag, ctx.guild.id)

        if record is None:
            return await ctx.error("nhi hai tag not found")

        nsfw_status = record["is_nsfw"]
        if nsfw_status is False:
            query_nsfw = "UPDATE tags SET is_nsfw = $1 WHERE guild_id = $2 AND name = $3"
            await ctx.bot.db.execute(query_nsfw, True, ctx.guild.id, tag)
            return await ctx.success("ho gya")

        query_nsfw = "UPDATE tags SET is_nsfw = $1 WHERE guild_id = $2 AND name = $3"
        await ctx.bot.db.execute(query_nsfw, False, ctx.guild.id, tag)
        return await ctx.success("ho gya")

    @tag.command(name="purge")
    async def purge_tags(self, ctx, member: discord.Member):

        query = "SELECT COUNT(*) FROM tags WHERE guild_id=$1 AND owner_id=$2;"
        count = await ctx.db.fetchrow(query, ctx.guild.id, member.id)
        count = count[0]

        if count == 0:
            return await ctx.error(f"hai hi nhi XD")

        query = "DELETE FROM tags WHERE guild_id=$1 AND owner_id=$2;"
        await ctx.db.execute(query, ctx.guild.id, member.id)
        await ctx.success("ho gya bc")

    @tag.command(name="edit")
    async def edit_tag(self, ctx, name: TagName, *, content):

        query_one = "SELECT owner_id FROM tags WHERE name = $1 AND guild_id = $2"
        owner = await ctx.bot.db.execute(query_one, name, ctx.guild.id)

        if owner is None:
            return await ctx.error("nhi mila")

        if owner != ctx.author.id:
            return await ctx.error("gand mara")

        query = "UPDATE tags SET content = $1 WHERE name = $2 AND guild_id = $3"
        await ctx.db.execute(query, content, name, ctx.guild.id)
        await ctx.success("ho gya bc")

    @tag.command(name="search")
    async def search_tag(self, ctx, *, name):
        if len(name) < 3:
            return await ctx.error("abey 3 likj le")

        tag = await Tag.filter(guild_id=ctx.guild.id, name__icontains=name)

        if tag is None:
            return await ctx.error("No tags found.")

        tag_names = []
        for tags in tag:
            tag_names.append(f"{tag.index(tags) + 1}. {tags.name} (ID: {tags.id})\n")

        paginator = Pages(
            ctx, title="Total tags: {}".format(len(tag_names)), entries=tag_names, per_page=5, show_entry_count=True
        )

        await paginator.paginate()


def setup(bot) -> None:
    bot.add_cog(Utility(bot))

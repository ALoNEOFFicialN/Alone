from models import Scrim, Tourney
from typing import Optional
from discord.ext import commands
from PIL import ImageColor
import discord, re
import contextlib


class ColorConverter(commands.Converter):
    async def convert(self, ctx, arg: str):
        with contextlib.suppress(AttributeError):
            match = re.match(r"\(?(\d+),?\s*(\d+),?\s*(\d+)\)?", arg)
            check = all(0 <= int(x) <= 255 for x in match.groups())

        if match and check:
            return discord.Color.from_rgb([int(i) for i in match.groups()])

        converter = commands.ColorConverter()
        try:
            result = await converter.convert(ctx, arg)
        except commands.BadColourArgument:
            try:
                color = ImageColor.getrgb(arg)
                result = discord.Color.from_rgb(*color)
            except ValueError:
                result = None

        if result:
            return result

        raise commands.BadArgument(f"Could not find any color that matches this: `{arg}`.")


class BannedMember(commands.Converter):
    async def convert(self, ctx, argument):
        if argument.isdigit():
            member_id = int(argument, base=10)
            try:
                return await ctx.guild.fetch_ban(discord.Object(id=member_id))
            except discord.NotFound:
                raise commands.BadArgument("This member has not been banned before.") from None

        ban_list = await ctx.guild.bans()
        entity = discord.utils.find(lambda u: str(u.user) == argument, ban_list)

        if entity is None:
            raise commands.BadArgument("This member has not been banned before.")
        return entity


class ActionReason(commands.Converter):
    async def convert(self, ctx, argument):
        ret = f"{ctx.author} (ID: {ctx.author.id}): {argument}"

        if len(ret) > 512:
            reason_max = 512 - len(ret) + len(argument)
            raise commands.BadArgument(f"Reason is too long ({len(argument)}/{reason_max})")
        return ret


def can_execute_action(ctx, user, target):
    return user.id == ctx.bot.owner_id or user == ctx.guild.owner or user.top_role > target.top_role


class MemberID(commands.Converter):
    async def convert(self, ctx, argument):
        try:
            m = await commands.MemberConverter().convert(ctx, argument)
        except commands.BadArgument:
            try:
                member_id = int(argument, base=10)
            except ValueError:
                raise commands.BadArgument(f"{argument} is not a valid member or member ID.") from None
            else:
                m = await ctx.bot.get_or_fetch_member(ctx.guild, member_id)
                if m is None:
                    # hackban case
                    return type("_Hackban", (), {"id": member_id, "__str__": lambda s: f"Member ID {s.id}"})()

        if not can_execute_action(ctx, ctx.author, m):
            raise commands.BadArgument("You cannot do this action on this user due to role hierarchy.")

        elif not can_execute_action(ctx, ctx.me, m):
            raise commands.BadArgument("I cannot do this action on this user due to role hierarchy.")

        return m


class ScrimID(commands.Converter):
    async def convert(self, ctx, argument) -> Optional[Scrim]:
        if not argument.isdigit():
            raise commands.BadArgument(
                f"This is not a valid Scrim ID.\n\nGet a valid ID with `{ctx.prefix}smanager config`"
            )

        scrim = await Scrim.get_or_none(pk=int(argument), guild_id=ctx.guild.id)
        if scrim is None:
            raise commands.BadArgument(
                f"This is not a valid Scrim ID.\n\nGet a valid ID with `{ctx.prefix}smanager config`"
            )

        return scrim


class TourneyID(commands.Converter):
    async def convert(self, ctx, argument) -> Optional[Tourney]:
        if not argument.isdigit():
            raise commands.BadArgument(
                (f"This is not a valid Tourney ID.\n\nGet a valid ID with `{ctx.prefix}tourney config`")
            )

        tourney = await Tourney.get_or_none(pk=int(argument), guild_id=ctx.guild.id)
        if tourney is None:
            raise commands.BadArgument(
                f"This is not a valid Tourney ID.\n\nGet a valid ID with `{ctx.prefix}tourney config`"
            )

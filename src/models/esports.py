import asyncio
import io
import json
from .fields import *
import discord
import utils
from PIL import Image, ImageFont, ImageDraw
from typing import Optional, Union
from tortoise import models, fields
from constants import Day
from pathlib import Path
from .functions import *
from ast import literal_eval as leval

__all__ = ("Tourney", "TMSlot", "Scrim", "AssignedSlot", "ReservedSlot", "BannedTeam", "TagCheck")


class Tourney(models.Model):
    class Meta:
        table = "tm.tourney"

    id = fields.BigIntField(pk=True, index=True)
    guild_id = fields.BigIntField()
    name = fields.CharField(max_length=200, default="Quotient-Tourney")
    registration_channel_id = fields.BigIntField(index=True)
    confirm_channel_id = fields.BigIntField()
    role_id = fields.BigIntField()
    required_mentions = fields.IntField()
    total_slots = fields.IntField()
    banned_users = ArrayField(fields.BigIntField(), default=list)
    host_id = fields.BigIntField()
    multiregister = fields.BooleanField(default=False)
    started_at = fields.DatetimeField(null=True)
    closed_at = fields.DatetimeField(null=True)
    open_role_id = fields.BigIntField(null=True)

    assigned_slots: fields.ManyToManyRelation["TMSlot"] = fields.ManyToManyField("models.TMSlot")

    @property
    def guild(self) -> Optional[discord.Guild]:
        return self.bot.get_guild(self.guild_id)

    @property
    def logschan(self):
        if self.guild is not None:
            return discord.utils.get(self.guild.text_channels, name="quotient-tourney-logs")

    @property
    def registration_channel(self):
        if self.guild is not None:
            return self.guild.get_channel(self.registration_channel_id)

    @property
    def confirm_channel(self):
        if self.guild is not None:
            return self.guild.get_channel(self.confirm_channel_id)

    @property
    def closed(self):
        return True if self.closed_at else False

    @property
    def role(self):
        if self.guild is not None:
            return self.guild.get_role(self.role_id)

    @property
    def open_role(self):
        if self.guild is not None:
            if self.open_role_id != None:
                return self.guild.get_role(self.open_role_id)
            else:
                return self.guild.default_role

    @property
    def modrole(self):
        if self.guild is not None:
            return discord.utils.get(self.guild.roles, name="tourney-mod")


class TMSlot(models.Model):
    class Meta:
        table = "tm.register"

    id = fields.BigIntField(pk=True)
    num = fields.IntField()
    team_name = fields.TextField()
    leader_id = fields.BigIntField()
    members = ArrayField(fields.BigIntField(), default=list)
    jump_url = fields.TextField(null=True)


class Scrim(models.Model):
    class Meta:
        table = "sm.scrims"

    id = fields.BigIntField(pk=True, index=True)
    guild_id = fields.BigIntField()
    name = fields.TextField(default="Quotient-Scrims")
    registration_channel_id = fields.BigIntField(index=True)
    slotlist_channel_id = fields.BigIntField()
    slotlist_message_id = fields.BigIntField(null=True)
    role_id = fields.BigIntField(null=True)
    required_mentions = fields.IntField()
    start_from = fields.IntField(default=1)
    available_slots = ArrayField(fields.IntField(), default=list)
    total_slots = fields.IntField()
    host_id = fields.BigIntField()
    open_time = fields.DatetimeField()
    opened_at = fields.DatetimeField(null=True)
    closed_at = fields.DatetimeField(null=True)
    autoclean = fields.BooleanField(default=False)
    autoslotlist = fields.BooleanField(default=True)
    ping_role_id = fields.BigIntField(null=True)
    multiregister = fields.BooleanField(default=False)
    stoggle = fields.BooleanField(default=True)
    open_role_id = fields.BigIntField(null=True)
    autodelete_rejects = fields.BooleanField(default=False)
    teamname_compulsion = fields.BooleanField(default=False)

    open_days = ArrayField(fields.CharEnumField(Day), default=lambda: list(Day))
    slotlist_format = fields.TextField(null=True)
    assigned_slots: fields.ManyToManyRelation["AssignedSlot"] = fields.ManyToManyField("models.AssignedSlot")
    reserved_slots: fields.ManyToManyRelation["ReservedSlot"] = fields.ManyToManyField("models.ReservedSlot")
    banned_teams: fields.ManyToManyRelation["BannedTeam"] = fields.ManyToManyField("models.BannedTeam")

    @property
    def guild(self) -> Optional[discord.Guild]:
        return self.bot.get_guild(self.guild_id)

    @property
    def role(self):
        if self.guild is not None:
            return self.guild.get_role(self.role_id)

    @property
    def logschan(self):
        if self.guild is not None:
            return discord.utils.get(self.guild.text_channels, name="quotient-scrims-logs")

    @property
    def modrole(self):
        if self.guild is not None:
            return discord.utils.get(self.guild.roles, name="scrims-mod")

    @property
    def registration_channel(self):
        return self.bot.get_channel(self.registration_channel_id)

    @property
    def slotlist_channel(self):
        return self.bot.get_channel(self.slotlist_channel_id)

    @property
    def host(self):
        if self.guild is not None:
            return self.guild.get_member(self.host_id)

        return self.bot.get_user(self.host_id)

    @property
    def available_to_reserve(self):
        """
        gives a range obj of available slots to reserve.
        this isn't true because some slots might be already reserved , we will sort them later
        """
        return range(self.start_from, self.total_slots + self.start_from)

    @property
    def banned_users(self):
        return list(map(self.bot.get_user, self.banned_users_ids()))

    @property
    def opened(self):
        if self.opened_at is None:
            return False

        if self.closed_at is not None:
            return self.closed_at < self.opened_at

        return True

    @property
    def closed(self):
        return not self.opened

    @property
    def ping_role(self):
        if self.guild is not None:
            return self.guild.get_role(self.ping_role_id)

    @property
    def open_role(self):
        if self.guild is not None:
            if self.open_role_id is not None:
                return self.guild.get_role(self.open_role_id)
            else:
                return self.guild.default_role

    @property  # what? you think its useless , i know :)
    def toggle(self):
        return self.stoggle

    @property
    def teams_registered(self):  # This should be awaited
        return self.assigned_slots.order_by("num").all()

    async def reserved_user_ids(self):
        return (i.user_id for i in await self.reserved_slots.all())

    async def banned_user_ids(self):
        return (i.user_id for i in await self.banned_teams.all())

    # async def create_slotlist(self):
    #     slots = await self.teams_registered
    #     description = "\n".join(f"Slot {slot.num:02}  ->  {slot.team_name}" for slot in slots)
    #     embed = discord.Embed(title=self.name + " Slotlist", description=f"```{description}```")
    #     channel = self.slotlist_channel
    #     return embed, channel

    async def create_slotlist(self):
        slots = await self.teams_registered
        ids = [slot.num for slot in slots]
        fslots = []
        for id in ids:
            fslots.append([slot for slot in slots if slot.num == id][0])

        desc = "\n".join(f"Slot {slot.num:02}  ->  {slot.team_name}" for slot in slots)

        if self.slotlist_format != None:
            format = leval(self.slotlist_format)

            embed = discord.Embed.from_dict(format)
            embed.description = f"```{desc}```{embed.description if embed.description else ''}"

        else:
            embed = discord.Embed(title=self.name + " Slotlist", description=f"```{desc}```", color=self.bot.color)
        channel = self.slotlist_channel
        return embed, channel

    async def create_slotlist_img(self):
        """
        This is done! Now do whatever you can : )
        """
        slots = await self.teams_registered

        def wrapper():
            font = ImageFont.truetype(str(Path.cwd() / "src" / "data" / "font" / "Ubuntu-Regular.ttf"), 16)
            rects = []

            for slot in slots:
                image = Image.new("RGBA", (290, 30), "#2e2e2e")
                draw = ImageDraw.Draw(image)
                draw.text((10, 5), f"Slot {slot.num:02}  |  {slot.team_name}", font=font, fill="white")
                rects.append(image)

            # We will add 10 slots in a image.
            images = []
            for group in utils.split_list(rects, 10):
                size = (
                    290,
                    len(group) * 40,
                )
                image = Image.new("RGBA", size)
                x = 0
                y = 0

                for rect in group:
                    image.paste(rect, (x, y))
                    y += rect.size[1] + 10

                img_bytes = io.BytesIO()
                image.save(img_bytes, "PNG")
                img_bytes.seek(0)
                images.append(discord.File(img_bytes, "slotlist.png"))

            return images

        return await asyncio.get_event_loop().run_in_executor(
            None, wrapper
        )  # As pillow is blocking, we will process image in executor


class BaseSlot(models.Model):
    class Meta:
        abstract = True

    id = fields.IntField(pk=True)
    num = fields.IntField(null=True)  # this will never be null but there are already records in the table so
    user_id = fields.BigIntField()
    team_name = fields.TextField(null=True)
    members = ArrayField(fields.BigIntField(), default=list)


class AssignedSlot(BaseSlot):
    class Meta:
        table = "sm.assigned_slots"

    jump_url = fields.TextField(null=True)


class ReservedSlot(BaseSlot):
    class Meta:
        table = "sm.reserved_slots"

    expires = fields.DatetimeField(null=True)


class BannedTeam(BaseSlot):
    class Meta:
        table = "sm.banned_teams"

    expires = fields.DatetimeField(null=True)


# ************************************************************************************************


class TagCheck(models.Model):
    class Meta:
        table = "tagcheck"

    guild_id = fields.BigIntField(pk=True)
    channel_id = fields.BigIntField()
    required_mentions = fields.IntField(default=0)

    @property
    def channel(self):
        return self.bot.get_channel(self.channel_id)

    @property
    def modrole(self):
        guild = self.bot.get_guild(self.guild_id)
        if guild != None:
            return discord.utils.get(guild.roles, name="scrims-mod")

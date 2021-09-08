from models import Guild


async def check_member_role(bot, data):
    g_id, m_id = data["guild_id"], data["member_id"]

    guild = bot.get_guild(g_id)
    if not guild:
        return {"ok": True, "result": False}

    if not guild.chunked:
        bot.loop.create_task(guild.chunk())

    member = guild.get_member(m_id)
    if not member:
        return {"ok": True, "result": False}

    if member.guild_permissions.manage_guild:
        ...

    return {"ok": True, "result": True}

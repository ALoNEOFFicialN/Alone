import models


async def cache(bot):
    # until we implement redis

    records = await models.Guild.all()
    bot.guild_data = {}

    for record in records:
        bot.guild_data[record.guild_id] = {
            "prefix": record.prefix,
            "color": record.embed_color,
            "footer": record.embed_footer,
        }

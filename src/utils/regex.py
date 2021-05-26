import re

"""
Regex compiled by pythondiscord.com
Helper regex for moderation
"""

INVITE_RE = re.compile(
    r"(?:discord(?:[\.,]|dot)gg|"  # Could be discord.gg/
    r"discord(?:[\.,]|dot)com(?:\/|slash)invite|"  # or discord.com/invite/
    r"discordapp(?:[\.,]|dot)com(?:\/|slash)invite|"  # or discordapp.com/invite/
    r"discord(?:[\.,]|dot)me|"  # or discord.me
    r"discord(?:[\.,]|dot)io"  # or discord.io.
    r")(?:[\/]|slash)"  # / or 'slash'
    r"([a-zA-Z0-9\-]+)",  # the invite code itself
    flags=re.IGNORECASE,
)


TIME_REGEX = re.compile(r"(?:(\d{1,5})(h|s|m|d))+?")

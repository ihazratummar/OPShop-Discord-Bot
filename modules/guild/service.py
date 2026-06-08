import discord
import re
from core.database import Database
from modules.guild.model import GuildSettings


CUSTOM_EMOJI_REGEX = re.compile(r'^<a?:\w{2,32}:(\d{17,20})>$')

# Matches most Unicode emoji (Emoji_Presentation + modifiers + ZWJ sequences)
UNICODE_EMOJI_REGEX = re.compile(
    "["
    "\U0001F600-\U0001F64F"  # Emoticons
    "\U0001F300-\U0001F5FF"  # Misc Symbols and Pictographs
    "\U0001F680-\U0001F6FF"  # Transport and Map
    "\U0001F1E0-\U0001F1FF"  # Regional Indicators (Flags)
    "\U00002702-\U000027B0"  # Dingbats
    "\U0000FE00-\U0000FE0F"  # Variation Selectors
    "\U0001F900-\U0001F9FF"  # Supplemental Symbols
    "\U0001FA00-\U0001FA6F"  # Chess Symbols
    "\U0001FA70-\U0001FAFF"  # Symbols Extended-A
    "\U00002600-\U000026FF"  # Misc symbols (☀, ⚡, etc.)
    "\U0000200D"             # ZWJ
    "\U00002B50"             # Star ⭐
    "\U0000231A-\U0000231B"  # Watch, Hourglass
    "\U000023E9-\U000023F3"  # Various symbols
    "\U000023F8-\U000023FA"  # Various symbols
    "\U000025AA-\U000025AB"  # Squares
    "\U000025B6\U000025C0"   # Play buttons
    "\U000025FB-\U000025FE"  # Squares
    "\U00003030\U0000303D"   # Wavy dash, etc
    "\U00003297\U00003299"   # Circled Ideograph
    "]+",
    flags=re.UNICODE
)


class EmojiUtils:
    """Centralized emoji validation and conversion for both Unicode and custom Discord emojis."""

    @staticmethod
    def is_valid_unicode_emoji(value: str) -> bool:
        """Check if the string is a valid Unicode emoji (single or sequence)."""
        if not value or not value.strip():
            return False
        cleaned = value.strip()
        # Emojis are at most ~12 codepoints with ZWJ sequences
        if len(cleaned) > 20:
            return False
        return bool(UNICODE_EMOJI_REGEX.fullmatch(cleaned))

    @staticmethod
    def parse_custom_emoji(value: str) -> int | None:
        """Extract emoji ID from custom emoji string. Returns None if not custom format."""
        if not value:
            return None
        match = CUSTOM_EMOJI_REGEX.match(value.strip())
        return int(match.group(1)) if match else None

    @staticmethod
    def validate_emoji(value: str | None, guild: discord.Guild = None) -> str | None:
        """
        Validate and normalize an emoji string.

        Returns:
            - The cleaned emoji string if valid (Unicode or custom)
            - None if invalid or empty

        For custom emojis, optionally validates against the guild's emoji list.
        """
        if not value or not value.strip():
            return None

        cleaned = value.strip()

        # Check custom emoji first
        emoji_id = EmojiUtils.parse_custom_emoji(cleaned)
        if emoji_id is not None:
            if guild:
                emoji_obj = guild.get_emoji(emoji_id)
                if emoji_obj is None:
                    return None  # Custom emoji not found in guild
            return cleaned  # Valid custom emoji format

        # Check Unicode emoji
        if EmojiUtils.is_valid_unicode_emoji(cleaned):
            return cleaned

        return None  # Not a valid emoji

    @staticmethod
    def safe_emoji_for_component(
        value: str | None,
        fallback: str = "📁",
        guild: discord.Guild = None
    ) -> str | discord.PartialEmoji:
        """
        Convert a stored emoji string to a safe value for Discord UI components
        (SelectOption, Button, etc.).

        Returns:
            - Unicode string for default emojis
            - discord.PartialEmoji for custom emojis
            - fallback string if invalid/None
        """
        if not value or not value.strip():
            return fallback

        cleaned = value.strip()

        # Custom emoji → PartialEmoji
        emoji_id = EmojiUtils.parse_custom_emoji(cleaned)
        if emoji_id is not None:
            match = CUSTOM_EMOJI_REGEX.match(cleaned)
            if match:
                animated = cleaned.startswith("<a:")
                name = cleaned.split(":")[1]
                return discord.PartialEmoji(name=name, id=emoji_id, animated=animated)
            return fallback

        # Unicode emoji — return as-is
        if EmojiUtils.is_valid_unicode_emoji(cleaned):
            return cleaned

        return fallback


class GuildSettingService:

    @staticmethod
    async def get_guild_settings(guild: discord.Guild) -> GuildSettings:
        doc = await Database.guild_settings().find_one({"guild_id": guild.id})

        if doc:
            return GuildSettings(**doc)

        # return default settings object
        return GuildSettings(guild_id=guild.id)

    @staticmethod
    async def get_seller_roles(guild: discord.Guild) -> list[discord.Role]:
        guild_settings = await GuildSettingService.get_guild_settings(guild)
        seller_roles = []
        if guild_settings and guild_settings.seller_role_ids:
            for role_id in guild_settings.seller_role_ids:
                role = guild.get_role(role_id)
                if role:
                    seller_roles.append(role)
        return seller_roles

    @staticmethod
    def get_server_emoji(emoji_id: int | str, guild: discord.Guild) -> discord.Emoji | None:
        if isinstance(emoji_id, int) or str(emoji_id).isdigit():
            emoji = guild.get_emoji(int(emoji_id))
            if emoji:
                return emoji
            return discord.utils.get(guild._state.emojis, id=int(emoji_id))
        else:
            name = str(emoji_id)
            emoji = discord.utils.get(guild.emojis, name=name)
            if emoji:
                return emoji
            return discord.utils.get(guild._state.emojis, name=name)





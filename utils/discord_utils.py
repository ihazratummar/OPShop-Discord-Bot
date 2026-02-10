import asyncio

import discord
from datetime import datetime
from loguru import logger

# Module-level cooldown tracker
_channel_edit_cooldowns = {}
_COOLDOWN_SECONDS = 300

def can_edit_channel_name(channel_id: int) -> bool:
    """Check if channel name can be edited.(10 minute cooldown)"""

    if channel_id not in _channel_edit_cooldowns:
        return True

    last_edit = _channel_edit_cooldowns[channel_id]
    return (datetime.now() - last_edit).total_seconds() >= _COOLDOWN_SECONDS


def get_cooldown_remaining(channel_id: int) -> float:
    """Get remaining cooldown time in seconds"""
    if channel_id not in _channel_edit_cooldowns:
        return 0.0

    elapsed = (datetime.now() - _channel_edit_cooldowns[channel_id]).total_seconds()
    return max(0.0, _COOLDOWN_SECONDS - elapsed)


async def safe_channel_edit(
        channel: discord.TextChannel,
        overwrites=None,
        name=None,
        wait_for_cooldown=False
):
    """
    Safely edit channel with rate limit handling.
    Prioritizes permission changes over name changes.

    Args:
        channel : The Discord text channel to edit
        overwrites : A dictionary with permissions to edit channel
        name : The name of the channel to edit
        wait_for_cooldown : Whether or not to wait for cooldown
    """

    try:
        ## Always update permission first (critical)

        if overwrites:
            await channel.edit(overwrites=overwrites)
            logger.info(f"Successfully edited channel {channel.id}")

        # Handle name change
        if name:
            if can_edit_channel_name(channel_id=channel.id):
                await channel.edit(name=name)
                _channel_edit_cooldowns[channel.id] = datetime.now()
                logger.info(f"Successfully edited channel {channel.id}")
            else:
                cooldown_remaining = get_cooldown_remaining(channel_id=channel.id)

                if wait_for_cooldown:
                    logger.info(f"Waiting {cooldown_remaining:.0f}s before remaining channel {channel.id}")
                    await asyncio.sleep(cooldown_remaining +1) # +1 for safety margin

                    existing_channel = channel.guild.get_channel(channel.id)
                    if existing_channel is None:
                        logger.warning(f"Channel {channel.id} was deleted during cooldown")
                        # Clean up cooldown tracker since channel no loger exists
                        _channel_edit_cooldowns.pop(channel.id, None)
                        return

                    # Retry name change after cooldown
                    await channel.edit(name=name)
                    _channel_edit_cooldowns[channel.id] = datetime.now()
                    logger.info(f"Channel {channel.id} renamed to '{name}' after cooldown")
                else:
                    logger.info(f"Skipped channel rename - cooldown active ({cooldown_remaining:.0f}s remaining)")

    except discord.NotFound:
        # Channel was deleted
        logger.warning(f"Channel {channel.id} was deleted during cooldown")
        _channel_edit_cooldowns.pop(channel.id, None)

    except discord.HTTPException as e:
        if e.status == 429:
            logger.error(f"Rate limited on channel {channel.id}: {e}")
            _channel_edit_cooldowns[channel.id] = datetime.now()
        else:
            logger.error(f"Failed to edit channel {channel.id}: {e}")
            raise


def clear_channel_cooldown(channel_id: int):
    """Manually clean cooldown for a channel (use sparingly)"""
    if channel_id in _channel_edit_cooldowns:
        del _channel_edit_cooldowns[channel_id]

import discord
from discord.utils import get
from datetime import datetime
from loguru import logger


class AuditLogService:
    @staticmethod
    async def log_action(action_type: str, user: discord.User, details: str, guild: discord.Guild):
        """
        Log an action to the audit-logs channel.
        """
        if not guild:
            return

        channel = get(guild.text_channels, name="audit-logs")
        if not channel:
            # Try alt name
            channel = get(guild.text_channels, name="admin-logs")
        
        if not channel:
            logger.warning(f"Audit log channel not found in guild {guild.name}")
            return

        color = discord.Color.blue()
        if "delete" in action_type.lower() or "remove" in action_type.lower():
            color = discord.Color.red()
        elif "create" in action_type.lower() or "add" in action_type.lower():
            color = discord.Color.green()
        elif "update" in action_type.lower() or "edit" in action_type.lower():
            color = discord.Color.orange()

        embed = discord.Embed(
            title=f"Audit Log: {action_type}",
            description=details,
            color=color,
            timestamp=datetime.utcnow()
        )
        embed.set_author(name=f"{user.display_name} ({user.id})", icon_url=user.avatar.url if user.avatar else None)
        embed.set_footer(text="OP Shop Audit System")

        try:
            await channel.send(embed=embed)
        except Exception as e:
            logger.error(f"Failed to send audit log: {e}")

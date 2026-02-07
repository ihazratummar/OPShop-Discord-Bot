import discord


def embed_builder(
        title: str,
        description: str = None,
        color: discord.Color = discord.Color.red(),
        fields: list[tuple[str, str, bool]] = None,
        footer: tuple[str, str] = None,
        thumbnail: str = None,
        image_url: str = None
) -> discord.Embed:
    embed = discord.Embed(
        title=title,
        description=description if description else None,
        color=color
    )
    if fields:
        for name, value, inline in fields:
            embed.add_field(name=name, value=value, inline=inline)

    if footer:
        footer_text, icon_url = footer
        embed.set_footer(text=footer_text, icon_url=icon_url)

    if thumbnail:
        embed.set_thumbnail(url=thumbnail)
    if image_url:
        embed.set_image(url=image_url)

    return embed


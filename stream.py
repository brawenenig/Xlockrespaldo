import discord
from discord import app_commands, ui
from discord.ext import commands
from supabase import create_client, Client
url='https://ivygaxznxndtwyziklrz.supabase.co'
key='eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Iml2eWdheHpueG5kdHd5emlrbHJ6Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDg0NzcwMzMsImV4cCI6MjA2NDA1MzAzM30.E7B-cdA5hySuhrwIGO2UPwlA5rzJIK0HzoZq8K_l2E0'
supabase: Client = create_client(url, key)

class Stream(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    @app_commands.command(name="stream", description="Stream a game being played")
    @app_commands.describe(link="The link to your stream")
    @app_commands.checks.bot_has_permissions(view_channel=True, embed_links=True, attach_files=True)
    async def stream(
        self,
        interaction: discord.Interaction,
        link: str
    ):
        guild = interaction.guild
        channel = discord.utils.get(guild.text_channels, name="streams")

        if channel is None:
            return await interaction.response.send_message(
                content="No streams channel is set up.",
                ephemeral=True
            )

        perms = channel.permissions_for(guild.me)
        needed = ["view_channel", "send_messages", "embed_links", "attach_files"]
        missing = [perm for perm in needed if not getattr(perms, perm)]
        if missing:
            return await interaction.response.send_message(
                content=f"Missing permissions in {channel.mention}: {', '.join(missing)}",
                ephemeral=True
            )

        await interaction.response.send_message(
            content="Sending stream...",
            ephemeral=True,
            suppress_embeds=True
        )

        embed = discord.Embed(
            description=(
                f"{guild.name} Stream\n"
                f"**Streamer:** {interaction.user.mention}"
            ),
            color=discord.Color.blue()
        )
        embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)

        view = ui.View()
        if link:
            view.add_item(ui.Button(label="Watch Stream", style=discord.ButtonStyle.url, url=link))

        try:
            message = await channel.send(content="@here", embed=embed, view=view)
        except discord.HTTPException:
            return await interaction.edit_original_response(
                content=f"Failed to send the message in {channel.mention}.",
            )

        await interaction.edit_original_response(content=f"Stream message sent. View message -> {message.jump_url}")

async def setup(bot: commands.Bot):
    await bot.add_cog(Stream(bot))

import discord
import supabase
from discord.ext import commands
from discord import app_commands
from supabase import create_client, Client

url = 'https://ivygaxznxndtwyziklrz.supabase.co'
key = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Iml2eWdheHpueG5kdHd5emlrbHJ6Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDg0NzcwMzMsImV4cCI6MjA2NDA1MzAzM30.E7B-cdA5hySuhrwIGO2UPwlA5rzJIK0HzoZq8K_l2E0'
supabase: Client = create_client(url, key)

class Ban(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name='ban', description='Ban a member from your server.')
    @app_commands.describe(member='The member to ban.', reason='The reason for banning the member.')
    async def ban(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
        if not interaction.user.guild_permissions.ban_members:
            await interaction.response.send_message("**You do not have permission to ban members.**", ephemeral=True)
            return

        try:
            await member.ban(reason=reason)
            await interaction.response.send_message(
                f"**{member.mention} has been banned from the server.**\n**Reason:** {reason}", ephemeral=True
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                "**I do not have permission to ban this member.**", ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                f"**An error occurred while trying to ban the member:** {str(e)}", ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(Ban(bot))
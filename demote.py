import discord
from discord.ext import commands
from discord import app_commands
from supabase import create_client, Client

url = 'https://ivygaxznxndtwyziklrz.supabase.co'
key = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Iml2eWdheHpueG5kdHd5emlrbHJ6Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDg0NzcwMzMsImV4cCI6MjA2NDA1MzAzM30.E7B-cdA5hySuhrwIGO2UPwlA5rzJIK0HzoZq8K_l2E0'
supabase: Client = create_client(url, key)

class demote(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name='demote', description='Demote a franchise owner from their team.')
    async def demote(self, interaction: discord.Interaction, user: discord.Member):
        await interaction.response.defer(ephemeral=True)

        serverdb = supabase.table('servers').select('*').eq('guild_id', interaction.guild.id).execute()
        staffrole = serverdb.data[0]['staff']
        owner_role_id = serverdb.data[0]['fowner']

        if owner_role_id is None:
            error = discord.Embed(
                title='<:offline:1352790185523282004> Error Detected',
                description=f'\n>>> Please run `/setup` and set `Franchise Owner`.',
                color=0x8B0000
            )
            await interaction.followup.send(embed=error, ephemeral=True)
            return

        staffr = interaction.guild.get_role(staffrole)
        if not (staffr in interaction.user.roles or interaction.user.guild_permissions.administrator):
            await interaction.followup.send('❌ | Invalid Permission.', ephemeral=True)
            return

        team_data = supabase.table('teams').select('*').eq('owner', user.id).eq('guild', interaction.guild.id).execute()
        if not team_data.data:
            error = discord.Embed(
                title='<:offline:1352790185523282004> Error Detected',
                description=f'\n>>> The user is not listed as the owner of any team.',
                color=0x8B0000
            )
            await interaction.followup.send(embed=error, ephemeral=True)
            return

        team = team_data.data
        team_role = interaction.guild.get_role(int(team[0]['role']))

        try:
            owner_role = interaction.guild.get_role(int(owner_role_id))
            if owner_role:
                await user.remove_roles(owner_role)
            if team_role:
                if interaction.guild.me.top_role > team_role:
                    try:
                        await user.remove_roles(team_role)
                        print(f"Removed team role: {team_role.name} from {user.name}")
                    except discord.Forbidden:
                        await interaction.followup.send(
                            "❌ | The bot does not have permission to remove the team role. Please check the role hierarchy.",
                            ephemeral=True
                        )
                        return
                else:
                    await interaction.followup.send(
                        "❌ | The bot's role must be higher than the team role in the role hierarchy to remove it.",
                        ephemeral=True
                    )
                    return
            else:
                print("Team role not found or invalid.")

            supabase.table('teams').update({'owner': None}).eq('role', team[0]['role']).execute()
            await interaction.followup.send('<a:Online:1352470565021290506> | User has been demoted.', ephemeral=True)
        except discord.Forbidden:
            error = discord.Embed(
                title='<:offline:1352790185523282004> Error Detected',
                description=f'\n>>> Please make sure the bot\'s role is above the roles you are trying to remove.',
                color=0x8B0000
            )
            await interaction.followup.send(embed=error, ephemeral=True)
            return

async def setup(bot):
    await bot.add_cog(demote(bot))
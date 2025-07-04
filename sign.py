import discord
from discord.ext import commands
from discord import app_commands
from supabase import create_client, Client
from datetime import datetime

url = 'https://ivygaxznxndtwyziklrz.supabase.co'
key = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Iml2eWdheHpueG5kdHd5emlrbHJ6Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDg0NzcwMzMsImV4cCI6MjA2NDA1MzAzM30.E7B-cdA5hySuhrwIGO2UPwlA5rzJIK0HzoZq8K_l2E0'
supabase: Client = create_client(url, key)

class Sign(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="sign", description="Fichar a un jugador para un equipo (Solo admins)")
    @app_commands.describe(
        team="Equipo al que fichar al jugador",
        player="Jugador a fichar"
    )
    @app_commands.default_permissions(administrator=True)
    async def sign(self, interaction: discord.Interaction, team: discord.Role, player: discord.Member):
        try:
            # Verificar permisos de administrador
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message(
                    "❌ Solo los administradores pueden usar este comando.",
                    ephemeral=True
                )
                return

            # Verificar que no se está fichando a sí mismo
            if player == interaction.user:
                await interaction.response.send_message(
                    "❌ No puedes ficharte a ti mismo.",
                    ephemeral=True
                )
                return

            # Verificar si el sistema de fichajes está activado
            server_config = supabase.table('servers').select('sign').eq('guild_id', str(interaction.guild.id)).execute()
            if not server_config.data or not server_config.data[0]['sign']:
                await interaction.response.send_message(
                    "❌ El sistema de fichajes está desactivado en este servidor.",
                    ephemeral=True
                )
                return

            # Verificar que el rol es un equipo registrado
            team_data = supabase.table('teams').select('*').eq('role', str(team.id)).eq('guild', str(interaction.guild.id)).execute()
            if not team_data.data:
                await interaction.response.send_message(
                    "❌ El rol seleccionado no es un equipo registrado.",
                    ephemeral=True
                )
                return

            team_data = team_data.data[0]

            # Verificar canal de transacciones
            trans_channel = supabase.table('servers').select('TransChannel').eq('guild_id', str(interaction.guild.id)).execute()
            if not trans_channel.data or not trans_channel.data[0]['TransChannel']:
                await interaction.response.send_message(
                    "❌ No hay canal de transacciones configurado. Usa /setup primero.",
                    ephemeral=True
                )
                return

            channel = interaction.guild.get_channel(int(trans_channel.data[0]['TransChannel']))
            if not channel:
                await interaction.response.send_message(
                    "❌ No se encontró el canal de transacciones configurado.",
                    ephemeral=True
                )
                return

            # Verificar que el jugador no está en otro equipo
            all_teams = supabase.table('teams').select('role').eq('guild', str(interaction.guild.id)).execute()
            for team_role in all_teams.data:
                if interaction.guild.get_role(int(team_role['role'])) in player.roles:
                    await interaction.response.send_message(
                        "❌ El jugador ya pertenece a otro equipo.",
                        ephemeral=True
                    )
                    return

            # Obtener datos del equipo
            emoji = team_data['emoji']
            emoji_id = str(emoji).split(":")[-1][:-1] if ":" in emoji else None
            emoji_url = f"https://cdn.discordapp.com/emojis/{emoji_id}.png?size=96" if emoji_id else None
            
            # Obtener roster cap
            roster_cap = supabase.table('servers').select('rcap').eq('guild_id', str(interaction.guild.id)).execute()
            roster_cap = roster_cap.data[0].get('rcap', 20) if roster_cap.data else 20

            # Obtener DT del equipo
            dt = interaction.guild.get_member(int(team_data['owner'])) if team_data.get('owner') else None

            # Fichar al jugador
            await player.add_roles(team)

            # Crear embed de fichaje al estilo XY Lock
            embed = discord.Embed(
                title="✅ Jugador Fichado",
                description=(
                    f"**{team.name}** ha fichado a {player.mention} `{player.display_name}`!\n\n"
                    f"> **Coach:** {dt.mention if dt else 'No asignado'} `{dt.display_name if dt else 'N/A'}`\n"
                    f"> **Roster:** {len(team.members)}/{roster_cap}"
                ),
                color=team.color
            )
            
            if emoji_url:
                embed.set_thumbnail(url=emoji_url)
            
            embed.set_footer(
                text=f"XY Lock APP • Fichaje realizado por {interaction.user.display_name}",
                icon_url=interaction.user.display_avatar.url
            )

            # Enviar confirmación al canal de transacciones
            await channel.send(embed=embed)
            
            # Notificar al jugador
            try:
                player_embed = discord.Embed(
                    title="🎉 ¡Has sido fichado!",
                    description=(
                        f"Has sido fichado por **{interaction.user.mention}** para el equipo:\n\n"
                        f"**{emoji} {team.name}**\n"
                        f"> **Coach:** {dt.mention if dt else 'No asignado'}\n"
                        f"> **Roster actual:** {len(team.members)}/{roster_cap}"
                    ),
                    color=team.color
                )
                if emoji_url:
                    player_embed.set_thumbnail(url=emoji_url)
                await player.send(embed=player_embed)
            except discord.Forbidden:
                pass  # El usuario tiene los DMs cerrados

            await interaction.response.send_message(
                f"✅ Has fichado a {player.mention} para {team.mention}.",
                ephemeral=True
            )

        except Exception as e:
            await interaction.response.send_message(
                f"❌ Ocurrió un error al procesar el fichaje: {str(e)}",
                ephemeral=True
            )
            print(f"Error en comando sign: {e}")

async def setup(bot):
    await bot.add_cog(Sign(bot))

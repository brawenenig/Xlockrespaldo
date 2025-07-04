import discord
from discord.ext import commands
from discord import app_commands
from supabase import create_client, Client
from datetime import datetime

url = 'https://ivygaxznxndtwyziklrz.supabase.co'
key = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Iml2eWdheHpueG5kdHd5emlrbHJ6Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDg0NzcwMzMsImV4cCI6MjA2NDA1MzAzM30.E7B-cdA5hySuhrwIGO2UPwlA5rzJIK0HzoZq8K_l2E0'
supabase: Client = create_client(url, key)

class Kick(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name='kick', description='Expulsar a un jugador de tu equipo')
    @app_commands.describe(
        jugador='El jugador a expulsar del equipo',
        motivo='Motivo de la expulsión (opcional)'
    )
    async def kick(self, interaction: discord.Interaction, jugador: discord.Member, motivo: str = None):
        try:
            # Verificar que el usuario es DT/sub-DT de algún equipo
            response = supabase.table('teams').select('*').or_(
                f"owner.eq.{interaction.user.id},coach.eq.{interaction.user.id},general.eq.{interaction.user.id}"
            ).eq('guild', str(interaction.guild.id)).execute()
            
            if not response.data:
                # Buscar si el usuario es sub-DT
                all_teams = supabase.table('teams').select('*').eq('guild', str(interaction.guild.id)).execute()
                user_teams = [team for team in all_teams.data if str(interaction.user.id) in team.get('subdts', [])]
                
                if not user_teams:
                    await interaction.response.send_message("❌ No tienes permiso para expulsar jugadores.", ephemeral=True)
                    return
                
                team_data = user_teams[0]
            else:
                team_data = response.data[0]

            # Verificar que el jugador pertenece al equipo
            team_role = interaction.guild.get_role(int(team_data['role']))
            if team_role not in jugador.roles:
                await interaction.response.send_message("❌ El jugador no pertenece a tu equipo.", ephemeral=True)
                return

            # Obtener datos para el embed
            emoji = team_data['emoji']
            emoji_id = str(emoji).split(":")[-1][:-1] if ":" in emoji else None
            emoji_url = f"https://cdn.discordapp.com/emojis/{emoji_id}.png?size=96" if emoji_id else None
            
            # Obtener roster cap
            config = supabase.table('servers').select('rcap').eq('guild_id', str(interaction.guild.id)).execute()
            roster_cap = config.data[0].get('rcap', 20) if config.data else 20
            
            # Obtener DT del equipo
            dt = interaction.guild.get_member(int(team_data['owner'])) if team_data.get('owner') else None

            # Remover el rol del equipo al jugador
            await jugador.remove_roles(team_role)
            
            # Crear embed de notificación al estilo XY Lock
            embed = discord.Embed(
                title="🚪 Jugador Expulsado",
                description=(
                    f"**{interaction.user.mention}** ha expulsado a **{jugador.mention}** del equipo:\n\n"
                    f"**{emoji} {team_role.name}**\n"
                    f"> **Coach:** {dt.mention if dt else 'No asignado'}\n"
                    f"> **Roster actual:** {len(team_role.members)}/{roster_cap}"
                ),
                color=0xe74c3c  # Rojo
            )
            
            if emoji_url:
                embed.set_thumbnail(url=emoji_url)
            
            if motivo:
                embed.add_field(name="📄 Motivo", value=motivo, inline=False)
            
            # Añadir fecha y hora en el footer
            now = datetime.now()
            fecha_hora = now.strftime("%d/%m/%Y %I:%M %p").lower()
            embed.set_footer(
                text=f"XY Lock APP • {fecha_hora}",
                icon_url=interaction.user.display_avatar.url
            )

            # Función para enviar a los canales correspondientes
            async def send_to_channels(embed):
                # Obtener canales específicos
                config = supabase.table('servers').select('releaseChannel, TransChannel').eq('guild_id', str(interaction.guild.id)).execute()
                
                channels = []
                if config.data:
                    # Priorizar releaseChannel, si no existe usar TransChannel
                    if config.data[0].get('releaseChannel'):
                        channel = interaction.guild.get_channel(int(config.data[0]['releaseChannel']))
                        if channel:
                            channels.append(channel)
                    elif config.data[0].get('TransChannel'):
                        channel = interaction.guild.get_channel(int(config.data[0]['TransChannel']))
                        if channel:
                            channels.append(channel)
                
                if not channels:
                    print("No se encontraron canales configurados para enviar la notificación")
                    return
                
                for channel in channels:
                    try:
                        print(f"Enviando notificación a canal {channel.name} ({channel.id})")
                        await channel.send(embed=embed)
                    except discord.HTTPException as e:
                        print(f"No se pudo enviar mensaje al canal {channel.id}: {str(e)}")
                        continue

            # Enviar notificación a los canales correspondientes
            await send_to_channels(embed)
            
            # Notificar al jugador expulsado
            try:
                user_embed = discord.Embed(
                    title="🚪 Has sido expulsado",
                    description=(
                        f"Has sido expulsado de **{team_role.name}** por {interaction.user.mention}.\n\n"
                        f"Si crees que esto es un error, contacta con el DT del equipo."
                    ),
                    color=0xe74c3c
                )
                if motivo:
                    user_embed.add_field(name="Motivo de expulsión", value=motivo, inline=False)
                if emoji_url:
                    user_embed.set_thumbnail(url=emoji_url)
                await jugador.send(embed=user_embed)
            except discord.Forbidden:
                print(f"No se pudo enviar DM a {jugador.display_name}")
                pass  # El usuario tiene los DMs cerrados
            
            await interaction.response.send_message(
                f"✅ Has expulsado a {jugador.mention} de tu equipo.",
                ephemeral=True
            )

        except Exception as e:
            print(f"Error en comando kick: {e}")
            await interaction.response.send_message(
                f"❌ Ocurrió un error al procesar la expulsión: {str(e)}",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(Kick(bot))
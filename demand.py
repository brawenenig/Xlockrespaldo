import discord
from discord.ext import commands
from discord import app_commands
from supabase import create_client, Client
from datetime import datetime

url = 'https://ivygaxznxndtwyziklrz.supabase.co'
key = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Iml2eWdheHpueG5kdHd5emlrbHJ6Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDg0NzcwMzMsImV4cCI6MjA2NDA1MzAzM30.E7B-cdA5hySuhrwIGO2UPwlA5rzJIK0HzoZq8K_l2E0'
supabase: Client = create_client(url, key)

class Demand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name='demand', description='Solicitar salir de un equipo')
    @app_commands.describe(
        motivo="Motivo por el que quieres salir del equipo (opcional)"
    )
    async def demand(self, interaction: discord.Interaction, motivo: str = None):
        try:
            # Verificar si el usuario es DT o sub-DT de algún equipo
            teams_response = supabase.table('teams').select('*').eq('guild', str(interaction.guild.id)).execute()
            
            for team in teams_response.data:
                if str(interaction.user.id) == team.get('owner') or str(interaction.user.id) in team.get('subdts', []):
                    await interaction.response.send_message(
                        "❌ Los directores técnicos y asistentes no pueden solicitar salir de un equipo.",
                        ephemeral=True
                    )
                    return
            
            # Obtener información del equipo del jugador
            if not teams_response.data:
                await interaction.response.send_message("❌ No hay equipos registrados en este servidor.", ephemeral=True)
                return
            
            # Buscar el equipo al que pertenece el jugador
            team_data = None
            team_role = None
            
            for team in teams_response.data:
                role = interaction.guild.get_role(int(team['role']))
                if role and role in interaction.user.roles:
                    team_data = team
                    team_role = role
                    break
            
            if not team_data or not team_role:
                await interaction.response.send_message("❌ No perteneces a ningún equipo.", ephemeral=True)
                return
            
            # Obtener DT del equipo y sub-DTs
            dt = interaction.guild.get_member(int(team_data['owner'])) if team_data.get('owner') else None
            subdts = [interaction.guild.get_member(int(subdt)) for subdt in team_data.get('subdts', []) if interaction.guild.get_member(int(subdt))]
            
            if not dt:
                await interaction.response.send_message("❌ No se encontró al DT del equipo.", ephemeral=True)
                return
            
            # Obtener datos para el embed
            emoji = team_data['emoji']
            emoji_id = str(emoji).split(":")[-1][:-1] if ":" in emoji else None
            emoji_url = f"https://cdn.discordapp.com/emojis/{emoji_id}.png?size=96" if emoji_id else None
            
            # Obtener roster cap
            config = supabase.table('servers').select('rcap').eq('guild_id', str(interaction.guild.id)).execute()
            roster_cap = config.data[0].get('rcap', 20) if config.data else 20
            
            # Crear embed de solicitud al estilo XY Lock (azul oceano)
            embed = discord.Embed(
                title="📝 Solicitud de Salida",
                description=(
                    f"{interaction.user.mention} solicita salir de tu equipo:\n\n"
                    f"**{emoji} {team_role.name}**\n"
                    f"> **Jugadores actuales:** {len(team_role.members)}/{roster_cap}\n"
                    f"> **Coach:** {dt.mention if dt else 'No asignado'}"
                ),
                color=0x3498db  # Azul oceano
            )
            
            if emoji_url:
                embed.set_thumbnail(url=emoji_url)
            
            if motivo:
                embed.add_field(name="📄 Motivo", value=motivo, inline=False)
            
            embed.set_footer(
                text=f"XY Lock APP • Solicitud de {interaction.user.display_name}",
                icon_url=interaction.user.display_avatar.url
            )

            class DemandView(discord.ui.View):
                def __init__(self, bot, team_data: dict, user: discord.Member, guild: discord.Guild, motivo: str = None):
                    super().__init__(timeout=86400)  # 24 horas
                    self.bot = bot
                    self.team_data = team_data
                    self.user = user
                    self.guild = guild
                    self.motivo = motivo
                    self.value = None
                
                async def send_to_release_channel(self, embed: discord.Embed):
                    # Obtener canales específicos
                    config = supabase.table('servers').select('releaseChannel, TransChannel').eq('guild_id', str(self.guild.id)).execute()
                    
                    channels = []
                    if config.data:
                        # Priorizar releaseChannel, si no existe usar TransChannel
                        if config.data[0].get('releaseChannel'):
                            channel = self.guild.get_channel(int(config.data[0]['releaseChannel']))
                            if channel:
                                channels.append(channel)
                        elif config.data[0].get('TransChannel'):
                            channel = self.guild.get_channel(int(config.data[0]['TransChannel']))
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
                
                @discord.ui.button(label="ACEPTAR", style=discord.ButtonStyle.success, emoji="✅")
                async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
                    # Verificar que quien acepta es el DT o sub-DT
                    if str(interaction.user.id) != self.team_data['owner'] and str(interaction.user.id) not in self.team_data.get('subdts', []):
                        await interaction.response.send_message("❌ Solo el DT o sub-DT puede aceptar esta solicitud.", ephemeral=True)
                        return
                    
                    # Remover el rol del equipo al jugador
                    team_role = self.guild.get_role(int(self.team_data['role']))
                    member = self.guild.get_member(self.user.id)
                    
                    if team_role and member:
                        await member.remove_roles(team_role)
                        
                        # Crear embed de confirmación
                        emoji = self.team_data['emoji']
                        emoji_id = str(emoji).split(":")[-1][:-1] if ":" in emoji else None
                        emoji_url = f"https://cdn.discordapp.com/emojis/{emoji_id}.png?size=96" if emoji_id else None

                        embed = discord.Embed(
                            title="✅ Jugador Salido",
                            description=(
                                f"**{interaction.user.mention}** ha aceptado la solicitud de **{self.user.mention}** para salir del equipo:\n\n"
                                f"**{emoji} {team_role.name}**\n"
                                f"> **Jugadores actuales:** {len(team_role.members)}/{roster_cap}"
                            ),
                            color=0x2ecc71  # Verde
                        )
                        
                        if emoji_url:
                            embed.set_thumbnail(url=emoji_url)
                        
                        if self.motivo:
                            embed.add_field(name="📄 Motivo", value=self.motivo, inline=False)
                        
                        embed.set_footer(
                            text="XY Lock APP",
                            icon_url=interaction.user.display_avatar.url
                        )
                        
                        # Enviar a releaseChannel o TransChannel
                        await self.send_to_release_channel(embed)
                        
                        await interaction.response.send_message("✅ Solicitud aceptada. El jugador ha sido removido del equipo.", ephemeral=True)
                        
                        # Notificar al jugador
                        try:
                            user_embed = discord.Embed(
                                title="✅ Solicitud Aceptada",
                                description=f"Tu solicitud para salir de **{team_role.name}** ha sido aceptada por {interaction.user.mention}.",
                                color=0x2ecc71
                            )
                            if self.motivo:
                                user_embed.add_field(name="Motivo registrado", value=self.motivo, inline=False)
                            await self.user.send(embed=user_embed)
                        except discord.Forbidden:
                            print(f"No se pudo enviar DM a {self.user.display_name}")
                            pass  # El usuario tiene los DMs cerrados
                        
                        self.value = True
                        self.stop()
                
                @discord.ui.button(label="RECHAZAR", style=discord.ButtonStyle.danger, emoji="✖️")
                async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
                    # Verificar que quien rechaza es el DT o sub-DT
                    if str(interaction.user.id) != self.team_data['owner'] and str(interaction.user.id) not in self.team_data.get('subdts', []):
                        await interaction.response.send_message("❌ Solo el DT o sub-DT puede rechazar esta solicitud.", ephemeral=True)
                        return
                    
                    team_role = self.guild.get_role(int(self.team_data['role']))
                    
                    await interaction.response.send_message("❌ Solicitud rechazada.", ephemeral=True)
                    
                    # Notificar al jugador
                    try:
                        user_embed = discord.Embed(
                            title="❌ Solicitud Rechazada",
                            description=f"Tu solicitud para salir de **{team_role.name}** ha sido rechazada por {interaction.user.mention}.",
                            color=0xe74c3c
                        )
                        if self.motivo:
                            user_embed.add_field(name="Motivo que proporcionaste", value=self.motivo, inline=False)
                        await self.user.send(embed=user_embed)
                    except discord.Forbidden:
                        print(f"No se pudo enviar DM a {self.user.display_name}")
                        pass  # El usuario tiene los DMs cerrados
                    
                    self.value = False
                    self.stop()
            
            # Enviar solicitud al DT y sub-DTs por DM
            recipients = [dt] + subdts
            sent_to = []
            failed_to_send = []
            
            for recipient in recipients:
                try:
                    if recipient:
                        await recipient.send(
                            embed=embed,
                            view=DemandView(self.bot, team_data, interaction.user, interaction.guild, motivo)
                        )
                        sent_to.append(recipient.mention)
                except (discord.Forbidden, discord.HTTPException) as e:
                    if isinstance(e, discord.Forbidden):
                        failed_to_send.append(recipient.display_name if recipient else "Usuario desconocido")
                    continue
            
            if not sent_to:
                await interaction.response.send_message(
                    "❌ No se pudo enviar la solicitud. El DT y sub-DTs tienen los mensajes privados desactivados.",
                    ephemeral=True
                )
            else:
                response_msg = f"✅ Tu solicitud de salida ha sido enviada a: {' '.join(sent_to)}"
                
                if failed_to_send:
                    response_msg += f"\n\n⚠️ No se pudo enviar a: {', '.join(failed_to_send)} (mensajes privados desactivados)"
                
                await interaction.response.send_message(
                    response_msg,
                    ephemeral=True
                )
        
        except Exception as e:
            print(f"Error en comando demand: {e}")
            await interaction.response.send_message(
                f"❌ Ocurrió un error al procesar tu solicitud: {str(e)}",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(Demand(bot))